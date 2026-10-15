"""
Testes da COMUNICAÇÃO entre a IA e o servidor — FILA #27, #28.

Este ficheiro é separado de `tests.py` por uma razão prática e não
estética: `tests.py` está a ser editado por outra sessão, e dois autores no
mesmo ficheiro é a colisão que `docs/COORDENACAO_IA.md` existe para
impedir. Ficheiro novo, zero sobreposição.

O que estes testes travam, e porquê cada um existe
---------------------------------------------------
A camada `amplia_mcp` tinha uma propriedade que os testes existentes não
tocavam: ela responde bem a quem lhe pergunta, e não se importa de não ter
utilizador nenhum a perguntar.

O defeito medido (L3, 13/13) foi este. O modelo local — SmolLM2 de 1,7 B, a
correr no browser — recebia do seu system prompt uma lista escrita à mão com
treze nomes de tool: `navegar`, `consultar`, `criar`, `irrigacao`,
`excluir`… As treze não existem. Nenhuma. E as 79 verdadeiras não estavam em
lado nenhum do prompt que o modelo lê.

Consequência medida, ponta a ponta, por HTTP: **toda** a tool call que o
modelo conseguia escrever voltava `tool_fora_do_catalogo`. Não era uma tool
que às vezes falhava — era a ponte inteira entre o modelo e as mãos cortada.

Cada teste abaixo é uma das duas metades da correcção:
  * `sugestoes` — o servidor responde com o nome CERTO quando o modelo
    acerta o assunto e erra o nome. Isto funciona hoje, sem tocar no
    `ia-local.js`, que é de outra IAs.
  * `vocabulario` — os nomes verdadeiros, todos, num texto que cabe na
    janela do modelo, derivados do catálogo a cada chamada.
"""

import json

from django.contrib.auth.models import User
from django.test import Client, TestCase

from app.amplia_mcp import (
    _com_aviso,
    _linha_grupo,
    nome_tool,
    sugerir_tools,
    vocabulario,
)
from app.ia.sandbox import INTENTS

# Os nomes que o `IA_SYSTEM` de `ia-local.js:4116-4128` ensinava ao modelo.
# Estão escritos aqui à mão de propósito: é uma lista de ASSERÇÃO, não de
# comportamento. A lista de produção tem de ser derivada — a de teste pode
# ser fixa, porque o que se quer provar é que ela deixou de estar em lado
# nenhum do prompt.
NOMES_ENSINADOS_ANTES = (
    "navegar",
    "consultar",
    "criar",
    "iniciar_cadastro",
    "irrigacao",
    "atualizar",
    "excluir",
    "relatorio",
    "buscar_web",
    "abrir_pagina",
    "buscar_dados",
    "criar_operacao",
    "buscar_web_agro",
)


class SugestaoDeToolTest(TestCase):
    """O servidor deixa de ser uma parede quando o modelo erra o nome."""

    def test_phantom_recebe_o_nome_certo(self):
        """O caso medido: `irrigacao` existe como assunto, não como tool.

        O modelo aprendeu o assunto certo e o nome errado. A resposta antiga
        ("tool fora do catalogo") não lhe dizia o que escrever a seguir, e o
        produtor via um erro de máquina em vez de uma resposta.
        """
        r = sugerir_tools("amplia_irrigacao")
        self.assertIn("amplia_ligar_irrigador", r)
        self.assertIn("amplia_desligar_irrigador", r)

    def test_sugere_tambem_sem_o_prefixo(self):
        """O modelo esquece o `amplia_` mais vezes do que o inventa.

        O `ia-local.js` normaliza o prefixo antes de enviar, mas um cliente
        MCP externo não o faz — e a resposta tem de servir os dois.
        """
        self.assertEqual(sugerir_tools("irrigacao"), sugerir_tools("amplia_irrigacao"))

    def test_sugestoes_sao_nomes_que_existem(self):
        """Uma sugestão errada é pior do que nenhuma.

        Se `sugerir_tools` devolvesse um nome inventado, o modelo obedeceria
        e o fantasma mudava de nome em vez de desaparecer.
        """
        for nome in NOMES_ENSINADOS_ANTES:
            with self.subTest(nome=nome):
                for sugestao in sugerir_tools(nome):
                    self.assertTrue(
                        sugestao.startswith("amplia_"),
                        f"{sugestao} nao tem o prefixo",
                    )
                    self.assertIn(
                        sugestao.removeprefix("amplia_"),
                        INTENTS,
                        f"{sugestao} foi sugerida mas nao existe no catalogo",
                    )

    def test_nada_similiar_nao_inventa_nada(self):
        """Palavra sem relação com nenhuma tool devolve lista vazia.

        O contrário — sugerir sempre os cinco primeiros — faria o modelo
        receber nomes plausíveis e errados em vez de aprender que não há
        nada parecido.
        """
        self.assertEqual(sugerir_tools("amplia_xqzzw"), [])

    def test_erro_via_http_traz_as_sugestoes(self):
        """Ponta a ponta: a resposta de erro carrega o caminho de recuperação.

        É esta a propriedade que muda o que o produtor vê. Sem `sugestoes`, o
        `toolCallGovernada` devolve a string de erro ao ecrã. Com elas, o
        modelo tem o nome certo no mesmo turno.
        """
        User.objects.create_user("sug", "sug@x.com", "p")
        c = Client()
        c.login(username="sug", password="p")
        r = c.post(
            "/api/amplia/exec/",
            data=json.dumps({"tool": "amplia_irrigacao", "args": {}}),
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 200)
        j = r.json()
        self.assertFalse(j["ok"])
        self.assertEqual(j["codigo"], "tool_fora_do_catalogo")
        self.assertIn("amplia_ligar_irrigador", j["sugestoes"])
        # O total é informação de catálogo, e serve o modelo a decidir se
        # vale a pena tentar de novo.
        self.assertEqual(j["total_tools"], len(INTENTS))

    def test_tool_sem_prefixo_tambem_traz_sugestoes(self):
        """`tool_desconhecida` e `tool_fora_do_catalogo` são o mesmo problema
        visto de dois lados, e os dois precisam da mesma ajuda."""
        User.objects.create_user("sug2", "sug2@x.com", "p")
        r = executar("sug2", "irrigacao")
        self.assertEqual(r["codigo"], "tool_desconhecida")
        self.assertIn("amplia_ligar_irrigador", r["sugestoes"])


class VocabularioTest(TestCase):
    """Os nomes verdadeiros, num texto que o modelo de 1,7 B aguenta."""

    # ─────────────────────────────────────────────────────────────────────
    # PORQUÊ ESTE tearDown EXISTE
    #
    # MEDIDO 2026-10-05. `test_derivado_e_nao_escrito` insere um intent em
    # `INTENTS` e remove-o num `finally`. O `finally` está certo — mas
    # `INTENTS` **é** `REGISTO` (verificado: `REGISTO is INTENTS` -> True),
    # ou seja, é o dicionário partilhado de que dependem
    # `CatalogoHigieneTest::test_flags_seguem_a_relacao` e
    # `SmokeTodasIntentsTest::test_smoke_55_intents`, noutro ficheiro.
    #
    # Com o `finally`, a chave nova sai. **Mas `spec = dict(INTENTS[...])` é
    # uma cópia rasa**: se alguém mutar um valor dentro de `spec`, muda o
    # original e o `pop` só remove a chave — não desfaz a mutação.
    #
    # O sintoma observado era subtil e enganador: as duas falhas de
    # catálogo passavam isoladas e falhavam na suite completa, e o sintoma
    # parecia "o registo tem flags erradas" quando o registo estava certo.
    #
    # A protecção é de classe, não de teste: snapshot antes, restaura
    # depois, mesmo que o teste rebente a meio. Um `finally` dentro do
    # teste protege o teste; um `tearDown` protege **os outros testes**.
    # ─────────────────────────────────────────────────────────────────────

    def setUp(self):
        # Cópia rasa de topo: chega, porque o que se restaura são as CHAVES
        # (entradas e saídas), não os valores.
        self._intents_antes = set(INTENTS)

    def tearDown(self):
        # Remove o que apareceu. Não toca em valores: um teste que mutou
        # um valor não é restaurado aqui, e não fingimos que é.
        #
        # `super().tearDown()` vai no fim para não saltar a limpeza do
        # Django se a remoção levantar.
        for nome in set(INTENTS) - self._intents_antes:
            INTENTS.pop(nome, None)
        super().tearDown()

    def test_todos_os_intents_estao_no_texto(self):
        """A RELAÇÃO que importa: nenhum nome pode faltar.

        A propriedade de que a IA precisa é "consigo ver tudo o que existe".
        Um vocabulário que seja correcto no total e deixe um nome de fora é
        pior do que não existir — porque não há como o modelo saber o que
        lhe falta.
        """
        v = vocabulario()
        faltam = [n for n in INTENTS if n not in v["texto"]]
        self.assertEqual(faltam, [], f"{len(faltam)} intents nao chegam ao modelo")

    def test_total_conta_nomes_e_nao_assuntos(self):
        """`len(dict)` é o número de assuntos. O número que interessa é o de
        ferramentas, e os doisomlham-se — 33 contra 76 medidos.

        Um total que não bate com o catálogo é um número em que ninguém pode
        confiar, e é pior do que nenhum.
        """
        v = vocabulario()
        self.assertEqual(v["total"], len(INTENTS))
        self.assertLess(v["namespaces"], v["total"])

    def test_cabe_na_janela_do_modelo_que_a_le(self):
        """O orçamento é do modelo que lê, não do servidor que escreve.

         SmolLM2 de 1,7 B: janela de 4 096 tokens. Com o catálogo completo
         (~8 700 tokens medidos) não havia conversa possível. O vocabulário
         tem de caber com espaço para o contexto do sistema e o histórico.

         O teste mede uma RELAÇÃO, não um número. Um número literal aqui
         seria um change-detector: passaria a falhar no dia em que se juntasse
         uma tool, e a pessoa que o viu partiria ou apagava o teste ou
        subia o teto — as duas coisas erradas. A relação é o que importa:
         o vocabulário tem de ser uma fracção pequena do catálogo e da janela.
        """
        v = vocabulario()

        # 1. Por omissão, cabe. O chamador não deve ter de saber o número.
        self.assertTrue(v["cabe"], "o vocabulario por omissao nao cabe")

        # 2. Menos de metade da janela de 4 096 tokens. `4 caracteres por
        #    token` é a regra grossa para português com pontuação; com metade
        #    da janela para o prompt, sobra a conversa inteira.
        #    4 caracteres/token x metade da janela = 4096/2 x 4
        orcamento = (4096 // 2) * 4
        self.assertLess(
            v["chars"],
            orcamento,
            f"{v['chars']} chars ultrapassa o orçamento de {orcamento} "
            f"para um modelo de janela 4096",
        )

        # 3. E uma fracção do catálogo completo — que é o que estourava.
        #    A relação é o contrato: o vocabulário existe porque o catálogo
        #    não cabe, e se o catálogo encolher o vocabulário tem de
        #    encolher com ele.
        import json as _json

        from app.amplia_mcp import TOOLS_CATALOGO, catalogo_tools

        catalogo = _json.dumps(
            catalogo_tools() + list(TOOLS_CATALOGO), ensure_ascii=False
        )
        self.assertLess(
            v["chars"],
            len(catalogo),
            "o vocabulario deixou de ser mais pequeno que o catalogo que "
            "motiva a sua existencia",
        )

    def test_derivado_e_nao_escrito(self):
        """Um intent novo tem de aparecer sem ninguém editar este ficheiro.

        Este é o teste que impede a recaída. A causa raiz da FILA #27 foi uma
        lista escrita à mão; o que fecha a porta é que a próxima lista
        escrita à mão seja impossível de introduzir sem quebrar um teste.
        """
        antes = vocabulario()["total"]
        spec = dict(INTENTS["clima_agora"])
        INTENTS["teste_derivado_nao_escrito"] = spec
        try:
            self.assertIn("teste_derivado_nao_escrito", vocabulario()["texto"])
            self.assertEqual(vocabulario()["total"], antes + 1)
        finally:
            INTENTS.pop("teste_derivado_nao_escrito", None)

    def test_escrita_fica_do_lado_que_altera_dados(self):
        """A separação do texto é a mesma que o sandbox consulta.

        Uma tool de escrita listada como leitura faz o produtor perder o
        aviso. E uma de leitura listada como escrita faz-o confirmar coisas
        que não mudam nada — que é como um pedido de confirmação ensina a
        dizer "sim" sem ler.
        """
        from app.ia.sandbox import somente_leitura

        v = vocabulario()
        for nome, spec in INTENTS.items():
            with self.subTest(intent=nome):
                if somente_leitura(spec):
                    self.assertIn(
                        nome,
                        v["leitura"].get(
                            str((spec.get("flags") or ["_"])[0]).split(".")[0], []
                        ),
                    )
                else:
                    self.assertIn(
                        nome,
                        v["escrita"].get(
                            str((spec.get("flags") or ["_"])[0]).split(".")[0], []
                        ),
                    )

    def test_intent_sem_flag_nao_aparece_como_leitura(self):
        """`somente_leitura` é fail-closed: sem flag, é escrita.

        O vocabulário tem de herdar esse facto. A versão anterior deste teste
        verificava-o com `ajuda` — que deixou de estar no caso, ao passar a
        declarar `ia.read`. A regra continua a ser a mesma e é verificada de
        forma geral: se a coluna "leitura" contiver um intent sem flag, o
        modelo lê que aquela coluna é ficção e perde a única pista que tinha
        para não chamar acções por engano.

        Verificar por nome era frágil de qualquer forma: dependia de um intent
        concreto estar (ou não) sem flag, e a flag de um intent é exactamente
        a coisa que este teste não pode assumir que está quieta.
        """
        from app.ia.sandbox import INTENTS as REGISTO

        v = vocabulario()
        for namespace, nomes in v["leitura"].items():
            for nome in nomes:
                self.assertTrue(
                    (REGISTO[nome].get("flags") or []),
                    f"'{nome}' aparece como leitura em '{namespace}' "
                    "sem declarar flag nenhuma",
                )

    def test_lista_cortada_diz_que_esta_cortada(self):
        """Um vocabulário truncado que parece completo é mentira por omissão.

        O modelo lê a lista, conclui que é tudo o que existe, e fica com as
        ferramentas que faltaram como se nunca tivessem existido — sem
        nenhuma forma de desconfiar. É a mesma razão pela qual um widget sem
        dado mostra "sem dado" (decisão D2).
        """
        v = vocabulario(limite=900)
        self.assertFalse(v["cabe"])
        self.assertIn("LISTA INCOMPLETA", v["texto"])

    def test_limite_estreito_respeita_o_teto(self):
        """O orçamento é do chamador, mas não é uma corda sem fim."""
        for limite in (500, 900, 2400, 99999):
            with self.subTest(limite=limite):
                v = vocabulario(limite=limite)
                self.assertLessEqual(len(v["texto"]), max(limite, 260))

    def test_linha_de_grupo_nao_corta_sem_avisar(self):
        """`nomes` truncados a meio são indistinguíveis de nomes inventados.

        É o mesmo risco do vocabulário inteiro, dentro do grupo: um nome a
        meio (`relatorio_vaci`) parece um nome e não é nenhum.
        """
        nomes = [f"ferramenta_muito_longa_{i:03d}" for i in range(40)]
        linha = _linha_grupo("  grupo", nomes, limite=120)
        self.assertLess(len(linha), 200)
        self.assertIn("+", linha)
        self.assertIn("grupo:", linha)

    def test_grupo_sem_nomes_que_caibam_ainda_diz_o_assunto(self):
        """O pior caso não pode devolver uma linha vazia nem uma falsa."""
        linha = _linha_grupo("  assunto", ["x" * 300], limite=40)
        self.assertIn("assunto", linha)
        self.assertIn("omiti", linha)


class SuperficieHttpTest(TestCase):
    """O endpoint que o browser vai buscar."""

    def setUp(self):
        User.objects.create_user("voc", "voc@x.com", "p")
        self.c = Client()
        self.c.login(username="voc", password="p")

    def test_exige_login(self):
        self.assertEqual(Client().get("/api/amplia/vocabulario/").status_code, 302)

    def test_devolve_texto_e_estrutura(self):
        r = self.c.get("/api/amplia/vocabulario/")
        self.assertEqual(r.status_code, 200)
        j = r.json()
        for chave in ("texto", "cabe", "chars", "total", "leitura", "escrita"):
            self.assertIn(chave, j)
        self.assertEqual(j["total"], len(INTENTS))

    def test_limite_por_query(self):
        j = self.c.get("/api/amplia/vocabulario/?limite=1200").json()
        self.assertEqual(j["limite"], 1200)
        self.assertFalse(j["cabe"])

    def test_limite_lixo_nao_derruba(self):
        """`?limite=abc` não pode ser um 500.

        O chamador é uma aba de browser a três Tacadas de um erro de sintaxe.
        Uma view que levanta devolve-lhe uma página de traceback em vez de um
        vocabulário, e o modelo fica sem saber os nomes — que é exactamente o
        defeito que este endpoint veio fechar.
        """
        for ruim in ("abc", "", "-1", "0", "999999999999999999999"):
            with self.subTest(valor=ruim):
                r = self.c.get(f"/api/amplia/vocabulario/?limite={ruim}")
                self.assertEqual(r.status_code, 200)
                self.assertIn("texto", r.json())

    def test_contexto_antigo_ainda_responde(self):
        """A view de contexto foi renomeada e o nome novo tem de funcionar.

         Houve um intervalo em que `urls.py` apontava para `contexto_view` e a
         função ainda se chamava `ctx` — `manage.py check` falhava com
         AttributeError e o projecto inteiro não arrancava. Um teste que só
        ophone a rota não apanha um nome trocado a meio.
        """
        r = self.c.get("/api/amplia/contexto/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("contexto", r.json())


class AvisoDeCapacidadeTest(TestCase):
    """FILA #28: o aviso de capacidade nunca pode ser o que se corta."""

    def test_aviso_sobrevive_a_uma_descricao_gigante(self):
        """O defeito era latente, e a correcção é sobre a ordem do sacrifício.

        A primeira versão fazia `(descricao + aviso)[:900]`, e o aviso ficava
        no fim — a última coisa a ser cortada. O máximo observado era 720
        caracteres, por isso ainda não tinha mordido; bastava um intent novo
        com uma descrição comprida. Uma tool de escrita anunciada sem aviso é
        o modelo a aprender que o aviso é decoração.
        """
        aviso = " ATENCAO: esta tool ALTERA dados e pode pedir confirmacao."
        out = _com_aviso("x" * 5000, aviso)
        self.assertLessEqual(len(out), 900)
        # Inteiro, e no fim: é o aviso que sobrevive, não uma versão dele.
        self.assertTrue(out.endswith(aviso), f"o aviso foi cortado: ...{out[-70:]!r}")
        self.assertIn("ALTERA dados", out)

    def test_descricao_curta_nao_e_estragada(self):
        """O caso comum tem de ficar exactamente como estava."""
        out = _com_aviso("Consulta o clima.", " ATENCAO: x.")
        self.assertEqual(out, "Consulta o clima. ATENCAO: x.")

    def test_sem_aviso_e_so_corte(self):
        """Tool de leitura: nada a sacrificar, nada a inventar."""
        self.assertEqual(_com_aviso("y" * 2000, ""), "y" * 900)

    def test_todo_intent_publicado_guarda_o_aviso_que_lhe_toca(self):
        """A regra, aplicada ao catálogo inteiro e não a um exemplo.

        Se amanhã alguém escrever um `descricao` de 2000 caracteres, este
        teste é o que avisa — antes do produtor.
        """
        from app.amplia_mcp import catalogo_tools

        for t in catalogo_tools():
            with self.subTest(tool=t["name"]):
                if t["x-read-only"]:
                    self.assertNotIn("ATENCAO", t["description"])
                else:
                    self.assertIn("ATENCAO", t["description"])


def executar(username: str, tool: str):
    """Atalho local: chama a porta de execução como a view chama."""
    from app.amplia_mcp import executar_para

    u = User.objects.get(username=username)
    return executar_para(u, tool, {})


class PromptMcpTest(TestCase):
    """A terceira superfície do MCP: o que se PEDE, e não o que se lê.

    Um servidor com 79 `tools`, uns `resources` e nenhum `prompts` obriga o
    agente a descobrir por tentativa-e-erro duas coisas que o código já sabe:
    que uma escrita pede confirmação, e que um nome inventado volta com
    `sugestoes`. Cada tentativa é uma chamada ao servidor, e um `ok=False`
    na trilha.
    """

    def test_catalogo_tem_nome_e_descricao(self):
        """`list_prompts` sem descrição é um catálogo que ninguém consegue
        escolher. A descrição é o que o agente lê para decidir."""
        from app.amplia_mcp import prompts_mcp

        cat = prompts_mcp.catalogo_prompts()
        self.assertTrue(cat)
        for item in cat:
            self.assertTrue(item["name"].startswith("amplia_"), item)
            self.assertTrue(item["description"].strip(), f"{item['name']} sem texto")

    def test_todo_o_catalogo_monta(self):
        from app.amplia_mcp import prompts_mcp

        for nome in prompts_mcp.PROMPTS:
            with self.subTest(prompt=nome):
                texto = prompts_mcp.montar(nome)
                self.assertIsInstance(texto, str)
                self.assertTrue(texto.strip())

    def test_prompt_inexistente_e_none_e_nao_string_vazia(self):
        """A diferença entre "não existe" e "existe e não diz nada".

        Uma string vazia é lida pelo cliente como um prompt válido em branco.
        É a mesma falha que `read_resource` tinha, e a correcção é a mesma:
        devolver `None` para o servidor poder dizer que não existe.
        """
        from app.amplia_mcp import prompts_mcp

        self.assertIsNone(prompts_mcp.montar("amplia_nao_existe"))

    def test_ferramentas_da_o_nome_exacto_com_prefixo(self):
        """O texto tem de trazer o nome que o agente vai escrever.

        Um texto que ensina `ligar_irrigador` e pede `amplia_ligar_irrigador`
        produz metade das llamadas com o nome errado. E o nome errado não
        falha em silêncio — paga-se com uma linha de auditoria.
        """
        from app.amplia_mcp import prompts_mcp

        texto = prompts_mcp.montar("amplia_ferramentas")
        for nome in INTENTS:
            self.assertIn(f"amplia_{nome}", texto)
        # E nenhum nome solto, que seria a forma de o agente escrever sem o
        # prefixo. A excepção é o texto de instrução, onde o nome aparece
        # dentro de backticks — daí o teste olhar para o padrão de lista.
        self.assertNotIn(", ligar_irrigador,", texto)

    def test_seguranca_nomeia_os_campos_que_o_agente_usa(self):
        """Instrução que não dá o NOME do campo é opinião, não instrução.

        Um agente que lê "volta sugestões" em maiúsculas continua sem saber o
        que escrever. Tem de ser `sugestoes`, `needs_confirm` e `confirm` —
        os três nomes que o código já põe na resposta.
        """
        from app.amplia_mcp import prompts_mcp

        texto = prompts_mcp.montar("amplia_seguranca")
        for campo in ("needs_confirm", "confirm", "sugestoes", "IAExecucao"):
            with self.subTest(campo=campo):
                self.assertIn(campo, texto)

    def test_seguranca_lista_as_escritas_reais(self):
        """A lista de "cuidado com estas" é derivada, não lembrada.

        Se alguém acrescentar uma tool de escrita, entra aqui sem ninguém
        editar. Uma lista escrita à mão é a que divergiu e custou a FILA #27.
        """
        from app.amplia_mcp import prompts_mcp
        from app.ia.sandbox import somente_leitura

        texto = prompts_mcp.montar("amplia_seguranca")
        for nome, spec in INTENTS.items():
            if somente_leitura(spec):
                continue
            with self.subTest(intent=nome):
                self.assertIn(nome, texto)

    def test_campos_so_fala_do_que_pergunta(self):
        """Uma tool sem `required_fields` não entra na conversa de duas voltas.

        Listar toda a gente seria ruído que tornaria a lista inútil — o mesmo
        princípio pelo qual o vocabulário só põe os nomes que importam.
        """
        from app.amplia_mcp import prompts_mcp

        texto = prompts_mcp.montar("amplia_campos")
        com_campos = {n for n, s in INTENTS.items() if (s or {}).get("required_fields")}
        if com_campos:
            self.assertTrue(any(n in texto for n in com_campos))
        # `clima_agora` não pede campos; não deve seradido a falar deles.
        if "clima_agora" not in com_campos:
            self.assertNotIn("clima_agora", texto)
