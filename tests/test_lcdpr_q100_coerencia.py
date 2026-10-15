"""O Q100 do botão tinha dois defeitos que nenhum teste via.

MEDIDO 2026-10-04 (agente 9), comparando os dois geradores de LCDPR sobre o
mesmo dado. Este ficheiro não é sobre o leiaute da Receita — é sobre coisas
que se provam sem o documento da Receita.

Bug 1 — a receita saía classificada como despesa
------------------------------------------------
`LancamentoFinanceiro.tipo_lancamento_lcdpr` tem `default="2"`, e "2" é
"Despesa de Custeio e Investimentos" (`app/models/financeiro.py:99-111`).
O gerador copiava esse campo cru para o Q100 sem o comparar com `l.tipo`:

    |Q100|15032026|1|||6|Venda de grao||2|1234.56||1234.56 S|
                                ^^                  ^^^^^^^^
                          diz "despesa"     o valor está na coluna de ENTRADA

Uma receita de R$ 1.234,56 classificada como despesa, na mesma linha em que o
valor entra como entrada. Quem valida o ficheiro em Abril lê o "2".

Bug 2 — um `|` no texto deslocava a linha toda
----------------------------------------------
Os registos são texto delimitado por `|`, e vários campos recebem texto **que o
produtor escreve**: descrição, número de documento, endereço. Nenhum era
limpo, e um `|` num deles empurra todos os campos seguintes uma posição.

Por que ninguém viu
-------------------
`app/services/lcdpr.py:78` faz o Bug 1 **bem**
(`tipo_lanc = "1" if lanc.tipo == "RECEITA" else "2"`), e
`tests/test_lcdpr_leiaute.py` audita **esse** gerador. O gerador que o botão
chama é outro. É a classe de falha que o `MERGED.md` §7.4 descreve —
"correção documentada como feita, e não feita" — num ficheiro que vai para a
Receita.
"""

from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from app.models.core import Propriedade
from app.models.financeiro import LancamentoFinanceiro
from app.services.lcdpr_export import LCDPRExporter

#: O Q100 é escrito por `lcdpr_layout.linha_lcdpr_q100`. Os índices abaixo são
#: posições DIRECTAS na lista que `split("|")` produz — e o primeiro elemento
#: é vazio, porque a linha começa no separador. Por isso a data é 2, não 1.
CAMPO_DATA = 2
CAMPO_TIPO_DOC = 6
CAMPO_HIST = 7
CAMPO_PART = 8
CAMPO_TIPO = 9
CAMPO_ENTRADA = 10
CAMPO_SAIDA = 11
CAMPO_SALDO = 12

RECEITA = "1"  # Receita da Atividade Rural
DESPESA = "2"  # Despesa de Custeio e Investimentos
ADIANTAMENTO = "3"  # Produtos entregues a adiantamento


def campo(linha, indice):
    """Valor do campo na posição `indice` da linha splitada por `|`."""
    partes = linha.split("|")
    return partes[indice] if len(partes) > indice else ""


class Q100CoerenciaTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("q100", "q100@x.com", "x")

        # MEDIDO 2026-10-05: este `setUp` estava desatualizado. A
        # `LCDPRDadosIncompletos` exige talhoes cadastrados — o `0040` declara
        # imoveis rurais, e uma propriedade sem talhao nao tem imoveis. Sete
        # testes falhavam por isto, **sem que houvesse defeito no que
        # testavam**. A guarda esta certa; o cenario de teste e' que estava mal.
        # Detalhe do raciocinio: `tests/lcpr_fixtures.py`.
        from tests.lcpr_fixtures import propriedade_com_imoveis

        self.prop = propriedade_com_imoveis(
            self.user,
            nome="Fazenda Q100",
            cpf_cnpj="12345678901",
            area_total=Decimal("100.00"),
        )

    def _lancamento(self, **kw):
        base = {
            "propriedade": self.prop,
            "data": "2026-03-15",
            "categoria": "Venda",
            "descricao": "Venda de grao",
            "pago": True,
        }
        base.update(kw)
        return LancamentoFinanceiro.objects.create(**base)

    def _ficheiro(self):
        return LCDPRExporter(self.prop, 2026).gerar_arquivo()

    def _q100(self):
        return [x for x in self._ficheiro().splitlines() if x.startswith("|Q100|")]

    # ------------------------------------------------------------------
    # Bug 1 — o tipo do lançamento
    # ------------------------------------------------------------------

    def test_uma_receita_nao_sai_classificada_como_despesa(self):
        """A receita tem de ir como receita. Este teste falhava."""
        self._lancamento(tipo="RECEITA", valor=Decimal("1234.56"))

        linhas = self._q100()
        self.assertEqual(len(linhas), 1, "o lancamento devia ter saido no ficheiro")

        tipo = campo(linhas[0], CAMPO_TIPO)
        self.assertEqual(
            tipo,
            RECEITA,
            f"a receita de 1234.56 saiu com tipo {tipo!r} (despesa). O valor "
            "esta na coluna de entrada, portanto 'despesa' e' contraditorio "
            "com a propria linha.",
        )
        self.assertEqual(campo(linhas[0], CAMPO_ENTRADA), "1234.56")
        self.assertEqual(campo(linhas[0], CAMPO_SAIDA), "", "a receita nao tem saida")

    def test_uma_despesa_continua_despesa(self):
        """A correcção não pode inverter o caso simétrico."""
        self._lancamento(
            tipo="DESPESA",
            categoria="Custo",
            descricao="Semente",
            data="2026-04-20",
            valor=Decimal("300.00"),
        )

        linhas = self._q100()
        self.assertEqual(len(linhas), 1)
        self.assertEqual(campo(linhas[0], CAMPO_TIPO), DESPESA)
        self.assertEqual(campo(linhas[0], CAMPO_SAIDA), "300.00")
        self.assertEqual(campo(linhas[0], CAMPO_ENTRADA), "")

    def test_o_tipo_agrees_com_a_coluna_em_que_o_valor_entrou(self):
        """A invariante, sem depender do Leiaute.

        Se há valor na entrada e o tipo diz despesa — ou valor na saída e o
        tipo diz receita — a linha mente sobre si mesma. Isso é errado
        qualquer que seja a posição dos campos no documento da Receita.
        """
        self._lancamento(tipo="RECEITA", valor=Decimal("1234.56"), data="2026-03-15")
        self._lancamento(
            tipo="DESPESA",
            categoria="Custo",
            descricao="Semente",
            data="2026-04-20",
            valor=Decimal("300.00"),
        )
        self._lancamento(
            tipo="RECEITA",
            descricao="Adiantamento",
            data="2026-05-10",
            valor=Decimal("500.00"),
            tipo_lancamento_lcdpr=ADIANTAMENTO,
        )

        linhas = self._q100()
        self.assertEqual(len(linhas), 3)

        for ln in linhas:
            tipo = campo(ln, CAMPO_TIPO)
            if campo(ln, CAMPO_ENTRADA):
                self.assertNotEqual(
                    tipo,
                    DESPESA,
                    f"valor na entrada com tipo {tipo!r}: {ln}",
                )
            if campo(ln, CAMPO_SAIDA):
                self.assertNotEqual(
                    tipo,
                    RECEITA,
                    f"valor na saida com tipo {tipo!r}: {ln}",
                )

    def test_o_adiantamento_explicito_e_preservado(self):
        """`3` é uma escolha do produtor e significa outra coisa.

        Um adiantamento de recursos não é receita nem despesa: é entrega de
        produto contra recurso adiantado. Derivar tudo de `l.tipo` apagaria
        essa distinção — e o tipo 3 nunca sairia do ficheiro.
        """
        self._lancamento(
            tipo="RECEITA",
            descricao="Adiantamento de recursos",
            data="2026-05-10",
            valor=Decimal("500.00"),
            tipo_lancamento_lcdpr=ADIANTAMENTO,
        )

        linhas = self._q100()
        self.assertEqual(len(linhas), 1)
        self.assertEqual(
            campo(linhas[0], CAMPO_TIPO),
            ADIANTAMENTO,
            "o produtor escolheu 3 (adiantamento) e o ficheiro nao pode "
            "reclassificar isso como receita",
        )

    # ------------------------------------------------------------------
    # Bug 2 — o separador dentro do texto
    # ------------------------------------------------------------------

    def _estrutura(self):
        """{registo: numero de campos} do ficheiro actual.

        O interior de uma linha LCDPR e' cheio de `|` — sao os delimitadores.
        Contar `|` nao prova nada. O que prova e' se o `|` que veio do
        *texto* acrescenta um campo, e por isso o teste compara esta contagem
        com a de um ficheiro gerado sem separadores no texto.
        """
        contagem = {}
        for linha in self._ficheiro().splitlines():
            if linha.strip():
                partes = linha.split("|")
                contagem[partes[1]] = len(partes) - 2
        return contagem

    def test_um_separador_no_texto_nao_desloca_a_linha(self):
        """`|`, CR e LF dentro de um campo de texto nao podem sobreviver.

        Os registos sao delimitados por `|`. Um `|` num campo de texto livre
        — que e' exactamente o que o produtor escreve ("sementes | herbicida")
        — empurra todos os campos seguintes uma posicao. A Receita le o campo
        errado, e nao ha aviso.

        O que se compara e' a contagem de campos por registo, com e sem
        separadores no texto. Nao se conta `|` no interior da linha: eles sao
        os delimitadores, e um teste que os contasse estaria a acusar o
        ficheiro bem formado de estar mal.
        """
        self._lancamento(
            tipo="DESPESA",
            categoria="Custo",
            descricao="Semente",
            numero_documento="NF123",
            data="2026-02-10",
            valor=Decimal("10.00"),
        )
        texto_limpo = self._estrutura()

        # O mesmo produtor, com separadores em tres campos de texto.
        self.prop.endereco = "Rua A | Lote 3"
        self.prop.nome = "Fazenda | Boa Vista"
        self.prop.save()
        self._lancamento(
            tipo="DESPESA",
            categoria="Custo",
            descricao="Sementes | Herbicida",
            numero_documento="NF|123",
            data="2026-02-11",
            valor=Decimal("10.00"),
        )
        com_separador = self._estrutura()

        self.assertEqual(
            com_separador,
            texto_limpo,
            "um `|` no texto mudou o numero de campos de algum registo: "
            f"com separador {com_separador} contra limpo {texto_limpo}",
        )

        # E o texto continua legivel — saneado, nao apagado.
        hist = [x for x in self._q100() if "Sementes" in x]
        self.assertEqual(len(hist), 1)
        self.assertIn("Sementes Herbicida", hist[0])

    def test_o_numero_de_documento_com_separador_nao_alinha_a_linha(self):
        """O caso que desalinha tudo: `NF|123` no meio de um campo curto.

        A contagem **nao e' um numero magico**, e e' por isso que este teste
        nao diz "12 campos". Este ficheiro ja perdeu e ganhou campos desde que
        o teste foi escrito: `SLD_FIN` e `NAT_SLD_FIN` foram separados por outra
        pessoa e o Q100 passou de 12 para 13. Um `assertEqual(n, 14)` teria
        falhado por uma mudanca *correcta*, e a reaccao natural seria afrouxar
        o numero ate passar — que e' como um teste de conformidade se converte
        em decoracao.

        O invariante e' "**o mesmo numero de campos, com e sem o separador**".
        """
        self._lancamento(
            tipo="DESPESA",
            categoria="Custo",
            descricao="Compra",
            numero_documento="NF123",
            data="2026-02-10",
            valor=Decimal("10.00"),
        )
        sem_sep = self._q100()[-1]

        self._lancamento(
            tipo="DESPESA",
            categoria="Custo",
            descricao="Compra",
            numero_documento="NF|123",
            data="2026-02-11",
            valor=Decimal("50.00"),
        )
        com_sep = self._q100()[-1]

        self.assertNotEqual(com_sep, sem_sep, "o teste nao esta a exercitar nada")
        self.assertEqual(
            len(com_sep.split("|")),
            len(sem_sep.split("|")),
            f"o `|` no numero do documento mudou o numero de campos: "
            f"{com_sep!r} contra {sem_sep!r}",
        )

        # O separador virou espaco e cada campo continua no seu sitio.
        self.assertIn("NF 123", com_sep)
        self.assertEqual(campo(com_sep, CAMPO_TIPO_DOC), "6")
        self.assertEqual(campo(com_sep, CAMPO_HIST), "Compra")
        self.assertEqual(campo(com_sep, CAMPO_SAIDA), "50.00")

    def test_o_texto_limpo_mantem_o_que_diz(self):
        """Sanear não pode apagar o histórico.

        Um histórico cortado por uma limpeza é um histórico errado. O
        produtor precisa de ler no ficheiro o que escreveu.
        """
        self._lancamento(
            tipo="DESPESA",
            categoria="Custo",
            descricao="Compra de 150 kg de ureia",
            valor=Decimal("100.00"),
        )

        linhas = self._q100()
        self.assertEqual(len(linhas), 1)
        self.assertEqual(campo(linhas[0], CAMPO_HIST), "Compra de 150 kg de ureia")

    def test_uma_quebra_de_linha_no_texto_nao_cria_uma_linha_fantasma(self):
        """CR/LF no texto parte a linha em duas no ficheiro entregue."""
        self._lancamento(
            tipo="DESPESA",
            categoria="Custo",
            descricao="Compra\r\ncontinuacao",
            valor=Decimal("100.00"),
        )

        for linha in self._ficheiro().splitlines():
            if linha.strip() and not linha.startswith("|"):
                self.fail(
                    f"linha sem separador inicial — o texto furou o registo: {linha!r}"
                )

        self.assertEqual(len(self._q100()), 1, "o registo partiu-se em dois")
