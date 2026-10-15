"""O switch da nuvem usa o modelo de verdade — não um adesivo no prompt.

O DEFEITO QUE ISTO IMPEDE
=========================
O modo "Usar agente da nuvem" era só uma frase no system do modelo LOCAL
("consulte diretamente a nuvem"), e o modelo local não sai da máquina: ou
ignorava, ou fingia. Este teste trava o caminho real — conversa ao Gemini
via `/api/ia/nuvem/`, com papéis traduzidos (assistant->model) e instrução
de sistema separada — e a queda silenciosa para o motor local em falha.

O QUE ESTE TESTE TRAVA
======================
1. Papéis traduzidos e histórico podado no pedido.
2. Sem pergunta, recusa honesta sem rede.
3. Sem chave, motivo sem_chave sem rede.
4. Sucesso mockado chega intacto com provedor gemini.
5. Falha remota vira motivo com "motor local" (o frontend cai de volta).
"""

import io
import json
import urllib.error
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

User = get_user_model()

URL = reverse("ia-nuvem")


def _resposta(texto):
    return {
        "candidates": [
            {"content": {"parts": [{"text": texto}]}, "finishReason": "STOP"}
        ]
    }


class NuvemChatTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="nuvem_teste", password="x")
        self.client.force_login(self.user)

    def _post(self, mensagens):
        return self.client.post(
            URL,
            data=json.dumps({"mensagens": mensagens}),
            content_type="application/json",
        )

    def test_sem_mensagens_e_400(self):
        r = self._post([])
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["motivo"], "sem_pergunta")

    def test_sem_chave_nao_chama_nuvem(self):
        with mock.patch("app.ia.nuvem._ler_chave", return_value=""):
            with mock.patch("app.ia.nuvem._chave_da_propriedade", return_value=""):
                with mock.patch("urllib.request.urlopen") as Abrir:
                    r = self._post([{"role": "user", "content": "oi"}])
        j = r.json()
        self.assertFalse(j["ok"])
        self.assertEqual(j["motivo"], "sem_chave")
        Abrir.assert_not_called()

    def test_papeis_traduzidos_e_instrucao_separada(self):
        corpo = json.dumps(_resposta("Olá, produtor!")).encode()
        fake = mock.MagicMock()
        fake.__enter__.return_value.read.return_value = corpo
        msgs = [{"role": "system", "content": "lixo ignora"}] + [
            {"role": "user", "content": "x" * 900},
            {"role": "assistant", "content": "entendi"},
            {"role": "user", "content": "e agora?"},
        ]
        with mock.patch("app.ia.nuvem._ler_chave", return_value="CHAVE"):
            with mock.patch("urllib.request.urlopen", return_value=fake) as Abrir:
                r = self._post(msgs)
        j = r.json()
        self.assertTrue(j["ok"])
        self.assertIn("produtor", j["resposta"])
        enviado = json.loads(Abrir.call_args[0][0].data)
        # system vai em systemInstruction, nunca na conversa
        self.assertIn("AmplIA", enviado["systemInstruction"]["parts"][0]["text"])
        papeis = [m["role"] for m in enviado["contents"]]
        self.assertNotIn("system", papeis)
        self.assertNotIn("assistant", papeis)
        self.assertIn("model", papeis)
        # podado e cortado
        for m in enviado["contents"]:
            self.assertLessEqual(len(m["parts"][0]["text"]), 500)
        self.assertLessEqual(len(enviado["contents"]), 8)

    def test_falha_remota_cai_no_motor_local(self):
        corpo = io.BytesIO(b'{"error": {"message": "boom"}}')
        erro = urllib.error.HTTPError(URL, 500, "Server Error", {}, corpo)
        with mock.patch("app.ia.nuvem._ler_chave", return_value="CHAVE"):
            with mock.patch("urllib.request.urlopen", side_effect=erro):
                r = self._post([{"role": "user", "content": "oi"}])
        j = r.json()
        self.assertFalse(j["ok"])
        self.assertIn("motor local", j["erro"])

    def test_anonimo_nao_entra(self):
        self.client.logout()
        r = self._post([{"role": "user", "content": "oi"}])
        self.assertEqual(r.status_code, 302)
