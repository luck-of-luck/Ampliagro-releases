"""Testes do gerenciador de alertas (management command gerar_alertas)."""

from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from app.management.commands.gerar_alertas import Command
from app.models import (
    AnimalIndividual,
    ApiarioColmeia,
    AtividadePlanejada,
    Cultura,
    Device,
    EstoqueItem,
    EventoSanitario,
    Insumo,
    LancamentoFinanceiro,
    Maquinario,
    MonitoramentoPraga,
    Parcelamento,
    PlanoSafra,
    Propriedade,
    Racao,
    Safra,
    Talhao,
)


def _mkuser(name):
    return User.objects.create_user(username=name, password="x")


class GerenciadorAlertasTest(TestCase):
    def setUp(self):
        self.u = _mkuser("alertas")
        self.prop = Propriedade.objects.create(
            user=self.u, nome="Faz Alertas", area_total=100, uf="MT", cidade="Sorriso"
        )
        self.hoje = date.today()
        self.cmd = Command()

    def _alertas(self):
        return self.cmd._verificar_propriedade(
            self.u, self.prop, self.hoje, self.hoje + timedelta(days=30)
        )

    def _titulos(self):
        return [a["titulo"] for a in self._alertas()]

    def test_prop_limpa_sem_alertas(self):
        self.assertEqual(self._alertas(), [])

    def test_manutencao_atrasada(self):
        Maquinario.objects.create(
            propriedade=self.prop,
            tipo="TRATOR",
            nome="Trator A",
            proxima_manutencao=self.hoje - timedelta(days=3),
        )
        self.assertTrue(any("Manutenção atrasada" in t for t in self._titulos()))

    def test_insumo_abaixo_minimo(self):
        Insumo.objects.create(
            propriedade=self.prop,
            categoria="ADUBO",
            nome="NPK A",
            quantidade=2,
            unidade="sc",
            valor_unitario=10,
            estoque_minimo=10,
        )
        self.assertTrue(any("abaixo do mínimo" in t for t in self._titulos()))

    def test_racao_vencida(self):
        Racao.objects.create(
            propriedade=self.prop,
            nome="Ração A",
            quantidade=10,
            data_validade=self.hoje - timedelta(days=1),
        )
        self.assertTrue(any("Ração vencida" in t for t in self._titulos()))

    def test_despesa_sem_vencimento_nao_e_conta_vencida(self):
        """Este teste CODIFICAVA O BUG. Agora exige a coisa certa.

        `LancamentoFinanceiro.data` e' quando a despesa ACONTECEU. Uma despesa
        de dois dias, sem data de vencimento registada, NAO e' um atraso — e
        dizer que e' repete o mesmo numero todos os meses, para sempre.
        """
        LancamentoFinanceiro.objects.create(
            propriedade=self.prop,
            tipo="DESPESA",
            categoria="INSUMOS",
            valor=100,
            data=self.hoje - timedelta(days=2),
        )
        self.assertFalse(
            any("vencida(s)" in t for t in self._titulos()),
            "uma despesa sem data de vencimento foi tratada como atraso. "
            "`data` e' quando ACONTECEU, nao quando vence",
        )

    def test_conta_com_vencimento_passado_e_um_atraso_real(self):
        """E o atraso verdadeiro, que nao pode perder-se na correccao."""
        from app.models import ContaAPagar

        ContaAPagar.objects.create(
            propriedade=self.prop,
            descricao="Fertilizante",
            valor=Decimal("1200.00"),
            vencimento=self.hoje - timedelta(days=3),
            fornecedor="Cenario X",
        )
        self.assertTrue(
            any("vencida(s)" in t for t in self._titulos()),
            "o atraso real deixou de ser reportado — a correccao apagou o sinal",
        )

    def test_a_despesa_sem_data_aparece_como_pergunta(self):
        """Nao se esconde: entra como 'sem vencimento', a perguntar."""
        LancamentoFinanceiro.objects.create(
            propriedade=self.prop,
            tipo="DESPESA",
            categoria="INSUMOS",
            valor=100,
            data=self.hoje - timedelta(days=400),
        )
        titulos = self._titulos()
        self.assertTrue(
            any("sem data de vencimento" in t for t in titulos),
            f"a despesa em aberto desapareceu: {titulos}",
        )

    def test_parcela_vencida(self):
        lac = LancamentoFinanceiro.objects.create(
            propriedade=self.prop,
            tipo="DESPESA",
            categoria="MAQUINAS",
            valor=1000,
            data=self.hoje - timedelta(days=40),
        )
        Parcelamento.objects.create(
            propriedade=self.prop,
            lancamento=lac,
            tipo="PAGAR",
            numero=1,
            total_parcelas=5,
            valor_total=1000,
            valor_parcela=200,
            data_vencimento=self.hoje - timedelta(days=1),
            status="ABERTA",
        )
        self.assertTrue(any("parcela(s) vencida" in t for t in self._titulos()))

    def test_mip_critico(self):
        talhao = Talhao.objects.create(
            propriedade=self.prop, nome="T1", area_hectare=10, ativo=True
        )
        MonitoramentoPraga.objects.create(
            talhao=talhao,
            data=self.hoje,
            praga="Lagarta",
            nivel_infestacao=70,
            nivel_controle=50,
            acao_recomendada="Aplicar X",
        )
        self.assertTrue(any("MIP crítico" in t for t in self._titulos()))

    def test_vacina_atrasada(self):
        ind = AnimalIndividual.objects.create(
            propriedade=self.prop, brinco="BV1", sexo="F", especie="BOV"
        )
        EventoSanitario.objects.create(
            animal=ind,
            tipo="vacina",
            produto="Aftosa",
            data=self.hoje,
            proxima_dose=self.hoje - timedelta(days=1),
        )
        self.assertTrue(any("atrasada" in t for t in self._titulos()))

    def test_bateria_baixa(self):
        Device.objects.create(
            propriedade=self.prop,
            device_eui="EUIALERTA01",
            nome="Sensor A",
            bateria_pct=10,
        )
        self.assertTrue(any("bateria baixa" in t for t in self._titulos()))

    def test_tarefa_atrasada(self):
        cultura = Cultura.objects.create(nome="SojaAlerta", grupo="graos")
        safra = Safra.objects.create(
            propriedade=self.prop, cultura=cultura, ano=2026, area_plantada=10
        )
        plano = PlanoSafra.objects.create(safra=safra)
        AtividadePlanejada.objects.create(
            plano=plano,
            nome="Pulverizar",
            data_prevista=self.hoje - timedelta(days=2),
            concluida=False,
        )
        self.assertTrue(any("atrasada(s)" in t for t in self._titulos()))

    def test_estoque_zerado_e_vencido(self):
        EstoqueItem.objects.create(
            propriedade=self.prop,
            categoria="DEFENSIVO",
            nome="Item Z",
            quantidade=0,
            unidade="L",
            data_validade=self.hoje - timedelta(days=1),
        )
        titulos = self._titulos()
        self.assertTrue(any("zerado" in t for t in titulos))
        self.assertTrue(any("vencido" in t for t in titulos))


class AlertaConfigTest(TestCase):
    """Ponto de alerta por usuário: on/off + dias + limite."""

    def setUp(self):
        self.u = _mkuser("cfg")
        self.prop = Propriedade.objects.create(
            user=self.u, nome="Faz Cfg", area_total=10, uf="MT", cidade="X"
        )
        self.hoje = date.today()
        self.cmd = Command()

    def _titulos(self):
        return [
            a["titulo"]
            for a in self.cmd._verificar_propriedade(
                self.u, self.prop, self.hoje, self.hoje + timedelta(days=30)
            )
        ]

    def test_desligar_regra_some_alerta(self):
        from app.models import AlertaConfig

        Maquinario.objects.create(
            propriedade=self.prop,
            tipo="TRATOR",
            nome="Trator C",
            proxima_manutencao=self.hoje - timedelta(days=1),
        )
        self.assertTrue(any("Manutenção" in t for t in self._titulos()))
        AlertaConfig.objects.create(user=self.u, regra="manutencao", ativo=False)
        self.assertFalse(any("Manutenção" in t for t in self._titulos()))

    def test_dias_custom_respeitado(self):
        from app.models import AlertaConfig

        Maquinario.objects.create(
            propriedade=self.prop,
            tipo="TRATOR",
            nome="Trator D",
            proxima_manutencao=self.hoje + timedelta(days=30),
        )
        self.assertFalse(any("Manutenção" in t for t in self._titulos()))
        AlertaConfig.objects.create(user=self.u, regra="manutencao", dias=60)
        self.assertTrue(any("Manutenção próxima" in t for t in self._titulos()))

    def test_limite_custom_bateria(self):
        from app.models import AlertaConfig, Device

        Device.objects.create(
            propriedade=self.prop,
            device_eui="EUICFG01",
            nome="Sensor C",
            bateria_pct=50,
        )
        self.assertFalse(any("bateria" in t for t in self._titulos()))
        AlertaConfig.objects.create(user=self.u, regra="bateria", limite=80)
        self.assertTrue(any("bateria baixa" in t for t in self._titulos()))

    def test_api_get_lista_regras(self):
        from django.test import Client

        c = Client()
        c.force_login(self.u)
        r = c.get("/api/alertas-config/")
        self.assertEqual(r.status_code, 200)
        regras = r.json()["regras"]
        chaves = {x["regra"] for x in regras}

        # A contagem e' o canario que apanha uma regra acrescentada sem
        # pensar. Subiu de 20 para 21 com `contas_sem_vencimento`, que e' um
        # sinal distinto: uma despesa sem data de vencimento NAO e' um atraso,
        # e por isso nao pode ser `critical`.
        self.assertEqual(len(regras), 21)
        self.assertIn("manutencao", chaves)
        self.assertIn("saldo_contas", chaves)
        self.assertIn(
            "contas_sem_vencimento",
            chaves,
            "a regra que pergunta pelas despesas sem data tem de ser "
            "configuravel — se nao, nao ha como desligar um alerta que nao "
            "serve a uma fazenda que tem as datas todas",
        )

    def test_api_put_salva(self):
        from django.test import Client

        from app.models import AlertaConfig

        c = Client()
        c.force_login(self.u)
        r = c.put(
            "/api/alertas-config/",
            data={"regra": "manutencao", "ativo": False, "dias": 45},
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 200)
        cfg = AlertaConfig.objects.get(user=self.u, regra="manutencao")
        self.assertFalse(cfg.ativo)
        self.assertEqual(cfg.dias, 45)

    def test_api_put_regra_invalida(self):
        from django.test import Client

        c = Client()
        c.force_login(self.u)
        r = c.put(
            "/api/alertas-config/",
            data={"regra": "inexistente", "ativo": True},
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 400)
from decimal import Decimal  # noqa: E402
