from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("app", "0074_perfilusuario_config")]
    operations = [migrations.AddField(
        model_name="propriedade", name="cadastro_fiscal",
        field=models.JSONField(default=dict, blank=True,
            help_text="Dados do contribuinte, contador e contrapartes para revisão do LCDPR."),
    )]
