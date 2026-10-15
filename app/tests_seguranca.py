"""Testes de segurança: financeiro fechado, uploads, criptografia."""

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings

from app.models import (
    ContaBancaria,
    LancamentoFinanceiro,
    PerfilUsuario,
    Propriedade,
)


def _mkuser(name):
    return User.objects.create_user(username=name, password="x")


class FinanceiroFechadoTest(TestCase):
    def setUp(self):
        self.produtor = _mkuser("sec-prod")
        self.prop = Propriedade.objects.create(
            user=self.produtor, nome="Faz Sec", area_total=10, uf="MT", cidade="X"
        )
        from django.utils import timezone

        LancamentoFinanceiro.objects.create(
            propriedade=self.prop,
            tipo="DESPESA",
            categoria="INSUMOS",
            valor=100,
            data=timezone.now().date(),
        )
        self.fin = _mkuser("sec-fin")
        PerfilUsuario.objects.update_or_create(
            user=self.fin,
            defaults={
                "tipo_usuario": "servidor",
                "area_servidor": "FINANCEIRO",
                "propriedade_vinculada": self.prop,
            },
        )
        self.mec = _mkuser("sec-mec")
        PerfilUsuario.objects.update_or_create(
            user=self.mec,
            defaults={
                "tipo_usuario": "servidor",
                "area_servidor": "MECANICA",
                "propriedade_vinculada": self.prop,
            },
        )

    def _get(self, user, url):
        c = Client()
        c.force_login(user)
        return c.get(url)

    def test_financeiro_area_ve_vinculada(self):
        r = self._get(self.fin, "/api/lancamentos/")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(len(r.json()["results"] or r.json()) >= 1)

    def test_mecanica_bloqueada_403(self):
        for url in ["/api/lancamentos/", "/api/contas-bancarias/"]:
            r = self._get(self.mec, url)
            self.assertEqual(r.status_code, 403, url)

    def test_produtor_normal(self):
        r = self._get(self.produtor, "/api/lancamentos/")
        self.assertEqual(r.status_code, 200)


class UploadSeguroTest(TestCase):
    def test_extensao_bloqueada(self):
        from django.core.exceptions import ValidationError

        from app.models import MonitoramentoPraga, Propriedade, Talhao

        u = _mkuser("up")
        prop = Propriedade.objects.create(
            user=u, nome="Faz Up", area_total=10, uf="MT", cidade="X"
        )
        talhao = Talhao.objects.create(
            propriedade=prop, nome="T", area_hectare=1, ativo=True
        )
        from django.core.files.uploadedfile import SimpleUploadedFile
        from django.utils import timezone

        m = MonitoramentoPraga(
            talhao=talhao,
            data=timezone.now().date(),
            praga="X",
            nivel_infestacao=1,
            foto=SimpleUploadedFile("virus.exe", b"MZ..."),
        )
        with self.assertRaises(ValidationError):
            m.full_clean()

    def test_tamanho_bloqueado(self):
        from django.core.exceptions import ValidationError

        from app.validators import validate_upload_size

        class F:
            size = 11 * 1024 * 1024

        with self.assertRaises(ValidationError):
            validate_upload_size(F())


@override_settings(AMPLIAGRO_DATA_KEY="P9BO46kX9OJ46V3LRADIHqiGN_lP_ElHOT9u9nZdWdM=")
class CriptografiaTest(TestCase):
    def test_roundtrip_doc(self):
        from django.utils import timezone

        u = _mkuser("cripto")
        prop = Propriedade.objects.create(
            user=u, nome="Faz Cripto", area_total=10, uf="MT", cidade="X"
        )
        lac = LancamentoFinanceiro.objects.create(
            propriedade=prop,
            tipo="DESPESA",
            categoria="INSUMOS",
            valor=10,
            data=timezone.now().date(),
            participante_doc="12345678901",
        )
        bruto = None
        from django.db import connection as _conn

        with _conn.cursor() as cur:
            cur.execute(
                "SELECT participante_doc FROM app_lancamentofinanceiro WHERE id = %s",
                [lac.pk],
            )
            bruto = cur.fetchone()[0]
        self.assertTrue(str(bruto).startswith("enc1:"))
        lac.refresh_from_db()
        self.assertEqual(lac.participante_doc, "12345678901")

    def test_legado_claro_passa(self):
        from django.utils import timezone

        u = _mkuser("cripto2")
        prop = Propriedade.objects.create(
            user=u, nome="Faz Cripto2", area_total=10, uf="MT", cidade="X"
        )
        lac = LancamentoFinanceiro.objects.create(
            propriedade=prop,
            tipo="DESPESA",
            categoria="INSUMOS",
            valor=10,
            data=timezone.now().date(),
        )
        LancamentoFinanceiro.objects.filter(pk=lac.pk).update(
            participante_doc="99988877766"
        )
        lac.refresh_from_db()
        self.assertEqual(lac.participante_doc, "99988877766")

    def test_gateway_hash_auth(self):
        from app.models import Gateway
        from app.seguranca import hash_cego

        u = _mkuser("gw")
        prop = Propriedade.objects.create(
            user=u, nome="Faz Gw", area_total=10, uf="MT", cidade="X"
        )
        gw = Gateway.objects.create(
            propriedade=prop, nome="GW1", gateway_eui="EUI" + "1" * 13
        )
        chave = gw.api_key  # claro na memória
        self.assertTrue(chave and not str(chave).startswith("enc1:"))
        from django.db import connection as _conn2

        with _conn2.cursor() as cur:
            cur.execute("SELECT api_key FROM app_gateway WHERE id = %s", [gw.pk])
            bruto = cur.fetchone()[0]
        self.assertTrue(str(bruto).startswith("enc1:"))
        achado = Gateway.objects.get(api_key_hash=hash_cego(chave))
        self.assertEqual(achado.pk, gw.pk)
