"""Viewsets mecânicos para endpoints que o JS chama mas não tinham rota.

Padrão: ModelViewSet + IsAuthenticated + escopo por usuário (lookup reverso
até propriedade__user) + validação pós-save (apaga + 403 se fugir do escopo).
Escopo cobre leitura E escrita (perform_create verifica o objeto salvo).
"""

from django.core.exceptions import PermissionDenied
from rest_framework import serializers, viewsets
from rest_framework.permissions import IsAuthenticated

from app.models import (
    AlertaTelemetria,
    AnimalIndividual,
    AtividadePlanejada,
    EventoSanitario,
    Inventario,
    InventarioItem,
    MovimentacaoEstoque,
    OrdemCompra,
    Pesagem,
    Piquete,
    PlanoSafra,
    ProtocoloSanitario,
    RastreabilidadeSafra,
    RastroItem,
    ReceituarioAgronomico,
    RegraAlertaTelemetria,
    TelemetryData,
)


def _mk_serializer(model):
    return type(
        f"{model.__name__}AutoSerializer",
        (serializers.ModelSerializer,),
        {
            "Meta": type("Meta", (), {"model": model, "fields": "__all__"}),
        },
    )


def make_scoped_viewset(model, scope_lookup, filters=(), search=()):
    ser = _mk_serializer(model)

    class AutoViewSet(viewsets.ModelViewSet):
        serializer_class = ser
        permission_classes = [IsAuthenticated]
        filterset_fields = list(filters)
        search_fields = list(search)

        def _exigir_ativo(self):
            """Revogação, dentro da view. DEFENCE IN DEPTH.

            MEDIDO 2026-10-04 (agente 4). O `ServidorRevogadoMiddleware`
            resolve o HTTP, mas cada viewset declara as suas próprias
            `permission_classes`, o que sobrepõe qualquer default do DRF — e
            uma tarefa do Celery não passa por HTTP nenhum. Ver
            `app/services/revogacao.py`.
            """
            from app.services.revogacao import exigir_servidor_ativo

            exigir_servidor_ativo(self.request.user)

        def get_queryset(self):
            self._exigir_ativo()
            return model.objects.filter(**{scope_lookup: self.request.user}).order_by(
                "-id"
            )

        def perform_create(self, serializer):
            self._exigir_ativo()
            obj = serializer.save()
            ok = (
                model.objects.filter(pk=obj.pk)
                .filter(**{scope_lookup: self.request.user})
                .exists()
            )
            if not ok:
                obj.delete()
                raise PermissionDenied("Fora do escopo do seu usuário")

        def perform_update(self, serializer):
            self._exigir_ativo()
            serializer.save()

        def perform_destroy(self, instance):
            self._exigir_ativo()
            instance.delete()

    AutoViewSet.__name__ = f"{model.__name__}AutoViewSet"
    return AutoViewSet


AlertaTelemetriaViewSet = make_scoped_viewset(
    AlertaTelemetria, "propriedade__user", filters=("resolvido", "severidade")
)
AtividadePlanejadaViewSet = make_scoped_viewset(
    AtividadePlanejada,
    "plano__safra__propriedade__user",
    filters=("concluida",),
    search=("nome",),
)
AnimalIndividualViewSet = make_scoped_viewset(
    AnimalIndividual,
    "propriedade__user",
    filters=("especie", "status"),
    search=("brinco", "nome"),
)
EventoSanitarioViewSet = make_scoped_viewset(
    EventoSanitario, "animal__propriedade__user", filters=("tipo",)
)
InventarioViewSet = make_scoped_viewset(Inventario, "propriedade__user")
InventarioItemViewSet = make_scoped_viewset(
    InventarioItem, "inventario__propriedade__user"
)
MovimentacaoEstoqueViewSet = make_scoped_viewset(
    MovimentacaoEstoque, "item__propriedade__user", filters=("tipo",)
)
OrdemCompraViewSet = make_scoped_viewset(
    OrdemCompra, "propriedade__user", filters=("status",)
)
PesagemViewSet = make_scoped_viewset(Pesagem, "animal__propriedade__user")
PiqueteViewSet = make_scoped_viewset(
    Piquete, "propriedade__user", filters=("status",), search=("nome",)
)
PlanoSafraViewSet = make_scoped_viewset(PlanoSafra, "safra__propriedade__user")
ProtocoloSanitarioViewSet = make_scoped_viewset(ProtocoloSanitario, "propriedade__user")
RastreabilidadeSafraViewSet2 = make_scoped_viewset(
    RastreabilidadeSafra, "safra__propriedade__user"
)
RastroItemViewSet2 = make_scoped_viewset(RastroItem, "propriedade__user")
ReceituarioViewSet = make_scoped_viewset(
    ReceituarioAgronomico, "safra__propriedade__user"
)
RegraAlertaViewSet2 = make_scoped_viewset(RegraAlertaTelemetria, "propriedade__user")
TelemetryDataViewSet = make_scoped_viewset(
    TelemetryData, "propriedade__user", filters=("metric", "qualidade")
)

__all__ = [
    "AlertaTelemetriaViewSet",
    "AnimalIndividualViewSet",
    "AtividadePlanejadaViewSet",
    "EventoSanitarioViewSet",
    "InventarioViewSet",
    "InventarioItemViewSet",
    "MovimentacaoEstoqueViewSet",
    "OrdemCompraViewSet",
    "PesagemViewSet",
    "PiqueteViewSet",
    "PlanoSafraViewSet",
    "ProtocoloSanitarioViewSet",
    "RastreabilidadeSafraViewSet2",
    "RastroItemViewSet2",
    "ReceituarioViewSet",
    "RegraAlertaViewSet2",
    "TelemetryDataViewSet",
]
