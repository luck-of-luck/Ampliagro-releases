"""
Registro de modelos críticos no django-auditlog.

Importado em app/apps.py:ready() para ativar o tracking
de alterações nos modelos mais importantes do sistema.
"""

from auditlog.registry import auditlog

from app.models import (
    Animal,
    Device,
    EstoqueItem,
    Funcionario,
    LancamentoFinanceiro,
    Maquinario,
    PerfilUsuario,
    Propriedade,
    RegraAlertaTelemetria,
    TarefaEstagio,
)

_AUDITED_MODELS = [
    LancamentoFinanceiro,
    Funcionario,
    Propriedade,
    Maquinario,
    EstoqueItem,
    Animal,
    TarefaEstagio,
    Device,
    RegraAlertaTelemetria,
    PerfilUsuario,
]

for model in _AUDITED_MODELS:
    auditlog.register(model)
