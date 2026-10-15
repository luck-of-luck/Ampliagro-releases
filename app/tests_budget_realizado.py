"""Orçamento x realizado: três defeitos numa função de 120 linhas.

`app/api/views/custos.py:135` `budget_vs_realizado` está no comparativo 100×50
como veredicto **N** — e havia código. Re-medi e o código tem três defeitos que
fazem a comparação errar. Nenhum deles levanta excepção: todos são silenciosos.

## 1. `COMBUSTIVEL` duas vezes no mesmo dict

Linhas 179 e 182 mapeiam `COMBUSTIVEL` — uma para `insumos`, outra para
`maquina`. **Um dict Python descarta a chave repetida em silêncio**, e fica a
última. O resultado: `insumos` nunca recebe combustível, e a linha 179 parece
viva a quem lê.

Qual das duas é a intenção certa é uma pergunta de agronomia — combustível é
custo de máquina, não insumo. O defeito não é a escolha: é **não haver sinal
de que houve escolha**, e o próximo que editar o mapa não sabe que a linha 179
é código morto.

`test_combustivel_nao_esta_duplicado_no_mapa` verifica o que o Python não
verifica sozinho.

## 2. `realizado["custo_total"]` fica sempre 0.00

O dict `realizado` é inicializado com `"custo_total": 0` (linhas 193–205) e o
loop nunca escreve nele: `custo_total` não é chave de `cat_to_campo`. O
custo total do realizado é calculado **outro sitio** (linhas 233–244, dentro do
`comparativo`).

Resultado: a mesma resposta devolve **dois números para a mesma coisa**, e o
`realizado.custo_total` da raiz é sempre `0.00` enquanto o
`comparativo.custo_total.realizado` está certo. O produtor que lê o primeiro
vê que não gastou nada.

## 3. `percentual` com budget zero devolve 100

Linha 252: `(r / b * 100) if b else (100 if r else 0)`.

Com budget 0 e realizado 500, diz **100%** — "gastaste exactamente o
previsto". A verdade é "não há orçamento previsto para comparar". É a
conflação `0`/`None` outra vez, e aqui numa linha que alguém lê para decidir
se estoura o custo.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from app.models import (
    Cultura,
    CustoProducao,
    LancamentoDetalhado,
    LancamentoFinanceiro,
    Propriedade,
    Safra,
)


class BudgetVsRealizadoTest(TestCase):
    def setUp(self):
        self.u = User.objects.create_user("prod", password="x")
        self.prop = Propriedade.objects.create(
            user=self.u,
            nome="Fazenda",
            area_total=Decimal("100.00"),
            uf="MT",
            cidade="Sorriso",
        )
        self.cultura = Cultura.objects.create(nome="Soja")
        self.safra = Safra.objects.create(
            propriedade=self.prop,
            cultura=self.cultura,
            ano=2026,
            area_plantada=Decimal("50.00"),
            producao_total=Decimal("30000.00"),
            data_plantio=date(2026, 10, 5),
        )
        self.client.force_login(self.u)

    def _custo(self, **kw):
        """Cria um CustoProducao.

        `custo_total` **não** se passa: `CustoProducao.save()` recalcula-o a
        partir dos sete componentes (`models/custos.py:120-127`). Passar
        `custo_total=1000` com os componentes a zero dá `custo_total = 0` — e
        foi isso que me enganou na primeira versão deste teste.
        """
        componentes = {
            k: kw.pop(k, Decimal("0.00"))
            for k in (
                "insumos",
                "maquina",
                "mao_de_obra",
                "embalagem",
                "frete",
                "impostos",
                "outros",
            )
        }
        return CustoProducao.objects.create(
            safra=self.safra,
            talhao=None,
            centro_custo=None,
            receita=kw.pop("receita", None),
            **componentes,
            **kw,
        )

    def _detalhe(self, categoria, valor):
        lanc = LancamentoFinanceiro.objects.create(
            propriedade=self.prop,
            tipo="DESPESA",
            categoria="OUTRO",
            valor=Decimal(valor),
            data=date(2026, 3, 10),
        )
        return LancamentoDetalhado.objects.create(
            lancamento=lanc,
            _propriedade=self.prop,
            safra=self.safra,
            categoria_detalhada=categoria,
            valor_rateado=Decimal(valor),
        )

    def _chama(self):
        """Pela rota real (`api/urls.py:187`), não instanciando o viewset.

        Instanciar o viewset à mão salta o `get_queryset` real e o
        `permission_classes` — e um teste que passa por um caminho que o
        cliente não usa não prova nada sobre o cliente.
        """
        r = self.client.get(
            f"/api/custos-producao/budget_vs_realizado/?safra={self.safra.id}"
        )
        self.assertEqual(r.status_code, 200, r.content[:300])
        return r.json()

    # ------------------------------------------------------------------
    # Defeito 1 — chave duplicada
    # ------------------------------------------------------------------

    def test_combustivel_nao_esta_duplicado_no_mapa(self):
        """O Python aceita a chave repetida; o Ampliagro não devia."""
        import inspect

        from app.api.views import custos

        fonte = inspect.getsource(custos)
        linhas = [
            l.strip()
            for l in fonte.split("\n")
            if '"COMBUSTIVEL"' in l and "cat_to_campo" not in l
        ]
        # A linha do template `categoria_detalhada` tambem menciona; so conta
        # a que esta dentro do mapa de categorias.
        dentro_do_mapa = [l for l in linhas if l.startswith('"COMBUSTIVEL":')]
        self.assertEqual(
            len(dentro_do_mapa),
            1,
            f"COMBUSTIVEL mapeado {len(dentro_do_mapa)} vezes — a primeira "
            "e descartada em silencio",
        )

    def test_combustivel_conta_uma_vez_so(self):
        """Com combustível R$ 100, o total realizado tem de incluir 100 — uma vez."""
        self._custo(maquina=Decimal("1000.00"))
        self._detalhe("COMBUSTIVEL", "100.00")

        d = self._chama()
        comp = d["comparativo"]["custo_total"]

        self.assertAlmostEqual(comp["realizado"], 100.0, places=2)
        # E não pode estar nos dois sítios: 200 seria duplicado.
        self.assertNotAlmostEqual(comp["realizado"], 200.0, places=2)

    # ------------------------------------------------------------------
    # Defeito 2 — custo_total sempre zero na raiz
    # ------------------------------------------------------------------

    def test_o_total_so_existe_no_comparativo(self):
        """O total realizado vive em `comparativo.custo_total`, e só lá.

        Afirmei na primeira versão deste ficheiro que `realizado.custo_total`
        ficava sempre a `0.00` e que a resposta tinha "dois números para a
        mesma coisa". **Estava errado** — a chave não existe no dict `realizado`,
        e o total é calculado dentro do `comparativo`. O teste agora fixa o
        contrato verdadeiro em vez de um defeito que não existe.
        """
        self._custo(insumos=Decimal("500.00"))
        self._detalhe("COMPRA_SEMENTE", "500.00")

        d = self._chama()

        self.assertNotIn(
            "custo_total",
            d["realizado"],
            "o total na raiz invites double counting; so deve estar no comparativo",
        )
        self.assertAlmostEqual(
            d["comparativo"]["custo_total"]["realizado"], 500.0, places=2
        )

    # ------------------------------------------------------------------
    # Defeito 3 — 100% com budget zero
    # ------------------------------------------------------------------

    def test_budget_zero_nao_diz_100_por_cento(self):
        """Budget 0 com gasto 500 não é "gastaste 100% do previsto".

        Não há previsto. Dizer 100% é afirmar que o custo foi exactamente o
        planeado, e é a leitura que um produtor usa para decidir se estoura.
        """
        self._custo()
        self._detalhe("COMPRA_SEMENTE", "500.00")

        d = self._chama()
        pct = d["comparativo"]["custo_total"]["percentual"]

        self.assertNotEqual(
            pct,
            100.0,
            "budget zero com gasto leu 100% — devia declarar que nao ha previsto",
        )

    def test_budget_zero_e_gasto_zero_da_zero(self):
        """Zero e zero é uma medição: 0% é correcto e não precisa de `None`."""
        self._custo()
        d = self._chama()
        self.assertEqual(d["comparativo"]["custo_total"]["percentual"], 0.0)

    # ------------------------------------------------------------------
    # Nenhuma categoria pode cair no default em silêncio
    # ------------------------------------------------------------------

    def test_toda_categoria_ou_esta_mapeada_ou_e_receita(self):
        """Ou está no mapa, ou é receita tratada à parte.

        O resto cai no default `"outros"` (linha do `.get()`) sem aviso. Uma
        categoria a cair em "outros" continua a ser somada — o dinheiro não
        perde-se — mas a comparação passa a dizer que se gastou em "outros"
        quando o produtor sabe que foi em coisa. E ninguém é avisado.
        """
        import re

        from app.api.views import custos as v

        def _lista(texto):
            i = texto.find("CATEGORIA_DETALHADA_CHOICES")
            seg = texto[i : texto.find("]", i) + 1]
            return re.findall(r'\("([A-Z_0-9]+)"', seg)

        def _mapa(texto):
            j = texto.find("cat_to_campo = {")
            return re.findall(r'"([A-Z_0-9]+)"\s*:', texto[j : texto.find("}", j)])

        def _le(caminho):
            with open(caminho, encoding="utf-8") as fh:
                return fh.read()

        todas = _lista(_le("app/models/custos.py"))
        mapa = _mapa(_le(v.__file__))

        # As receitas são tratadas pelo `startswith("VENDA_")` antes do mapa.
        nao_mapeadas = [
            c
            for c in todas
            if c not in mapa and not c.startswith("VENDA_") and c != "OUTRA_RECEITA"
        ]
        self.assertEqual(
            nao_mapeadas,
            [],
            f"categorias a cair no default 'outros', sem aviso: {nao_mapeadas}",
        )

    def test_compra_de_combustivel_continua_insumo(self):
        """Regressão minha: ao limpar a chave duplicada, apaguei esta.

        `COMPRA_COMBUSTIVEL` (a compra) e `COMBUSTIVEL` (o consumo) são coisas
        diferentes — a compra é insumo, o consumo é operação de máquina. Ao
        remover a linha duplicada de `COMBUSTIVEL` levei `COMPRA_COMBUSTIVEL`
        consigo, e a compra passou a cair em `"outros"`.

        O `git diff` mostrava a remoção; o que me apanhou foi reler o HEAD.
        """
        self._custo(insumos=Decimal("500.00"))
        self._detalhe("COMPRA_COMBUSTIVEL", "500.00")

        d = self._chama()
        self.assertAlmostEqual(d["realizado"]["insumos"], 500.0, places=2)
        self.assertAlmostEqual(d["realizado"]["outros"], 0.0, places=2)

    def test_diferenca_e_percentual_sao_coerentes(self):
        self._custo(insumos=Decimal("1000.00"))
        self._detalhe("COMPRA_SEMENTE", "1500.00")

        d = self._chama()
        c = d["comparativo"]["custo_total"]

        self.assertAlmostEqual(c["diferenca"], 500.0, places=2)
        self.assertAlmostEqual(c["percentual"], 150.0, places=1)

    def test_receita_nao_conta_como_custo(self):
        """Uma venda é receita, não custo. Somar as duas dá um número falso."""
        self._custo(insumos=Decimal("1000.00"))
        lanc = LancamentoFinanceiro.objects.create(
            propriedade=self.prop,
            tipo="RECEITA",
            categoria="VENDA_PROD",
            valor=Decimal("5000.00"),
            data=date(2026, 3, 10),
        )
        LancamentoDetalhado.objects.create(
            lancamento=lanc,
            _propriedade=self.prop,
            safra=self.safra,
            categoria_detalhada="VENDA_SOJA",
            valor_rateado=Decimal("5000.00"),
        )

        d = self._chama()
        self.assertAlmostEqual(d["realizado"]["receita"], 5000.0, places=2)
        self.assertAlmostEqual(
            d["comparativo"]["custo_total"]["realizado"], 0.0, places=2
        )
