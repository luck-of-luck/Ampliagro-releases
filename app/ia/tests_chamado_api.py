"""O Chamado Amplia ponta a ponta — e a trava, testada partindo o sistema.

POR QUE HÁ TANTO TESTE AQUI E TÃO POUCO NO RESTO
================================================
Porque a trava é uma PROMESSA ao produtor, e uma promessa que só o handler
respeita é uma promessa que uma sessão cansada não respeita. Estes testes não
verificam que o handler funciona — verificam que a garantia falha quando se
tenta fazê-la falhar.

O teste mais importante é `test_preset_que_vem_mas_e_errado_e_recusado`: chama a
intent de escrita a apontar para um preset que NÃO é a zona, e confirma que nada
foi gravado. Se alguém aplicar a validação a um sítio errado — ou a nenhum —
esse teste fica vermelho, que é o ponto.

O QUE ESTES TESTES NÃO PROVAM
=============================
Que o painel desenha bem os blocos. Isso é JavaScript e é medido no browser.
Aqui prova-se a aritmética e a autorização — as duas coisas em que um erro
custa dinheiro ao produtor.
"""


# A lista de tools de catalogo vive num sitio so. Ver o porque em
# `app/amplia_mcp/ferramentas_aceitas.py`.
from app.amplia_mcp.ferramentas_aceitas import (  # noqa: E402
    TOOLS_CATALOGO_ACEITAS,
)
from django.contrib.auth.models import User
from django.test import TestCase

from app.ia import chamado as ch
from app.ia import registro, sandbox


def bloco_texto(txt="oi"):
    return {"tipo": "texto", "texto": txt}


def bloco_tabela():
    return {
        "tipo": "tabela",
        "titulo": "Despesas",
        "colunas": ["categoria", "valor"],
        "linhas": [["Adubo", "1.200,00"], ["Semente", "800,00"]],
    }


def ferramentas_publicadas():
    """As tools COMO O CLIENTE AS VÊ.

    `catalogo_tools()` sozinho NÃO é a superfície pública: devolve a forma plana
    e sem `required`. Quem publica o contrato é `contrato.enriquecer` — é a
    traducao que a view e o servidor MCP usam. Testar contra `catalogo_tools()`
    mede o interior e dá um veredicto sobre o que o cliente recebe que é falso.
    Já aconteceu aqui: com `catalogo_tools()` os schemas pareciam não declarar
    `required`, e declaram.
    """
    from app.amplia_mcp import catalogo_tools
    from app.amplia_mcp.contrato import enriquecer

    return enriquecer(catalogo_tools())


class BaseChamado(TestCase):
    def setUp(self):
        # O `sandbox` MEMORIZA resultados, e a chave inclui o `user.id`. Noutro
        # teste da suite, um utilizador com o mesmo id (o rollback do SQLite
        # reutiliza ids) pode deixar uma resposta em cache para a mesma
        # `(user, intent, params)` — e o teste recebe o veredito guardado em vez
        # do que a máquina de estados devolve. Foi assim que
        # `test_pede_confirmacao_antes_de_escrever` passou isolado e falhou na
        # suite completa.
        #
        # Limpar o cache em `setUp` não é a correcção: um teste que
        # depende da ordem de execução dos outros não mede o que diz medir.
        from django.core.cache import cache

        cache.clear()
        self.user = User.objects.create_user("produtor", password="x")
        self.outro = User.objects.create_user("vizinho", password="x")

    def executar(self, nome, params, user=None, **kw):
        return sandbox.executar(user or self.user, nome, params, **kw)

    def criar(self, user=None, **extra):
        blocos = extra.pop("blocos", [bloco_texto(), bloco_tabela()])
        return self.executar(
            "chamado_criar",
            {"blocos": blocos, "confirm": True, "nome": "Meu resumo", **extra},
            user=user,
        )


class CriarTest(BaseChamado):
    def test_cria_e_devolve_os_blocos(self):
        r = self.criar()
        self.assertTrue(r["ok"], r)
        d = r["dados"]
        self.assertTrue(d["criado"])
        self.assertEqual(d["total"], 2)
        self.assertEqual([b["tipo"] for b in d["blocos"]], ["texto", "tabela"])

    def test_cria_o_preset_na_widget_bar(self):
        # Uma peça sem preset é invisível: existe na base e o produtor nunca a
        # vê. É o "botão que parece funcionar e não faz nada".
        from app.models import PresetPalco

        self.criar()
        self.assertTrue(
            PresetPalco.objects.do_produtore(self.user)
            .filter(slug=ch.SLUG_CHAMADO)
            .exists()
        )

    def test_o_preset_criado_e_aceite_pelo_dashboard(self):
        # `preset_permitido` é a validação que apanha presets fantasma. Se o
        # slug não estiver em PRESETS_SISTEMA, a peça é apagada no momento em
        # que o produtor grava o estado — e a feature funciona uma vez.
        from app.presets import limpar_presets_bloqueados, preset_permitido

        self.assertTrue(preset_permitido(ch.SLUG_CHAMADO))
        self.criar()
        estado = {
            "presets": {ch.SLUG_CHAMADO: {"widgets": []}},
            "presets_order": [ch.SLUG_CHAMADO],
            "active_preset": ch.SLUG_CHAMADO,
        }
        limpo, removidos = limpar_presets_bloqueados(estado)
        self.assertEqual(removidos, [])
        self.assertIn(ch.SLUG_CHAMADO, limpo["presets"])

    def test_tabela_com_linhas_da_ia_nao_e_medida(self):
        """Uma tabela com linhas escritas pela IA NÃO é `medido`.

        Este teste afirmava o contrário durante uma versão: dizia que linhas
        bastavam. Bastavam para um bloco de dado que o SERVIDOR preencheu, e
        não para um bloco de dados que um modelo de 1,7B escreveu — que é o que
        este teste monta.

        A diferença entre as duas coisas é a diferença entre uma conta e uma
        conta inventada, e o producer não as distingue no ecrã: as duas mostram
        algarismos com o formato certo numa coluna com o nome certo.
        """
        r = self.criar()
        tabela = [b for b in r["dados"]["blocos"] if b["tipo"] == "tabela"][0]
        self.assertEqual(tabela["fonte_dado"], "sem_dado")

    def test_texto_com_numero_sem_apoio_avisa_e_desce(self):
        r = self.criar(
            blocos=[
                {"tipo": "texto", "texto": "A margem caiu para 18% deste ano."},
                bloco_tabela(),
            ]
        )
        d = r["dados"]
        texto = [b for b in d["blocos"] if b["tipo"] == "texto"][0]
        self.assertEqual(texto["fonte_dado"], "sem_dado")
        self.assertTrue(d["numeros_sem_apoio"])
        self.assertIn("18", d["numeros_sem_apoio"][0]["numero"])
        # E o aviso tem de chegar ao produtor em português legível, não num
        # código: o aviso é para ele, não para o log.
        self.assertIn("18", r["resposta"])

    def test_tipo_desconhecido_e_descartado_com_motivo(self):
        r = self.criar(blocos=[bloco_texto(), {"tipo": "video"}])
        self.assertEqual(r["dados"]["total"], 1)
        self.assertTrue(any("desconhecido" in d for d in r["dados"]["descartados"]))

    def test_pede_confirmacao_antes_de_escrever(self):
        # `requires_confirmation` é o que transforma isto num pedido ao produtor
        # e não numa acção. Sem ele, a IA cria a peça sem ninguém perguntar.
        r = self.executar("chamado_criar", {"blocos": [bloco_texto()]})
        self.assertTrue(r.get("needs_confirm"))
        self.assertEqual(r.get("state"), "AGUARDANDO_CONFIRMACAO")
        from app.models import ChamadoAmplia

        self.assertFalse(ChamadoAmplia.objects.exists())

    def test_recria_substitui_e_nao_duplica(self):
        self.criar()
        r = self.criar(blocos=[bloco_texto("outro")])
        self.assertFalse(r["dados"]["criado"])
        from app.models import ChamadoAmplia

        self.assertEqual(ChamadoAmplia.objects.do_produtore(self.user).count(), 1)
        self.assertEqual(r["dados"]["total"], 1)


class TravaTest(BaseChamado):
    """A garantia central. Estes testes é que são o produto."""

    def test_preset_que_vem_mas_e_errado_e_recusado(self):
        # É ESTE o teste que a garantia vive. Um preset que chega e não é a zona
        # tem de ser recusado COM MOTIVO, e nada pode ser gravado.
        self.criar()
        antes = self.executar("chamado_ler", {})["dados"]["versao"]
        for errado in ("custom-custo", "amplia", "cafe", "custom-1"):
            with self.subTest(preset=errado):
                r = self.executar(
                    "chamado_editar",
                    {
                        "preset": errado,
                        "delta": {"op": "remover", "id": "b1"},
                        "confirm": True,
                    },
                )
                self.assertFalse(r["ok"])
                self.assertIn(ch.NOME_CHAMADO, r["erro"])
        # E a peça está intacta: recusar sem gravar é o que torna a recusa uma
        # garantia em vez de um aviso.
        depois = self.executar("chamado_ler", {})["dados"]
        self.assertEqual(depois["versao"], antes)
        self.assertEqual(depois["total"], 2)

    def test_o_motivo_diz_que_so_le_e_oferece_o_camado(self):
        # Um "não" sem explicação faz o produtor concluir que a IA avariou.
        self.criar()
        r = self.executar(
            "chamado_editar",
            {
                "preset": "custom-custo",
                "delta": {"op": "remover", "id": "b1"},
                "confirm": True,
            },
        )
        self.assertFalse(r["ok"])
        self.assertIn("só lê", r["erro"])
        self.assertIn(ch.NOME_CHAMADO, r["erro"])

    def test_preset_ausente_nao_e_uma_passagem(self):
        # O `sandbox` intercepta o campo obrigatório em falta ANTES do handler e
        # devolve COLETANDO_DADOS — melhor do que a minha recusa: pergunta em vez
        # de dizer que não. O que NÃO pode é deixar passar.
        #
        # A versão anterior do handler fazia `params.get("preset") or SLUG` e
        # caía na zona com o campo vazio: falha-aberta, que é a pior forma de
        # uma trava. Este teste fixa que a ausência não escreve nada.
        #
        # A verificação vai ao MODELO e não a `chamado_ler` por uma razão que só
        # aparece aqui: a máquina de estados do sandbox fica à espera do
        # `preset`, e a leitura seguinte pelo mesmo caminho herda esse estado.
        # Testar o estado conversacional não prova a garantia; prova que a base
        # não foi tocada.
        from app.models import ChamadoAmplia

        self.criar()
        antes = ChamadoAmplia.objects.do_produtore(self.user).get()
        self.executar(
            "chamado_editar",
            {"delta": {"op": "remover", "id": "b1"}, "confirm": True},
        )
        depois = ChamadoAmplia.objects.do_produtore(self.user).get()
        self.assertEqual(depois.versao, antes.versao, "nada pode ter mudado")
        self.assertEqual(depois.corpo, antes.corpo)

    def test_arquivado_e_somente_leitura(self):
        self.criar()
        self.executar("chamado_publicar", {"acao": "arquivar", "confirm": True})
        r = self.executar(
            "chamado_editar",
            {
                "preset": ch.SLUG_CHAMADO,
                "delta": {"op": "remover", "id": "b1"},
                "confirm": True,
            },
        )
        self.assertFalse(r["ok"])
        self.assertIn("arquivado", r["erro"])
        # E continua legível: arquivar é fechar a porta, não apagar o conteúdo.
        self.assertTrue(self.executar("chamado_ler", {})["dados"]["existe"])

    def test_reabrir_devolve_a_escrita(self):
        self.criar()
        self.executar("chamado_publicar", {"acao": "arquivar", "confirm": True})
        self.executar("chamado_publicar", {"acao": "publicar", "confirm": True})
        r = self.executar(
            "chamado_editar",
            {
                "preset": ch.SLUG_CHAMADO,
                "delta": {"op": "remover", "id": "b2"},
                "confirm": True,
            },
        )
        self.assertTrue(r["ok"], r)

    def test_criar_recusa_um_preset_alheio(self):
        # `criar` não exige `preset` — criar é por definição a zona. Mas um
        # preset alheio que venha explícito tem de ser recusado, senão a trava
        # é "por omissão" e basta um dia alguém juntar o parâmetro.
        r = self.executar(
            "chamado_criar",
            {"blocos": [bloco_texto()], "preset": "custom-alheio", "confirm": True},
        )
        self.assertFalse(r["ok"])
        self.assertIn(ch.NOME_CHAMADO, r["erro"])

    def test_editar_inexistente_diz_que_crie_primeiro(self):
        r = self.executar(
            "chamado_editar",
            {
                "preset": ch.SLUG_CHAMADO,
                "delta": {"op": "remover", "id": "b1"},
                "confirm": True,
            },
        )
        self.assertFalse(r["ok"])
        self.assertIn("criar", r["erro"])


class TenantTest(BaseChamado):
    def test_o_vizinho_nao_ve_a_peca(self):
        self.criar()
        r = self.executar("chamado_ler", {}, user=self.outro)
        self.assertFalse(r["dados"]["existe"])

    def test_o_vizinho_nao_edita_a_peca(self):
        # O `id` não existe para ele. Sem isto, `ChamadoAmplia.objects.first()`
        # em vez de `do_produtore` seria um vazamento entre contas — e o único
        # sinal seria o produtor A ver uma alteração que não fez.
        self.criar()
        r = self.executar(
            "chamado_editar",
            {
                "preset": ch.SLUG_CHAMADO,
                "delta": {"op": "remover", "id": "b1"},
                "confirm": True,
            },
            user=self.outro,
        )
        self.assertFalse(r["ok"])

    def test_cada_produtor_tem_a_sua_peca(self):
        self.criar()
        self.criar(user=self.outro)
        r = self.executar("chamado_ler", {})
        self.assertEqual(r["dados"]["total"], 2)
        r2 = self.executar("chamado_ler", {}, user=self.outro)
        self.assertEqual(r2["dados"]["total"], 2)


class VersaoTest(BaseChamado):
    def test_versao_desatualizada_recusa(self):
        # Duas edições a partir da mesma leitura sobrepõem-se uma à outra: a
        # segunda escreve o corpo antigo por cima do novo, e o produtor vê uma
        # alteração sua desaparecer sem ninguém a ter tocado.
        self.criar()
        lida = self.executar("chamado_ler", {})["dados"]["versao"]
        self.executar(
            "chamado_editar",
            {
                "preset": ch.SLUG_CHAMADO,
                "delta": {"op": "remover", "id": "b2"},
                "confirm": True,
                "versao": lida,
            },
        )
        r = self.executar(
            "chamado_editar",
            {
                "preset": ch.SLUG_CHAMADO,
                "delta": {"op": "remover", "id": "b1"},
                "confirm": True,
                "versao": lida,
            },
        )
        self.assertFalse(r["ok"])
        self.assertIn("mudou entretanto", r["erro"])
        self.assertEqual(r["dados"]["versao_atual"], lida + 1)

    def test_versao_certa_passa(self):
        self.criar()
        lida = self.executar("chamado_ler", {})["dados"]["versao"]
        r = self.executar(
            "chamado_editar",
            {
                "preset": ch.SLUG_CHAMADO,
                "delta": {"op": "remover", "id": "b2"},
                "confirm": True,
                "versao": lida,
            },
        )
        self.assertTrue(r["ok"], r)

    def test_delta_que_nao_muda_avisa_com_os_ids(self):
        # Um "não mudaste nada" sem os ids é um beço sem saída para o modelo.
        self.criar()
        r = self.executar(
            "chamado_editar",
            {
                "preset": ch.SLUG_CHAMADO,
                "delta": {"op": "remover", "id": "b99"},
                "confirm": True,
            },
        )
        self.assertFalse(r["ok"])
        self.assertIn("b1", r["dados"]["ids"])
        self.assertIn("remover", r["dados"]["operacoes"])


class DeltaTest(BaseChamado):
    def setUp(self):
        super().setUp()
        self.criar(blocos=[bloco_texto("a"), bloco_tabela(), bloco_texto("c")])

    def editar(self, delta, **extra):
        return self.executar(
            "chamado_editar",
            {"preset": ch.SLUG_CHAMADO, "delta": delta, "confirm": True, **extra},
        )

    def test_acrescentar(self):
        r = self.editar({"op": "adicionar", "blocos": [bloco_texto("nova")]})
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["dados"]["total"], 4)

    def test_remover(self):
        r = self.editar({"op": "remover", "id": "b2"})
        self.assertEqual([b["id"] for b in r["dados"]["blocos"]], ["b1", "b3"])

    def test_reescrever_texto(self):
        r = self.editar({"op": "reescrever_texto", "id": "b1", "texto": "outra"})
        b1 = [b for b in r["dados"]["blocos"] if b["id"] == "b1"][0]
        self.assertEqual(b1["config"]["texto"], "outra")

    def test_reordenar(self):
        r = self.editar({"op": "reordenar", "ordem": ["b3", "b2", "b1"]})
        self.assertEqual([b["id"] for b in r["dados"]["blocos"]], ["b3", "b2", "b1"])

    def test_substituir(self):
        r = self.editar(
            {
                "op": "substituir",
                "id": "b1",
                "bloco": {"tipo": "texto", "texto": "troca"},
            }
        )
        b1 = [b for b in r["dados"]["blocos"] if b["id"] == "b1"][0]
        self.assertEqual(b1["config"]["texto"], "troca")

    def test_o_preset_da_widget_bar_acompanha_a_versao(self):
        from app.models import PresetPalco

        r = self.editar({"op": "remover", "id": "b3"})
        preset = PresetPalco.objects.do_produtore(self.user).get(slug=ch.SLUG_CHAMADO)
        self.assertEqual(preset.estrutura["versao"], r["dados"]["versao"])
        self.assertEqual(preset.estrutura["blocos"], 2)


class SuperficieMcpTest(TestCase):
    """O que o MCP publica tem de estar coerente com o que existe."""

    def test_o_catalogo_publica_os_blocos_e_a_zona(self):
        # Os blocos vivem DENTRO de `amplia_catalogos`, e não numa tool
        # própria. Houve uma `amplia_chamado_blocos` separada e foi removida de
        # propósito: o repo já tinha dois testes a dizer que duas tools de
        # catálogo chegam ("Duas, não cinco. Cada tool extra é uma escolha a mais
        # para errar"), e para um SmolLM2 de 1,7B a correr na aba cada tool nova
        # é um nome a mais para ser escolhido mal. O que o modelo precisa é o
        # dicionário, não mais um botão onde o buscar.
        #
        # O bloco continua alcançável sem inchar a tool: `amplia://blocos` é um
        # recurso, e um recurso não se escolhe — pede-se pelo nome.
        from app.amplia_mcp import executar_catalogo

        u = User.objects.create_user("produtor", password="x")
        r = executar_catalogo(u, "amplia_catalogos", {})
        self.assertTrue(r["ok"], r)
        self.assertIn("blocos", r)
        self.assertIn("zona_escrita", r)
        self.assertEqual({b["id"] for b in r["blocos"]}, set(ch.CATALOGO_BLOCOS))
        self.assertEqual(r["zona_escrita"]["preset"], ch.SLUG_CHAMADO)
        self.assertIn("remover", r["zona_escrita"]["operacoes"])

    def test_as_tools_de_catalogo_nao_creceram(self):
        # A guarda que decide o número de tools de catálogo. Fica aqui para
        # dizer de onde veio a decisão, e porque voltar a acrescentar uma é uma
        # escolha que tem de ser tomada — e não tropeçada.
        #
        # MEDIDO 2026-10-05: era `assertEqual(NOMES_CATALOGO, ACEITAS)`, e
        # era IMPOSSIVEL de satisfazer ao mesmo tempo que
        # `tests_ciclo_automacao.py::ComparativoAcessivelTest`, que exige que
        # `amplia_comparativo_revisao` esteja na allowlist.
        #
        # As duas listas medem coisas diferentes, e a distincao esta' escrita
        # em `ferramentas_aceitas.py`:
        #
        #     NOMES_CATALOGO          entradas de CATALOGO
        #     TOOLS_CATALOGO_ACEITAS  nomes PUBLICAVEIS -- quem `executar_para`
        #                             aceita chamar
        #
        # Publicar e' uma decisao; ser entrada de catalogo e' um mecanismo. Uma
        # capacidade pode responder por `executar_para` sem ser entrada de
        # catalogo -- e' o caso do intent `comparativo_revisao`, que passa pelo
        # sandbox e herda `x-read-only`. Com igualdade, uma das duas guardas
        # tinha de estar vermelha.
        #
        # O que continua protegido: TODA tool de catalogo tem de estar
        # declarada. O que deixa de se exigir e' que a allowlist nao possa
        # conter mais do que o catalogo. A entrada orfa -- declarada e sem
        # porta -- e' apanhada do outro lado, por `ComparativoAcessivelTest`.
        from app.amplia_mcp import NOMES_CATALOGO

        declarados = frozenset(TOOLS_CATALOGO_ACEITAS)
        self.assertLessEqual(
            NOMES_CATALOGO,
            declarados,
            "tool de catalogo por declarar: %s"
            % sorted(NOMES_CATALOGO - declarados),
        )

    def test_o_recurso_amplia_blocos_existe(self):
        from app.amplia_mcp import catalogo_blocos

        d = catalogo_blocos()
        self.assertEqual({b["id"] for b in d["blocos"]}, set(ch.CATALOGO_BLOCOS))
        self.assertEqual(d["zona_escrita"]["preset"], ch.SLUG_CHAMADO)

    def test_as_intents_do_chamado_estao_publicadas(self):
        nomes = {t["name"] for t in ferramentas_publicadas()}
        for esperado in (
            "amplia_chamado_criar",
            "amplia_chamado_editar",
            "amplia_chamado_ler",
            "amplia_chamado_publicar",
        ):
            with self.subTest(esperado=esperado):
                self.assertIn(esperado, nomes)

    def test_o_schema_do_preset_declara_o_enum(self):
        # Um schema que só diz "string" obriga a IA a descobrir qual é o preset
        # certo, e uma descoberta que falha é uma escrita recusada — ou pior,
        # uma escrita no sítio errado. Com o `enum`, a restrição é legível por
        # máquina e não é uma nota que se pode não ler.
        achada = [
            t for t in ferramentas_publicadas() if t["name"] == "amplia_chamado_editar"
        ][0]
        preset = achada["inputSchema"]["properties"]["preset"]
        self.assertEqual(preset.get("enum"), [ch.SLUG_CHAMADO])

    def test_as_escritas_declaram_required(self):
        # O defeito medido do contrato: nove intents pediam campos e nenhuma
        # publicava `required`. A IA só descobria tentando, e cada tentativa
        # era uma ida ao estado COLETANDO_DADOS.
        por_nome = {t["name"]: t for t in ferramentas_publicadas()}
        for nome, campo in (
            ("amplia_chamado_criar", "blocos"),
            ("amplia_chamado_editar", "delta"),
            ("amplia_chamado_editar", "preset"),
            ("amplia_chamado_publicar", "acao"),
        ):
            with self.subTest(nome=nome, campo=campo):
                schema = por_nome[nome]["inputSchema"]
                self.assertIn(campo, schema.get("required", []))

    def test_a_escrita_declara_confirm(self):
        # Das 24 tools de escrita, 19 não declaravam `confirm` — e as 24
        # fechavam o schema. A única forma de confirmar era violar o contrato
        # que o próprio servidor tinha publicado.
        for t in ferramentas_publicadas():
            nome = t["name"]
            if not nome.startswith("amplia_chamado_"):
                continue
            if "confirm" not in t["inputSchema"].get("properties", {}):
                continue
            with self.subTest(nome=nome):
                self.assertNotIn("confirm", t["inputSchema"]["required"])

    def test_a_leitura_nao_declara_confirm(self):
        achada = [
            t for t in ferramentas_publicadas() if t["name"] == "amplia_chamado_ler"
        ][0]
        self.assertNotIn("confirm", achada["inputSchema"].get("properties", {}))


class SuperficieHttpTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("produtor", password="x")
        self.client.force_login(self.user)
        sandbox.executar(
            self.user,
            "chamado_criar",
            {"blocos": [bloco_texto(), bloco_tabela()], "confirm": True},
        )

    def test_a_widget_bar_le_a_peca(self):
        r = self.client.get("/api/amplia/palco/chamado/")
        self.assertEqual(r.status_code, 200)
        d = r.json()["chamado"]
        self.assertTrue(d["existe"])
        self.assertEqual(d["total"], 2)
        self.assertEqual(d["preset"], ch.SLUG_CHAMADO)

    def test_o_palco_info_anuncia_a_zona(self):
        r = self.client.get("/api/amplia/palco/info/")
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertEqual(d["zona_escrita"]["preset"], ch.SLUG_CHAMADO)
        self.assertTrue(d["meu_chamado"]["existe"])

    def test_o_endpoint_recusa_escrita(self):
        # A escrita da IA passa pelo sandbox. Um POST aqui seria o segundo
        # caminho — e tem de responder 405, não aceitar.
        r = self.client.post("/api/amplia/palco/chamado/", {"blocos": []})
        self.assertEqual(r.status_code, 405)

    def test_outro_produtor_nao_ve_a_peca(self):
        outro = User.objects.create_user("vizinho", password="x")
        self.client.force_login(outro)
        r = self.client.get("/api/amplia/palco/chamado/")
        self.assertFalse(r.json()["chamado"]["existe"])


class ContratoDoRegistoTest(TestCase):
    """O registo tem de ser coerente — a doutrina que já custou a FILA #27."""

    def test_as_quatro_intents_existem(self):
        for nome in (
            "chamado_criar",
            "chamado_editar",
            "chamado_ler",
            "chamado_publicar",
        ):
            with self.subTest(nome=nome):
                self.assertIn(nome, registro.REGISTO)

    def test_nao_ha_colisao_de_nomes(self):
        self.assertEqual(registro.nomes_duplicados(), {})

    def test_so_a_leitura_e_leitura(self):
        do_sistema = {n for n in registro.REGISTO if n.startswith("chamado_")}
        leitura = {
            n for n in do_sistema if sandbox.somente_leitura(registro.REGISTO[n])
        }
        self.assertEqual(leitura, {"chamado_ler"})

    def test_as_escritas_pedem_confirmacao(self):
        for nome in ("chamado_criar", "chamado_editar", "chamado_publicar"):
            with self.subTest(nome=nome):
                self.assertTrue(registro.REGISTO[nome]["requires_confirmation"])
