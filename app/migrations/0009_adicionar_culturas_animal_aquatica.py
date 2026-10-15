from django.db import migrations

NOVAS_CULTURAS = {
    "aves": [
        ("Peru", "aves"),
        ("Codorna", "aves"),
        ("Marreco", "aves"),
        ("Galinha", "aves"),
    ],
    "suinos": [
        ("Matriz Suína", "cabeças"),
    ],
    "leite": [
        ("Vaca Leiteira", "litros"),
        ("Cabra Leiteira", "litros"),
    ],
    "peixes": [
        ("Peixe (Tambaqui)", "kg"),
        ("Peixe (Pacu)", "kg"),
        ("Peixe (Carpa)", "kg"),
        ("Peixe (Truta)", "kg"),
        ("Peixe (Jundiá)", "kg"),
        ("Peixe (Curimatã)", "kg"),
        ("Peixe (Pirarucu)", "kg"),
    ],
    "crustaceos": [
        ("Camarão", "kg"),
    ],
}


def aplicar(apps, schema_editor):
    Cultura = apps.get_model("app", "Cultura")
    for grupo, culturas in NOVAS_CULTURAS.items():
        for nome, unidade in culturas:
            if not Cultura.objects.filter(nome__iexact=nome).exists():
                Cultura.objects.create(
                    nome=nome, grupo="outro", unidade_comercial=unidade
                )


def reverter(apps, schema_editor):
    Cultura = apps.get_model("app", "Cultura")
    for grupo, culturas in NOVAS_CULTURAS.items():
        for nome, _ in culturas:
            Cultura.objects.filter(nome__iexact=nome).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("app", "0008_expandir_grupos_culturas"),
    ]

    operations = [
        migrations.RunPython(aplicar, reverter),
    ]
