"""API de capacidade de pagamento — a porta que o banco consulta.

## O que isto é

O item nº 1 do plano da análise competitiva (§21.3, §23). A decisão de
arquitectura não é competir com o banco de crédito rural: é **ser a fonte
auditável que o banco consulta**. O `E-agro` do Bradesco decide crédito com
"dados comportamentais e agronômicos" — e esses dados já estão aqui, mas
até agora não havia forma de os entregar.

## Três decisões que esta view toma, e porquê

1. **Não decide crédito.** `decisao_de_credito` é sempre `None`. Um sistema de
   gestão que emite opinião sobre capacidade de pagamento está a fazer algo
   que não pode medir, e a regulação do crédito rural não é dele. Ver
   `capacidade_pagamento.py`.

2. **Read-only.** Nenhum verbo de escrita. Os dados saem; nada entra. Se
   isto escrevesse, o produtor poderia "criar" um histórico de custo que o
   banco depois leria — e aí o histórico deixa de ser auditável.

3. **`403` para propriedade alheia, `404` para inexistente.** Mesma separação
   que o `TenantIsolationMiddleware` faz (a distinção é de propósito: `404`
   para quem errou o número, `403` para quem está a tentar ver a lavoura do
   vizinho).

## O que o consumidor tem de saber

Um factor ausente vem `null` **com `motivo`**. Isto não é defeito: é o valor
mais importante do payload. Um factor que falta e se lê como `0` diz ao banco
"o produtor não tem receita" quando a verdade é "não sabemos" — e essa
distinção é a diferença entre aprovar e negar um crédito.
"""

from __future__ import annotations

from datetime import date

from django.utils.dateparse import parse_date
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from app.hierarquia import propriedades_financeiras
from app.services.capacidade_pagamento import (
    capacidade_pagamento,
    custo_por_hectare_medio,
    historico_safras,
)


class CapacidadePagamentoViewSet(ViewSet):
    """Fatores observáveis de crédito. Read-only, e não decide."""

    permission_classes = [IsAuthenticated]

    def _resolver(self, request, raw):
        """Devolve (propriedade, erro). `404` vs `403` são respostas distintas.

        Um `id` inexistente é `404`: quem o pediu errou o número. Um `id` de
        outra pessoa é `403`: está a tentar ver o registo de alguém. colapsar
        as duas esconde a tentativa dentro de um erro banal — que é o que o
        `TenantIsolationMiddleware` já avisa em docstring
        (`app/middleware.py:28-40`).

        `propriedades_financeiras(user)` já aplica o filtro de posse E a
        permissão de servidor (`hierarquia.py:407-418`), por isso a pertença
        não é uma segunda verificação: é o filtro.
        """
        from app.models import Propriedade

        if not raw:
            return None, Response(
                {"erro": "propriedade_id obrigatório"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            propriedade_id = int(raw)
        except (TypeError, ValueError):
            return None, Response(
                {"erro": "propriedade_id inválido"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            prop = Propriedade.objects.get(id=propriedade_id)
        except Propriedade.DoesNotExist:
            return None, Response(
                {"erro": "propriedade não encontrada"},
                status=status.HTTP_404_NOT_FOUND,
            )

        permitidas = {p.id for p in propriedades_financeiras(request.user)}
        if propriedade_id not in permitidas:
            return None, Response(
                {"erro": "propriedade não pertence ao seu escopo"},
                status=status.HTTP_403_FORBIDDEN,
            )
        return prop, None

    @extend_schema(
        parameters=[
            OpenApiParameter("propriedade_id", int, required=True),
            OpenApiParameter("inicio", str, required=False),
            OpenApiParameter("fim", str, required=False),
        ],
        responses={200: dict},
    )
    @action(detail=False, methods=["get"])
    def fatores(self, request):
        """Fatores de capacidade de pagamento de uma propriedade.

        GET /api/credito/fatores/?propriedade_id=1
        """
        prop, erro = self._resolver(request, request.query_params.get("propriedade_id"))
        if erro:
            return erro

        return Response(
            capacidade_pagamento(
                prop.id,
                data_inicio=parse_date(request.query_params.get("inicio") or ""),
                data_fim=parse_date(request.query_params.get("fim") or ""),
            )
        )

    @extend_schema(
        parameters=[OpenApiParameter("propriedade_id", int, required=True)],
        responses={200: dict},
    )
    @action(detail=False, methods=["get"])
    def historico(self, request):
        """Histórico de custo por hectare, safra a safra.

        GET /api/credito/historico/?propriedade_id=1

        É este endpoint que produz o asset do §21.5: um histórico que nem o
        produtor tem (usa o sistema há uma safra) nem o banco tem (pede três
        anos e recebe uma planilha).
        """
        prop, erro = self._resolver(request, request.query_params.get("propriedade_id"))
        if erro:
            return erro

        return Response(
            {
                "propriedade_id": prop.id,
                "safras": historico_safras(prop.id),
                "custo_por_hectare_medio": custo_por_hectare_medio(prop.id),
                "decisao_de_credito": None,
            }
        )
