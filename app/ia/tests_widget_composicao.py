"""A composicao de widgets que um handler pode devolver. Fase 1.

O QUE ESTE TESTE PROVA, E POR QUE EXISTE
=========================================
Antes desta fase, um intent devolvia `resposta` e `dados`, e a IA escrevia texto.
A tela era montada pelo `render_preset`, que e' um intent **separado**: a IA tinha
de o chamar explicitamente, e `IAExecucao` via as duas coisas sem ligacao nenhuma
entre "o que ela perguntou" e "a mesa que apareceu".

`widget_composicao` fecha isso: o handler que respondia a pergunta **anexa** a mesa
que quer mostrar. Nao e' um intent novo, nao e' um segundo caminho, e nao muda o que
o produtor ve quando o campo nao vem.

A COMPOSICAO E' APRESENTACAO, NAO DADO
======================================
Nenhum numero e' inventado aqui. `_normalizar_composicao` nao calcula nada, nao
toca no banco e nao conhece o catalogo: so normaliza o formato. A valida��ao contra
`CATALOGO_IA` e a fronteira de seguranca e continua a ser `palco.validar_estrutura`
(`app/ia/palco.py:198-259`), no caminho que monta a tela.

Esta distincao e' a que faz a Fase 1 ser segura: quem decide **o que** aparece e'
o handler, que ja' tem os dados; quem decide **se** aquele widget existe e' o
catalogo; e o sandbox so garante o formato.
"""

from django.contrib.auth.models import User
from django.test import TestCase


class NormalizarComposicaoTest(TestCase):
    """`_normalizar_composicao` — a fronteira do formato. Sem base de dados."""

    def test_aceita_lista_de_widgets(self):
        from app.ia.sandbox import _normalizar_composicao

        saida = _normalizar_composicao(
            [{"tipo": "kpi-custo", "titulo": "Custo", "config": {"periodo": "30d"}}]
        )
        self.assertEqual(
            saida,
            [{"tipo": "kpi-custo", "titulo": "Custo", "config": {"periodo": "30d"}}],
        )

    def test_aceita_o_forma_de_envelope(self):
        """`{"widgets": [...]}` tambem vale — e' o que `render_preset` devolve."""
        from app.ia.sandbox import _normalizar_composicao

        saida = _normalizar_composicao({"widgets": [{"tipo": "chart-safras"}]})
        self.assertEqual(saida, [{"tipo": "chart-safras"}])

    def test_o_que_nao_e_lista_da_none_e_nao_lista_vazia(self):
        """`None` e' formato errado; `[]` e' uma mesa sem widgets.

        Sao situa��oes opostas na vida do produtor e nao podem ser o mesmo valor.
        """
        from app.ia.sandbox import _normalizar_composicao

        self.assertIsNone(_normalizar_composicao("kpi-custo"))
        self.assertIsNone(_normalizar_composicao(42))
        self.assertIsNone(_normalizar_composicao({"nada": 1}))
        self.assertIsNone(_normalizar_composicao([]))

    def test_corta_o_teto_e_deduplica(self):
        """Oito e' o mesmo teto de `palco.MAX_WIDGETS` (`palco.py:187`).

        Nao e' o mesmo objecto — e devia ser. Um dia `MAX_WIDGETS` subir e este 8
        ficar, tem dois tetos a dizer coisas diferentes. Se este teste um dia
        falhar, a pergunta certa e' "o outro subiu?".
        """
        from app.ia import palco
        from app.ia.sandbox import _TETO_COMPOSICAO, _normalizar_composicao

        self.assertEqual(_TETO_COMPOSICAO, palco.MAX_WIDGETS)

        muitos = [{"tipo": f"t{i}"} for i in range(30)]
        cortados = _normalizar_composicao(muitos)
        self.assertIsNotNone(cortados)
        self.assertEqual(len(cortados), palco.MAX_WIDGETS)

        repetido = [{"tipo": "kpi-custo"}, {"tipo": "kpi-custo"}]
        unicos = _normalizar_composicao(repetido)
        self.assertIsNotNone(unicos)
        self.assertEqual(len(unicos), 1)

    def test_ignora_o_que_nao_se_junta_a_um_widget(self):
        """So `tipo`, `titulo` e `config` passam.

        Uma chave a mais e' superficie. E `config` tem de ser dicionario: uma lista
        ali nao e' configuracao, e quem a consume vai assumeir dicionario.
        """
        from app.ia.sandbox import _normalizar_composicao

        saida = _normalizar_composicao(
            [
                {"tipo": "kpi-custo", "handler": "print(1)", "config": ["a"]},
                "texto solto",
                {"tipo": ""},
            ]
        )
        self.assertEqual(saida, [{"tipo": "kpi-custo"}])

    def test_o_titulo_preso(self):
        """120 caracteres, como o `palco.py:239`."""
        from app.ia.sandbox import _normalizar_composicao

        saida = _normalizar_composicao([{"tipo": "kpi-custo", "titulo": "x" * 400}])
        self.assertEqual(len(saida[0]["titulo"]), 120)


class ComposicaoNoResultadoTest(TestCase):
    """A composicao atravessa o sandbox e sobrevive ao cache."""

    def setUp(self):
        from app.ia import registro

        self.u = User.objects.create_user("comp_user", password="x1234567")
        self.registro = registro

    # O intent de ensaio. Escolhi `resumo_safra` (TTL 300) e nao `vai_chover`
    # porque `vai_chover` tem TTL **0** por desenho (`sandbox.py:58`): os
    # intents de tempo nao podem ser cacheados, porque o copilito decide sobre
    # o estado das tarefas e a chave nao inclui esse estado. Usar um intent de
    # tempo aqui daria um teste que passa sem exercitar o cache.
    ALVO = "resumo_safra"

    def _executa(self, **params):
        from app.ia.sandbox import executar

        return executar(self.u, self.ALVO, params, via="sessao")

    def _com_handler(self, retorno):
        """Troca o handler do intent pelo que o teste precisa."""
        spec = self.registro.REGISTO[self.ALVO]
        self._original = spec["handler"]
        spec["handler"] = lambda user, params, ctx: retorno
        return spec

    def _restaura(self):
        self.registro.REGISTO[self.ALVO]["handler"] = self._original

    def test_a_composicao_sobe_no_resultado(self):
        self._com_handler(
            {
                "ok": True,
                "resposta": "Resumo da safra.",
                "widget_composicao": [
                    {"tipo": "chart-safras", "config": {"periodo": "prox7"}}
                ],
            }
        )
        try:
            out = self._executa()
        finally:
            self._restaura()

        self.assertTrue(out.get("ok"), out)
        self.assertEqual(
            out.get("widget_composicao"),
            [{"tipo": "chart-safras", "config": {"periodo": "prox7"}}],
        )

    def test_sem_composicao_nada_muda(self):
        """A regra que protecte o que ja funciona: sem o campo, o resultado
        tem de ser o de sempre — byte a byte nas chaves que o browser le."""
        self._com_handler({"ok": True, "resposta": "Resumo da safra."})
        try:
            out = self._executa()
        finally:
            self._restaura()

        self.assertTrue(out.get("ok"), out)
        self.assertNotIn("widget_composicao", out)

    def test_a_composicao_sobrevive_ao_cache(self):
        """A 2a chamada vem do cache. A composicao tem de vir com.

        MEDIDO 2026-10-08: sem isto o produtor que repete a pergunta ve a mesa
        desaparecer — e `dados` e `resposta` continuam la, o que faz o defeito
        parecer um bug de tela em vez de um bug de cache.
        """
        from django.core.cache import cache

        self._com_handler(
            {
                "ok": True,
                "resposta": "Resumo da safra.",
                "widget_composicao": [{"tipo": "chart-safras"}],
            }
        )
        cache.clear()
        try:
            primeira = self._executa()
            segunda = self._executa()
        finally:
            self._restaura()
            cache.clear()

        self.assertFalse(primeira.get("cached"), "a 1a chamada foi de cache")
        self.assertTrue(segunda.get("cached"), "a 2a nao foi de cache")
        self.assertEqual(segunda.get("widget_composicao"), [{"tipo": "chart-safras"}])

    def test_a_composicao_nao_inventa_numero(self):
        """O dado continua a vir do handler. A composicao nao tem `valor`.

        Este e' o limite que a `VISAO.md` proibe atravessar: a Fase 1 e' mudanca de
        APRESENTACAO. Um numero que apareca aqui sem vir do handler e' um numero
        inventado, e o teste e' a unica linha que impede isso de virar habito.
        """
        from app.ia.sandbox import _normalizar_composicao

        saida = _normalizar_composicao(
            [{"tipo": "kpi-custo", "valor": 12345, "dados": {"valor": 1}}]
        )
        self.assertEqual(saida, [{"tipo": "kpi-custo"}])
        self.assertNotIn("valor", saida[0])
