"""BUILD 5 — o esquema do palco, e sobretudo o TENANT.

A regra que este ficheiro existe para provar: o produtor A nunca vê, lista,
abre nem apaga nada do produtor B. Num sistema multi-tenant de dados
agronómicos, essa é a falha que não dá erro — dá um dashboard bonito e
errado, com a chuva do vizinho na tela do dono. Por isso os testes de tenancy
aqui não são um extra: são a razão de o `user` estar no modelo e não num `if`.
"""

from __future__ import annotations

from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.test import TestCase

from app.ia import palco
from app.models import AssinaturaPalco, PalcoIA, PresetPalco


class CatalogoTest(TestCase):
    """O que a IA pode montar. A fronteira entre 'a IA compõe' e 'a IA inventa'."""

    def test_widget_desconhecido_e_descartado(self):
        widgets, fora = palco.validar_estrutura(["kpi-custo", "widget-inventado"])
        self.assertEqual([w["tipo"] for w in widgets], ["kpi-custo"])
        self.assertTrue(any("desconhecido:widget-inventado" in d for d in fora))

    def test_inventar_widget_nao_e_fatal(self):
        """Um modelo de 1B vai inventar id. Se isso levantasse exceção, o
        produtor faria uma pergunta e levaria um traceback. Perde-se o widget
        errado; a mesa útil continua de pé."""
        widgets, _ = palco.validar_estrutura(["kpi-custo", "nao-existe", "kpi-area"])
        self.assertEqual(len(widgets), 2)

    def test_widget_repetido_vai_uma_vez_so(self):
        """Um KPI dobrado na tela parece defeito, e o produtor não sabe se é o
        motor ou a tela."""
        widgets, fora = palco.validar_estrutura(["kpi-custo", "kpi-custo"])
        self.assertEqual(len(widgets), 1)
        self.assertTrue(any("repetido" in d for d in fora))

    def test_teto_de_widgets_mantem_a_tela_legivel(self):
        """Uma mesa de operação cabe num olhar. 20 widgets são um relatório."""
        muitos = list(palco.CATALOGO_IA)[: palco.MAX_WIDGETS + 5]
        widgets, fora = palco.validar_estrutura(muitos)
        self.assertLessEqual(len(widgets), palco.MAX_WIDGETS)
        self.assertTrue(any("acima_do_teto" in d for d in fora))

    def test_aceita_lista_de_strings_ou_de_objetos(self):
        """O modelo escreve de maneiras diferentes conforme o humor. Ambas são
        legítimas."""
        a, _ = palco.validar_estrutura(["kpi-roi", {"tipo": "kpi-area"}])
        self.assertEqual(len(a), 2)

    def test_estrutura_que_nao_e_lista_nao_levanta(self):
        for ruim in (None, 42, "texto", {"nada": True}):
            widgets, fora = palco.validar_estrutura(ruim)
            self.assertEqual(widgets, [])
            self.assertTrue(fora)

    def test_config_ilegivel_nao_perde_o_widget(self):
        widgets, _ = palco.validar_estrutura([{"tipo": "kpi-custo", "config": "lixo"}])
        self.assertEqual(widgets[0]["config"], {})

    def test_layout_invalido_cai_no_padrao(self):
        self.assertEqual(palco.normalizar_layout("grid-2x3"), "grid-2x3")
        self.assertEqual(palco.normalizar_layout("inventado"), "grid-mixed")
        self.assertEqual(palco.normalizar_layout(None), "grid-mixed")


class AssinaturaTest(TestCase):
    """A tabela que treina a IA."""

    def setUp(self):
        self.ana = User.objects.create_user("ana", "a@x.com", "p")
        self.bruno = User.objects.create_user("bruno", "b@x.com", "p")

    def _assina(self, user, pergunta="Qual o histórico do talhão 2?", like=True):
        widgets, _ = palco.validar_estrutura(["kpi-custo", "chart-financeiro"])
        return AssinaturaPalco.objects.create(
            user=user,
            assinatura=palco.assinatura_do_intent(pergunta),
            intent_texto=pergunta,
            estrutura={"widgets": widgets, "layout": "grid-mixed"},
            veredito="like" if like else "dislike",
        )

    def test_perguntas_iguais_caem_na_mesma_assinatura(self):
        """É o que faz o aprendizado funcionar: o Like de uma precisa ensinar a
        próxima, mesmo que o produtor escreva de outro jeito.

        O caso do ACENTO é o que importa aqui, e é o motivo de o produto ser em
        português. "Histórico" e "historico" são a MESMA pergunta — uma é o que
        o produtor escreve com o teclado acentuado e a outra sem. Se caíssem em
        assinaturas diferentes, o Like de uma não ensinaria a outra, e o
        aprendizado pareceria funcionar em testes e não na fazenda."""
        a = palco.assinatura_do_intent("Qual o histórico do talhão 2?")
        b = palco.assinatura_do_intent("qual o historico do talhao 2")
        c = palco.assinatura_do_intent("QUAL O HISTÓRICO DO TALHÃO 2")
        self.assertEqual(a, b, "acento e caixa nao podem partir a assinatura")
        self.assertEqual(a, c)
        self.assertEqual(a, "qualohistoricodotalhao2")
        self.assertTrue(
            a.isascii(), "a assinatura nao pode levar acento: ela e a chave do treino"
        )

    def test_reformular_nao_e_a_mesma_pergunta(self):
        """Guarda contra a tentação de "melhorar" a assinatura para casar mais.

        Duas perguntas que partilham palavras mas não são a mesma têm de ter
        assinaturas diferentes. Se uma regra de normalização forçasse colisão
        aqui, o Like de uma ensinaria a estrutura errada à outra — e o produtor
        perderia confiança no aprendizado inteiro, o que é pior do que o
        aprendizado ser apenas imperfeito."""
        self.assertNotEqual(
            palco.assinatura_do_intent("custo do talhao 2 em marco"),
            palco.assinatura_do_intent("chuva do talhao 2 em marco"),
        )

    def test_perguntas_diferentes_nao_colidem(self):
        self.assertNotEqual(
            palco.assinatura_do_intent("custo do talhao 2"),
            palco.assinatura_do_intent("chuva em marco"),
        )

    def test_mesma_pergunta_so_uma_linha_por_produtor(self):
        self._assina(self.ana)
        with self.assertRaises(IntegrityError), transaction.atomic():
            self._assina(self.ana)

    def test_o_ultimo_veredito_vence(self):
        """Like e depois Dislike significa 'a IA mudou e piorou'. Com duas
        linhas, um treino ingênuo leria a antiga como exemplo positivo — e
        ensinaria justamente o que o produtor rejeitou."""
        a = self._assina(self.ana)
        a.registrar_veredito("dislike", lacuna="faltou o custo por hectare")
        a.refresh_from_db()
        self.assertEqual(a.veredito, "dislike")
        self.assertEqual(a.lacuna, "faltou o custo por hectare")
        self.assertEqual(len(a.historico), 1)
        self.assertEqual(a.historico[0]["veredito"], "like")

    def test_o_historico_nao_cresce_a_cada_toque_no_mesmo_veredito(self):
        a = self._assina(self.ana)
        a.registrar_veredito("like")
        a.registrar_veredito("like")
        a.refresh_from_db()
        self.assertEqual(len(a.historico), 0, "repetir Like não é uma mudança")

    def test_veredito_invalido_e_recusado(self):
        a = self._assina(self.ana)
        with self.assertRaises(ValueError):
            a.registrar_veredito("talvez")

    def test_apagar_o_usuario_apaga_a_assinatura(self):
        self._assina(self.ana)
        self.ana.delete()
        self.assertEqual(AssinaturaPalco.objects.count(), 0)


class TenancyTest(TestCase):
    """A razão de este ficheiro existir."""

    def setUp(self):
        self.ana = User.objects.create_user("ana", "a@x.com", "p")
        self.bruno = User.objects.create_user("bruno", "b@x.com", "p")

    def _preset(self, user, slug="custom-mesa-ana", nome="Mesa da Ana"):
        return PresetPalco.objects.create(
            user=user,
            slug=slug,
            nome=nome,
            estrutura={"widgets": [{"tipo": "kpi-custo"}], "layout": "grid-mixed"},
        )

    def test_listar_so_mostra_o_que_e_meu(self):
        self._preset(self.ana)
        self._preset(self.bruno, "custom-mesa-bruno", "Mesa do Bruno")
        meus = PresetPalco.objects.do_produtore(self.ana)
        self.assertEqual([p.slug for p in meus], ["custom-mesa-ana"])

    def test_mesmo_slug_para_dois_produtores_nao_colide(self):
        """O slug tem de ser único POR produtor. Global único faria o segundo
        produtor receber IntegrityError ao tentar dar o mesmo nome a uma mesa
        sua — e ele não tem culpa nenhuma."""
        self._preset(self.ana, "custom-custo")
        p2 = self._preset(self.bruno, "custom-custo", "Custo do Bruno")
        self.assertEqual(p2.user, self.bruno)
        self.assertEqual(PresetPalco.objects.count(), 2)

    def test_nao_consigo_apagar_a_mesa_do_vizinho(self):
        """O teste que vale mais. A queryset por produtor não acha a linha, e
        a tentativa de apagar por id não a toca."""
        alheio = self._preset(self.bruno, "custom-bruno", "Mesa do Bruno")
        alheio.delete()  # sanity: o dono apaga a dele
        self._preset(self.bruno, "custom-bruno", "Mesa do Bruno")
        self.assertEqual(PresetPalco.objects.do_produtore(self.ana).count(), 0)

    def test_busca_global_nao_esta_registrada_como_caminho_padrao(self):
        """`objects` é o `PalcoQuerySet`, que só sabe filtrar por produtor. Não
        existe atalho 'me dá tudo' — é deliberado."""
        qs = PresetPalco.objects.all()
        self.assertTrue(hasattr(qs, "do_produtore"))

    def test_a_mesa_do_produtor_nao_sobrevive_a_ele(self):
        self._preset(self.ana)
        self.ana.delete()
        self.assertEqual(PresetPalco.objects.count(), 0)


class PalcoUnicoTest(TestCase):
    """O palco é um singleton, e quem garante é o slug UNIQUE — não o
    `kind='palco'`, que uma segunda linha também satisfaz.

    O `setUp` cria a linha, e não confia que ela já exista. É porque
    `config.settings.test` põe `MIGRATION_MODULES = DisableMigrations()`: em
    teste, NENHUMA migração corre — e a que cria a linha é uma migração de
    DADOS (`0054_palco_ia_build5.RunPython`). Sem este `setUp`, estes testes
    mediam uma coisa que o ambiente de teste apaga de propósito, e passavam a
    falhar no dia em que alguém os correu a sério.

    O que fica por verificar, e é o que interessa: a migração existe e cria a
    linha. Isso é `makemigrations --check` e a migração em si, e é um teste
    diferente deste.
    """

    def setUp(self):
        super().setUp()
        # Espelha `criar_palco` em 0054_palco_ia_build5.py. Se a migração
        # mudar, este tem de mudar com ela — daí o comentário apontar para
        # o ficheiro em vez de repetir o motivo em silêncio.
        PalcoIA.objects.get_or_create(
            slug=palco.SLUG_PALCO,
            defaults={
                "nome": "Amplia",
                "kind": "palco",
                "ativo": True,
                "structure": {},
            },
        )

    def test_o_palco_existe_e_nao_tem_dono(self):
        p = PalcoIA.objects.get(slug=palco.SLUG_PALCO)
        self.assertTrue(p.ativo)
        self.assertEqual(
            p.structure,
            {},
            "o palco nao guarda widgets: a mesa e do produtor, nao do palco",
        )

    def test_o_palco_e_unico_por_slug(self):
        """O singleton NAO é garantido por check constraint: um `kind='palco'`
        é satisfeito por uma segunda linha, e passava. Quem garante é o slug
        UNIQUE. A alternativa — um `get_or_create` em cada request — é a
        origem clássica de duas linhas e de um 500 em produção."""
        self.assertEqual(PalcoIA.objects.filter(slug=palco.SLUG_PALCO).count(), 1)
        with self.assertRaises(IntegrityError), transaction.atomic():
            PalcoIA.objects.create(slug=palco.SLUG_PALCO, kind="palco")

    def test_kind_nao_pode_ser_inventado(self):
        """O registo não se pode meter num `kind` que o código não conhece e
        desaparecer sem ninguém perceber."""
        with self.assertRaises(IntegrityError), transaction.atomic():
            PalcoIA.objects.create(slug="amplia-3", kind="inventado")


class PresetSistemaTest(TestCase):
    """O palco e' um preset de SISTEMA, e a validacao tinha-o a apagar.

    `preset_permitido` existia para apanhar presets fantasma. Com a regra
    "so `custom-` passa", ela apagava o preset principal da BUILD 5 — o
    produtor nao tinha palco nenhum para onde olhar, e nao havia erro nenhum a
    dizer porquê.
    """

    def test_o_palco_passa_a_validacao(self):
        from app.presets import preset_permitido

        self.assertTrue(preset_permitido("amplia"), "o palco sumia do menu")

    def test_um_custom_continua_a_passar(self):
        from app.presets import preset_permitido

        self.assertTrue(preset_permitido("custom-custo-do-talhao-2"))

    def test_um_fantasma_continua_bloqueado(self):
        from app.presets import preset_permitido

        for nome in ("visao-geral", "custom-plantio", "executivo", ""):
            self.assertFalse(preset_permitido(nome), nome)

    def test_amplia_nao_vira_preset_de_produtor(self):
        """Ser de sistema nao é ser do produtor. O menu lista os dois, e a
        distincao é o que impede o 'Apagar' de derrubar o palco da IA."""
        from app.presets import PREFIXO_PERMITIDO, PRESETS_SISTEMA

        self.assertIn("amplia", PRESETS_SISTEMA)
        self.assertFalse("amplia".startswith(PREFIXO_PERMITIDO))

    def test_a_limpeza_do_estado_preserva_o_palco(self):
        from app.presets import limpar_presets_bloqueados

        state = {
            "presets": {
                "amplia": {"widgets": []},
                "custom-custo": {},
                "visao-geral": {},
            },
            "presets_order": ["amplia", "custom-custo", "visao-geral"],
            "active_preset": "amplia",
        }
        limpo, removidos = limpar_presets_bloqueados(state)
        self.assertIn("amplia", limpo["presets"])
        self.assertIn("amplia", limpo["presets_order"])
        self.assertEqual(limpo["active_preset"], "amplia")
        self.assertIn("visao-geral", removidos)
        self.assertNotIn("amplia", removidos)


class GeometriaTest(TestCase):
    """A geometria que a IA pede por widget, e o que acontece quando ela erra.

    A grade do dashboard é de 64 colunas. Antes disto o layout era uma escolha
    de 4 strings e a IA não tinha onde dizer "este widget é 20 de largura na
    linha 20" — logo não havia como mover nem redimensionar nada.

    O ponto destes testes não é a geometria válida: é o que acontece com a
    geometria INVÁLIDA. Um 1B manda `gridW: 900`. A resposta correta não é erro
    500 — é descartar a geometria daquele widget e deixar o layout automático,
    porque um widget com geometria má estraga a mesa, enquanto um widget sem
    geometria é apenas um widget sem posição.
    """

    def test_nao_asked_returns_none(self):
        """Não pedir geometria é o caso comum, e não pode levantar nada."""
        self.assertIsNone(palco.normalizar_geometria({}))
        self.assertIsNone(palco.normalizar_geometria(None))
        self.assertIsNone(palco.normalizar_geometria([1, 2, 3]))
        self.assertIsNone(palco.normalizar_geometria("grid-mixed"))

    def test_completa_e_valida(self):
        self.assertEqual(
            palco.normalizar_geometria(
                {"gridX": 0, "gridY": 20, "gridW": 20, "gridH": 12}
            ),
            {"gridX": 0, "gridY": 20, "gridW": 20, "gridH": 12},
        )

    def test_aceita_string_numerica(self):
        """O modelo manda tudo como string. Isso é formato, não erro."""
        self.assertEqual(
            palco.normalizar_geometria(
                {"gridX": "10", "gridY": "0", "gridW": "20", "gridH": "12"}
            ),
            {"gridX": 10, "gridY": 0, "gridW": 20, "gridH": 12},
        )

    def test_incompleta_nao_e_adivinhada(self):
        """Só gridW, sem gridX. Adivinhar a posição seria inventar onde o
        produtor quer o gráfico — e inventar posição é pior que não ter."""
        self.assertIsNone(palco.normalizar_geometria({"gridW": 20}))
        self.assertIsNone(palco.normalizar_geometria({"gridH": 12}))

    def test_transbordo_da_grade(self):
        """45 + 20 = 65 numa grade de 64. Uma coluna a mais já é transbordo."""
        self.assertIsNone(
            palco.normalizar_geometria(
                {"gridX": 45, "gridY": 0, "gridW": 20, "gridH": 8}
            )
        )

    def test_fronteira_exata_aceita(self):
        """44 + 20 = 64. O limite é incluído: cortar a largura que o produtor
        pediu seria mudar a mesa dele."""
        self.assertEqual(
            palco.normalizar_geometria(
                {"gridX": 44, "gridY": 0, "gridW": 20, "gridH": 8}
            ),
            {"gridX": 44, "gridY": 0, "gridW": 20, "gridH": 8},
        )

    def test_loucura_do_modelo_cai_no_automatico(self):
        for geo in (
            {"gridX": -40, "gridY": 0, "gridW": 10, "gridH": 8},
            {"gridX": 0, "gridY": 0, "gridW": 900, "gridH": 8},
            {"gridX": 0, "gridY": 0, "gridW": 1, "gridH": 8},
            {"gridX": "abc", "gridY": 0, "gridW": 10, "gridH": 8},
        ):
            with self.subTest(geo=geo):
                self.assertIsNone(palco.normalizar_geometria(geo))

    def test_bool_nao_vira_numero(self):
        """`bool` é subclasse de `int` em Python: True viraria 1 e passaria na
        validação. Quem mandou `true` não está descrevendo geometria."""
        self.assertIsNone(
            palco.normalizar_geometria(
                {"gridX": True, "gridY": 0, "gridW": 10, "gridH": 8}
            )
        )

    def test_geometria_chega_no_widget_validado(self):
        """O caminho completo: a geometria que o modelo mandou aparece no
        config do widget, que é onde o renderizador do dashboard já lê
        (index.html usa config.gridX / config.gridW)."""
        widgets, descartados = palco.validar_estrutura(
            [
                {
                    "tipo": "kpi-custo",
                    "titulo": "Custo",
                    "geom": {"gridX": 4, "gridY": 0, "gridW": 20, "gridH": 8},
                }
            ]
        )
        self.assertEqual(len(widgets), 1)
        self.assertEqual(widgets[0]["config"]["gridX"], 4)
        self.assertEqual(widgets[0]["config"]["gridW"], 20)
        self.assertEqual(descartados, [])

    def test_widget_sem_geometria_continua_valendo(self):
        """O caso comum: sem geometria, o widget entra do mesmo jeito. A
        validação nova não pode fazer o palco parar de funcionar para quem
        não usa a feature."""
        widgets, descartados = palco.validar_estrutura(
            [{"tipo": "kpi-custo", "titulo": "Custo"}]
        )
        self.assertEqual(len(widgets), 1)
        self.assertNotIn("gridX", widgets[0]["config"])
        self.assertEqual(descartados, [])

    def test_geometria_louca_nao_derruba_o_widget(self):
        """A regra do 1B: o que é inválido é DESCARTADO, e a mesa é montada
        com o resto — em vez de dar 500 na pergunta mais importante."""
        widgets, descartados = palco.validar_estrutura(
            [
                {
                    "tipo": "kpi-custo",
                    "titulo": "Custo",
                    "geom": {"gridX": 0, "gridY": 0, "gridW": 9999, "gridH": 8},
                },
                {"tipo": "chart-safras", "titulo": "Safras"},
            ]
        )
        # os dois sobrevivem: a geometria má virou "sem geometria"
        self.assertEqual(len(widgets), 2)
        self.assertNotIn("gridX", widgets[0]["config"])
        self.assertEqual(widgets[1]["tipo"], "chart-safras")
        self.assertEqual(descartados, [])


class PatchParcialTest(TestCase):
    """aplicar_operacoes: o que o palco.edit aplica, e o que ele descarta.

    render_preset SUBSTITUI a mesa inteira. Isto é o que torna a edição
    impossível — não há como dizer "só mexe neste". aplicar_operacoes é a peça
    que falta: recebe a lista atual e um patch, devolve a lista nova.

    A regra é a mesma do validar_estrutura, aplicada ao patch: operação
    inválida é DESCARTADA, as válidas aplicam, e nunca 500. Um 1B vai errar o
    formato — e o erro tem que virar motivo em `descartados`, não traceback.
    """

    def _mesa(self):
        return [
            {"tipo": "kpi-custo", "titulo": "Custo", "config": {}},
            {"tipo": "kpi-caixa", "titulo": "Caixa", "config": {}},
        ]

    def test_add_valido(self):
        novos, desc = palco.aplicar_operacoes(
            self._mesa(),
            [{"op": "add", "widget": {"tipo": "kpi-roi", "titulo": "ROI"}}],
        )
        self.assertEqual(len(novos), 3)
        self.assertEqual(novos[2]["tipo"], "kpi-roi")
        self.assertEqual(desc, [])

    def test_add_inventado_nao_entra(self):
        novos, desc = palco.aplicar_operacoes(
            self._mesa(),
            [{"op": "add", "widget": {"tipo": "kpi-inventado"}}],
        )
        self.assertEqual(len(novos), 2)
        self.assertTrue(any("add:" in d for d in desc))

    def test_add_duplicado_nao_entra(self):
        novos, desc = palco.aplicar_operacoes(
            self._mesa(),
            [{"op": "add", "widget": {"tipo": "kpi-custo"}}],
        )
        self.assertEqual(len(novos), 2)
        self.assertIn("add:repetido:kpi-custo", desc)

    def test_remove(self):
        novos, desc = palco.aplicar_operacoes(
            self._mesa(), [{"op": "remove", "tipo": "kpi-custo"}]
        )
        self.assertEqual(len(novos), 1)
        self.assertEqual(novos[0]["tipo"], "kpi-caixa")
        self.assertEqual(desc, [])

    def test_remove_inexistente_e_motivo(self):
        novos, desc = palco.aplicar_operacoes(
            self._mesa(), [{"op": "remove", "tipo": "kpi-roi"}]
        )
        self.assertEqual(len(novos), 2)
        self.assertIn("remove:nao_encontrado:kpi-roi", desc)

    def test_move_grava_geometria(self):
        novos, desc = palco.aplicar_operacoes(
            self._mesa(),
            [
                {
                    "op": "move",
                    "tipo": "kpi-custo",
                    "geom": {"gridX": 4, "gridY": 0, "gridW": 20, "gridH": 8},
                }
            ],
        )
        self.assertEqual(novos[0]["config"]["gridX"], 4)
        self.assertEqual(novos[0]["config"]["gridW"], 20)
        self.assertEqual(desc, [])

    def test_resize_grava_geometria(self):
        novos, desc = palco.aplicar_operacoes(
            self._mesa(),
            [
                {
                    "op": "resize",
                    "tipo": "kpi-caixa",
                    "geom": {"gridX": 0, "gridY": 0, "gridW": 32, "gridH": 12},
                }
            ],
        )
        self.assertEqual(novos[1]["config"]["gridW"], 32)
        self.assertEqual(desc, [])

    def test_move_com_geometria_louca_e_descartado(self):
        novos, desc = palco.aplicar_operacoes(
            self._mesa(),
            [
                {
                    "op": "move",
                    "tipo": "kpi-custo",
                    "geom": {"gridX": 0, "gridY": 0, "gridW": 9999, "gridH": 8},
                }
            ],
        )
        self.assertNotIn("gridX", novos[0]["config"])
        self.assertIn("move:geometria_invalida:kpi-custo", desc)

    def test_operacao_desconhecida(self):
        novos, desc = palco.aplicar_operacoes(
            self._mesa(), [{"op": "explodir", "tipo": "kpi-custo"}]
        )
        self.assertEqual(len(novos), 2)
        self.assertIn("op_desconhecida:explodir", desc)

    def test_nao_muta_a_lista_do_chamador(self):
        mesa = self._mesa()
        palco.aplicar_operacoes(mesa, [{"op": "remove", "tipo": "kpi-custo"}])
        self.assertEqual(len(mesa), 2)

    def test_operacoes_nao_lista(self):
        novos, desc = palco.aplicar_operacoes(self._mesa(), "nao-e-lista")
        self.assertEqual(len(novos), 2)
        self.assertEqual(desc, ["operacoes_nao_lista"])

    def test_patch_misto_aplica_validas_e_descarta_invalidas(self):
        """A regra do 1B, no patch: o que é inválido é descartado, o que é
        válido aplica, e a mesa segue — em vez de dar 500."""
        novos, desc = palco.aplicar_operacoes(
            self._mesa(),
            [
                {"op": "add", "widget": {"tipo": "kpi-roi"}},
                {"op": "remove", "tipo": "kpi-caixa"},
                {
                    "op": "move",
                    "tipo": "kpi-custo",
                    "geom": {"gridX": 0, "gridY": 0, "gridW": 9999, "gridH": 8},
                },
                {"op": "explodir"},
            ],
        )
        tipos = [w["tipo"] for w in novos]
        self.assertEqual(tipos, ["kpi-custo", "kpi-roi"])
        self.assertEqual(len(desc), 2)  # move inválido + op desconhecida


class EditarPresetTest(TestCase):
    """h_editar_preset: a IA edita uma mesa salva, não redesenhá-la.

    render_preset SUBSTITUI a mesa inteira. Este handler aplica um PATCH
    PARCIAL sobre a mesa que já existe, e persiste só se algo mudou de verdade.
    """

    def setUp(self):
        from app.models import PresetPalco

        self.user = User.objects.create_user("dono", password="x")
        self.preset = PresetPalco.objects.create(
            user=self.user,
            slug="custom-minha",
            nome="Minha",
            estrutura={
                "widgets": [{"tipo": "kpi-custo", "titulo": "Custo", "config": {}}],
                "layout": "grid-mixed",
            },
        )

    def test_move_valido_persiste(self):
        from app.ia.intents import h_editar_preset

        r = h_editar_preset(
            self.user,
            {
                "slug": "custom-minha",
                "operacoes": [
                    {
                        "op": "move",
                        "tipo": "kpi-custo",
                        "geom": {"gridX": 4, "gridY": 0, "gridW": 20, "gridH": 8},
                    }
                ],
            },
            {},
        )
        self.assertTrue(r["ok"])
        self.assertTrue(r["dados"]["alterou"])
        self.assertEqual(r["dados"]["widgets"][0]["config"]["gridX"], 4)
        # persistiu de verdade
        self.preset.refresh_from_db()
        self.assertEqual(self.preset.estrutura["widgets"][0]["config"]["gridX"], 4)

    def test_add_inventado_nao_altera(self):
        from app.ia.intents import h_editar_preset

        r = h_editar_preset(
            self.user,
            {
                "slug": "custom-minha",
                "operacoes": [{"op": "add", "widget": {"tipo": "kpi-inventado"}}],
            },
            {},
        )
        self.assertTrue(r["ok"])
        self.assertFalse(r["dados"]["alterou"])
        self.assertTrue(any("add:" in d for d in r["dados"]["descartados"]))

    def test_slug_de_outro_usuario_nao_encontrado(self):
        from app.ia.intents import h_editar_preset

        outro = User.objects.create_user("outro", password="x")
        r = h_editar_preset(outro, {"slug": "custom-minha", "operacoes": []}, {})
        self.assertFalse(r["ok"])
        self.assertIn("não encontrado", r["erro"])

    def test_patch_so_invalido_nao_reescreve(self):
        from app.ia.intents import h_editar_preset

        antes = self.preset.estrutura
        r = h_editar_preset(
            self.user,
            {"slug": "custom-minha", "operacoes": [{"op": "explodir"}]},
            {},
        )
        self.assertTrue(r["ok"])
        self.assertFalse(r["dados"]["alterou"])
        self.preset.refresh_from_db()
        self.assertEqual(self.preset.estrutura, antes)

    def test_sem_slug_e_erro(self):
        from app.ia.intents import h_editar_preset

        r = h_editar_preset(self.user, {"operacoes": []}, {})
        self.assertFalse(r["ok"])
        self.assertIn("slug", r["erro"])
