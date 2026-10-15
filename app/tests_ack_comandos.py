"""Um ACK é a mensagem mais perigosa do sistema.

Porque estes testes são quase todos de recusa
============================================
Um ACK diz "isto aconteceu no mundo físico". Se for aceito sem Verification,
o sistema fecha o ciclo sobre uma mentira — e a mentira que fecha o ciclo é
a que o produtor mais caro paga: a cultura seca com o painel a dizer que
está tudo bem.

Um teste que só prova "o ACK foi aceite" não vale nada. O que interessa é a
recusa: ACK de outro produtor, ACK de comando não publicado, ACK de comando
errado, ACK sem `ok`.

O broker é injectado e o gateway é autenticado com `api_key` real, para os
testes medirem a regra e não o mock.
"""

from __future__ import annotations

import json
from datetime import timedelta
from unittest import mock

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.utils import timezone

from app.iot.ack import AckRecusado, confirmar
from app.models import (
    AlertaTelemetria,
    ComandoDevice,
    Device,
    Gateway,
    Propriedade,
    RegraAlertaTelemetria,
)
from app.seguranca import hash_cego


class _Base(TestCase):
    """Duas fazendas, com as regras vivas e um comando JA publicado."""

    def setUp(self):
        self.a = User.objects.create_user("ack_a", password="x")
        self.b = User.objects.create_user("ack_b", password="x")
        self.prop_a = Propriedade.objects.create(
            user=self.a, nome="Faz A", area_total=10, uf="MT", cidade="X"
        )
        self.prop_b = Propriedade.objects.create(
            user=self.b, nome="Faz B", area_total=10, uf="MT", cidade="Y"
        )
        self.dev_a = Device.objects.create(
            propriedade=self.prop_a, device_eui="EUACKA1", nome="Valvula A"
        )
        self.dev_b = Device.objects.create(
            propriedade=self.prop_b, device_eui="EUACKB1", nome="Valvula B"
        )
        self.regra = RegraAlertaTelemetria.objects.create(
            propriedade=self.prop_a,
            nome="Solo seco",
            metric="umidade_solo",
            tipo="threshold_min",
            valor_ref=20,
            acao_fisica="abrir_valvula",
        )
        AlertaTelemetria.objects.create(
            regra=self.regra,
            propriedade=self.prop_a,
            device=self.dev_a,
            metric="umidade_solo",
            valor=5,
            severidade="warning",
            mensagem="seca",
            timestamp=timezone.now(),
        )
        # JA PUBLICADO: um ACK so faz sentido sobre o que saiu. E' este o
        # estado que o publisher deixa, e o unico em que confirmar e' verdade.
        self.cmd = ComandoDevice.objects.create(
            device=self.dev_a,
            comando="valve_open",
            payload={"via": "regra_auto", "regra_id": self.regra.id},
            status="enviado",
            enviado_em=timezone.now(),
            expira_em=timezone.now() + timedelta(minutes=30),
        )

    def _ok(self, **kw):
        params = {
            "cmd_id": self.cmd.id,
            "device": self.dev_a,
            "propriedade": self.prop_a,
            "ok": True,
        }
        params.update(kw)
        return confirmar(**params)


class AckConfirmacaoTest(_Base):
    def test_ack_do_device_certo_confirma(self):
        cmd, mudou = self._ok()
        self.assertTrue(mudou)
        self.assertEqual(cmd.status, "ack")
        self.assertTrue(cmd.resposta["ok"])

    def test_ack_negado_fica_erro_com_prefixo(self):
        # Negado pelo device e' um RESULTADO, nao um timeout. O prefixo
        # `ack_negado` e' o que impede o `expirar_comandos` de contar isto
        # como falha de rede mais tarde.
        cmd, _ = self._ok(ok=False, motivo="valvula travada")
        self.assertEqual(cmd.status, "ack")
        self.assertTrue(cmd.ultimo_erro.startswith("ack_negado"))
        self.assertIn("valvula travada", cmd.ultimo_erro)
        self.assertFalse(cmd.resposta["ok"])

    def test_ack_repetido_e_no_op(self):
        # QoS 1 significa "pode repetir". Um 409 faria o gateway entrar em
        # laco de retentativa porque nunca tem sucesso.
        self._ok()
        cmd, mudou = self._ok()
        self.assertFalse(mudou)
        self.assertEqual(cmd.status, "ack")

    def test_ack_de_comando_nao_publicado_e_recusado(self):
        # O mais importante. Um ACK de um `pendente` nao tem como ser verdade:
        # nao foi enviado nada. E' replay ou mentira.
        self.cmd.status = "pendente"
        self.cmd.enviado_em = None
        self.cmd.save(update_fields=["status", "enviado_em"])
        with self.assertRaises(AckRecusado) as e:
            self._ok()
        self.assertIn("pendente", e.exception.motivo)

    def test_ack_de_comando_de_outra_propriedade_e_recusado(self):
        with self.assertRaises(AckRecusado) as e:
            self._ok(device=self.dev_b)
        self.assertEqual(e.exception.http_status, 403)

    def test_ack_de_comando_inexistente_e_404(self):
        with self.assertRaises(AckRecusado) as e:
            self._ok(cmd_id=999999)
        self.assertEqual(e.exception.http_status, 404)

    def test_cmd_id_ilegivel_e_400(self):
        with self.assertRaises(AckRecusado) as e:
            self._ok(cmd_id="abc")
        self.assertEqual(e.exception.http_status, 400)

    def test_ack_tarde_e_registado_como_tal(self):
        # O comando expirou (30 min sem ACK) e MESMO ASSIM o device
        # confirmou. E' melhor registar do que perder — mas o atraso fica
        # escrito, porque "abriu 40 min depois" muda o que se pode concluir.
        self.cmd.status = "erro"
        self.cmd.ultimo_erro = "timeout: sem ack do gateway"
        self.cmd.save(update_fields=["status", "ultimo_erro"])
        cmd, mudou = self._ok()
        self.assertTrue(mudou)
        self.assertEqual(cmd.status, "ack")
        self.assertTrue(cmd.enviado_em)


class AckHttpTest(_Base):
    """O portão de produção. Aqui a autenticação é a do gateway, a mesma da
    telemetria — menos credenciais para uma coisa mais perigosa seria um
    caminho mais facil."""

    def setUp(self):
        super().setUp()
        self.chave = "chave-secreta-do-gateway-a"
        # MEDIDO 2026-10-05: passa-se `api_key`, NUNCA `api_key_hash`.
        # `Gateway.save()` deriva o indice cego do valor claro e SOBRESCREVE
        # o que vier no campo. Passar o hash directamente produz um indice de
        # uma chave diferente — e o `_resolve_auth` nunca casa, o que parece
        # "a autenticacao esta quebrada" quando nao esta.
        gw = Gateway.objects.create(
            propriedade=self.prop_a,
            nome="GW A",
            gateway_eui="EUIACKGWA",
            api_key=self.chave,
        )
        self.assertEqual(gw.api_key_hash, hash_cego(self.chave))
        self.dev_a.gateway = gw
        self.dev_a.save(update_fields=["gateway"])
        self.url = "/api/iot/comando/ack/"

    def _post(self, corpo, chave=None):
        c = Client()
        headers = {"HTTP_X_API_KEY": chave} if chave is not None else {}
        return c.post(self.url, json.dumps(corpo), "application/json", **headers)

    def test_ack_autenticado_confirma(self):
        r = self._post(
            {
                "cmd_id": self.cmd.id,
                "device_eui": "EUACKA1",
                "ok": True,
                "resposta": {"posicao": "aberta"},
            },
            chave=self.chave,
        )
        self.assertEqual(r.status_code, 200, r.content)
        self.cmd.refresh_from_db()
        self.assertEqual(self.cmd.status, "ack")
        self.assertEqual(self.cmd.resposta["posicao"], "aberta")

    def test_sem_credencial_e_401_e_nao_muda_nada(self):
        r = self._post({"cmd_id": self.cmd.id, "device_eui": "EUACKA1", "ok": True})
        self.assertEqual(r.status_code, 401)
        self.cmd.refresh_from_db()
        self.assertEqual(self.cmd.status, "enviado")

    def test_credencial_invalida_e_401(self):
        r = self._post(
            {"cmd_id": self.cmd.id, "device_eui": "EUACKA1", "ok": True},
            chave="chave-errada",
        )
        self.assertEqual(r.status_code, 401)
        self.cmd.refresh_from_db()
        self.assertEqual(self.cmd.status, "enviado")

    def test_device_de_outra_fazenda_e_403(self):
        # A credencial e' valida, mas o device nao e' desta propriedade.
        # 403 e nao 404: quem tem credencial ja sabe que o device existe.
        r = self._post(
            {"cmd_id": self.cmd.id, "device_eui": "EUACKB1", "ok": True},
            chave=self.chave,
        )
        self.assertEqual(r.status_code, 403)
        self.cmd.refresh_from_db()
        self.assertEqual(self.cmd.status, "enviado")

    def test_ok_ausente_e_400(self):
        # Adivinhar "deu certo" fecharia o ciclo sobre um valor que ninguem
        # disse. E' o erro que nao pode ser reparado a posteriori.
        r = self._post(
            {"cmd_id": self.cmd.id, "device_eui": "EUACKA1"},
            chave=self.chave,
        )
        self.assertEqual(r.status_code, 400)
        self.cmd.refresh_from_db()
        self.assertEqual(self.cmd.status, "enviado")

    def test_get_e_recusado(self):
        c = Client()
        r = c.get(self.url, HTTP_X_API_KEY=self.chave)
        self.assertEqual(r.status_code, 405)


class CicloCompletoTest(_Base):
    """O caminho inteiro: publicar, depois confirmar. É o que prova que a
    promessa da automação se cumpre — e o que faltava antes."""

    def test_publicar_e_confirmar(self):
        from app.iot.publicar import publicar

        # O comando nasce PENDENTE — e' o que o publisher procura. O fixture
        # da classe base deixa-o `enviado` para os testes de ACK; aqui o que
        # se mede e' o ciclo, portanto volta ao estado de partida.
        self.cmd.status = "pendente"
        self.cmd.enviado_em = None
        self.cmd.save(update_fields=["status", "enviado_em"])

        topicos = []
        r = publicar(publicar_fn=lambda t, corpo: topicos.append((t, corpo)))
        self.assertEqual(r["publicados"], 1, r)
        self.cmd.refresh_from_db()
        self.assertEqual(self.cmd.status, "enviado")

        cmd, mudou = confirmar(
            cmd_id=self.cmd.id,
            device=self.dev_a,
            propriedade=self.prop_a,
            ok=True,
            resposta={"posicao": "aberta"},
        )
        self.assertTrue(mudou)
        self.assertEqual(cmd.status, "ack")
        # O device recebeu um comando que leva o id de volta, para o ACK
        # poder falar do comando certo.
        corpo = json.loads(topicos[0][1].decode("utf-8"))
        self.assertEqual(corpo["cmd_id"], self.cmd.id)
        self.assertIn("/cmd", topicos[0][0])

    def test_comando_nao_publicado_nao_tem_ack(self):
        # O caso opposite: se o publisher recusou, nao ha ACK para dar.
        from app.iot.publicar import publicar

        # A regra e' desligada: o publisher recusa, e o comando fica
        # `pendente` sem nunca ter saido.
        self.regra.ativa = False
        self.regra.save(update_fields=["ativa"])
        self.cmd.status = "pendente"
        self.cmd.enviado_em = None
        self.cmd.save(update_fields=["status", "enviado_em"])

        r = publicar(publicar_fn=lambda t, corpo: None)
        self.assertEqual(r["publicados"], 0)
        self.assertEqual(r["recusados"], 1)
        with self.assertRaises(AckRecusado):
            confirmar(
                cmd_id=self.cmd.id,
                device=self.dev_a,
                propriedade=self.prop_a,
                ok=True,
            )
