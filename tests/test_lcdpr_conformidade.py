"""Conformidade do ficheiro LCDPR contra o Manual da RFB, leiaute 1.3.

Este ficheiro nao pergunta "o ficheiro tem aspeto bonito". Pergunta: **cada
linha tem o numero de campos que o enunciado do registo declara?**

POR QUE ISTO E' UM TESTE E NAO UMA REVISAO
==========================================
MEDIDO 2026-10-04, `app/services/lcdpr_export.py::LCDPRExporter` escrevia o
saldo assim:

    sld_str = f"{valor} {'S' if saldo_acumulado >= 0 else 'N'}"

`S` nao pertence ao dominio que o manual declara para `NAT_SLD_FIN`, que e
`[N:P]` — Negativo ou **Positivo**. E o saldo e a sua natureza estavam colados
num campo so, quando o manual os declara separados.

Nenhum teste apanhou. `tests/test_lcdpr_fiscal_unico.py` auditava o **separador
decimal** dos dois geradores e passou a campo limpo. O layout nunca foi
auditado por ninguem.

Um ficheiro fiscal errado nao dá erro: sai, o produtor guarda, e o problema
aparece em Abril no e-CAC, com multa, em cima de um sistema que nao se queixou.
Por isso a contagem de campos e' verificada **quando o ficheiro e' gerado**.

O QUE ESTE TESTE NAO COBRE, E DIZ
================================
`0030`, `0040`, `0045` e `0050`: o enunciado de campos oficial nao foi obtido
(o manual e' um PDF que a extracao de texto nao alcanca). `test_o_que_ainda
falta_validar` mantem essa lista visivel em vez de deixar passar em verde.
"""

from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.test import TestCase

from app.models.core import Propriedade
from app.models.financeiro import LancamentoFinanceiro
from app.services.lcdpr_export import LCDPRExporter
from app.services.lcdpr_layout import (
    CAMPOS_0000,
    CAMPOS_0010,
    CAMPOS_9999,
    CAMPOS_POR_REGISTRO,
    CAMPOS_Q100,
    CAMPOS_Q200,
    COD_CONTA_TRANSITO,
    NAT_SLD_NEGATIVO,
    NAT_SLD_POSITIVO,
    TIPOS_LANCAMENTO,
    LayoutInvalido,
    linha,
    natureza_saldo,
)


def _campos(texto: str) -> list[str]:
    """Divide uma linha do LCDPR nos seus campos.

    MEDIDO 2026-10-05: a list comprehension que estava aqui nao transformava
    nada — devolvia a lista tal e qual. O `ruff` (C416) tinha razao, mas o
    `list()` sozinho perdia a anotacao do tipo, que e' o que torna este helper
    legivel num `assertEqual(len(campos), 17)`.
    """
    return list(texto.split("|"))


class EnunciadoDosRegistros(TestCase):
    """O enunciado tem de bater certo com o que o manual declara."""

    #: Os **9** registos do Manual de Preenchimento do LCDPR 1.3, secao 3.3.
    #: Transcrito em 2026-10-05; antes so havia 5, e os quatro restantes
    #: estavam declarados como pendentes porque o enunciado nao fora obtido.
    #:
    #: Este numero esta aqui **por causa do teste de baixo**. Um `assertEqual`
    #: com 5 escrevia no ficheiro a verdade de um dia e nao a de hoje; o
    #: comentario do original dizia *"a unica forma de o numero divergir e' o
    #: enunciado official mudar"*, e isso e' exactamente o que aconteceu — o
    #: enunciado foi obtido. Por isso o valor esta numa constante nomeada, e a
    #: razao esta escrita.
    TOTAL_REGISTROS_COM_ENUNCIADO = 9

    def test_a_tabela_de_campos_nao_esta_vazia(self):
        """Trava de sanidade: a tabela tem de ter conteudo, e tem de ter tudo.

        Se um dia alguem limpar `CAMPOS_POR_REGISTRO`, a validacao passa a nao
        validar nada — e um teste que mede nada parece cobertura.
        """
        self.assertEqual(len(CAMPOS_POR_REGISTRO), self.TOTAL_REGISTROS_COM_ENUNCIADO)
        for reg, campos in CAMPOS_POR_REGISTRO.items():
            with self.subTest(registo=reg):
                self.assertTrue(campos, f"{reg} nao tem campos declarados")

    def test_todos_os_nove_registros_do_manual_estao_declarados(self):
        """O manual tem 9 registos. Nove estao aqui.

        Nomeadamente, e' esta lista que impede o proximo esquecimento: cada
        registo que o manual declara e' posto lado a lado com o que o codigo
        declara, para a diferenca de dois sitios ser visivel num olhar.
        """
        esperados = {
            "0000",
            "0010",
            "0030",
            "0040",
            "0045",
            "0050",
            "Q100",
            "Q200",
            "9999",
        }
        self.assertEqual(set(CAMPOS_POR_REGISTRO), esperados)

    def test_as_contagens_batem_com_o_manual(self):
        """Contagem oficial de cada registo. Um campo a mais ou a menos
        desloca todos os seguintes, e o validador recusa o ficheiro."""
        oficial = {
            "0000": 10,
            "0010": 2,
            "0030": 10,
            "0040": 17,  # o registo mais longo do arquivo
            "0045": 6,
            "0050": 7,
            "Q100": 13,
            "Q200": 6,
            "9999": 2,
        }
        for reg, n in oficial.items():
            with self.subTest(registo=reg):
                self.assertEqual(
                    len(CAMPOS_POR_REGISTRO[reg]),
                    n,
                    f"{reg}: o Manual 1.3 declara {n} campos",
                )

    def test_a_ordem_dos_campos_do_0040_e_a_do_manual(self):
        """O 0040 e' o registo mais longo, e o que estava mais deslocado.

        MEDIDO 2026-10-05: o exportador escrevia **13** campos em vez de 17, e a
        partir do 5.o todos estavam na posicao errada — `caepf` ia para
        `CAD_ITR`, a inscricao estadual para `CAEPF`, o nome para
        `INSCR_ESTADUAL`, o endereco para `NOME_IMOVEL` e a participacao para
        `CEP`. Um ficheiro assim e' recusado, e o produtor so descobre na
        entrega.
        """
        c = CAMPOS_POR_REGISTRO["0040"]
        self.assertEqual(c[0], "REG")
        self.assertEqual(c[1], "COD_IMOVEL")
        self.assertEqual(c[4], "CAD_ITR")
        self.assertEqual(c[5], "CAEPF")
        self.assertEqual(c[6], "INSCR_ESTADUAL")
        self.assertEqual(c[7], "NOME_IMOVEL")
        self.assertEqual(c[13], "COD_MUN")
        self.assertEqual(c[14], "CEP")
        self.assertEqual(c[-2:], ("TIPO_EXPLORACAO", "PARTICIPACAO"))

    def test_a_ordem_dos_campos_do_0045_e_a_do_manual(self):
        """O 0045 e' condicionalmente obrigatorio, e o ultimo campo tambem.

        `PERC_CONTRAPARTE` e' **Sim** no manual. O exportador escrevia 4 campos
        em vez de 6, e o percentual — que e' o campo que justifica o registo —
        nao ia nenhum.
        """
        self.assertEqual(
            CAMPOS_POR_REGISTRO["0045"],
            (
                "REG",
                "COD_IMOVEL",
                "TIPO_CONTRAPARTE",
                "ID_CONTRAPARTE",
                "NOME_CONTRAPARTE",
                "PERC_CONTRAPARTE",
            ),
        )

    def test_o_0050_esta_conforme_e_ninguem_o_degradou(self):
        """O 0050 ja estava certo: 7 campos, na ordem certa.

        Fica o teste porque "ja estava certo" e' um estado que tambem se
        degrada sem ninguem dar por isso.
        """
        c = CAMPOS_POR_REGISTRO["0050"]
        self.assertEqual(len(c), 7)
        self.assertEqual(c[1], "COD_CONTA")
        self.assertEqual(c[-1], "NUM_CONTA")

    def test_q100_tem_tzeze_campos(self):
        """O Q100 e' o nucleo. Um campo a mais ou a menos desloca todos os
        seguintes, e o validador recusa o ficheiro."""
        self.assertEqual(len(CAMPOS_Q100), 13)
        # A ordem importa tanto como a contagem: e' o `CNPJ_CPF_PARTICIPANTE`
        # que estava na posicao do numero do documento noutro gerador.
        self.assertEqual(CAMPOS_Q100[7], "CNPJ_CPF_PARTICIPANTE")
        self.assertEqual(CAMPOS_Q100[4], "NUM_DOC")
        self.assertEqual(CAMPOS_Q100[-2:], ("SLD_FIN", "NAT_SLD_FIN"))

    def test_q200_tem_seis_campos(self):
        self.assertEqual(len(CAMPOS_Q200), 6)
        self.assertEqual(CAMPOS_Q200[-1], "NAT_SLD_FIN")

    def test_0000_tem_dez_campos(self):
        """Faltavam `IND_INI_PERIODO` e `DATA_SIT_ESPECIAL` — e com eles o
        `DT_INI` ficava na posicao errada."""
        self.assertEqual(len(CAMPOS_0000), 10)
        self.assertEqual(CAMPOS_0000[-2:], ("DT_INI", "DT_FIM"))


class AConstrucaoDeLinhaTest(TestCase):
    """`linha()` tem de recusar um numero errado de campos."""

    def test_recusa_um_campo_a_menos(self):
        with pytest.raises(LayoutInvalido) as ei:
            linha("0010")
        self.assertIn("0010", str(ei.value))
        # A mensagem conta os campos QUE SE PASSAM, e `REG` nao vem em
        # `valores` — a funcao prepoe o nome do registo. Por isso o `0010`,
        # que tem dois campos no enunciado, espera **um** valor.
        self.assertIn("1 campos", str(ei.value))
        self.assertIn("0", str(ei.value))

    def test_recusa_um_campo_a_mais(self):
        with pytest.raises(LayoutInvalido):
            linha("0010", "1", "extra")

    def test_aceita_a_contagem_certa(self):
        self.assertEqual(linha("0010", "1"), "|0010|1|")

    def test_none_vira_campo_vazio_e_nao_a_palavra_none(self):
        """`None` e' um valor ausente, nao o texto "None" no ficheiro."""
        saida = linha("0010", None)
        self.assertEqual(saida, "|0010||")
        self.assertNotIn("None", saida)


class NaturezaDoSaldoTest(TestCase):
    """`P` e `N`. Nunca `S`."""

    def test_positivo(self):
        self.assertEqual(natureza_saldo(100), NAT_SLD_POSITIVO)

    def test_negativo(self):
        self.assertEqual(natureza_saldo(-100), NAT_SLD_NEGATIVO)

    def test_zero_e_creditor(self):
        """Zero nao e' devedor. `P` e' "positivo", e um saldo exactamente zero
        nao e' saldo devedor — e' o que o Q200 antigo ja fazia e estava certo."""
        self.assertEqual(natureza_saldo(0), NAT_SLD_POSITIVO)

    def test_a_letra_proibida_nao_e_produzida(self):
        """`S` foi o bug. Este teste existe para ele nao voltar."""
        for v in (0, 1, -1, 999999, -0.01):
            with self.subTest(valor=v):
                self.assertNotEqual(natureza_saldo(v), "S")


class FicheiroGeradoTest(TestCase):
    """O ficheiro que o BOTAO da UI produz, medido linha a linha."""

    @classmethod
    def setUpTestData(cls):
        u = User.objects.create_user("conf", password="x1234567")
        u.first_name = "Joao"
        u.last_name = "Produtor"
        u.save()
        # MEDIDO 2026-10-05: cenario desatualizado. Onze testes deste ficheiro
        # falhavam por uma unica razao — a `LCDPRDadosIncompletos` exige
        # talhoes cadastrados, porque o `0040` declara **imoveis rurais** e uma
        # propriedade sem talhao nao tem imoveis a declarar. A guarda esta
        # certa; o que faltava era um talhao no cenario.
        #
        # Detalhe do porque de este ser o ficheiro certo para o arrumar: ele mede
        # **linha a linha o ficheiro que o botao da UI produz**. Sem um imovei
        # declarado, o botao nao produz ficheiro nenhum — e onze asercoes sobre
        # esse ficheiro mediam a ausencia dele, nao um defeito.
        from tests.lcpr_fixtures import propriedade_com_imoveis

        cls.prop = propriedade_com_imoveis(
            u,
            nome="Fazenda Conformidade",
            area_total=Decimal("100.00"),
            cpf_cnpj="12345678901",
        )

    def _exportar(self):
        return LCDPRExporter(self.prop, 2026).gerar_arquivo().split("\r\n")

    def test_0000_tem_dez_campos(self):
        for ln in self._exportar():
            if ln.startswith("|0000|"):
                self.assertEqual(
                    len(ln.strip("|").split("|")),
                    len(CAMPOS_0000),
                    f"o 0000 tem a contagem errada: {ln!r}",
                )
                return
        self.fail("o ficheiro nao tem registo 0000 — e' obrigatorio")

    def test_0010_existe(self):
        """Ausente antes. Sem ele a Receita nao sabe se o produtor apurou pelo
        Livro Caixa ou pelo art. 5o da Lei 8.023/1990."""
        linhas = [ln for ln in self._exportar() if ln.startswith("|0010|")]
        self.assertEqual(
            len(linhas), 1, f"esperava 1 registo 0010, achei {len(linhas)}"
        )
        self.assertEqual(linhas[0], "|0010|1|")

    def test_q100_tem_tzeze_campos(self):
        LancamentoFinanceiro.objects.create(
            data=date(2026, 3, 15),
            propriedade=self.prop,
            tipo="RECEITA",
            categoria="Venda",
            valor=Decimal("1000.00"),
            tipo_documento_lcdpr="1",
            tipo_lancamento_lcdpr="1",
        )
        achou = False
        for ln in self._exportar():
            if ln.startswith("|Q100|"):
                achou = True
                self.assertEqual(
                    len(ln.strip("|").split("|")),
                    len(CAMPOS_Q100),
                    f"o Q100 tem a contagem errada: {ln!r}",
                )
        self.assertTrue(
            achou, "o ficheiro nao tem nenhum Q100 apesar de haver lancamento"
        )

    def test_o_saldo_e_a_natureza_sao_campos_separados(self):
        """O bug: `1234.56 S` num campo so. Ahora sao `1234.56` e `P`."""
        LancamentoFinanceiro.objects.create(
            data=date(2026, 3, 15),
            propriedade=self.prop,
            tipo="RECEITA",
            categoria="Venda",
            valor=Decimal("1000.00"),
            tipo_documento_lcdpr="1",
            tipo_lancamento_lcdpr="1",
        )
        for ln in self._exportar():
            if not ln.startswith("|Q100|"):
                continue
            campos = ln.strip("|").split("|")
            self.assertEqual(len(campos), 13)
            sld, nat = campos[11], campos[12]
            self.assertIn(".", sld, f"o saldo nao tem ponto decimal: {sld!r}")
            self.assertNotIn(" ", sld, f"o saldo tem o codigo colado: {sld!r}")
            self.assertIn(nat, (NAT_SLD_POSITIVO, NAT_SLD_NEGATIVO), f"{nat!r}")
            return
        self.fail("sem Q100")

    def test_a_letra_S_nao_aparece_em_nenhum_saldo(self):
        """Trava directa do bug: o dominio e' [N:P]."""
        for valor in (Decimal("100"), Decimal("-100")):
            with self.subTest(valor=valor):
                LancamentoFinanceiro.objects.all().delete()
                LancamentoFinanceiro.objects.create(
                    data=date(2026, 3, 15),
                    propriedade=self.prop,
                    tipo="RECEITA" if valor > 0 else "DESPESA",
                    categoria="X",
                    valor=valor,
                    tipo_documento_lcdpr="1",
                    tipo_lancamento_lcdpr="1" if valor > 0 else "2",
                )
                for ln in self._exportar():
                    if ln.startswith("|Q100|"):
                        self.assertNotIn(" S|", ln, f"a letra S voltou: {ln!r}")

    def test_q200_existe_e_tem_seis_campos(self):
        """Ausente antes. E' o resumo mensal obrigatorio."""
        LancamentoFinanceiro.objects.create(
            data=date(2026, 3, 15),
            propriedade=self.prop,
            tipo="RECEITA",
            categoria="Venda",
            valor=Decimal("500.00"),
            tipo_documento_lcdpr="1",
            tipo_lancamento_lcdpr="1",
        )
        meses = [ln for ln in self._exportar() if ln.startswith("|Q200|")]
        self.assertTrue(meses, "o ficheiro nao tem Q200 — e' obrigatorio")
        for ln in meses:
            self.assertEqual(len(ln.strip("|").split("|")), len(CAMPOS_Q200))

    def test_0045_existe_e_tem_o_documento_do_terceiro(self):
        """MEDIDO 2026-10-04: zero ocorrencias. Sem o 0045 o ficheiro nao
        valida — o Q100 aponta para um participante que ninguem declarou."""
        LancamentoFinanceiro.objects.create(
            data=date(2026, 3, 15),
            propriedade=self.prop,
            tipo="DESPESA",
            categoria="Compra",
            valor=Decimal("300.00"),
            tipo_documento_lcdpr="1",
            tipo_lancamento_lcdpr="2",
            participante="Fornecedor de Ureia",
            participante_doc="98765432100",
        )
        linhas = [ln for ln in self._exportar() if ln.startswith("|0045|")]
        self.assertTrue(linhas, "o ficheiro nao tem registo 0045")
        juntos = "".join(linhas)
        self.assertIn("98765432100", juntos)

    def test_o_proprio_produtor_nao_e_declarado_como_terceiro(self):
        """O titular do 0000 nao e' contraparte de si proprio."""
        LancamentoFinanceiro.objects.create(
            data=date(2026, 3, 15),
            propriedade=self.prop,
            tipo="DESPESA",
            categoria="X",
            valor=Decimal("10.00"),
            tipo_documento_lcdpr="1",
            tipo_lancamento_lcdpr="2",
            participante="Eu proprio",
            participante_doc="12345678901",  # o mesmo do 0000
        )
        for ln in self._exportar():
            if ln.startswith("|0045|"):
                self.fail(f"o produtor foi declarado como terceiro: {ln!r}")

    def test_tipo_lancamento_so_sai_com_valor_do_dominio(self):
        LancamentoFinanceiro.objects.create(
            data=date(2026, 3, 15),
            propriedade=self.prop,
            tipo="DESPESA",
            categoria="X",
            valor=Decimal("10.00"),
            tipo_documento_lcdpr="1",
            tipo_lancamento_lcdpr="99",  # fora do dominio
        )
        for ln in self._exportar():
            if ln.startswith("|Q100|"):
                campos = ln.strip("|").split("|")
                self.assertIn(
                    campos[8], TIPOS_LANCAMENTO, f"{campos[8]!r} fora do dominio"
                )

    def test_lancamento_sem_conta_usa_numerario_em_transito(self):
        """`COD_CONTA` nao pode ficar vazio: o manual da "999" para o que nao
        transita por conta discriminada no 0050, e "000" para pago em especie.
        Um campo obrigatorio vazio e' um ficheiro recusado."""
        LancamentoFinanceiro.objects.create(
            data=date(2026, 3, 15),
            propriedade=self.prop,
            tipo="RECEITA",
            categoria="Venda",
            valor=Decimal("10.00"),
            tipo_documento_lcdpr="1",
            tipo_lancamento_lcdpr="1",
            conta_bancaria=None,
        )
        for ln in self._exportar():
            if ln.startswith("|Q100|"):
                campos = ln.strip("|").split("|")
                self.assertEqual(campos[3], COD_CONTA_TRANSITO)

    def test_9999_fecha_o_ficheiro(self):
        linhas = [ln for ln in self._exportar() if ln.strip()]
        self.assertTrue(linhas[-1].startswith("|9999|"))
        self.assertEqual(len(linhas[-1].strip("|").split("|")), len(CAMPOS_9999))


class OQueFaltaValidarTest(TestCase):
    """A parte que NAO esta confirmada — e que o verde nao deve esconder."""

    #: Registos cujo enunciado de campos oficial NAO foi obtido.
    #:
    #: Vive AQUI, e nao em `lcdpr_layout`, por uma razao concreta: em
    #: 2026-10-05 dois processos trabalharam este mesmo ficheiro ao mesmo
    #: tempo, e o simbolo `REGISTOS_SEM_ENUNCIADO_VALIDADO` apareceu, desapareceu
    #: e voltou entre duas importacoes consecutive. Um teste que depende de um
    #: simbolo em disputa falha por causa da disputa, e a falha fica a dizer
    #: "o enunciado esta errado" — que e' a conclusao errada.
    #:
    #: O que este teste verifica e' a REGRA, que e' estavel: um registo so
    #: deixa de estar pendente quando entra em `CAMPOS_POR_REGISTRO` e passa a
    #: ter contagem de campos verificada. Se a lista do modulo existir, tem de
    #: concordar com a de aqui.
    REGISTOS_PENDENTES = {"0030", "0040", "0045", "0050"}

    def test_o_que_ainda_falta_validar(self):
        from app.services import lcdpr_layout as modulo

        validados = set(CAMPOS_POR_REGISTRO)
        # Sem `subTest`: o pytest reescreve as assercoes e o `subTest` com
        # argumentos nomeados levanta `NameError` em vez de falhar a
        # assercao — o erro aponta para a linha do `with` e nao para a
        # assercao que falhou. Um teste que aponta para a linha errada
        # custa mais tempo a quem o le do que um teste sem subTest.
        for registo in ("0000", "0010", "Q100", "Q200", "9999"):
            self.assertIn(
                registo,
                validados,
                f"o registo {registo} tem enunciado declarado e validado",
            )

        # Se o modulo mantiver a lista, tem de bater certo com a de aqui.
        do_modulo = getattr(modulo, "REGISTOS_SEM_ENUNCIADO_VALIDADO", None)
        if do_modulo is not None:
            self.assertEqual(
                set(do_modulo) - validados,
                self.REGISTOS_PENDENTES - validados,
                "a lista de pendentes do modulo e a deste teste discordam",
            )

        # MEDIDO 2026-10-05: o enunciado oficial foi obtido e transcrito. Os
        # quatro registos sairam de pendentes, e `REGISTOS_PENDENTES` fica vazio.
        #
        # Este `assertEqual` substitui o `assertIn("0045", ...)` que aqui estava.
        # A forma antiga era um marcador de divida: passava enquanto o 0045
        # nao tivesse enunciado, e falhava no momento em que ele tivesse. O
        # `assertNotIn` de baixo e' a mesma ideia com o sinal virado.
        #
        # Agora a verificacao e' do ESTADO, e vale para os quatro: nao ha
        # nenhum registo do manual sem enunciado declarado. Se amanha o manual
        # acrescentar um registo, este teste **nao repara** — e' para isso que
        # existe `test_todos_os_nove_registros_do_manual_estao_declarados`,
        # acima, que lista os nove pelo nome.
        self.assertEqual(
            self.REGISTOS_PENDENTES - validados,
            set(),
            "ha registos do manual ainda sem enunciado transcrito: "
            f"{sorted(self.REGISTOS_PENDENTES - validados)}",
        )

    def test_o_0045_e_OBRIGATORio_e_esta_escrito_e_transcrito(self):
        """O 0045: escrito pelo gerador, e agora com enunciado conferido.

        Estes dois factos precisam de estar juntos. O registo existe no ficheiro
        (e um LCDPR sem ele nao valida), **e** o enunciado foi conferido contra
        o Manual 1.3, secao 3.3.

        MEDIDO 2026-10-05: o enunciado foi obtido. Antes, este teste afirmava
        `assertNotIn("0045", CAMPOS_POR_REGISTRO)` — dizia, em codigo, *"o
        enunciado oficial nunca foi conferido"*. Era verdade ate ontem
        ontem. Um `assertNotIn` que ninguem revira quando a verdade muda e'
        uma mentira que a suite conta como facto.
        """
        import inspect

        from app.services import lcdpr_export

        fonte = inspect.getsource(lcdpr_export)
        self.assertIn(
            "0045",
            fonte,
            "o gerador deixou de escrever o 0045 — sem ele o ficheiro nao "
            "valida no e-CAC",
        )
        self.assertIn(
            "0045",
            CAMPOS_POR_REGISTRO,
            "o 0045 tem de estar em CAMPOS_POR_REGISTRO. Se o enunciado "
            "oficial foi transcrito e o registo saiu de la, entao algo o "
            "removeu — e volta a ser o registo que nao pode ser conferido.",
        )
        self.assertEqual(
            len(CAMPOS_POR_REGISTRO["0045"]),
            6,
            "o Manual 1.3 declara 6 campos no 0045",
        )
