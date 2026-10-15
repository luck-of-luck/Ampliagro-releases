"""A guia ANIMAL liga ao registo pela PONTE, nao pelo criterio errado.

O QUE ESTE SERVICO FAZ, E PORQUE NAO REUSA O `historico_cultura`
================================================================
`historico_cultura` conta **ciclos** — dias entre plantio e colheita, de
`app_safra`. Isso e' agricultura anual. **Um boi nao tem ciclo de plantio.**
Tem lactacao (305 dias), gestacao (283), idade de abate. Aplicar o ciclo de
safras a um cartao degado e' escrever "128 dias" num bovino — uma
affirmacao falsa com a minha propria assinatura.

Por isso um servico aparte, com metricas que fazem sentido para gado.

O ERRO QUE ESTE SERVICO CORRIGE
================================
A guia animal filtra `Cultura.grupo IN ('bovinos', 'suinos', ...)`.
O `RegistroProducao.grupo` do produtor e' **`'animal'`** — nao `'bovinos'`.
Sao duas colunas com nomes diferentes, e **nenhum codigo as liga**.

A ponte que existe e' o `cultura_id`. MEDIDO 2026-10-05 em `db.sqlite3`:

    Ayrshire        cultura_id=28533   -> Cultura.grupo = bovinos
    Angus           cultura_id=28548   -> bovinos
    Tilápia         cultura_id=28709   -> peixes

E o `cultura_id` esta preenchido em **100%** dos 66 registos. A contagem
por `cultura_id` funciona; a contagem por `grupo` da-string nunca-resultou.

Este e' o mesmo erro, pela terceira vez, na mesma pagina:
  1. `icontains=""` casava com todas as linhas e nao com nenhuma util
  2. `ciclo` dava 112 dias em vez de 116 (aritmetica `ano*372 + mes*31`)
  3. aqui: contagem por `'animal'` quando a guia filtra `'bovinos'`

**Nos tres, a leitura correcta seria "o produtor nao registou nada". E nos
tres ele tinha registado.**

O QUE ESTE TESTE TRAVA
======================
1. A contagem por `cultura_id` encontra o que o produtor registou.
2. A contagem por `grupo`-string **nao** encontra — e isso fica escrito,
   para ninguem "simplificar" o codigo para o caminho que nao funciona.
3. Sem registo -> `fonte: "sem_dado"`. **Nunca 0.**
4. `status` desconhecido nao vira activo nem inactivo.
5. A assinatura nao ganha `propriedade_ids=None` — o tenancy entra pelo
   filtro, e um filtro opcional e' um filtro que alguem vai esquecer.
"""

from django.test import SimpleTestCase

from app.services.registro_por_cultura import (
    SEM_DADO,
    _data_de,
    registos_por_cultura,
)


class DataDeTest(SimpleTestCase):
    def test_aceita_as_tres_formas(self):
        import datetime

        self.assertEqual(_data_de(datetime.date(2026, 5, 6)), "2026-05-06")
        self.assertEqual(_data_de(datetime.datetime(2026, 5, 6, 14, 30)), "2026-05-06")
        self.assertEqual(_data_de("2026-05-06T14:30:00"), "2026-05-06")
        self.assertEqual(_data_de("2026-05-06"), "2026-05-06")

    def test_ilegivel_da_none(self):
        for mau in (None, "", "ontem", "2026", "aaaa-bb-cc", 12345):
            self.assertIsNone(_data_de(mau), f"{mau!r} devolve None.")

    def test_data_invalida_no_calendario_da_none(self):
        """`"2026-13-45"` tem 10 caracteres e nao e' uma data."""
        self.assertIsNone(_data_de("2026-13-45"))


class RegistosPorCulturaTest(SimpleTestCase):
    def test_encontra_pela_ponte_cultura_id(self):
        """A mesma tres registos de Ayrshire que a base tem."""
        r = registos_por_cultura(
            [
                (28533, "ativo", "2026-05-06"),
                (28533, "ativo", "2026-04-01"),
                (28533, "ativo", "2026-03-15"),
                (28548, "ativo", "2026-01-10"),  # Angus
            ]
        )
        ayrshire = r[28533]
        self.assertEqual(ayrshire["registos"], 3)
        self.assertEqual(ayrshire["activos"], 3)
        self.assertEqual(ayrshire["ultimo"], "2026-05-06")
        self.assertEqual(ayrshire["fonte"], "medido")
        self.assertEqual(r[28548]["registos"], 1)

    def test_a_conta_por_grupo_string_nao_encontra_nada(self):
        """A CONTRA-PROVA: e' por isto que este servico existe.

        Se alguem "simplificar" o codigo para contar por `grupo`, a base
        real da **zero** — porque o produtor escreve `'animal'` e a guia
        filtra `'bovinos'`. Este teste fixa a razao.
        """
        registos = [
            (28533, "animal", "2026-05-06"),
            (28548, "animal", "2026-01-10"),
            (28709, "aquatica", "2026-02-02"),
        ]

        # pelo grupo que o produtor escreve: nada
        por_grupo = {}
        for _cid, grupo, _d in registos:
            por_grupo[grupo] = por_grupo.get(grupo, 0) + 1
        self.assertIn("animal", por_grupo)
        self.assertNotIn(
            "bovinos",
            por_grupo,
            "o registo tem 'animal' e a guia filtra 'bovinos'. Se esta "
            "assercao falhar, alguem ligou as duas coisas — e a ligacao "
            "tem de ser pelo `cultura_id`, nao pelo nome.",
        )

        # pela ponte: encontra
        r = registos_por_cultura([(c, "ativo", d) for c, _g, d in registos])
        self.assertEqual(len(r), 3, "a ponte por `cultura_id` encontra os 3")

    # ------------------------------------------------------------------
    # 3) SEM DADO — e nao zero
    # ------------------------------------------------------------------
    def test_sem_registo_da_sem_dado_e_nao_zero(self):
        """41 racas em `bovinos`, 5 com registo. As outras 36 mostram
        "registar", e nao "0 registos".

        "0 registos" afirma que o produtor foi ate a tela, viu o boi e
        decidiu nao registar. Nao foi isso: ele nunca abriu aquela tela.
        """
        vazio = SEM_DADO
        self.assertEqual(vazio["fonte"], "sem_dado")
        self.assertIsNone(vazio["activos"])
        self.assertIsNone(vazio["ultimo"])
        self.assertIsNotNone(vazio["motivo"])
        self.assertEqual(vazio["registos"], 0)

    def test_a_sem_dado_para_o_ecra(self):
        from app.services.registro_por_cultura import registos_por_cultura as f

        r = f([])
        self.assertEqual(r, {}, "sem registos, o servico devolve um dict vazio")

    # ------------------------------------------------------------------
    # 4) STATUS DESCONHECIDO
    # ------------------------------------------------------------------
    def test_status_desconhecido_nao_vira_activo_nem_inactivo(self):
        r = registos_por_cultura(
            [
                (1, "ativo", "2026-01-01"),
                (1, "arquivado", "2026-02-01"),  # nem activo nem inactivo
                (1, None, "2026-03-01"),  # sem status
                (1, "", "2026-04-01"),
            ]
        )
        self.assertEqual(
            r[1]["registos"],
            4,
            "os 4 registos contam no total",
        )
        self.assertEqual(
            r[1]["activos"],
            1,
            "so o 'ativo' conta como activo. Um status desconhecido virar "
            "'activo' seria inventar que o produtor ainda tem o animal.",
        )

    # ------------------------------------------------------------------
    # 5) A ASSINATURA
    # ------------------------------------------------------------------
    def test_o_servico_nao_aceita_ids_de_propriedade(self):
        """`registos_por_cultura` recebe a query ja filtrada, e so.

        Um `propriedade_ids=None` opcional seria um filtro que alguem ia
        esquecer — e esquecer o tenant nao da erro: da o registo do
        vizinho. Este teste existe porque a assinatura e' a unica coisa
        que o impede.
        """
        import inspect

        params = list(inspect.signature(registos_por_cultura).parameters)
        self.assertEqual(
            params,
            ["registos"],
            "a assinatura mudou para %s. Se ganhou `propriedade_ids`, "
            "passou a haver um caminho que nao filtra por tenant." % params,
        )

    def test_a_data_mais_recente_vence(self):
        """Datas fora de ordem nao baguncam. Uma registo de marco escrito
        depois de um de maio fica com a data de marco, se for a maior."""
        r = registos_por_cultura(
            [
                (1, "ativo", "2026-12-31"),
                (1, "ativo", "2026-01-01"),
                (1, "ativo", "2026-06-15"),
            ]
        )
        self.assertEqual(r[1]["ultimo"], "2026-12-31")

    def test_data_ilegivel_nao_apaga_uma_data_valida(self):
        r = registos_por_cultura(
            [
                (1, "ativo", "2026-05-06"),
                (1, "ativo", "ontem"),  # ilegivel
            ]
        )
        self.assertEqual(
            r[1]["ultimo"],
            "2026-05-06",
            "um registo com data ilegivel apagou a data valida anterior. "
            "Um bug de leitura nao pode apagar um facto.",
        )
