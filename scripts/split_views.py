import ast
import os
import shutil

TARGET_DIR = 'app/views_new'
if not os.path.exists(TARGET_DIR):
    os.makedirs(TARGET_DIR)

views_content = open('app/views.py', encoding='utf-8').read()
lines = views_content.split('\n')

GROUPS = {
    'auth': ['login_view', 'logout_view', 'demo_login_view', 'onboarding_view', 'onboarding_save'],
    'cadastro': ['cadastro_animal_view', 'cadastro_apiario_view', 'cadastro_caminhao_view', 'cadastro_estoque_view', 'cadastro_financeiro_view', 'cadastro_funcionario_view', 'cadastro_insumo_view', 'cadastro_maquinario_view', 'cadastro_propriedade_view', 'cadastro_rota_view', 'cadastro_safra_view', 'cadastro_talhao_view'],
    'dashboard': ['index_view', 'dashboard_os_view', 'resumo_gerencial_view', 'pitch_view'],
    'campo': ['setor_campo_view', 'setor_estoque_view', 'agenda_agricola_view', 'previsao_clima_view', 'previsao_safra_view'],
    'servidor': ['servidor_dashboard_view', 'servidor_estoque_view', 'servidor_agenda_view', 'servidor_alertas_view'],
    'operario': ['operario_kanban_view', 'operario_perfil_view', 'operario_registrar_view', 'operario_criar_login', 'operario_remover_login', 'adicionar_funcionario_view'],
    'iot': ['sensores_view', 'dispositivos_view', 'telemetria_view', 'alertas_criticos_view', 'alertas_info_view'],
    'guias': ['guia_vegetal_view', 'guia_animal_view', 'guia_aquatica_view', 'guia_sistemas_view', 'registro_cafe_view', 'registro_cultura_view', '_montar_grupos_animal', '_montar_grupos_aquatica', '_montar_grupos_sistemas', '_montar_grupos_vegetal', '_make_section_view'],
    'config': ['perfil_config_view', 'config_dia_view', 'config_noturno_view', 'config_sistema_view', 'config_page_view', 'erro_report_view'],
    'financeiro': ['simulador_financeiro_view', 'simulador_colheita_view', 'simulador_lucro_view'],
    'logistica': ['logistica_caminhao_view', 'logistica_rotas_view', 'mapa_view'],
    'estoque': ['estoque_geral_view', 'estoque_insumos_view'],
    'equipe': ['equipe_agenda_view', 'equipe_empregados_view'],
    'api': ['get_talhoes_api', 'servidor_config_api'],
    'pecuaria': ['agenda_pecuaria_view', 'racoes_nutricao_view', 'animais_gado_view'],
    'utils': ['is_produtor', 'is_operario', 'is_tipo_usuario', 'produtor_required', 'operario_required', 'kanban_allowed', 'kanban_required', 'perfil_allowed', 'perfil_required', 'get_user_propriedade', 'get_user_funcionario', '_no_store'],
}

COMMON_IMPORTS = """import json
from django import forms
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from app.hierarquia import hierarquia_required
from app.models import *
from .utils import *
"""

tree = ast.parse(views_content)
node_sources = {}
for node in tree.body:
    if isinstance(node, ast.FunctionDef) or isinstance(node, ast.ClassDef):
        name = node.name
        start = node.lineno - 1
        end = node.end_lineno
        if hasattr(node, 'decorator_list') and node.decorator_list:
            start = node.decorator_list[0].lineno - 1
        source = '\n'.join(lines[start:end])
        node_sources[name] = source

all_names = set(node_sources.keys())
mapped_names = set()
for g, names in GROUPS.items():
    mapped_names.update(names)

unmapped = all_names - mapped_names
if unmapped:
    print("WARNING: Unmapped views:", unmapped)
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

print("Done generating views in", TARGET_DIR)
