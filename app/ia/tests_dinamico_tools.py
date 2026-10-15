"""
Testes da BUILD 2: as Tools Divinas.

O invariante central, e o unico que realmente importa aqui:

    um campo que o modelo INVENTOU nunca chega ao banco, e o modelo recebe
    um erro que permite corrigir.

O segundo invariante, tão grave quanto o primeiro:

    dois produtores com o mesmo slug nao enxergam um ao outro. `slug` tem
    unique constraint em `(user, slug)`, NAO global — dois usuarios podem ter
    `slug="geladeira"` ao mesmo tempo. Logo, resolver por slug SEM dono é
    vazamento, e é a armadilha mais óbvia desta camada.

O terceiro: a Criação de ferramenta é ESCRITA, e escrita pede confirmação.
"""

import json

from django.contrib.auth.models import User
from django.test import TestCase

from app.ia import dinamico_intents as di
from app.models import DynamicApp, DynamicRecord

CAMPOS_GELADEIRA = [
    {"rotulo": "Alimento", "tipo": "TEXTO", "obrigatorio": True},
    {"rotulo": "Quantidade kg", "tipo": "DECIMAL", "obrigatorio": False},
]


def _criar(user, nome, campos=None, confirm=True, **extra):
    p = {"nome": nome, "campos": campos or CAMPOS_GELADEIRA}
    p.update(extra)
    if confirm:
        p["confirm"] = True
    return di.h_criar_entidade(user, p, {})


def _gravar(user, slug, dados, confirm=True):
    p = {"entity_slug": slug, "dados": dados}
    if confirm:
        p["confirm"] = True
    return di.h_inserir_registro(user, p, {})


class CriarEntidadeTest(TestCase):
    def setUp(self):
        self.u = User.objects.create_user("ana", "a@x.com", "p")

    def test_cria_ferramenta_com_slug_derivado(self):
        r = _criar(self.u, "Controle de Geladeira")
        self.assertTrue(r["ok"], r)
        self.assertIn("controle-de-geladeira", r["resposta"])
        self.assertEqual(r["dados"]["estado"], "PRONTO")
        self.assertEqual(DynamicApp.objects.filter(user=self.u).count(), 1)

    def test_escrita_pede_confirmacao(self):
        """Criar schema é decisão do produtor, não efeito colateral de conversa.

        Sem confirmação, uma alucinação do modelo ("crie uma ferramenta de
        impostos") materializaria estrutura na conta do produtor sem ele ter
        visto nada.
        """
        r = _criar(self.u, "Controle de Geladeira", confirm=False)
        self.assertTrue(r["ok"], r)
        self.assertTrue(r["needs_confirm"])
        self.assertEqual(
            DynamicApp.objects.filter(user=self.u).count(), 0, "não grava sem confirm"
        )

    def test_tipo_invalido_recusa_antes_de_pedir_confirmacao(self):
        """Perguntar "cria esta?" para algo que não pode ser criado desperdiça a
        única coisa que o produtor faz de atenção aqui."""
        r = di.h_criar_entidade(
            self.u,
            {
                "nome": "X",
                "campos": [{"rotulo": "Idade", "tipo": "VARCHAR_MYSQL"}],
                "confirm": True,
            },
            {},
        )
        self.assertFalse(r["ok"])
        self.assertIn("VARCHAR_MYSQL", r["erro"])
        self.assertIn("TEXTO", r["erro"], "a mensagem lista os tipos aceitos")
        self.assertEqual(DynamicApp.objects.filter(user=self.u).count(), 0)

    def test_opcoes_sem_lista_recusa(self):
        r = di.h_criar_entidade(
            self.u,
            {
                "nome": "X",
                "campos": [{"rotulo": "Estado", "tipo": "OPCOES"}],
                "confirm": True,
            },
            {},
        )
        self.assertFalse(r["ok"])
        self.assertIn("opcoes", r["erro"])

    def test_excede_teto_de_campos_recusa(self):
        """20 é o teto pelo prompt do SmolLM2 (4096 tokens) e pelo que um modelo
        de 1.7B consegue planejar de fato."""
        muitos = [
            {"rotulo": f"C{i}", "tipo": "TEXTO"} for i in range(di.MAX_CAMPOS + 1)
        ]
        r = di.h_criar_entidade(
            self.u, {"nome": "X", "campos": muitos, "confirm": True}, {}
        )
        self.assertFalse(r["ok"])
        self.assertIn(str(di.MAX_CAMPOS), r["erro"])

    def test_schema_como_string_json_e_aceito(self):
        """Um modelo pequeno naturalmente produz JSON como texto. Recusar por
        formato, com o conteúdo certo, desperdiça a chance de a tool funcionar."""
        r = di.h_criar_entidade(
            self.u,
            {
                "nome": "Teste String",
                "campos": json.dumps(CAMPOS_GELADEIRA),
                "confirm": True,
            },
            {},
        )
        self.assertTrue(r["ok"], r)

    def test_resposta_lista_os_campos_para_o_modelo_se_corrigir(self):
        r = _criar(self.u, "Controle de Geladeira")
        self.assertIn("alimento", r["resposta"])
        self.assertIn("quantidade_kg", r["resposta"])


class AlucinacaoDeChaveTest(TestCase):
    """O invariante central da BUILD 2."""

    def setUp(self):
        self.u = User.objects.create_user("ana", "a@x.com", "p")
        self.slug = _criar(self.u, "Controle de Geladeira")["dados"]["slug"]

    def test_campo_inventado_recusa_e_nao_grava(self):
        """O exemplo do enunciado: `idade_da_vaca` numa ferramenta sem esse campo.

        Recusar e dizer o nome é a diferença entre o produtor descobrir o erro
        e o produtor não descobrir nunca.
        """
        r = _gravar(self.u, self.slug, {"alimento": "Ração", "idade_da_vaca": 10})
        self.assertFalse(r["ok"], "campo alucinado nao pode ser aceito")
        self.assertIn("idade_da_vaca", r["erro"])
        self.assertEqual(DynamicRecord.objects.filter(user=self.u).count(), 0)

    def test_erro_lista_as_chaves_validas_para_o_modelo_corrigir(self):
        """Sem o nome do campo válido, o modelo não tem como se corrigir — e um
        modelo que não se corrige repete o erro em cada registro."""
        r = _gravar(self.u, self.slug, {"alimento": "X", "idade_da_vaca": 10})
        self.assertIn("alimento", r["erro"])
        self.assertIn("quantidade_kg", r["erro"])
        self.assertEqual(r["dados"]["campos_validos"], ["alimento", "quantidade_kg"])

    def test_recusa_eh_atomica_nao_grava_o_campo_bom(self):
        _gravar(self.u, self.slug, {"alimento": "Ração A"})
        _gravar(self.u, self.slug, {"alimento": "Ração B", "inventado": 1})
        dados = set(
            DynamicRecord.objects.filter(user=self.u).values_list(
                "dados__alimento", flat=True
            )
        )
        self.assertEqual(
            dados, {"Ração A"}, "o registro com campo alucinado nao pode existir"
        )

    def test_corrigir_e_gravar(self):
        """O ciclo completo: erro -> o modelo corrige -> grava. É o que prova que
        a defesa é utilizável e não só um portão."""
        primeira = _gravar(self.u, self.slug, {"alimento": "X", "idade_da_vaca": 10})
        self.assertFalse(primeira["ok"])

        validos = primeira["dados"]["campos_validos"]
        segunda = _gravar(self.u, self.slug, {"alimento": "Ração", validos[1]: 12})
        self.assertTrue(segunda["ok"], segunda.get("erro"))
        self.assertEqual(DynamicRecord.objects.filter(user=self.u).count(), 1)

    def test_campo_obrigatorio_ausente_recusa(self):
        r = _gravar(self.u, self.slug, {"quantidade_kg": 5})
        self.assertFalse(r["ok"])
        self.assertIn("alimento", r["erro"])

    def test_valor_de_tipo_errado_recusa(self):
        r = _gravar(self.u, self.slug, {"alimento": "X", "quantidade_kg": "muito"})
        self.assertFalse(r["ok"])

    def test_confirmacao_vem_apos_validar(self):
        """Perguntar confirmação para um payload que será recusado faz o produtor
        confirmar algo que não vai acontecer, e ensina o modelo a reter sem
        aprender nada."""
        r = _gravar(self.u, self.slug, {"alimento": "X", "inventado": 1}, confirm=False)
        self.assertFalse(r["ok"], "payload invalido nao chega a pedir confirmacao")
        self.assertNotIn("needs_confirm", r)

    def test_escrita_valida_pede_confirmacao(self):
        r = _gravar(self.u, self.slug, {"alimento": "Ração"}, confirm=False)
        self.assertTrue(r["ok"])
        self.assertTrue(r["needs_confirm"])
        self.assertEqual(DynamicRecord.objects.filter(user=self.u).count(), 0)


class TenancyTest(TestCase):
    """`slug` e' unico por (user, slug), nao global. A resolucao SEMPRE leva o
    dono no filtro — sem isso, `filter(slug=X).first()` acha a tool do outro."""

    def setUp(self):
        self.ana = User.objects.create_user("ana", "a@x.com", "p")
        self.bob = User.objects.create_user("bob", "b@x.com", "p")
        # MESMO nome nos dois: slugs iguais, constraint permite
        self.slug_ana = _criar(self.ana, "Controle de Geladeira")["dados"]["slug"]
        self.slug_bob = _criar(self.bob, "Controle de Geladeira")["dados"]["slug"]
        _gravar(self.ana, self.slug_ana, {"alimento": "Ração da Ana"})

    def test_slug_colide_entre_usuarios(self):
        """Premissa do teste: se isto deixar de ser verdade, o resto deste
        arquivo deixa de testar o que diz testar."""
        self.assertEqual(self.slug_ana, self.slug_bob)

    def test_leitura_nao_enxerga_a_tool_do_outro(self):
        r = di.h_consultar_registros(self.bob, {"entity_slug": self.slug_bob}, {})
        self.assertTrue(r["ok"])
        self.assertNotIn("Ração da Ana", r["resposta"])
        self.assertEqual(r["dados"]["total"], 0)

    def test_insert_com_slug_que_so_existe_para_outro_recusa(self):
        """A sonda real da resolução sem dono.

        Ana cria "Registro de Vacinas" (slug `registro-de-vacinas`). Bob NUNCA
        criou nada com esse nome. Se a resolução fosse `filter(slug=X).first()`
        sem o `user`, ela acharia a ferramenta de Ana e Bob gravaria nela.
        Como `slug` tem unique constraint só em `(user, slug)`, esse é
        exatamente o cenário em que o bug apareceria.
        """
        slug_so_ana = _criar(
            self.ana,
            "Registro de Vacinas",
            campos=[{"rotulo": "Vacina", "tipo": "TEXTO"}],
        )["dados"]["slug"]
        self.assertFalse(
            DynamicApp.objects.filter(user=self.bob, slug=slug_so_ana).exists(),
            "premissa do teste: o slug nao pode existir para Bob",
        )

        r = _gravar(self.bob, slug_so_ana, {"vacina": "Raiva"})
        self.assertFalse(r["ok"], "nao pode gravar na ferramenta de outro usuario")
        self.assertIn("nao encontrada", r["erro"])
        self.assertEqual(DynamicRecord.objects.filter(app__slug=slug_so_ana).count(), 0)

    def test_slug_compartilhado_resolve_para_a_ferramenta_propria(self):
        """O complemento do anterior: com slug IGUAL, cada um chega na SUA.

        Aqui o insert de Bob tem sucesso — e está certo. A falha aqui seria
         confundir "achou a ferramenta errada" com "achou a ferramenta
        certa do usuario errado", e a segunda é a segurança funcionando.
        """
        r = _gravar(self.bob, self.slug_bob, {"alimento": "Ração do Bob"})
        self.assertTrue(r["ok"], r.get("erro"))
        alvos = set(
            DynamicRecord.objects.filter(
                dados__alimento__in=["Ração da Ana", "Ração do Bob"]
            ).values_list("user_id", flat=True)
        )
        self.assertEqual(len(alvos), 2, "cada um gravou na SUA ferramenta")

    def test_erro_de_nao_encontrado_lista_as_tools_do_proprio_usuario(self):
        """A pista que permite corrigir em uma segunda chamada."""
        slug_so_ana = _criar(
            self.ana,
            "Registro de Vacinas",
            campos=[{"rotulo": "Vacina", "tipo": "TEXTO"}],
        )["dados"]["slug"]
        r = _gravar(self.bob, slug_so_ana, {"vacina": "X"})
        self.assertFalse(r["ok"])
        self.assertIn(
            self.slug_bob,
            r["erro"],
            "deve listar as ferramentas DO USUARIO, e nao as do outro",
        )
        self.assertNotIn(slug_so_ana, r["erro"], "nao pode vazar o nome da tool alheia")

    def test_erro_de_nao_encontrado_diz_para_criar_primeiro(self):
        vazio = User.objects.create_user("carla", "c@x.com", "p")
        r = _gravar(vazio, "qualquer-coisa", {"a": 1})
        self.assertFalse(r["ok"])
        self.assertIn("create_entity", r["erro"])

    def test_usuario_anonimo_e_negado(self):
        from django.contrib.auth.models import AnonymousUser

        r = di.h_consultar_registros(
            AnonymousUser(), {"entity_slug": self.slug_ana}, {}
        )
        self.assertFalse(r["ok"])

    def test_slug_numeric_aponta_para_id_alheio_recusado(self):
        """Aceitar id numérico cria a tentação de `filter(pk=...)` sem dono.

        `resolver_app` compõe `user` E `pk` no mesmo filter; com o id da
        ferramenta de Ana, a busca por Bob não acha nada.
        """
        app_ana = DynamicApp.objects.get(user=self.ana, slug=self.slug_ana)
        r = _gravar(self.bob, str(app_ana.pk), {"alimento": "X"})
        self.assertFalse(r["ok"], "id de ferramenta alheia nao pode ser usado")
        self.assertEqual(DynamicRecord.objects.filter(user=self.ana).count(), 1)


class ConsultarRegistrosTest(TestCase):
    def setUp(self):
        self.u = User.objects.create_user("ana", "a@x.com", "p")
        self.slug = _criar(self.u, "Controle de Geladeira")["dados"]["slug"]
        _gravar(self.u, self.slug, {"alimento": "Ração", "quantidade_kg": 10})
        _gravar(self.u, self.slug, {"alimento": "Sal", "quantidade_kg": 2})

    def test_le_todos(self):
        r = di.h_consultar_registros(self.u, {"entity_slug": self.slug}, {})
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["dados"]["total"], 2)

    def test_filtro_valido_filtra(self):
        r = di.h_consultar_registros(
            self.u, {"entity_slug": self.slug, "filtros": {"alimento": "Sal"}}, {}
        )
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["dados"]["total"], 1)
        self.assertNotIn("Ração,", r["resposta"])

    def test_filtro_com_chave_alucinada_recusa_em_vez_de_devolver_vazio(self):
        """O ponto não-óbvio. `dados__<chave>` com chave inventada devolve VAZIO, e
        vazio é indistinguível de "não existe esse dado". O modelo leria "0
        registros" e concluiria que o produtor não tem ração — quando o que
        houve foi ele ter errado o nome do campo."""
        r = di.h_consultar_registros(
            self.u, {"entity_slug": self.slug, "filtros": {"idade_da_vaca": 3}}, {}
        )
        self.assertFalse(r["ok"], "filtro invalido nao pode virar lista vazia")
        self.assertIn("idade_da_vaca", r["erro"])
        self.assertIn("alimento", r["erro"], "deve listar os campos filtráveis")

    def test_filtro_vazio_recusa_com_instrucao(self):
        r = di.h_consultar_registros(
            self.u, {"entity_slug": self.slug, "filtros": {"alimento": ""}}, {}
        )
        self.assertFalse(r["ok"])
        self.assertIn("Omita a chave", r["erro"])

    def test_limite_e_respeitado(self):
        r = di.h_consultar_registros(
            self.u, {"entity_slug": self.slug, "limite": 9999}, {}
        )
        self.assertTrue(r["ok"])
        self.assertLessEqual(r["dados"]["total"], di.MAX_RESULTADOS)

    def test_leitura_nao_exige_confirmacao(self):
        r = di.h_consultar_registros(self.u, {"entity_slug": self.slug}, {})
        self.assertNotIn("needs_confirm", r)

    def test_resposta_trunca_valor_longo(self):
        """Resposta de leitura vai para o prompt do modelo. Um valor de 2000
        caracteres estoura a janela e derruba a resposta inteira."""
        _gravar(self.u, self.slug, {"alimento": "X" * 3000})
        r = di.h_consultar_registros(
            self.u, {"entity_slug": self.slug, "limite": 5}, {}
        )
        self.assertTrue(r["ok"])
        for linha in r["resposta"].split("\n"):
            self.assertLess(
                len(linha), 400, "linha de resposta longa demais para o prompt"
            )


class PublicoDasToolsTest(TestCase):
    """As tools precisam estar expostas, com o schema certo e a flag certa."""

    def setUp(self):
        from app.amplia_mcp import catalogo_tools

        self.cat = {t["name"]: t for t in catalogo_tools()}

    def test_as_tres_estao_no_catalogo(self):
        for nome in (
            "amplia_criar_entidade",
            "amplia_inserir_registro",
            "amplia_consultar_registros",
        ):
            self.assertIn(nome, self.cat)

    def test_escritas_sao_marcadas_como_escrita(self):
        """A flag é o que o sandbox consulta. Se `criar_entidade` aparecesse como
        somente-leitura, ela escaparia da confirmação."""
        for nome in ("amplia_criar_entidade", "amplia_inserir_registro"):
            self.assertFalse(self.cat[nome]["x-read-only"], nome)
        self.assertTrue(self.cat["amplia_consultar_registros"]["x-read-only"])

    def test_declaram_os_parametros(self):
        """0 de 68 tools declaravam properties. Estas três declaram, porque a
        primeira camada da defesa contra alucinação é o modelo saber o nome
        exato do parâmetro."""
        self.assertIn(
            "campos", self.cat["amplia_criar_entidade"]["inputSchema"]["properties"]
        )
        self.assertIn(
            "dados", self.cat["amplia_inserir_registro"]["inputSchema"]["properties"]
        )
        self.assertIn(
            "entity_slug",
            self.cat["amplia_consultar_registros"]["inputSchema"]["properties"],
        )

    def test_descricao_diz_para_nao_inventar_campo(self):
        """A descricao da tool e o prompt do modelo. Se ela nao disser "nao
        invente o nome do campo", o modelo nao tem instrucao de primeira linha."""
        desc = self.cat["amplia_inserir_registro"]["description"].lower()
        self.assertIn("nunca invente", desc)
        self.assertIn("recusa", desc, "a descricao avisa que a gravacao e recusada")

    def test_ia_nao_precisa_gerar_codigo(self):
        """A diretriz do mapa: nada de `eval`/`exec` nem de `.py` gerado."""
        import pathlib

        fonte = pathlib.Path("app/ia/dinamico_intents.py").read_text(encoding="utf-8")
        for proibido in ("eval(", "exec(", "__import__", "subprocess"):
            self.assertNotIn(
                proibido, fonte, f"{proibido} nao pode aparecer no Criador Livre"
            )
