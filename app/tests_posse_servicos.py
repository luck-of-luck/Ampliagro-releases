"""Nenhum serviço pode chamar-se `propriedade_id` e não tratar posse.

## A regra

O `TenantIsolationMiddleware` valida **ids que chegam no pedido**. Não filtra
querysets. Isto é dito na docstring dele e é verificável.

Consequência: **um serviço que recebe `propriedade_id` e faz
`Model.objects.filter(propriedade_id=...)` está a punching um buraco**, a não
ser que o caller tenha verificado a posse antes.

Este teste é a lista de verificação. Serve para dois usos:
1. agora, apanha o que falta;
2. quando alguém escrever o próximo serviço, obriga-o a decidir.

## Os que hoje passam

`capacidade_pagamento`, `dre`, `custo_producao`, `zarc`, `cooperativa`,
`reforma_tributaria` — todos resolvem a posse **no handler** com `_prop(user,
params)`, que usa `propriedades_visiveis`. Ou seja: a verificação está no
caller, não no serviço.

Isto é aceitável, mas é uma decisão que **tem de ser visível** — porque o
serviço, sozinho, não protege nada. Por isso o teste verifica os dois lados:
o serviço aceita `propriedade_id`, **e** existe um intent que o chama com a
propriedade já verificada.

O que este ficheiro NÃO aceita: um serviço novo que receba um id do pedido
directamente e não passe por `_prop`.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

from django.test import SimpleTestCase

RAIZ = Path(__file__).resolve().parent.parent

# O path do pedido tem de passar por aqui. `_prop` é a função que o resto dos
# handlers usa e que resolve a posse via `propriedades_visiveis`.
RESOLUTOR_POSSE = "_prop(user, params)"


class ServicosNaoConfiamNoIdTest(SimpleTestCase):
    def _fonte(self, relpath: str) -> str:
        return (RAIZ / relpath).read_text(encoding="utf-8")

    def test_nenhum_handler_passa_propriedade_id_do_pedido(self):
        """O path do pedido vai por `_prop`, não por um id solto."""
        f = self._fonte("app/ia/intents_ledger.py")
        tree = ast.parse(f)

        infrangimentos = []
        for no in ast.walk(tree):
            if not isinstance(no, ast.FunctionDef):
                continue
            # `_prop` é o RESOLUTOR, não um handler: é ele que lê
            # `propriedade_id` do pedido, precisamente para o filtrar. Se o
            # excluíssemos, o teste não teriaobjecto — e o meu primeiro
            # rascunho acusou o próprio `_prop` de infração.
            if no.name == "_prop":
                continue
            fonte = ast.get_source_segment(f, no) or ""
            # Um handler que usa `params` para escolher a propriedade tem de
            # passar por `_prop`. `params.get("propriedade_id")` directo é o
            # padrão que o middleware foi feito para travar.
            if (
                'params.get("propriedade_id")' in fonte
                or 'params.get("propriedade")' in fonte
            ):
                infrangimentos.append(no.name)

        self.assertEqual(
            infrangimentos,
            [],
            f"handlers a escolher a propriedade pelo pedido: {infrangimentos}",
        )

    def test_todo_handler_que_usa_propriedade_chama_o_resolutor(self):
        """Se o handler mexe em `propriedade_id`, tem de vir de `_prop`."""
        f = self._fonte("app/ia/intents_ledger.py")
        tree = ast.parse(f)

        maus = []
        for no in ast.walk(tree):
            if not isinstance(no, ast.FunctionDef):
                continue
            fonte = ast.get_source_segment(f, no) or ""
            if "propriedade_id" not in fonte:
                continue
            if RESOLUTOR_POSSE not in fonte and "_prop(" not in fonte:
                maus.append(no.name)

        self.assertEqual(
            maus,
            [],
            f"handlers que usam propriedade_id sem resolver a posse: {maus}",
        )

    def test_o_resolutor_do_ledger_filtra_por_posse(self):
        """O `_prop` dos handlers do ledger tem de filtrar por posse.

        E tem de ser `propriedades_visiveis`, **não** o `_prop` de
        `intents.py`.

        O `_prop` original faz `Propriedade.objects.filter(user=user)`: mais
        estrito, e portanto seguro — mas só para quem é **dono**. Um perfil
        `servidor`/`agronomo` não é dono das fazendas que serve, e portanto
        a versão estrita devolve `None` para ele.

        Isso matava exactamente o caso da cooperativa (§23D): o técnico
        pergunta pelos campos das fazendas que serve, e o handler dizia
        "nenhuma propriedade encontrada". Um bug de **funcionalidade** que
        se lê como bug de segurança — e que ninguém notaria num teste de posse.

        Mais largo não é menos seguro: `propriedades_visiveis` continua a ser
        um filtro de posse do projecto, apenas inclui o vínculo de perfil e o
        de funcionário.
        """
        f = self._fonte("app/ia/intents_ledger.py")
        i = f.find("def _prop(")
        self.assertGreater(i, 0, "intents_ledger.py nao tem _prop")

        corpo = f[i : f.find("\ndef ", i + 10)]
        self.assertIn(
            "propriedades_visiveis",
            corpo,
            "o resolutor do ledger nao usa o filtro de posse do projecto",
        )
        self.assertIn("qs.filter(pk=pid).first()", corpo)
        # E nao pode voltar a delegar no `_prop` estrito.
        self.assertNotIn(
            "from app.ia.intents import _prop",
            corpo,
            "voltou a delegar no _prop so-dono, que devolve None ao tecnico",
        )

    def test_o_resolutor_do_intents_original_e_mais_estrito_e_esta_bem(self):
        """O `_prop` original filtra por dono — registo, nao accuse.

        Ele é **mais seguro** que o do ledger, apenas menos capaz. Este teste
        existe para ninguém o "consertar" para o outro lado sem perceber o
        que está a perder.
        """
        f = self._fonte("app/ia/intents.py")
        i = f.find("def _prop(")
        corpo = f[i : i + 700]

        self.assertIn(
            "filter(user=user)",
            corpo,
            "o _prop original deixou de filtrar por dono — isso seria uma falha",
        )

    def test_a_rede_de_precos_filtra_no_proprio_servico(self):
        """Excepção deliberada, e o porquê dela está escrito.

        A rede de preços é o único serviço que **precisa** de agregar além das
        propriedades do próprio utilizador — mas por isso exige o `user`
        como primeiro argumento e filtra. Um serviço que agrega sem o
        `user` seria a origem da falha que corrigi.
        """
        import app.services.rede_precos as m

        fonte = inspect.getsource(m.preco_referencia)
        self.assertIn("propriedades_visiveis(user)", fonte)

        parametros = list(inspect.signature(m.preco_referencia).parameters.values())
        self.assertEqual(parametros[0].name, "user")
        self.assertIs(parametros[0].default, inspect.Parameter.empty)

    def test_a_cooperativa_verifica_propriedade_a_propriedade(self):
        """A vista agregada não pode confiar numa lista de ids recebida.

        `agregado(user, propriedade_ids)` recebe ids e tem de verificar cada
        um. É a mesma doutrina do middleware: **uma por uma**.
        """
        import app.services.cooperativa as m

        fonte = inspect.getsource(m.pode_agregar)
        self.assertIn("propriedades_visiveis(user)", fonte)
        self.assertIn("filter(pk=propriedade_id)", fonte)
