import json
import logging
import math
import random
import traceback
from collections import defaultdict
from datetime import date, datetime, timedelta

import requests
from django.conf import settings
from django.contrib.auth import authenticate, login
from django.contrib.auth.models import User
from django.core.cache import cache
from django.db import transaction
from django.db.models import Avg, Count, F, Q, Sum
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_date
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from app.api.serializers import *
from app.hierarquia import *
from app.models import *
from app.services.clima import ClimaService

from .utils import *


def cultura_do_pagamento(data):
    """O id da cultura no corpo do pedido, em qualquer um dos dois nomes.

    MEDIDO 2026-10-06: o `guide.js` envia `cultureId` (camelCase, o nome
    declarado no `RegistroProducaoWriteSerializer`), mas `create()` e
    `update()` liam `data.get("cultureId")` — o nome do CAMPO do modelo. A
    chave nunca era encontrada, `cid` ficava `None` e o registo nascia sem
    cultura: o "adicionar registo rapido" das guias guardava linhas órfãs
    que depois não apareciam em nenhum filtro por cultura.

    Aceita `cultureId` (frontend), `culturaId` (o outro nome ja usado noutros
    clientes) e `cultura` (parametro de query). `None` quando nada foi enviado,
    e nesse caso o registo mantém a cultura que já tinha.
    """
    for chave in ("cultureId", "culturaId", "cultura"):
        valor = data.get(chave)
        if valor not in (None, ""):
            return valor
    return None


class RegistroProducaoViewSet(viewsets.ModelViewSet):
    serializer_class = RegistroProducaoSerializer
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        """Retorna serializer dinâmico baseado na cultura + preferências do usuário."""
        from app.api.serializers import get_registro_producao_serializers

        cultura = self.request.query_params.get("cultura") or "cafe"
        ReadSerializer, WriteSerializer = get_registro_producao_serializers(
            cultura, self.request.user
        )
        if self.action in ("create", "update", "partial_update"):
            return WriteSerializer
        return ReadSerializer

    def get_queryset(self):
        qs = RegistroProducao.objects.filter(user=self.request.user).select_related(
            "cultura"
        )
        cultura = self.request.query_params.get("cultura")
        if cultura:
            if str(cultura).isdigit():
                qs = qs.filter(cultura_id=cultura)
            else:
                qs = qs.filter(cultura_key=cultura)
        # Isolamento por talhão quando informado (evita misturar talhões da mesma cultura)
        talhao = self.request.query_params.get("talhao")
        if talhao:
            qs = qs.filter(fields_json__talhaoId=str(talhao)) | qs.filter(
                fields_json__talhao=str(talhao)
            )
        return qs.distinct()

    def create(self, request, *args, **kwargs):
        data = request.data
        if not data.get("name"):
            return Response(
                {"error": "Nome é obrigatório"}, status=status.HTTP_400_BAD_REQUEST
            )
        cultura_fk = None
        cultura_key = ""
        cid = cultura_do_pagamento(data)
        if cid is not None:
            if str(cid).isdigit():
                try:
                    cultura_fk = Cultura.objects.get(pk=int(cid))
                except Cultura.DoesNotExist:
                    cultura_key = str(cid)
            else:
                cultura_key = str(cid)
        try:
            quantidade = (
                float(data.get("quantity"))
                if data.get("quantity") not in (None, "")
                else None
            )
        except (TypeError, ValueError):
            quantidade = None
        registro = RegistroProducao.objects.create(
            user=request.user,
            cultura=cultura_fk,
            cultura_key=cultura_key,
            grupo=data.get("groupId", "vegetal") or "vegetal",
            nome=data.get("name"),
            status=data.get("status", "ativo") or "ativo",
            location=data.get("location", "") or "",
            data_registro=data.get("date") or data.get("plantingDate") or None,
            quantidade=quantidade,
            unidade=data.get("unit", "") or "",
            observacoes=data.get("observations", "") or "",
            fields_json=data.get("fields") or {},
            treatments=data.get("treatments") or [],
        )
        # Responde com o serializer de LEITURA (o de escrita é write-only e
        # serializaria {} — sem id para o chamador)
        ReadSerializer, _ = get_registro_producao_serializers(
            self.request.query_params.get("cultura") or "cafe", self.request.user
        )
        return Response(
            ReadSerializer(registro, context=self.get_serializer_context()).data,
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        try:
            registro = self.get_object()
        except Exception:
            return Response(
                {"error": "Registro não encontrado"}, status=status.HTTP_404_NOT_FOUND
            )
        data = request.data
        if not data.get("name"):
            return Response(
                {"error": "Nome é obrigatório"}, status=status.HTTP_400_BAD_REQUEST
            )
        cultura_fk = registro.cultura
        cultura_key = registro.cultura_key
        cid = cultura_do_pagamento(data)
        if cid is not None:
            if str(cid).isdigit():
                try:
                    nova = Cultura.objects.get(pk=int(cid))
                    if str(cid) != str(registro.cultura_id):
                        cultura_fk = nova
                except Cultura.DoesNotExist:
                    cultura_fk = None
                    cultura_key = str(cid)
            else:
                cultura_key = str(cid)
        try:
            quantidade = (
                float(data.get("quantity"))
                if data.get("quantity") not in (None, "")
                else None
            )
        except (TypeError, ValueError):
            quantidade = None
        registro.cultura = cultura_fk
        registro.cultura_key = cultura_key
        registro.grupo = data.get("groupId", "vegetal") or "vegetal"
        registro.nome = data.get("name")
        registro.status = data.get("status", "ativo") or "ativo"
        registro.location = data.get("location", "") or ""
        registro.data_registro = data.get("date") or data.get("plantingDate") or None
        registro.quantidade = quantidade
        registro.unidade = data.get("unit", "") or ""
        registro.observacoes = data.get("observations", "") or ""
        registro.fields_json = data.get("fields") or {}
        registro.treatments = data.get("treatments") or []
        registro.save()
        ReadSerializer, _ = get_registro_producao_serializers(
            self.request.query_params.get("cultura") or "cafe", self.request.user
        )
        return Response(
            ReadSerializer(registro, context=self.get_serializer_context()).data
        )


class EstagioCulturaViewSet(viewsets.ModelViewSet):
    filterset_fields = ["registro"]
    search_fields = ["nome"]
    ordering_fields = ["ordem"]
    serializer_class = EstagioCulturaSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        try:
            perfil = user.perfil
            if perfil.tipo_usuario != "produtor":
                prop = perfil.propriedade_vinculada
                if prop:
                    return EstagioCultura.objects.filter(
                        registro__user=prop.user
                    ).select_related("registro", "estagio_pai")
        except Exception:
            pass
        return EstagioCultura.objects.filter(registro__user=user).select_related(
            "registro", "estagio_pai"
        )

    def perform_create(self, serializer):
        registro_id = self.request.data.get("registro")
        user = self.request.user
        # Servidor cria estágio no registro da fazenda vinculada
        try:
            perfil = user.perfil
            if perfil.tipo_usuario != "produtor" and perfil.propriedade_vinculada:
                # servidor: verifica se registro pertence à fazenda dele
                if registro_id:
                    from app.models import RegistroProducao

                    try:
                        registro = RegistroProducao.objects.get(
                            pk=registro_id, user=perfil.propriedade_vinculada.user
                        )
                        serializer.save(registro=registro)
                        return
                    except RegistroProducao.DoesNotExist:
                        raise PermissionDenied("Registro não pertence à sua fazenda")
        except Exception:
            pass
        if registro_id:
            from app.models import RegistroProducao

            try:
                registro = RegistroProducao.objects.get(pk=registro_id, user=user)
                serializer.save(registro=registro)
            except RegistroProducao.DoesNotExist:
                raise PermissionDenied(
                    "Registro não encontrado ou não pertence ao usuário"
                )
        else:
            serializer.save()


class TarefaEstagioViewSet(viewsets.ModelViewSet):
    filterset_fields = ["estagio", "status", "concluida", "propriedade"]
    search_fields = ["descricao"]
    ordering_fields = ["data_limite", "criado_em", "status"]
    serializer_class = TarefaEstagioSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        # Servidor vê tarefas da fazenda vinculada + tarefas atribuídas a ele/cargo
        try:
            perfil = user.perfil
            if perfil.tipo_usuario != "produtor":
                prop = perfil.propriedade_vinculada
                if prop:
                    from django.db.models import Q

                    return (
                        TarefaEstagio.objects.filter(
                            Q(propriedade=prop)
                            | Q(estagio__registro__user=prop.user)
                            | Q(funcionario__user=user)
                            | Q(cargo_alvo__iexact=perfil.area_servidor)
                        )
                        .distinct()
                        .select_related("estagio", "funcionario", "propriedade")
                    )
                # sem propriedade vinculada: só tarefas diretamente atribuídas
                return TarefaEstagio.objects.filter(
                    funcionario__user=user
                ).select_related("estagio", "funcionario", "propriedade")
        except Exception as exc:
            # MEDIDO 2026-10-05: isto era `pass`, e era o que tornava a
            # correccao do `mover` (3db866a) NAO OBSERVAVEL.
            #
            # O `get_object()` chama este `get_queryset` ANTES do `mover`.
            # Com `pass`, um perfil que falha produzia um queryset de
            # fallback, o pedido morria em 403/404 ANTES do `mover`, e o
            # `except` do `mover` — que devolve 503 — nunca era alcancado.
            # A correccao existia e nao se via.
            #
            # E o 403 que saia era uma MENTIRA sobre a causa: dizia "nao
            # tens acesso" quando a verdade era "nao consegui ler o teu
            # perfil". Sao coisas diferentes, e o produtor age diferente:
            # a primeira leva-o a pedir permissao ao dono da fazenda; a
            # segunda leva-o a tentar de novo.
            #
            # E a MESMA classe da falha do painel que dizia "sem dado"
            # sem ter feito fetch, e dos 210 metros de lavoura inventada
            # no fallback do IBGE. Um `403` que esconde um erro de base e'
            # um `0` que esconde uma ausencia de medicao.
            #
            # DEIXA O ERRO SUBIR. Nao se transforma em 403: nao ha forma
            # de devolver 503 daqui dentro de um `get_queryset`, e
            # inventar um `Response` aqui seria pior — o `get_queryset`
            # tem de devolver um QuerySet, e um dia alguem usa-o sem DRF.
            import logging

            logging.getLogger(__name__).error(
                "TarefaEstagioViewSet.get_queryset: nao foi possivel ler "
                "o perfil do utilizador (%s). O pedido NAO vai receber um "
                "403 a dizer 'nao tens acesso' — ia ser mentira sobre a "
                "causa. A correccao e' criar o PerfilUsuario, nunca "
                "afrouxar esta verificacao.",
                type(exc).__name__,
                exc_info=True,
            )
            raise
        return TarefaEstagio.objects.filter(
            estagio__registro__user=user
        ).select_related("estagio", "funcionario", "propriedade")

    def perform_create(self, serializer):
        # Se servidor cria, força propriedade vinculada
        try:
            perfil = self.request.user.perfil
            if perfil.tipo_usuario != "produtor" and perfil.propriedade_vinculada:
                serializer.save(propriedade=perfil.propriedade_vinculada)
                return
        except Exception:
            # NAO e' para o `pass` passar.
            #
            # Este `try` existe para o servidor gravar na propriedade
            # vinculada. Se `request.user.perfil` rebentar, o `pass`
            # deixava `serializer.save()` correr SEM `propriedade` — um
            # registo orfao, que ninguem consegue depois atribuir a ninguem.
            #
            # Nao e' uma fuga de dados: e' um registo que fica preso. Mas
            # "nao consigo ler o teu perfil" e' uma coisa que o servidor
            # tem de dizer, e nao uma coisa que se resolve gravando na
            # mesma.
            import logging

            logging.getLogger(__name__).error(
                "perform_create: nao foi possivel ler o perfil do servidor. "
                "A gravacao SEM propriedade foi recusada. A versao anterior "
                "gravava na mesma e deixava um registo orfao.",
                exc_info=True,
            )
            raise
        serializer.save()

    @action(detail=True, methods=["post"], url_path="mover")
    def mover(self, request, pk=None):
        """Kanban drag&drop: POST {status: 'pendente'|'andamento'|'concluido'}"""
        tarefa = self.get_object()
        novo = request.data.get("status")
        if novo not in ["pendente", "andamento", "concluido"]:
            return Response({"ok": False, "erro": "status inválido"}, status=400)
        # Servidor só pode mover se for da sua fazenda/área
        #
        # Este `try` envolve o bloco INTEIRO de permissões. Antes, um erro
        # aqui caía em `pass` e seguia para `tarefa.save()`, devolvendo
        # 200 {"ok": true} — a verificação de cargo a falhar para o lado
        # permissivo. MEDIDO: e' a mesma classe do fail-open do
        # TenantIsolationMiddleware (ver commit ca92fbf), mas pior: aquele
        # respondia 503 e este respondia 200, e este decide CARGO, nao
        # apenas propriedade.
        #
        # Como e' que falha? `request.user.perfil` não existe para um
        # utilizador sem PerfilUsuario; `perfil.permissoes` pode ser uma
        # string em vez de dict, e `.get` rebenta; a base pode estar sem
        # uma coluna. Nenhum destes e' um "utilizador mal-intencionado" —
        # sao estados normais de um sistema a meio de uma migracao, e davam
        # a qualquer pessoa autenticada o direito de mudar o estado de uma
        # tarefa.
        #
        # Agora: quando nao se consegue VERIFICAR, nao se passa.
        try:
            perfil = request.user.perfil
            if perfil.tipo_usuario != "produtor":
                prop = perfil.propriedade_vinculada
                # 1) verifica fazenda
                if (
                    prop
                    and tarefa.propriedade_id not in [None, prop.id]
                    and tarefa.estagio.registro.user_id != prop.user_id
                ):
                    return Response(
                        {"ok": False, "erro": "Tarefa não é da sua fazenda"}, status=403
                    )
                # 2) verifica cargo/área mesmo dentro da fazenda
                if tarefa.cargo_alvo and tarefa.cargo_alvo.strip() not in ["", "GERAL"]:
                    if (
                        tarefa.cargo_alvo.upper()
                        != (perfil.area_servidor or "").upper()
                    ):
                        # permite se tem paginas_extra liberada
                        extras = (perfil.permissoes or {}).get("paginas_extra", [])
                        if (
                            tarefa.cargo_alvo not in extras
                            and tarefa.cargo_alvo.upper()
                            not in [e.upper() for e in extras]
                        ):
                            # permite se for tarefa diretamente atribuída a ele
                            if (
                                not tarefa.funcionario
                                or tarefa.funcionario.user_id != request.user.id
                            ):
                                return Response(
                                    {
                                        "ok": False,
                                        "erro": f"Sem permissão: tarefa é de {tarefa.cargo_alvo}, sua área é {perfil.area_servidor}",
                                    },
                                    status=403,
                                )
        except Exception as exc:
            # NAO e' para o `pass` passar. Ver o comentario do `try`.
            #
            # 503 e' "volta ja" e diz a verdade: eu nao consegui confirmar
            # que tens permissao. Um 200 aqui seria dizer "tens permissao"
            # sem nunca ter perguntado.
            import logging

            logging.getLogger(__name__).error(
                "TarefaEstagioViewSet.mover: verificacao de permissao "
                "falhou (%s). A request e' RECUSADA com 503. A versao "
                "anterior registava o erro e continuava para `tarefa.save()` "
                "com 200 — a verificacao de CARGO falhava para o lado "
                "permissivo. A correccao e' na base/perfil, nunca "
                "afrouxar isto.",
                type(exc).__name__,
                exc_info=True,
            )
            return Response(
                {
                    "ok": False,
                    "erro": (
                        "Nao foi possivel verificar a sua permissao sobre "
                        "esta tarefa. O pedido foi recusado em vez de "
                        "assumido como autorizado. Tente de novo."
                    ),
                },
                status=503,
            )
        tarefa.status = novo
        # concluida sync via save()
        tarefa.save()
        return Response({"ok": True, "id": tarefa.id, "status": tarefa.status})


class SafraViewSet(viewsets.ModelViewSet):
    serializer_class = SafraSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["cultura", "talhao", "propriedade", "ano"]

    def get_queryset(self):
        return Safra.objects.filter(propriedade__user=self.request.user).select_related(
            "propriedade", "cultura", "talhao"
        )

    def list(self, request, *args, **kwargs):
        """
        Override list to ensure JSON response even on errors.
        Prevents Django DEBUG HTML pages (AssertionError) from being returned.
        """
        try:
            return super().list(request, *args, **kwargs)
        except AssertionError as e:
            import logging

            logging.getLogger(__name__).error(f"SafraViewSet AssertionError: {e}")
            return Response(
                {"error": "Erro interno ao listar safras", "detail": str(e)},
                status=500,
            )
        except Exception as e:
            import logging

            logging.getLogger(__name__).exception("SafraViewSet list error")
            return Response(
                {"error": "Erro ao listar safras", "detail": str(e)},
                status=500,
            )

    def perform_create(self, serializer):
        self._validate_propriedade(serializer)
        serializer.save()

    def _validate_propriedade(self, serializer):
        prop = serializer.validated_data.get("propriedade")
        if prop and prop.user != self.request.user:
            raise PermissionDenied("Esta propriedade não pertence ao seu usuário")


class TalhaoViewSet(viewsets.ModelViewSet):
    filterset_fields = ["propriedade"]
    search_fields = ["nome"]
    ordering_fields = ["nome", "area_hectare"]
    serializer_class = TalhaoSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Talhao.objects.filter(
            propriedade__user=self.request.user
        ).select_related("propriedade", "cultura_atual")

    def perform_create(self, serializer):
        self._validate_propriedade(serializer)
        serializer.save()

    def _validate_propriedade(self, serializer):
        prop = serializer.validated_data.get("propriedade")
        if prop and prop.user != self.request.user:
            raise PermissionDenied("Esta propriedade não pertence ao seu usuário")


class TalhaoGeometriaViewSet(viewsets.ModelViewSet):
    filterset_fields = ["talhao"]
    serializer_class = TalhaoGeometriaSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # PERF: select_related("talhao") — o serializer expoe talhao_nome via
        # CharField(source="talhao.nome"); sem eager eram 58 queries numa página
        # de 50. (O outro método desta MESMA classe já usava select_related.)
        return TalhaoGeometria.objects.filter(
            talhao__propriedade__user=self.request.user
        ).select_related("talhao")


@extend_schema(responses=SPASimpleSerializer)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def salvar_geometria(request):
    talhao_id = request.data.get("talhao_id") or request.data.get("talhao")
    geojson = request.data.get("geojson") or request.data.get("geometry")
    if not talhao_id or not geojson:
        return Response(
            {"ok": False, "erro": "talhao_id e geojson obrigatórios"}, status=400
        )
    from app.models import Talhao, TalhaoGeometria

    try:
        talhao = Talhao.objects.get(id=talhao_id, propriedade__user=request.user)
    except Talhao.DoesNotExist:
        return Response(
            {"ok": False, "erro": "Talhão não encontrado ou sem permissão"}, status=404
        )
    # calcula área (geodésica, WGS84) e centroide via geojson
    try:
        import json as _json

        from app.services.geo import area_ha as _area_ha
        from app.services.geo import centroide as _centroide

        feats = (
            geojson
            if isinstance(geojson, dict) and geojson.get("type") == "Feature"
            else {"type": "Feature", "geometry": geojson, "properties": {}}
        )
        geom = feats.get("geometry") or geojson
        area_calc = None
        centroide = {}
        if geom and geom.get("type") in ("Polygon", "MultiPolygon"):
            # Area geodesica de verdade (WGS84, Chamberlain & Duquette). Antes
            # este bloco devolvia area NULA e o model tem o campo
            # area_calculada_ha desde sempre — nunca preenchido. O comentario
            # antigo prometia shoelace em graus, que erra ~15% em Porto Alegre.
            area_calc = _area_ha(geom)
            lon, lat = _centroide(geom)
            if lat is not None:
                centroide = {"lat": lat, "lon": lon}
        obj, _ = TalhaoGeometria.objects.update_or_create(
            talhao=talhao,
            defaults={
                "geojson": feats,
                "centroide_lat": centroide.get("lat"),
                "centroide_lon": centroide.get("lon"),
                "area_calculada_ha": area_calc,
            },
        )
        # atualiza talhao coordenadas para compatibilidade
        talhao.coordenadas = geojson
        talhao.save(update_fields=["coordenadas"])
        return Response(
            {
                "ok": True,
                "id": obj.id,
                "centroide": centroide,
                "area_ha": area_calc,
            }
        )
    except Exception as e:
        return Response({"ok": False, "erro": str(e)}, status=500)


@extend_schema(responses=SPASimpleSerializer)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def talhoes_geometria_fc(request):
    from app.models import TalhaoGeometria

    propriedade_id = request.GET.get("propriedade_id")
    qs = TalhaoGeometria.objects.filter(
        talhao__propriedade__user=request.user
    ).select_related("talhao")
    if propriedade_id:
        qs = qs.filter(talhao__propriedade_id=propriedade_id)
    features = []
    for g in qs:
        feats = g.geojson or {}
        if feats.get("type") != "Feature":
            feats = {"type": "Feature", "geometry": feats, "properties": {}}
        feats["properties"] = {
            **feats.get("properties", {}),
            "talhao_id": g.talhao_id,
            "talhao_nome": g.talhao.nome,
            "area_ha": str(g.area_calculada_ha or g.talhao.area_hectare),
        }
        features.append(feats)
    return Response({"type": "FeatureCollection", "features": features})


class PropriedadeViewSet(viewsets.ModelViewSet):
    search_fields = ["nome", "cidade"]
    ordering_fields = ["nome", "area_total"]
    serializer_class = PropriedadeSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Propriedade.objects.filter(user=self.request.user).annotate(
            talhao_count=Count("talhoes", distinct=True),
            safra_count=Count("safras", distinct=True),
        )

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=True, methods=["get"], url_path="clima")
    def clima(self, request, pk=None):
        """
        Retorna previsão do clima para a propriedade.
        Usa latitude/longitude se disponíveis, senão geocodifica cidade/UF.
        """
        prop = self.get_object()
        lat, lon = prop.latitude, prop.longitude
        cidade, uf = prop.cidade, prop.uf

        # Se não tem lat/lon, tenta geocodificar via IBGE/Open-Meteo geocoding
        if lat is None or lon is None:
            if cidade and uf:
                lat, lon = self._geocode_cidade_uf(cidade, uf)
                if lat and lon:
                    # Atualiza a propriedade com as coordenadas para cache
                    prop.latitude = lat
                    prop.longitude = lon
                    prop.save(update_fields=["latitude", "longitude"])
            else:
                return Response(
                    {"error": "Propriedade sem coordenadas nem cidade/UF definidos"},
                    status=400,
                )

        # Busca previsão via ClimaService (Open-Meteo)
        clima_data = ClimaService.get_previsao(lat, lon)

        return Response(
            {
                "propriedade": prop.nome,
                "cidade": cidade,
                "uf": uf,
                "latitude": lat,
                "longitude": lon,
                "clima": clima_data,
                "fonte": "open-meteo",
            }
        )

    @action(detail=True, methods=["post"], url_path="geocode")
    def geocode(self, request, pk=None):
        """
        Geocodifica cidade/UF da propriedade e salva latitude/longitude.
        """
        prop = self.get_object()
        cidade = request.data.get("cidade", prop.cidade)
        uf = request.data.get("uf", prop.uf)

        if not cidade or not uf:
            return Response({"error": "Cidade e UF são obrigatórios"}, status=400)

        lat, lon = self._geocode_cidade_uf(cidade, uf)
        if lat is None or lon is None:
            return Response(
                {"error": "Não foi possível geocodificar a cidade/UF"}, status=400
            )

        prop.latitude = lat
        prop.longitude = lon
        prop.cidade = cidade
        prop.uf = uf.upper()
        prop.save(update_fields=["latitude", "longitude", "cidade", "uf"])

        return Response(
            {
                "propriedade": prop.nome,
                "cidade": prop.cidade,
                "uf": prop.uf,
                "latitude": lat,
                "longitude": lon,
            }
        )

    def _geocode_cidade_uf(self, cidade: str, uf: str) -> tuple:
        """
        Geocodifica cidade/UF usando Open-Meteo Geocoding API (gratuito, sem chave).
        """
        import json
        import urllib.parse
        import urllib.request

        try:
            query = urllib.parse.quote(f"{cidade}, {uf}, Brasil")
            url = f"https://geocoding-api.open-meteo.com/v1/search?name={query}&count=1&language=pt&format=json"
            req = urllib.request.Request(url, headers={"User-Agent": "Ampliagro/1.0"})
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode())
                if data.get("results"):
                    result = data["results"][0]
                    return float(result["latitude"]), float(result["longitude"])
        except Exception as e:
            logging.getLogger(__name__).warning(f"Geocoding failed: {e}")
        return None, None


class AplicacaoInsumoViewSet(viewsets.ModelViewSet):
    filterset_fields = ["talhao", "insumo"]
    ordering_fields = ["data"]
    serializer_class = AplicacaoInsumoSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return AplicacaoInsumo.objects.filter(
            insumo__propriedade__user=self.request.user
        ).select_related("insumo", "talhao")
