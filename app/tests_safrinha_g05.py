"""G-05 alerta safrinha — o criterio de saida do plano-correcao.

1. Funcoes puras: None sem ciclo/janela (sem_dado propaga); no dia do limite
   False, no dia seguinte True.
2. Com ZARC semeada + cultivar com ciclo: o achado sai da cadeia
   `montar_cenario -> regras_deterministicas` no dia certo, com a fonte
   "Embrapa - ZARC" ao lado da data (VISAO Fase 1.1).
3. ZARC vazia: zero achados de safrinha e NENHUMA data ISO no payload de
   `safras` (VISAO §0.2: 0 registros -> nada inventado).
4. Safra colhida: silencio (alertar sobre trabalho feito desliga a
   notificacao — licao copiloto).
5. Cadeia inteira ate `IAAlertaProativo` (espelho test_custo_proativo): um
   achado que nao vira alerta gravado nao chegou ao produtor.
"""

import json
import re
from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from app.ia.proativo import (
    limite_safrinha,
    montar_cenario,
    regras_deterministicas,
    risco_safrinha,
)
from app.models import (
    IAAlertaProativo,
    Cultivar,
    Cultura,
    Propriedade,
    Safra,
    Talhao,
    ZARC,
)

ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


class LimitePuroG05Test(SimpleTestCase):
    """Sem BD: a aritmetica da janela nao precisa de banco nem de relogio."""

    def test_sem_ciclo_ou_sem_janela_devolve_none(self):
        self.assertIsNone(limite_safrinha(None, 120))
        self.assertIsNone(limite_safrinha(date(2026, 12, 31), None))

    def test_limite_e_fim_da_janela_menos_ciclo(self):
        self.assertEqual(
            limite_safrinha(date(2026, 12, 31), 120), date(2026, 9, 2)
        )

    def test_risco_none_quando_limite_none(self):
        self.assertIsNone(risco_safrinha(date(2026, 10, 5), None))

    def test_no_dia_do_limite_false_no_dia_seguinte_true(self):
        hoje = date(2026, 10, 5)
        self.assertFalse(risco_safrinha(hoje, hoje))
        self.assertTrue(risco_safrinha(hoje, hoje - timedelta(days=1)))


class SafrinhaG05Test(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("produtor_g05", "g05@x.com", "x")
        self.prop = Propriedade.objects.create(
            user=self.user, nome="Fazenda G05", cidade="Sorriso", uf="MT",
            area_total=100,
        )
        self.talhao = Talhao.objects.create(
            propriedade=self.prop, nome="T-G05", area_hectare=10
        )
        self.cultura = Cultura.objects.create(nome="Soja G05", grupo="graos")
        self.cultivar = Cultivar.objects.create(
            cultura=self.cultura, nome_comercial="TMG G05", ciclo_max=120
        )
        self.hoje = timezone.localdate()

    def _zarc(self, fim_janela):
        return ZARC.objects.create(
            cultura=self.cultura,
            uf="MT",
            municipio="Sorriso",
            data_inicio_plantio=self.hoje - timedelta(days=30),
            data_fim_plantio=fim_janela,
            ciclo_dias=120,
        )

    def _safra(self, **kw):
        dados = dict(
            propriedade=self.prop,
            talhao=self.talhao,
            cultura=self.cultura,
            cultivar=self.cultivar,
            ano=2026,
            safra_nome=kw.pop("safra_nome", "Soja 2026/27"),
            area_plantada=10,
        )
        dados.update(kw)
        return Safra.objects.create(**dados)

    def _cenario(self):
        return montar_cenario(self.user, self.prop)

    def _achados_safrinha(self, cenario):
        return [
            a
            for a in regras_deterministicas(cenario)
            if a.get("regra") == "safrinha_janela_zarc"
        ]

    # --- criterios de saida -------------------------------------------------

    def test_zarc_semeada_dispara_no_dia_certo(self):
        """limite = ontem (fim da janela = hoje + ciclo - 1) -> risco True."""
        self._zarc(self.hoje + timedelta(days=119))
        self._safra()
        cenario = self._cenario()
        achados = self._achados_safrinha(cenario)
        self.assertEqual(len(achados), 1)
        a = achados[0]
        self.assertEqual(a["nivel"], "atencao")
        # Fonte ao lado da data (VISAO Fase 1.1).
        self.assertIn("Embrapa — ZARC", a["mensagem"])
        self.assertEqual(a["evidencia"]["fonte"], "Embrapa — ZARC")

    def test_no_dia_do_limite_ainda_nao_alerta(self):
        """limite = hoje -> plantar hoje ainda cabe (hoje + ciclo == fim)."""
        self._zarc(self.hoje + timedelta(days=120))
        self._safra()
        cenario = self._cenario()
        self.assertEqual(self._achados_safrinha(cenario), [])
        # Sem alerta tambem significa que a regra nao subiu para cima.
        self.assertFalse(
            [s for s in cenario["safras"] if s.get("risco")],
            "risco deveria ser False no dia do limite",
        )

    def test_zarc_vazia_zero_alertas_e_zero_datas(self):
        """VISAO §0.2: 0 registros -> nenhuma data gerada, nenhum achado."""
        self._safra()  # sem ZARC para o municipio
        cenario = self._cenario()
        self.assertEqual(self._achados_safrinha(cenario), [])
        # Varredura do payload: nenhuma data ISO de janela/limite.
        payload = json.dumps(cenario["safras"], ensure_ascii=False, default=str)
        self.assertIsNone(
            ISO_DATE.search(payload),
            f"payload com data ISO inventada: {payload}",
        )
        for s in cenario["safras"]:
            self.assertIsNone(s["limite"])
            self.assertIsNone(s["risco"])

    def test_safra_colhida_silencio(self):
        """Colheita registrada -> a janela deixou de ser assunto."""
        self._zarc(self.hoje + timedelta(days=119))
        self._safra(data_colheita=self.hoje - timedelta(days=10))
        cenario = self._cenario()
        self.assertEqual(self._achados_safrinha(cenario), [])
        self.assertEqual([s for s in cenario["safras"] if s.get("risco")], [])

    def test_sem_cultivar_sem_ciclo_nao_alerta(self):
        """Sem ciclo o sistema nao sabe — e 'nao saber' e' None, nao False."""
        self._zarc(self.hoje + timedelta(days=119))
        self._safra(cultivar=None)
        cenario = self._cenario()
        self.assertEqual(self._achados_safrinha(cenario), [])
        for s in cenario["safras"]:
            self.assertIsNone(s["risco"])

    def test_safrinha_sobe_o_cenario_sem_tarefa_nem_conta(self):
        """Risco de safrinha e' cenario por si (mesma razao das contas):
        sem tarefa, sem conta e com janela fechando, o cenario sobe."""
        self._zarc(self.hoje + timedelta(days=119))
        self._safra()
        cenario = self._cenario()
        self.assertTrue(cenario["tem_cenario"])

    def test_sem_risco_sem_tarefa_nao_e_cenario(self):
        """O outro lado: sem safra nao ha risco, e o cenario nao nasce para
        dizer 'nada a aviar' (ruim e' o que faz o produtor desligar)."""
        cenario = self._cenario()
        self.assertFalse(cenario["tem_cenario"])

    def test_cadeia_completa_ate_o_alerta_gravado(self):
        """Licao MEDIDO do custo: achado que nao vira `IAAlertaProativo`
        nao chegou ao produtor. Percurso da cadeia inteira:
        montar_cenario -> regras_deterministicas -> emitir_alerta."""
        from app.ia.proativo import emitir_alerta

        self._zarc(self.hoje + timedelta(days=119))
        self._safra()
        cenario = self._cenario()
        achados = [a for a in regras_deterministicas(cenario)]
        safrinha = [a for a in achados if a["regra"] == "safrinha_janela_zarc"]
        self.assertEqual(len(safrinha), 1, "a regra de safrinha nao achou o risco")
        a = safrinha[0]
        r = emitir_alerta(
            self.user,
            self.prop,
            titulo=a["titulo"],
            mensagem=a["mensagem"],
            nivel=a["nivel"],
            origem="regra",
            regra=a["regra"],
            evidencia=a.get("evidencia"),
        )
        self.assertTrue(r["ok"])
        self.assertEqual(IAAlertaProativo.objects.count(), 1)
        alerta = IAAlertaProativo.objects.get()
        self.assertIn("Embrapa — ZARC", alerta.mensagem)
        self.assertEqual(alerta.regra, "safrinha_janela_zarc")
