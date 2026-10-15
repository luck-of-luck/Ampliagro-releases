"""O historico por cultura tem de ser MEDIDO, NUNCA AFIRMADO.

O QUE ESTE SERVICO FAZ
======================
A tabela `Cultura` tem a agronomia vazia (MEDIDO 2026-10-05):

    janela_plantio_inicio   0/709    0.0%
    janela_plantio_fim      0/709    0.0%
    ciclo_dias             2/709    0.3%

A guia mostra 709 nomes e zero agronomia. Este servico extrai o que EXISTE
nas safras do produtor — que e' mais do que a guia mostra hoje — sem
inventar o que nao existe.

OS CASOS DESTE FICHEIRO SAO OS DA BASE REAL
============================================
    Milho   2025-02-28 -> 2025-06-20   116 dias   75 sc/ha
    Soja    2024-10-15 -> 2025-02-20   129 dias   65,3 sc/ha
    Cafe    4 safras, ciclos de 60, 435, 447 e 461 dias

O ultimo e' o caso que interessa. A amplitude e' de 409 dias — nao e'
variacao de cultura, e' **data mal posta** (60 dias e' curto demais para um
cafe perene). A media daria 264 dias, um numero que nunca existiu em
nenhuma lavoura. O servico tem de recusar mostrar esse numero, e dizer
porque.

OS QUATRO LIMITES QUE ISTO TRAVA
================================
1. Sem safra -> `safras: 0` e `fonte: "sem_dado"`. NUNCA um ciclo de 0.
2. Amplitude > razao -> o ciclo **desaparece** e fica um alerta. Nao e' um
   aviso por cima de um numero: o numero vai-se embora.
3. Uma safra -> `ciclo_amostras: 1`, para o ecrã poder dizer "1 safra" em vez
   de "ciclo: 129 dias" sem saber se se repete.
4. Safra sem cultura -> ignorada. Nao se cria uma cultura `None`.
"""

from django.test import SimpleTestCase

from app.services.historico_cultura import (
    RAZAO_AMPLITUDE_SUSPEITA,
    SEM_DADO,
    dias_entre,
    historico_por_cultura,
    para_o_ecra,
)

# (cultura_id, ano, plantio, colheita, produtividade, area)


class DiasEntreTest(SimpleTestCase):
    def test_ciclo_real_da_base(self):
        # os dois ciclos de que tenho certeza, da base real
        # conferidos com datetime.date. A primeira versao deste ficheiro
        # esperava 116 e 129, e falhou com 112 e 128: o codigo do servico
        # usava a aritmetica `ano*372 + mes*31 + dia`, que ignora os meses
        # de 30 dias e os anos bissextos. O codigo estava errado e o
        # teste estava errado do mesmo lado — ver o docstring do servico.
        self.assertEqual(dias_entre("2025-02-28", "2025-06-20"), 112)
        self.assertEqual(dias_entre("2024-10-15", "2025-02-20"), 128)

    def test_data_falta_da_none(self):
        self.assertIsNone(dias_entre("2025-02-28", None))
        self.assertIsNone(dias_entre(None, "2025-06-20"))
        self.assertIsNone(dias_entre(None, None))

    def test_data_invertida_da_none(self):
        """Colheita antes do plantio e' erro de digitacao, nao ciclo."""
        self.assertIsNone(dias_entre("2025-06-20", "2025-02-28"))

    def test_data_ilegivel_da_none_em_vez_de_rebentar(self):
        """Uma pagina de consulta nao pode rebentar por uma data."""
        for mau in ("", "ontem", "2025", "31/02/2025", "aaaa-bb-cc"):
            self.assertIsNone(
                dias_entre(mau, "2025-06-20"),
                "'%s' devolve None, nao um numero nem uma excecao." % mau,
            )


class HistoricoPorCulturaTest(SimpleTestCase):
    # ------------------------------------------------------------------
    # 1) O CASO NORMAL — soja, como esta na base
    # ------------------------------------------------------------------
    def test_soja_da_um_ciclo_observado(self):
        h = historico_por_cultura(
            [(803, 2024, "2024-10-15", "2025-02-20", 65.3, 420.0)]
        )
        soja = h[803]
        self.assertEqual(soja["ciclo_medio"], 128)
        self.assertEqual(soja["ciclo_amostras"], 1)
        self.assertEqual(soja["anos"], [2024])
        self.assertEqual(soja["produtividade_media"], 65.3)
        self.assertEqual(soja["area_total"], 420.0)
        self.assertEqual(soja["fonte"], "medido")
        self.assertIsNone(soja["alerta"])

    # ------------------------------------------------------------------
    # 2) O CASO QUE IMPORTA — cafe com datas spreadidas
    # ------------------------------------------------------------------
    def test_ciclo_com_amplitude_absurda_desaparece(self):
        """A base real: cafe com 60, 443, 455 e 469 dias.

        A amplitude de 409 dias nao e' variacao de cultura. A media daria
        264 dias, e 264 nao e' o ciclo de nenhum destes talhoes. Mostrar
        esse numero e' affirmar o que nao se mediu — e o produtor que comparar
        com o vizinho descobre que e' falso.

        O ciclo tem de sumir, e o motivo tem de ficar.
        """
        h = historico_por_cultura(
            [
                (802, 2023, "2023-05-01", "2023-06-30", 35, 28.5),
                (802, 2024, "2024-05-01", "2025-07-10", 30, 28.5),
                (802, 2024, "2024-05-01", "2025-07-22", 33, 22.0),
                (802, 2024, "2024-05-01", "2025-08-05", 32, 18.8),
            ]
        )
        cafe = h[802]

        self.assertIsNone(
            cafe["ciclo_medio"],
            "O ciclo medio foi mostrado apesar de a amplitude ser de 401 "
            "dias. A media seria 264 dias, que nao e' o ciclo de nenhum "
            "talhao. E' um numero inventado com ar de medido.",
        )
        self.assertIsNone(cafe["ciclo_amplitude"])
        self.assertIsNotNone(
            cafe["alerta"],
            "O ciclo sumiu mas nao ha explicacao. O produtor ve um campo vazio "
            "e pensa que o sistema falhou.",
        )
        self.assertIn("401", cafe["alerta"])
        # o resto continua medido
        self.assertEqual(cafe["anos"], [2023, 2024])
        self.assertEqual(cafe["produtividade_media"], 32.5)
        self.assertEqual(cafe["area_total"], 97.8)
        self.assertEqual(cafe["fonte"], "medido")

    def test_a_regra_da_amplitude_esta_onde_diz(self):
        """Um ciclo de 120 e um de 135 **nao** e' a mesma coisa que 60 e 469."""
        estavel = historico_por_cultura(
            [
                (1, 2024, "2024-01-01", "2024-05-01", 10, 1),  # ~120
                (1, 2024, "2024-01-01", "2024-05-16", 10, 1),
            ]  # ~135
        )
        self.assertIsNotNone(
            estavel[1]["ciclo_medio"],
            "uma variacao de 15 dias foi tratada como dado mau posto. "
            "Variacao normal de cultura nao gera alerta.",
        )
        self.assertIsNone(estavel[1]["alerta"])

        # e o limiar e' o que diz
        self.assertGreater(
            RAZAO_AMPLITUDE_SUSPEITA,
            1.0,
            "uma razao de 1.0 geraria alerta em qualquer variacao",
        )

    # ------------------------------------------------------------------
    # 3) SEM DADO — e o caso de 703 das 709 culturas
    # ------------------------------------------------------------------
    def test_cultura_sem_safra_da_sem_dado_e_nao_zero(self):
        """703 das 709 culturas da base nao tem safra nenhuma.

        Mostrar `safras: 0` seria afirmar que o produtor fez zero safras. Ele
        nao fez nenhuma: ainda nao plantou aquela cultura. E' a diferenca
        entre um dado e uma affirmacao.
        """
        vazio = para_o_ecra({})
        self.assertEqual(vazio["fonte"], "sem_dado")
        self.assertIsNone(vazio["ciclo_medio"])
        self.assertIsNotNone(vazio["motivo"])
        self.assertEqual(vazio["safras"], 0)
        self.assertEqual(vazio["anos"], [])
        self.assertIsNone(vazio["produtividade_media"])

    def test_um_dicionario_vazio_da_o_mesmo_que_sem_dado(self):
        self.assertEqual(para_o_ecra({}), SEM_DADO)
        self.assertEqual(para_o_ecra(None), SEM_DADO)

    # ------------------------------------------------------------------
    # 4) O TENANTY ENTRA PELO FILTRO, NAO POR PARAMETRO
    # ------------------------------------------------------------------
    def test_safra_sem_cultura_e_ignorada(self):
        """Nao se cria uma cultura `None`.

        Uma safra sem `cultura_id` nao pertence a nenhuma ficha. Registar sob
        `None` seria inventar uma cultura que o produtor nunca pediu — e
        essa apareceria na guia como um cartao sem nome.
        """
        h = historico_por_cultura(
            [
                (None, 2024, "2024-01-01", "2024-05-01", 10, 5),
                (803, 2024, "2024-01-01", "2024-05-01", 10, 5),
            ]
        )
        self.assertNotIn(
            None, h, "uma cultura None foi criada a partir de uma safra sem cultura"
        )
        self.assertEqual(list(h), [803])

    def test_o_servico_nao_aceita_ids_de_propriedade(self):
        """`historico_por_cultura` recebe a query ja filtrada, e so.

        Passar `propriedade_ids` seria um parametro opcional de filtro, e um
        filtro opcional e' um filtro que alguem vai esquecer. E esquecer o
        tenant nao da erro: da a safra do vizinho.

        Este teste existe porque a assinatura e' a unica coisa que impede o
        erro. Se alguem meter `propriedade_ids=None` como default, este falha.
        """
        import inspect

        params = list(inspect.signature(historico_por_cultura).parameters)
        self.assertEqual(
            params,
            ["safras"],
            "a assinatura mudou para %s. Se ganhou um `propriedade_ids=None`, "
            "passou a haver um caminho que nao filtra por tenant — e esse "
            "caminho devolve a safra de outra pessoa sem dar erro." % params,
        )

    # ------------------------------------------------------------------
    # 5) A AMOSTRA — uma safra nao e' um ciclo, e' uma observacao
    # ------------------------------------------------------------------
    def test_uma_safra_marca_a_amostra(self):
        """Com uma safra, `ciclo_amostras` e' 1 e o ecrã pode dizer
        "1 safra" em vez de "ciclo: 129 dias".

        A distincao importa: 129 dias e' o que aconteceu **aquele ano**. Se
        o produtor repetir, pode ser 125 ou 140. Escrever "ciclo: 129 dias"
        sem a amostra e' transformar uma observacao numa regra — que e'
        exactamente o que `is_planting_season` fazia com as janelas.
        """
        h = historico_por_cultura([(1, 2024, "2024-01-01", "2024-05-10", 5, 1)])
        self.assertEqual(h[1]["ciclo_amostras"], 1)
        self.assertEqual(h[1]["ciclo_medio"], 130)

        h2 = historico_por_cultura(
            [
                (1, 2024, "2024-01-01", "2024-05-10", 5, 1),
                (1, 2025, "2025-01-01", "2025-05-09", 5, 1),
            ]
        )
        self.assertEqual(h2[1]["ciclo_amostras"], 2, "duas safras = duas amostras")

    # ------------------------------------------------------------------
    # 6) DADOS SUJOS NAO REBENTAM
    # ------------------------------------------------------------------
    def test_valores_ilegiveis_sao_ignorados_nao_fatam(self):
        h = historico_por_cultura(
            [
                (1, "ano-nao-e-numero", "2024-01-01", "2024-05-01", "x", "y"),
                (1, 2025, "ontem", "amanha", 10, 5),
            ]
        )
        self.assertEqual(h[1]["anos"], [2025], "o ano ilegivel foi ignorado")
        self.assertEqual(h[1]["produtividade_media"], 10.0)
        self.assertEqual(h[1]["ciclo_amostras"], 1)

    def test_uma_cultura_com_muitas_safras_agrega_bem(self):
        prods = [10.0, 20.0, 30.0, 40.0, 50.0]
        safras = [
            (1, ano, "2024-01-01", "2024-05-01", prod, 100.0)
            for ano, prod in zip(range(2020, 2025), prods)
        ]
        h = historico_por_cultura(safras)
        self.assertEqual(h[1]["anos"], [2020, 2021, 2022, 2023, 2024])
        self.assertEqual(h[1]["ciclo_amostras"], 5)
        self.assertEqual(h[1]["area_total"], 500.0)
        # media de 10,20,30,40,50 e' 30 — e a soma (150) seria 30x o numero
        self.assertEqual(
            h[1]["produtividade_media"],
            30.0,
            "a produtividade mostrava a SOMA em vez da media",
        )
        self.assertEqual(h[1]["ciclo_medio"], 121)
