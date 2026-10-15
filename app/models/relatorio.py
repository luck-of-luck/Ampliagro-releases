from datetime import timedelta

from django.contrib.auth.models import User
from django.core.validators import FileExtensionValidator
from django.db import models
from django.utils import timezone

from app.validators import validate_json_safe, validate_upload_size


class RelatorioTemplate(models.Model):
    TIPO_CHOICES = [
        ("financeiro", "Financeiro"),
        ("producao", "Produção"),
        ("gerencial", "Gerencial Completo"),
        ("safra", "Safra Específica"),
        ("personalizado", "Personalizado"),
    ]
    FORMATO_CHOICES = [
        ("pdf", "PDF"),
        ("excel", "Excel"),
        ("csv", "CSV"),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    nome = models.CharField(max_length=100)
    tipo = models.CharField(
        max_length=20, choices=TIPO_CHOICES, default="personalizado"
    )
    formato = models.CharField(max_length=10, choices=FORMATO_CHOICES, default="pdf")
    configuracao = models.JSONField(
        default=dict, help_text="Config: widgets_incluidos, filtros, layout, etc."
    )
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Template de Relatório"
        verbose_name_plural = "Templates de Relatórios"

    def __str__(self):
        return f"{self.nome} ({self.get_tipo_display()})"


class RelatorioGerado(models.Model):
    STATUS_CHOICES = [
        ("pendente", "Pendente"),
        ("processando", "Processando"),
        ("concluido", "Concluído"),
        ("erro", "Erro"),
    ]
    template = models.ForeignKey(
        "RelatorioTemplate", on_delete=models.CASCADE, related_name="relatorios_gerados"
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default="pendente")
    arquivo = models.FileField(
        upload_to="relatorios/",
        blank=True,
        null=True,
        validators=[
            FileExtensionValidator(["pdf", "xlsx", "csv", "png", "jpg", "jpeg"]),
            validate_upload_size,
        ],
    )
    parametros = models.JSONField(default=dict)
    erro_msg = models.TextField(blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    concluido_em = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["-criado_em"]
        verbose_name = "Relatório Gerado"
        verbose_name_plural = "Relatórios Gerados"

    def __str__(self):
        return f"{self.template.nome} - {self.criado_em.strftime('%d/%m/%Y %H:%M')}"
