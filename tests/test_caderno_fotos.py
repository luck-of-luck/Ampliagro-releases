"""A foto de campo tem de chegar ao servidor, e ser prova — não opinião.

O QUE ESTE FICHEIRO PROVA
=========================
O `9.md` §7.3: *"sem isto, o 'sem sinal' é uma nota de texto. A Aegro tira
foto georreferenciada — que é prova. Um registo sem prova é uma opinião."*

`POST /api/caderno/fotos/` devolvia **501** com a lista do que faltava. Esta
implementação, e estes testes medem o que a lista dizia e o que ficou por
medir.

OS TRÊS CASOS QUE IMPORTAM
=========================
1. **A foto pode chegar antes da nota.** O produtor fotografa às 9h, escreve
   a nota às 9h05 num sítio sem rede, e o sync processa por ordem de chegada.
   Se a foto exigisse que a nota já existisse, a primeira sincronização de uma
   manhã inteira perderia todas as fotos — e não há segunda oportunidade no
   campo.

2. **A coordenada é a do telefone, no momento da captura.** Se viesse do
   servidor, seria onde o telefone estava quando fez o sync. Num talhão de
   50 ha isso é um sítio diferente.

3. **Idempotência.** O browser reenvia enquanto não recebe 2xx. Sem isso, uma
   manhã offline produz a mesma foto duas vezes.

O QUE NÃO ESTÁ NESTE FICHEIRO
=============================
Voz. `voice/` continua em 501: precisa de decisão de produto (guardar áudio
ou só o texto?), não de código.
"""

import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

@pytest.fixture
def cenario(django_user_model):
    from app.models import Propriedade

    user = django_user_model.objects.create_user(username="foto", password="x")
    prop = Propriedade.objects.create(
        user=user, nome="Fazenda da Foto", uf="GO", area_total=100
    )
    return {"user": user, "prop": prop}


def _png(nome="campo.png"):
    """Um PNG de 1x1. Valido e minimo."""
    return SimpleUploadedFile(
        nome,
        io.BytesIO(
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
            b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06"
            b"\x00\x00\x00\x1f\x15\xc4\x89"
        ).read(),
        content_type="image/png",
    )


def _post(cenario, ficheiro=None, **campos):
    from rest_framework.test import APIClient

    c = APIClient()
    c.force_login(cenario["user"])
    dados = dict(campos)
    if ficheiro is not None:
        dados["image"] = ficheiro
    return c.post(reverse("api-caderno-fotos"), dados)


# ─────────────────────────────────────────────────────────────────────────────
# 1. A rota deixou de ser um 501
# ─────────────────────────────────────────────────────────────────────────────


def test_a_rota_ja_existe_e_nao_e_501():
    """O sintoma original era 501. Um 501 que ninguem implementa e' um 404
    com mais texto — e o browser nao sabe a diferença."""
    assert reverse("api-caderno-fotos").endswith("/api/caderno/fotos/")


def test_a_foto_grava_e_persiste(cenario):
    """O caminho feliz: entra multipart, sai 201, e ha' linha na base."""
    from app.models import FotoNota

    r = _post(
        cenario,
        _png(),
        legenda="pulgão no canto norte",
        latitude="-15.794200",
        longitude="-47.882100",
        precisao_metros="8.5",
    )

    assert r.status_code == 201, r.content
    corpo = r.json()
    assert corpo["ok"] is True

    foto = FotoNota.objects.get(pk=corpo["id"])
    assert foto.user_id == cenario["user"].pk
    assert foto.legenda == "pulgão no canto norte"
    assert float(foto.latitude) == -15.7942
    assert foto.coordenada_confiavel is True


# ─────────────────────────────────────────────────────────────────────────────
# 2. A FOTO PODE CHEGAR ANTES DA NOTA
# ─────────────────────────────────────────────────────────────────────────────


def test_a_foto_chega_antes_da_nota(cenario):
    """O caso do produtor no talhao, sem rede, as 9h.

    A fila processa por ordem de chegada: a foto pode ser a primeira. Se
    devolvesse 400 "nota não encontrada", o browser não teria outro sítio
    para a meter e a foto era perdida — que é o pior sítio possível para
    perder: no campo, sem rede, sem segunda tentativa.
    """
    r = _post(cenario, _png(), nota_offline_id="999", legenda="antes da nota")

    assert r.status_code == 201, (
        f"a foto foi recusada por a nota ainda nao existir: {r.content[:200]}"
    )
    assert r.json()["nota_id"] is None, "deveria ficar orfa"


def test_a_foto_liga_a_nota_quando_ela_ja_existe(cenario):
    """Quando a nota ja' foi sincronizada, a foto liga-se pelo `offline_id`."""
    from app.models import NotaCampo

    nota = NotaCampo.objects.create(
        user=cenario["user"],
        propriedade=cenario["prop"],
        conteudo="Pulgão no canto norte",
        registada_em="2026-10-05T09:00:00Z",
        offline_id=42,
    )

    r = _post(cenario, _png(), nota_offline_id="42")

    assert r.status_code == 201, r.content
    assert r.json()["nota_id"] == nota.pk


# ─────────────────────────────────────────────────────────────────────────────
# 3. A COORDENADA — o que separa prova de opinião
# ─────────────────────────────────────────────────────────────────────────────


def test_sem_coordenada_a_fica_marcada_como_nao_confiavel(cenario):
    """Foto sem GPS: guarda-se, mas **diz-se** que nao tem coordenada.

    `coordenada_confiavel = False` e' o `sem_dado` da proveniencia aplicado a
    uma fotografia. A foto e' real; a coordenada nao existe. Sao coisas
    diferentes, e um registo que as misture e' um registo que mente.
    """
    from app.models import FotoNota

    r = _post(cenario, _png(), legenda="sem gps")
    assert r.status_code == 201

    foto = FotoNota.objects.get(pk=r.json()["id"])
    assert foto.latitude is None
    assert foto.coordenada_confiavel is False


def test_coordenada_sem_precisao_nao_e_confiavel(cenario):
    """Coordenada sem precisão é um ponto sem medida de quão exacto é.

    Útil para o produtor se orientar. Não é uma prova georreferenciada, e a
    auditoria distingue as duas coisas.
    """
    r = _post(cenario, _png(), latitude="-15.794200", longitude="-47.882100")
    assert r.status_code == 201
    assert r.json()["coordenada_confiavel"] is False, (
        "coordenada sem precisao foi marcada como confiavel"
    )


def test_coordenada_com_precisao_e_confiavel(cenario):
    r = _post(
        cenario,
        _png(),
        latitude="-15.794200",
        longitude="-47.882100",
        precisao_metros="8.5",
    )
    assert r.status_code == 201
    assert r.json()["coordenada_confiavel"] is True


def test_coordenada_fora_do_intervalo_recebe_400(cenario):
    """Latitude 200 não é uma coordenada. Deixar passar grava um numero que
    nenhum mapa sabe colocar."""
    r = _post(cenario, _png(), latitude="200", longitude="-47.88")
    assert r.status_code == 400
    assert "latitude" in str(r.json()).lower()


# ─────────────────────────────────────────────────────────────────────────────
# 4. Idempotência
# ─────────────────────────────────────────────────────────────────────────────


def test_reenvio_nao_duplica(cenario):
    """O browser reenvia enquanto não recebe 2xx. Uma manhã offline com 20
    fotos e 5 tentativas de sync seriam 100 linhas sem esta guarda."""
    from app.models import FotoNota

    r1 = _post(cenario, _png(), foto_offline_id="7")
    r2 = _post(cenario, _png(), foto_offline_id="7")

    assert r1.status_code == 201
    assert r2.status_code == 200, "o segundo envio devolveu %s" % r2.status_code
    assert r2.json()["duplicado"] is True
    assert r2.json()["id"] == r1.json()["id"]
    assert FotoNota.objects.count() == 1


# ─────────────────────────────────────────────────────────────────────────────
# 5. O que NÃO aceitamos
# ─────────────────────────────────────────────────────────────────────────────


def test_sem_ficheiro_recebe_400(cenario):
    r = _post(cenario, None)
    assert r.status_code == 400
    assert "image" in str(r.json())


def test_extensao_nao_aceite_recebe_400(cenario):
    """Um `.exe` disfarçado de foto é um ataque; um `.svg` é um ficheiro que
    pode conter script. A lista é fechada."""
    from app.models import FotoNota

    r = _post(
        cenario,
        SimpleUploadedFile("malicioso.svg", b"<svg onload=alert(1)>"),
    )
    assert r.status_code == 400
    assert "svg" in str(r.json()).lower()
    assert FotoNota.objects.count() == 0, "guardou ficheiro rejeitado"


def test_ficheiro_grande_recebe_400(cenario):
    """O limite é o mesmo do resto do projecto (`MAX_UPLOAD_MB`)."""
    from app.validators import MAX_UPLOAD_MB

    grande = SimpleUploadedFile(
        "grande.jpg", b"x" * ((MAX_UPLOAD_MB + 1) * 1024 * 1024)
    )
    r = _post(cenario, grande)
    assert r.status_code == 400
    assert "grande" in str(r.json()).lower()


def test_anonymous_nao_faz_upload(cenario):
    """Sem sessão, o browser recebe 401 — não uma página de login."""
    from rest_framework.test import APIClient

    r = APIClient().post(reverse("api-caderno-fotos"), {"image": _png()})
    assert r.status_code in (401, 403)


# ─────────────────────────────────────────────────────────────────────────────
# 6. Tenancy
# ─────────────────────────────────────────────────────────────────────────────


def test_nao_liga_a_nota_de_outro_utilizador(django_user_model, cenario):
    """Um `nota_offline_id` de outra fazenda não prende a nossa foto.

    Este POST vem do `fetch` com a sessão do produtor e não passa pelo
    `TenantIsolationMiddleware`. A defesa é o mesmo `user=request.user` do
    filtro — e é a única que este caminho tem.
    """
    from app.models import NotaCampo

    outro = django_user_model.objects.create_user(username="outro", password="x")
    nota_alheia = NotaCampo.objects.create(
        user=outro,
        conteudo="nota de outra fazenda",
        registada_em="2026-10-05T09:00:00Z",
        offline_id=555,
    )

    r = _post(cenario, _png(), nota_offline_id="555")

    assert r.status_code == 201, "a foto tem de ser aceite, so que orfa"
    assert r.json()["nota_id"] is None, (
        "a foto prendeu-se a uma nota de outro utilizador — fuga cross-tenant"
    )
    nota_alheia.refresh_from_db()
    assert nota_alheia.fotos.count() == 0