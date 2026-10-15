"""A IA VÊ a imagem (Gemini), em vez de extrair texto dela (OCR).

O DEFEITO QUE ISTO IMPEDE
=========================
O "Selecionar área" entrega um PNG da página — gráficos do dashboard
incluídos. Se esse PNG fosse para o OCR, o resultado seria um texto sem
cor, forma ou tendência: a IA "leria" o gráfico sem nunca o ter visto.
O pedido é explícito: ver a imagem, não um texto tirado dela.

O QUE ESTE TESTE TRAVA
======================
1. Sem GEMINI_API_KEY no servidor, a resposta é `sem_chave` com a
   instrução — e nenhuma chamada sai (quota não queima à toa).
2. Imagem ilegível é recusada com 400 antes de qualquer rede.
3. Com a nuvem mockada, a resposta do modelo chega intacta ao chat.
4. Chave recusada pela nuvem (400 com "API key") vira `chave_invalida`,
   e não um 500 nem um texto inventado.
5. Anônimo não entra (login obrigatório).
"""

import io
import json
import urllib.error
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

User = get_user_model()

#: PNG 1x1 válido — o menor bytes que passam na validação de assinatura.
PNG_1X1 = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)

URL = reverse("ia-ver-imagem")


def _resposta_gemini(texto):
    return {
        "candidates": [
            {"content": {"parts": [{"text": texto}]}, "finishReason": "STOP"}
        ]
    }


class VerImagemTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="visao_teste", password="x")
        self.client.force_login(self.user)

    def _post(self, imagem, pergunta="O que há aqui?"):
        return self.client.post(
            URL,
            data=json.dumps({"imagem": imagem, "pergunta": pergunta}),
            content_type="application/json",
        )

    def test_sem_chave_nao_chama_nuvem(self):
        with mock.patch("app.ia.visao._ler_chave", return_value=""):
            with mock.patch("urllib.request.urlopen") as Abrir:
                r = self._post(PNG_1X1)
        j = r.json()
        self.assertFalse(j["ok"])
        self.assertEqual(j["motivo"], "sem_chave")
        Abrir.assert_not_called()

    def test_imagem_ilegiven_e_400_antes_da_rede(self):
        with mock.patch("app.ia.visao._ler_chave", return_value="CHAVE"):
            with mock.patch("urllib.request.urlopen") as Abrir:
                r = self._post("isto-nao-e-base64!!!")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["motivo"], "imagem_invalida")
        Abrir.assert_not_called()

    def test_sucesso_mockado_chega_intacto(self):
        corpo = json.dumps(
            _resposta_gemini("Vejo um gráfico de barras em alta.")
        ).encode()
        fake = mock.MagicMock()
        fake.__enter__.return_value.read.return_value = corpo
        with mock.patch("app.ia.visao._ler_chave", return_value="CHAVE"):
            with mock.patch("urllib.request.urlopen", return_value=fake) as Abrir:
                r = self._post(PNG_1X1)
        j = r.json()
        self.assertTrue(j["ok"])
        self.assertEqual(j["provedor"], "gemini")
        self.assertIn("barras em alta", j["resposta"])
        # O formato DO PEDIDO também é contrato: a REST fala camelCase
        # (`inlineData`/`mimeType`); snake_case vira 400 na nuvem.
        req = Abrir.call_args[0][0]
        self.assertIn(":generateContent", req.full_url)
        self.assertNotIn("key=", req.full_url)
        self.assertEqual(req.get_header("X-goog-api-key"), "CHAVE")
        partes = json.loads(req.data)["contents"][0]["parts"]
        self.assertIn("text", partes[0])
        self.assertEqual(partes[1]["inlineData"]["mimeType"], "image/png")
        self.assertTrue(partes[1]["inlineData"]["data"])

    def test_chave_da_propriedade_tem_precedencia(self):
        corpo = json.dumps(_resposta_gemini("Vejo números.")).encode()
        fake = mock.MagicMock()
        fake.__enter__.return_value.read.return_value = corpo
        with mock.patch("app.ia.visao._ler_chave", return_value=""):
            with mock.patch(
                "app.ia.visao._chave_da_propriedade", return_value="PROP-KEY"
            ):
                with mock.patch("urllib.request.urlopen", return_value=fake) as Abrir:
                    r = self._post(PNG_1X1)
        j = r.json()
        self.assertTrue(j["ok"])
        req = Abrir.call_args[0][0]
        self.assertEqual(req.get_header("X-goog-api-key"), "PROP-KEY")

    def test_sem_propriedade_cai_no_ambiente(self):
        from app.ia.visao import _chave_da_propriedade

        # usuário sem propriedade: "" sem levantar, sem rede
        self.assertEqual(_chave_da_propriedade(self.user), "")
        self.assertEqual(_chave_da_propriedade(None), "")

    def test_chave_recusada_vira_motivo(self):
        corpo = io.BytesIO(
            b'{"error": {"message": "API key not valid. Pass a valid API key."}}'
        )
        erro = urllib.error.HTTPError(URL, 400, "Bad Request", {}, corpo)
        with mock.patch("app.ia.visao._ler_chave", return_value="ERRADA"):
            with mock.patch("urllib.request.urlopen", side_effect=erro):
                r = self._post(PNG_1X1)
        j = r.json()
        self.assertFalse(j["ok"])
        self.assertEqual(j["motivo"], "chave_invalida")

    def test_401_tambem_e_chave_invalida(self):
        corpo = io.BytesIO(
            b'{"error": {"code": 401, "message": "invalid authentication credentials"}}'
        )
        erro = urllib.error.HTTPError(URL, 401, "Unauthorized", {}, corpo)
        with mock.patch("app.ia.visao._ler_chave", return_value="MORTA"):
            with mock.patch("urllib.request.urlopen", side_effect=erro):
                r = self._post(PNG_1X1)
        j = r.json()
        self.assertFalse(j["ok"])
        self.assertEqual(j["motivo"], "chave_invalida")

    def test_anonimo_nao_entra(self):
        self.client.logout()
        r = self._post(PNG_1X1)
        self.assertEqual(r.status_code, 302)


class ChaveNuvemTest(TestCase):
    """A engrenagem tem de funcionar de verdade: sem ela, nem a nuvem nem
    a visão por propriedade existem — e era exatamente esse o estado (view
    sem import, módulos sem loader). Trava o round-trip GET/POST/DELETE,
    incluindo a cifra em repouso."""

    def setUp(self):
        from app.models import Propriedade

        self.user = User.objects.create_user(username="chave_teste", password="x")
        self.prop = Propriedade.objects.create(
            user=self.user, nome="Fazenda Chave", area_total=10
        )
        self.client.force_login(self.user)

    def test_round_trip_chave(self):
        from app.models.ia import ChaveIA

        url = reverse("ia-chave-nuvem")
        self.assertEqual(self.client.get(url).json()["tem_chave"], False)
        r = self.client.post(
            url,
            data=json.dumps({"chave": "SEGREDO-123"}),
            content_type="application/json",
        )
        j = r.json()
        self.assertTrue(j["ok"])
        self.assertEqual(j["provedor"], "gemini")
        self.assertEqual(self.client.get(url).json()["tem_chave"], True)
        # cifrada em repouso: SQL cru (sem conversores do campo) não pode
        # conter o texto puro — `values_list` já passaria por
        # `from_db_value` e devolveria descriptografado, o que não prova nada.
        from django.db import connection

        with connection.cursor() as cur:
            cur.execute(
                "SELECT chave FROM %s WHERE propriedade_id = %%s"
                % ChaveIA._meta.db_table,
                [self.prop.id],
            )
            bruta = cur.fetchone()[0]
        self.assertTrue(str(bruta).startswith("enc1:"))
        self.assertNotIn("SEGREDO-123", str(bruta))
        r = self.client.delete(url)
        self.assertTrue(r.json()["ok"])
        self.assertEqual(self.client.get(url).json()["tem_chave"], False)

    def test_post_sem_chave_e_400(self):
        url = reverse("ia-chave-nuvem")
        r = self.client.post(url, data=json.dumps({}), content_type="application/json")
        self.assertEqual(r.status_code, 400)

    def test_testar_sem_colar_e_400(self):
        url = reverse("ia-chave-testar")
        r = self.client.post(
            url, data=json.dumps({"chave": "  "}), content_type="application/json"
        )
        self.assertEqual(r.status_code, 400)
        self.assertFalse(r.json()["valido"])

    def test_testar_valida_sem_salvar(self):
        from app.models.ia import ChaveIA

        fake = mock.MagicMock()
        fake.__enter__.return_value.read.return_value = json.dumps(
            {"models": [{"name": "models/gemini-3.8-flash"}]}
        ).encode()
        url = reverse("ia-chave-testar")
        with mock.patch("urllib.request.urlopen", return_value=fake):
            r = self.client.post(
                url,
                data=json.dumps({"chave": "CANDIDATA-1"}),
                content_type="application/json",
            )
        j = r.json()
        self.assertTrue(j["ok"])
        self.assertTrue(j["valido"])
        # validar não é gravar: nada pode ter ido parar no banco
        self.assertFalse(ChaveIA.objects.exists())

    def test_testar_recusada_nao_salva(self):
        from app.models.ia import ChaveIA

        corpo = io.BytesIO(b'{"error": {"message": "API key not valid."}}')
        erro = urllib.error.HTTPError(
            reverse("ia-chave-testar"), 400, "Bad Request", {}, corpo
        )
        with mock.patch("urllib.request.urlopen", side_effect=erro):
            r = self.client.post(
                reverse("ia-chave-testar"),
                data=json.dumps({"chave": "ERRADA"}),
                content_type="application/json",
            )
        j = r.json()
        self.assertFalse(j["valido"])
        self.assertEqual(j["motivo"], "chave_invalida")
        self.assertFalse(ChaveIA.objects.exists())
