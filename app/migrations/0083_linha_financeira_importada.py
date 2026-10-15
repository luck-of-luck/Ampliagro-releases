from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("app", "0082_remove_cultivar_app_cultiva_cultura_68da7d_idx_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="LinhaFinanceiraImportada",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("origem", models.CharField(max_length=100)),
                ("id_externo", models.CharField(max_length=100)),
                ("hash_conteudo", models.CharField(max_length=64)),
                ("arquivo", models.CharField(max_length=255)),
                (
                    "fonte_dado",
                    models.CharField(
                        default="declarado", editable=False, max_length=20
                    ),
                ),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                (
                    "importado_por",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "lancamento",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT,
                        to="app.lancamentofinanceiro",
                    ),
                ),
                (
                    "propriedade",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        to="app.propriedade",
                    ),
                ),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(
                        fields=("propriedade", "origem", "id_externo"),
                        name="financeiro_origem_id_unico",
                    )
                ]
            },
        ),
    ]
