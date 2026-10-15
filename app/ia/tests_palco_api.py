"""As vistas do palco, e sobretudo: o que um produtor NÃO pode fazer.

Estes testes existem por causa de uma frase: o pedido mais importante do
produto é o que a IA responde, e uma falha de tenancy aí não dá erro — dá uma
mesa de operação com os números de outra pessoa, que o produtor lê como
suínos e age em cima. Um dashboard bonito e errado é pior do que um 500.

Por isso o foco está nos ataques, não no caminho feliz. O caminho feliz é
óbvio; o `pk` trocado no pedido não é.
"""

from __future__ import annotations

import json

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from app.models import AssinaturaPalco, PresetPalco


class BasePalco(TestCase):
    def setUp(self):
        self.ana = User.objects.create_user("ana", "a@x.com", "p")
        self.bruno = User.objects.create_user("bruno", "b@x.com", "p")
        self.client.force_login(self.ana)
        self.url_render = reverse("amplia_mcp:palco_render")
        self.url_avaliar = reverse("amplia_mcp:palco_avaliar")
        self.url_clonar = reverse("amplia_mcp:palco_clonar")
        self.url_info = reverse("amplia_mcp:palco_info")

    def post(self, url, dados):
        return self.client.post(
            url, data=json.dumps(dados), content_type="application/json"
        )

    @staticmethod
    def mesa(n=2):
        # Ids do catálogo REAL. A primeira versão usava `chart-financeiro`,
        # que era uma entrada de LAYOUT do dashboard e não um widget com
        # dados — o servidor descartava-o, e o teste falhava por 1 != 2 sem
        # ninguém perceber que o erro estava no id e não na contagem.
        return {
            "widgets": ["kpi-custo", "kpi-produtividade", "kpi-caixa"][:n],
            "layout": "grid-mixed",
        }

    def assinatura_do_bruno(self, pergunta="custo do talhao 2"):
        from app.ia import palco

        return AssinaturaPalco.objects.create(
            user=self.bruno,
            assinatura=palco.assinatura_do_intent(pergunta),
            intent_texto=pergunta,
            estrutura=self.mesa(),
            veredito="like",
        )


class RenderTest(BasePalco):
    def test_render_devolve_a_mesa_validada(self):
        r = self.post(self.url_render, {"intent": "custo do talhao 2", **self.mesa()})
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertTrue(d["ok"])
        self.assertEqual(len(d["widgets"]), 2)
        self.assertEqual(d["palco"], "amplia")
        self.assertTrue(d["assinatura"])

    def test_render_nao_grava_nada(self):
        """A mesa é efemérica. Gravar aqui faria cada pergunta virar uma mesa
        permanente, e o dashboard de amanhã abriria com a resposta de ontem."""
        self.post(self.url_render, {"intent": "custo", **self.mesa()})
        self.assertEqual(AssinaturaPalco.objects.count(), 0)
        self.assertEqual(PresetPalco.objects.count(), 0)

    def test_widget_inventado_cai_fora_sem_matar_a_mesa(self):
        r = self.post(
            self.url_render, {"intent": "x", "widgets": ["kpi-custo", "nao-existe"]}
        )
        d = r.json()
        self.assertEqual(len(d["widgets"]), 1)
        self.assertTrue(any("desconhecido" in x for x in d["descartados"]))

    def test_ia_que_nao_manda_nada_da_422_com_mensagem(self):
        r = self.post(self.url_render, {"intent": "x", "widgets": []})
        self.assertEqual(r.status_code, 422)
        self.assertIn("nenhum widget", r.json()["erro"])

    def test_corpo_invalido_nao_da_500(self):
        r = self.client.post(
            self.url_render, data="{isto nao e json", content_type="application/json"
        )
        self.assertEqual(r.status_code, 422)

    def test_exige_login(self):
        self.client.logout()
        r = self.post(self.url_render, self.mesa())
        self.assertIn(r.status_code, (302, 401, 403))

    def test_get_nao_e_aceite(self):
        r = self.client.get(self.url_render)
        self.assertIn(r.status_code, (405, 302))


class AvaliarTest(BasePalco):
    def test_like_cria_a_assinatura(self):
        r = self.post(
            self.url_avaliar,
            {
                "assinatura": "custodotalhao2",
                "intent": "custo do talhao 2",
                "veredito": "like",
                "estrutura": self.mesa(),
            },
        )
        self.assertEqual(r.status_code, 200)
        a = AssinaturaPalco.objects.get()
        self.assertEqual(
            a.user, self.ana, "a assinatura e SEMPRE do produtor que avaliou"
        )
        self.assertEqual(a.veredito, "like")

    def test_dislike_guarda_a_lacuna(self):
        self.post(
            self.url_avaliar,
            {
                "assinatura": "x1",
                "intent": "custo",
                "veredito": "dislike",
                "lacuna": "faltou o custo por hectare",
                "estrutura": self.mesa(),
            },
        )
        self.assertEqual(
            AssinaturaPalco.objects.get().lacuna, "faltou o custo por hectare"
        )

    def test_a_mesma_pergunta_consolida_numa_linha_so(self):
        """Mil Likes da mesma pergunta são uma linha de treino a ser
        reforçada, não mil linhas."""
        for _ in range(3):
            self.post(
                self.url_avaliar,
                {
                    "assinatura": "x1",
                    "intent": "custo",
                    "veredito": "like",
                    "estrutura": self.mesa(),
                },
            )
        self.assertEqual(AssinaturaPalco.objects.count(), 1)

    def test_veredito_novo_substitui_o_anterior(self):
        self.post(
            self.url_avaliar,
            {
                "assinatura": "x1",
                "intent": "custo",
                "veredito": "like",
                "estrutura": self.mesa(),
            },
        )
        self.post(
            self.url_avaliar,
            {
                "assinatura": "x1",
                "intent": "custo",
                "veredito": "dislike",
                "estrutura": self.mesa(),
            },
        )
        a = AssinaturaPalco.objects.get()
        self.assertEqual(a.veredito, "dislike")
        self.assertEqual(len(a.historico), 1)

    def test_veredito_invalido_recusado(self):
        r = self.post(
            self.url_avaliar,
            {"assinatura": "x1", "veredito": "talvez", "estrutura": self.mesa()},
        )
        self.assertEqual(r.status_code, 422)
        self.assertEqual(AssinaturaPalco.objects.count(), 0)

    def test_assinatura_ausente_recusada(self):
        r = self.post(self.url_avaliar, {"veredito": "like", "estrutura": self.mesa()})
        self.assertEqual(r.status_code, 400)

    def test_dislike_do_bruno_nao_toca_na_da_ana(self):
        """Cada produtor tem a sua linha. Uma intencao partilhada não funde
        TRAININGS de pessoas diferentes — o que o produtor A aprovou não é
        verdade sobre o B."""
        self.assinatura_do_bruno()
        self.post(
            self.url_avaliar,
            {
                "assinatura": "custodotalhao2",
                "veredito": "dislike",
                "estrutura": self.mesa(),
            },
        )
        bruno = AssinaturaPalco.objects.get(user=self.bruno)
        self.assertEqual(
            bruno.veredito, "like", "o dislike da Ana nao reescreve a do Bruno"
        )


class ClonarTest(BasePalco):
    def test_clonar_cria_preset_do_produtor(self):
        r = self.post(
            self.url_clonar, {"nome": "Custo por Talhão", "estrutura": self.mesa()}
        )
        self.assertEqual(r.status_code, 201)
        p = PresetPalco.objects.get()
        self.assertEqual(p.user, self.ana)
        self.assertEqual(p.nome, "Custo por Talhão")

    def test_o_slug_comeca_custom_para_o_dashboard_aceitar(self):
        """Sem `custom-`, a mesa é criada e nunca aparece no menu: um botão que
        parece funcionar e não faz nada."""
        from app.presets import preset_permitido

        self.post(
            self.url_clonar, {"nome": "Custo por Talhão", "estrutura": self.mesa()}
        )
        slug = PresetPalco.objects.get().slug
        self.assertTrue(slug.startswith("custom-"), slug)
        self.assertTrue(
            preset_permitido(slug), "o dashboard existente rejeitaria este slug"
        )

    def test_nao_adota_assinatura_de_outro_produtor(self):
        """O ATAQUE. Trocar a assinatura no pedido para apontar o dashboard à
        linha de outro produtor. A resposta tem de ser 200 sem `origem` — o
        dashboard do produtor é legítimamente seu; o que não pode é ser
        pendurado no treino de outra pessoa."""
        alheia = self.assinatura_do_bruno()
        r = self.post(
            self.url_clonar,
            {
                "nome": "Minha",
                "estrutura": self.mesa(),
                "assinatura": alheia.assinatura,
            },
        )
        self.assertEqual(r.status_code, 201)
        meu = PresetPalco.objects.get(user=self.ana)
        self.assertIsNone(meu.origem, "adotou a assinatura de outro produtor")
        self.assertNotEqual(meu.origem_id, alheia.pk)

    def test_assinatura_propria_e_adotada(self):
        self.post(
            self.url_avaliar,
            {"assinatura": "x1", "veredito": "like", "estrutura": self.mesa()},
        )
        self.post(
            self.url_clonar,
            {"nome": "Minha", "estrutura": self.mesa(), "assinatura": "x1"},
        )
        self.assertIsNotNone(PresetPalco.objects.get().origem)

    def test_clicar_duas_vezes_atualiza_sem_erro(self):
        """Clicar duas vezes em "Salvar" não pode dar 409: é o mesmo pedido, e
        tratá-lo como conflito faria o botão parecer quebrado."""
        r1 = self.post(self.url_clonar, {"nome": "Minha", "estrutura": self.mesa(1)})
        r2 = self.post(self.url_clonar, {"nome": "Minha", "estrutura": self.mesa(2)})
        self.assertEqual(r1.status_code, 201)
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(PresetPalco.objects.count(), 1)
        self.assertEqual(len(PresetPalco.objects.get().estrutura["widgets"]), 2)

    def test_mesa_vazia_nao_cria_preset(self):
        r = self.post(self.url_clonar, {"nome": "Minha", "estrutura": {"widgets": []}})
        self.assertEqual(r.status_code, 422)
        self.assertEqual(PresetPalco.objects.count(), 0)

    def test_nomes_diferentes_dao_presets_diferentes(self):
        self.post(self.url_clonar, {"nome": "Custo", "estrutura": self.mesa()})
        self.post(self.url_clonar, {"nome": "Chuva", "estrutura": self.mesa()})
        self.assertEqual(PresetPalco.objects.count(), 2)

    def test_o_preset_nunca_leva_dono_do_pedido(self):
        """Não existe campo de dono no payload, e mesmo que se invente um, a
        vista não o lê."""
        r = self.post(
            self.url_clonar,
            {
                "nome": "Minha",
                "estrutura": self.mesa(),
                "user": self.bruno.pk,
                "user_id": self.bruno.pk,
            },
        )
        self.assertEqual(r.status_code, 201)
        self.assertEqual(PresetPalco.objects.get().user, self.ana)


class InfoTest(BasePalco):
    def test_info_so_lista_o_que_e_meu(self):
        self.post(self.url_clonar, {"nome": "Minha", "estrutura": self.mesa()})
        self.client.force_login(self.bruno)
        d = self.client.get(self.url_info).json()
        self.assertEqual(d["meus_presets"], [], "o Bruno nao ve a mesa da Ana")
        self.assertTrue(d["palco"]["fluido"])

    def test_info_exige_login(self):
        self.client.logout()
        r = self.client.get(self.url_info)
        self.assertIn(r.status_code, (302, 401, 403))

    def test_catalogo_e_publico(self):
        """O JS precisa de saber o que existe para não oferecer widget que o
        servidor vai descartar."""
        d = self.client.get(self.url_info).json()
        cat = d["catalogo"]
        self.assertIn("kpi-custo", cat)
        # E cada widget declara de onde vem o seu dado. Um widget offered sem
        # fonte e' a premissa errada de volta: o modelo escolhe, o servidor
        # nao sabe preencher, e a mesa fica com titulos e zeros.
        for tipo, spec in cat.items():
            self.assertIn(spec.get("fonte"), ("servidor", "top_globais"), tipo)


# =============================================================================
# A intent que liga a IA a mesa
# =============================================================================
#
# O INTENT, e nao o texto. `ia-local.js` passa a resposta do modelo por
# `sanitizarResposta`, que remove cercas ``` e todo o JSON antes de qualquer
# consumidor a ver. Um protocolo baseado num bloco de cerca nunca chegaria ao
# ecra — e nenhum teste unitario do parser dizia isso, porque o parsing, sozinho,
# estava certo. A via certa ja existia: a IA pede uma tool, a tool e um intent
# no sandbox, o sandbox valida e devolve `dados`.


class RenderPresetIntentTest(TestCase):
    def setUp(self):
        self.ana = User.objects.create_user("ana", "a@x.com", "p")

    def _executa(self, **params):
        from app.ia.sandbox import executar

        return executar(self.ana, "render_preset", params)

    def test_a_intent_existe_e_e_de_leitura(self):
        """Uma intent que escreve fica na lista com flag, para o sandbox
        continuar a separar o que le do que age. Montar uma mesa nao age sobre
        o mundo: so desenha o que ja estava la."""
        from app.ia.sandbox import INTENTS, somente_leitura

        self.assertIn("render_preset", INTENTS)
        self.assertTrue(somente_leitura(INTENTS["render_preset"]))
        self.assertEqual(
            INTENTS["render_preset"]["flags"],
            ["palco.read"],
            "um intent sem flags e presumido de ESCRITA; esta so desenha",
        )

    def test_a_intent_aparece_no_catalogo_que_o_modelo_ve(self):
        """Se nao aparecer no catalogo, o modelo nunca a chama — e o defeito
        aparece como 'a IA nao monta nada', que e indistinguivel de 'a IA e
        burra'."""
        from app.amplia_mcp import catalogo_tools

        nomes = [t["name"] for t in catalogo_tools()]
        self.assertIn("amplia_render_preset", nomes)

    def test_a_descricao_diz_quando_usar_e_quando_nao(self):
        """Um 1B decide pela descricao. Sem o 'NAO use para', ele leva a mesa
        para 'vai chover' e o produtor recebe um dashboard em vez de uma
        previsao — que e o pior sitio possivel para desperdicar a confianca."""
        from app.ia.sandbox import INTENTS

        d = INTENTS["render_preset"]["descricao"]
        self.assertIn("NÃO use", d)
        self.assertIn("kpi-custo", d)

    def test_monta_a_mesa_validada(self):
        r = self._executa(
            intent="custo do talhao 2", widgets=["kpi-custo", "kpi-produtividade"]
        )
        self.assertTrue(r["ok"])
        d = r["dados"]
        self.assertEqual(d["palco"], "amplia")
        self.assertEqual(
            [w["tipo"] for w in d["widgets"]], ["kpi-custo", "kpi-produtividade"]
        )
        self.assertTrue(d["assinatura"])

    def test_a_resposta_nao_fala_em_ids_de_widget(self):
        """A `resposta` é o texto que o produtor LÊ.

        Pelo caminho governado (`ia-local.js`) o `r.resposta` do sandbox vai
        directo para a tela: não há nada entre ele e o chat que o reescreva.
        E era lá que ids internos apareciam — "Mesa montada no preset Amplia:
        kpi-custo, kpi-produtividade" — que é sintaxe de máquina apresentada
        ao produtor no lugar de uma resposta. `kpi-produtividade` não lhe diz
        nada sobre a safra dele.

        O `tipo` continua nos `dados`, que é onde o frontend o precisa para
        escolher o renderizador. Só a frase muda.
        """
        r = self._executa(
            intent="custo do talhao 2", widgets=["kpi-custo", "kpi-produtividade"]
        )
        self.assertTrue(r["ok"])
        texto = r["resposta"]

        for interno in ("kpi-custo", "kpi-produtividade"):
            self.assertNotIn(
                interno,
                texto,
                "a frase que o produtor le nao pode trazer o id do widget",
            )
        # E tem de dizer ALGUMA coisa de jeito: trocar ids por nada nao é
        # corrigir, é apagar a resposta.
        self.assertIn("Mesa montada", texto)

    def test_a_resposta_diz_o_que_faltou_lancar(self):
        """O que ficou sem numero é distinto do que está a zero.

        Uma mesa montada sem nenhum lançamento não é uma mesa vazia: é uma
        safra que o produtor ainda não registou. Se a frase não disser isso, o
        que ele lê é "montei um painel e não tem nada", e a conclusão que ele
        tira — que a IA falhou — é errada.
        """
        r = self._executa(intent="custo", widgets=["kpi-custo"])
        self.assertTrue(r["ok"])
        # O utilizador de teste não tem lançamentos: tudo fica sem dado.
        self.assertTrue(r["dados"]["sem_dado"])
        # A palavra da tela é "sem dado"; a da frase é "lançado", porque é
        # essa a acção que falta ao produtor. O que se verifica é que a
        # frase diz que falta algo — não que repita o rótulo do cartão.
        self.assertIn("lançado", r["resposta"].lower())

    def test_a_lista_de_sem_dado_conta_o_que_a_proveniencia_marcou(self):
        """A lista tem de vir do `fonte_dado`, e não de "o config está vazio".

        `_proveniencia` nunca devolve um config vazio — mesmo sem medição
        nenhuma escreve `fonte_dado: sem_dado`. A lista antiga olhava para o
        config vazio, e por isso ficava VAZIA mesmo com a mesa toda sem
        número. E o `dados` volta ao modelo como contexto: ensinava-lhe que
        não faltava nada, e a IA contava ao produtor uma tela cheia de vazio
        como se fosse uma resposta completa.
        """
        r = self._executa(intent="custo", widgets=["kpi-custo"])
        marcado = [
            w["tipo"]
            for w in r["dados"]["widgets"]
            if (w.get("config") or {}).get("fonte_dado") == "sem_dado"
        ]
        self.assertTrue(marcado, "o widget devia estar marcado como sem dado")
        self.assertEqual(
            r["dados"]["sem_dado"],
            marcado,
            "a lista e o config tem de contar a mesma coisa",
        )

    def test_widget_com_dado_nao_entra_na_lista_de_sem_dado(self):
        """O contrário também é obrigatório.

        Um widget que TEM medição e aparecesse na lista de sem dado faria o
        produtor desconfiar de um número que está certo — e o custo de um
        falso "falta dado" é maior do que o de omitir a lista.
        """
        from decimal import Decimal

        from django.utils import timezone

        from app.models import LancamentoFinanceiro, Propriedade

        u = User.objects.get(username="ana")
        prop = Propriedade.objects.create(
            user=u, nome="Sitio", area_total=Decimal("100")
        )
        LancamentoFinanceiro.objects.create(
            propriedade=prop,
            tipo="DESPESA",
            categoria="INSUMOS",
            valor=Decimal("100"),
            data=timezone.now().date(),
        )
        r = self._executa(intent="custo", widgets=["kpi-custo"])
        self.assertTrue(r["ok"])
        self.assertNotIn(
            "kpi-custo",
            r["dados"]["sem_dado"],
            "ha despesa lancada: este widget tem medicao",
        )

    def test_a_frase_tem_os_titulos_que_os_cartoes_mostram(self):
        """A frase e a tela dizem a mesma coisa.

        O `titulo` é o que o cartão mostra; se a frase disser outra coisa, o
        produtor lê duas versões da mesma mesa e não sabe qual é a verdade.
        """
        r = self._executa(intent="custo", widgets=["kpi-custo"])
        titulos = [w["titulo"] for w in r["dados"]["widgets"]]
        for t in titulos:
            self.assertIn(t, r["resposta"])

    def test_widget_inventado_e_descartado_com_marca(self):
        """E descartado COM a marca de que foi. Um `dados` silencioso sem o
        descartado parece 'a IA escolheu assim', e ninguem percebe que a
        pergunta nao foi respondida por completo."""
        r = self._executa(intent="x", widgets=["kpi-custo", "widget-que-nao-existe"])
        self.assertTrue(r["ok"])
        self.assertEqual(len(r["dados"]["widgets"]), 1)
        self.assertTrue(any("desconhecido" in x for x in r["dados"]["descartados"]))

    def test_nada_reconhecido_da_erro_com_o_catalogo(self):
        """A IA precisa de saber o que pode usar, no momento em que falhou. Um
        'nenhum widget reconhecido' sem lista deixa o modelo a tentar o mesmo
        id errado."""
        r = self._executa(intent="x", widgets=["inventado"])
        self.assertFalse(r["ok"])
        self.assertIn("catalogo", r["dados"])

    def test_nao_grava_nada(self):
        """A mesa e efemera. Gravar aqui faria cada pergunta virar um dashboard
        permanente, e o produtor abriria amanha uma tela que nao pediu."""
        from app.models import AssinaturaPalco, PresetPalco

        self._executa(intent="custo do talhao 2", widgets=["kpi-custo"])
        self.assertEqual(AssinaturaPalco.objects.count(), 0)
        self.assertEqual(PresetPalco.objects.count(), 0)

    def test_a_intent_nao_depende_de_ter_dados_do_usuario(self):
        """Montar a mesa e formatar; os dados vem do que a tool trouxer. Uma
        intent que exigisse propriedade transformaria 'monte um painel de custo'
        numa falha de cadastro, e o produtor culparia a IA."""
        r = self._executa(intent="monte um painel qualquer", widgets=["kpi-custo"])
        self.assertTrue(r["ok"])

    # --- Novos testes da Fase E ---
    def test_config_da_ia_sobrevive_quando_o_servidor_nao_preenche(self):
        """O config da IA sobrevive quando o servidor não preenche (top_globais)."""
        r = self._executa(
            intent="teste",
            widgets=[{"tipo": "kpi-chuva-1km", "config": {"periodo": "prox7"}}],
        )
        self.assertTrue(r["ok"])
        d = r["dados"]
        # O config da IA deve permanecer intacto, e sem_dado=True é adicionado
        self.assertEqual(
            d["widgets"][0]["config"].get("periodo"),
            "prox7",
            "O config da IA deve permanecer intacto para widgets top_globais",
        )
        self.assertTrue(
            d["widgets"][0]["config"].get("sem_dado"),
            "sem_dado deve ser True para widgets top_globais",
        )

    def test_o_servidor_ganha_a_colisao(self):
        """O servidor ganha na colisão de chaves que ELE produz.

        Chaves que só a IA mandou sobrevivem. Chaves que o servidor calcula são
        sobrescritas pelo servidor.
        """
        r = self._executa(
            intent="teste",
            widgets=[{"tipo": "kpi-custo", "config": {"valor": 999, "periodo": "2021"}}],
        )
        self.assertTrue(r["ok"])
        d = r["dados"]
        config = d["widgets"][0]["config"]
        # period é chave só da IA → sobrevive
        self.assertEqual(
            config.get("periodo"),
            "2021",
            "Chave da IA que o servidor não produziu deve sobreviver",
        )
        # valor: o servidor NÃO produziu (sem dados no BD), então o da IA fica
        # Se o servidor tivesse produzido, ele sobrescreveria
        self.assertEqual(
            config.get("valor"),
            999,
            "Como o servidor não tem dados, o valor da IA permanece",
        )
        # O servidor adiciona seus metadados
        self.assertEqual(config.get("fonte_dado"), "sem_dado")

    def test_sem_dado_aponta_widget_sem_numero_do_banco(self):
        """sem_dado indica widgets sem número do banco (top_globais ou servidor sem dados)."""
        r = self._executa(
            intent="teste",
            widgets=[{"tipo": "kpi-chuva-1km", "config": {"periodo": "prox7"}}],
        )
        self.assertTrue(r["ok"])
        d = r["dados"]
        self.assertIn(
            "kpi-chuva-1km",
            d["sem_dado"],
            "kpi-chuva-1km deve aparecer em sem_dado pois é top_globais",
        )
