"""A tabela de CFOP é uma afirmação de cobertura. Estes testes são a verificação.

Uma tabela de CFOP escrita à mão mente sobre aquilo que cobre. O modo de
falhar não é deitar código abaixo — é deitar código a **funcionar** e a
**não deitar código abaixo**, que é o que o `SEMENTE` do DRE fazia.

Estes testes fixam três decisões, não a lista inteira:

1. Uma entrada é `DESPESA`; uma saída é `RECEITA`. **Nunca o contrário.**
2. Apuração (`6`, `7`) não gera lançamento.
3. Um CFOP fora da tabela é **recusado com motivo**, não adivinhado — nem
   mesmo quando o primeiro dígito sugere uma operação conhecida.
"""

from __future__ import annotations

from django.test import SimpleTestCase

from app.services.cfop import APURACAO, DESCONHECIDO, ENTRADA, SAIDA, classificar


class CategoriaEntradaTest(SimpleTestCase):
    def test_entrada_e_despesa(self):
        cat, motivo = classificar("1102")
        self.assertIsNotNone(cat, f"1102 recusado: {motivo}")
        self.assertEqual(cat.classe, ENTRADA)
        self.assertEqual(cat.tipo_lancamento, "DESPESA")
        self.assertTrue(cat.mexe_estoque, "compra tem de aumentar o estoque")

    def test_saida_e_receita(self):
        cat, motivo = classificar("5102")
        self.assertIsNotNone(cat, f"5102 recusado: {motivo}")
        self.assertEqual(cat.classe, SAIDA)
        self.assertEqual(cat.tipo_lancamento, "RECEITA")

    def test_saida_nao_mexe_no_estoque(self):
        """A venda sai do estoque; o Ampliagro não tem baixa por lote.

        Mesmo que um dia ha baixa, **vender** não pode *aumentar* o estoque
        de insumo — foi o que o importador antigo fazia.
        """
        cat, _ = classificar("5102")
        self.assertFalse(cat.mexe_estoque)

    def test_o_sinal_nunca_se_inverte(self):
        """A invariante mais importante, sobre toda a tabela."""
        for cfop in ("1101", "1102", "1113", "1121", "1904", "2101", "2201", "1199"):
            cat, motivo = classificar(cfop)
            self.assertIsNotNone(cat, f"{cfop} devia ser entrada: {motivo}")
            self.assertEqual(
                cat.tipo_lancamento,
                "DESPESA",
                f"{cfop} é entrada e saiu como {cat.tipo_lancamento}",
            )
        for cfop in ("5101", "5102", "5103", "5115", "5202", "5553", "5199"):
            cat, motivo = classificar(cfop)
            self.assertIsNotNone(cat, f"{cfop} devia ser saída: {motivo}")
            self.assertEqual(
                cat.tipo_lancamento,
                "RECEITA",
                f"{cfop} é saída e saiu como {cat.tipo_lancamento}",
            )


class CategoriaApuracaoTest(SimpleTestCase):
    def test_apuracao_nao_gera_lancamento(self):
        for cfop in ("5901", "6901", "7901", "1202", "2204", "6999"):
            cat, _ = classificar(cfop)
            self.assertIsNotNone(cat, f"{cfop} devia ser apuração")
            self.assertEqual(cat.classe, APURACAO, f"{cfop} devia ser apuração")
            self.assertIsNone(
                cat.tipo_lancamento,
                f"{cfop} de apuração tem tipo de lançamento — ia entrar no DRE",
            )


class ListaBrancaTest(SimpleTestCase):
    """A disciplina: o que não está na tabela, não entra."""

    def test_cfop_desconhecido_e_recusado_com_motivo(self):
        cat, motivo = classificar("9999")
        self.assertIsNone(cat, "CFOP desconhecido foi classificado")
        self.assertIn("9999", motivo)
        self.assertIn("lucro", motivo, "o motivo tem de dizer o que está em jogo")

    def test_cfop_fora_da_tabela_nao_entra_so_pelo_primeiro_digito(self):
        """`1500` começa por 1, mas não está na tabela — e não entra.

        A temptingão é classificar pelo primeiro dígito. Não dá: `1201` é
        retorno (entrada) e `1202` é devolução (apuração), e ambos começam por
        1. Um sinal errado num lançamento é irreversível.
        """
        cat, motivo = classificar("1500")
        self.assertIsNone(cat, "1500 classificado so pelo primeiro digito")
        self.assertIsNotNone(motivo)

    def test_generico_99_entra_pela_regra_do_operador(self):
        """A SEFAZ reserva o sufixo `99` para "outros" de cada operação.

        `5999` é "outra saída" — receita, não apuração. Escrevi o contrário
        na primeira versão deste teste; o primeiro dígito continua a mandar,
        e o `99` só generaliza *dentro* da operação.
        """
        self.assertEqual(classificar("1199")[0].tipo_lancamento, "DESPESA")
        self.assertEqual(classificar("5199")[0].tipo_lancamento, "RECEITA")
        self.assertEqual(classificar("5999")[0].classe, SAIDA)
        self.assertEqual(classificar("6999")[0].classe, APURACAO)

    def test_cfop_malformado_e_recusado(self):
        for entrada in (None, "", "  ", "abc", "51", "51020", "5O12"):
            cat, motivo = classificar(entrada)
            self.assertIsNone(cat, f"CFOP {entrada!r} foi classificado")
            self.assertIsNotNone(motivo, f"CFOP {entrada!r} recusado sem motivo")

    def test_cfop_aceita_int_e_str(self):
        """O XML traz texto; um chamador pode trazer int."""
        self.assertEqual(classificar(5102)[0].tipo_lancamento, "RECEITA")
        self.assertEqual(classificar("5102")[0].tipo_lancamento, "RECEITA")

    def test_constante_desconhecido_existe(self):
        """`DESCONHECIDO` é parte da API pública do módulo.

        Um chamador que compara `cat.classe == DESCONHECIDO` num `None` está a
        comparar `None == 'desconhecido'`, que é sempre falso e sempre passa.
        """
        self.assertIsInstance(DESCONHECIDO, str)
        self.assertNotEqual(DESCONHECIDO, ENTRADA)
        self.assertNotEqual(DESCONHECIDO, SAIDA)
        self.assertNotEqual(DESCONHECIDO, APURACAO)
