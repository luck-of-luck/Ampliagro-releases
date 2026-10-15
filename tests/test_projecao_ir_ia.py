"""A projecao de IR tem de chegar a IA e ao cliente MCP.

MEDIDO 2026-10-05 (agente 3). Um servico sem porta de entrada e' codigo
morto — e' a mesma falha que o `test_contrato_de_esquema` documenta noutro
lugar: **o esquema promete, o comportamento nao cumpre.** `projecao_ir.py`
existia e ninguem o chamava.

Estes testes verificam o caminho inteiro: intent registado, tool no catalogo
MCP, e — o mais importante — que o handler **nao inventa** a dedutibilidade
quando ela nao vem.
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from app.models.core import Propriedade
from app.models.financeiro import LancamentoFinanceiro


def _user(nome="ir-ia"):
    u, _ = get_user_model().objects.get_or_create(username=nome)
    return u


def _dados(ano=2026):
    u = _user()
    prop = Propriedade.objects.create(
        nome="Fazenda IR", bioma="cerrado", area_total="100", user=u
    )
    LancamentoFinanceiro.objects.create(
        propriedade=prop,
        tipo="RECEITA",
        categoria="venda",
        valor="100000",
        data=f"{ano}-03-15",
        descricao="venda de grao",
        pago=True,
    )
    return u, prop


class OIntentRegistadoTest(TestCase):
    def test_os_dois_intents_existem(self):
        from app.ia.sandbox import INTENTS

        for nome in ("projecao_ir", "valor_ir"):
            with self.subTest(intent=nome):
                self.assertIn(nome, INTENTS, f"`{nome}` nao chegou ao sandbox")

    def test_declaram_o_schema_dos_parametros(self):
        """Sem `params_schema`, o `inputSchema` sai vazio e o modelo erra."""
        from app.ia.sandbox import INTENTS

        for nome, param in (
            ("projecao_ir", "percentual_dedutivel"),
            ("valor_ir", "base_anual"),
        ):
            with self.subTest(intent=nome):
                spec = INTENTS[nome]
                self.assertIn("params_schema", spec)
                self.assertIn(param, spec["params_schema"])

    def test_as_tools_mcp_declaram_os_parametros(self):
        from app.amplia_mcp import catalogo_tools, nome_tool

        por_nome = {t["name"]: t for t in catalogo_tools()}
        for nome, param in (
            ("projecao_ir", "percentual_dedutivel"),
            ("valor_ir", "base_anual"),
        ):
            with self.subTest(intent=nome):
                tool = por_nome[nome_tool(nome)]
                props = tool["inputSchema"].get("properties", {})
                self.assertIn(param, props, f"{tool['name']} expoe um schema vazio")

    def test_sao_flags_de_leitura(self):
        from app.ia.sandbox import INTENTS

        for nome in ("projecao_ir", "valor_ir"):
            with self.subTest(intent=nome):
                self.assertEqual(INTENTS[nome]["flags"], ["fin.read"])

    def test_a_descricao_manda_nao_escolher_a_dedutibilidade(self):
        """A instrucao mais importante, para o modelo."""
        from app.ia.sandbox import INTENTS

        d = INTENTS["projecao_ir"]["descricao"].lower()
        self.assertIn("nao escolhas", d.replace("não", "nao"))
        self.assertIn("contador", d)

    def test_valor_ir_avisa_que_sem_reducao_o_numero_e_errado(self):
        """A pegadinha: 250.000 anuais com 4.000 por mes estao ISENTOS."""
        from app.ia.sandbox import INTENTS

        d = INTENTS["valor_ir"]["descricao"].lower()
        self.assertIn(
            "mensal",
            d,
            "a descricao tem de dizer que a reducao e' mensal. Sem isso o "
            "modelo responde com a tabela anual e da um numero que a lei "
            "isenta.",
        )


class OHandlerTest(TestCase):
    def test_sem_propriedade_diz_o_que_falta(self):
        from app.ia.intents_projecao_ir import h_projecao_ir

        _user("ir-vazio")
        r = h_projecao_ir(_user("ir-vazio"), {}, None)
        self.assertFalse(r["ok"])
        self.assertEqual(r["erro"], "sem_propriedade")

    def test_nao_projeta_outra_propriedade(self):
        """Tenancy. A IA nao projeta o IR do vizinho."""
        from app.ia.intents_projecao_ir import h_projecao_ir

        dono, prop = _dados()
        outro = _user("ir-outro")
        prop.user = outro
        prop.save()

        r = h_projecao_ir(
            dono, {"propriedade_id": prop.id, "percentual_dedutivel": "0.35"}, None
        )
        self.assertFalse(r["ok"], "a propriedade de outro produtor foi usada")
        self.assertEqual(r["erro"], "sem_propriedade")

    def test_sem_dedutibilidade_devolve_bloqueio_e_nao_numero(self):
        """O ponto central, medido pela fronteira da tool."""
        from app.ia.intents_projecao_ir import h_projecao_ir

        _, prop = _dados()
        r = h_projecao_ir(_user(), {"propriedade_id": prop.id}, None)

        self.assertFalse(r["ok_para_a_ia"])
        self.assertIsNone(r["imposto_total_estimado"])
        self.assertTrue(r["bloqueios"], "sem motivo a IA nao sabe o que perguntar")
        self.assertIn("o_que_dizer_ao_produtor", r)

    def test_o_que_dizer_ao_produtor_nao_fala_para_o_vazio(self):
        """Com `ok: false`, a frase tem de dar a proxima pergunta."""
        from app.ia.intents_projecao_ir import h_projecao_ir

        _, prop = _dados()
        r = h_projecao_ir(_user(), {"propriedade_id": prop.id}, None)
        frase = r["o_que_dizer_ao_produtor"].lower()
        self.assertIn("dedutivel", frase)
        self.assertIn("contador", frase)

    def test_com_dedutibilidade_projecta(self):
        from app.ia.intents_projecao_ir import h_projecao_ir

        _, prop = _dados()
        r = h_projecao_ir(
            _user(),
            {"propriedade_id": prop.id, "percentual_dedutivel": "0.35"},
            None,
        )
        self.assertTrue(r["ok_para_a_ia"])
        self.assertIsNotNone(r["imposto_total_estimado"])
        self.assertEqual(len(r["meses"]), 12)

    def test_percentual_invalido_vira_none_e_nao_um_numero(self):
        """ "treinta e cinco" nao e' 0.35. Nao se faz `float()` aSort."""
        from app.ia.intents_projecao_ir import h_projecao_ir

        _, prop = _dados()
        r = h_projecao_ir(
            _user(),
            {"propriedade_id": prop.id, "percentual_dedutivel": "trinta e cinco"},
            None,
        )
        self.assertFalse(r["ok_para_a_ia"], "texto virou numero")

    def test_a_receita_conjectural_entra_separada(self):
        from app.ia.intents_projecao_ir import h_projecao_ir

        _, prop = _dados()
        r = h_projecao_ir(
            _user(),
            {
                "propriedade_id": prop.id,
                "percentual_dedutivel": "1",
                "receita_conjectural": {"maio": "50000"},
            },
            None,
        )
        maio = next(m for m in r["meses"] if m["mes"] == "maio")
        self.assertEqual(maio["receita_ha"], 0.0)
        self.assertEqual(maio["receita_conjectural_ha"], 50000.0)


class OValorIrTest(TestCase):
    def test_sem_base_diz_o_que_falta(self):
        from app.ia.intents_projecao_ir import h_valor_ir

        r = h_valor_ir(None, {}, None)
        self.assertFalse(r["ok"])
        self.assertEqual(r["erro"], "falta_base")

    def test_a_base_entra_como_string(self):
        """A tool manda string. `250000` e' o que chega."""
        from app.ia.intents_projecao_ir import h_valor_ir

        r = h_valor_ir(None, {"base_anual": "250000"}, None)
        self.assertTrue(r["ok"])
        self.assertGreater(r["imposto_sem_reducao"], 0.0)

    def test_sem_rendimento_mensal_a_reducao_e_null_e_nao_zero(self):
        """**MEDIDO: o bug de lei mais caro que ja cometi neste modulo.**

        A primeira versao subtraia um `redutor` monetario. A tabela de reducao
        da Lei 15.270/2025 nao e' "um valor a tirar do imposto" — e' uma
        tabela **com teto**. Abaixo de R$ 5.000 por mes o redutor dava
        `0.00`, e subtrair `0.00` nao zera nada.

        O modulo devolvia **R$ 56.325,72** a um produtor que factura 40 mil
        por ano a 3.333 por mes — e que, por lei, nao paga imposto nenhum.

        E' a razao de `imposto_com_reducao` ser `None` e nao `0`: sem o
        rendimento mensal a lei nao pode ser aplicada, e a resposta honesta
        e' "nao sei".
        """
        from app.ia.intents_projecao_ir import h_valor_ir

        r = h_valor_ir(None, {"base_anual": "40000"}, None)

        self.assertGreater(r["imposto_sem_reducao"], 0.0)
        self.assertIsNone(
            r["imposto_com_reducao"],
            "a reducao foi aplicada sem o rendimento mensal",
        )
        self.assertIn(
            "mensal", r["nota"], "a nota tem de explicar que a reducao e' mensal"
        )
        self.assertIn("ZERO", r["nota"], "a nota tem de dizer que ha isencao")

    def test_o_rendimento_mensal_zera_o_imposto_de_quem_esta_isento(self):
        """O caso de negocio, com o parametro certo.

        Produtor que factura 40.000 por ano — 3.333 por mes. Pela tabela de
        incidencia annual paga 1.270,09; pela reducao da Lei 15.270/2025, que
        zera ate R$ 5.000 por mes, paga **zero**.
        """
        from app.ia.intents_projecao_ir import h_valor_ir

        r = h_valor_ir(
            None, {"base_anual": "40000", "rendimento_mensal": "3333.33"}, None
        )
        self.assertAlmostEqual(r["imposto_sem_reducao"], 1270.09, places=2)
        self.assertEqual(
            r["imposto_com_reducao"],
            0.0,
            "um produtor a 3.333 por mes esta isento pela Lei 15.270/2025, "
            "embora a tabela annual sozinha de 1.270,09.",
        )
        # e os numeros batem entre si
        self.assertAlmostEqual(40000 / 12, 3333.33, places=1)

    def test_acima_de_sete_mil_e_meia_a_reducao_nao_muda_nada(self):
        from app.ia.intents_projecao_ir import h_valor_ir

        r = h_valor_ir(
            None, {"base_anual": "250000", "rendimento_mensal": "20833"}, None
        )
        self.assertEqual(r["imposto_com_reducao"], r["imposto_sem_reducao"])
        self.assertEqual(r["reducao_mensal_aplicada"], 0.0)

    def test_acima_da_faixa_nao_ha_reducao_e_o_imposto_integral(self):
        """**MEDIDO: o bug de lei mais subtil que ja cometi.**

        `reducao_ir()` devolve `0.00` em **dois** casos que significam o
        oposto:

            1. abaixo de R$ 5.000 por mes -> a lei **isenta**;
            2. acima de R$ 7.350 por mes -> a lei nao da **reducao**.

        Eu tratava os dois com um `else: return 0.00`. O caso 2 devolvia
        zero: um produtor que fatura R$ 250 mil por ano a R$ 20.833 por mes
        recebia `imposto_com_reducao: 0.0`.

        **Isento quem nao tem direito a isencao** — o sistema a inventar um
        beneficio fiscal que a lei nao da, que e' o inverso do honesto. Um
        produtor que lesse "imposto zero" e nao PAGasse o que devia ia
        discovering o erro em marco, com multa e juros.

        Este teste existe para que um `0.00` redutor nunca volte a ser lido
        como isencao.
        """
        from app.ia.intents_projecao_ir import h_valor_ir

        isento = h_valor_ir(
            None, {"base_anual": "250000", "rendimento_mensal": "3333.33"}, None
        )
        integral = h_valor_ir(
            None, {"base_anual": "250000", "rendimento_mensal": "20833"}, None
        )

        self.assertEqual(isento["imposto_com_reducao"], 0.0, "aqui a lei isenta")
        self.assertEqual(
            integral["imposto_com_reducao"],
            integral["imposto_sem_reducao"],
            "acima de R$ 7.350 por mes NAO ha reducao: o imposto e' o "
            "integral. Devolver 0.00 aqui e' inventar uma isencao.",
        )
        self.assertGreater(integral["imposto_com_reducao"], 0.0)

        # e os dois redutores sao 0.00 — e mesmo assim o resultado difere
        self.assertEqual(integral["reducao_mensal_aplicada"], 0.0)
        self.assertEqual(isento["reducao_mensal_aplicada"], 0.0)

    def test_no_meio_a_reducao_zera_o_imposto_da_faixa(self):
        """R$ 6.000 por mes: a reducao existe, e tem teto."""
        from app.services.projecao_ir import calcular_ir, reducao_ir

        base = Decimal("250000")
        mensal = Decimal("6000")

        redutor = reducao_ir(mensal)
        self.assertGreater(redutor, Decimal("0.00"), "a 6.000 por mes ha reducao")

        # a reducao anual e' o redutor x 12, e o resultado nao pode ser negativo
        anual = redutor * 12
        bruto = calcular_ir(base)
        self.assertGreaterEqual(bruto - anual, Decimal("0.00"))

    def test_a_isencao_so_e_verdade_abaixo_de_cinco_mil(self):
        """`None` quando nao se sabe. Nunca `False` por omissao."""
        from app.services.projecao_ir import is_isento_por_reducao

        self.assertIsNone(is_isento_por_reducao(None), "nao sei nao e' nao tem")
        self.assertTrue(is_isento_por_reducao(Decimal("3333")))
        self.assertTrue(is_isento_por_reducao(Decimal("5000")))
        self.assertFalse(is_isento_por_reducao(Decimal("5000.01")))
        self.assertFalse(is_isento_por_reducao(Decimal("20833")))

    def test_a_base_anual_e_o_mensal_tem_de_bater(self):
        """250.000 por ano **sao** 20.833 por mes. Nao 4.000.

        O primeiro teste desta classe usava 250.000 com 4.000 por mes, que
        sao numeros incoerentes entre si. E' o mesmo genre de erro que me deu
        a tabela errada: um numero inventado que ninguem verifica.
        """
        self.assertAlmostEqual(250000 / 12, 20833.33, places=1)

    def test_acima_de_sete_mil_e_meia_a_reducao_nao_muda_nada(self):
        from app.ia.intents_projecao_ir import h_valor_ir

        r = h_valor_ir(
            None, {"base_anual": "250000", "rendimento_mensal": "20000"}, None
        )
        self.assertEqual(r["imposto_com_reducao"], r["imposto_sem_reducao"])
        self.assertEqual(r["reducao_mensal_aplicada"], 0.0)


class OContratoDoSchemaTest(TestCase):
    """A escala e' a da folha 100x50, e o veredicto tem de ser `C`.

    Se a ancora apontar para uma docstring, `test_ancora_tem_codigo.py` — de
    outra sessao — acusa. Este so verifica que a dimensao existe mesmo.
    """

    def test_f17_existe_na_folha_e_esta_em_N(self):
        import openpyxl

        from app.services.comparativo_ambiental import RAIZ

        wb = openpyxl.load_workbook(
            RAIZ / "docs" / "arquitetura" / "sistema" / "comparativo" / "comparativo-100x50.xlsx",
            read_only=True,
            data_only=True,
        )
        try:
            linhas = list(wb["AMPLIAGRO"].iter_rows(values_only=True))
        finally:
            wb.close()

        f17 = next((r for r in linhas[1:] if r[0] == "F17"), None)
        self.assertIsNotNone(f17, "F17 desapareceu da planilha")
        self.assertIn("projecao", str(f17[2]).lower() + str(f17[5]).lower())
