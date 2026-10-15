"""O MCP tem de conseguir MONTAR uma tela sem nunca inventar.

Estes testes existem para travar três coisas, e as três são o mesmo defeito
visto de ângulos diferentes: a IA a apresentar como verdade algo que ninguém
mediu.

  1. Uma página só pode citar widgets que existem no catálogo.
  2. Um widget simulado tem de se-annunciar como simulado.
  3. Um dado que não existe tem de voltar `None` — nunca 0.

O 3 é o mais subtil e o mais importante. Zero é um número. Um painel que
mostra "custo por hectare: R$ 0,00" está a afirmar que a despesa foi zero, e
quem lê acredita. "Não há lançamentos" e "a despesa foi zero" são frases
opostas, e a interface tem de conseguir dizer a primeira.
"""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from app.amplia_mcp import (
    NOMES_CATALOGO,
    TOOLS_CATALOGO,
    catalogo_completo,
    executar_catalogo,
)

# MEDIDO 2026-10-05: `TOOLS_CATALOGO_ACEITAS` vive em `app.amplia_mcp.ferramentas_aceitas`,
# e nao e' exportada por `app/amplia_mcp/__init__.py`. Importar daqui dava
# ImportError e apagava o ficheiro inteiro de 17 testes da suite — um erro de
# import que se manifesta como "17 testes desapareceram", que e' exactamente
# a coisa que eu tinha acabado de fazer a outro ficheiro.
from app.amplia_mcp.ferramentas_aceitas import TOOLS_CATALOGO_ACEITAS
from app.ia.paginas import (
    MODELOS,
    montar,
    nome_modelo,
    o_que_existe,
    referencia_widgets,
)


class CatalogoNaoInventa(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="dono", password="x")

    def test_as_tools_de_catalogo_existem_e_sao_as_aceites(self):
        """Cada tool do catalogo tem de estar na lista de decididas.

        A lista NOMINADA vive em `app/amplia_mcp/ferramentas_aceitas.py`, e
        essa e' a decisao escrita. Antes esta assercao vivia aqui E em mais
        dois ficheiros, cada uma com a sua lista -- e quando as tools
        passaram de 3 para 4, uma actualizou-se e as outras duas falharam.
        Tres listas sao tres verdades, e a que ninguem mexe e' a que apodrece.

        O nome antigo dizia "sao_duas" e deixou de ser verdade: passou a ter
        leitores de dominio, todos por contexto e nenhum a escrever. Ver a
        decisao em `ferramentas_aceitas.py`.

        ## MEDIDO 2026-10-05: era `assertEqual`, e era impossivel

        Comparava por IGUALDADE `NOMES_CATALOGO` com `TOOLS_CATALOGO_ACEITAS`,
        e repetia a lista de nomes escrita aqui. A igualdade e' o que partia:
        as duas listas medem coisas diferentes -- uma e' entradas de catalogo,
        a outra e' nomes publicaveis, e um intent publicavel nao e' entrada de
        catalogo. Com igualdade, este teste e
        `tests_ciclo_automacao.py::ComparativoAcessivelTest` tinham de estar
        em conflito permanente.

        Fica a assercao que importa e que e' a mais forte: a lista tem de
        EXISTIR e tem de COBRIR o catalogo. A copia escrita a mao foi para --
        e' a "quarta verdade" que a docstring acima acusa.
        """
        declarados = set(TOOLS_CATALOGO_ACEITAS)
        self.assertTrue(
            declarados,
            "a lista de decididas esta' vazia: uma tool nova nao teria de ser "
            "declarada por ninguem, e a decisao de a publicar deixa de "
            "existir.",
        )
        por_declarar = set(NOMES_CATALOGO) - declarados
        self.assertEqual(
            por_declarar,
            set(),
            "tool de catalogo por decidir: %s" % sorted(por_declarar),
        )
        # E cada tool que existe tem de ser usavel: com descricao vazia o
        # modelo nao sabe o que ela faz, e sem schema de objecto a chamada
        # nao tem forma.
        for t in TOOLS_CATALOGO:
            self.assertTrue(t["description"].strip(), "tool sem descricao")
            self.assertEqual(t["inputSchema"]["type"], "object")

    def test_o_catalogo_diz_a_diferenca_entre_medido_e_simulado(self):
        """A coluna `fonte_dado` é o ponto inteiro do catálogo.

        Sem ela a IA monta uma tela com `kpi-praga-ai` ao lado de
        `kpi-produtividade` e mostra os dois com a mesma cara.
        """
        widgets = referencia_widgets()
        self.assertTrue(widgets)
        for w in widgets:
            self.assertIn(w["fonte_dado"], {"medido", "simulado"})
            self.assertEqual(
                w["fonte_dado"] == "simulado",
                bool(w["simulado"]),
                f"{w['id']}: fonte_dado e simulado discordam de simulado",
            )
        # e tem de haver os dois lados representados, senão o aviso é genérico
        self.assertTrue(any(w["simulado"] for w in widgets))
        self.assertTrue(any(not w["simulado"] for w in widgets))

    def test_apenas_medidos_tira_os_simulados(self):
        so_medidos = referencia_widgets(somente_medidos=True)
        self.assertTrue(so_medidos)
        self.assertFalse([w for w in so_medidos if w["simulado"]])

    def test_cada_modelo_so_cita_widgets_do_catalogo(self):
        """A garantia central: não se pode montar uma página de widget inventado.

        Um modelo que citasse um id fora do `CATALOGO_IA` passaria pelo
        validador do palco (que descarta o que não conhece) e a tela saía com
        menos cartões do que o modelo pede — sem erro visível. Aqui o modelo é
        rejeitado na construção, que é onde o erro ainda é barato.
        """
        from app.ia.palco import CATALOGO_IA

        for chave, m in MODELOS.items():
            for w in m["widgets"]:
                self.assertIn(
                    w, CATALOGO_IA, f"modelo {chave!r} cita widget inexistente {w!r}"
                )

    def test_um_nome_de_modelo_inventado_nao_monta_nada(self):
        r = montar(self.user, "dashboard-de-gado-super-avancado")
        self.assertFalse(r["ok"])
        # O erro traz as opções. Um LLM pequeno insiste quando não tem
        # resposta; dar-lhe o caminho é o que o faz parar.
        self.assertIn("modelos_disponiveis", r)
        self.assertTrue(r["modelos_disponiveis"])

    def test_nome_variado_cai_no_canonico(self):
        """Dois agentes que pedem 'café' e 'cafe' têm de montar a mesma tela."""
        for variante in ("cafe", "Café", "CAFÉ", " cafe ", "café"):
            self.assertEqual(nome_modelo(variante), "cafe")

    def test_a_conta_vazia_diz_o_que_lalta(self):
        """Não há dado, e a tela diz que não há. Não mostra zeros."""
        r = montar(self.user, "cafe")
        self.assertTrue(r["ok"])
        self.assertFalse(r["completa"])
        self.assertTrue(r["faltando"], "conta sem safra devia dizer que falta safra")
        self.assertIsNotNone(r["aviso"])

    def test_nenhum_valor_zero_pode_vir_de_dado_ausente(self):
        """A regra que impede a mentira silenciosa.

        Qualquer widget de servidor que fique sem valor tem de voltar `None`
        com `sem_dado`. Se voltar 0, o painel diz "a despesa foi zero" quando a
        verdade é "nunca foi registada nenhuma".
        """
        from app.ia.palco import WIDGETS_SERVIDOR

        r = montar(self.user, "panorama")
        self.assertTrue(r["ok"])
        for w in r["widgets"]:
            cfg = w.get("config") or {}
            if w.get("tipo") in WIDGETS_SERVIDOR and cfg.get("valor") is None:
                self.assertTrue(
                    cfg.get("sem_dado"),
                    f"{w.get('tipo')} voltou None sem marcar sem_dado",
                )
            # E nenhum valor tem de ser um 0 disfarçado de medição
            if cfg.get("sem_dado"):
                self.assertIsNone(cfg.get("valor"))


class PaginaCarimbada(TestCase):
    """Com dado real, a página tem de trazer o número E a origem."""

    def setUp(self):
        from app.models import (
            Cultura,
            LancamentoFinanceiro,
            Propriedade,
            Safra,
        )

        self.user = User.objects.create_user(username="dono2", password="x")
        self._cafe, _ = Cultura.objects.get_or_create(
            nome="Café", defaults={"grupo": "graos"}
        )
        self.prop = Propriedade.objects.create(
            user=self.user,
            nome="Fazenda Real",
            cidade="Muzambinho",
            uf="MG",
            area_total=Decimal("1200"),
        )
        self.safra = Safra.objects.create(
            propriedade=self.prop,
            cultura=self._cafe,
            ano=2025,
            safra_nome="2025/26",
            area_plantada=Decimal("1200"),
        )

    def test_widget_traz_a_fonte_e_o_numero_batem_certo(self):
        """Nada aqui tem lançamento, logo `kpi-custo` é `sem_dado`.

        Este setUp cria propriedade e safra, e só. O que o teste afirma é que
        a página diz exactamente o que tem — e o que não tem é o custo, os
        lançamentos, e a produção.
        """
        r = montar(self.user, "panorama")
        self.assertTrue(r["ok"])
        por_tipo = {w["tipo"]: w for w in r["widgets"]}

        # a área existe (area_plantada veio da safra) — logo é medida
        self.assertEqual(por_tipo["kpi-area"]["fonte_dado"], "medido")

        # o custo não: zero lançamentos. E `kpi-custo` NÃO pode dizer "medido"
        # por ser de servidor — o carimbo lê o resultado, não o catálogo.
        self.assertEqual(por_tipo["kpi-custo"]["fonte_dado"], "sem_dado")

        for w in r["widgets"]:
            self.assertIn(w["fonte_dado"], {"medido", "sem_dado", "simulado"})

    def test_nenhum_modelo_traz_widget_simulado(self):
        """O invariante que substituiu o interruptor morto.

        Havia um parâmetro `permitir_simulado` que o LLM via no schema e que
        era um `pass` no código. Nenhum modelo cita um simulado, logo ele nunca
        fez nada — e um interruptor morto oferecido a um modelo é pior do que
        nenhum: marca-se `true` a toa, gasta-se uma chamada, e a tela não muda.

        Este teste trava o facto em vez de travar a opção: se amanhã um modelo
        passar a citar um simulado, o CONTENTO muda e este teste diz. A opção
        pode voltar, mas tem de voltar a fazer alguma coisa.
        """
        from app.ia.palco import CATALOGO_IA

        for chave, m in MODELOS.items():
            for w in m["widgets"]:
                self.assertFalse(
                    (CATALOGO_IA.get(w) or {}).get("simulado"),
                    f"modelo {chave!r} cita o widget SIMULADO {w!r}; nenhum modelo "
                    f"deve, e nao ha como ligar um.",
                )

    def test_fonte_dado_reflete_o_resultado_nao_o_catalogo(self):
        """`fonte_dado` tem de ser lido do DADO.

        A versão anterior derivava do catálogo: "é de servidor? então é
        medido" — mesmo quando o cálculo tinha devolvido `{}` por falta de
        linhas. Um carimbo de proveniência que não olha para o que se está a
        carimbar não é um carimbo, é uma constante com vestido.
        """
        from app.models import Safra

        # CONTA COM SAFRA COM SAFRA E LANÇAMENTO, mas SEM PRODUÇÃO registada.
        r = montar(self.user, "cafe")
        por_tipo = {w["tipo"]: w for w in r["widgets"]}

        # kpi-area tem área (vem da safra) -> medido
        self.assertEqual(por_tipo["kpi-area"]["fonte_dado"], "medido")
        self.assertNotIn("sem_dado", por_tipo["kpi-area"].get("config") or {})

        # kpi-custo não tem lançamento -> sem_dado, e diz
        self.assertEqual(por_tipo["kpi-custo"]["fonte_dado"], "sem_dado")
        self.assertTrue(por_tipo["kpi-custo"]["config"].get("sem_dado"))

        # kpi-produtividade não tem produção -> sem_dado, e diz
        self.assertEqual(por_tipo["kpi-produtividade"]["fonte_dado"], "sem_dado")
        self.assertTrue(por_tipo["kpi-produtividade"]["config"].get("sem_dado"))

        # e nunca os dois ao mesmo tempo: um config contraditório não é
        # interpretável, e o consumidor tem de escolher em que acreditar
        for w in r["widgets"]:
            cfg = w.get("config") or {}
            if cfg.get("sem_dado"):
                self.assertEqual(
                    w["fonte_dado"], "sem_dado", f"{w['tipo']} tem sem_dado e medido"
                )
            else:
                self.assertNotEqual(w["fonte_dado"], "sem_dado")

    def test_o_que_existe_conta_a_area(self):
        """`area_total` a zero não é "área conhecida": é área por medir.

        Contá-la como pronta faria a IA dividir por zero a achar que tem
        hectares.
        """
        from app.models import Propriedade

        inv = o_que_existe(self.user)
        self.assertTrue(inv["propriedade"])
        self.assertTrue(inv["area_utilizavel"])
        self.assertFalse(inv["lancamento"])

        Propriedade.objects.filter(pk=self.prop.pk).update(area_total=Decimal("0"))
        inv2 = o_que_existe(self.user)
        self.assertTrue(inv2["propriedade"])
        self.assertFalse(inv2["area_utilizavel"], "área 0 contou como área utilizável")


class ToolDeCatalogo(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="dono3", password="x")

    def test_amplia_catalogos_responde(self):
        r = executar_catalogo(self.user, "amplia_catalogos", {})
        self.assertTrue(r["ok"])
        self.assertIn("modelos", r)
        self.assertIn("widgets", r)
        self.assertTrue(r["resumo"])

    def test_amplia_catalogos_filtra_medidos(self):
        r = executar_catalogo(self.user, "amplia_catalogos", {"apenas_medidos": True})
        self.assertFalse([w for w in r["widgets"] if w["simulado"]])

    def test_amplia_desenhar_pagina_usa_o_privilegio_da_conta(self):
        """Duas contas, dois resultados. Sem isto, um agente externo vê a
        fazenda de outro — que é o pior defeito que esta camada pode ter."""
        from app.models import (
            Cultura,
            LancamentoFinanceiro,
            Propriedade,
            Safra,
        )

        outro = User.objects.create_user(username="dono4", password="x")
        p2 = Propriedade.objects.create(
            user=outro, nome="Outra", cidade="X", uf="MG", area_total=Decimal("50")
        )
        cafe, _ = Cultura.objects.get_or_create(
            nome="Café", defaults={"grupo": "graos"}
        )
        Safra.objects.create(
            propriedade=p2,
            cultura=cafe,
            ano=2025,
            safra_nome="a",
            area_plantada=Decimal("50"),
        )
        LancamentoFinanceiro.objects.create(
            propriedade=p2,
            tipo="RECEITA",
            categoria="RECEITA",
            descricao="Venda",
            valor=Decimal("100000"),
            data="2025-01-01",
            pago=True,
            tipo_documento_lcdpr="NF",
        )

        a = executar_catalogo(self.user, "amplia_desenhar_pagina", {"modelo": "cafe"})
        b = executar_catalogo(outro, "amplia_desenhar_pagina", {"modelo": "cafe"})
        self.assertTrue(a["ok"] and b["ok"])
        self.assertFalse(a["completa"], "conta sem safra não devia estar completa")
        self.assertTrue(b["completa"])

    def test_tool_desconhecida_da_erro_sem_explodir(self):
        r = executar_catalogo(self.user, "amplia_inventar_coisas", {})
        self.assertFalse(r["ok"])
        self.assertIn("erro", r)

    def test_o_catalogo_completo_nao_levanta_sem_utilizador_valido(self):
        r = catalogo_completo()
        self.assertTrue(r["modelos"])
        self.assertTrue(r["widgets"])
