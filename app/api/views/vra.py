from datetime import datetime

from django.db import transaction
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from app.api.serializers import PrescricaoVRA_Serializer, ZARC_Serializer
from app.hierarquia import propriedades_visiveis
from app.models import ZARC, Cultura, Insumo, PrescricaoVRA, Safra, Talhao
from app.services.vra import VRAISOXMLService

# `verificar_safra` do serviço, importado com o prefixo para não colidir com o
# nome do `@action` acima — que é o mesmo nome por razoes de API.
from app.services.zarc import verificar_safra as verificar_safra_zarc


class PrescricaoVRAViewSet(viewsets.ModelViewSet):
    serializer_class = PrescricaoVRA_Serializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return PrescricaoVRA.objects.filter(
            safra__propriedade__user=self.request.user
        ).select_related("safra", "talhao", "cultura", "insumo")

    def perform_create(self, serializer):
        serializer.save()

    @action(detail=True, methods=["get"])
    def export_iso_xml(self, request, pk=None):
        prescricao = self.get_object()
        xml = VRAISOXMLService.generate_prescricao_xml(prescricao)
        filename = f"vra_{prescricao.id}_{prescricao.cultura.nome}.xml"
        response = Response(xml, content_type="application/xml")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response

    @action(detail=True, methods=["post"])
    def generate_iso_xml(self, request, pk=None):
        prescricao = self.get_object()
        # A atribuicao foi removida (ruff F841): o valor devolvido nao era
        # usado. A CHAMADA mantem-se -- e' ela que grava o ficheiro, e o
        # `len(prescricao.iso_xml)` abaixo le o resultado do mesmo servico.
        VRAISOXMLService.save_xml_file(prescricao)
        return Response({"ok": True, "xml_length": len(prescricao.iso_xml)})

    @action(detail=False, methods=["post"])
    def bulk_create_from_talhao(self, request):
        """Cria prescrições VRA para todos os talhões de uma safra"""
        safra_id = request.data.get("safra_id")
        talhao_ids = request.data.get("talhao_ids", [])
        dose_ha = request.data.get("dose_ha")
        tipo_insumo = request.data.get("tipo_insumo")
        insumo_id = request.data.get("insumo_id")
        unidade = request.data.get("unidade")

        if not all([safra_id, dose_ha, tipo_insumo, unidade]):
            return Response(
                {"erro": "safra_id, dose_ha, tipo_insumo, unidade obrigatórios"},
                status=400,
            )

        from django.db import transaction

        from app.models import Safra, Talhao

        try:
            safra = Safra.objects.get(id=safra_id, propriedade__user=self.request.user)
        except Safra.DoesNotExist:
            return Response({"erro": "Safra não encontrada"}, status=404)

        talhoes = (
            Talhao.objects.filter(id__in=talhao_ids, propriedade=safra.propriedade)
            if talhao_ids
            else safra.talhoes.all()
        )

        prescricoes = []
        with transaction.atomic():
            for talhao in talhoes:
                presc = PrescricaoVRA.objects.create(
                    safra=safra,
                    talhao=talhao,
                    cultura=safra.cultura,
                    tipo_insumo=tipo_insumo,
                    insumo_id=insumo_id,
                    dose_ha=dose_ha,
                    unidade=unidade,
                )
                prescricoes.append(presc)

        return Response(
            {"criadas": len(prescricoes), "ids": [p.id for p in prescricoes]}
        )


class ZARCViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ZARC_Serializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        uf = self.request.query_params.get("uf")
        cultura_id = self.request.query_params.get("cultura_id")
        qs = ZARC.objects.all()
        if uf:
            qs = qs.filter(uf=uf)
        if cultura_id:
            qs = qs.filter(cultura_id=cultura_id)
        return qs.select_related("cultura")

    @action(detail=False, methods=["get"])
    def consultar_zarc(self, request):
        """Consulta ZARC por cultura, UF, município"""
        cultura_id = request.query_params.get("cultura_id")
        uf = request.query_params.get("uf")
        municipio = request.query_params.get("municipio")

        if not cultura_id or not uf:
            return Response({"erro": "cultura_id e uf obrigatórios"}, status=400)

        qs = ZARC.objects.filter(cultura_id=cultura_id, uf=uf)
        if municipio:
            qs = qs.filter(municipio__icontains=municipio)

        zarcs = qs[:10]
        serializer = self.get_serializer(zarcs, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["post"])
    def verificar_janela_plantio(self, request):
        """Verifica se a data atual está na janela ZARC"""
        cultura_id = request.data.get("cultura_id")
        uf = request.data.get("uf")
        municipio = request.data.get("municipio")
        data = request.data.get("data")

        if not all([cultura_id, uf, municipio, data]):
            return Response(
                {"erro": "cultura_id, uf, municipio, data obrigatórios"}, status=400
            )

        zarc = ZARC.objects.filter(
            cultura_id=cultura_id, uf=uf, municipio__icontains=municipio
        ).first()

        if not zarc:
            return Response(
                {
                    "encontrado": False,
                    "mensagem": "ZARC não encontrado para estes parâmetros",
                }
            )

        data_obj = datetime.strptime(data, "%Y-%m-%d").date()
        dentro_janela = zarc.data_inicio_plantio <= data_obj <= zarc.data_fim_plantio

        return Response(
            {
                "encontrado": True,
                "zarc_id": zarc.id,
                "dentro_janela": dentro_janela,
                "janela_inicio": zarc.data_inicio_plantio,
                "janela_fim": zarc.data_fim_plantio,
                "risco_climatico": float(zarc.risco_climatico),
            }
        )

    @action(detail=False, methods=["get"])
    def verificar_safra(self, request):
        """A safra do produtor está dentro da janela ZARC?

        GET /api/zarc/verificar_safra/?safra_id=1

        Difere de `verificar_janela_plantio` numa coisa que importa: aqui a
        geografia vem da PROPRIEDADE do produtor, não de parâmetros. O
        produtor não deveria ter de saber o próprio município para ter direito
        ao aviso de que a lavoura dele está fora da janela.

        A lógica vive em `app/services/zarc.py` — este endpoint não repete
        regra nenhuma. E devolve `dentro_da_janela: null` + `motivo` quando não
        há ZARC para a geografia: **ausência nunca vira `False`**, porque
        `False` significa "fora da janela" e acusaria o produtor de um risco
        que o sistema não tem como avaliar.
        """
        from app.models import Safra

        raw = request.query_params.get("safra_id")
        if not raw:
            return Response(
                {"erro": "safra_id obrigatório"}, status=status.HTTP_400_BAD_REQUEST
            )
        try:
            safra_id = int(raw)
        except (TypeError, ValueError):
            return Response(
                {"erro": "safra_id inválido"}, status=status.HTTP_400_BAD_REQUEST
            )

        safra = Safra.objects.filter(pk=safra_id).select_related("propriedade").first()
        if safra is None:
            return Response(
                {"erro": "safra não encontrada"}, status=status.HTTP_404_NOT_FOUND
            )

        # A posse entra no filtro, sempre: a geografia é o dado mais sensível
        # daqui (diz onde está a fazenda).
        if (
            not propriedades_visiveis(request.user)
            .filter(pk=safra.propriedade_id)
            .exists()
        ):
            return Response(
                {"erro": "safra não pertence ao seu escopo"},
                status=status.HTTP_403_FORBIDDEN,
            )

        return Response(verificar_safra_zarc(safra_id))
