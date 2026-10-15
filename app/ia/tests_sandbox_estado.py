"""Uma pergunta pendente não pode sequestrar uma chamada programática.

Esta é a classe de defeito que o `tests/e2e/chamado.spec.ts` encontrou no
browser e que nenhum teste apanhava: uma peça reescrita que não aparecia, com o
servidor a dizer `ok: true`.

O que acontecia
===============
`executar()` recupera o estado conversacional — `COLETANDO_DADOS`,
`AGUARDANDO_CONFIRMACAO` — para transformar a resposta do produtor no resto do
que faltava. Fazia isso sempre que `estado_atual` não fosse "NENHUM",
INCLUINDO quando não havia resposta nenhuma: um tool call programático, que
traz `tool` e `args` completos.

O resultado era o `chamado_editar` pedir o `delta` e o `chamado_criar` seguinte
— completo, explícito — receber "O que queres mudar?" e `ok: true`. Para quem
chama, a escrita correra. Não correra.

Porque `ok: true` é o pior detalhe
=================================
Um erro obriga o modelo a tentar outra vez e diz ao produtor o que aconteceu.
Um `ok: true` que não fez nada faz o modelo avançar, o produtor fica com a peça
antiga, e a causa fica do lado errado do sistema: o teste aponta para o sintoma
(lá em baixo, no `toContainText`), e a causa está aqui.

A regra que fecha a classe
==========================
Uma máquina de estados conversacional retoma-se com uma RESPOSTA. Sem
`entrada` não há resposta, e portanto não há nada a retomar: o intent pedido é
que tem de correr.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase

from app.ia import sandbox
from app.models.ia import IAContextoConversa

User = get_user_model()


class ChamadoNaoSequestradoTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="sequestro", password="x")

    def contexto(self, **kw):
        defaults = {
            "user": self.user,
            "estado_atual": "NENHUM",
            "intent_pendente": "",
            "dados_coletados": {},
        }
        defaults.update(kw)
        obj, _ = IAContextoConversa.objects.update_or_create(
            user=self.user, defaults=defaults
        )
        return obj

    # ------------------------------------------------------------------
    # 1. COLETANDO_DADOS
    # ------------------------------------------------------------------
    def test_um_tool_call_nao_e_engolido_por_uma_pergunta_pendente(self):
        self.contexto(
            estado_atual="COLETANDO_DADOS",
            intent_pendente="chamado_editar",
            dados_coletados={"preset": "chamado-amplia"},
        )

        r = sandbox.executar(
            self.user,
            "chamado_criar",
            {"blocos": [{"tipo": "texto", "texto": "PECA NOVA"}], "confirm": True},
        )

        # A peça tem de existir de verdade. O `ok` sozinho não prova nada: foi
        # exactamente o que mentiu.
        from app.models.palco import ChamadoAmplia

        peca = ChamadoAmplia.objects.filter(user=self.user).first()
        self.assertIsNotNone(peca, "a peça não foi criada")
        textos = [
            str((b.get("config") or {}).get("texto") or "") for b in (peca.corpo or [])
        ]
        self.assertIn(
            "PECA NOVA",
            " ".join(textos),
            f"a peça ficou com o conteúdo antigo: {textos}",
        )
        self.assertNotIn("O que queres mudar", str(r.get("resposta", "")))

    # ------------------------------------------------------------------
    # 2. AGUARDANDO_CONFIRMACAO
    # ------------------------------------------------------------------
    def test_um_tool_call_nao_e_cancelado_por_uma_confirmacao_pendente(self):
        self.contexto(
            estado_atual="AGUARDANDO_CONFIRMACAO",
            intent_pendente="chamado_criar",
            dados_coletados={"blocos": [{"tipo": "texto", "texto": "VELHA"}]},
        )

        r = sandbox.executar(
            self.user,
            "chamado_criar",
            {"blocos": [{"tipo": "texto", "texto": "NOVA"}], "confirm": True},
        )

        self.assertNotIn(
            "Operação cancelada",
            str(r.get("resposta", "")),
            "o cancelamento conversacional não pode atingir uma chamada de tool",
        )
        from app.models.palco import ChamadoAmplia

        peca = ChamadoAmplia.objects.filter(user=self.user).first()
        self.assertIsNotNone(peca)
        self.assertIn(
            "NOVA",
            " ".join(
                str((b.get("config") or {}).get("texto") or "")
                for b in (peca.corpo or [])
            ),
        )

    # ------------------------------------------------------------------
    # 3. O ESTADO PENDENTE SOBREVIVE À CHAMADA PROGRAMÁTICA
    # ------------------------------------------------------------------
    def test_a_pergunta_pendente_nao_se_apaga_so_por_passar_uma_tool(self):
        """A pergunta é do produtor. Respondê-la ou não é dele.

        Uma chamada programática não é resposta, e não deve apagar o que ficou
        pendente: se o produtor responder "sim" a seguir, espera que aquilo
        aconteça.
        """
        self.contexto(
            estado_atual="COLETANDO_DADOS",
            intent_pendente="chamado_editar",
            dados_coletados={"preset": "chamado-amplia"},
        )

        sandbox.executar(
            self.user,
            "chamado_criar",
            {"blocos": [{"tipo": "texto", "texto": "PECA NOVA"}], "confirm": True},
        )

        ctx = IAContextoConversa.objects.get(user=self.user)
        self.assertEqual(
            ctx.intent_pendente,
            "chamado_editar",
            "a pergunta que o produtor ainda pode responder foi deitada fora",
        )

    # ------------------------------------------------------------------
    # 4. A RETOMA HUMANA CONTINUA A FUNCIONAR
    # ------------------------------------------------------------------
    def test_uma_resposta_humana_ainda_retoma_a_pergunta(self):
        """O acima não pode ser um "nunca mais perguntar nada".

        Sem isto, a correcção do sequestro vinha ao preço de a conversa deixar de
        funcionar — e um teste que só prova a meia parte deixa essa troca
        escondida.
        """
        self.contexto(
            estado_atual="COLETANDO_DADOS",
            intent_pendente="chamado_criar",
            dados_coletados={"preset": "chamado-amplia"},
        )

        # O que falta é `blocos`. A resposta humana preenche.
        r = sandbox.executar(
            self.user,
            "chamado_criar",
            {},
            meta={"entrada": '{"tipo":"texto","texto":"DO TEU LADO"}'},
        )

        # Pode pedir confirmação em vez de executar — o que interessa é que já
        # NÃO pediu outro campo, e que o estado avançou.
        self.assertNotIn("Por favor, informe", str(r.get("resposta", "")))

    # ------------------------------------------------------------------
    # 5. O CANCELAMENTO HUMANO CONTINUA A FUNCIONAR
    # ------------------------------------------------------------------
    def test_um_cancelamento_humano_ainda_cancela(self):
        self.contexto(
            estado_atual="AGUARDANDO_CONFIRMACAO",
            intent_pendente="chamado_criar",
            dados_coletados={"blocos": [{"tipo": "texto", "texto": "X"}]},
        )

        r = sandbox.executar(
            self.user, "chamado_criar", {}, meta={"entrada": "cancelar"}
        )
        self.assertIn("cancelada", str(r.get("resposta", "")).lower())

        ctx = IAContextoConversa.objects.get(user=self.user)
        self.assertEqual(ctx.estado_atual, "NENHUM")
        self.assertEqual(ctx.intent_pendente, "")


# ------------------------------------------------------------------
# 6. UMA RECUSA NÃO É O VALOR DO CAMPO
# ------------------------------------------------------------------
#
# Este é o caso irmão do sequestro, pelo lado do VALOR: ali o estado
# engolia uma chamada; aqui o estado engole uma RESPOSTA que não é
# resposta.
#
# MEDIDO 2026-10-04, conversando:
#
#     "cria uma tarefa para adubar o talhao"
#       -> "Como se chama a tarefa? (ex.: aplicar herbicida, vacinar o gado)"
#     "não"
#       -> titulo = "não"
#       -> "Criar esta tarefa no cronograma? (Diga 'sim' ou 'não')"
#
# O sistema propôs ao produtor confirmar uma tarefa chamada "não". A causa
# é o `for` da rama `COLETANDO_DADOS`, que enche o primeiro campo vazio
# com `entrada.strip()` sem perguntar o que a entrada é.
#
# O alcance é largo: `registro.py` mostra **14** intents de escrita com
# `required_fields`, e todos chegam a este ramo. Com
# `cadastrar_funcionario`, "não" virava o nome do funcionário.
#
# Por que cancelar e não repetir a pergunta: é o que a rama de
# `AGUARDANDO_CONFIRMACAO` faz (linha 434), e uma recusa a "que safra?"
# não é um nome de safra.
class RecusaNaoEhValorTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="recusa", password="x")

    def com_pedido_de_titulo(self):
        IAContextoConversa.objects.update_or_create(
            user=self.user,
            defaults={
                "estado_atual": "COLETANDO_DADOS",
                "intent_pendente": "associar_tarefa",
                "dados_coletados": {},
            },
        )

    def test_um_nao_nao_vira_titulo_de_tarefa(self):
        self.com_pedido_de_titulo()

        r = sandbox.executar(self.user, "associar_tarefa", {}, meta={"entrada": "não"})

        self.assertIn("cancelada", str(r.get("resposta", "")).lower())

        ctx = IAContextoConversa.objects.get(user=self.user)
        self.assertEqual(ctx.estado_atual, "NENHUM")
        self.assertEqual(ctx.intent_pendente, "")

    def test_o_cancelamento_apaga_o_que_tinha_sido_coletado(self):
        """Cancelar a meio tem de limpar. Deixar o que ficou hanging
        seria o mesmo sequestro, com outro nome: o próximo pedido
        herdaria `titulo` de uma conversa que o produtor já fechou."""
        self.com_pedido_de_titulo()
        ctx = IAContextoConversa.objects.get(user=self.user)
        ctx.dados_coletados = {"titulo": "meio titulo"}
        ctx.save()

        sandbox.executar(self.user, "associar_tarefa", {}, meta={"entrada": "deixa"})

        ctx = IAContextoConversa.objects.get(user=self.user)
        self.assertEqual(ctx.dados_coletados, {})

    def test_um_titulo_que_contem_nao_no_meio_continua_a_ser_titulo(self):
        """A âncora no início é o que evita o defeito OPOSTO.

        "Medida de nada" é um título. Se a regra pegasse em "nada" ou em
        qualquer ocorrência, estaríamos a perder o dado do produtor —
        que é pior do que gravar "não", porque o produtor não o vê.
        """
        self.com_pedido_de_titulo()

        r = sandbox.executar(
            self.user,
            "associar_tarefa",
            {},
            meta={"entrada": "Medida de nada"},
        )

        # Não pode ter cancelado. E tem de ter avançado para a
        # confirmação — o que prova que o texto foi aceite como título.
        self.assertNotIn("cancelada", str(r.get("resposta", "")).lower())
        self.assertTrue(r.get("needs_confirm"), r)

        ctx = IAContextoConversa.objects.get(user=self.user)
        self.assertEqual(ctx.dados_coletados.get("titulo"), "Medida de nada")

    def test_qualquer_nao_e_recusa(self):
        """ "Pode ser qualquer um" é uma RESPOSTA honesta.

        Se a regra pegasse em "qualquer", estaríamos a cancelar a recolha
        de um campo que o produtor respondeu. É o defeito oposto ao que se
        está a curar, e é por isso que a lista não inclui essa palavra —
        apesar de `wizDispensavel` a tratar como "pular" nos passos de
        lista, que é outro contexto.

        E usa-se `_e_recusa`, não `_RECUSA.match`: a função é que dobra os
        acentos, e "não" escrito como o produtor escreve não casa com
        `nao`. Testar a regex crua dava verde com o defeito em cima.
        """
        for nao_recusa in ("qualquer", "Medida de nada", "Nada a fazer hoje", "Joao"):
            self.assertIsNone(
                sandbox._RECUSA.match(sandbox._texto_sem_acento(nao_recusa).lower()),
                f"{nao_recusa!r} não devia ser recusa",
            )
        for recusa in ("não", "NÃO", "deixa", "sem isso", "Melhor não", "cancelar"):
            self.assertTrue(sandbox._e_recusa(recusa), f"{recusa!r} devia ser recusa")
