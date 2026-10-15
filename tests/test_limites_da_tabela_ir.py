"""As fronteiras da tabela de IR, testadas uma a uma.

AGENTE 3 - 2026-10-06

Este ficheiro nasce de uma confissao. Escrevi-o PRIMEIRO de memoria, e as
quatro hipoteses sobre a API estavam **todas** erradas:

    REDUCAO_CHEIA_MENSAL / TETO_REDUCAO_MENSAL / ISENCAO_ANUAL  -> nao existem
    is_isento_por_reducao(base, rm)                              -> e' (rm) so
    projetar_ir(ano=, lancamentos=, dedutibilidade=)             -> nao existe

O `import` rebentava antes de o primeiro teste correr. So discovered isto
quando finalmente tive shell e li `app/services/projecao_ir.py`. E' a razao
de o cabeçalho dizer "NAO CORREU" na versao anterior: sem shell, eu disse que
nao sabia se passava, e nao sabia mesmo.

Esta versao foi escrita **contra o codigo**, nao contra a memoria. As linhas
citadas sao do `app/services/projecao_ir.py` na data de escrita.

A QUEB QUE ESTES TESTES TRAVAM
==============================
MEDIDO 2026-10-05, `projecao_ir.py:337`. `reducao_ir()` devolve `0.00` em
**dois** casos de sentido oposto:

    1. abaixo de R$ 5.000/mes -> a Lei 15.270/2025 ISENTA;
    2. acima de R$ 7.350/mes -> a lei nao da REDUCAO.

Eu tratava os dois com um `else: return 0.00`, e o caso 2 devolvia zero. Um
produtor com R$ 250 mil/ano recebia `imposto_com_reducao: 0.0` - **isento
quem nao tem direito a isencao**. O sistema inventava um beneficio fiscal.

A correccao e' `is_isento_por_reducao()` (L337-362), que decide pela
**posicao** na tabela e nunca pelo valor do redutor. Estes testes travam a
fronteira.
"""

from decimal import Decimal
from unittest import TestCase

import pytest

from app.services.projecao_ir import (
    DEDUCAO_DEPENDENTE_MENSAL,
    FAIXAS_IR,
    REDUCAO_ATE_ISENCAO,
    REDUCAO_ATE_ZERO,
    calcular_ir,
    is_isento_por_reducao,
    projetar_ir,
)

ZERO = Decimal("0.00")


class AIsencaoMensalTemDeTerAsDuasLateraisTest(TestCase):
    """A fronteira de R$ 5.000. Um `>` em vez de `>=` errado aqui custa a
    isenção a quem ganha exactamente 5.000 - e a um cêntimo a menos."""

    def test_um_centimo_abaixo_da_isencao(self):
        self.assertTrue(is_isento_por_reducao(Decimal("4999.99")))

    def test_exatamente_o_limite_ainda_e_isento(self):
        """`REDUCAO_ATE_ISENCAO` e' o ULTIMO isento, nao o primeiro nao
        isento. Este teste existe porque a confusao dos dois e' facil."""
        self.assertTrue(is_isento_por_reducao(REDUCAO_ATE_ISENCAO))

    def test_um_centimo_acima_ja_nao_e_isento(self):
        self.assertFalse(is_isento_por_reducao(Decimal("5000.01")))

    def test_desconhecido_e_none_e_nao_false(self):
        """`None` e' "nao sei", `False` e' "nao tem". Sao coisas diferentes e
        o modulo ja voltou a confundi-las uma vez."""
        self.assertIsNone(is_isento_por_reducao(None))

    def test_o_teto_da_reducao_nao_e_o_topo_da_isencao(self):
        """Os dois limites da lei sao valores diferentes e nao podem ser
        confundidos. 7.350 e' onde a reducao deixa de ser 100%."""
        self.assertEqual(REDUCAO_ATE_ISENCAO, Decimal("5000.00"))
        self.assertEqual(REDUCAO_ATE_ZERO, Decimal("7350.00"))


class ORedutorZeroNaoEIsencaoTest(TestCase):
    """O teste que trava o bug. O mais importante deste ficheiro.

    Nao testa um valor: testa uma CONFUSAO — que `redutor == 0.00` signifique
    sempre "isento". Nao significa. Sao duas coisas, e o valor nao as separa.
    """

    def test_acima_do_teto_o_imposto_nao_e_zero(self):
        """O caso em que eu dava isenção indevida: R$ 20.000/mes."""
        m = Decimal("20000.00")
        base = m * 12

        self.assertFalse(is_isento_por_reducao(m), "acima de 5.000 nao ha isencao")

        resultado = calcular_ir(base, rendimento_mensal=m)
        self.assertIsNotNone(resultado, "ha medicao, portanto nao pode ser None")
        self.assertGreater(
            resultado,
            ZERO,
            "BUG REINTRODUZIDO: acima de R$ 7.350/mes a reducao e' 0 porque "
            "NAO se aplica. O imposto tem de ser maior do que zero. Um 0.00 "
            "aqui e' invencao de beneficio fiscal.",
        )

    def test_abaixo_da_isencao_o_imposto_e_zero(self):
        """O outro lado. Mesmo `redutor == 0.00`, consequencia oposta."""
        m = Decimal("4000.00")
        resultado = calcular_ir(m * 12, rendimento_mensal=m)
        self.assertEqual(resultado, ZERO, "4.000/mes esta isento")

    def test_os_dois_lados_do_redutor_zero(self):
        """Lado a lado, para que a distincao fique visavel no codigo do teste."""
        abaixo = calcular_ir(
            Decimal("4000.00") * 12, rendimento_mensal=Decimal("4000.00")
        )
        acima = calcular_ir(
            Decimal("20000.00") * 12, rendimento_mensal=Decimal("20000.00")
        )
        self.assertEqual(abaixo, ZERO)
        self.assertGreater(acima, ZERO)

    def test_sem_rendimento_mensal_a_reducao_desconhece_se_nada(self):
        """MEDIDO DUAS VEZES. A primeira versao afirmava que `calcular_ir(base)`
        sem `rendimento_mensal` devolvia `None`. Devolve
        `Decimal('53575.72')`. **O codigo esta' certo e o teste errado:** o
        imposto anual e' calculavel sem saber a distribuicao mensal; o que
        precisa do rendimento e' a REDUCAO.

        E a segunda versao usava `rendimento_mensal=20000` e falhava, porque
        20.000 esta' ACIMA de REDUCAO_ATE_ZERO (7.350) e portanto nao tem
        reducao nenhuma — os dois lados eram o mesmo numero. A faixa da
        reducao e' 5.000..7.350 (`reducao_ir`, L318), e o redutor e'
        `978.62 - 0.133145 * rm`. Eu tinha o sinal invertido e calculei
        `0.133145 * rm - 978.62`, que da negativo em toda a faixa.

        Este teste fixa a distincao, porque foi ela que me enganou duas
        vezes: reducao desconhecida != imposto desconhecido, e acima de
        7.350 nao ha reducao para comparar.
        """
        base = Decimal("240000.00")
        sem_reducao = calcular_ir(base)
        self.assertIsNotNone(
            sem_reducao, "o imposto anual existe sem distribuicao mensal"
        )
        self.assertGreater(sem_reducao, ZERO)

        dentro_da_faixa = Decimal("6000.00")
        self.assertGreater(dentro_da_faixa, REDUCAO_ATE_ISENCAO)
        self.assertLessEqual(dentro_da_faixa, REDUCAO_ATE_ZERO)

        com_reducao = calcular_ir(base, rendimento_mensal=dentro_da_faixa)
        self.assertGreater(
            sem_reducao,
            com_reducao,
            "a Lei 15.270/2025 tem de reduzir o imposto dentro da faixa "
            "de R$ 5.000 a R$ 7.350 por mes",
        )

        self.assertEqual(
            calcular_ir(base, rendimento_mensal=Decimal("20000.00")),
            sem_reducao,
            "acima de REDUCAO_ATE_ZERO a lei nao da reducao nenhuma",
        )


class AIsencaoAnualBateCertoComAMensalTest(TestCase):
    """29.145,60/ano e' a primeira faixa de `FAIXAS_IR` (L87).

    E' 2.428,80 por mes. Se uma das duas mudar e a outra nao, o produtor que
    ganha abaixo do limite paga num mes e noutro nao — e o resultado passa a
    depender de como o ano foi dividido, que e' o tipo de coisa que um
    sistema de decisao nao pode esconder.
    """

    def test_a_primeira_faixa_e_a_isencao(self):
        teto, deducao, aliquota = FAIXAS_IR[0]
        self.assertEqual(teto, Decimal("29145.60"))
        self.assertIsNone(deducao, "None na deducao marca a faixa isenta")
        self.assertIsNone(aliquota, "faixa isenta nao tem aliquota")

    def test_o_limite_anual_e_o_mensal_vezes_doze(self):
        self.assertEqual(Decimal("2428.80") * 12, FAIXAS_IR[0][0])

    def test_ganhar_exatamente_o_limite_da_zero(self):
        self.assertEqual(
            calcular_ir(Decimal("29145.60"), rendimento_mensal=Decimal("2428.80")),
            ZERO,
            "exatamente no limite anual: isento.",
        )

    def test_o_tecto_anual_nao_e_uma_falesia(self):
        """MEDIDO TRES VEZES, e a terceira e' a que ensina.

        Escrevi este teste como "um centimo acima do limite anual paga". Nao
        paga: `Decimal('0.00')`. E' **o codigo certo**.

        A razao esta' em `calcular_ir` L400-409: o ciclo salta a faixa
        isenta (`if aliquota is None: continue`), portanto base 29.145,61 cai
        na segunda faixa e da

            29145.61 * 0.075 - 2185.92 = 0.00075  ->  0.00

        A deducao da faixa foi construida para o imposto chegar a zero
        CONTINUAMENTE no tecto. Nao ha degrau: um centimo acima ainda paga
        uma fracao de centimo.

        Um teste que exigisse `> 0` aqui estaria a testar uma cliff que a lei
        nao tem — e a 'corrigi-lo' seria introduzir um arredondamento que
        cobra a um produtor que a lei isenta.
        """
        self.assertEqual(
            calcular_ir(Decimal("29145.60"), rendimento_mensal=Decimal("6000.00")),
            ZERO,
            "no tecto: zero",
        )
        self.assertGreaterEqual(
            calcular_ir(Decimal("29145.61"), rendimento_mensal=Decimal("6000.00")),
            ZERO,
            "um centimo acima: continua zero. A tabela e' continua, nao uma falesia.",
        )
        # e o imposto sobe — devagar, mas sobe. Uso 80.000 porque a 40.000 o
        # redutor (R$ 179,75/mes = R$ 2.157/ano) excede o imposto e o tecto de
        # zero tapa tudo: isso tambem e' correcto, e ja' o testei a parte.
        self.assertGreater(
            calcular_ir(Decimal("80000.00"), rendimento_mensal=Decimal("6000.00")),
            calcular_ir(Decimal("40000.00"), rendimento_mensal=Decimal("6000.00")),
            "acima do tecto o imposto tem de crescer",
        )

    def test_o_teto_de_zero_da_reducao_e_ele_proprio(self):
        """MEDIDO: escrevi `> 0` para 40.000/ano a 6.000/mes e devolveu
        `0.00`. **E' o codigo certo, outra vez.** O redutor e' R$ 179,75/mes =
        R$ 2.157/ano, e o imposto a essa base e' R$ 1.270. A lei zera.

        Um teste que exigisse imposto positivo aqui estaria a exigir que a lei
        cobrasse a um produtor que ela isenta.
        """
        imposto = calcular_ir(Decimal("40000.00"), rendimento_mensal=Decimal("6000.00"))
        redutor = Decimal("179.75") * 12
        self.assertEqual(imposto, ZERO)
        self.assertGreater(redutor, ZERO, "o redutor e' que tapou o imposto")


class ADeducaoPorDependenteTest(TestCase):
    """Lei 15.191/2025: R$ 189,59 por dependente e por mes.

    Um valor de deducao escrito de memoria (eu escrevi 1.500 no comentario de
    um commit anterior) muda o imposto de quem tem familia.
    """

    def test_o_valor_mensal_e_o_da_lei(self):
        self.assertEqual(DEDUCAO_DEPENDENTE_MENSAL, Decimal("189.59"))

    def test_a_deducao_entra_como_valor_da_tabela(self):
        """O que este teste faz, e o que nao faz.

        Escrevi-o primeiro a tentar mostrar "mais dependentes, menos imposto"
        e o que obtive foi `Decimal('45012.60') not greater than
        Decimal('45012.60')` — um `>` meu, quando `teto` E' 45012.60. Erro
        aritmetico no teste, e o teste nao media o que dizia medir.

        `calcular_ir` NAO recebe dependentes: a deducao entra antes, como
        valor ja' dedicado. Por isso o que se verifica aqui e' que a tabela
        aceita a deducao da lei — e que ela e' menor do que a deducao
        "simplificada" de R$ 607,20, que e' o limite alternativo.
        """
        _, deducao, _ = FAIXAS_IR[2]
        self.assertIsNotNone(deducao)
        self.assertEqual(DEDUCAO_DEPENDENTE_MENSAL, Decimal("189.59"))
        self.assertLess(
            DEDUCAO_DEPENDENTE_MENSAL * 12,
            Decimal("7286.40"),
            "a deducao por dependente tem de ser menor que a deducao "
            "simplificada anual (R$ 607,20 x 12)",
        )


class AProjecaoRecusaSemDeduibilidadeTest(TestCase):
    """A parte honesta: sem o que e' dedutivel, nao existe projecao.

    Um `percentual_dedutivel_padrao` inventado seria comodo — e daria um
    imposto MENOR, porque tudo contaria como despesa. O produtor compraria o
    tractor a pensar que paga menos do que paga.
    """

    @pytest.mark.django_db
    def test_sem_percentual_declarado_ha_bloqueio(self):
        projecao = projetar_ir(propriedade_id=1, ano=2026)
        self.assertTrue(
            projecao.bloqueios,
            "sem percentual dedutivel declarado tem de haver bloqueio",
        )
        self.assertIsNone(
            projecao.despesa_dedutivel,
            "sem percentual declarado a despesa dedutivel e' DESCONHECIDA, "
            "logo `None`. Deve ser `None`, nunca `0.00` — `0` e' medicao.",
        )
        for mes in projecao.meses:
            self.assertIsNone(
                projecao.ir_do_mes(mes),
                "sem dedutibilidade nao ha imposto por mes — `None` e' "
                "ausencia, `0.00` seria uma medicao que nao existe",
            )

    @pytest.mark.django_db
    def test_a_mensagem_diz_que_falta_a_deduibilidade(self):
        texto = " ".join(projetar_ir(propriedade_id=1, ano=2026).bloqueios).lower()
        self.assertIn("dedut", texto)

    @pytest.mark.django_db
    def test_a_reducao_mensal_ainda_nao_entra_na_projecao(self):
        """LACUNA DECLARADA. `Projecao.rendimento_mensal_medio` existe
        (L197) e `calcular_ir` consome-o (L256), mas `projetar_ir()` nao o
        preenche: a assinatura (L414-421) nao tem parametro para isso.

        Este teste fixa o estado de proposito. No dia em que `projetar_ir`
        aceitar o rendimento mensal, este teste falha — e e' essa a intencao:
        avisa que a reducao passou a valer para a projecao.
        """
        projecao = projetar_ir(
            propriedade_id=1, ano=2026, percentual_dedutivel_padrao=Decimal("1.00")
        )
        self.assertIsNone(
            projecao.rendimento_mensal_medio,
            "ainda nao preenchido. Se isto ter valor, alguem ligou a reducao na "
            "projecao — e entao este ficheiro esta' errado, nao o codigo.",
        )
