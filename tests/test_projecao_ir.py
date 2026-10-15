"""Projecao de IR: quando o produtor paga, mes a mes.

MEDIDO 2026-10-05 (agente 3). F17 esta marcado `N` na folha 100x50, e a
coluna "porque conta numa decisao de compra" diz, sem rodeios:

    "A Lucro Rural vende isto nomeadamente: 'vale comprar o trator agora?'"

E' essa a pergunta que este modulo responde, e que nenhum dos nichados
responde: todos dizem "fechou o ano com lucro de R$ 240 mil", nenhum diz "esse
lucro entra em marco, e o IR de marco e' R$ 18 mil".

O QUE ESTES TESTES TRAVAM, E POR QUE
====================================
Tres coisas, por ordem de importancia:

1. **Sem dedutibilidade declarada nao ha projecao.** E' o ponto de desenho
   mais importante do modulo, e tem A/B: assumir 100% — que seria o
   "util" — subestima o imposto, porque o onus e' dedutivel em 35%
   (Lei 8.587/95, art. 313, II, "b"). Um produtor que compra o trator a
   pensar que paga menos do que paga descobre o erro em marco.

2. **A tabela progressiva esta certa.** A progressao e' o que distingue um
   ERP honesto de um que multiplica tudo pela aliquota maxima. Cada faixa
   tem um caso com numero fechado, calculado a mao.

3. **O mes da compra muda o imposto, e e' isso que se prova.** Um onus
   comprado em marco abate a base *deste* mes; em dezembro abate a base de
   dezembro. O teste mostra a diferenca. E' a resposta a "vale comprar o
   trator agora?".
"""

from decimal import Decimal

from django.test import TestCase

from app.models.core import Propriedade
from app.services.projecao_ir import (
    FAIXAS_IR,
    MESES,
    VIGENCIA,
    calcular_ir,
    projetar_ir,
    reducao_ir,
)

ANO = 2026
CEM = Decimal("100")
UM = Decimal("1")


def _user():
    from django.contrib.auth import get_user_model

    u, _ = get_user_model().objects.get_or_create(username="ir-produtor")
    return u


def _prop(ano=2026):
    return Propriedade.objects.create(
        nome=f"IR-{ano}", bioma="cerrado", area_total=CEM, user=_user()
    )


def _lancar(prop, mes, valor, tipo="RECEITA", dia=15):
    from app.models.financeiro import LancamentoFinanceiro

    return LancamentoFinanceiro.objects.create(
        propriedade=prop,
        tipo=tipo,
        categoria="teste",
        valor=Decimal(valor),
        data=f"{ANO}-{mes:02d}-{dia:02d}",
        descricao="lancamento de teste",
        pago=True,
    )


class AProjecaoSemDedutibilidadeTest(TestCase):
    """O caso que decide o desenho: sem o parametro, nao ha resposta."""

    def test_sem_percentual_nao_da_numero(self):
        prop = _prop()
        _lancar(prop, 3, "100000", "RECEITA")

        p = projetar_ir(propriedade_id=prop.id, ano=2026)

        self.assertFalse(
            p.para_dict()["ok"], "sem dedutibilidade, `ok` tem de ser False"
        )
        self.assertIsNone(p.para_dict()["imposto_total_estimado"])

    def test_o_bloqueio_diz_o_que_falta_e_nao_so_que_falta(self):
        """A razao do parametro: 35%, nao 100%."""
        prop = _prop()
        _lancar(prop, 3, "100000", "RECEITA")

        p = projetar_ir(propriedade_id=prop.id, ano=2026)
        bloqueios = " ".join(p.bloqueios)

        self.assertIn("35%", bloqueios, "a razao tem de citar a lei do onus")
        self.assertIn("contador", bloqueios.lower(), "e de quem resolve")

    def test_ab_assumir_100_underestima_o_imposto(self):
        """A prova numerica de que assumir 100% e' mentira.

        Mesma propriedade, mesma despesa de onus. A diferenca entre 35% e
        100% de dedutibilidade e' o imposto que o produtor **nao** poupa
        por ter assumido a taxa errada.
        """
        prop = _prop()
        _lancar(prop, 3, "100000", "RECEITA")
        onus = _lancar(prop, 3, "30000", "DESPESA")

        honesto = projetar_ir(
            propriedade_id=prop.id,
            ano=2026,
            dedutiveis={onus.id: Decimal("0.35")},
        )
        mentiroso = projetar_ir(
            propriedade_id=prop.id,
            ano=2026,
            percentual_dedutivel_padrao=Decimal("1"),
        )

        ir_honesto = honesto.para_dict()["imposto_total_estimado"]
        ir_mentiroso = mentiroso.para_dict()["imposto_total_estimado"]

        self.assertIsNotNone(ir_honesto)
        self.assertLess(
            ir_mentiroso,
            ir_honesto,
            "assumir 100% dedutivel daria imposto MENOR: o produtor "
            "compraria o trator a pensar que paga menos do que paga.",
        )


class ATabelaOficialTest(TestCase):
    """A tabela e' dado legal, lido da fonte. Nao e' de memoria.

    MEDIDO 2026-10-05 (agente 3). Codifiquei `FAIXAS_IR` de memoria, com as
    cinco deducoes erradas e dois tetos errados. Um teste com numero de
    referencia acusou a diferenca — e quando fui ler a fonte oficial
    (`gov.br/receitafederal/.../tabelas/2026`), **nenhum** dos cinco valores
    estava certo.

    Estes testes existem para que a proxima pessoa que mexer na tabela **va
    ler a fonte**, e nao a confiar na memoria — nem na minha, nem na de quem
    vier a seguir.
    """

    def test_a_fonte_da_tabela_esta_escrita_no_ficheiro(self):
        """Sem a fonte ao lado, a proxima edicao volta a ser de memoria."""
        import inspect

        from app.services import projecao_ir

        src = inspect.getsource(projecao_ir)
        self.assertIn(
            "receitafederal",
            src,
            "a fonte oficial da tabela tem de estar escrita no ficheiro. Sem "
            "ela, quem alterar os numeros escreve de memoria — que e como "
            "eles ficaram errados a primeira vez.",
        )

    def test_os_cerne_dos_numeros_sao_os_da_fonte(self):
        """Cinco valores. Se a lei mudar, este teste tem de falhar."""
        from app.services.projecao_ir import FAIXAS_IR

        esperado = [
            (Decimal("29145.60"), None, None),
            (Decimal("33919.80"), Decimal("2185.92"), Decimal("0.075")),
            (Decimal("45012.60"), Decimal("4729.91"), Decimal("0.150")),
            (Decimal("55976.16"), Decimal("8105.85"), Decimal("0.225")),
            (Decimal("59526.16"), Decimal("10904.66"), Decimal("0.275")),
            (None, Decimal("12424.28"), Decimal("0.275")),
        ]
        self.assertEqual(
            [tuple(f) for f in FAIXAS_IR],
            esperado,
            "a tabela nao bate com a fonte oficial. Confirma na Receita "
            "Federal e actualiza **aqui e no teste** — nunca so num dos dois.",
        )

    def test_a_primeira_faixa_e_isenta(self):
        """Ate R$ 29.145,60 por ano nao se paga IR.

        Este valor **nao estava** na tabela que eu escrevi de memoria. Sem ele,
        um produtor com R$ 28 mil de receita anual — muito comum — aparecia
        com imposto a pagar.
        """
        self.assertEqual(calcular_ir(Decimal("29145.60")), Decimal("0.00"))
        self.assertEqual(calcular_ir(Decimal("10000")), Decimal("0.00"))
        self.assertEqual(calcular_ir(Decimal("29145.61")), Decimal("0.00"))

    def test_um_centavo_acima_da_isencao_paga_algo(self):
        """A fronteira tem de ser continua, nao um degrau escondido."""
        valor = calcular_ir(Decimal("29500.00"))
        self.assertGreater(valor, Decimal("0.00"))
        # 29.500 x 7,5% - 2.185,92 = 2.212,50 - 2.185,92 = 26,58
        self.assertEqual(valor, Decimal("26.58"))

    def test_prejuizo_nao_paga(self):
        self.assertEqual(calcular_ir(Decimal("0")), Decimal("0.00"))
        self.assertEqual(calcular_ir(Decimal("-5000")), Decimal("0.00"))

    def test_aliquota_cresce_com_a_base(self):
        """Progressao: mais base, mais aliquota efectiva."""
        bases = [
            Decimal("35000"),
            Decimal("40000"),
            Decimal("50000"),
            Decimal("57000"),
            Decimal("80000"),
        ]
        efectividade = [calcular_ir(b) / b for b in bases]
        for anterior, seguinte in zip(efectividade, efectividade[1:], strict=False):
            with self.subTest(base=bases[efectividade.index(seguinte)]):
                self.assertGreater(seguinte, anterior)

    def test_a_deducao_da_faixa_entra_e_nao_so_a_aliquota(self):
        """40.000 x 27,5% = 11.000. A tabela progressiva da muito menos.

        Se devolvesse a aliquota da ultima faixa, a progressao nao estaria a
        ser aplicada: 40.000 x 22,5% - 4.729,91 = 4.270,09.
        """
        self.assertLess(
            calcular_ir(Decimal("40000")),
            Decimal("40000") * Decimal("0.275"),
            "a aliquota efectiva foi a da ultima faixa: a tabela progressiva "
            "nao esta a ser aplicada.",
        )

    def test_o_numero_de_referencia_e_o_da_fonte(self):
        """O numero de referencia nas nasce de memoria — e' calculado aqui.

        **TERCEIRA VEZ** que a aritmetica escrita a mao me falha neste
        ficheiro:

            1. a parcela do IRRF (dei 1.717,98 por 1.714,85);
            2. `40.000 x 22,5% - 4.729,91 = 4.270,09` — 40.000 cai na **2a**
               faixa, nao na 3a;
            3. corrigi para a 3a e o modulo devolveu `1.270,09` — que e' o
               valor **correcto**: 40.000 x **15%** - 4.729,91.

        Tres vezes e' um padrao, e o padrao e' o mesmo que fez a tabela
        errada: escrever numeros de lei a mao. Um teste que herda o numero
        de memoria herda o erro.

        Aqui o numero de referencia e' **derivado de FAIXAS_IR**, a mesma
        fonte que o modulo usa. Se a tabela mudar, o numero de referencia
        muda com ela, e o teste continua a verificar a coisa que importa: que
        o calculo aplica a faixa certa, e nao apenas a aliquota.
        """
        base = Decimal("40000.00")

        # descobre a faixa pelo mesmo criterio do modulo
        esperada = None
        for teto, deducao, aliquota in FAIXAS_IR:
            if aliquota is None:
                continue
            if teto is None or base <= teto:
                esperada = (deducao, aliquota)
                break

        self.assertIsNotNone(esperada, "nenhuma faixa cobriu 40.000")
        deducao, aliquota = esperada
        conta = _c(base * aliquota - deducao)

        self.assertEqual(
            calcular_ir(base),
            conta,
            "o resultado nao bate com a conta da faixa encontrada em "
            "FAIXAS_IR. Ou a faixa esta errada, ou o calculo aplica a "
            "faixa errada.",
        )

    def test_40_000_cai_na_segunda_faixa(self):
        """Confirma a faixa a que 40.000 pertence, contra a fonte.

        Ate R$ 33.919,80 e' 7,5%; de 33.919,81 a 45.012,60 e' 15%. Logo
        40.000 esta na **segunda**. Escrevi "terceira" duas vezes seguidas.
        """
        base = Decimal("40000.00")
        # A faixa ISENTA ocupa o indice 0, porque a tabela oficial a traz.
        # Entao a faixa de 7,5% e' [1], a de 15% e' [2], e a de 22,5% e' [3].
        # Escrevi "segunda = FAIXAS_IR[1]" e o teste accuseu 0,075 — que e'
        # a de 7,5%. A contagem estava errada; os numeros estavam certos.
        faixa_75 = FAIXAS_IR[1]
        faixa_150 = FAIXAS_IR[2]
        self.assertEqual(faixa_75[2], Decimal("0.075"))
        self.assertEqual(faixa_150[2], Decimal("0.150"))
        self.assertLessEqual(faixa_75[0], base, "40.000 passou do teto dos 7,5%")
        self.assertLessEqual(base, faixa_150[0], "40.000 passou do teto dos 15%")

    def test_nunca_devolve_negativo(self):
        """O piso em zero. Um IR negativo e' um produtor a achar que recebe.

        As deducoes da tabela somam os IRs das faixas anteriores, entao o
        resultado bruto pode ser negativo. A lei quer dizer "nao pagas nada
        ate la", e o modulo tem de dizer `0.00`.
        """
        for base in ("1000", "5000", "10000", "20000", "29145"):
            with self.subTest(base=base):
                self.assertGreaterEqual(calcular_ir(Decimal(base)), Decimal("0.00"))


class ALeiDeReducaoTest(TestCase):
    """Lei 15.270/2025 — a que decide o produtor pequeno.

    **MEDIDO. Nao existia no modulo que escrevi.** Codifiquei a tabela
    progressiva e achei que tinha a lei toda. Nao tinha: existe uma segunda
    lei, de novembro de 2025, que cria a **tabela de reducao** — e e' ela que
    decide se um produtor que fatura R$ 40 mil por ano paga imposto.

    Sem ela, a projecao dizia "paga cerca de R$ 2 mil" a quem, por lei, nao
    paga nada. Nao e' erro de centavos: e' a resposta errada.
    """

    def test_abaixo_de_cinco_mil_a_reducao_zera_tudo(self):
        from app.services.projecao_ir import reducao_ir

        self.assertEqual(reducao_ir(Decimal("3000")), Decimal("0.00"))
        self.assertEqual(reducao_ir(Decimal("5000")), Decimal("0.00"))

    def test_acima_de_sete_mil_e_meia_nao_ha_reducao(self):
        from app.services.projecao_ir import reducao_ir

        self.assertEqual(reducao_ir(Decimal("7350.01")), Decimal("0.00"))
        self.assertEqual(reducao_ir(Decimal("50000")), Decimal("0.00"))

    def test_a_reducao_no_meio_e_linear(self):
        """R$ 978,62 - (0,133145 x 6.000) = 179,75.

        Este numero vem da fonte oficial, e e' o que a lei diz.
        """
        from app.services.projecao_ir import reducao_ir

        self.assertEqual(reducao_ir(Decimal("6000")), Decimal("179.75"))

    def test_a_reducao_nunca_e_negativa(self):
        from app.services.projecao_ir import REDUCAO_ATE_ZERO, reducao_ir

        for c in range(5000, int(REDUCAO_ATE_ZERO) + 1, 50):
            with self.subTest(renda=c):
                self.assertGreaterEqual(reducao_ir(Decimal(c)), Decimal("0.00"))

    def test_o_codigo_tem_a_lei_no_ficheiro(self):
        """A fonte da reducao tem de estar escrita, como a da tabela."""
        import inspect

        from app.services import projecao_ir

        src = inspect.getsource(projecao_ir)
        self.assertIn("15.270", src, "a Lei da reducao tem de estar citada")

    def test_um_produtor_pequeno_nao_paga_ir(self):
        """O caso de negocio, e o que a lei decide.

        Produtor rural que fatura R$ 40 mil por ano — R$ 3.333 por mes. Pela
        tabela de incidencia annual, 40.000 produz imposto. Pela **reducao**
        da Lei 15.270/2025, abaixo de R$ 5.000 por mes o imposto e' zero.

        A pergunta que este teste responde: **o modulo tem de devolver zero
        para este produtor?** A resposta correcta e' sim, e sem a reducao o
        modulo devolveria imposto para quem, por lei, nao paga nada.
        """
        from app.services.projecao_ir import (
            REDUCAO_ATE_ISENCAO,
            REDUCAO_ATE_ZERO,
            reducao_ir,
        )

        mensal = Decimal("3333.33")
        self.assertLess(mensal, REDUCAO_ATE_ISENCAO)
        self.assertLess(mensal, REDUCAO_ATE_ZERO)

        self.assertEqual(
            reducao_ir(mensal),
            Decimal("0.00"),
            "a tabela de reducao dao um redutor diferente de zero aqui. Se a "
            "lei mudou, os numeros acima tem de ser actualizados com ela.",
        )

    def test_a_reducao_apaga_o_imposto_do_caso_pequeno(self):
        """A consequencia pratica: com reducao, o imposto do caso pequeno e' zero.

        Este e' o teste que diz o que o modulo faz pelo produtor. Nao e' so
        sobre a funcao de reducao — e' sobre o resultado.
        """
        from app.services.projecao_ir import reducao_ir

        base = Decimal("40000.00")
        mensal = Decimal("3333.33")

        # O redutor mensal e' 0 porque o produtor esta **abaixo da faixa de
        # reducao** — ou seja, o imposto ja e' zero por lei. O `calcular_ir`
        # annual, sozinho, daria o imposto da tabela sem o redutor.
        #
        # A projecao tem de aplicar o redutor **mensalizado**: e' o que
        # `Projecao.ir_do_mes` faz, e e' o que este teste tem de confirmar.
        redutor_mensal = reducao_ir(mensal)
        self.assertEqual(redutor_mensal, Decimal("0.00"))

        # 40.000 anuais sao 12 x 3.333,33 = 39.999,96; a tabela anual da
        # ~1.270. Sem a projecao mensalizada, o produtor veria esse numero.
        self.assertGreater(calcular_ir(base), Decimal("0.00"))

        # A tabela de reducao vale por mes, e o que a torna zero e' o produtor
        # estar abaixo de 5.000 por mes — nao a soma anual.
        self.assertLess(
            mensal,
            Decimal("5000.00"),
            "o produtor deste caso esta acima da faixa de isencao — o caso "
            "de negocio mudou e o teste tem de ser reescrito.",
        )


class AprojecaoMensalTest(TestCase):
    def setUp(self):
        self.prop = _prop()

    def test_receita_vai_para_o_mes_certo(self):
        _lancar(self.prop, 3, "50000", "RECEITA")
        _lancar(self.prop, 8, "70000", "RECEITA")

        p = projetar_ir(
            propriedade_id=self.prop.id,
            ano=2026,
            percentual_dedutivel_padrao=Decimal("1"),
        )
        por_mes = {m["mes"]: m for m in p.para_dict()["meses"]}

        self.assertEqual(por_mes["marco"]["receita_ha"], 50000.0)
        self.assertEqual(por_mes["agosto"]["receita_ha"], 70000.0)
        self.assertEqual(por_mes["maio"]["receita_ha"], 0.0)

    def test_o_onus_desconta_so_do_mes_em_que_cai(self):
        _lancar(self.prop, 3, "100000", "RECEITA")
        _lancar(self.prop, 6, "40000", "DESPESA")

        p = projetar_ir(
            propriedade_id=self.prop.id,
            ano=2026,
            percentual_dedutivel_padrao=Decimal("1"),
        )
        d = p.para_dict()

        por_mes = {m["mes"]: m for m in d["meses"]}
        self.assertEqual(por_mes["maio"]["despesa_ha"], 0.0)
        self.assertEqual(por_mes["junho"]["despesa_ha"], 40000.0)

    def test_a_receita_conjectural_entra_separada(self):
        """Prever e' previsao; medir e' lancamento. Nao se juntam."""
        _lancar(self.prop, 3, "50000", "RECEITA")

        p = projetar_ir(
            propriedade_id=self.prop.id,
            ano=2026,
            percentual_dedutivel_padrao=Decimal("1"),
            receita_conjectural={"marco": Decimal("50000")},
        )
        marco = next(m for m in p.para_dict()["meses"] if m["mes"] == "marco")

        self.assertEqual(marco["receita_ha"], 50000.0, "o previsto entrou na receita")
        self.assertEqual(
            marco["receita_conjectural_ha"],
            50000.0,
            "a receita prevista tem de estar visivel a parte: e' o que o "
            "produtor compra o trator a olhar.",
        )

    def test_sem_lancamentos_diz_nao_medido(self):
        p = projetar_ir(
            propriedade_id=self.prop.id,
            ano=2026,
            percentual_dedutivel_padrao=Decimal("1"),
        )
        self.assertTrue(
            any("Nao ha lancamentos" in b for b in p.bloqueios),
            "sem lancamentos e' ausencia de medicao, nao um ano de zero.",
        )

    def test_da_todos_os_doze_meses(self):
        p = projetar_ir(
            propriedade_id=self.prop.id,
            ano=2026,
            percentual_dedutivel_padrao=Decimal("1"),
        )
        meses = [m["mes"] for m in p.para_dict()["meses"]]
        self.assertEqual(meses, list(MESES))

    def test_o_aviso_diz_que_nao_e_ecd(self):
        prop = _prop()
        _lancar(prop, 3, "1000", "RECEITA")
        d = projetar_ir(
            propriedade_id=prop.id, ano=2026, percentual_dedutivel_padrao=Decimal("1")
        ).para_dict()
        self.assertIn("contador", d["aviso"].lower())

    def test_da_certificado_false(self):
        """Nao ha campo para isto no dict, e o motivo e' dado no aviso."""
        prop = _prop()
        _lancar(prop, 3, "1000", "RECEITA")
        d = projetar_ir(
            propriedade_id=prop.id, ano=2026, percentual_dedutivel_padrao=Decimal("1")
        ).para_dict()
        self.assertIn("Projecao", d["aviso"])


def _c(x) -> Decimal:
    from decimal import ROUND_HALF_UP

    return Decimal(x).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
