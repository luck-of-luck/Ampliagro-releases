import ast
import os

TARGET_DIR = 'app/api/views_new'
if not os.path.exists(TARGET_DIR):
    os.makedirs(TARGET_DIR)

views_content = open('app/api/views.py', encoding='utf-8').read()
lines = views_content.split('\n')

GROUPS = {
    'cultures': ['CulturaViewSet', 'ibge_proxy_data', 'ibge_ufs', '_ibge_cached_get', '_load_cultures_config', '_chave_mercado_for_cultura', '_normalize_nome'],
    'production': ['RegistroProducaoViewSet', 'EstagioCulturaViewSet', 'TarefaEstagioViewSet', 'SafraViewSet', 'TalhaoViewSet', 'TalhaoGeometriaViewSet', 'salvar_geometria', 'talhoes_geometria_fc', 'PropriedadeViewSet', 'AplicacaoInsumoViewSet'],
    'financial': ['LancamentoFinanceiroViewSet', 'financeiro_data', 'compras_data', 'vendas_data'],
    'iot': ['EstacaoMeteoViewSet', 'LeituraSensorViewSet', 'sensores_data', 'dispositivos_data', 'weather_integracao', 'weather_forecast', '_get_real_weather', '_gen_fallback_metrics', '_gen_fallback_history', '_owm_icon'],
    'kanban': ['agenda_data', 'agenda_producao_data', 'agenda_analises_data'],
    'user': ['PerfilUsuarioViewSet', 'WidgetUsuarioViewSet', 'DashboardUserState', 'dashboard_state', 'perfil_data', 'dashboard_data', 'notificacoes_data', 'notificacao_ler', 'onboarding_save', 'widget_data', 'widgets_layout_sync', 'widgets_usuario_spa', 'novidades_data', '_build_alertas_e_novidades', 'FuncionarioViewSet', 'OperarioRegistroViewSet'],
    'estoque': ['EstoqueItemViewSet', 'InsumoViewSet', 'estoque_data', 'armazem_data'],
    'maquinario': ['MaquinarioViewSet', 'maquinarios_data', 'caminhoes_data', 'rotas_data'],
    'pecuaria': ['AnimalViewSet', 'ProducaoAnimalViewSet', 'pecuaria_data', 'racoes_data'],
    'apiario': ['ApiarioColmeiaViewSet', 'ProducaoApiarioViewSet', 'apiario_data'],
    'relatorios': ['RelatorioGeradoViewSet', 'RelatorioTemplateViewSet', 'gerar_relatorio', 'relatorio_status', 'export_dashboard_csv', 'export_dashboard_excel'],
    'core': ['visao_geral_data', 'commodities_data', 'previsao_safra_data', 'previsao_clima_data', 'gestao_data', 'ErroReportViewSet'],
    'utils': ['IsOwner', 'SPASimpleSerializer', '_parse_value', '_to_float', '_atomic_with_retry', 'fmt_num'],
}

COMMON_IMPORTS = """import json
import logging
import traceback
import math
import random
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
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from app.models import *
from app.api.serializers import *
from app.hierarquia import *
from .utils import *
"""

tree = ast.parse(views_content)
node_sources = {}
for node in tree.body:
    if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.Assign, ast.AnnAssign)):
        if isinstance(node, ast.Assign):
            if isinstance(node.targets[0], ast.Name):
                name = node.targets[0].id
            else:
                continue
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name):
                name = node.target.id
            else:
                continue
        else:
            name = node.name
        start = node.lineno - 1
        end = node.end_lineno
        if hasattr(node, 'decorator_list') and node.decorator_list:
            start = node.decorator_list[0].lineno - 1
        source = '\n'.join(lines[start:end])
        node_sources[name] = source

# Ensure everything is mapped
all_names = set(node_sources.keys())
mapped_names = set()
for g, names in GROUPS.items():
    mapped_names.update(names)

unmapped = all_names - mapped_names
if unmapped:
    print("WARNING: Unmapped:", unmapped)
    GROUPS['utils'].extend(list(unmapped))

for group, names in GROUPS.items():
    file_path = os.path.join(TARGET_DIR, f"{group}.py")
    with open(file_path, 'w', encoding='utf-8') as f:
        if group != 'utils':
            f.write(COMMON_IMPORTS + '\n\n')
        else:
            f.write(COMMON_IMPORTS.replace('from .utils import *\n', '') + '\n\n')

        for name in names:
            if name in node_sources:
                f.write(node_sources[name] + '\n\n')

# Create __init__.py
init_path = os.path.join(TARGET_DIR, '__init__.py')
with open(init_path, 'w', encoding='utf-8') as f:
    for group, names in GROUPS.items():
        if names and group != 'utils':
            f.write(f"from .{group} import *\n")

print("Done generating api/views in", TARGET_DIR)
