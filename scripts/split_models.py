import ast
import os
import shutil

TARGET_DIR = "app/models_new"
if not os.path.exists(TARGET_DIR):
    os.makedirs(TARGET_DIR)

models_content = open("app/models.py", encoding="utf-8").read()
lines = models_content.split("\n")

# Define which models go where
GROUPS = {
    "core": ["Cultura", "Propriedade", "Talhao", "TalhaoGeometria"],
    "safra": ["Safra", "Insumo", "AplicacaoInsumo"],
    "equipe": ["Funcionario"],
    "maquinario": ["Maquinario"],
    "financeiro": ["LancamentoFinanceiro"],
    "pecuaria": ["Animal", "ProducaoAnimal"],
    "estoque": ["EstoqueItem"],
    "apiario": ["ApiarioColmeia", "ProducaoApiario"],
    "producao": ["RegistroProducao", "EstagioCultura", "TarefaEstagio"],
    "iot": [
        "Gateway",
        "Device",
        "TelemetryData",
        "RegraAlertaTelemetria",
        "AlertaTelemetria",
        "ComandoDevice",
        "FonteDadosExterna",
        "EstacaoMeteo",
        "LeituraSensor",
    ],
    "usuario": ["PerfilUsuario", "DashboardUserState", "WidgetUsuario", "Notificacao"],
    "relatorio": ["RelatorioTemplate", "RelatorioGerado"],
    "erro": ["ErroReport"],
}

# Choices / Constants
EXTRA_MAPPING = {
    "core": ["BIOMAS"],
    "safra": ["CATEGORIAS_INSUMO"],
    "equipe": ["CARGOS"],
    "maquinario": ["TIPOS_MAQUINARIO"],
    "financeiro": ["CATEGORIAS_FINANCEIRO"],
    "pecuaria": ["ESPECIES_ANIMAL", "TIPOS_PRODUCAO_ANIMAL"],
    "estoque": ["CATEGORIAS_ESTOQUE"],
    "iot": [
        "ALERT_CONDITIONS",
        "SEVERITY_CHOICES",
        "GATEWAY_STATUS",
        "PUSH_PROTOCOLO",
        "TELEMETRY_METRIC_CHOICES",
        "DEVICE_TIPO",
        "GATEWAY_TIPO",
    ],
    "erro": ["TIPOS_ERRO"],
}

COMMON_IMPORTS = """from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone
from datetime import timedelta
from app.validators import validate_json_safe
"""

tree = ast.parse(models_content)

# Map node name to source code lines
node_sources = {}
for node in tree.body:
    if isinstance(node, ast.ClassDef) or isinstance(node, ast.Assign):
        if isinstance(node, ast.ClassDef):
            name = node.name
        else:
            if isinstance(node.targets[0], ast.Name):
                name = node.targets[0].id
            else:
                continue
        start = node.lineno - 1
        end = node.end_lineno
        # Include decorators if any
        if hasattr(node, "decorator_list") and node.decorator_list:
            start = node.decorator_list[0].lineno - 1

        source = "\n".join(lines[start:end])
        node_sources[name] = source

# Identify remaining classes and assignments
all_names = set(node_sources.keys())
mapped_names = set()
for g, names in GROUPS.items():
    mapped_names.update(names)
for g, names in EXTRA_MAPPING.items():
    mapped_names.update(names)

unmapped = all_names - mapped_names
print("Unmapped:", unmapped)

# Generate files
for group, names in GROUPS.items():
    extra = EXTRA_MAPPING.get(group, [])
    group_names = extra + names

    file_path = os.path.join(TARGET_DIR, f"{group}.py")
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(COMMON_IMPORTS + "\n")
        # We need to preserve some models references.
        # Django allows "app.ModelName" for foreign keys, but if there's direct references we might need imports.
        # Let's just output the source.

        for name in group_names:
            if name in node_sources:
                f.write(node_sources[name] + "\n\n")

# Create __init__.py
init_path = os.path.join(TARGET_DIR, "__init__.py")
with open(init_path, "w", encoding="utf-8") as f:
    for group, names in GROUPS.items():
        if names:
            f.write(f"from .{group} import {', '.join(names)}\n")

print("Done generating models in", TARGET_DIR)
