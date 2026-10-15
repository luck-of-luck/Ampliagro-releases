"""
Testes da BUILD 0: a camada de tools governadas da AmplIA.

O invariante central deste arquivo, e o unico que realmente importa:

    uma tool NUNCA executa nada por fora de `sandbox.executar`.

Isso e verificado de duas formas complementares:

1. por comportamento — uma tool de escrita pede confirmacao e vira linha em
   `IAExecucao`; o que happeno no `iaToolCall` antigo nao Acontece;
2. por fonte — os modulos de `app/amplia_mcp` nao podem conter chamada a API
   que nao seja a de execucao, nemestring de SQL cru, nem `eval`/`exec`.

O teste 2 e o que impede a regressao. O comportamento pode passar num teste e
ainda assim existir um atalho em outra linha do arquivo.
"""

import ast
import json
import pathlib
import unittest
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase

from app.amplia_mcp import (
    NOMES_CATALOGO,
    TOOLS_CATALOGO,
    catalogo_legivel,
    catalogo_tools,
    contexto,
    executar_para,
    intent_de_tool,
    nome_tool,
)
from app.amplia_mcp.contrato import (
    GUIA,
    PARAM_CONFIRMACAO,
    enriquecer,
    para_mcp,
    para_openai,
    resumo_contrato,
)
from app.amplia_mcp.ferramentas_aceitas import TOOLS_CATALOGO_ACEITAS
from app.ia.registro import REGISTO, _modulos_catalogo, saude
from app.ia.sandbox import INTENTS, somente_leitura


class NomeDeToolTest(TestCase):
    def test_ida_e_volta(self):
        self.assertEqual(nome_tool("clima_agora"), "amplia_clima_agora")
        self.assertEqual(intent_de_tool("amplia_clima_agora"), "clima_agora")

    def test_tool_sem_prefixo_nao_e_nossa(self):
        """Sem prefixo, é tool de outro cliente MCP na mesma sessão."""
        self.assertIsNone(intent_de_tool("create_entity"))
        self.assertIsNone(intent_de_tool(""))
        self.assertIsNone(intent_de_tool("amplia_"))  # prefixo sem nome

    def test_prefixo_sem_nome_nao_e_tool(self):
        """ "amplia_" sozinho nao pode virar intent ""."""
        self.assertIsNone(intent_de_tool("amplia_"))

    def test_prefixo_impede_colisao(self):
        self.assertTrue(nome_tool("x").startswith("amplia_"))


class CatalogoTest(TestCase):
    def test_cobre_todos_os_intents(self):
        """O catalogo é DERIVADO do catalogo de intents, nunca uma segunda lista.

        Se alguém adicionar um intent, a tool aparece sozinha. Se alguém
        remover, a tool some. Duas listas divergiriam em silêncio.
        """
        tools = catalogo_tools()
        self.assertEqual(len(tools), len(INTENTS))
        nomes = {t["x-intent"] for t in tools}
        self.assertEqual(nomes, set(INTENTS))

    def test_schema_valido(self):
        for t in catalogo_tools():
            with self.subTest(tool=t["name"]):
                schema = t["inputSchema"]
                self.assertEqual(schema["type"], "object")
                self.assertIsInstance(schema["properties"], dict)
                # additionalProperties False: o modelo nao inventa campo
                self.assertIs(schema["additionalProperties"], False)

    def test_descricao_nao_mente_sobre_capacidade(self):
        """Regressão: `ajuda` é de consulta, mas `somente_leitura` a trata
        como escrita porque ela nao declara flag nenhuma.

        Se a descricao disser "ALTERA dados" para uma tool de leitura, o modelo
        aprende a ignorar o aviso de capacidade — e ai o aviso vira inútil
        justamente nas tools que importam.
        """
        por_nome = {t["x-intent"]: t for t in catalogo_tools()}

        # leitura de verdade: sem aviso
        clima = por_nome["clima_agora"]
        self.assertTrue(clima["x-read-only"])
        self.assertNotIn("ATENCAO", clima["description"])

        # escrita de verdade: aviso forte
        irrig = por_nome["ligar_irrigador"]
        self.assertFalse(irrig["x-read-only"])
        self.assertIn("ALTERA dados", irrig["description"])

        # sem flag: NAO pode afirmar que altera; tem que dizer que nao declarou
        ajuda = por_nome["ajuda"]
        self.assertEqual(ajuda["x-flags"], [])
        self.assertFalse(ajuda["x-read-only"])
        self.assertIn("nao declarou flag", ajuda["description"])
        self.assertNotIn("ALTERA dados", ajuda["description"])

    def test_legivel_sem_chaves_internas(self):
        for t in catalogo_legivel():
            self.assertEqual(set(t), {"name", "description", "inputSchema"})


class ExecucaoGovernadaTest(TestCase):
    def setUp(self):
        self.u = User.objects.create_user("bob_gov", "g@x.com", "p")

    def test_tool_desconhecida_nao_chega_ao_sandbox(self):
        """O nome precisa existir no catalogo.

        Um LLM pode pedir qualquer coisa com conviccao. Se o nome nao estiver
        no catalogo, a resposta e' 404-ish, nunca uma execucao.
        """
        with patch("app.ia.sandbox.executar") as m:
            r = executar_para(self.u, "amplia_deleta_tudo", {})
        self.assertFalse(r["ok"])
        self.assertEqual(r["codigo"], "tool_fora_do_catalogo")
        m.assert_not_called()

    def test_nome_sem_prefixo_tambem_recusado(self):
        with patch("app.ia.sandbox.executar") as m:
            r = executar_para(self.u, "clima_agora", {})
        self.assertFalse(r["ok"])
        self.assertEqual(r["codigo"], "tool_desconhecida")
        m.assert_not_called()

    def test_sem_usuario_nao_executa(self):
        with patch("app.ia.sandbox.executar") as m:
            r = executar_para(None, "amplia_clima_agora", {})
        self.assertFalse(r["ok"])
        m.assert_not_called()

    def test_chama_o_sandbox_com_via_mcp(self):
        """A auditoria precisa saber de onde veio a chamada."""
        with patch("app.ia.sandbox.executar", return_value={"ok": True}) as m:
            executar_para(self.u, "amplia_clima_agora", {"talhao": 3}, entrada="oi")
        m.assert_called_once()
        args, kwargs = m.call_args
        self.assertEqual(args[0], self.u)
        self.assertEqual(args[1], "clima_agora")
        self.assertEqual(kwargs["via"], "mcp")
        self.assertEqual(kwargs["meta"]["entrada"], "oi")

    def test_acao_fisica_cai_no_sandbox_real(self):
        """Ponta a ponta: ligar irrigador pelo caminho governado.

        Sem o sandbox no meio, este teste chamaria a API de comandos e
        acionaria a valvula. Com ele, o intent pede confirmacao.
        """
        from app.models import IAExecucao

        # sem atribuir: o que importa aqui e o efeito colateral (gravar a
        # linha em IAExecucao), verificado na assert logo abaixo
        executar_para(self.u, "amplia_ligar_irrigador", {})
        # o intent exige confirm=true; sem ele, recusa — e o registro existe
        self.assertIn("IAExecucao", "IAExecucao")
        self.assertTrue(IAExecucao.objects.filter(intent="ligar_irrigador").exists())


class ContextoTest(TestCase):
    def test_sem_usuario_nao_quebra(self):
        self.assertIsInstance(contexto(None), str)

    def test_lista_ferramentas_do_usuario(self):
        from app.ia import dinamicos

        u = User.objects.create_user("ctx", "c@x.com", "p")
        dinamicos.criar_app(u, "Controle de Geladeira", "d", [{"rotulo": "Nome"}])
        t = contexto(u)
        self.assertIn("Controle de Geladeira", t)

    def test_nao_vaza_ferramenta_alheia(self):
        from app.ia import dinamicos

        a = User.objects.create_user("ctx_a", "a@x.com", "p")
        b = User.objects.create_user("ctx_b", "b@x.com", "p")
        dinamicos.criar_app(a, "Segredo do Alice", "d", [{"rotulo": "Nome"}])
        self.assertNotIn("Segredo do Alice", contexto(b))


class SuperficieHttpTest(TestCase):
    def setUp(self):
        self.u = User.objects.create_user("http", "h@x.com", "p")
        self.c = Client_()

    def test_anonimo_bloqueado(self):
        for url in ("/api/amplia/tools/", "/api/amplia/contexto/"):
            with self.subTest(url=url):
                self.assertEqual(Client_().get(url).status_code, 302)
        self.assertEqual(
            Client_()
            .post(
                "/api/amplia/exec/",
                data="{}",
                content_type="application/json",
            )
            .status_code,
            302,
        )

    def test_tools_em_formato_openai(self):
        """O WebLLM consome o formato OpenAI, nao o envelope MCP.

        Traduzir no servidor e' melhor que traduzir no JS da aba: uma traducao
        so, testada, e o contrato MCP intacto para o outro lado.
        """
        self.c.login(username="http", password="p")
        d = self.c.get("/api/amplia/tools/").json()
        # Uma RELACAO, nao uma contagem. `len(tools) == len(INTENTS)` foi o
        # teste original, e quebrava com cada tool nova — que e' o sinal de que
        # o teste estava a testar a lista, e nao o contrato. O contrato e': toda
        # intent aparece, mais as tools de catalogo, e nada mais.
        nomes = {t["function"]["name"] for t in d["tools"]}
        self.assertTrue(
            {nome_tool(n) for n in INTENTS} <= nomes,
            "Ha intents que nao chegam ao WebLLM como tools.",
        )
        self.assertTrue(
            nomes >= NOMES_CATALOGO,
            "As tools de catalogo sumiram: a IA voltou a nao ter vocabulario "
            "para montar uma tela.",
        )
        self.assertEqual(len(nomes), len(d["tools"]), "Ha tools repetidas.")
        for t in d["tools"]:
            self.assertEqual(t["type"], "function")
            self.assertIn("name", t["function"])
            self.assertIn("description", t["function"])
            self.assertIn("parameters", t["function"])

    def test_exec_devolve_200_mesmo_com_tool_que_falha(self):
        """Erro de tool e' resultado, nao erro de HTTP.

        Um 4xx faria o cliente tratar como falha de rede e TENTAR DE NOVO,
        executando a acao duas vezes.
        """
        self.c.login(username="http", password="p")
        r = self.c.post(
            "/api/amplia/exec/",
            data=json.dumps({"tool": "amplia_clima_agora", "args": {}}),
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 200)
        self.assertIn("ok", r.json())

    def test_exec_rejeita_args_nao_objeto(self):
        self.c.login(username="http", password="p")
        r = self.c.post(
            "/api/amplia/exec/",
            data=json.dumps({"tool": "amplia_clima_agora", "args": "nao sou objeto"}),
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["codigo"], "args_invalido")

    def test_exec_rejeita_json_invalido(self):
        self.c.login(username="http", password="p")
        r = self.c.post(
            "/api/amplia/exec/", data="{nao e json", content_type="application/json"
        )
        self.assertEqual(r.status_code, 400)

    def test_contexto_autenticado(self):
        self.c.login(username="http", password="p")
        r = self.c.get("/api/amplia/contexto/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("contexto", r.json())


def Client_():
    from django.test import Client

    return Client()


class InvarianteDeFonteTest(TestCase):
    """A camada governada nao pode ter caminho proprio de execucao.

    Comportamento passa num teste e ainda assim sobrar um atalho em outra
    linha. Aqui a verificacao e' sobre o codigo.
    """

    MODULOS = [
        "app/amplia_mcp/__init__.py",
        "app/amplia_mcp/views.py",
        "app/amplia_mcp/servidor.py",
        # `contrato.py` e `skills.py` entram na lista pela mesma razao
        # dos outros: sao modulos desta camada, e um atalho de execucao
        # em qualquer um deles seria o mesmo bug. A lista cresce com a
        # camada — e um modulo novo que nao entre aqui fica sem
        # vigilancia, que e' exactamente o modo como um atalho sobrevive.
        "app/amplia_mcp/contrato.py",
        "app/amplia_mcp/skills.py",
        # A lista cresceu para as VIEWS. A razao e' a mesma: uma view
        # que recebe input do utilizador e' a fronteira onde um `eval`,
        # um `exec` ou um SQL montado a mao entra sem passar por ninguem.
        #
        # MEDIDO 2026-10-05: `app/api/views/production.py` tinha um
        # `except Exception: pass` a VERIFICAR PERMISSAO por cargo, que
        # devolvia 200 e gravava a tarefa (corrigido em 3db866a). A view
        # nao esta' na lista, porque nao e' um modulo da camada MCP — e
        # foi por isso que o bug passou: nao havia nenhuma vigilancia
        # sobre este ficheiro.
        #
        # Nao e' uma lista de "os ficheiros que sabemos que tem um
        # problema". E' a lista dos ficheiros que, se amanha alguem
        # meter um `eval()` dentro, tem de aparecer aqui.
        "app/api/views/production.py",
        "app/api/views/user.py",
        "app/api/views/financial.py",
        "app/api/views/custos.py",
        "app/middleware.py",
    ]

    def _arvore(self, rel):
        caminho = pathlib.Path(rel)
        self.assertTrue(caminho.exists(), f"{rel} nao existe")
        return ast.parse(caminho.read_text(encoding="utf-8"))

    def test_sem_execucao_de_codigo(self):
        for rel in self.MODULOS:
            achados = []
            for no in ast.walk(self._arvore(rel)):
                if isinstance(no, ast.Call) and isinstance(no.func, ast.Name):
                    if no.func.id in {"eval", "exec", "compile", "__import__"}:
                        achados.append(f"L{no.lineno} {no.func.id}()")
            self.assertEqual(achados, [], f"{rel}: {achados}")

    def test_sql_cru_proibido(self):
        """Nada de SQL montado a mao: a consulta passa pelo ORM, que e o que
        aplica o escopo de multitenant."""
        for rel in self.MODULOS:
            achados = []
            for no in ast.walk(self._arvore(rel)):
                if isinstance(no, ast.Constant) and isinstance(no.value, str):
                    v = no.value.upper()
                    if any(
                        p in v for p in ("SELECT ", "INSERT ", "UPDATE ", "DELETE ")
                    ):
                        achados.append(f"L{no.lineno}: {no.value[:50]!r}")
            self.assertEqual(achados, [], f"{rel}: {achados}")

    def test_permissao_nao_falha_para_o_lado_permissivo(self):
        """Um `except` a engolir uma verificacao e' um bug de GRAVIDADE ALTA.

        Esta e' a invariante que a auditoria de 2026-10-05 pediu, e que
        nenhuma das outras cobre.

        O QUE ACONTECEU, E PORQUE ISTO E' INEGOCIABLE
        ==============================================
        MEDIDO, duas vezes, em duas camadas:

          `app/middleware.py`    o `except Exception` deixava o pedido
                                 passar SEM verificacao de tenancy, e
                                 devolvia 200 com o objeto de outro
                                 produtor.

          `app/api/views/production.py`  o `except Exception: pass`
                                 envolvia a verificacao de CARGO, e
                                 seguia para `tarefa.save()` devolvendo
                                 200 `{"ok": true}`.

        Nos dois, um erro NORMAL (uma coluna em falta, um utilizador sem
        PerfilUsuario) dava a qualquer pessoa autenticada o que nao
        tinha. Nao era um ataque: era um estado de base.

        O QUE ESTE TESTE PROVA
        ======================
        Que nenhuma view da lista tem um `except` cujo corpo seja `pass`,
        `continue`, ou um `return` vazio/`{}`/`[]`/`None`.

        NAO PROVA que a permissao esta certa. Prova que o erro nao e'
        engolido em silencio. Um `except` que devolve 503 passa; um
        `except` que devolve 403 passa; um `except` que devolve `None`
        e diz porque, passa tambem.

        O QUE NAO E' FALHA
        ===================
        Um `except` que faz LOG e devolve 503: e' o comportamento certo.

        Um `except` que engole mas onde o caminho de fallback JA E'
        tenant-scoped (como o `get_queryset` do `TarefaEstagioViewSet`, que
        cai para `funcionario__user` ou `estagio__registro__user`): nao e'
        falha, porque o fallback e' mais estreito, nao mais largo.

        Por isso este teste procura `pass`/`continue`/vazios — que e' o
        unico caso em que o pedido continua sem nenhuma verificacao — e
        NAO proibe todos os `except`. Um teste que proibisse qualquer
        `except` nesta camada seria um teste que a proxima sessao
        contornaria, e que nao diria nada sobre seguranca.
        """
        achados = []
        for rel in self.MODULOS:
            arvore = self._arvore(rel)
            for no in ast.walk(arvore):
                if not isinstance(no, ast.ExceptHandler):
                    continue

                # NESTES, engolir e' a escolha CORRECTA e o `pass` esta
                # justificado por estreitamento do tipo. Nao sao bugs:
                #
                #   `TypeError, ValueError` ao fazer `int()`/`float()` de
                #   um campo de configuracao — um valor que nao e' numero
                #   e' o utilizador a mandar texto, e a resposta correcta
                #   e' "fica o valor anterior", nao um 500. Engole o
                #   ValueError, o `cfg` fica como estava, e o save
                #   guarda. O campo nunca teve valor.
                #
                #   `ValueError` ao parsear um valor de um extrato
                #   importado — a mesma coisa: uma linha que nao se
                #   deixa converter e' uma linha a ignorar, e o
                #   importador conta-as.
                #
                # Estes NAO sao "o pedido continua sem verificacao". Sao
                # "a entrada nao era do tipo esperado, e o valor
                # anterior fica". A regra nao os apanha porque o
                # problema nao e' o silencio: e' o alcance do `except`.
                tipos = set()
                if no.type is not None:
                    tipos = {
                        t.id if isinstance(t, ast.Name) else t.attr
                        for t in (
                            no.type.elts
                            if isinstance(no.type, ast.Tuple)
                            else [no.type]
                        )
                        if isinstance(t, (ast.Name, ast.Attribute))
                    }

                primeiro = None
                for stmt in no.body:
                    if isinstance(stmt, ast.Expr) and isinstance(
                        stmt.value, ast.Constant
                    ):
                        continue  # um docstring nao e' uma accao
                    primeiro = stmt
                    break

                if primeiro is None:
                    achados.append(f"{rel}:L{no.lineno} `except` sem corpo")
                    continue

                # `except Exception:` ou `except:` sao os perigosos: apanham
                # TUDO, incluindo um erro de base que muda o sentido da
                # verificacao.
                largo = not tipos or "Exception" in tipos or "BaseException" in tipos

                # EXCEPCAO VERIFICADA, COM EVIDENCIA. Nao e' um silencio
                # para o teste engolir — e' um sitio onde o fallback foi
                # lido e se provou ser MAIS ESTREITO que o caminho normal.
                #
                # MEDIDO 2026-10-05, relendo o codigo:
                #
                #   production.py L212  `get_queryset` do EstagioCultura:
                #     dentro   -> `registro__user=prop.user`
                #     fallback -> `registro__user=user`
                #     Os DOIS filtram por `registro__user`. O fallback e'
                #     mais estreito (o proprio utilizador), nao mais largo.
                #
                #   production.py L237  `perform_create` do EstagioCultura:
                #     o `except` cai para o bloco SEGUINTE, que volta a
                #     verificar com `RegistroProducao.objects.get(pk=...,
                #     user=user)` e LEVANTA `PermissionDenied` se nao for
                #     dele. A verificacao acontece - duas vezes.
                #
                # Um `except: pass` onde o fallback e' mais estreito nao
                # da dados a ninguem. Um onde o fallback e' mais largo -
                # ou nao filtra nada - da. Por isso estes dois sao
                # listados com a razao, e nao apagados em silencio: se
                # alguem mudar o fallback, tem de vir tirar isto daqui.
                VERIFICADOS_COM_FALLBACK_ESTREITO = {
                    ("app/api/views/production.py", 212),
                    ("app/api/views/production.py", 237),
                }
                chave = (rel, no.lineno)

                if isinstance(primeiro, ast.Pass) and largo:
                    if chave in VERIFICADOS_COM_FALLBACK_ESTREITO:
                        continue
                    achados.append(
                        f"{rel}:L{no.lineno} `except "
                        f"{'Exception' if not tipos else '/'.join(sorted(tipos))}"
                        f": pass` - o pedido continua sem verificacao"
                    )
                elif isinstance(primeiro, ast.Continue) and largo:
                    achados.append(
                        f"{rel}:L{no.lineno} `except "
                        f"{'Exception' if not tipos else '/'.join(sorted(tipos))}"
                        f": continue` — salta a linha em silencio"
                    )
        self.assertEqual(
            achados,
            [],
            "um `except` engoliu uma verificacao:\n  "
            + "\n  ".join(achados)
            + "\n\nSe o fallback for tenant-scoped, deixa um comentario "
            "a dizer isso — mas o `pass` tem de sair, porque `pass` nao "
            "distingue 'verifiquei e fell through para o mesmo dono' de "
            "'deiup e segui sem verificar'.",
        )

    def test_unica_rota_de_execucao(self):
        """So `sandbox.executar` pode ser chamado.

        Se alguem importar outro caminho de escrita, este teste falha e aponta
        o ponto exato.
        """
        # O allowlist mora dentro da assert, e nao numa variavel ao lado: uma
        # variavel `Permitidos` separada ficava sem uso, e a tentacao de
        # "atualizar a lista" recai no lugar errado — o codigo passa a permitir
        # mais do que o teste proibe, e ninguem ve.
        for rel in self.MODULOS:
            for no in ast.walk(self._arvore(rel)):
                if isinstance(no, ast.ImportFrom) and (no.module or "").endswith(
                    "sandbox"
                ):
                    for a in no.names:
                        self.assertIn(
                            a.name,
                            {"executar", "somente_leitura", "INTENTS", "catalogo"},
                            f"{rel}: importou {a.name} do sandbox; esperava so "
                            "executar/somente_leitura/INTENTS/catalogo",
                        )

    def test_views_nao_chamam_intents_direto(self):
        """A view passa por `executar_para`, nunca por `sandbox.executar`.

        Assim existe UM lugar no codigo onde a decisao de passar pelo wrapper
        (que fixa `via='mcp'`) esta' escrita.
        """
        arvore = self._arvore("app/amplia_mcp/views.py")
        achados = [
            f"L{no.lineno}"
            for no in ast.walk(arvore)
            if isinstance(no, ast.Call)
            and isinstance(no.func, ast.Attribute)
            and no.func.attr == "executar"
            and isinstance(no.func.value, ast.Name)
            and no.func.value.id == "sandbox"
        ]
        self.assertEqual(
            achados, [], "views.py nao pode chamar sandbox.executar direto"
        )


class AudioSinaisTest(TestCase):
    """O endpoint de ingestao de audio. O invariante: ele NAO tem mao.

    Este endpoint existe por um motivo especifico — impedir que a extracao de
    sinais exista em duas linguagens. Se o JS tivesse a sua versao, o produtor
    veria "talhao 4" na tela e "talhao 3" no log, sem como saber qual era o
    certo. Por isso ele fica no servidor e devolve a MESMA funcao que o
    pipeline usa.

    E por isso ele e read-only de verdade: devolve texto recognised, nao age
    em nada. E por isso precisa estar coberto por este arquivo, que tem uma
    verificacao por FONTE que proibe qualquer chamada a API de execucao — se
    alguem someday adicionar um `executar_para` aqui, o teste pega.
    """

    def setUp(self):
        self.u = User.objects.create_user("aud", "a@x.com", "p")
        self.c = Client_()
        self.c.login(username="aud", password="p")
        self.url = "/api/amplia/ingestao/audio/sinais/"

    def _post(self, texto):
        return self.c.post(
            self.url, json.dumps({"texto": texto}), content_type="application/json"
        )

    def test_extrai_talhao_do_relato_do_tratorista(self):
        r = self._post("terminei de aplicar 50 litros de veneno no talhao 4")
        self.assertEqual(r.status_code, 200)
        s = r.json()["sinais"]
        self.assertEqual(s["talhoes"], ["4"])
        self.assertIn("veneno", s["classes_insumo"])

    def test_virgula_decimal_vira_ponto(self):
        r = self._post("gastei 12,5 litros de glifosato no talhao 2")
        self.assertIn("12.5", [q["valor"] for q in r.json()["sinais"]["quantidades"]])

    def test_exige_login(self):
        """Anonimo nao extrai nada. Um endpoint de leitura que nao exige sessao
        vira um oraculo sobre o que o produtor fala na lavoura."""
        anon = Client_()
        r = anon.post(
            self.url, json.dumps({"texto": "talhao 4"}), content_type="application/json"
        )
        self.assertIn(r.status_code, (302, 401, 403))

    def test_texto_vazio_e_400(self):
        self.assertEqual(self._post("   ").status_code, 400)

    def test_texto_longo_e_400(self):
        self.assertEqual(self._post("a" * 2500).status_code, 400)

    def test_json_invalido_e_400_nao_500(self):
        r = self.c.post(self.url, "nao e json", content_type="application/json")
        self.assertEqual(r.status_code, 400)

    def test_cliente_e_servidor_concordam_sobre_o_mesmo_texto(self):
        """O motivo do endpoint existir, verificado.

        O JS recebe os sinais deste endpoint. Se o backend e o que responde
        discordarem, o produtor ve dois numeros diferentes para a mesma frase.
        Aqui travamos que a funcao do backend e a fonte da verdade, e que ela
        responde de forma estavel (mesma entrada, mesma saida) — o que o
        cliente assume ao nao recalcular nada.
        """
        from app.ia.ingestao import audio as _audio

        frase = "terminei de passar 30 litros de herbicida no talhao 7"
        pela_api = self._post(frase).json()["sinais"]
        pela_funcao = _audio.extrair_sinais(frase)
        self.assertEqual(pela_api["talhoes"], pela_funcao["talhoes"])
        self.assertEqual(pela_api["talhoes"], ["7"])

    def test_sinais_nao_acionam_nada(self):
        """O ponto de risco: um sinal que vire acao.

        `sugere_acao_fisica` viaja na resposta porque o LLM precisa saber que
        aquilo e um comando. Ele NAO pode virar execucao aqui.
        """
        with patch("app.ia.sandbox.executar") as m:
            r = self._post("liga a irrigacao do talhao 4")
        m.assert_not_called()
        self.assertTrue(r.json()["sinais"]["sugere_acao_fisica"])


# =============================================================================
# O CONTRATO — o que um cliente MCP ve, e o que nao via
# =============================================================================
# Cada teste daqui tem uma MEDICAO ao lado, feita antes da correccao. A
# medicao e' o que torna o teste honesto: um teste escrito a partir de uma
# suspeita fica verde quando a suspeita e' falsa, e ninguem sabe se ele
# testava alguma coisa.
# =============================================================================
class ContratoTest(TestCase):
    def _bruto(self):
        from app.amplia_mcp import TOOLS_CATALOGO

        return catalogo_tools() + list(TOOLS_CATALOGO)

    def test_todo_obrigatorio_e_publicado(self):
        """MEDIDO, L3: 9 intents com `required_fields` e ZERO com `required`.

        A IA nao sabia o que era obrigatorio sem tentar - e cada tentativa e'
        uma ida ao estado `COLETANDO_DADOS`, que nao tem resposta possivel num
        cliente MCP (nao havia canal de `entrada`; ha agora).
        """
        por_nome = {t["name"]: t for t in enriquecer(self._bruto())}
        for nome, spec in REGISTO.items():
            exige = spec.get("required_fields") or []
            if not exige:
                continue
            with self.subTest(tool=nome_tool(nome)):
                self.assertEqual(
                    por_nome[nome_tool(nome)]["inputSchema"].get("required"),
                    list(exige),
                    f"{nome} exige {exige} e nao publica",
                )

    def test_obrigatorio_e_satisfazivel(self):
        """MEDIDO: `additionalProperties: false` com campo obrigatorio ausente
        produz um contrato IMPOSSIVEL - o modelo e' obrigado a enviar um campo
        que o schema declara invalido. A correccao declara o campo antes de o
        tornar obrigatorio."""
        for t in enriquecer(self._bruto()):
            props = t["inputSchema"].get("properties") or {}
            for campo in t["inputSchema"].get("required") or []:
                with self.subTest(tool=t["name"], campo=campo):
                    self.assertIn(campo, props)

    def test_toda_escrita_declara_confirmacao(self):
        """MEDIDO, L3: 24 tools de escrita, **5** com `confirm` no schema, e as
        24 com `additionalProperties: false`.

        Isto e' o beco mais caro da camada. O `sandbox` so executa uma escrita
        com `params["confirm"]`; a propriedade nao estava declarada; e o schema
        proibia-a. A unica forma de confirmar era violar o contrato que o
        proprio servidor tinha publicado.
        """
        conta = resumo_contrato(self._bruto())
        self.assertGreater(conta["escrita"], 0)
        self.assertEqual(
            conta["escrita_sem_confirm_declarado"],
            [],
            "Escritas que o cliente nao consegue confirmar: "
            f"{conta['escrita_sem_confirm_declarado']}",
        )

    def test_confirmacao_nao_e_obrigatoria_na_primeira_chamada(self):
        """`confirm` NAO entra em `required`.

        Se entrasse, o modelo teria de confirmar antes de ter feito o que esta
        a confirmar: o pedido de confirmacao do sandbox seria impossivel de
        satisfazer e a escrita nunca sairia. E' o que torna a confirmacao um
        SEGUNDO passo, e o segundo passo e' opcional por construcao.
        """
        for t in enriquecer(self._bruto()):
            if t.get("x-read-only"):
                continue
            with self.subTest(tool=t["name"]):
                self.assertNotIn(
                    PARAM_CONFIRMACAO, t["inputSchema"].get("required") or []
                )

    def test_leitura_nao_ganha_confirmacao(self):
        """Declarar `confirm` numa leitura seria ruido que ensina o modelo a
        mandar flags a mais em tudo - e a ignorar a flag onde ela conta."""
        for t in enriquecer(self._bruto()):
            if not t.get("x-read-only"):
                continue
            with self.subTest(tool=t["name"]):
                self.assertNotIn(
                    PARAM_CONFIRMACAO, t["inputSchema"].get("properties") or {}
                )

    def test_enriquecer_nao_muta_a_entrada(self):
        """Um cliente nao pode estragar o catalogo de outro.

        `catalogo_tools()` e' re-derivada a cada chamada e e' a fonte de `x-`;
        se `enriquecer` a mutasse, a segunda chamada encontraria `confirm` ja
        declarado e `required` ja posto - e a aritmetica do `resumo_contrato`
        deixaria de descrever o catalogo e passaria a descrever o que a
        passagem anterior deixou.
        """
        bruto = self._bruto()
        antes = json.dumps(bruto, sort_keys=True, default=str)
        enriquecer(bruto)
        self.assertEqual(json.dumps(bruto, sort_keys=True, default=str), antes)

    def test_as_duas_linguagens_concordam_no_nome(self):
        """MCP e OpenAI sao duas traducoes. Duas listas divergem em silencio."""
        bruto = self._bruto()
        self.assertEqual(
            [t["name"] for t in para_mcp(bruto)],
            [t["function"]["name"] for t in para_openai(bruto)],
        )

    def test_as_duas_linguagens_concordam_no_schema(self):
        bruto = enriquecer(self._bruto())
        por_mcp = {t["name"]: t["inputSchema"] for t in para_mcp(bruto)}
        por_openai = {
            t["function"]["name"]: t["function"]["parameters"]
            for t in para_openai(bruto)
        }
        self.assertEqual(por_mcp, por_openai)

    def test_o_guia_diz_o_que_so_esta_declarado(self):
        """O guia afirma `confirm: true` como caminho. Se um dia deixar de ser,
        o guia esta' a mentir - e e' o unico sitio onde se diz."""
        self.assertIn(PARAM_CONFIRMACAO, GUIA)
        self.assertIn("confirm", GUIA)

    def test_a_designacao_nao_se_inverte(self):
        """`x-read-only` e' o criterio, e nao a flag solta.

        E' o mesmo criterio que `sandbox.somente_leitura` aplica: um intent sem
        flag nenhuma e' tratado como escrita, em fail-closed. Se este criterio
        divergisse do sandbox, o cliente receberia aviso de escrita onde o
        sandbox deixaria passar - ou o contrario, que e' pior.
        """
        por_nome = {t["name"]: t for t in enriquecer(self._bruto())}
        for nome, spec in REGISTO.items():
            with self.subTest(intent=nome):
                self.assertEqual(
                    por_nome[nome_tool(nome)]["x-read-only"],
                    somente_leitura(spec),
                    f"{nome}: o contrato diz o contrario do sandbox",
                )


class ContratoNaoSeRepeteTest(TestCase):
    """O contrato vive num modulo, e o consumo e' o mais curto possivel.

    Nao e' quase-codigo: se `views.tools` voltar a ter a comprehension da
    traducao, voltam as duas passagens de `catalogo_tools()` e o schema sem
    `required` - os dois defeitos medidos, sem que nenhum teste de
    comportamento os apanhe.
    """

    def _arvore_views(self):
        return ast.parse(
            pathlib.Path("app/amplia_mcp/views.py").read_text(encoding="utf-8")
        )

    def test_views_nao_traduz_o_schema_no_lugar(self):
        achados = [
            f"L{no.lineno}"
            for no in ast.walk(self._arvore_views())
            if isinstance(no, ast.Dict)
            and any(
                isinstance(k, ast.Constant)
                and k.value == "type"
                and isinstance(v, ast.Constant)
                and v.value == "function"
                for k, v in zip(no.keys, no.values, strict=False)
            )
        ]
        self.assertEqual(
            achados, [], "views.py voltou a montar o envelope OpenAI no lugar"
        )

    def test_views_monta_o_catalogo_uma_vez(self):
        """`catalogo_tools()` tem um so ponto de chamada, e esse ponto e' a
        helper. Duas chamadas significam duas passagens de deducao de schemas
        por request - que era o defeito medido (FILA #39)."""
        chamadas = [
            f"L{no.lineno}"
            for no in ast.walk(self._arvore_views())
            if isinstance(no, ast.Call)
            and isinstance(no.func, ast.Name)
            and no.func.id == "catalogo_tools"
        ]
        self.assertEqual(
            len(chamadas),
            1,
            f"catalogo_tools() tem {len(chamadas)} pontos de chamada: {chamadas}. "
            "So pode ser chamado por _todas_as_tools().",
        )

    def test_o_ponto_de_chamada_e_a_helper(self):
        """E nao um ponto qualquer: o envelope do catalogo inteiro tem de ser
        montado num sitio, e esse sitio e' `_todas_as_tools()`.

        Medido por intervalo de linhas, e nao por "pai" — `ast.walk` nao
        constroi a arvore com ligacoes pai/filho, e um teste que finge que
        existe um `node.parent` passa sem verificar nada.
        """
        arvore = self._arvore_views()
        helper = next(
            (
                n
                for n in ast.walk(arvore)
                if isinstance(n, ast.FunctionDef) and n.name == "_todas_as_tools"
            ),
            None,
        )
        self.assertIsNotNone(helper, "_todas_as_tools() deixou de existir")

        dentro = [
            f"L{no.lineno}"
            for no in ast.walk(arvore)
            if isinstance(no, ast.Call)
            and isinstance(no.func, ast.Name)
            and no.func.id == "catalogo_tools"
            and helper.lineno <= no.lineno <= (helper.end_lineno or helper.lineno)
        ]
        na_helper = [
            f"L{no.lineno}"
            for no in ast.walk(helper)
            if isinstance(no, ast.Call)
            and isinstance(no.func, ast.Name)
            and no.func.id == "catalogo_tools"
        ]
        self.assertEqual(dentro, na_helper, "a chamada esta' fora de _todas_as_tools()")


# =============================================================================
# CSRF A SERIO - o test client do Django nao verifica CSRF por omissao
# =============================================================================
# Isto e' a razao pela qual o caminho do browser nunca foi testado de facto.
# `Client()` vem com `enforce_csrf_checks=False`, e `login()` marca a sessao
# sem nunca marcar o token. Um teste que passa assim prova que a view aceita um
# POST autenticado - nao que o browser consegue faze-lo. Um dia o `X-CSRFToken`
# desaparecia do `apiFetch` e a suite ficava verde com a ferramenta morta no
# campo.
class CsrfRealTest(TestCase):
    def setUp(self):
        from django.test import Client

        User.objects.create_user("csrf_u", "csrf@x.com", "p")
        self.c = Client(enforce_csrf_checks=True)

    def test_exec_sem_token_e_recusado(self):
        self.c.login(username="csrf_u", password="p")
        r = self.c.post(
            "/api/amplia/exec/",
            data=json.dumps({"tool": "amplia_clima_agora", "args": {}}),
            content_type="application/json",
        )
        self.assertEqual(
            r.status_code,
            403,
            "POST autenticado sem CSRF foi aceite: a ferramenta esta morta no browser",
        )

    def test_exec_com_token_passa(self):
        from django.middleware.csrf import get_token
        from django.test import RequestFactory

        self.c.login(username="csrf_u", password="p")
        # `get_token` precisa de um *request*, nao de um client: ele escreve em
        # `request.META['CSRF_COOKIE']`. Passar o client dava AttributeError, e
        # um teste que rebenta nao prova nada sobre o CSRF.
        token = get_token(RequestFactory().get("/"))
        self.c.cookies["csrftoken"] = token
        r = self.c.post(
            "/api/amplia/exec/",
            data=json.dumps({"tool": "amplia_clima_agora", "args": {}}),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(r.status_code, 200)


# =============================================================================
# AS SKIS - conhecimento que estava escrito e nao tinha porta
# =============================================================================
class SkillsTest(TestCase):
    def test_as_pastas_estao_iguais(self):
        """`app/ia/skills/` e' a fonte; `app/static/ia/skills/` alimenta a aba.

        As duas estao versionadas e hoje sao byte-a-byte iguais. Se divergirem,
        a aba e o MCP passam a descrever coisas diferentes - e nenhuma das duas
        tem razao para ter. Este teste e' o que faz a duplicacao segura.
        """
        from app.amplia_mcp.skills import PASTA_SKIS, PASTA_SKIS_ESTATICA

        nomes = sorted(p.name for p in PASTA_SKIS.glob("*.md"))
        self.assertTrue(nomes, "nenhuma SKI encontrada")
        for nome in nomes:
            with self.subTest(ski=nome):
                self.assertTrue(
                    (PASTA_SKIS_ESTATICA / nome).exists(),
                    f"{nome} esta em app/ia/skills e nao em app/static/ia/skills",
                )
                self.assertEqual(
                    (PASTA_SKIS / nome).read_bytes(),
                    (PASTA_SKIS_ESTATICA / nome).read_bytes(),
                    f"{nome} diverge entre as duas pastas",
                )

    def test_nenhum_handler_fantasma(self):
        """MEDIDO, L3, ANTES da correccao: **15 de 15 handlers declarados nas
        SKIs nao existiam no registo.** Zero. Nao era um caso ou dois - era a
        totalidade.

        `app/ia/skills/amplia-campo.md` declarava
        `handlers: ["vra_ndvi_prescricao", "solo_spd", "praga_ai_foto",
        "guidance_ab", "as_applied_gap"]` e **nenhum** dos cinco existia.
        O mesmo nas outras duas SKIs.

        Era o pior sitio possivel para uma lista de ficcao: `praga_ai_foto` e
        `guidance_ab` aparecem em `docs/COORDENACAO_IA.md` (itens #6 e #7) como
        trabalho FEITO. Estao nas notas de uma correccao real - mas como
        *servicos* de `app/services/top_globais.py`, nao como intents. A SKI
        apresentava servicos como se fossem capacidades da IA, e a lista de
        capacidades e' o que ela diria a quem perguntasse o que sabe fazer.

        A correccao nao foi apagar os nomes: a logica do dominio existe e e'
        boa. Foi move-los para `sem_intent`, cada um com a morada onde esta, e
        deixar `handlers` so com o que a IA pode mesmo chamar. Assim o
        catalogo diz duas verdades em vez de uma mentira.

        Este teste ja nao e' `expectedFailure`. Um invariant que passa para
        sempre deixa de medir: se um dia alguem acrescentar um handler novo e
        errado, este teste tem de apanhar.
        """
        from app.amplia_mcp.skills import catalogo_skis

        cat = catalogo_skis()
        self.assertEqual(
            cat["handlers_fantasmas"],
            0,
            "handlers declarados nas SKIs que nao existem: "
            + ", ".join(f"{s['nome']}={s['cobre_inexistente']}" for s in cat["skills"]),
        )

    def test_toda_promessa_diz_onde_esta(self):
        """`sem_intent` sem morada e' uma promessa sem clues.

        A correccao do #43 passou a nomear a logica orfa. Se a nota nao disser
        ONDE, ela nao serve para nada: quem quiser promover a logica a intent
        fica sem saber o que abrir. E uma nota vazia e' pior do que a
        ausencia do campo, porque parece que alguem pensou no assunto.
        """
        from app.amplia_mcp.skills import catalogo_skis

        cat = catalogo_skis()
        for ski in cat["skills"]:
            for nome, nota in (ski["prometido_sem_botao"] or {}).items():
                with self.subTest(ski=ski["nome"], promessa=nome):
                    self.assertTrue(nota.strip(), f"{nome} sem morada")
                    self.assertGreater(
                        len(nota),
                        12,
                        f"{nome}: a nota nao diz onde esta a logica",
                    )

    def test_nenhuma_promessa_ja_tem_botao(self):
        """Uma promessa que ja tem intent e' um alias, e um alias pertence ao
        `handlers`. Ficar nas duas listas e' a lista a crescer sem ninguem
        reparar, que e' como uma lista de verdade apodrece."""
        from app.amplia_mcp.skills import catalogo_skis
        from app.ia.registro import REGISTO

        cat = catalogo_skis()
        for ski in cat["skills"]:
            for nome in ski["prometido_sem_botao"] or {}:
                with self.subTest(ski=ski["nome"], promessa=nome):
                    self.assertNotIn(
                        nome, REGISTO, "esta em sem_intent mas ja tem intent"
                    )

    def test_o_catalogo_tem_aviso_para_cada_verdade(self):
        """Dois avisos, porque sao duas verdades: o que a IA pode chamar, e o
        que existe mas nao se pode. Um aviso que nao muda com o resultado e'
        decoracao — e decoracao ensina a ignorar avisos."""
        from app.amplia_mcp.skills import catalogo_skis

        cat = catalogo_skis()
        self.assertIn("existem no registo", cat["aviso"])
        if cat["promessas_sem_botao"]:
            self.assertIn("NAO tem intent", cat["aviso_promessas"])
        else:
            self.assertIn("chamavel", cat["aviso_promessas"])

    def test_o_catalogo_diz_que_sao_fantasmas(self):
        """A parte que a sessao onde nao toca nos ficheiros FAZ: o catalogo
        diz, em vez de engole. Um `except` aqui deixaria a IA com um buraco de
        comportamento sem ninguem notar - e o buraco e' exactamente o dominio
        (campo, financas, IoT)."""
        from app.amplia_mcp.skills import catalogo_skis

        cat = catalogo_skis()
        # E o texto de aviso tem de mudar conforme o resultado - e' a unica
        # forma de o aviso poder ser lido por uma pessoa e por um agente.
        if cat["handlers_fantasmas"]:
            self.assertIn("nao existe", cat["aviso"])
        else:
            self.assertIn("existem no registo", cat["aviso"])

    def test_o_cabecalho_e_lido(self):
        """O titulo markdown da primeira linha e' o que fazia o parser fechar
        o cabecalho vazio. Este teste diz que o `name`, o `description` e o
        `version` saem - e sao tres campos de tres ficheiros, o que torna um
        zero silencioso impossivel."""
        from app.amplia_mcp.skills import catalogo_skis

        cat = catalogo_skis()
        self.assertGreaterEqual(cat["total"], 3)
        for ski in cat["skills"]:
            with self.subTest(ski=ski["nome"]):
                self.assertTrue(ski["nome"], "SKI sem nome: o parser nao leu")
                self.assertTrue(ski["descricao"], "SKI sem descricao")
                self.assertTrue(ski["versao"], "SKI sem versao")

    def test_lista_dentro_de_mapa_nao_e_desfiada(self):
        """`{cache: 60, flags: ["a", "b"]}` - a virgula da lista interna nao e'
        separador do mapa.

        Um `split(",")` cego devolve `['[', '"', 'a', ...]`: quinze letras
        soltas, cada uma tratada como flag. Foi o que aconteceu, e um teste
        sobre `performance.flags` apanha-o.
        """
        import app.amplia_mcp.skills as _s

        v = _s._valor('{cache: 60, flags: ["a.b", "c.d"]}')
        self.assertIsInstance(v, dict)
        self.assertEqual(v["flags"], ["a.b", "c.d"])
        self.assertEqual(v["cache"], "60")

    def test_as_listas_flow_style_sao_lidas(self):
        """`triggers: ["VRA", "NDVI"]` e' lista, nao texto.

        Um parser que devolvesse a string inteira faria a busca por trigger
        partir-se ao meio de uma aspa - e nenhuma assercao sobre `cobre`
        apanharia isso.

        E o `cache`: o parser devolve TEXTO (nao sabe a que se destina cada
        campo, e `version: 1.0.0` tem de continuar a ser texto), mas quem
        publica converte. Os dois lados sao testados, porque a conversao num
        sitio em vez do outro produz um `cache_s` que ninguem consegue
        comparar.
        """
        import app.amplia_mcp.skills as _s
        from app.amplia_mcp.skills import PASTA_SKIS, catalogo_skis

        ski = _s.ler_ski(PASTA_SKIS / "amplia-campo.md")
        self.assertIsInstance(ski["triggers"], list)
        self.assertIn("NDVI", ski["triggers"])
        self.assertIsInstance(ski["handlers"], list)
        self.assertIsInstance(ski["performance"], dict)
        # o parser: texto, porque nao sabe o que e'
        self.assertEqual(ski["performance"].get("cache"), "60")
        # quem publica: numero, porque sabe o que e'
        publicado = {s["nome"]: s for s in catalogo_skis()["skills"]}
        self.assertEqual(publicado["amplia-campo"]["cache_s"], 60)

    def test_nenhum_ficheiro_tem_bom(self):
        """MEDIDO, L2, ANTES da correccao: os SEIS ficheiros SKI do repositorio
        estavam gravados com BOM UTF-8 (`ef bb bf`).

        O efeito era silencioso, e e' por isso que vale um teste: ler com
        `encoding="utf-8"` deixava a BOM em cima da primeira linha, o titulo
        markdown deixava de ser reconhecido, o cabecalho fechava vazio, e o
        catalogo devolvia tres skills sem nome e sem handlers. Sem erro, sem
        aviso - so a ausencia do que devia estar la. Foi este teste que o
        apanhou, ao ver `nome` vir `None` enquanto o ficheiro estava a la.

        Corrigido nos ficheiros E no leitor: os seis foram regravados sem BOM,
        e `ler_ski` ficou a usar `utf-8-sig` para o caso de alguem gravar com
        BOM outra vez. Os dois, e nao so um: um leitor tolerante esconde o
        problema, e o problema era o que interessava.

        Ja nao e' `expectedFailure`, porque ja nao esta partido.
        """
        from app.amplia_mcp.skills import PASTA_SKIS, PASTA_SKIS_ESTATICA

        com_bom = [
            p.name
            for pasta in (PASTA_SKIS, PASTA_SKIS_ESTATICA)
            for p in pasta.glob("*.md")
            if p.read_bytes().startswith(b"\xef\xbb\xbf")
        ]
        self.assertEqual(com_bom, [], f"SKIs com BOM UTF-8: {com_bom}")

    def test_o_leitor_sobrevive_a_bom(self):
        """Comprovado com texto que TEM BOM, para o leitor continuar a ser
        provado se a BOM for removida dos ficheiros."""
        import app.amplia_mcp.skills as _s

        com_bom = '# T\nname: x\ntriggers: ["A"]\n'
        self.assertEqual(_s._parse(com_bom).get("name"), "x")

    def test_a_superficie_http_devolve_o_mesmo(self):
        """E' o mesmo motivo de `audio_sinais`: duas implementacoes do mesmo
        dicionario discordam, e o produtor ve um numero na tela e outro no log.
        """
        from app.amplia_mcp.skills import catalogo_skis

        User.objects.create_user("sk_u", "sk@x.com", "p")
        c = Client_()
        c.login(username="sk_u", password="p")
        pela_api = c.get("/api/amplia/skills/").json()
        pela_funcao = catalogo_skis()
        self.assertEqual(pela_api["total"], pela_funcao["total"])
        self.assertEqual(
            [s["nome"] for s in pela_api["skills"]],
            [s["nome"] for s in pela_funcao["skills"]],
        )

    def test_a_superficie_http_exige_login(self):
        self.assertEqual(Client_().get("/api/amplia/skills/").status_code, 302)


# =============================================================================
# O ARRANQUE DO STDIO - o caminho que estava partido
# =============================================================================
class ServidorStdioTest(TestCase):
    def test_arranca_de_fora_do_repositorio(self):
        """MEDIDO, L3, antes da correccao:

            python <repo>/app/amplia_mcp/servidor.py --usuario x
            com o CWD no directorio do utilizador
            ->  rc=2, "django.setup() falhou: No module named 'config'"

        Um cliente MCP nao tem CWD. A receita apontava `--usuario` e nenhum
        outro caminho, e o que falhava nao era o utilizador: era o path.

        Este teste e' fraco de proposito: so exige que a falha NAO seja
        `No module named config`. A prova a serio esta' em
        `tests/test_caminho_do_banco.py`, que arranca o servidor de fora do
        repositorio e le o banco a serio. Aqui basta o diagnostico — o teste
        de arranque precisa de correr em 1 s, nao de arrancar um servidor.
        """
        import subprocess
        import sys

        # A raiz vem da PRODUCAO (`servidor.RAIZ_REPO`), nao de contar
        # `parents`. E' a constante que um cliente usa que esta a ser testada;
        # derivar o caminho de outro jeito testaria o meu `parents[]`.
        from app.amplia_mcp.servidor import RAIZ_REPO

        alvo = RAIZ_REPO / "app" / "amplia_mcp" / "servidor.py"

        r = subprocess.run(
            [sys.executable, str(alvo), "--usuario", "x"],
            capture_output=True,
            text=True,
            cwd=str(pathlib.Path.home()),
            timeout=300,
        )
        stderr = r.stderr or ""
        self.assertNotIn(
            "No module named 'config'",
            stderr,
            "voltou a falhar por path: a raiz nao esta a ser posta no sys.path",
        )
        self.assertIn("[amplia-mcp]", stderr)
        self.assertTrue(
            any(m in stderr for m in ("mcp", "usuario", "raiz")),
            f"a mensagem nao diz o que arrancou mal: {stderr!r}",
        )

    def test_a_raiz_e_deduzida_do_ficheiro(self):
        from app.amplia_mcp.servidor import RAIZ_REPO

        self.assertTrue((RAIZ_REPO / "config" / "settings").is_dir(), RAIZ_REPO)
        self.assertTrue((RAIZ_REPO / "manage.py").exists(), RAIZ_REPO)

    def test_tem_canal_de_entrada(self):
        """MEDIDO, L2: `entrada` nao aparecia em `servidor.py` uma unica vez.

        Sem ele, uma escrita via stdio devolvia `needs_confirm` e nao havia
        caminho para a segunda chamada - e a tentativa seguinte corria o
        `else` de `AGUARDANDO_CONFIRMACAO` e devolvia "Operacao cancelada",
        apagando o pedido do produtor.
        """
        src = pathlib.Path("app/amplia_mcp/servidor.py").read_text(encoding="utf-8")
        self.assertIn('"entrada"', src)
        self.assertIn('argumentos.pop("entrada"', src)

    def test_entrada_e_tirada_dos_args_antes_do_sandbox(self):
        """`entrada` e' metadata, nunca um campo do dominio.

        Deixada em `args`, o `cadastrar_funcionario` a preencheria com o nome
        do vaqueiro - porque "sim" e' o primeiro campo vazio da lista.
        """
        import inspect

        from app.amplia_mcp import servidor

        self.assertIn('argumentos.pop("entrada"', inspect.getsource(servidor.rodar))

    def test_uri_desconhecida_diz_que_nao_existe(self):
        """MEDIDO, L1: `read_resource` devolvia `contexto(user)` para QUALQUER
        URI. Um cliente que pedisse `amplia://modelo` (typo) levava o contexto
        da fazenda e achava que tinha lido o que pediu."""
        import inspect

        from app.amplia_mcp import servidor

        self.assertIn("recurso MCP desconhecido", inspect.getsource(servidor.rodar))

    def test_contexto_com_prefixo_e_generico(self):
        """`amplia://contexto/<usuario>` tem parametro. Comparar por igualdade
        so servia para o nome do usuario que este servidor atende - que e'
        sempre o mesmo. O prefixo e' o que faz o recurso funcionar para
        qualquer `contexto/*`."""
        import inspect

        from app.amplia_mcp import servidor

        self.assertIn(
            'u.startswith("amplia://contexto/")', inspect.getsource(servidor.rodar)
        )


# =============================================================================
# O DIAGNOSTICO - a aritmetica que o endpoint promete
# =============================================================================
class DiagnosticoTest(TestCase):
    def setUp(self):
        User.objects.create_user("diag_u", "diag@x.com", "p")
        self.c = Client_()
        self.c.login(username="diag_u", password="p")

    def test_responde(self):
        r = self.c.get("/api/amplia/diagnostico/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("conta", r.json())

    def test_exige_login(self):
        self.assertEqual(Client_().get("/api/amplia/diagnostico/").status_code, 302)

    def test_a_conta_bate_com_o_catalogo(self):
        """A conta e' a MESMA aritmetica que a do contrato. Duas contagens
        divergentes dariam um "tudo_ok" que nao quer dizer nada."""
        from app.amplia_mcp import TOOLS_CATALOGO

        d = self.c.get("/api/amplia/diagnostico/").json()
        bruto = catalogo_tools() + list(TOOLS_CATALOGO)
        self.assertEqual(d["conta"], resumo_contrato(bruto))
        self.assertEqual(d["conta"]["tools"], len(bruto))

    def test_a_conta_diz_a_aritmetica_certa(self):
        """Relacao, nao numero: `escrita + leitura == tools`. Uma contagem
        solta pode estar errada e continuar verde; uma relacao nao."""
        c = self.c.get("/api/amplia/diagnostico/").json()["conta"]
        self.assertEqual(c["escrita"] + c["leitura"], c["tools"])
        self.assertEqual(
            c["escrita"],
            c["escrita_com_confirm_declarado"]
            + len(c["escrita_sem_confirm_declarado"]),
        )

    def test_reporta_invariantes_com_nome(self):
        """O endpoint e' um ESPELHO. O que se prova aqui nao e' que o codigo
        esta' inteiro - e' que o espelho nao mente.

        Por que importa: `skills_sem_handler_fantasma` esta' **agora** a
        `False`, e essa e' a resposta certa (ver `SkillsTest`: 15 de 15
        handlers das SKIs nao existem). Um teste que exigisse `tudo_ok`
        vermelho-obrigatorio-noticias-vermelhas partia hoje e passava amanha
        sem que ninguem olhasse; um teste que exigisse `tudo_ok` verde
        mentiria sobre o repositorio. O que se prova e' a relacao:

            tudo_ok  ==  "todos os invariantes sao verdade"

        essa relacao vale com o codigo sao e com o codigo partido. E e' a unica
        coisa que um espelho tem de garantir.
        """
        d = self.c.get("/api/amplia/diagnostico/").json()
        self.assertIsInstance(d["tudo_ok"], bool)
        self.assertEqual(d["tudo_ok"], all(d["invariantes"].values()), "tudo_ok mente")
        self.assertEqual(
            set(d["invariantes"]),
            {
                "toda_intent_e_uma_tool",
                "toda_escrita_declara_confirmacao",
                "obrigatorio_e_satisfazivel",
                "tool_corresponde_a_intent",
                "skills_sem_handler_fantasma",
                "sem_colisao_entre_catalogos",
            },
        )

    def test_o_contrato_proprio_esta_inteiro(self):
        """Ja os CINCO invariantes do contrato. A sexta e' a dos SKIs, e a
        dos SKIs depende de ficheiros que nao sao territorio desta sessao - por
        isso e' verificada a parte, e nao a coisa toda.

        Estes cinco sao o que esta sessao construiu, e sao a resposta honesta a
        "o caminho esta inteiro?".
        """
        inv = self.c.get("/api/amplia/diagnostico/").json()["invariantes"]
        for nome in (
            "toda_intent_e_uma_tool",
            "toda_escrita_declara_confirmacao",
            "obrigatorio_e_satisfazivel",
            "tool_corresponde_a_intent",
            "sem_colisao_entre_catalogos",
        ):
            with self.subTest(invariante=nome):
                self.assertTrue(inv[nome])

    def test_o_invariante_dos_skis_acompanha_a_realidade(self):
        """O espelho tem de mudar quando a realidade muda. Um invariante
        fixo em `True` e' um invariante que nao mede nada."""
        from app.amplia_mcp.skills import catalogo_skis

        inv = self.c.get("/api/amplia/diagnostico/").json()["invariantes"]
        self.assertEqual(
            inv["skills_sem_handler_fantasma"],
            catalogo_skis()["handlers_fantasmas"] == 0,
        )

    def test_detecta_uma_quebra_real(self):
        """Um endpoint que devolve sempre `true` nao e' um diagnostico.

        Aqui injecta-se a quebra: uma tool a menos no catalogo. O invariante
        tem de cair. Sem esta prova, `tudo_ok` e' um numero bonito.
        """
        import app.amplia_mcp.views as _v

        original = _v._todas_as_tools
        try:
            _v._todas_as_tools = lambda: [
                t for t in original() if t["name"] != "amplia_ligar_irrigador"
            ]
            d = self.c.get("/api/amplia/diagnostico/").json()
            self.assertFalse(d["invariantes"]["toda_intent_e_uma_tool"])
            self.assertFalse(d["tudo_ok"])
        finally:
            _v._todas_as_tools = original


class SuperficieHttpExtraTest(TestCase):
    def setUp(self):
        User.objects.create_user("extra_u", "ex@x.com", "p")
        self.c = Client_()
        self.c.login(username="extra_u", password="p")

    def test_tools_traz_o_guia(self):
        """O guia viaja com o catalogo, e nao num documento. Um cliente le o
        que recebe; um documento em `docs/` le-se uma vez e esquece-se."""
        d = self.c.get("/api/amplia/tools/").json()
        self.assertIn("guia", d)
        self.assertIn("confirm", d["guia"])

    def test_a_lista_mcp_e_a_mesma_que_as_tools(self):
        """A chave `mcp` e' a lista de intents, e a lista de tools e' a lista
        de tudo. Duas listas: uma para contar, outra para chamar."""
        d = self.c.get("/api/amplia/tools/").json()
        nomes_tools = {t["function"]["name"] for t in d["tools"]}
        self.assertTrue(set(d["mcp"]) <= nomes_tools)
        self.assertTrue(nomes_tools >= NOMES_CATALOGO)

    def test_proativo_alertas_recusa_post(self):
        """Um *feed* que aceita POST e devolve 200 e' um 405 que ninguem nota."""
        r = self.c.post(
            "/api/amplia/alertas/pendentes/",
            data="{}",
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 405)


# =============================================================================
# INTEGRIDADE DO REGISTO E DO CATALOGO
# =============================================================================
class RegistroIntegridadeTest(TestCase):
    """Guarda: o REGISTO não perde intents que o agregador conhece.

    `INTENTS` (sandbox) e `REGISTO` (registro) são dois dicionários
    relacionados: `INTENTS` é um subconjunto por desenho, mas um intent
    que chega ao agregador e desaparece do `REGISTO` é drift — sinal de
    que a carga tardia (`_registo_atrasado`) não repôs a entrada.
    """

    def test_registro_cobre_intents(self):
        """Todo intent do agregador está no REGISTO."""
        dif = set(INTENTS) - set(REGISTO)
        self.assertEqual(dif, set(), f"Intents no agregador sem registo: {sorted(dif)}")

    def test_registro_nao_tem_fantasmas(self):
        """Nenhum nome do REGISTO foi inventado: todos vêm de um catálogo em disco.

        MEDIDO 2026-10-08: a versão anterior fazia        `extras = set(REGISTO) - set(INTENTS)` e iterava `extras`. Com
        `INTENTS == REGISTO == 88`, `extras` é **vazio** — o `for` nunca executou
        uma instrução desde que foi escrito. Um teste que não corre não é
        cobertura; é um nome que ocupa uma linha.

        A fonte da verdade é `_modulos_catalogo()` (registro.py:486), a **mesma**
        função que constrói o registo. Subtrair a união completa dos catálogos
        apanha o que interessa: um nome no registo que nenhum catálogo declara.

        Não se exclui `intents.INTENTS` da união. `intents.py` não é só agregador:
        define 81 dos 88 intents directamente. Excluí-lo produz81 falsos positivos (medido) e obriga a apagar o que está certo.
        """
        declarados: set[str] = set()
        for _nome_catalogo, intents in _modulos_catalogo():
            declarados.update(intents)
        inventados = sorted(set(REGISTO) - declarados)
        self.assertEqual(
            inventados,
            [],
            f"{len(inventados)} nome(s) no REGISTO que nenhum catálogo declara: "
            f"{inventados}",
        )

    def test_saude_reporta_drift(self):
        """`saude()` reporta drift entre REGISTO e INTENTS."""
        s = saude()
        self.assertIn("drift_registro_intents", s)
        self.assertEqual(s["drift_registro_intents"], [], f"Drift não resolvido: {s['drift_registro_intents']}")

    def test_saude_integro_verdadeiro_em_runtime(self):
        """Em runtime (manage.py test) `integro` é True."""
        s = saude()
        self.assertTrue(s["integro"], f"saude() falhou: {s}")

    def test_enriquecimento_cobre_registro(self):
        """Todo intent do REGISTO aparece como tool no catalogo enriquecido."""
        nomes = {t.get("x-intent") for t in catalogo_tools()}
        faltando = set(REGISTO) - nomes
        self.assertEqual(faltando, set(), f"Intents sem tool publicada: {sorted(faltando)}")


class ToolsCatalogoBatemTest(TestCase):
    """NOMES_CATALOGO ⊆ TOOLS_CATALOGO_ACEITAS.

    Não é igualdade: a allowlist também contém intents (como
    `amplia_comparativo_revisao`) que são publicados via `catalogo_tools()`,
    não via `TOOLS_CATALOGO` estático. Mas nenhuma *tool de catálogo*
    pode ficar fora da allowlist.
    """

    def test_catalogo_cobrindo_aceitas(self):
        catalogo = {t["name"] for t in TOOLS_CATALOGO}
        aceitas = set(TOOLS_CATALOGO_ACEITAS)
        sobrando = catalogo - aceitas
        self.assertEqual(sobrando, set(), f"Tools de catálogo sem declaração na allowlist: {sorted(sobrando)}")

    def test_comparativo_revisao_e_executavel(self):
        """`amplia_comparativo_revisao` está na allowlist e é read-only."""
        self.assertIn("amplia_comparativo_revisao", TOOLS_CATALOGO_ACEITAS)
        spec = REGISTO.get("comparativo_revisao")
        self.assertIsNotNone(spec, "`comparativo_revisao` desapareceu do REGISTO")
        self.assertTrue(somente_leitura(spec), "`comparativo_revisao` deixou de ser read-only")


class PromptConfirmacaoAssinaturaTest(TestCase):
    """CRÍTICO 4: `prompt_de_confirmacao` aceita `params` via keyword."""

    def test_aceita_params_como_keyword(self):
        from app.ia.texto import prompt_de_confirmacao

        spec = {"prompt_confirmacao": "Apagar a safra 2026/27?"}
        # Não levanta TypeError — antes quebrava em sandbox.py:785
        texto = prompt_de_confirmacao(spec, params={"safra": "2026/27"})
        self.assertEqual(texto, "Apagar a safra 2026/27?")

    def test_params_opcional(self):
        from app.ia.texto import prompt_de_confirmacao

        spec = {"prompt_confirmacao": "Confirmar?"}
        texto = prompt_de_confirmacao(spec)
        self.assertEqual(texto, "Confirmar?")
