"""O webhook TTN nao tem bypass. E este teste e' o que o mantem assim.

O QUE ESTE GUARDA
=================
`app/iot/views.py:14` dizia, sobre `POST /api/iot/mqtt/webhook/`:

    "webhook TTN/ChirpStack (sem api_key, valida por config)"

**A frase estava errada.** Nao ha "valida por config": nao ha allowlist de
`FonteDadosExterna` neste caminho, nao ha assinatura de payload, e nao ha
`AMPLIAGRO_DATA_KEY`. O que existe e' `Gateway.api_key_hash` com hash cego
(`app/seguranca.py:hash_cego`), que e' o mesmo gate dos outros pushes.

Isto nao e' um erro de documentacao. E' uma frase que descreve um bypass que
nao existe, num ficheiro que alguem vai ler para decidir se pode expor um
broker a internet. Um leitor que acredite e' quem expoe.

E o codigo esta CERTO. `push_telemetry:134` responde 401 sem credencial, e o
comentario em `:148-158` descreve o bypass como trabalho por fazer, em vez de
o fazer. Este teste existe para que essa distincao se mantenha.

A ASSIMETRIA QUE ISTO PROTEGE
=============================
    POST /api/iot/push/                     exige api_key
    POST /api/iot/push/<device_eui>/        exige api_key
    POST /api/iot/mqtt/webhook/             exige api_key   <-- este ficheiro

O terceiro existe porque o TTN entrega por HTTP e o corpo traz o
`dev_eui` em vez de o ter na URL. Reconhecer a FORMA do payload
(`uplink_message`, `end_device_ids`) nao autentica nada — serve para extrair
o `dev_eui` e perguntar por ele. `views.py:174-177` diz isso em comentario, e
este teste verifica que o comentario e' verdade.

POR QUE FALHA SE ALGUEM MEXER
============================
O bypass sem `api_key` continua POR FAZER, e e' razoavel: um ChirpStack
autenticado por basic-auth nao repete a credencial em cada uplink. Se um dia
se implementar, tem de ser com allowlist + assinatura, e este teste tem de
mudar **propositalmente** — com o bypass virado em texto explicito, para
que a desactivacao seja um acto e nao um esquecimento.

Enquanto isso, este teste e' a declarative que mantem a porta fechada.
"""

from django.test import TestCase


class WebhookTtnSemAuthTest(TestCase):
    """Todas as ingestaes exigem credencial — incluindo a do webhook."""

    def test_push_sem_api_key_leva_401(self):
        """A base: o push generico recusa sem `X-API-Key`."""
        r = self.client.post("/api/iot/push/", {}, content_type="application/json")
        self.assertEqual(
            r.status_code,
            401,
            "push sem `X-API-Key` deixou de levar 401. Toda a proteccao de "
            "telemetria assenta nesta recusa.",
        )

    def test_webhook_ttn_sem_api_key_leva_401(self):
        """O que este ficheiro guarda: o webhook NAO tem bypass.

        O payload tem a forma que o `views.py:178` reconhece. A forma
        recognizes mas nao autentica — o `_get_device_from_request` e'
        quem decide, e sem credencial responde 401.
        """
        payload = {
            "uplink_message": {
                "f_port": 2,
                "decoded_payload": {"temperatura": 23.4},
                "end_device_ids": {"dev_eui": "ABCD1234ABCD1234"},
            }
        }
        r = self.client.post(
            "/api/iot/mqtt/webhook/", payload, content_type="application/json"
        )
        self.assertEqual(
            r.status_code,
            401,
            "O webhook TTN deixou de exigir `api_key`. A rota estava "
            "documentada como 'sem api_key, valida por config' "
            "(`app/iot/views.py:14`) e essa frase estava errada: nao ha "
            "validacao por config.\n\n"
            "Se implementares o bypass sem `api_key`, tem de ser com "
            "(1) allowlist de `FonteDadosExterna` e (2) assinatura do "
            "payload. A desactivacao deste teste tem de ser um acto "
            "deliberado: troca-o por uma classe nova que exija as duas "
            "verificacoes, para que o codigo novo nao possa herdar a "
            "permissao que este teste recusa.",
        )

    def test_reconhecer_a_forma_do_payload_nao_autentica(self):
        """A forma e' um DICA de por onde pedir, nao uma credencial.

        Este e' o teste que impede a proxima invencao: "o payload tem
        `end_device_ids`, logo vem de um dispositivo nosso". Nao vem. O
        `dev_eui` sai do CORPO do pedido, e um corpo de pedido e' escrita do
        cliente. So a `api_key` e' prova.
        """
        payload = {
            "end_device_ids": {"dev_eui": "DEADBEEFDEADBEEF"},
            "decoded_payload": {"temperatura": 99.9},
        }
        r = self.client.post(
            "/api/iot/mqtt/webhook/", payload, content_type="application/json"
        )
        self.assertIn(
            r.status_code,
            (401, 404),
            f"um payload com `dev_eui` no corpo, sem `api_key`, deu "
            f"{r.status_code}. O `dev_eui` do corpo nao autentica: e' "
            "escrita do cliente, nao prova de origem.",
        )

    def test_telemetria_consulta_exige_sessao(self):
        """A leitura tambem esta fechada — nao so a escrita.

        Um endpoint de telemetria aberto devolve a serie historica de
        qualquer sensor. `views.py:317` tem `@login_required`; este teste
        e' o que diz que isso e' uma decisao e nao um esquecimento.
        """
        r = self.client.get("/api/iot/telemetry/")
        self.assertIn(
            r.status_code,
            (302, 401, 403),
            f"`/api/iot/telemetry/` respondeu {r.status_code} a anonimo. "
            "Devolve a serie de sensores de toda a herdade.",
        )
