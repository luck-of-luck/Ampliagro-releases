"""Auditoria do LCDPR contra o Leiaute 1.3.

O ficheiro fiscal mais perigoso do sistema: um `.txt` errado nao dá erro
nenhum no Ampliagro — da erro em Abril, no e-CAC, com multa em cima.

O QUE MEDI
==========
1. `_formatar_valor` troca PONTO por VIRGULA. O Leiaute 1.3 da RFB e' um
   ficheiro de texto delimitado por `|` com numeros em formato INTEIRO ou
   com PONTO decimal. Virgula decimal e' o formato brasileiro de tela, nao
   de ficheiro. Se o ficheiro leva virgula, o e-CAC le como texto ou
   invalida a linha.

2. O Q100 nao escreve numero de sequencia, e o `9999` conta as linhas
   contando-se a si proprio. A regra e' "numero total de linhas do
   ficheiro, incluindo o 9999". Com `len(linhas) + 1` isso esta certo
   POR ACCIDENTE: `linhas` ainda nao contem o 9999. Mas se alguem acrescentar
   uma linha DEPOIS do 9999, o numero fica errado e nao ha teste.

3. `Saldo inicial deve ser matematicamente zero` — o codigo escreve sempre
   `0,00` com um comentario a dizer que nao e obrigatorio. Coincide com a
   regra. Anotado, nao corrigido.

O QUE ESTA CERTO
================
- CPF/CNPJ real (`self.propriedade.cpf_cnpj`) — ja corrigido
- `pago=True` filtra regime de caixa (recebimento/pagamento efetivo), que e'
  o que o LCDPR exige
- Os 5 blocos do Leiaute 1.3 estao todos presentes: 0000, 0010, 0040, Q100,
  Q200, 9999

DENTES
======
Ver `provar_lcdpr.py`.
"""

from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from app.models.core import Propriedade
from app.models.financeiro import LancamentoFinanceiro
from app.services.lcdpr import LCDPRGenerator


class FormatoNumericoTest(TestCase):
    """O Leiaute 1.3 e' um ficheiro para a RFB, nao para um olho humano."""

    def setUp(self):
        self.u = User.objects.create_user("fiscal_lcdpr", password="x1234567")
        self.u.first_name = "Joao"
        self.u.last_name = "Produtor"
        self.u.save()
        self.prop = Propriedade.objects.create(
            user=self.u,
            nome="Fazenda LCDPR",
            area_total=Decimal("50.00"),
            cpf_cnpj="123.456.789-01",
        )

    def test_o_valor_usa_ponto_e_nao_virgula(self):
        """Ponto decimal. O e-CAC nao le "1.234,56"."""
        gen = LCDPRGenerator(self.prop.id, 2026)
        saida = gen._formatar_valor(Decimal("1234.56"))
        self.assertNotIn(
            ",",
            saida,
            "o LCDPR trocou ponto por virgula. Virgula decimal e' formato de "
            "tela; o ficheiro da RFB usa ponto. Este .txt seria rejeitado no "
            "e-CAC.",
        )
        self.assertEqual(saida, "1234.56")

    def test_o_cpf_sai_so_com_digitos(self):
        """`123.456.789-01` tem pontuacao; o registo 0000 quer so digitos."""
        LancamentoFinanceiro.objects.create(
            propriedade=self.prop,
            data="2026-03-10",
            valor=Decimal("100.00"),
            tipo="RECEITA",
            pago=True,
            descricao="Venda de grao",
        )
        saida = LCDPRGenerator(self.prop.id, 2026).gerar_arquivo()
        reg0000 = [l for l in saida.split("\r\n") if l.startswith("|0000|")][0]
        campo_cpf = reg0000.split("|")[3]
        self.assertEqual(
            campo_cpf,
            "12345678901",
            "o CPF tem de sair so com digitos",
        )
        self.assertNotIn(".", reg0000.split("|")[3])
        self.assertNotIn("-", reg0000.split("|")[3])


class EstruturaDoLeiauteTest(TestCase):
    """Os blocos que o e-CAC exige, e a ordem deles."""

    def setUp(self):
        self.u = User.objects.create_user("fiscal_est", password="x1234567")
        self.prop = Propriedade.objects.create(
            user=self.u,
            nome="Faz",
            area_total=Decimal("10.00"),
            cpf_cnpj="12345678901",
        )
        LancamentoFinanceiro.objects.create(
            propriedade=self.prop,
            data="2026-03-10",
            valor=Decimal("1000.00"),
            tipo="RECEITA",
            pago=True,
            descricao="Receita de teste",
        )
        self.linhas = LCDPRGenerator(self.prop.id, 2026).gerar_arquivo().split("\r\n")
        self.linhas = [l for l in self.linhas if l]

    def test_os_blocos_do_leiaute_estao_todos(self):
        for bloco in ("0000", "0010", "0040", "Q100", "Q200", "9999"):
            self.assertTrue(
                any(l.startswith(f"|{bloco}|") for l in self.linhas),
                f"falta o bloco {bloco} — o ficheiro seria incompleto",
            )

    def test_a_ordem_e_correta(self):
        """0000 abre, 9999 fecha. O e-CAC le pela ordem."""
        ordem = [l.split("|")[1] for l in self.linhas]
        self.assertEqual(ordem[0], "0000", "o ficheiro nao abre com o 0000")
        self.assertEqual(ordem[-1], "9999", "o ficheiro nao fecha com o 9999")

    def test_o_9999_conta_o_numero_correto_de_linhas(self):
        """O numero e' o total de linhas DO FICHEIRO, incluindo o 9999."""
        ultimo = self.linhas[-1].split("|")
        declarado = int(ultimo[2])
        self.assertEqual(
            declarado,
            len(self.linhas),
            f"o 9999 declara {declarado} linhas e o ficheiro tem {len(self.linhas)}",
        )

    def test_o_q200_tem_doze_meses(self):
        """Resumo mensal: 12 linhas, uma por mes."""
        q200 = [l for l in self.linhas if l.startswith("|Q200|")]
        self.assertEqual(len(q200), 12, "o Q200 tem de ter 12 meses")
        meses = [l.split("|")[2] for l in q200]
        self.assertEqual(meses, [f"{m:02d}" for m in range(1, 13)])

    def test_a_sofra_de_caixa_filtra_pago(self):
        """Regime de caixa: so entra o que foi efetivamente pago/recebido."""
        LancamentoFinanceiro.objects.create(
            propriedade=self.prop,
            data="2026-04-10",
            valor=Decimal("9999.00"),
            tipo="RECEITA",
            pago=False,  # em aberto — NAO entra
            descricao="A receber",
        )
        q100 = [
            l
            for l in LCDPRGenerator(self.prop.id, 2026).gerar_arquivo().split("\r\n")
            if l.startswith("|Q100|")
        ]
        for l in q100:
            self.assertNotIn(
                "A receber",
                l,
                "um lancamento em aberto entrou no ficheiro de regime de caixa",
            )


class SaldoInicialTest(TestCase):
    """O Q100 nao escreve saldo linha-a-linha.

    ANOTADO, NAO CORRIGIDO. Escrevi este teste para confirmar, e o ficheiro
    nao tem o campo: `lcdpr.py:63-65` mete sempre `0` com o comentario
    "Saldo nao e' obrigatorio no Q100 linha a linha para esta versao".

    Nao afirmo que isso viola o Leiaute 1.3 — nao tenho o documento da RFB
    comigo para confirmar, e um ficheiro fiscal nao se corrige por opiniao.
    Fica registado como PERGUNTA, nao como achado.
    """

    def setUp(self):
        self.u = User.objects.create_user("fiscal_saldo", password="x1234567")
        self.prop = Propriedade.objects.create(
            user=self.u, nome="F", area_total=Decimal("10.00"), cpf_cnpj="12345678901"
        )

    def test_o_registro_mete_zero_e_nao_um_saldo_calculado(self):
        """Constata o estado actual. Se mudar, este teste avisa."""
        LancamentoFinanceiro.objects.create(
            propriedade=self.prop,
            data="2026-01-05",
            valor=Decimal("500.00"),
            tipo="RECEITA",
            pago=True,
            descricao="r",
        )
        linha = [
            l
            for l in LCDPRGenerator(self.prop.id, 2026).gerar_arquivo().split("\r\n")
            if l.startswith("|Q100|")
        ][0]
        campos = linha.split("|")
        # len=13. posicoes medidas no ficheiro real:
        #  [0]='' [1]=Q100 [2]=data [3]=imovel [4]=cpf [5]=doc
        #  [6]=tipo_doc [7]=historico [8]=valor [9]=tipo_lanc [10]=sep
        #  [11]=saldo [12]=''
        # `split("|")` come o separador, e um separador a mais no fim
        # desloca o indice — foi o que me fez ler '1' onde estava '0.00'.
        self.assertEqual(
            campos[11],
            "0.00",
            "o Q100 passou a escrever um saldo calculado. Se o Leiaute passou "
            "a exige-lo, tem de estar certo — rever entao `lcdpr.py:78-80`.",
        )

    def test_o_0040_escreve_a_area_no_formato_do_ficheiro(self):
        """A area vai no mesmo formato numerico do resto do ficheiro.

        ESTE TESTE NAO TEM DENTES, E E' HONESTO DIZER-SE.

        A correccao do 0040 e' correcta (`_formatar_valor(area_total)` em vez
        de `area_total` cru), mas nao consigo provar por este caminho.
        Verifiquei antes de escrever:

            f"{Decimal('1234.50'):.2f}"  ->  "1234.50"
            str(Decimal("1234.50"))       ->  "1234.50"

        Sao a MESMA string. O `Decimal.__str__` ja usa ponto, e o campo e'
        `DecimalField`, nunca `float` nem `str`. Entao a mutacao M2 — voltar
        a escrever o valor cru — NAO faz este teste falhar.

        Nao vou fabricar um teste verde que nao mede nada. Foi exactamente esse
        o erro que fiz com o XXE: escrevi um teste que passava com o parser
        nativo, publiquei a correccao, e so quando parti o produto e' que
        percebi que nao media a diferenca que eu dizia medir.

        O que este teste garante: a area tem o formato do ficheiro. Se
        alguem mudar `_formatar_valor` para outra coisa, aqui salta.
        """
        prop = Propriedade.objects.create(
            user=self.u,
            nome="G",
            area_total=Decimal("1234.50"),
            cpf_cnpj="98765432100",
        )
        linha = [
            l
            for l in LCDPRGenerator(prop.id, 2026).gerar_arquivo().split("\r\n")
            if l.startswith("|0040|")
        ][0]
        area = linha.split("|")[5]
        self.assertNotIn(
            ",",
            area,
            "a area saiu com virgula decimal — e' o separador de milhar, nao "
            "o decimal. O ficheiro da RFB usa ponto.",
        )
        self.assertEqual(area, "1234.50")
