import csv
from datetime import date, timedelta

from django.db.models import DecimalField, ExpressionWrapper, F, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.http import HttpResponse
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from app.api.pagination import LargeTableCursorPagination
from app.api.serializers import (
    MovimentoEstoqueSerializer,
    RastreabilidadeSafraSerializer,
    RastroItemSerializer,
)
from app.models import Insumo, MovimentoEstoque, RastreabilidadeSafra, RastroItem


class RastroItemViewSet(viewsets.ModelViewSet):
    serializer_class = RastroItemSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = LargeTableCursorPagination

    @staticmethod
    def with_saldo(qs):
        """
        Anexa o saldo como campo annotated (N+1 -> 0).

        RastroItem.saldo e um @property que roda 2 aggregates por linha
        (movimentos SAIDA + AJUSTE). Em listagens isso virava 2 queries por
        item — 107 queries numa pagina de 50, e ~10.000 em alertas_ruptura.
        Aqui o JOIN e feito uma unica vez na query da lista.
        """
        return qs.annotate(
            saldo_calculado=Coalesce(
                ExpressionWrapper(
                    F("quantidade_recebida")
                    - Coalesce(
                        Sum(
                            "movimentos__quantidade", filter=Q(movimentos__tipo="SAIDA")
                        ),
                        Value(0),
                        output_field=DecimalField(max_digits=14, decimal_places=3),
                    )
                    + Coalesce(
                        Sum(
                            "movimentos__quantidade",
                            filter=Q(movimentos__tipo="AJUSTE"),
                        ),
                        Value(0),
                        output_field=DecimalField(max_digits=14, decimal_places=3),
                    ),
                    output_field=DecimalField(max_digits=14, decimal_places=3),
                ),
                Value(0),
                output_field=DecimalField(max_digits=14, decimal_places=3),
            )
        )

    def get_queryset(self):
        qs = RastroItem.objects.filter(
            propriedade__user=self.request.user
        ).select_related("insumo", "propriedade")
        vencido = self.request.query_params.get("vencido")
        if vencido == "true":
            qs = qs.filter(data_validade__lt=date.today())
        elif vencido == "false":
            qs = qs.filter(
                Q(data_validade__gte=date.today()) | Q(data_validade__isnull=True)
            )
        insumo = self.request.query_params.get("insumo")
        if insumo:
            qs = qs.filter(insumo_id=insumo)
        return self.with_saldo(qs)

    def perform_create(self, serializer):
        prop = serializer.validated_data.get("propriedade")
        if prop and prop.user != self.request.user:
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied("Propriedade não pertence ao usuário.")
        serializer.save()

    @action(detail=False, methods=["get"])
    def alertas_validade(self, request):
        """Itens que vencem em ≤ 30 dias ou já vencidos."""
        hoje = date.today()
        limite = hoje + timedelta(days=30)
        qs = (
            self.get_queryset()
            .filter(data_validade__isnull=False, data_validade__lte=limite)
            .order_by("data_validade")
        )
        # Teto de seguranca: antes sem paginacao, cada linha custava 2 queries do
        # .saldo -> 5.000 lotes vencendo significavam 10.001 queries num request.
        qs = qs[:500]
        return Response(RastroItemSerializer(qs, many=True).data)

    @action(detail=True, methods=["get"])
    def cadeia(self, request, pk=None):
        """Cadeia de rastreabilidade: RastroItem → movimentos → aplicações em safras."""
        obj = self.get_object()
        movimentos = obj.movimentos.select_related("talhao", "funcionario").order_by(
            "data_movimento"
        )
        rastros_safra = RastreabilidadeSafra.objects.filter(
            rastro_item=obj
        ).select_related("safra", "talhao", "insumo", "aplicacao")
        return Response(
            {
                "rastro": RastroItemSerializer(obj).data,
                "movimentos": MovimentoEstoqueSerializer(movimentos, many=True).data,
                "aplicacoes_safra": RastreabilidadeSafraSerializer(
                    rastros_safra, many=True
                ).data,
            }
        )

    @action(detail=False, methods=["get"])
    def sugestao_uso(self, request):
        """
        Sugestão de qual lote usar primeiro (FIFO ou FEFO).
        GET /api/rastros/sugestao_uso/?insumo=X&metodo=fefo|fifo
        FEFO (padrão): menor data_validade primeiro (nulls por último), evita vencimento.
        FIFO: menor data_recebimento primeiro, evita obsolescência.
        Retorna lotes com saldo > 0 ordenados pela estratégia escolhida.
        """
        insumo_id = request.query_params.get("insumo")
        metodo = request.query_params.get("metodo", "fefo").lower()
        if not insumo_id:
            return Response({"detail": "Parâmetro insumo é obrigatório."}, status=400)
        if metodo not in ("fefo", "fifo"):
            return Response({"detail": "metodo deve ser fefo ou fifo."}, status=400)

        qs = self.get_queryset().filter(insumo_id=insumo_id)
        # saldo>0 agora vem do annotate (0 queries extras por lote)
        lotes_com_saldo = [r for r in qs if r.saldo_calculado > 0]

        if metodo == "fefo":
            # FEFO: data_validade ASC (None = sem validade → por último), depois data_recebimento
            lotes_com_saldo.sort(
                key=lambda r: (
                    r.data_validade is None,
                    r.data_validade or date.max,
                    r.data_recebimento,
                )
            )
        else:
            # FIFO: data_recebimento ASC
            lotes_com_saldo.sort(key=lambda r: r.data_recebimento)

        return Response(
            {
                "metodo": metodo,
                "insumo": int(insumo_id),
                "sugestao": RastroItemSerializer(lotes_com_saldo, many=True).data,
                "total_lotes": len(lotes_com_saldo),
            }
        )

    @action(detail=False, methods=["get"])
    def alertas_ruptura(self, request):
        """
        Insumos abaixo do estoque mínimo.
        GET /api/rastros/alertas_ruptura/
        Compara saldo total de RastroItems por Insumo vs Insumo.estoque_minimo.
        Só reporta insumos que têm estoque_minimo definido.
        """
        # PERF: antes este endpoint fazia 1 query por insumo + 2 queries por lote
        # (a property .saldo) + mais 2 por lote ao serializar -> 427 queries com
        # 20 insumos/200 lotes, e ~10.000 em producao.
        # Agora: 1 aggregate para os saldos + 1 query para todos os lotes.
        # `list(insumos)` materializa a queryset de uma vez — sem isso o
        # select_related("propriedade") era re-consultado a cada iteração.
        insumos = list(
            Insumo.objects.filter(
                propriedade__user=request.user,
                estoque_minimo__isnull=False,
            ).select_related("propriedade")
        )
        insumo_ids = [i.id for i in insumos]

        saldos = {}
        if insumo_ids:
            # MEDIDO 2026-10-05, por EXECUCAO. Isto era um
            # `.values("insumo_id").annotate(...)` com
            # `Sum("quantidade_recebida")` E `Sum("movimentos__quantidade")`
            # na MESMA expressao. Dois defeitos:
            #
            # 1. Somar a relacao `movimentos` JUNTA a tabela, e cada linha de
            #    movimento duplica a linha do RastroItem — logo
            #    `quantidade_recebida` sai multiplicada pelo numero de
            #    movimentos. O erro cresce com o uso.
            #
            # 2. `Sum(..., filter=Q(movimentos__tipo="AJUSTE"))` devolve NULL
            #    quando nao ha ajustes, e ajustes sao raros. Em SQL
            #    `100 - 30 + NULL` e' NULL, e o `Coalesce(..., 0` devolvia
            #    **ZERO**. Foi isto que escondeu (1): o sintoma nao era um
            #    numero grande, era sempre 0.
            #
            # MEDIDO: 100 recebidas, 3 saidas de 10 -> formula antiga dava 0,
            # a de agora da 70. Com saldo 0, `0 < estoque_minimo` era verdade
            # quase sempre e o endpoint reportava TODOS os insumos como
            # ruptura, com o deficit inteiro. O alerta que existe para avisar
            # antes da compra disparava sempre, e por isso deixou de se ler.
            #
            # A correccao e' NAO juntar: duas queries. `recebido` agrega o
            # RastroItem sozinho, e os movimentos agrupam por (insumo, tipo).
            # A relacao MovimentoEstoque -> RastroItem e' many-to-one, portanto
            # essa juncao nao duplica linha nenhuma.
            #
            # A semantica fica a mesma de antes: subtrai SAIDA, soma AJUSTE.
            # ENTRADA e TRANSF continuam de fora — mudar isso e' decisao de
            # negocio, e nao se muda regra de negocio a consertar aritmetica.
            recebido = dict(
                RastroItem.objects.filter(
                    propriedade__user=request.user, insumo_id__in=insumo_ids
                )
                .values("insumo_id")
                .annotate(s=Sum("quantidade_recebida"))
                .values_list("insumo_id", "s")
            )

            por_insumo: dict = {}
            for _insumo_id, _tipo, _soma in (
                MovimentoEstoque.objects.filter(
                    tipo__in=("SAIDA", "AJUSTE"),
                    rastro_item__propriedade__user=request.user,
                    rastro_item__insumo_id__in=insumo_ids,
                )
                .values("rastro_item__insumo_id", "tipo")
                .annotate(s=Sum("quantidade"))
                .values_list("rastro_item__insumo_id", "tipo", "s")
            ):
                por_insumo.setdefault(_insumo_id, {})[_tipo] = _soma or 0

            saldos = {
                _insumo_id: _qtd
                - por_insumo.get(_insumo_id, {}).get("SAIDA", 0)
                + por_insumo.get(_insumo_id, {}).get("AJUSTE", 0)
                for _insumo_id, _qtd in recebido.items()
            }

        # Lotes por insumo em UMA query, com select_related para o serializer
        # nao disparar 1 query por lote em insumo/propriedade.
        lotes_por_insumo = {}
        if insumo_ids:
            for lote in self.with_saldo(
                RastroItem.objects.filter(
                    propriedade__user=request.user, insumo_id__in=insumo_ids
                ).select_related("insumo", "propriedade")
            ):
                lotes_por_insumo.setdefault(lote.insumo_id, []).append(lote)

        alertas = []
        for ins in insumos:
            saldo_total = float(saldos.get(ins.id, 0) or 0)
            if saldo_total < float(ins.estoque_minimo):
                lotes = lotes_por_insumo.get(ins.id, [])
                lotes_data = RastroItemSerializer(lotes, many=True).data
                alertas.append(
                    {
                        "insumo": {
                            "id": ins.id,
                            "nome": ins.nome,
                            "categoria": ins.categoria,
                            "unidade": ins.unidade,
                        },
                        "estoque_minimo": float(ins.estoque_minimo),
                        "saldo_total": round(saldo_total, 2),
                        "deficit": round(float(ins.estoque_minimo) - saldo_total, 2),
                        "total_lotes": len(lotes_data),
                        "lotes": lotes_data,
                    }
                )

        # Ordenar por maior deficit relativo primeiro
        alertas.sort(
            key=lambda a: a["deficit"] / max(a["estoque_minimo"], 1), reverse=True
        )
        return Response({"alertas": alertas, "total": len(alertas)})

    @action(detail=False, methods=["get"])
    def export_globalgap(self, request):
        """
        Exporta rastreabilidade em CSV formatado para auditoria GlobalG.A.P.
        GET /api/rastros/export_globalgap/?safra=X
        Colunas: lote, insumo, fornecedor, NF, datas, quantidades, talhão, safra, aplicação.
        """
        safra_id = request.query_params.get("safra")
        rastros = self.get_queryset().select_related("insumo", "propriedade")
        if safra_id:
            rastro_ids = RastreabilidadeSafra.objects.filter(
                safra_id=safra_id, rastro_item__isnull=False
            ).values_list("rastro_item_id", flat=True)
            rastros = rastros.filter(id__in=rastro_ids)

        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = (
            'attachment; filename="rastreabilidade_globalgap.csv"'
        )
        response.write("\ufeff")
        writer = csv.writer(response, delimiter=";")
        writer.writerow(
            [
                "Lote",
                "Insumo",
                "Categoria Insumo",
                "Fornecedor",
                "NF Entrada",
                "Data Recebimento",
                "Data Validade",
                "Qtd Recebida",
                "Saldo",
                "Unidade",
                "QR Hash",
                "Talhao",
                "Safra",
                "Data Aplicacao",
                "Operacao",
                "Qtd Aplicada",
            ]
        )
        for r in rastros:
            aplicacoes = RastreabilidadeSafra.objects.filter(
                rastro_item=r
            ).select_related("talhao", "safra")
            if not aplicacoes.exists():
                writer.writerow(
                    [
                        r.numero_lote,
                        r.insumo.nome,
                        r.insumo.categoria,
                        r.fornecedor,
                        r.nf_entrada,
                        r.data_recebimento,
                        r.data_validade or "",
                        r.quantidade_recebida,
                        r.saldo,
                        r.unidade,
                        r.qr_code_hash,
                        "",
                        "",
                        "",
                        "",
                        "",
                    ]
                )
            else:
                for ap in aplicacoes:
                    talhao_nome = ""
                    if ap.talhao:
                        talhao_nome = ap.talhao.nome
                    elif ap.talhao_efetivo:
                        talhao_nome = ap.talhao_efetivo.nome
                    writer.writerow(
                        [
                            r.numero_lote,
                            r.insumo.nome,
                            r.insumo.categoria,
                            r.fornecedor,
                            r.nf_entrada,
                            r.data_recebimento,
                            r.data_validade or "",
                            r.quantidade_recebida,
                            r.saldo,
                            r.unidade,
                            r.qr_code_hash,
                            talhao_nome,
                            str(ap.safra),
                            ap.data_aplicacao,
                            ap.operacao,
                            ap.quantidade_aplicada,
                        ]
                    )
        return response


class MovimentoEstoqueViewSet(viewsets.ModelViewSet):
    serializer_class = MovimentoEstoqueSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = LargeTableCursorPagination

    def get_queryset(self):
        return MovimentoEstoque.objects.filter(
            rastro_item__propriedade__user=self.request.user
        ).select_related("rastro_item", "talhao", "funcionario")


class RastreabilidadeSafraViewSet(viewsets.ModelViewSet):
    serializer_class = RastreabilidadeSafraSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = LargeTableCursorPagination

    def get_queryset(self):
        return RastreabilidadeSafra.objects.filter(
            safra__propriedade__user=self.request.user
        ).select_related("safra", "insumo", "talhao", "rastro_item", "aplicacao")
