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

from .utils import *


@login_required
@hierarquia_required("equipe-agenda")
def equipe_agenda_view(request):
    from app.models import Funcionario

    funcionarios = Funcionario.objects.filter(
        propriedade__user=request.user
    ).select_related("propriedade", "user")
    return render(
        request,
        "equipe-agenda.html",
        {
            "funcionarios": funcionarios,
            "propriedades": Propriedade.objects.filter(user=request.user),
        },
    )


@login_required
def equipe_empregados_view(request):
    from app.models import Funcionario

    funcionarios = Funcionario.objects.filter(
        propriedade__user=request.user
    ).select_related("propriedade", "user")
    return render(
        request,
        "equipe-empregados.html",
        {
            "funcionarios": funcionarios,
            "propriedades": Propriedade.objects.filter(user=request.user),
        },
    )
