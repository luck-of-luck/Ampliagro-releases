"""A tela do orcado x realizado - o endpoint.

`app/services/custo_talhao.py` faz a conta. Este modulo expoe-a. Existia o
servico e nao existia caminho HTTP para ele: o produtor no conseguia VER a conta
que o sistema fazia. Um motor sem porta e' uma feature que ninguem usa.

Duas decisoes que nao sao obvias:

**Leitura sem escrita.** E' `GET`. O quadro orcado x realizado nao grava nada -
ler uma conta nao pode criar um lancamento, e um `POST` que recalcula invites
alguem a escrever sem querer. O que muda o numero e' o produtor a lancare
despesa, no cadastro financeiro, que e' onde ele ja lancava.

**O `propriedade_id` e' opcional e validado.** Sem ele, a conta e' da primeira
propriedade do produtor. Com ele, tem de ser DELA - `propriedade__user=request.user`
no filtro. Passar o id de outra propriedade nao da 404 nem 403: da a lista
vazia desse produtor, que e' a resposta honesta para "isto nao e' teu" sem
confirmar que existe. (Ver `tests/test_custo_por_talhao.py`, classe
`IsolamentoPorPropriedade`.)

O payload vai em `as_dict()`, que ja converte `Decimal` para `float` na
fronteira - o `json.dumps` nao conhece `Decimal`, e medido em 2026-10-05 foi
exatamente isso que rebentou `Lote3IntentsTest::test_109_lucro_talhao`.
"""

from __future__ import annotations

from decimal import Decimal

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from app.models import Propriedade
from app.services.custo_talhao import custo_por_talhao


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def custo_por_talhao_data(request):
    """Orcado x realizado por talhao.

    Query params (ambos opcionais):
      `propriedade_id` - se omitido, usa a primeira propriedade do produtor.
      `ano`            - se omitido, agrega todos os anos.

    Devolve `custo_talhao.as_dict()` mais um bloco `pendencias` que diz o que
    falta preencher. Esse bloco existe porque o `as_dict()` honesto usa `None`
    para "sem orcado", e `None` na tela e' uma coluna vazia que nao diz ao
    produtor que ha trabalho por fazer. `None` e `0` sao coisas diferentes e
    as duas precisam de ser vistas.
    """
    usuario = request.user

    propriedade = None
    prop_id = request.GET.get("propriedade_id")
    if prop_id:
        try:
            prop_id = int(prop_id)
        except (TypeError, ValueError):
            return Response(
                {"erro": "propriedade_id tem de ser um numero"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        propriedade = Propriedade.objects.filter(id=prop_id, user=usuario).first()
        if propriedade is None:
            # Nao existe OU nao e' dele. Mesma resposta nos dois casos: nao
            # confirmamos a existencia de um recurso de outro produtor.
            return Response(
                {"erro": "propriedade nao encontrada"},
                status=status.HTTP_404_NOT_FOUND,
            )

    ano = None
    ano_raw = request.GET.get("ano")
    if ano_raw:
        try:
            ano = int(ano_raw)
        except (TypeError, ValueError):
            return Response(
                {"erro": "ano tem de ser um numero"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    resultado = custo_por_talhao(usuario, propriedade=propriedade, ano=ano)

    payload = resultado.as_dict()
    payload["pendencias"] = {
        "nao_alocado_registros": resultado.nao_alocado_registros,
        "nao_alocado_despesa": float(resultado.nao_alocado_despesa),
        "nao_alocado_receita": float(resultado.nao_alocado_receita),
        "talhoes_sem_lancamento": resultado.talhoes_sem_lancamento,
        "talhoes_sem_orcado": [l.talhao for l in resultado.linhas if l.orcado is None],
        "comprometido_total": float(
            sum(
                (l.comprometido_despesa for l in resultado.linhas),
                Decimal("0"),
            )
        ),
        "tem_dados": resultado.tem_dados,
    }
    # `tem_dados` tambem no topo: e' a primeira coisa que a tela precisa de
    # saber, antes de decidir se desenha uma tabela vazia ou um aviso.
    payload["tem_dados"] = resultado.tem_dados

    return Response(payload)
