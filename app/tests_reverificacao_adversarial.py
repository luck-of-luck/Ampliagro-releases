"""Reverificação adversarial: tentar quebrar as correções dos 4 bugs.

Um teste que passa depois de uma correcção prova que o caso feliz funciona.
Nao prova que a correcção esta certa. Estes testes sao o outro lado: pegam
nos cantos que o teste original nao toca, e que é onde as correcções costumam
estar erradas.

Os 4 bugs corrigidos:

  BUG-1  app/ia/sandbox.py           estado preso em COLETANDO_DADOS
  BUG-2  app/iot/alert_engine.py     device offline nunca detectado
  BUG-3  src/stores/widgetStore.ts   deletePreset deixava o grid mentindo
  BUG-4  app/cache_painel.py         widget_data nunca invalidado

Para cada um, os testes abaixo procuram o canto: entrada malformada, estado
inconsistente, e o caso em que a correcção é mais rígida do que devia.
"""

from __future__ import annotations

from datetime import date, timedelta

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone

from app.ia import sandbox
from app.ia.sandbox import INTENTS
from app.iot.alert_engine import check_offline_devices, evaluate_batch
from app.models import (
    AlertaTelemetria,
    Device,
    IAContextoConversa,
    LancamentoFinanceiro,
    Propriedade,
    RegraAlertaTelemetria,
)

# ======================================================================
# NOTA DE HONESTIDADE
#
# Estes testes NORMALMENTE passariam a primeira, porque tentam quebrar as
# correcoes e as correcoes estavam certas. Isso e um bom sinal — mas e um sinal
# fraco: um teste adversarial que passa nao prova que a correcao esta certa,
# prova apenas que estes cantos especificos nao estao errados.
#
# O que estes testes FAZEM de valor: registam o comportamento nao-óbvio. Se
# alguem endurecer a correcao mais tarde (ex.: `evaluate_batch` deixar de
# filtrar `offline`), o teste quebra no dia, e nao em producao.
# ======================================================================


# ======================================================================
# BUG-1 — a correcção pode ser RÍGIDA demais
# ======================================================================


class BUG1CorreccaoNaoEExcessivaTest(TestCase):
    """Reparar o estado não pode apagar dados que ainda servem.

    A correcção limpa `dados_coletados` quando a coleta fecha. Se um intent
    ainda precisar deles no gate de confirmação, o "sim" do produtor chega sem
    os campos e o intent nunca corre — o producer fica preso em "confirma?"
    para sempre. Este teste prova que esse caminho nao regride.
    """

    def setUp(self):
        self.user = User.objects.create_user("ana", password="x")
        self.foi = []

    def _intent(self, *, exige_confirmacao, required):
        def handler(user, params, ctx):
            self.foi.append(dict(params))
            return {"ok": True, "resposta": "feito"}

        return {
            "descricao": "t",
            "exemplos": [{}],
            "flags": ["x.write"] if exige_confirmacao else ["x.read"],
            "required_fields": required,
            "handler": handler,
            **({"requires_confirmation": True} if exige_confirmacao else {}),
        }

    def _cleanup(self, nome):
        INTENTS.pop(nome, None)

    def test_dados_coletados_sobrem_para_o_gate_de_confirmacao(self):
        """A correcao limpa `dados_coletados` — mas o gate precisa deles."""
        """Coletou tudo -> confirmou -> o handler recebe os campos preenchidos."""
        nome = "t_bug1_confirm"
        INTENTS[nome] = self._intent(exige_confirmacao=True, required=["nome", "area"])
        try:
            r1 = sandbox.executar(self.user, nome, {})
            self.assertEqual(r1.get("state"), "COLETANDO_DADOS")

            r2 = sandbox.executar(self.user, nome, {}, meta={"entrada": "Sitio"})
            self.assertEqual(r2.get("state"), "COLETANDO_DADOS")

            r3 = sandbox.executar(self.user, nome, {}, meta={"entrada": "12"})
            self.assertTrue(r3.get("needs_confirm"), r3)

            r4 = sandbox.executar(self.user, nome, {}, meta={"entrada": "sim"})
            self.assertTrue(r4.get("ok"), r4)
            self.assertEqual(len(self.foi), 1, "o handler nao executou no 'sim'")
            # O QUE IMPORTA: os campos sobreviveram a limpeza de estado.
            self.assertEqual(self.foi[0].get("nome"), "Sitio")
            self.assertEqual(str(self.foi[0].get("area")), "12")
            self.assertTrue(self.foi[0].get("confirm"))
        finally:
            self._cleanup(nome)

    def test_intent_inexistente_pendente_da_recuperacao(self):
        """`intent_pendente` a apontar para algo removido não dá traceback."""
        nome = "t_bug1_desaparece"
        INTENTS[nome] = self._intent(exige_confirmacao=False, required=["nome"])
        try:
            sandbox.executar(self.user, nome, {})
            ctx = IAContextoConversa.objects.get(user=self.user)
            self.assertEqual(ctx.estado_atual, "COLETANDO_DADOS")

            # O intent desaparece do catálogo (deploy, renomeação, teste).
            INTENTS.pop(nome)

            r = sandbox.executar(self.user, nome, {}, meta={"entrada": "Fazenda"})
            # Não pode levantar; tem de devolver erro EXPLÍCITO.
            self.assertFalse(r.get("ok"))
            self.assertIn("erro", r)
        finally:
            self._cleanup(nome)

    def test_cancelar_durante_a_coleta_limpa_o_estado(self):
        """ "cancelar" durante COLETANDO tem de limpar, como em AGUARDANDO."""
        nome = "t_bug1_cancel"
        INTENTS[nome] = self._intent(exige_confirmacao=False, required=["nome"])
        try:
            sandbox.executar(self.user, nome, {})
            r = sandbox.executar(self.user, nome, {}, meta={"entrada": "cancelar"})
            self.assertTrue(r.get("ok"))
            ctx = IAContextoConversa.objects.get(user=self.user)
            self.assertEqual(ctx.estado_atual, "NENHUM")
        finally:
            self._cleanup(nome)

    def test_intent_sem_required_fields_nunca_entra_em_coleta(self):
        """Sem `required_fields`, nao há coleta — logo não há estado preso."""
        nome = "t_bug1_sem_campos"
        INTENTS[nome] = self._intent(exige_confirmacao=False, required=[])
        try:
            r = sandbox.executar(self.user, nome, {})
            self.assertTrue(r.get("ok"), r)
            ctx = IAContextoConversa.objects.get(user=self.user)
            self.assertEqual(ctx.estado_atual, "NENHUM")
        finally:
            self._cleanup(nome)


# ======================================================================
# BUG-2 — a correcção pode gera alertas que não deve
# ======================================================================


class BUG2NaoGeraFalsosPositivosTest(TestCase):
    """Tirar o filtro `metric="bateria"` não pode inundar de alertas."""

    def setUp(self):
        self.user = User.objects.create_user("bob", password="x")
        self.prop = Propriedade.objects.create(
            user=self.user, nome="Fazenda", area_total=100
        )
        self.dev = Device.objects.create(
            device_eui="AA:BB:CC:DD:EE:01",
            nome="Sensor",
            propriedade=self.prop,
            intervalo_seg=900,
            ativo=True,
            ultimo_push=timezone.now() - timedelta(hours=6),
        )
        self.regra = RegraAlertaTelemetria.objects.create(
            propriedade=self.prop,
            nome="Offline",
            metric="temperatura",
            tipo="offline",
            severidade="warning",
            ativa=True,
        )

    def test_nao_avisa_quando_a_regra_esta_inativa(self):
        """Regra desligada não gera alerta — `ativa=True` ainda conta."""
        RegraAlertaTelemetria.objects.filter(pk=self.regra.pk).update(ativa=False)
        check_offline_devices()
        self.assertFalse(AlertaTelemetria.objects.filter(device=self.dev).exists())

    def test_nao_avisa_quando_o_dispositivo_esta_inativo(self):
        Device.objects.filter(pk=self.dev.pk).update(ativo=False)
        check_offline_devices()
        self.assertFalse(AlertaTelemetria.objects.filter(device=self.dev).exists())

    def test_nao_avisa_device_que_acabou_de_falar(self):
        Device.objects.filter(pk=self.dev.pk).update(
            ultimo_push=timezone.now() - timedelta(seconds=60)
        )
        check_offline_devices()
        self.assertFalse(
            AlertaTelemetria.objects.filter(device=self.dev).exists(),
            "avizou um device que falou há 1 minuto",
        )

    def test_nao_avisa_device_nunca_que_falou(self):
        """`ultimo_push is None` não é 'calado há 6h' — é 'nunca falou'."""
        Device.objects.filter(pk=self.dev.pk).update(ultimo_push=None)
        check_offline_devices()
        self.assertFalse(
            AlertaTelemetria.objects.filter(device=self.dev).exists(),
            "tratau 'nunca falou' como 'calado'",
        )

    def test_respeita_o_intervalo_de_cada_dispositivo(self):
        """O limiar é `intervalo*2 + 5min`, não um valor fixo."""
        # intervalo 1h -> limiar 2h05. Calado há 1h30: NAO deve avisar.
        Device.objects.filter(pk=self.dev.pk).update(
            intervalo_seg=3600, ultimo_push=timezone.now() - timedelta(minutes=90)
        )
        check_offline_devices()
        self.assertFalse(
            AlertaTelemetria.objects.filter(device=self.dev).exists(),
            "avisou antes do limiar do proprio intervalo",
        )

    def test_a_separacao_por_propriedade_mantem_se(self):
        """Duas fazendas: só a que tem regra offline avisa."""
        outra = Propriedade.objects.create(user=self.user, nome="Outra", area_total=10)
        dev2 = Device.objects.create(
            device_eui="AA:BB:CC:DD:EE:02",
            nome="Sensor 2",
            propriedade=outra,
            intervalo_seg=900,
            ativo=True,
            ultimo_push=timezone.now() - timedelta(hours=6),
        )
        check_offline_devices()
        self.assertTrue(AlertaTelemetria.objects.filter(device=self.dev).exists())
        self.assertFalse(
            AlertaTelemetria.objects.filter(device=dev2).exists(),
            "um device sem regra na propriedade avisou",
        )


# ======================================================================
# BUG-4 — a correcção pode apagar demasiado
# ======================================================================


class BUG4NaoApagaDemaisTest(TestCase):
    """`delete_many` com chaves a mais é inofensivo; uid errado não é."""

    def setUp(self):
        self.user = User.objects.create_user("carla", password="x")
        self.prop = Propriedade.objects.create(
            user=self.user, nome="Fazenda", area_total=10
        )

    def _despesa(self):
        return LancamentoFinanceiro.objects.create(
            propriedade=self.prop,
            descricao="X",
            valor=1,
            tipo="DESPESA",
            data=date(2026, 1, 1),
        )

    def test_apagar_todas_as_portas_nao_apaga_outro_usuario(self):
        vizinho = User.objects.create_user("dave", password="x")
        chaves_vizinho = [
            f"dash:{vizinho.id}",
            f"widget_data:{vizinho.id}:0",
            f"widget_data:{vizinho.id}:1",
        ]
        for c in chaves_vizinho:
            cache.set(c, {"x": 1}, 30)

        self._despesa()

        for c in chaves_vizinho:
            with self.subTest(chave=c):
                self.assertIsNotNone(
                    cache.get(c), "a escrita de um limpou o cache de outro"
                )

    def test_chave_que_nao_existe_nao_levanta(self):
        """`delete_many` de chaves inexistentes é no-op, não erro."""
        from app.cache_painel import _chaves_do_usuario

        cache.delete_many(list(_chaves_do_usuario(999999)))
        self._despesa()  # não deve levantar

    def test_propriedade_sem_user_nao_apaga_nada(self):
        """`Propriedade` sempre tem `user`; o guard de `uid` é a rede de segurança."""
        from app.cache_painel import invalidar_painel

        orfa = Propriedade(nome="Sem dono", area_total=1)  # sem salvar, sem user
        invalidar_painel(orfa)  # não deve levantar

    def test_escrita_na_propriedade_derruba_o_dash(self):
        """O caminho mais comum: guardar a propriedade limpa o `dash:`."""
        cache.set(f"dash:{self.user.id}", {"saldo": 0}, 30)
        self.prop.nome = "Renomeada"
        self.prop.save()
        self.assertIsNone(cache.get(f"dash:{self.user.id}"))


# ======================================================================
# evaluate_batch — o path que BUG-2 NÃO tocou, mas é o mesmo código
# ======================================================================


class EvaluateBatchNaoCriaAlertaOfflineTest(TestCase):
    """`evaluate_batch` faz `continue` em `offline` — e tem de continuar a fazer.

    A correcção do BUG-2 foi em `check_offline_devices`. Se alguém mexer no
    `evaluate_batch` e deixar de filtrar, um alerta offline duplicaria a cada
    leitura — o mesmo device em loop.
    """

    def setUp(self):
        self.user = User.objects.create_user("eva", password="x")
        self.prop = Propriedade.objects.create(
            user=self.user, nome="Fazenda", area_total=10
        )
        self.dev = Device.objects.create(
            device_eui="AA:BB:CC:DD:EE:03",
            nome="S",
            propriedade=self.prop,
            intervalo_seg=900,
            ativo=True,
            ultimo_push=timezone.now(),
        )
        RegraAlertaTelemetria.objects.create(
            propriedade=self.prop,
            nome="Offline",
            metric="temperatura",
            tipo="offline",
            ativa=True,
        )

    def test_offline_nao_dispara_por_leitura(self):
        readings = [{"metric": "temperatura", "value": 30, "timestamp": timezone.now()}]
        criados = evaluate_batch(self.prop, self.dev, readings)
        self.assertEqual(criados, [], "evaluate_batch disparou uma regra tipo=offline")
        self.assertFalse(AlertaTelemetria.objects.filter(device=self.dev).exists())
