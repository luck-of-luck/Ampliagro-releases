"""O caminho MCP REAL do `preset_palco` — o que Claude Desktop vai chamar.

POR QUE ISTE FICHEIRO EXISTE
============================
O `capacidades.py:300` diz ao cliente MCP que esta capacidade `confirma: True`.
Isso e' um CAMPO. Ninguem o tinha corrido: ate aqui o `preset_palco` so' tinha
sido testado por `sandbox.executar` directamente, que e' o caminho de dentro.

A distincao nao e' de estilo. `executar_para` e' "a UNICA porta de saida deste
modulo" (docstring do proprio `__init__.py:284`), e entre a porta e o sandbox
ha' coisas que podem recusar:

- `intent_de_tool(nome)` traduz o NOME DA TOOL em nome de intent;
- `ferramentas_aceitas` tem uma allowlist separada do catalogo;
- `via` fica fixo em "mcp", o que muda a trilha de auditoria.

Um intent perfeito que seja recusado na allowlist e' um intent que o produtor
nunca vai usar, e os testes do lado de dentro nao o denunciam.

O QUE AS DUAS CHAMADAS PROVAM
=============================
O `amplia_mcp` e' um caminho de DOIS PASSOS e a suafontera depende disso:

1. a primeira chamada devolve `needs_confirm: true` e NAO executa;
2. a segunda repete o nome com `confirm: true` e executa.

Se a primeira gravasse, a confirmacao do MCP seria decorativa — e e' a
unica barreira antes de mexer no trabalho do produtor.
"""

from django.contrib.auth.models import User
from django.test import TestCase

from app.models.palco import PresetPalco


class PresetPalcoPeloMcpTest(TestCase):
    """O mesmo intent, pela porta que o Claude Desktop usa."""

    def setUp(self):
        self.ana = User.objects.create_user("ana_mcp", "a@x.com", "x1234567")
        self.args = {
            "nome": "Custo",
            "widgets": [{"tipo": "kpi-custo", "titulo": "Custo"}],
        }

    def _chama(self, **extra):
        from app.amplia_mcp import executar_para

        args = dict(self.args, **extra)
        return executar_para(self.ana, "amplia_preset_palco", args, via="stdio")

    # ------------------------------------------------------------- a porta

    def test_o_intent_e_alcancavel_pelo_nome_de_tool_do_mcp(self):
        """O MCP chama por NOME, e o nome tem `amplia_` a frente. Se a
        traducao falhar, `executar_para` recusa — e um intent recusado aqui
        nao aparece em nenhum teste do lado de dentro."""
        from app.amplia_mcp import intent_de_tool

        self.assertEqual(intent_de_tool("amplia_preset_palco"), "preset_palco")

    def test_a_primeira_chamada_pergunta_e_nao_grava(self):
        r = self._chama()
        self.assertTrue(r.get("ok"), r)
        self.assertTrue(
            r.get("needs_confirm"),
            "a primeira chamada gravou sem perguntar: " + str(r),
        )
        self.assertEqual(
            PresetPalco.objects.count(),
            0,
            "o MCP gravou um preset do produtor antes de perguntar",
        )

    def test_a_segunda_chamada_com_confirm_grava(self):
        self._chama()
        r = self._chama(confirm=True)
        self.assertTrue(r.get("ok"), r)
        self.assertFalse(r.get("needs_confirm"), "perguntou outra vez")
        self.assertEqual(PresetPalco.objects.count(), 1)
        self.assertEqual(PresetPalco.objects.get().user_id, self.ana.pk)

    # ------------------------------------------------- a garantia por traz

    def test_a_guarda_de_escrita_tambem_manda_aqui(self):
        """O `pode_escrever` nao e' uma promessa do intent: e' do handler, e o
        handler e' o mesmo por qualquer porta. Este teste existe para que
        abrir uma terceira via de execucao nao a contorne em silencio."""
        r = self._chama(confirm=True)
        self.assertTrue(r.get("ok"), r)
        self.assertEqual(
            PresetPalco.objects.get().slug.startswith("custom-"),
            True,
            "gravou num preset que nao e' do produtor",
        )

    def test_o_caminho_mcp_e_auditado_como_mcp(self):
        """`via` fixo em "mcp" e' o que permite responder depois "o que esta IA
        fez as 14h?". Se `executar_para` deixar de carimbar, a trilha perde a
        origem e a pergunta fica sem resposta."""
        r = self._chama()
        texto = str(r)
        self.assertTrue(r.get("ok"), texto)
        # O carimbo vive na trilha, nao na resposta. O que se mede aqui e' que
        # a chamada passa por `executar_para` e nao por um atalho.
        from app.models import IAExecucao

        self._chama(confirm=True)
        execucoes = list(IAExecucao.objects.filter(user=self.ana))
        self.assertTrue(execucoes, "a chamada pelo MCP nao deixou rasto de auditoria")

    def test_o_produtor_dos_params_nao_manda(self):
        """O corpo pode trazer `user`; o produtor continua a ser o do sandbox."""
        r = self._chama(confirm=True, user=999)
        self.assertTrue(r.get("ok"), r)
        self.assertEqual(PresetPalco.objects.get().user_id, self.ana.pk)
