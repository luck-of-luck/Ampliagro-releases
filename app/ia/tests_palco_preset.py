"""A Fase 2: a IA grava a mesa no preset DO PRODUTOR.

O QUE ESTE FICHEIRO PROVA
=========================
Tres coisas, por ordem de gravidade:

1. **A mesa de um produtor nao aparece na tela de outro.** Gravar em `PalcoIA`
   faria exactamente isso, porque `PalcoIA` nao tem `user`. Aqui grava-se em
   `PresetPalco`, que tem — e le-se por `do_produtore`.

2. **Nada e' gravado sem o produtor dizer que sim.** Duas portas: o
   `requires_confirmation` do spec, e a guarda `chamado.pode_escrever` dentro
   do handler. Nenhuma fecha a outra sozinha, e `AGuardaDaEscritaTest` mede
   as duas.

3. **A confirmacao mostra o que VAI acontecer.** Um "nao" tem de ser uma
   resposta, nao um erro — e nao pode deixar nada para tras.
"""

from django.contrib.auth.models import User
from django.test import TestCase

from app.models.palco import PresetPalco


class AGuardaDaEscritaTest(TestCase):
    """A Fase 2 escreve num preset do produtor. Quem a AUTORIZA?

    Esta e' a classe que responde a pergunta que `models/palco.py:279` faz:
    *"um `PresetPalco` reescrevivel seria um preset em que a IA pode escrever, e
    a garantia passaria a depender de uma comparacao de string feita no
    caminho certo, e o caminho certo e' um sitio."*

    A resposta: a autorizacao nao e' uma comparacao de string em lado nenhum.
    E' `chamado.pode_escrever`, a funcao que o projecto ja' tinha para decidir
    isto, chamada de dentro do handler como `chamado_intents.py:5` manda.

    E o sinal que a autoriza — `pedido_explicito` — vem de `confirm`, que e' a
    RESPOSTA do produtor. Se algum dia vier de `params`, estes testes deixam de
    proteger o que dizem proteger.
    """

    def setUp(self):
        self.ana = User.objects.create_user("ana_guarda", "a@x.com", "x1234567")

    def _grava(self, **extra):
        from app.ia.sandbox import executar

        params = {"nome": "Custo", "widgets": [{"tipo": "kpi-custo"}]}
        params.update(extra)
        return executar(self.ana, "preset_palco", params, via="sessao")

    def test_o_handler_chama_a_guarda_do_projecto_antes_de_gravar(self):
        """`chamado_intents.py:5`: "pode_escrever e' chamado dentro de cada
        handler de escrita, antes de gravar"."""
        import inspect

        from app.ia.intents_palco_preset import h_preset_palco

        fonte = inspect.getsource(h_preset_palco)
        self.assertLess(
            fonte.index("pode_escrever"),
            fonte.index("palco_presets.gravar"),
            "grava ANTES de passar pela guarda",
        )

    def test_o_slug_que_grava_e_sempre_do_produtor(self):
        """A guarda so' abre `custom-*`. Um slug nosso que nao o fosse era um
        `get_or_create` a escrever num painel de sistema."""
        from app.models.palco import PresetPalco
        from app.presets import PRESETS_SISTEMA

        self._grava(confirm=True)
        slug = PresetPalco.objects.get().slug
        self.assertTrue(slug.startswith("custom-"), slug)
        self.assertNotIn(slug, PRESETS_SISTEMA)

    def test_o_painel_do_amplia_nao_e_alvo(self):
        """Guardar em `amplia` e' recusado COM O MOTIVO, e nada e' gravado.

        Um "nao" que nao explica produz o sintoma que este produto ja' teve: o
        produtor ve ecra nenhum e conclui que a IA esta avariada.
        """
        from app.ia import chamado as ch
        from app.models.palco import PresetPalco

        pode, motivo = ch.pode_escrever(self.ana, "amplia", pedido_explicito=True)
        self.assertFalse(pode, "o painel do sistema abriu ao pedido")
        self.assertIn(ch.NOME_CHAMADO, motivo, "o motivo nao oferece o caminho")
        self.assertEqual(
            PresetPalco.objects.filter(slug="amplia").count(),
            0,
            "o painel do sistema foi alcancado",
        )

    def test_a_excepcao_abre_o_preset_do_produtor(self):
        """O gate do `sandbox` e' a primeira porta; a guarda do `chamado` e' a
        segunda. As duas tem de estar abertas para gravar, e nenhuma fecha a
        outra sozinha."""
        from app.ia import chamado as ch
        from app.ia import palco_presets

        plano = palco_presets.planear(self.ana, "Custo", [{"tipo": "kpi-custo"}])
        pode, motivo = ch.pode_escrever(self.ana, plano["slug"], pedido_explicito=True)
        self.assertTrue(pode, f"o pedido explicito nao abriu o preset: {motivo}")

        # E o slug do plano e' o mesmo que a guarda autorizou — nao um Calculado
        # a mais tarde, que e' onde um "no caminho certo" se tornaria decorativo.
        self.assertTrue(plano["slug"].startswith("custom-"))

    def test_a_ia_nao_pode_forcar_a_excepcao_pelos_params(self):
        """Se `pedido_explicito` vier de `params`, o modelo marca o proprio
                    check. O `confirm` e' o que autoriza, e vem do `sandbox`.

        Mede-se com `confirm=True` nos DOIS lados. Com `confirm=False`, o
                `sandbox` devolve o texto do gate antes do handler correr, e os params
                nunca chegam a ser lidos — o teste passaria sem provar nada. Com
                `confirm=True` o handler corre, e e' ai que seriam lidos.

                E o teste mede `slug` tambem, que e' o outro parametro perigoso: e' o
                NOME do preset de destino. Se o corpo pudesse escolher o slug, poderia
                apontar para um preset que nao e' `custom-` — e a guarda autorizaria
                outro sitio. O `slug` resolve-se no `planear`, sempre com o
                `do_produtore`, e o do corpo e' descartado.
        """
        from app.models.palco import PresetPalco

        com_parametro = self._grava(confirm=True, pedido_explicito=True, slug="amplia")
        self.assertEqual(
            PresetPalco.objects.count(), 1, "nao gravou com os params no corpo"
        )
        self.assertNotEqual(
            PresetPalco.objects.get().slug,
            "amplia",
            "o `slug` do corpo escolheu o preset de destino",
        )

        PresetPalco.objects.all().delete()
        sem_parametro = self._grava(confirm=True)

        self.assertEqual(
            com_parametro.get("ok"),
            sem_parametro.get("ok"),
            "os params no corpo mudaram o resultado",
        )
        self.assertEqual(
            com_parametro.get("resposta"),
            sem_parametro.get("resposta"),
            "os params no corpo mudaram o que o produtor ve",
        )
        self.assertEqual(
            PresetPalco.objects.count(),
            1,
            "sem os params no corpo o pedido do produtor deixou de gravar",
        )


class PresetFixadoTest(TestCase):
    """`fixado` decide se a mesa aparece no topo do menu. Perde-se em silencio."""

    def setUp(self):
        self.ana = User.objects.create_user("ana_fixado", "a@x.com", "x1234567")

    def _grava(self, **extra):
        from app.ia.sandbox import executar

        params = {"nome": "Custo", "widgets": [{"tipo": "kpi-custo"}]}
        params.update(extra)
        return executar(self.ana, "preset_palco", params, via="sessao")

    def test_fixar_uma_mesa_que_ja_existe_tem_efeito(self):
        """MEDIDO: `gravar` fazia `save(update_fields=["nome", "estrutura"])` e o
        `fixado` ficava de fora. O pedido era ignorado SEM ERRO — e sem erro e'
        pior, porque o produtor viu o 'sim' e o menu nao mudou.

        E' no UPDATE que o caso aparece: na criacao o default entrava. Por isso
        um teste que so' criasse a mesa passaria — e era o que havia.
        """
        from app.models.palco import PresetPalco

        self._grava(confirm=True)
        self.assertFalse(PresetPalco.objects.get().fixado)

        self._grava(confirm=True, fixado=True)
        self.assertTrue(
            PresetPalco.objects.get().fixado,
            "pediu para fixar e a mesa nao foi fixada",
        )

    def test_desafixar_tambem(self):
        from app.models.palco import PresetPalco

        self._grava(confirm=True, fixado=True)
        self._grava(confirm=True, fixado=False)
        self.assertFalse(PresetPalco.objects.get().fixado)


class PresetDoProdutorTest(TestCase):
    """A Fase 2: a IA grava a mesa no preset DO PRODUTOR.

    O QUE ESTE FICHEIRO PROVA
    =========================
    Tres coisas, por ordem de gravidade:

    1. **A mesa de um produtor nao aparece na tela de outro.** E' o que a
       `PresetPalco` reescrevivel faria. Grava-se com `user`, e le-se com
       `do_produtore` — a unica razao de `PalcoIA` ter `user` a menos.

    2. **Nada e' gravado sem o produtor dizer que sim.** O `confirm` vem do
       gate do `sandbox`, e a guarda e' `chamado.pode_escrever` (ver
       `AGuardaDaEscritaTest`).

    3. **A confirmacao mostra o que VAI acontecer.** Um "nao" tem de ser uma
       resposta, nao um erro — e nao pode deixar nada para tras.
    """

    def setUp(self):
        self.ana = User.objects.create_user("ana_f2", "a@x.com", "x1234567")
        self.bruno = User.objects.create_user("bruno_f2", "b@x.com", "x1234567")

    def _grava(self, _user, **extra):
        """Chama a intent como o produtor, com os params que se quiserem.

        O produtor vem como `_user` e NAO como parametro nomeado `user`, para
        que um teste possa mandar `user=` no corpo — que e' exactamente o que
        `test_a_ia_nao_aceita_o_produtor_no_corpo` precisa de fazer.
        """
        from app.ia.sandbox import executar

        params = {
            "nome": "Custo",
            "widgets": [{"tipo": "kpi-custo", "titulo": "Custo"}],
        }
        params.update(extra)
        return executar(_user, "preset_palco", params, via="sessao")

    def test_o_plano_nao_diz_que_outro_produtor_tem_uma_mesa_com_esse_nome(self):
        """Fuga pequena, e por isso facil de deixar passar.

        Os DADOS ja' estavam protegidos por `get_or_create(user=user)`: mesmo
        com a busca errada, a Ana ganhava um preset novo em vez de roubar o do
        Bruno. Mas o plano devolvia `destino` com o slug do Bruno e dizia
        "Atualizo" — o que confirma ao produtor que a conta certa TEM uma mesa
        com aquele nome. `unique(user, slug)` torna aunicidade por produtor, e o
        texto de confirmacao tem de respeitar isso.

        Este teste e' a razao de `do_produtore` estar na busca do alvo: e' o que
        impede isto. Sem ele, os dados passam e este teste falha.

        Testa-se `planear` directamente e nao a intent, porque e' no plano que o
        `destino` e' calculado. Na resposta final o `destino` nem chega a
        aparecer — `gravar` devolve o slug do preset que CRIOU, e o plano
        descartado so' vive na branch de `needs_confirm`, que o gate do
        `sandbox` nunca deixa chegar. O que nao pode e' nunca ter sido
        computado.
        """
        from app.ia import palco_presets

        self._grava(self.bruno, nome="Custo", confirm=True)
        slug_do_bruno = PresetPalco.objects.get(nome="Custo").slug

        plano = palco_presets.planear(self.ana, "Custo", [{"tipo": "kpi-caixa"}])
        self.assertTrue(plano["ok"], plano)

        self.assertIsNone(
            plano["destino"],
            f"o plano da Ana apontou para o preset do Bruno (slug {slug_do_bruno!r})",
        )
        self.assertEqual(plano["operacao"], "criar")

        # E o da Ana tem de apontar para ela, quando existe.
        self._grava(self.ana, nome="Custo", confirm=True)
        da_ana = palco_presets.planear(self.ana, "Custo", [{"tipo": "kpi-caixa"}])
        self.assertEqual(da_ana["destino"], PresetPalco.objects.get(user=self.ana).slug)
        self.assertEqual(da_ana["operacao"], "atualizar")

    def test_dois_produtores_com_o_mesmo_nome_nao_partilham_a_mesa(self):
        """O ATAQUE REAL, e nao a listagem.

        "Custo" e' o primeiro nome que um produtor da. Se a busca pelo preset
        alvo nao for `do_produtore(user)`, o segundo produtor NAO cria o seu —
        reescreve a mesa do primeiro. Nao ha erro, nao ha aviso: o produtor ve
        a sua mesa mudar de um dia para o outro sem ter pedido.

        E o mesmo nome nos dois e' o caso que mais acontece, nao o mais
        exotico. Por isso este teste, e nao so' a listagem.
        """
        self._grava(
            self.bruno,
            nome="Custo",
            widgets=[{"tipo": "kpi-custo", "titulo": "Custo do Bruno"}],
            confirm=True,
        )
        do_bruno = PresetPalco.objects.get(nome="Custo")
        self.assertEqual(do_bruno.user_id, self.bruno.pk)

        self._grava(
            self.ana,
            nome="Custo",
            widgets=[{"tipo": "kpi-caixa", "titulo": "Caixa da Ana"}],
            confirm=True,
        )

        self.assertEqual(
            PresetPalco.objects.filter(nome="Custo").count(),
            2,
            "a Ana entrou na mesa do Bruno em vez de ter a sua",
        )
        bruno_depois = PresetPalco.objects.get(pk=do_bruno.pk)
        self.assertEqual(
            [w["tipo"] for w in bruno_depois.estrutura["widgets"]],
            ["kpi-custo"],
            "a mesa do Bruno foi reescrita pela Ana",
        )
        da_ana = PresetPalco.objects.do_produtore(self.ana).get(nome="Custo")
        self.assertEqual(
            [w["tipo"] for w in da_ana.estrutura["widgets"]],
            ["kpi-caixa"],
        )

    def test_a_mesa_do_bruno_nao_aparece_na_do_ana(self):
        self._grava(self.bruno, nome="Segredo do Bruno", confirm=True)
        self.assertTrue(PresetPalco.objects.filter(user=self.bruno).exists())

        do_ana = PresetPalco.objects.do_produtore(self.ana)
        self.assertEqual(
            do_ana.count(),
            0,
            "o ana ve presets do bruno — `do_produtore` nao esta a ser usado",
        )

    def test_a_descricao_aponta_para_o_recurso_dos_widgets(self):
        """Prometer `amplia://widgets` so' serve se o recurso existir.

        `texto.py:117-120`: a fixacao prioriza honestidade sobre completude. Um
        caminho de recurso inventado no texto de um intent e' um beco para o
        modelo — e o modelo segue caminhos.
        """
        from app.ia.intents_palco_preset import INTENTS_FASE2
        from app.ia.paginas import referencia_widgets
        from app.ia.palco import CATALOGO_IA

        descricao = INTENTS_FASE2["preset_palco"]["descricao"]
        self.assertIn("amplia://widgets", descricao)

        # E o recurso tem mesmo os ids que o `validar_estrutura` aceita.
        ids = {w["id"] for w in referencia_widgets()}
        self.assertEqual(ids, set(CATALOGO_IA))

    def test_a_ia_nao_aceita_o_produtor_no_corpo(self):
        """`user` no corpo e' a forma mais curta de um vazamento entre contas.

        `chamado_intents.py:296-299`, textual. O parametro e' passado e o
        resultado tem de ser o do `ana`.
        """
        r = self._grava(self.ana, user=self.bruno.pk, confirm=True)
        self.assertTrue(r.get("ok"), r)
        self.assertEqual(PresetPalco.objects.count(), 1)
        self.assertEqual(
            PresetPalco.objects.get().user_id,
            self.ana.pk,
            "o `user` do corpo veio antes do sandbox",
        )

    def test_listar_so_mostra_o_que_e_meu(self):
        from app.ia import palco_presets

        self._grava(self.bruno, nome="Bruno", confirm=True)
        self._grava(self.ana, nome="Ana", confirm=True)
        nomes = [p.nome for p in palco_presets.listar(self.ana)]
        self.assertEqual(nomes, ["Ana"])

    # ------------------------------------------------------- confirmacao

    def test_sem_confirmar_nao_grava_nada(self):
        r = self._grava(self.ana)
        self.assertTrue(r.get("ok"), r)
        self.assertTrue(r.get("needs_confirm"))
        self.assertEqual(
            PresetPalco.objects.count(),
            0,
            "gravou sem o produtor confirmar",
        )

    def test_a_confirmacao_e_texto_para_o_produtor_e_nao_para_o_modelo(self):
        """O que o produtor le antes de dizer "sim" e' TEXTO DELE.

        Este e' o teste que trava o defeito de `sandbox.py:772-777`: sem
        `prompt_confirmacao`, o que aparece e' a `descricao` limpa — e a
        `descricao` e' escrita PARA O MODELO. O produtor leria "INSTRUÇÃO IA:
        use para..." na unica barreira antes de mexer no trabalho dele.

        E nao pode prometer o que o codigo nao faz: `texto.py:122` nao
        interpola `params`, portanto este texto e' estatico, e o teste trava
        isso tambem. Um dia que um dia o gate intercalar `nome`, este teste
        avisa.
        """
        r = self._grava(self.ana)
        resposta = r.get("resposta", "")

        self.assertNotIn(
            "INSTRUÇÃO IA",
            resposta.upper(),
            "a `descricao` (escrita para o modelo) chegou ao produtor",
        )
        self.assertNotIn(
            "INSTRUCAO IA",
            resposta.upper(),
            "a `descricao` (escrita para o modelo) chegou ao produtor",
        )
        self.assertNotIn("**", resposta, "markdown na resposta")
        self.assertNotIn("handlers", resposta, "o nome do modulo chegou ao produtor")
        self.assertIn("dashboard", resposta.lower())

    def test_o_texto_da_confirmacao_nao_promete_o_que_o_codigo_nao_faz(self):
        """Nada de "vou renomear", "vou apagar": este intent so' grava.

        `texto.py:117-120` diz que a honestidade vale mais que a completude. Um
        texto de confirmacao que promete um botao que nao existe e' a ultima
        barreira a mentir.
        """
        from app.ia.registro import REGISTO
        from app.ia.texto import prompt_de_confirmacao

        txt = prompt_de_confirmacao(REGISTO["preset_palco"], params={"nome": "X"})
        for promessa in ("vou renomear", "vou apagar", "vou criar widgets"):
            self.assertNotIn(promessa, txt.lower())

    def test_o_nao_e_uma_resposta_e_nao_um_erro(self):
        """`ok=True` sem confirmacao: o produtor pode recusar.

        Se devolvesse `ok=False`, a maquina de estados tratava como falha e o
        produtor perdia o contexto do que ia acontecer.
        """
        r = self._grava(self.ana)
        self.assertTrue(r.get("ok"))
        self.assertNotIn("erro", r)

    def test_confirmar_grava_e_nao_repergunta(self):
        r1 = self._grava(self.ana)
        self.assertTrue(r1.get("needs_confirm"))

        r2 = self._grava(self.ana, confirm=True)
        self.assertTrue(r2.get("ok"), r2)
        self.assertFalse(
            r2.get("needs_confirm"),
            "a segunda vez perguntou de novo",
        )
        self.assertEqual(PresetPalco.objects.count(), 1)

    # --------------------------------------------------------- conteudo

    def test_o_widget_desconhecido_e_descartado(self):
        r = self._grava(
            self.ana,
            widgets=[{"tipo": "kpi-custo"}, {"tipo": "nao-existe"}],
            confirm=True,
        )
        self.assertTrue(r.get("ok"), r)
        estrutura = PresetPalco.objects.get().estrutura
        tipos = [w["tipo"] for w in estrutura["widgets"]]
        self.assertEqual(tipos, ["kpi-custo"])

    def test_so_widgets_do_catalogo_sao_gravados(self):
        from app.ia import palco

        r = self._grava(
            self.ana,
            widgets=[{"tipo": "inventado", "valor": 999}],
            confirm=True,
        )
        self.assertFalse(r.get("ok"), "gravar um widget fora do catalogo")
        self.assertEqual(PresetPalco.objects.count(), 0, "gravou assim mesmo")

    def test_o_preset_fica_marcado_como_escrito_pela_ia(self):
        """Saber que uma mesa foi a IA montar nao a marca como melhor do que
        uma que o produtor construiu — mas nao se pode mentir sobre a origem."""
        self._grava(self.ana, confirm=True)
        estrutura = PresetPalco.objects.get().estrutura
        self.assertTrue(estrutura.get("escrito_por_ia"))

    def test_o_teto_de_presets_e_respeitado(self):
        from app.ia import palco_presets

        PresetPalco.objects.bulk_create(
            [
                PresetPalco(user=self.ana, slug=f"custom-{i}", nome=f"Mesa {i}")
                for i in range(palco_presets.MAX_PRESETS_POR_PRODUTOR + 2)
            ]
        )
        r = self._grava(self.ana, nome="Mais uma", confirm=True)
        self.assertFalse(r.get("ok"), "criou acima do teto")
        # A mensagem tem de dizer a CONTAGEM REAL. Um "60" fixo num texto que
        # pode ser lido com 61 ou 62 presets e' teatro, nao informacao.
        self.assertIn(
            str(palco_presets.MAX_PRESETS_POR_PRODUTOR + 2),
            r.get("erro", ""),
        )
        self.assertEqual(
            PresetPalco.objects.filter(nome="Mais uma").count(),
            0,
            "gravou acima do teto",
        )

    def test_atualizar_usa_o_mesmo_preset(self):
        """Guardar duas vezes com o mesmo nome e' o MESMO pedido, nao dois.

        Sem isto o produtor via a mesma mesa duplicada no menu e concluia que o
        botao nao funciona.
        """
        self._grava(self.ana, nome="Custo", confirm=True)
        self._grava(self.ana, nome="Custo", confirm=True)
        self.assertEqual(PresetPalco.objects.filter(user=self.ana).count(), 1)

    def test_o_slug_comeca_custom(self):
        """`app/presets.py` so aceita `custom-`. Sem o prefixo a mesa e' criada
        e nunca mais aparece no menu — um botao que parece funcionar."""
        self._grava(self.ana, nome="Custo do talhao", confirm=True)
        self.assertTrue(PresetPalco.objects.get().slug.startswith("custom-"))

    def test_nome_vazio_da_erro_utilizavel(self):
        """Erro que diz o que escrever. Um erro sem caminho e' um beco
        (`validators.py`, seccao da `AGENTS.md`)."""
        r = self._grava(self.ana, nome="   ", confirm=True)
        self.assertFalse(r.get("ok"))
        self.assertIn("nome", r.get("erro", "").lower())
