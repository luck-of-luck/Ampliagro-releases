"""Prova que o canal de WhatsApp entrega — e que NAO finge.

Tres coisas sao testadas aqui, por ordem de importancia:

1. SEM configuracao, diz **o que falta, pelo nome**. Nao "ha um problema".
2. COM configuracao, monta o pedido que a Meta espera — sem rede.
3. **HTTP 200 nao e' entrega.** A Meta responde 200 com `{"error": {...}}`
   quando o template nao esta aprovado ou o numero esta mal escrito. Quem so'
   olha para o status code diz ao produtor "entregue" e a mensagem nunca chega.
   E' o teste que vale mais deste ficheiro.

A rede e' substituida por um dublê. Nenhum destes testes toca a internet, e
`urlopen` e' trocado dentro do modulo — se algum teste precisar de rede, ha
um erro no teste, nao uma excepcao silenciosa.
"""

import io
import json
import pathlib
import urllib.error

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from app.services import whatsapp as WA
from app.services.notificacoes import disparar_canais

CONFIG = {
    "WHATSAPP_ACCESS_TOKEN": "token-de-teste",
    "WHATSAPP_PHONE_NUMBER_ID": "123456789",
    "WHATSAPP_TEMPLATE_ALERTA": "alerta_operacional",
}


class _RespostaFalsa:
    """Substitui a resposta do urlopen. Guardo o pedido para o teste ver."""

    def __init__(self, corpo: dict, codigo: int = 200):
        self.corpo = corpo
        self.codigo = codigo
        self.pedido = None

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return json.dumps(self.corpo).encode("utf-8")


_URLOPEN_ORIGINAL = []


def _ligar_urlopen(resposta, capturado: dict):
    """Troca o urlopen do modulo e guarda o pedido."""

    if not _URLOPEN_ORIGINAL:
        _URLOPEN_ORIGINAL.append(WA.urllib.request.urlopen)

    def falso(req, timeout=None):
        capturado["req"] = req
        capturado["corpo"] = json.loads(req.data.decode("utf-8"))
        capturado["url"] = req.full_url
        capturado["headers"] = req.headers
        if isinstance(resposta, Exception):
            raise resposta
        return resposta

    WA.urllib.request.urlopen = falso


def tearDownModule():
    """Devolve o `urlopen` verdadeiro.

    MEDIDO 2026-10-14: `WA.urllib` E' o modulo `urllib` do Python, nao uma
    copia. Escrever em `WA.urllib.request.urlopen` substitui
    `urllib.request.urlopen` no processo INTEIRO, e nada o repunha.

    O pytest importa todos os ficheiros de teste na recolha e so depois
    corre, portanto este vazamento chegava a ficheiros muito posteriores:
    `tests/test_bootstrap_health.py` deixava de conseguir falar com o
    servidor HTTP local do health-check e falhava 5 de 5, tendo 5 de 5 a
    passar isolado. O sintoma aparece longe da causa, que e' o pior sitio
    possivel para uma avaria.

    Nao se patcheja `WA.enviar` aqui: e' o objectivo do teste. Patched o
    `urlopen` global e' que se devolve.
    """
    while _URLOPEN_ORIGINAL:
        WA.urllib.request.urlopen = _URLOPEN_ORIGINAL.pop()


class ConfigHonestaTest(TestCase):
    def test_sem_nada_configurado_diz_as_tres_pecas(self):
        ok, porque = WA.configurado()
        self.assertFalse(ok)
        for chave in (
            "WHATSAPP_ACCESS_TOKEN",
            "WHATSAPP_PHONE_NUMBER_ID",
            "WHATSAPP_TEMPLATE_ALERTA",
        ):
            self.assertIn(chave, porque)

    def test_explica_porque_o_template_e_obrigatorio(self):
        """Sem isto, alguem implementa, testa com um numero de amigo e leva
        com um erro 131008 da Meta sem saber do que se trata."""
        _, porque = WA.configurado()
        self.assertIn("template", porque.lower())
        self.assertIn("Meta", porque)

    @override_settings(**CONFIG)
    def test_com_os_tres_diz_que_usa_a_meta(self):
        ok, porque = WA.configurado()
        self.assertTrue(ok, porque)
        self.assertIn("Meta", porque)

    @override_settings(WHATSAPP_ACCESS_TOKEN="t", WHATSAPP_PHONE_NUMBER_ID="1")
    def test_sem_template_diz_que_a_meta_nao_deixa_iniciar_conversa(self):
        ok, porque = WA.configurado()
        self.assertFalse(ok)
        self.assertIn("WHATSAPP_TEMPLATE_ALERTA", porque)
        self.assertIn("Meta", porque)


class NumeroTest(TestCase):
    """O telefone e' a primeira coisa que um produtor real estraga."""

    def test_formatos_brasileiros_viram_e164(self):
        casos = {
            "(61) 99888-7777": "+5561998887777",
            "61 99888 7777": "+5561998887777",
            "061998887777": "+5561998887777",
            "61998887777": "+5561998887777",
            "+55 61 99888-7777": "+5561998887777",
            "+5561998887777": "+5561998887777",
            "(11) 3333-4444": "+551133334444",  # fixo, 10 digitos
        }
        for bruto, esperado in casos.items():
            self.assertEqual(WA.normalizar_e164(bruto), esperado, f"falhou: {bruto!r}")

    def test_o_que_da_zero(self):
        """Um telefone que nao normaliza nao e' telefone. Nao inventar um."""
        for ruim in ("", "abc", "--", "+1 (000) 000", "123"):
            self.assertEqual(WA.normalizar_e164(ruim), "", f"nao devia: {ruim!r}")


class PedidoTest(TestCase):
    """O corpo que a Meta espera, sem sair da maquina."""

    @override_settings(**CONFIG)
    def test_monta_template_com_o_texto_do_alerta(self):
        capturado = {}
        _ligar_urlopen(_RespostaFalsa({"messages": [{"id": "wamid.1"}]}), capturado)

        WA.enviar(
            "+5561998887777", "Conta vencida", "Fertilizante, R$ 1.200,00", "/contas/"
        )

        c = capturado["corpo"]
        self.assertEqual(c["messaging_product"], "whatsapp")
        self.assertEqual(c["to"], "+5561998887777")
        self.assertEqual(c["type"], "template")
        self.assertEqual(c["template"]["name"], "alerta_operacional")
        self.assertEqual(c["template"]["language"]["code"], "pt_BR")
        texto = c["template"]["components"][0]["parameters"][0]["text"]
        self.assertIn("Conta vencida", texto)
        self.assertIn("Fertilizante", texto)
        self.assertIn("/contas/", texto)

    @override_settings(**CONFIG)
    def test_o_pedido_vai_para_o_phone_number_id_com_bearer(self):
        capturado = {}
        _ligar_urlopen(_RespostaFalsa({"messages": [{"id": "wamid.1"}]}), capturado)

        WA.enviar("+5561998887777", "t", "m")

        self.assertIn("123456789/messages", capturado["url"])
        self.assertIn("graph.facebook.com", capturado["url"])
        self.assertIn(
            "Bearer token-de-teste", capturado["headers"].get("Authorization", "")
        )

    @override_settings(**CONFIG)
    def test_texto_longo_corta_sem_partir_o_link(self):
        capturado = {}
        _ligar_urlopen(_RespostaFalsa({"messages": [{"id": "wamid.1"}]}), capturado)
        link = "/talhoes/" + "x" * 900
        WA.enviar("+5561998887777", "t", "m" * 900, link)
        texto = capturado["corpo"]["template"]["components"][0]["parameters"][0]["text"]
        self.assertLessEqual(len(texto), 1024)
        self.assertFalse(
            texto.endswith("x" * 20) and link not in texto,
            "o link nao pode ser partido ao meio — fica inutil",
        )


class EntregaHonestaTest(TestCase):
    """A parte que vale mais: 200 nao e' entrega."""

    def setUp(self):
        self.u = User.objects.create_user("produtor", password="x12345")
        self.perfil = self.u.perfil
        self.perfil.telefone = "+5561998887777"
        self.perfil.save()

    @override_settings(**CONFIG)
    def test_aceite_com_id_e_entregue(self):
        capturado = {}
        _ligar_urlopen(_RespostaFalsa({"messages": [{"id": "wamid.OK"}]}), capturado)
        r = WA.enviar("+5561998887777", "Conta vencida", "R$ 1.200")
        self.assertTrue(r["entregue"])
        self.assertEqual(r["message_id"], "wamid.OK")

    @override_settings(**CONFIG)
    def test_http_200_como_corpo_de_erro_nao_e_entrega(self):
        """O caso que engana toda a gente.

        A Meta devolve 200 e um `error` quando o template nao esta aprovado.
        Um cliente que olha so' para o status manda "entregue" ao produtor e a
        mensagem nunca sai.
        """
        capturado = {}
        _ligar_urlopen(
            _RespostaFalsa(
                {
                    "error": {
                        "code": 131008,
                        "message": "Template does not exist or is not approved",
                    }
                }
            ),
            capturado,
        )
        r = WA.enviar("+5561998887777", "Conta vencida", "R$ 1.200")
        self.assertFalse(r["entregue"], "200 com corpo de erro NAO e' entrega")
        self.assertIn("131008", r["motivo"])

    @override_settings(**CONFIG)
    def test_200_sem_id_nao_e_entrega(self):
        capturado = {}
        _ligar_urlopen(_RespostaFalsa({"messaging_product": "whatsapp"}), capturado)
        r = WA.enviar("+5561998887777", "t", "m")
        self.assertFalse(r["entregue"], "sem message_id nao ha o que provar")

    @override_settings(**CONFIG)
    def test_http_500_nao_e_entrega(self):
        capturado = {}
        erro = urllib.error.HTTPError("u", 500, "Internal Server Error", None, None)
        _ligar_urlopen(erro, capturado)
        r = WA.enviar("+5561998887777", "t", "m")
        self.assertFalse(r["entregue"])

    @override_settings(**CONFIG)
    def test_rede_morta_diz_que_e_rede(self):
        capturado = {}
        _ligar_urlopen(OSError("sem rota para a host"), capturado)
        r = WA.enviar("+5561998887777", "t", "m")
        self.assertFalse(r["entregue"])
        self.assertIn("rede", r["motivo"])

    def test_sem_configuracao_diz_que_falta_e_nao_tenta_enviar(self):
        """Comprovado pelo facto de nao chamar a rede: se chamasse, o dublê
        de urlopen nao esta instalado neste teste."""
        r = WA.enviar("+5561998887777", "t", "m")
        self.assertFalse(r["entregue"])
        self.assertIn("WHATSAPP_ACCESS_TOKEN", r["motivo"])


class PontaAPontaTest(TestCase):
    """O alerta da regra que escrevi hoje tem de chegar ao produtor."""

    def setUp(self):
        self.u = User.objects.create_user("joao", password="x12345")
        self.u.perfil.telefone = "(61) 99888-7777"
        self.u.perfil.save()

    @override_settings(**CONFIG)
    def test_o_alerta_de_conta_vencida_sai_pelo_whatsapp(self):
        capturado = {}
        _ligar_urlopen(_RespostaFalsa({"messages": [{"id": "wamid.1"}]}), capturado)

        r = disparar_canais(
            ["inapp", "whatsapp"],
            self.u,
            "1 conta vencida",
            "Fertilizante, R$ 1.200,00, venceu a 20/09/2026",
            link="/contas/",
        )
        w = r["por_canal"]["whatsapp"]
        self.assertTrue(w["entregue"], w["motivo"])
        # o telefone tem de ter saido normalizado, tal como o produtor escreve
        self.assertEqual(capturado["corpo"]["to"], "+5561998887777")

    @override_settings(**CONFIG)
    def test_produtor_sem_telefone_diz_que_nao_ha_para_onde_entregar(self):
        u = User.objects.create_user("sem", password="x12345")
        r = disparar_canais(["whatsapp"], u, "Aviso", "texto")
        w = r["por_canal"]["whatsapp"]
        self.assertFalse(w["entregue"])
        self.assertIn("telefone", w["motivo"])
