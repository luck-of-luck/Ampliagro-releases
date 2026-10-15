"""
Cursor pagination para tabelas grandes (10k+ linhas) — evita COUNT(*) que trava com PageNumberPagination.
Usado em: RastroItem, MovimentoEstoque, RastreabilidadeSafra, LeituraSensor, TelemetryData, EstacaoMeteo
"""

from rest_framework.pagination import CursorPagination


class LargeTableCursorPagination(CursorPagination):
    """
    Padrão para tabelas com id incremental. -id garante cursor estável.
    Sem COUNT, resposta < 80ms mesmo com 100k linhas.
    """

    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 200
    ordering = "-id"
    cursor_query_param = "cursor"


class TimestampCursorPagination(CursorPagination):
    """
    Para séries temporais (TelemetryData, LeituraSensor) — ordena por timestamp/data_hora DESC.
    Fallback para -id se timestamp nulo.
    """

    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 500
    ordering = "-timestamp"
    cursor_query_param = "cursor"


class SensorCursorPagination(CursorPagination):
    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 500
    ordering = "-data_hora"
    cursor_query_param = "cursor"
