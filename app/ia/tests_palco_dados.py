"""Os números da mesa: reais, e do produtor certo.

O teste mais importante deste ficheiro não é sobre números. É sobre VAZAMENTO.
Uma mesa de operação com a despesa do vizinho não dá erro nenhum — dá uma
tela normal, com números que parecem normais, e o produtor age em cima deles.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from app.ia import palco
from app.ia.palco_dados import enriquece
from app.models import Cultura, LancamentoFinanceiro, Propriedade, Safra, Talhao


def _prop(user, nome="Fazenda A"):
    return Propriedade.objects.create(
        user=user, nome=nome, area_total=500, uf="MT", cidade="Sorriso"
    )


def _lanca(prop, tipo, valor, quando=date(2026, 3, 1), categoria=None):
    """Cria um lancamento. A categoria por omissao segue o `tipo`.

    Era `categoria="INSUMO"` fixa, e `INSUMO` e' despesa —insumo nao entra.
    Os testes que queriam receita acabavam por gravar `RECEITA` com
    `INSUMO`, que e' exactamente o defeito que `LancamentoFinanceiro.clean()`
    recusa. O dado estava incoerente antes de haver regra que o apanhasse:
    o teste passava a medir o ROI com uma receita que era compra de insumo.

    Quem passa `categoria` continua a poder usar a que quiser — a regra e' do
    modelo, e um teste que queira medir essa regra tem de poder montar o caso.
    """
    if categoria is None:
        categoria = "VENDA_PROD" if tipo == "RECEITA" else "INSUMO"
    return LancamentoFinanceiro.objects.create(
        propriedade=prop,
        tipo=tipo,
        valor=Decimal(valor),
        data=quando,
        categoria=categoria,
    )


def _cultura(nome="Soja"):
    return Cultura.objects.create(
        nome=nome, grupo="graos", unidade_comercial="kg", ativo=True
    )


def _safra(prop, ano=2026, area="10", producao="30"):
    return Safra.objects.create(
        propriedade=prop,
        cultura=_cultura(f"Soja {ano}"),
        ano=ano,
        safra_nome=f"Safra {ano}",
        area_plantada=Decimal(area),
        area_colhida=Decimal(area),
        producao_total=Decimal(producao),
    )


class DadosReaisTest(TestCase):
    def setUp(self):
        self.ana = User.objects.create_user("ana", "a@x.com", "p")
        self.prop = _prop(self.ana)
        _lanca(self.prop, "DESPESA", "1000")
        _lanca(self.prop, "RECEITA", "3000")
        _safra(self.prop, area="10", producao="30")

    def _cfg(self, tipo, **kw):
        widgets = [{"tipo": tipo, "titulo": tipo, "config": {}}]
        return enriquece(self.ana, widgets, **kw)[0]["config"]

    def test_custo_por_hectare_e_calculo_real(self):
        cfg = self._cfg("kpi-custo")
        self.assertEqual(cfg["custo_total"], 1000.0)
        self.assertEqual(cfg["area_colhida"], 10.0)
        # 1000 / 10 ha. Um numero inventado aqui seria o pior defeito do
        # produto: o produtor multiplica a area e confere.
        self.assertEqual(cfg["custo_por_ha"], 100.0)

    def test_caixa_entradas_saidas_saldo(self):
        cfg = self._cfg("kpi-caixa")
        self.assertEqual(cfg["entradas"], 3000.0)
        self.assertEqual(cfg["saidas"], 1000.0)
        self.assertEqual(cfg["saldo"], 2000.0)

    def test_roi_calculado(self):
        cfg = self._cfg("kpi-roi")
        # (3000 - 1000) / 1000 = 200%
        self.assertEqual(cfg["roi_pct"], 200.0)

    def test_roi_sem_despesa_nao_da_infinito(self):
        """Na safra em que o produtor não gastou nada, o ROI é infinito. E
        "infinito" numa tela é pior que uma ausência — o produtor lê
        "infinito" e conclui que ganhou dinheiro infinito.

        O produtor é NOVO, de propósito: o `setUp` desta classe tem despesa, e
        um teste que herda o cenário da classe está a testar outra coisa.
        """
        limpo = User.objects.create_user("limpo", "l@x.com", "p")
        prop = _prop(limpo, "Fazenda B")
        _lanca(prop, "RECEITA", "500")
        widgets = [{"tipo": "kpi-roi", "titulo": "roi", "config": {}}]
        cfg = enriquece(limpo, widgets)[0]["config"]
        self.assertNotIn("roi_pct", cfg)
        self.assertEqual(cfg["receita_total"], 500.0)

    def test_produtividade_por_hectare(self):
        cfg = self._cfg("kpi-produtividade")
        # 30 unidades em 10 ha
        self.assertEqual(cfg["produtividade_ha"], 3.0)

    def test_divisao_por_zero_da_none_e_nao_zero(self):
        """Área zero é "não é possível saber", não "a produtividade é zero".

        Produtor novo, com uma safra de área zero e nada mais. Se este teste
        herdasse a safra do `setUp` (área 10, produção 30), o agregado daria
        3,0 e o teste estaria a passar por uma razão errada.
        """
        limpo = User.objects.create_user("zerado", "z@x.com", "p")
        prop = _prop(limpo, "Fazenda Vazia")
        _safra(prop, area="0", producao="0")
        widgets = [{"tipo": "kpi-produtividade", "titulo": "p", "config": {}}]
        cfg = enriquece(limpo, widgets)[0]["config"]
        self.assertIsNone(cfg["produtividade_ha"])

    def test_sem_dado_devolve_vazio_e_nao_zero(self):
        """Um '0' seria uma afirmação: 'a sua fazenda não custou nada'. Não
        é verdade — é que ninguém lançou nada. O vazio é a verdade.

        E o vazio agora DIZ que é vazio. `{}` e
        `{"fonte_dado": "sem_dado", "motivo": ...}` são a mesma coisa para o
        frontend, e nenhum dos dois é accionável: o produtor vê um cartão sem
        nada e não sabe se o trabalho dele se perdeu ou se falta preencher.
        """
        outro = User.objects.create_user("bruno", "b@x.com", "p")
        _prop(outro, "Fazenda Nova")
        widgets = [{"tipo": "kpi-custo", "titulo": "c", "config": {}}]
        cfg = enriquece(outro, widgets)[0]["config"]
        self.assertEqual(cfg.get("fonte_dado"), "sem_dado")
        self.assertTrue(cfg.get("motivo"), "sem_dado tem de dizer o motivo")
        for chave, valor in cfg.items():
            if chave in ("fonte_dado", "motivo"):
                continue
            self.assertNotEqual(valor, 0, f"{chave} = 0 num config sem dado")

        # e, para o contrarium: com lançamentos, o mesmo caminho e' `medido` —
        # e diz de onde foi lido
        com_dados = enriquece(self.ana, [{"tipo": "kpi-custo"}])[0]["config"]
        self.assertEqual(com_dados.get("fonte_dado"), "medido")
        self.assertTrue(com_dados.get("fonte"), "um medido tem de dizer a fonte")

    def test_widget_sem_calculo_fica_vazio(self):
        cfg = self._cfg("kpi-chuva-1km")
        self.assertEqual(cfg, {})


class TenancyDosDadosTest(TestCase):
    """O teste que vale mais. Um vazamento aqui não dá erro nenhum."""

    def setUp(self):
        self.ana = User.objects.create_user("ana", "a@x.com", "p")
        self.bruno = User.objects.create_user("bruno", "b@x.com", "p")
        self.pa = _prop(self.ana, "Fazenda da Ana")
        self.pb = _prop(self.bruno, "Fazenda do Bruno")
        _lanca(self.pa, "DESPESA", "111")
        _lanca(self.pb, "DESPESA", "999999")

    def test_a_mesa_nao_enxerga_a_despesa_do_vizinho(self):
        widgets = [{"tipo": "kpi-custo", "titulo": "c", "config": {}}]
        cfg = enriquece(self.ana, widgets)[0]["config"]
        self.assertEqual(cfg["custo_total"], 111.0)
        # O número do Bruno é 999999 e NÃO pode aparecer em nenhum campo.
        # A comparação é sobre o texto: `assertNotIn(999999.0, str(...))` levanta
        # TypeError, porque `in` sobre uma string quer uma string.
        self.assertNotIn("999999", str(cfg))

    def test_as_duas_mesas_sao_diferentes(self):
        a = enriquece(self.ana, [{"tipo": "kpi-custo", "titulo": "c", "config": {}}])[
            0
        ]["config"]
        b = enriquece(self.bruno, [{"tipo": "kpi-custo", "titulo": "c", "config": {}}])[
            0
        ]["config"]
        self.assertEqual(a["custo_total"], 111.0)
        self.assertEqual(b["custo_total"], 999999.0)

    def test_filtrar_por_propriedade(self):
        """Com duas propriedades do MESMO produtor, filtrar por uma tem de dar
        o número dessa — e só dessa."""
        segunda = _prop(self.ana, "Sede")
        _lanca(segunda, "DESPESA", "50")
        widgets = [{"tipo": "kpi-custo", "titulo": "c", "config": {}}]
        cfg = enriquece(self.ana, widgets, prop=segunda)[0]["config"]
        self.assertEqual(cfg["custo_total"], 50.0)

    def test_filtrar_por_talhao(self):
        talhao = Talhao.objects.create(
            propriedade=self.pa, nome="Talhão 2", area_hectare=5
        )
        self.pa = self.pa
        _lanca(self.pa, "DESPESA", "77", quando=date(2026, 3, 1))
        l2 = LancamentoFinanceiro.objects.create(
            propriedade=self.pa,
            tipo="DESPESA",
            valor=Decimal("5"),
            data=date(2026, 3, 2),
            categoria="INSUMO",
            talhao=talhao,
        )
        widgets = [{"tipo": "kpi-custo", "titulo": "c", "config": {}}]
        cfg = enriquece(self.ana, widgets, talhao="Talhão 2")[0]["config"]
        self.assertEqual(cfg["custo_total"], 5.0, l2.valor)


class CatalogoHonestoTest(TestCase):
    """Cada widget oferecido ao modelo tem de saber de onde vem o dado."""

    def test_todo_widget_declara_a_uma_fonte(self):
        for tipo, spec in palco.CATALOGO_IA.items():
            self.assertIn(spec.get("fonte"), ("servidor", "top_globais"), tipo)

    def test_as_fontes_partem_o_catalogo(self):
        self.assertEqual(
            palco.WIDGETS_SERVIDOR | palco.WIDGETS_TOP_GLOBAIS,
            set(palco.CATALOGO_IA),
        )
        self.assertFalse(palco.WIDGETS_SERVIDOR & palco.WIDGETS_TOP_GLOBAIS)

    def test_um_widget_que_o_servidor_nao_sabe_preencher_nao_se_declara_de_servidor(
        self,
    ):
        """A prevencao de regressao que vem da premissa errada original. `kpi-custo`
        parecia um KPI de custo e era uma entrada de LAYOUT; se voltar a entrar
        no catálogo sem fonte, o teste diz outra vez."""
        for tipo in palco.WIDGETS_SERVIDOR:
            widgets = [{"tipo": tipo, "titulo": tipo, "config": {}}]
            # corre com um produtor SEM dados: um widget que se declara de
            # servidor tem de pelo menos saber responder, mesmo que vazio.
            u = User.objects.create_user(f"u_{tipo}", "u@x.com", "p")
            _prop(u, f"P {tipo}")
            cfg = enriquece(u, widgets)[0]["config"]
            self.assertIsInstance(cfg, dict, tipo)
