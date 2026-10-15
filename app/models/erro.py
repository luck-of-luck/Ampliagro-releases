from datetime import timedelta

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

from app.validators import validate_json_safe

TIPOS_ERRO = [
    ("bug", "Bug / Erro no Sistema"),
    ("dados", "Dados Incorretos"),
    ("performance", "Problema de Performance"),
    ("seguranca", "Suspeita de Segurança"),
    ("usabilidade", "Problema de Usabilidade"),
    ("integracao", "Erro de Integração"),
    ("outro", "Outro"),
]


class ErroReport(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="erro_reports"
    )
    email = models.EmailField()
    tipo = models.CharField(max_length=20, choices=TIPOS_ERRO, default="bug")
    descricao = models.TextField(
        help_text="O que a pessoa estava fazendo quando o erro ocorreu"
    )
    passos = models.TextField(blank=True, help_text="Passos para reproduzir o erro")
    enviar_rastreamento = models.BooleanField(
        default=False, help_text="Enviar últimos acontecimentos para rastreamento"
    )
    contexto = models.JSONField(
        default=dict,
        blank=True,
        help_text="Últimos acontecimentos, logs, dados técnicos",
    )
    navegador = models.CharField(max_length=200, blank=True)
    url = models.CharField(max_length=500, blank=True)
    resolvido = models.BooleanField(default=False)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.get_tipo_display()} - {self.email} - {self.criado_em:%Y-%m-%d %H:%M}"

    class Meta:
        verbose_name = "Relato de Erro"
        verbose_name_plural = "Relatos de Erro"
        ordering = ["-criado_em"]
