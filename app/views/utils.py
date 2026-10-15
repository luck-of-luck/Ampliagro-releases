import json

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


def is_produtor(user):
    """Verifica se o usuário é um Produtor (acesso total)"""
    if not user.is_authenticated:
        return False
    try:
        return user.perfil.tipo_usuario == "produtor"
    except PerfilUsuario.DoesNotExist:
        return False


def is_operario(user):
    """Verifica se o usuário é um Operário ou subtipo (acesso restrito)"""
    if not user.is_authenticated:
        return False
    try:
        return user.perfil.tipo_usuario in [
            "operario",
            "agronomo",
            "mecanico",
            "administrativo",
        ]
    except PerfilUsuario.DoesNotExist:
        return False


def is_tipo_usuario(*tipos_permitidos):
    """Decorator para restringir acesso a tipos específicos de usuário"""

    def check(user):
        if not user.is_authenticated:
            return False
        try:
            return user.perfil.tipo_usuario in tipos_permitidos
        except PerfilUsuario.DoesNotExist:
            return False

    return user_passes_test(check, login_url="login")


def produtor_required(view_func):
    """Decorator que exige que o usuário seja Produtor"""
    return is_tipo_usuario("produtor")(view_func)


def operario_required(view_func):
    """Decorator que exige que o usuário seja Operário ou subtipo"""
    return is_tipo_usuario("operario", "agronomo", "mecanico", "administrativo")(
        view_func
    )


def kanban_allowed(user):
    """Verifica se o usuário pode acessar o Kanban (Produtor + Servidores + Operários)"""
    if not user.is_authenticated:
        return False
    try:
        # REVOGACAO. `ativo_servidor` tem default=True, portanto isto nao afecta
        # quem nao foi desligado explicitamente: so quando o produtor o desliga
        # em `lgpd.py`. Sem esta linha, um servidor desactivado que tivesse
        # sessao iniciada continuava a entrar no kanban — que mostra as tarefas
        # e os alertas de telemetria da fazenda.
        #
        # As outras tres rotas de /servidor/ passageiam por
        # `_perfil_e_propriedade`, que ja tem a regra. Esta nao: `kanban_allowed`
        # recebe o `user`, nao o `request`, e e' o unico portao do kanban.
        return (
            user.perfil.tipo_usuario
            in [
                "produtor",
                "operario",
                "agronomo",
                "mecanico",
                "administrativo",
                "servidor",
            ]
            and user.perfil.ativo_servidor
        )
    except PerfilUsuario.DoesNotExist:
        # "sem perfil = produtor legado" devolvia `True` — acesso TOTAL. Isso
        # transforma a ausencia de perfil em privilege escalation: qualquer
        # conta autenticada sem `PerfilUsuario` (criada por shell, bulk_create,
        # restauracao de backup, ou SSO que nao disparou o signal) entrava no
        # Kanban como produtor. No banco real havia 2 contas assim
        # (`testuser`, `test_nav`).
        #
        # A negacao e' a unica leitura segura: quem nao tem perfil nao tem tipo
        # declarado, e "nao declarado" nao pode virar "tem todos os poderes".
        # O `signals.py` continua criando o perfil na criação de conta; esta
        # e' a segunda linha de defesa, e ela precisa fechar para tras.
        return False


def kanban_required(view_func):
    """Decorator para páginas do Kanban (acesso para Produtor e Operários)"""
    return user_passes_test(kanban_allowed, login_url="login")(view_func)


def perfil_allowed(user):
    """Verifica se o usuário pode acessar o Perfil (todos logados)"""
    return user.is_authenticated


def perfil_required(view_func):
    """Decorator para página de Perfil"""
    return user_passes_test(perfil_allowed, login_url="login")(view_func)


def get_user_propriedade(user):
    """Retorna a propriedade vinculada ao usuário (para operários) ou a primeira do produtor"""
    if not user.is_authenticated:
        return None
    try:
        perfil = user.perfil
        if perfil.tipo_usuario == "produtor":
            return user.propriedades.first()
        elif perfil.propriedade_vinculada:
            return perfil.propriedade_vinculada
        elif perfil.funcionario:
            return perfil.funcionario.propriedade
    except PerfilUsuario.DoesNotExist:
        pass
    return None


def get_user_funcionario(user):
    """Retorna o funcionário vinculado ao usuário (para operários)"""
    if not user.is_authenticated:
        return None
    try:
        return user.perfil.funcionario
    except PerfilUsuario.DoesNotExist:
        return None


def _no_store(response):
    response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response["Pragma"] = "no-cache"
    return response


class CadastroForm(forms.Form):
    usuario = forms.CharField(max_length=150, required=True, label="Usuário")
    senha = forms.CharField(widget=forms.PasswordInput, required=True, label="Senha")
    email = forms.EmailField(required=True, label="E-mail Corporativo")


class OperarioLoginForm(forms.Form):
    """Formulário para login de operário: nome da fazenda + usuário + senha"""

    nome_fazenda = forms.CharField(
        max_length=100, required=True, label="Nome da Fazenda"
    )
    usuario = forms.CharField(max_length=150, required=True, label="Usuário")
    senha = forms.CharField(widget=forms.PasswordInput, required=True, label="Senha")
