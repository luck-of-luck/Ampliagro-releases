"""O filtro de posse da rede de preços — a falha que encontrei e corrigi.

## O que aconteceu

Escrevi `preco_referencia(produto, ...)` a filtrar por `tipo="RECEITA"` e por
`descricao__icontains=produto`. **Sem qualquer filtro de posse.**

Num deploy self-hosted de um produtor, isso é correcto e é o fosso: o ledger
dele é o dataset. Num deploy multi-tenant, o produtor A pergunta "qual o preço
da soja" e recebe a mediana, a contagem de transações e a contagem de fazendas
do produtor B.

## Porque o middleware não apanhava

`TenantIsolationMiddleware` valida **ids que chegam no pedido** —
`propriedade_id`, `fazenda_id`, `talhao_id`, `device_id` — e resolve cada um
dentro do utilizador. A docstring dele é explícita sobre o que é:

> "Garante que tudo que o request traz pertence ao utilizador."

**Não é um filtro de querysets.** Uma query de serviço que não filtra por dono
passa por ele intacta, porque não há nenhum parâmetro para ele rejeitar.

Isto é a diferença entre "o middleware está activo" e "o middleware protege
isto". Proteger **uma classe de inputs** não protege **uma classe de
queries** — e o meu serviço é da segunda.

## O que corrigi

`preco_referencia(user, produto, ...)` — o `user` é o **primeiro** argumento,
sem default, e a query filtra por `propriedades_visiveis(user)`.

Primeiro e sem default de propósito: um filtro de posse opcional é um filtro
que alguém esquece, e quem esquece é quem o escreve a seguir.

## A consequência honesta na promessa

`n_fazendas` passa a contar as fazendas **que o user pode ver**. Num dono
único isso é 1, e `concentracao_top1` é 1.0 — o que é a verdade, não um
número de mercado.

Isto **enfraquece** a promessa da §23G, e é o correcto. A concentração só
passa a ser um dado de mercado quando houver um âmbito partilhado explícito
(uma cooperativa com vínculo 1:N, que a §23D bloqueou por um perfil só
alcançar duas propriedades). Até lá, o número é o que é.

Publicar a concentração a 100% de uma fazenda própria seria honesto **e
inútil** — que é uma coisa diferente de ser enganoso.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from app.models import LancamentoFinanceiro, Propriedade
from app.services.rede_precos import preco_referencia


class PrecoPosseTest(TestCase):
    def setUp(self):
        self.eu = User.objects.create_user("eu", password="x")
        self.outro = User.objects.create_user("outro", password="x")

        # `valor_total` de 100 SC a R$ 1,50 = 150,00 -> 1,50 por unidade.
        self.minha = self._fazenda(self.eu, "Minha", total="150.00", preco="1.50")
        self.alheia = self._fazenda(self.outro, "Alheia", total="900.00", preco="9.00")

    def _fazenda(self, user, nome, total, preco):
        prop = Propriedade.objects.create(
            user=user,
            nome=nome,
            area_total=Decimal("100.00"),
            uf="MT",
            cidade="Sorriso",
        )
        for _ in range(5):
            LancamentoFinanceiro.objects.create(
                propriedade=prop,
                tipo="RECEITA",
                categoria="VENDA_PROD",
                descricao="NF-e SOJA",
                valor=Decimal(total),
                data=date(2026, 3, 10),
                quantidade=Decimal("100"),
                unidade="SC",
                cfop="5102",
            )
        return prop

    # ------------------------------------------------------------------

    def test_nao_ve_preco_de_outro_produtor(self):
        """A falha original: a mediana vinha de toda a base."""
        r = preco_referencia(self.eu, "SOJA")

        self.assertAlmostEqual(
            r["unidades"]["SC"]["mediana"],
            1.50,
            places=2,
            msg="a mediana includeu as vendas de outro produtor",
        )
        self.assertNotIn(
            self.alheia.id, r["transacoes_por_fazenda"], "viu a fazenda alheia"
        )
        self.assertEqual(r["n_transacoes"], 5, "contou transações alheias")

    def test_n_fazendas_so_conta_o_que_e_visivel(self):
        """`n_fazendas` tem de ser verdade, não uma ambição."""
        r = preco_referencia(self.eu, "SOJA")
        self.assertEqual(r["n_fazendas"], 1)

    def test_a_concentracao_de_um_dono_unico_e_um(self):
        """100% de uma fazenda própria é a verdade — e é inútil.

        Publicar isto como dado de mercado seria enganoso. O serviço
        devolve-o, porque é medido, e a promessa de §23G diz que só é
        referência com volume.
        """
        r = preco_referencia(self.eu, "SOJA")
        self.assertEqual(r["concentracao_top1"], 1.0)

    def test_cada_produtor_ve_o_seu_preco(self):
        meu = preco_referencia(self.eu, "SOJA")
        dele = preco_referencia(self.outro, "SOJA")

        self.assertAlmostEqual(meu["unidades"]["SC"]["mediana"], 1.50, places=2)
        self.assertAlmostEqual(dele["unidades"]["SC"]["mediana"], 9.00, places=2)

    def test_user_e_obrigatorio(self):
        """O `user` é o primeiro argumento e não tem default.

        Um filtro de posse opcional é um filtro que alguém esquece — e quem
        esquece é quem escreve o próximo serviço.
        """
        import inspect

        assinatura = inspect.signature(preco_referencia)
        parametros = list(assinatura.parameters.values())

        self.assertEqual(parametros[0].name, "user")
        self.assertIs(
            parametros[0].default, inspect.Parameter.empty, "user tem default"
        )
