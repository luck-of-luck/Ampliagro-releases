# -*- coding: utf-8 -*-
"""O publisher tem de RECUSAR mais do que aceita.

Porque estes testes são quase todos de recusa
============================================
Um teste de publicação que só prova "publicou" é um teste que não vale nada:
a função mais insegura do mundo também publica. O que interessa é o que ela
recusa, porque o dano de um publisher é uma válvula a abrir na propriedade
errada, ou a abrir quando já não há motivo.

O broker é injectado em todos os testes: nenhum toca em `paho`, nenhum abre
socket, nenhum precisa de `paho-mqtt` instalado. O que se testa é a
autorização, que é a parte que decide.
"""

from __future__ import annotations

import os
from datetime import timedelta
from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from app.iot import publicar as pub
from app.models import (
    AlertaTelemetria,
    ComandoDevice,
    Device,
    Propriedade,
    RegraAlertaTelemetria,
)


class _Base(TestCase):
    def setUp(self):
        self.a = User.objects.create_user("dono_a", password="x")
        self.b = User.objects.create_user("dono_b", password="x")
        self.prop_a = Propriedade.objects.create(
            user=self.a, nome="Faz A", area_total=10, uf="MT", cidade="X"
        )
        self.prop_b = Propriedade.objects.create(
            user=self.b, nome="Faz B", area_total=10, uf="MT", cidade="X"
        )
        self.dev_a = Device.objects.create(
            propriedade=self.prop_a, device_eui="EUIPAA01", nome="Valvula A"
        )
        self.dev_b = Device.objects.create(
            propriedade=self.prop_b, device_eui="EUIPBB01", nome="Valvula B"
        )
        self.regra = RegraAlertaTelemetria.objects.create(
            propriedade=self.prop_a,
            nome="Solo seco",
            metric="umidade_solo",
            tipo="threshold_min",
            valor_ref=20,
            acao_fisica="abrir_valvula",
        )

    def _alerta_vivo(self, regra=None, device=None):
        """O alerta por resolver: a prova de que a condição ainda se cumpre."""
        return AlertaTelemetria.objects.create(
            regra=regra or self.regra,
            propriedade=(regra or self.regra).propriedade,
            device=device or self.dev_a,
            metric="umidade_solo",
            valor=5,
            severidade="warning",
            mensagem="seca",
            timestamp=timezone.now(),
        )

    def _cmd(self, device=None, regra=None, **kw):
        payload = kw.pop(
            "payload", {"via": "regra_auto", "regra_id": (regra or self.regra).id}
        )
        return ComandoDevice.objects.create(
            device=device or self.dev_a,
            comando=kw.pop("comando", "valve_open"),
            payload=payload,
            expira_em=kw.pop("expira_em", timezone.now() + timedelta(minutes=30)),
            **kw,
        )

    def _publicado(self):
        """Um `publicar_fn` que regista o que saiu, sem broker nenhum."""
        calls = []

        def _fn(topico, corpo):
            calls.append((topico, corpo))

        return _fn, calls


class AutorizacaoTest(_Base):
    """O que tem de estar certo para o comando sair."""

    def test_tudo_em_ordem_publica(self):
        self._alerta_vivo()
        cmd = self._cmd()
        fn, calls = self._publicado()
        rel = pub.publicar(publicar_fn=fn)
        cmd.refresh_from_db()
        self.assertEqual(rel["publicados"], 1)
        self.assertEqual(cmd.status, "enviado")
        self.assertIsNotNone(cmd.enviado_em)
        self.assertEqual(len(calls), 1)

    def test_o_topico_segue_o_esquema_do_listener(self):
        # `mqtt_listener` assina `ampliagro/+/+/+/telemetry`. Se o downlink
        # usasse outro esquema, a ACL do broker nao conseguia cortar o que
        # nao e' telemetria — e a separacao entre leitura e accao perde-se.
        self._alerta_vivo()
        cmd = self._cmd()
        self.assertTrue(pub.topico_de(cmd).endswith(f"/{cmd.device.device_eui}/cmd"))

    def test_sem_regra_que_o_autorize_e_recusado(self):
        # Fail-closed: um comando que nao se sabe de onde veio nao sai.
        self._alerta_vivo()
        cmd = self._cmd(payload={"via": "manual"})
        with self.assertRaises(pub.Recusado) as e:
            pub.autorizar(cmd)
        self.assertIn("regra", e.exception.motivo)

    def test_regra_desativada_e_recusada(self):
        # O produtor desligou a regra depois de o comando ter nascido. A
        # intention dele deixou de existir; publicar seria desobedecer.
        self._alerta_vivo()
        self.regra.ativa = False
        self.regra.save(update_fields=["ativa"])
        with self.assertRaises(pub.Recusado):
            pub.autorizar(self._cmd())

    def test_regra_de_outra_propriedade_e_recusada(self):
        # O teste que vale mais. A regra e' de A; o device e' de B. Se isto
        # passar, uma regra configurada na fazenda A abre a valvula da B.
        self._alerta_vivo()
        with self.assertRaises(pub.Recusado) as e:
            pub.autorizar(self._cmd(device=self.dev_b))
        self.assertIn("propriedade", e.exception.motivo)

    def test_leitura_normalizada_e_recusada(self):
        # O alerta foi auto-resolvido: a chuva chegou, a solo húmido, e já
        # nao ha motivo para abrir a valvula. E' a recusa mais importante do
        # ficheiro, porque e' a que impede agua desperdicada.
        alerta = self._alerta_vivo()
        alerta.resolvido = True
        alerta.save(update_fields=["resolvido"])
        with self.assertRaises(pub.Recusado) as e:
            pub.autorizar(self._cmd())
        self.assertIn("normalizou", e.exception.motivo)

    def test_comando_incoerente_com_a_regra_e_recusado(self):
        # A regra diz "abre"; o comando diz "fechar". Um mapeamento por
        # traducao publicaria o comando errado em vez de recusar.
        self._alerta_vivo()
        with self.assertRaises(pub.Recusado):
            pub.autorizar(self._cmd(comando="valve_close"))

    def test_regra_sem_acao_publicavel_e_recusada(self):
        # As 18 das 20 REGRAS_AUTO nao tem acao_fisica. Se um dia uma delas a
        # ganhar, o comando tem de sair pela via do alerta, nao por downlink.
        self._alerta_vivo()
        self.regra.acao_fisica = ""
        self.regra.save(update_fields=["acao_fisica"])
        with self.assertRaises(pub.Recusado):
            pub.autorizar(self._cmd())

    def test_regra_inexistente_e_recusada(self):
        self._alerta_vivo()
        with self.assertRaises(pub.Recusado):
            pub.autorizar(self._cmd(payload={"via": "regra_auto", "regra_id": 999999}))

    def test_expirado_e_recusado(self):
        self._alerta_vivo()
        cmd = self._cmd(expira_em=timezone.now() - timedelta(minutes=1))
        with self.assertRaises(pub.Recusado):
            pub.autorizar(cmd)


class DesfechoTest(_Base):
    """O que acontece ao comando depois da publicação."""

    def test_falha_no_broker_deixa_na_fila(self):
        # A parte que impede "verde no vazio": se o broker cai, o comando
        # fica `pendente` com o erro escrito. Marcado `enviado` sem ter saído
        # seria o pior bug possível aqui — e o `enviado_em` mentiria.
        self._alerta_vivo()
        cmd = self._cmd()

        def _explode(topico, corpo):
            raise OSError("broker em baixo")

        rel = pub.publicar(publicar_fn=_explode)
        cmd.refresh_from_db()
        self.assertEqual(rel["erros"], 1)
        self.assertEqual(cmd.status, "pendente")
        self.assertEqual(cmd.tentativas, 1)
        self.assertIn("broker em baixo", cmd.ultimo_erro)

    def test_depois_das_tentativas_vira_erro(self):
        # `pendente` alimenta o dedup de `enfileirar_comando`: um comando
        # preso em `pendente` bloqueia um comando novo e legitimo do mesmo
        # device. Por isso ha de desistir.
        self._alerta_vivo()
        cmd = self._cmd(tentativas=pub.MAX_TENTATIVAS - 1)

        def _explode(topico, corpo):
            raise OSError("nunca")

        pub.publicar(publicar_fn=_explode)
        cmd.refresh_from_db()
        self.assertEqual(cmd.status, "erro")
        self.assertIn("tentativas", cmd.ultimo_erro)

    def test_recusado_nao_vira_erro(self):
        # Recusado por revalizacao e' decisao saudavel. Marcar `erro` puniria
        # o produtor por uma regra que ele proprio desactivou.
        cmd = self._cmd(payload={"via": "manual"})
        fn, calls = self._publicado()
        rel = pub.publicar(publicar_fn=fn)
        cmd.refresh_from_db()
        self.assertEqual(cmd.status, "pendente")
        self.assertEqual(rel["recusados"], 1)
        self.assertEqual(calls, [])

    def test_o_relatorio_diz_porque_recusou(self):
        # Um relatorio com "3 recusados" e sem motivo obriga o operador a
        # abrir a base de dados para_each um. E' o que torna a recusa
        # accionavel em vez de silenciosa.
        self._cmd(payload={"via": "manual"})
        rel = pub.publicar(publicar_fn=lambda t, c: None)
        self.assertTrue(rel["motivos"])
        self.assertTrue(any("regra" in m for m in rel["motivos"]))

    def test_dry_run_nao_publica_nem_grava(self):
        self._alerta_vivo()
        cmd = self._cmd()
        rel = pub.publicar(
            dry_run=True, publicar_fn=lambda t, c: (_ for _ in ()).throw(AssertionError)
        )
        cmd.refresh_from_db()
        self.assertEqual(cmd.status, "pendente")
        self.assertIsNone(cmd.enviado_em)
        self.assertEqual(rel["publicados"], 0)


class TlsTest(TestCase):
    """`valve_open` em claro é uma porta aberta na rede da fazenda."""

    def test_comando_fisico_sem_tls_e_recusado(self):
        env = {k: v for k, v in os.environ.items() if not k.startswith("AMPLIA_MQTT_")}
        with mock.patch.dict(os.environ, env, clear=True):
            from app.iot.broker import BrokerNaoConfigurado, exigir_tls

            with self.assertRaises(BrokerNaoConfigurado) as e:
                exigir_tls("valve_open")
            self.assertIn("TLS", e.exception.args[0])

    def test_com_tls_passa(self):
        with mock.patch.dict(os.environ, {"AMPLIA_MQTT_TLS": "1"}, clear=False):
            from app.iot.broker import exigir_tls

            exigir_tls("valve_open")  # nao levanta

    def test_comando_nao_fisico_nao_exige_tls(self):
        env = {k: v for k, v in os.environ.items() if not k.startswith("AMPLIA_MQTT_")}
        with mock.patch.dict(os.environ, env, clear=True):
            from app.iot.broker import exigir_tls

            exigir_tls("set_interval")  # nao levanta

    def test_a_excepcao_de_plaintext_so_com_flag_explicita(self):
        env = {k: v for k, v in os.environ.items() if not k.startswith("AMPLIA_MQTT_")}
        env["AMPLIA_MQTT_PERMITIR_SEM_TLS"] = "1"
        with mock.patch.dict(os.environ, env, clear=True):
            from app.iot.broker import exigir_tls

            exigir_tls("valve_open")  # nao levanta

    def test_sem_broker_configurado_nao_publica(self):
        # Um `localhost` default seria um publisher que "funciona" em dev e
        # falha em producao com um erro que nao diz o que falta.
        env = {k: v for k, v in os.environ.items() if not k.startswith("AMPLIA_MQTT_")}
        with mock.patch.dict(os.environ, env, clear=True):
            from app.iot.broker import BrokerNaoConfigurado, config

            with self.assertRaises(BrokerNaoConfigurado) as e:
                config()
            self.assertIn("AMPLIA_MQTT_BROKER", e.exception.args[0])
