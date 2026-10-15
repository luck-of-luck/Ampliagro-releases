"""
Testes das fundações do AmplIA: D1 (llm_gateway), D2 (json_portatil) e
D3 (motor dinâmico).

Estes testes não são cobertura de linha — cada um trava um INVARIANTE que,
se quebrar, vira bug em produção:

* D1: o gateway nunca levanta, e sem chave ele não chama nada externo.
* D2: o probe mente? — o SQLite NÃO tem `__contains`, e a camada precisa
  saber disso antes de gerar SQL.
* D3: um usuário não enxerga nem escreve ferramenta alheia; a IA não consegue
  escrever código; a configuração inválida falha no save, não na leitura.
"""

from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase

from app.ia import dinamicos
from app.ia import json_portatil as jp
from app.ia.llm_gateway import (
    Provedor,
    ProvedorNaoPermitido,
    chamar,
    registrar_provedor,
)
from app.ia.llm_gateway import (
    limpar_cache as _limpar_gateway_cache,
)
from app.models import DynamicApp, DynamicField, DynamicRecord

# ==========================================================================
# D1 — llm_gateway
# ==========================================================================


class _ProvedorQuebrado(Provedor):
    nome = "quebrado"

    def responder(self, prompt, cfg, **kwargs):
        raise ConnectionError("rede caiu")


class _ProvedorQueExigeChave(Provedor):
    nome = "exige_chave"
    requer_chave = True

    def responder(self, prompt, cfg, **kwargs):
        return "resposta remota"


class GatewayOfflineFirstTest(TestCase):
    """D1: o gateway degrada, nunca quebra."""

    def setUp(self):
        _limpar_gateway_cache()

    def tearDown(self):
        _limpar_gateway_cache()

    def test_padrao_e_local_sem_rede(self):
        """Sem configurar nada, é local. É o que mantém o produtor offline."""
        r = chamar("qual o clima?")
        self.assertTrue(r["ok"])
        self.assertEqual(r["provedor"], "local")
        self.assertEqual(r["pedido"], "local")
        self.assertEqual(r["erro"], "")

    def test_contrato_estavel(self):
        """O contrato não muda: quem chama sempre recebe as mesmas chaves."""
        r = chamar("x")
        for chave in ("ok", "texto", "provedor", "pedido", "erro", "duracao_ms"):
            self.assertIn(chave, r)
        self.assertIsInstance(r["duracao_ms"], int)
        self.assertIsInstance(r["ok"], bool)

    def test_local_nao_inventa_resposta(self):
        """Resposta fixa e honesta da primeira versão — não finge ser um modelo.

        Se um dia isto responder algo que parece uma resposta de IA, o produtor
        perde a garantia de que o que a AmplIA afirma veio do banco dele.
        """
        r = chamar("me analyze")
        self.assertIn("desligada", r["texto"].lower())
        self.assertNotIn("Olá", r["texto"])
        self.assertEqual(chamar("me analyze")["texto"], r["texto"])

    def test_provedor_quebrado_degrada_para_local(self):
        """Um provedor que estoura NÃO pode derrubar a chamada."""
        registrar_provedor("quebrado", _ProvedorQuebrado)
        # registrar so disponibiliza; e preciso SELECIONAR para exercitar
        r = chamar("oi", provedor="quebrado")
        self.assertFalse(r["ok"])
        self.assertIn("ConnectionError", r["erro"])
        self.assertEqual(r["provedor"], "local", "deve ter degradado para o local")
        self.assertTrue(r["texto"])

    def test_provedor_desconhecido_e_ignorado(self):
        """Nome fora do registro não vira import dinâmico."""
        from app.ia.llm_gateway import _ler_config

        _limpar_gateway_cache()
        cfg = _ler_config()
        cfg["provedor"] = "openai-que-nao-existe"
        # simula config invalida sem passar por configurar_provedor
        import app.ia.llm_gateway as g

        g._CACHE["cfg"] = cfg
        try:
            r = chamar("oi")
            self.assertEqual(r["provedor"], "local")
        finally:
            _limpar_gateway_cache()

    def test_provedor_que_exige_chave_sem_chave_fica_local(self):
        """Diretriz 4: sem credencial, não há chamada para fora."""
        registrar_provedor("exige_chave", _ProvedorQueExigeChave)
        r = chamar("oi", provedor="exige_chave")
        self.assertEqual(r["provedor"], "local")
        self.assertEqual(r["pedido"], "local")

    def test_configurar_provedor_inexistente_recusa(self):
        with self.assertRaises(ProvedorNaoPermitido):
            from app.ia.llm_gateway import configurar_provedor

            configurar_provedor("nao-registrado")

    def test_disponivel_nao_vaza_chave(self):
        """`disponivel()` vai para a UI. Não pode devolver o segredo."""
        from app.ia.llm_gateway import disponivel

        d = disponivel()
        self.assertIn("tem_chave", d)
        self.assertNotIn("chave", d)
        self.assertIs(d["em_nuvem"], False)


# ==========================================================================
# D2 — portabilidade do JSONField
# ==========================================================================


class ProbeJsonTest(TestCase):
    """D2: o probe tem que refletir a verdade do backend."""

    def setUp(self):
        jp.limpar_cache()

    def tearDown(self):
        jp.limpar_cache()

    def test_probe_nao_contamina_entre_features(self):
        """Regressão: o cache indexado só pelo vendor devolvia a feature errada.

        Com o bug, `supports_json_field` (True) contaminava
        `supports_json_field_contains` (False) e o SQLite se anunciava com
        JSONB. Um probe que mente gera SQL inválido em produção.
        """
        from django.db import connection

        jp.limpar_cache()
        for nome in (
            "supports_json_field",
            "supports_json_field_contains",
            "has_native_json_field",
            "has_json_operators",
            "supports_json_field",
        ):
            with self.subTest(feature=nome):
                jp.limpar_cache()
                esperado = bool(getattr(connection.features, nome, False))
                self.assertEqual(jp._supports(nome), esperado)
                # segunda leitura vem do cache e tem que ser igual
                self.assertEqual(jp._supports(nome), esperado)

    def test_diagnostico_bate_com_connection_features(self):
        from django.db import connection

        d = jp.diagnostico()
        self.assertEqual(d["json_field"], connection.features.supports_json_field)
        self.assertEqual(
            d["contains_suportado"], connection.features.supports_json_field_contains
        )
        self.assertEqual(d["vendor"], connection.vendor)

    def test_estrategia_coerente_com_o_vendor(self):
        """`estrategia_contains` não pode prometer jsonb num backend sem jsonb."""
        d = jp.diagnostico()
        if d["jsonb_nativo"]:
            self.assertEqual(d["estrategia_contains"], "jsonb")
        else:
            self.assertEqual(d["estrategia_contains"], "texto")

    def test_contem_nao_quebra_em_nenhum_backend(self):
        """`contem()` tem que devolver o mesmo conjunto nos dois backends.

        No SQLite, `__contains` levanta NotSupportedError. Se alguém escrever
        a query na mão e quebrar, este teste é o que denuncia.
        """
        u = User.objects.create_user("d2")
        app = DynamicApp.objects.create(user=u, nome="App D2", slug="app-d2")
        DynamicRecord.objects.create(
            app=app, user=u, dados={"status": "ativo", "qtd": 5, "aberta": False}
        )
        qs = DynamicRecord.objects.para(u).do_app(app)

        achados = list(jp.contem(qs, {"status": "ativo"}))
        self.assertEqual(len(achados), 1, "contem por chave deve achar o registro")
        self.assertEqual(jp.contem(qs, {"status": "ativo"})[0].dados["qtd"], 5)

        self.assertEqual(jp.contem(qs, {}).count(), 1, "par vazio não filtra")

    def test_contem_nao_confunde_valor_similar(self):
        """Regressão de portabilidade: `{"a": 1}` não pode casar `{"a": 12}`.

        A degradação ingênua seria `__icontains` no texto do JSON, que casaria
        os dois. Aqui a comparação é por chave, valor a valor.
        """
        u = User.objects.create_user("d2b")
        app = DynamicApp.objects.create(user=u, nome="App", slug="app")
        DynamicRecord.objects.create(app=app, user=u, dados={"codigo": 1})
        DynamicRecord.objects.create(app=app, user=u, dados={"codigo": 12})
        qs = DynamicRecord.objects.para(u).do_app(app)
        r = list(jp.contem(qs, {"codigo": 1}))
        self.assertEqual(len(r), 1)
        self.assertEqual(r[0].dados["codigo"], 1)

    def test_onde_campo_e_portatil(self):
        u = User.objects.create_user("d2c")
        app = DynamicApp.objects.create(user=u, nome="App", slug="app")
        DynamicRecord.objects.create(app=app, user=u, dados={"status": "ativo"})
        DynamicRecord.objects.create(app=app, user=u, dados={"status": "fechado"})
        qs = DynamicRecord.objects.para(u).do_app(app)
        self.assertEqual(jp.onde_campo(qs, "status", "fechado").count(), 1)
        self.assertEqual(jp.onde_existe(qs, "status").count(), 2)

    def test_ordenar_por_campo(self):
        u = User.objects.create_user("d2d")
        app = DynamicApp.objects.create(user=u, nome="App", slug="app")
        for n in (3, 1, 2):
            DynamicRecord.objects.create(app=app, user=u, dados={"n": n})
        qs = DynamicRecord.objects.para(u).do_app(app)
        self.assertEqual(
            [r.dados["n"] for r in jp.ordenar_por_campo(qs, "n")], [1, 2, 3]
        )
        self.assertEqual(
            [r.dados["n"] for r in jp.ordenar_por_campo(qs, "n", crescente=False)],
            [3, 2, 1],
        )


# ==========================================================================
# D3 — motor dinâmico
# ==========================================================================


def _app(user, nome="Controle de Geladeira", **kw):
    campos = kw.pop(
        "campos",
        [
            {"rotulo": "Alimento", "tipo": "TEXTO", "obrigatorio": True},
            {"rotulo": "Quantidade (kg)", "tipo": "DECIMAL"},
        ],
    )
    return dinamicos.criar_app(user, nome, "registro", campos, **kw)


class CriarAppTest(TestCase):
    def setUp(self):
        self.u = User.objects.create_user("criador", "c@x.com", "p")

    def test_fluxo_feliz(self):
        r = _app(self.u)
        self.assertTrue(r["ok"], r["erros"])
        app = r["app"]
        self.assertEqual(app.estado, "PRONTO")
        self.assertEqual(app.slug, "controle-de-geladeira")
        self.assertEqual(DynamicField.objects.filter(app=app).count(), 2)
        chaves = list(
            DynamicField.objects.filter(app=app).values_list("chave", flat=True)
        )
        self.assertEqual(chaves, ["alimento", "quantidade_kg"])

    def test_sem_campos_nao_cria(self):
        r = dinamicos.criar_app(self.u, "Vazia", "d", [])
        self.assertFalse(r["ok"])
        self.assertIn("campos", r["erros"])
        self.assertEqual(
            DynamicApp.objects.count(), 0, "não pode deixar app pela metade"
        )

    def test_anonimo_recusado(self):
        r = dinamicos.criar_app(None, "X", "d", [{"rotulo": "a"}])
        self.assertFalse(r["ok"])

    def test_slug_unico_por_usuario(self):
        a = _app(self.u, "Geladeira")["app"]
        b = _app(self.u, "Geladeira")["app"]
        self.assertNotEqual(a.slug, b.slug)
        self.assertEqual(b.slug, "geladeira-2")

    def test_slug_unico_entre_usuarios_e_independente(self):
        """Mesmo nome, usuários diferentes: slugs iguais são permitidos."""
        v = User.objects.create_user("v2", "v@x.com", "p")
        a = _app(self.u, "Relatorio")["app"]
        b = _app(v, "Relatorio")["app"]
        self.assertEqual(a.slug, b.slug)

    def test_tipo_invalido_recusado(self):
        r = _app(self.u, campos=[{"rotulo": "x", "tipo": "MAGIC"}])
        self.assertFalse(r["ok"])
        self.assertIn("tipo", r["erros"]["campos"])

    def test_chave_invalida_recusada(self):
        """A chave vira atributo de JSONField — precisa ser identificador."""
        for chave in ("Com Espaço", "1abc", "acentuado-çã", "x" * 61):
            with self.subTest(chave=chave):
                r = _app(
                    self.u,
                    f"App {chave[:12]}",
                    campos=[{"rotulo": "ok", "tipo": "TEXTO"}, {"chave": chave}],
                )
                self.assertFalse(r["ok"], f"chave {chave!r} deveria ser recusada")
                self.assertIn("chave", r["erros"]["campos"])

    def test_chave_duplicada_recusada(self):
        r = _app(
            self.u,
            campos=[
                {"rotulo": "Peso", "tipo": "TEXTO"},
                {"rotulo": "peso", "tipo": "TEXTO"},
            ],
        )
        self.assertFalse(r["ok"])
        self.assertIn("repetida", r["erros"]["campos"])

    def test_aceita_ambas_as_grafias_da_ia(self):
        """A IA produz `label`/`type` OU `rotulo`/`tipo`. Aceitar as duas."""
        r = _app(
            self.u,
            "Grafia IA",
            campos=[{"label": "Marca", "type": "TEXTO", "required": True}],
        )
        self.assertTrue(r["ok"], r["erros"])
        c = DynamicField.objects.get(app=r["app"])
        self.assertEqual(c.rotulo, "Marca")
        self.assertTrue(c.obrigatorio)

    def test_rotulo_so_com_simbolo_gera_chave_usable(self):
        r = _app(self.u, "Escrita", campos=[{"rotulo": "###"}])
        self.assertTrue(r["ok"], r["erros"])
        c = DynamicField.objects.get(app=r["app"])
        self.assertTrue(c.chave[0].isalpha() or c.chave[0] == "_")
        self.assertNotIn("#", c.chave)

    def test_validacao_do_field_no_save(self):
        """Configuração incoerente falha no save, não na leitura.

        OPCOES sem lista e REFERENCIA sem app alvo são estados que apareceriam
        como dado corrompido na tela do produtor.
        """
        app = _app(self.u)["app"]
        with self.assertRaises(ValidationError):
            DynamicField(app=app, chave="a", rotulo="A", tipo="OPCOES").full_clean()
        with self.assertRaises(ValidationError):
            DynamicField(app=app, chave="b", rotulo="B", tipo="REFERENCIA").full_clean()
        with self.assertRaises(ValidationError):
            DynamicField(
                app=app, chave="c", rotulo="C", tipo="TEXTO", opcoes=[{"valor": 1}]
            ).full_clean()

    def test_reference_sem_app_alvo_recusado_na_criacao(self):
        r = _app(
            self.u,
            "Com Ref",
            campos=[{"rotulo": "X", "tipo": "REFERENCIA"}],
        )
        self.assertFalse(r["ok"])


class RegistroTest(TestCase):
    def setUp(self):
        self.u = User.objects.create_user("reg", "r@x.com", "p")
        self.app = _app(self.u)["app"]

    def test_grava_coerindo_tipos(self):
        r = dinamicos.registrar(
            self.u,
            self.app,
            {"alimento": "Racao", "quantidade_kg": "12,5".replace(",", ".")},
        )
        self.assertTrue(r["ok"], r["erros"])
        d = r["registro"].dados
        self.assertEqual(d["alimento"], "Racao")
        self.assertIsInstance(d["quantidade_kg"], Decimal)
        self.assertEqual(d["quantidade_kg"], Decimal("12.5"))

    def test_obrigatorio_ausente(self):
        r = dinamicos.registrar(self.u, self.app, {})
        self.assertFalse(r["ok"])
        self.assertIn("alimento", r["erros"])

    def test_valor_vazio_usa_padrao(self):
        app = _app(
            self.u,
            "Com Padrao",
            campos=[
                {"rotulo": "Aviso", "tipo": "TEXTO", "obrigatorio": True},
                {"rotulo": "Qtd", "tipo": "NUMERO", "padrao": 1},
            ],
        )["app"]
        r = dinamicos.registrar(self.u, app, {"aviso": "oi"})
        self.assertTrue(r["ok"], r["erros"])
        self.assertEqual(r["registro"].dados["qtd"], 1)

    def test_opcao_fora_da_lista(self):
        app = _app(
            self.u,
            "Com Opcoes",
            campos=[
                {
                    "rotulo": "Status",
                    "tipo": "OPCOES",
                    "obrigatorio": True,
                    "opcoes": [
                        {"valor": "A", "rotulo": "Aberto"},
                        {"valor": "F", "rotulo": "Fechado"},
                    ],
                }
            ],
        )["app"]
        self.assertTrue(dinamicos.registrar(self.u, app, {"status": "A"})["ok"])
        r = dinamicos.registrar(self.u, app, {"status": "Z"})
        self.assertFalse(r["ok"])
        self.assertIn("status", r["erros"])

    def test_booleano_em_portugues(self):
        app = _app(
            self.u, "Com Bool", campos=[{"rotulo": "Ativo", "tipo": "BOOLEANO"}]
        )["app"]
        for entrada, esperado in (
            ("sim", True),
            ("não", False),
            (True, True),
            ("0", False),
        ):
            with self.subTest(entrada=entrada):
                r = dinamicos.registrar(self.u, app, {"ativo": entrada})
                self.assertTrue(r["ok"], r["erros"])
                self.assertIs(r["registro"].dados["ativo"], esperado)

    def test_data_invalida(self):
        app = _app(self.u, "Com Data", campos=[{"rotulo": "Quando", "tipo": "DATA"}])[
            "app"
        ]
        self.assertTrue(
            dinamicos.registrar(self.u, app, {"quando": "2026-09-26"})["ok"]
        )
        r = dinamicos.registrar(self.u, app, {"quando": "26/09/2026"})
        self.assertFalse(
            r["ok"], "data em dd/mm/aaaa deveria ser recusada com mensagem clara"
        )

    def test_chave_desconhecida_recusa_a_gravacao(self):
        """BUILD 2: a defesa contra alucinação de chave.

        O comportamento antigo era "descartar e seguir": a chave ia para
        `descartadas` e o registro era gravado com `ok: True`. O produtor pedia
        "registre a vacina da vaca", o modelo mandava um campo a mais, esse
        campo sumia — e o produtor nunca ficava sabendo que um dado que ELE
        pediu não foi salvo. Pior: o modelo não recebia nenhum indício de que
        errou, então repetia o mesmo erro no registro seguinte.

        Agora a gravação é recusada, e a mensagem lista as chaves válidas para
        que o modelo se corrija numa segunda chamada.
        """
        r = dinamicos.registrar(
            self.u, self.app, {"alimento": "X", "idade_da_vaca": 10}
        )
        self.assertFalse(r["ok"], "campo alucinado nao pode ser gravado em silencio")
        self.assertIsNone(r["registro"], "nada pode ser gravado numa recusa")

        # a mensagem precisa ser UTILIZAVEL pelo modelo: nomear a chave errada
        # e listar as validas. Um "campo invalido" generico nao da para corrigir.
        msg = " ".join(r["erros"].values())
        self.assertIn("idade_da_vaca", msg)
        self.assertIn("alimento", msg, "a lista de validas tem que estar na mensagem")
        self.assertIn("quantidade_kg", msg)

        # e nada foi gravado de fato
        from app.models import DynamicRecord

        self.assertEqual(
            DynamicRecord.objects.do_usuario_e_app(self.u, self.app).count(), 0
        )

    def test_recusa_e_atomica_quando_varios_campos_erram(self):
        """Um campo bom e um ruim: o bom nao vira registro pela metade."""
        r = dinamicos.registrar(
            self.u, self.app, {"alimento": "X", "campo_inventado": 1}
        )
        self.assertFalse(r["ok"])
        self.assertEqual(r["registro"], None)

    def test_modo_tolerante_ainda_existe_explicitamente(self):
        """`estrito=False` continua disponível — e é uma DECISÃO do chamador.

        Quem tolera é a rota do formulário: um campo removido do schema não
        pode custar ao produtor a gravação inteira. A rota da IA é estrita
        porque o modelo precisa aprender com o erro. Nenhuma das duas decide
        sozinha; a biblioteca oferece as duas.
        """
        r = dinamicos.registrar(
            self.u,
            self.app,
            {"alimento": "X", "campo_que_nao_existe": 1},
            estrito=False,
        )
        self.assertTrue(r["ok"], r["erros"])
        self.assertIn("campo_que_nao_existe", r["descartadas"])
        self.assertNotIn("campo_que_nao_existe", r["registro"].dados)

    def test_snapshot_do_schema_gravado(self):
        """'o que o formulário mostrava quando salvou' fica auditável."""
        r = dinamicos.registrar(self.u, self.app, {"alimento": "X"})
        snap = r["registro"].schema_snapshot
        self.assertEqual([c["chave"] for c in snap], ["alimento", "quantidade_kg"])

    def test_arquivada_nao_aceita_registro(self):
        self.app.estado = "ARQUIVADO"
        self.app.save()
        r = dinamicos.registrar(self.u, self.app, {"alimento": "X"})
        self.assertFalse(r["ok"])


class IsolamentoTest(TestCase):
    """D3: o invariant mais importante — um usuário não toca o dado do outro."""

    def setUp(self):
        self.a = User.objects.create_user("alice", "a@x.com", "p")
        self.b = User.objects.create_user("bob", "b@x.com", "p")
        self.app_a = _app(self.a, "App Alice")["app"]

    def test_para_none_devolve_vazio(self):
        """Fail-closed: sessão quebrada não pode virar 've tudo'."""
        self.assertEqual(DynamicRecord.objects.para(None).count(), 0)

    def test_para_anonimo_devolve_vazio(self):
        from django.contrib.auth.models import AnonymousUser

        self.assertEqual(DynamicRecord.objects.para(AnonymousUser()).count(), 0)

    def test_listar_so_mostra_o_que_e_do_usuario(self):
        """Isolamento na leitura.

        O comportamento antigo devolvia queryset vazio para a app alheia. Isso
        era seguro, mas indistinguível de "não tem registro" — e a indistinção
        é justamente o que BUILD 2 quer eliminar. Agora `listar` LEVANTA, e o
        motivo (app não é sua) não pode ser confundido com ausência de dado.
        """
        dinamicos.registrar(self.a, self.app_a, {"alimento": "X"})
        self.assertEqual(dinamicos.listar(self.a, self.app_a).count(), 1)

        with self.assertRaises(dinamicos.ErroDinamico) as ctx:
            dinamicos.listar(self.b, self.app_a)
        self.assertIn("usuario", str(ctx.exception).lower())

    def test_registrar_em_app_alheia_recusado(self):
        r = dinamicos.registrar(self.b, self.app_a, {"alimento": "X"})
        self.assertFalse(r["ok"])
        self.assertIn("app", r["erros"])

    def test_reference_para_registro_alheia_recusado(self):
        """Apontar para o registro do outro é o mesmo vazamento."""
        alvo = _app(self.b, "App Bob", campos=[{"rotulo": "Nome", "tipo": "TEXTO"}])[
            "app"
        ]
        meu = dinamicos.registrar(self.b, alvo, {"nome": "sobrevivo"})["registro"]
        app = _app(
            self.a,
            "Referencia",
            campos=[
                {"rotulo": "Aponta", "tipo": "REFERENCIA", "app_relacionada": alvo}
            ],
        )["app"]
        # o registro pertence ao app do bob, entao nem existe no escopo do alice
        r = dinamicos.registrar(self.a, app, {"aponta": meu.pk})
        self.assertFalse(r["ok"])
        self.assertIn("aponta", r["erros"])

    def test_descrever_exige_anonimo(self):
        from app.ia.dinamicos import ErroDinamico

        with self.assertRaises(ErroDinamico):
            dinamicos.descrever(None, self.app_a)

    def test_descrever_recusa_ferramenta_alheia(self):
        """`descrever` levanta, nao devolve schema vazio.

        Devolver um dicionário vazio seria o modo sutil de dar à IA a tela da
        ferramenta errada sem nenhum sinal de erro.
        """
        from app.ia.dinamicos import ErroDinamico

        with self.assertRaises(ErroDinamico):
            dinamicos.descrever(self.b, self.app_a)

    def test_descrever_usa_prefetch_quando_existe(self):
        """Com prefetch, descrever() nao pode disparar query."""
        from django.db import connection
        from django.test import override_settings

        # a lista vem ANTES da janela de medicao: o que se quer provar e que
        # descrever() nao dispara query, nao que listar_ferramentas() e gratis.
        # Sem o prefetch seriam 1 consulta por app, dentro do laco.
        apps = dinamicos.listar_ferramentas(self.a)
        self.assertGreater(len(apps), 0, "precisa de ao menos 1 ferramenta")

        with override_settings(DEBUG=True):
            from django.db import reset_queries

            reset_queries()
            for app in apps:
                dinamicos.descrever(self.a, app)
            self.assertEqual(len(connection.queries), 0, "prefetch nao foi usado (N+1)")

    def test_descrever_nao_vaza(self):
        d = dinamicos.descrever(self.a, self.app_a)
        self.assertEqual(d["nome"], "App Alice")
        self.assertEqual(
            [c["chave"] for c in d["campos"]], ["alimento", "quantidade_kg"]
        )

    def test_listar_ferramentas_escopado(self):
        _app(self.b, "App Bob")["app"]
        nomes = {a.nome for a in dinamicos.listar_ferramentas(self.a)}
        self.assertEqual(nomes, {"App Alice"})


class SemExecucaoDeCodigoTest(TestCase):
    """A diretriz 2 do mapa, verificada no nível do fonte.

    A IA escreve metadados. Este teste lê o fonte dos módulos do Criador Livre
    e falha se aparecer uma chamada real a `eval`/`exec`/`compile`/`__import__`.
    É um teste de invariante deliberado: protege a fronteira que não tem
    nenhuma flag de configuração para desligar.
    """

    ARQUIVOS = [
        "app/models/dinamico.py",
        "app/ia/dinamicos.py",
        "app/ia/json_portatil.py",
        "app/ia/llm_gateway/__init__.py",
    ]
    PROIBIDOS = {"eval", "exec", "compile", "__import__"}

    def test_nenhuma_chamada_de_execucao(self):
        import ast
        import pathlib

        achados = []
        for rel in self.ARQUIVOS:
            caminho = pathlib.Path(rel)
            if not caminho.exists():
                continue
            arv = ast.parse(caminho.read_text(encoding="utf-8"))
            for no in ast.walk(arv):
                if isinstance(no, ast.Call) and isinstance(no.func, ast.Name):
                    if no.func.id in self.PROIBIDOS:
                        achados.append(f"{rel}:{no.lineno} {no.func.id}()")
                # getattr(dados, '__class__') e companhia
                if isinstance(no, ast.Call) and isinstance(no.func, ast.Name):
                    if no.func.id == "getattr" and len(no.args) >= 2:
                        for a in no.args[1:]:
                            if isinstance(a, ast.Constant) and isinstance(a.value, str):
                                if a.value.startswith("__"):
                                    achados.append(
                                        f"{rel}:{no.lineno} getattr(..., {a.value!r})"
                                    )
        self.assertEqual(achados, [], f"execucao de codigo no Criador Livre: {achados}")
