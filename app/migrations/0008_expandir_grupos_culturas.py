from django.db import migrations

# Culturas existentes que mudam de grupo
REALOCACOES = {
    "Laranja": "citricos",
    "Limão": "citricos",
    "Tangerina": "citricos",
    "Uva": "trepadeiras",
    "Maracujá": "trepadeiras",
    "Batata-inglesa": "tuberculos",
    "Mandioca": "tuberculos",
    "Feijão": "leguminosas",
}

# Novas culturas: grupo -> lista de (nome, unidade_comercial)
NOVAS_CULTURAS = {
    "citricos": [
        ("Lima", "caixas"),
        ("Ponkan", "caixas"),
    ],
    "tuberculos": [
        ("Batata-doce", "sacas"),
        ("Cenoura", "caixas"),
        ("Beterraba", "caixas"),
        ("Rabanete", "caixas"),
        ("Inhame", "sacas"),
    ],
    "ervas": [
        ("Manjericão", "maços"),
        ("Alecrim", "maços"),
        ("Hortelã", "maços"),
        ("Coentro", "maços"),
        ("Cebolinha", "maços"),
        ("Salsa", "maços"),
        ("Orégano", "maços"),
    ],
    "leguminosas": [
        ("Ervilha", "sacas"),
        ("Grão-de-bico", "sacas"),
        ("Lentilha", "sacas"),
    ],
    "frutas_bosque": [
        ("Morango", "caixas"),
        ("Amora", "caixas"),
        ("Mirtilo", "caixas"),
        ("Framboesa", "caixas"),
    ],
    "especiarias": [
        ("Pimenta-do-reino", "sacas"),
        ("Pimenta-malagueta", "caixas"),
        ("Gengibre", "caixas"),
        ("Açafrão", "caixas"),
        ("Canela", "caixas"),
    ],
    "medicinais": [
        ("Camomila", "maços"),
        ("Erva-cidreira", "maços"),
        ("Babosa", "maços"),
        ("Guaco", "maços"),
    ],
    "panc": [
        ("Ora-pro-nóbis", "maços"),
        ("Taioba", "maços"),
        ("Peixinho-da-horta", "maços"),
        ("Capuchinha", "maços"),
    ],
    "trepadeiras": [
        ("Chuchu", "caixas"),
        ("Vagem", "caixas"),
    ],
    "nativas": [
        ("Ipê", "mudas"),
        ("Pau-brasil", "mudas"),
        ("Jacarandá", "mudas"),
    ],
    "graos": [
        ("Quinoa", "sacas"),
        ("Milheto", "sacas"),
    ],
    "frutas": [
        ("Goiaba", "caixas"),
        ("Pêssego", "caixas"),
        ("Figo", "caixas"),
        ("Amora-preta", "caixas"),
        ("Pitaya", "caixas"),
    ],
    "hortalicas": [
        ("Alface", "dúzias"),
        ("Couve", "maços"),
        ("Espinafre", "maços"),
        ("Brócolis", "caixas"),
        ("Couve-flor", "unidades"),
        ("Repolho", "unidades"),
        ("Pepino", "caixas"),
        ("Abobrinha", "caixas"),
        ("Berinjela", "caixas"),
    ],
    "oleaginosas": [
        ("Gergelim", "sacas"),
        ("Canola", "sacas"),
        ("Niger", "sacas"),
    ],
    "fibras": [
        ("Sisal", "toneladas"),
        ("Linho", "toneladas"),
    ],
    "cana": [],
}


def aplicar(apps, schema_editor):
    Cultura = apps.get_model("app", "Cultura")
    for nome, grupo in REALOCACOES.items():
        Cultura.objects.filter(nome__iexact=nome).update(grupo=grupo)
    for grupo, culturas in NOVAS_CULTURAS.items():
        for nome, unidade in culturas:
            if not Cultura.objects.filter(nome__iexact=nome).exists():
                Cultura.objects.create(
                    nome=nome, grupo=grupo, unidade_comercial=unidade
                )


def reverter(apps, schema_editor):
    Cultura = apps.get_model("app", "Cultura")
    for nome, grupo in REALOCACOES.items():
        Cultura.objects.filter(nome__iexact=nome).update(grupo=None)
    for grupo, culturas in NOVAS_CULTURAS.items():
        for nome, _ in culturas:
            Cultura.objects.filter(nome__iexact=nome).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("app", "0007_alter_cultura_grupo"),
    ]

    operations = [
        migrations.RunPython(aplicar, reverter),
    ]
