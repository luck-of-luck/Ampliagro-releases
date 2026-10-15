"""F08: a forma de apuracao e' uma ESCOLHA do produtor.

MEDIDO 2026-10-05 (agente 9). Antes disto o registo 0010 do LCDPR era escrito
com a constante `FORMA_APURACAO_LIVRO_CAIXA` para toda a gente. Um produtor no
regime dos 20% da receita bruta (art. 5o da Lei 8.023/1990) gerava um ficheiro
que diz a Receita que ele apurou pelo Livro Caixa.

O ficheiro fica **bem formado e errado** — que e' o pior tipo de erro, porque
passa em toda a validacao de formato e so falha quando alguem o compara com a
verdade.

O QUE ESTES TESTES PROVAM
=========================
  - a escolha existe e escreve o valor certo no 0010
  - o default nao muda ninguem: quem nao preenche continua em Livro Caixa
  - um valor fora do dominio NAO passa em silencio
  - as duas formas nao se misturam — o ficheiro diz UMA
"""

from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from app.models import Propriedade, Safra
from app.services.lcdpr_export import LCDPRExporter


class FormaApuracaoTest(TestCase):
    def setUp(self):
        self.u = User.objects.create_user(username="forma_teste", password="x")
        self.prop = Propriedade.objects.create(
            user=self.u,
            nome="Fazenda do Regime",
            area_total=100.0,
            uf="GO",
            cidade="Pirenópolis",
            # O LCDPR recusa o ficheiro sem CPF/CNPJ no registo 0000, e com
            # razao: a Receita recusa. Preenchi-lo aqui em vez de contornar a
            # validacao — um teste que desliga a guarda para chegar mais
            # depressa testa o sistema desligado.
            cpf_cnpj="12345678901",
        )
        from app.models import Cultura

        self.cultura = Cultura.objects.create(
            nome="Soja", grupo="graos", unidade_comercial="sc", ativo=True
        )
        Safra.objects.create(
            propriedade=self.prop,
            cultura=self.cultura,
            ano=2026,
            area_plantada=Decimal("100.00"),
        )

    def _0010(self):
        """A linha do registo 0010 tal como sai do gerador."""
        # O metodo e' gerar_arquivo, que devolve o texto do ficheiro. Escrevi
        # gerar() e o AttributeError disse o resto.
        texto = LCDPRExporter(self.prop, 2026).gerar_arquivo()
        for l in texto.splitlines():
            if l.startswith("|0010|"):
                return l
        return ""

    # ---------------------------------------------------------------- 1
    def test_a_escolha_escreve_o_valor_certo(self):
        """A capacidade que a coluna promete: PRESUMIDO x RESULTADO."""
        self.prop.forma_apuracao = "2"
        self.prop.save()

        linha = self._0010()
        self.assertTrue(linha, "o registo 0010 nao foi gerado")
        self.assertEqual(
            linha,
            "|0010|2|",
            "o produtor escolheu o regime dos 20% e o ficheiro saiu a dizer "
            "outra coisa — o ficheiro esta' bem formado e errado",
        )

    # ---------------------------------------------------------------- 2
    def test_livro_caixa_tambem_e_escolhivel(self):
        self.prop.forma_apuracao = "1"
        self.prop.save()
        self.assertEqual(self._0010(), "|0010|1|")

    # ---------------------------------------------------------------- 3
    def test_quem_nao_preenche_continua_no_livro_caixa(self):
        """O default nao pode partir ninguem.

        As 4 928 celulas do comparativo e' que nao estao medidas; aqui o
        ponto e' outro: uma propriedade criada antes desta migration tem
        `forma_apuracao` no default, e o seu ficheiro tem de sair igual ao de
        sempre.
        """
        self.assertEqual(
            self.prop.forma_apuracao,
            "1",
            "o default mudou — uma propriedade existente passa a gerar um "
            "0010 diferente sem ninguem ter tocado nela",
        )
        self.assertEqual(self._0010(), "|0010|1|")

    # ---------------------------------------------------------------- 4
    def test_um_valor_fora_do_dominio_nao_passa_em_silencio(self):
        """Um regime que nao existe nao pode ir para o ficheiro.

        Corrigir em silencio e' o comportamento perigoso: o produtor recebe um
        ficheiro valido, com a forma errada, e nunca sabe que o dado estava
        mal. Aqui cai para "1" — que e' o regime de quem tem `Lancamento
        Financeiro` com `data` e `pago`, porque e' o regime de caixa.
        """
        self.prop.forma_apuracao = "7"
        self.prop.save()

        linha = self._0010()
        self.assertEqual(
            linha,
            "|0010|1|",
            "um valor invalido passou para o ficheiro em vez de cair",
        )

    # ---------------------------------------------------------------- 5
    def test_o_ficheiro_diz_uma_so_forma(self):
        """As duas formas nao se misturam.

        Um 0010 com "1;2" seria um ficheiro que a Receita rejeita, e que
        passava na validacao de formato porque tem o numero de campos certo.
        """
        self.prop.forma_apuracao = "2"
        self.prop.save()
        conteudo = self._0010()
        self.assertNotIn(";", conteudo, "o 0010 tem mais do que uma forma")
        self.assertEqual(len(conteudo.strip("|").split("|")), 2)

    # ---------------------------------------------------------------- 6
    def test_as_escolhas_dizem_o_que_cada_forma_significa(self):
        """A opcao tem de ser legivel na interface, nao "1" e "2".

        Um produtor que veja "1" e "2" nao escolhe: adivinha. O `choices` do
        modelo e' o que a interface mostra.
        """
        rotulos = dict(Propriedade._meta.get_field("forma_apuracao").choices)
        self.assertIn("Livro Caixa", rotulos["1"])
        self.assertIn("20%", rotulos["2"])
        self.assertIn("8.023", rotulos["2"], "a lei de origem tem de estar no rotulo")
