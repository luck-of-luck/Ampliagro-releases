from django.db import migrations

RECLASSIFICACOES = {
    "Café": "graos",
    "Laranja": "frutas",
    "Limão": "frutas",
    "Tangerina": "frutas",
    "Mandioca": "hortalicas",
}


def reclassificar_grupos(apps, schema_editor):
    Cultura = apps.get_model("app", "Cultura")
    for nome, grupo in RECLASSIFICACOES.items():
        Cultura.objects.filter(nome__iexact=nome).update(grupo=grupo)


def reverter_grupos(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("app", "0005_erroreport"),
    ]

    operations = [
        migrations.RunPython(reclassificar_grupos, reverter_grupos),
    ]
