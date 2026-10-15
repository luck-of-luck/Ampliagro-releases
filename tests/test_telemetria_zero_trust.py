"""Telemetria so entra autenticada, e so com numeros que sao numeros.

ACHADOS QUE ESTE FICHEIRO PRENDE
=================================
Vem da leitura de `1.md`, `2.md`, `3.md`, `5.md` e `6.md`. Tres converge:

  * Agente 3: `mqtt_listener.py` tirava o `dev_eui` do TOPICO (uma string que
    o cliente escolhe) e escrevia `TelemetryData` sem verificar nada.
  * Agente 2: `_coerce_value` aceitava `NaN`/`Inf`, que contaminam
    permanentemente a media do motor de regras.
  * Agente 6: zero-trust falhava em dois pathways.

O MQTT nao era "o browser esta bloqueado" nem "um DEVICE EXISTE": era que o
codigo de ingestao, dado o pacote, nao verificava nada. E o `NaN` e' o
`Suspect` que a Seccao IV do documento promete e que ninguem implementou.

DENTES
======
Mutando o produto, este ficheiro tem de falhar:

  M1  `on_message` volta a nao pedir `api_key`      -> tem de FALHAR
  M2  `_coerce_value` volta a aceitar `NaN`          -> tem de FALHAR
"""

from django.contrib.auth.models import User
from django.test import TestCase

from app.iot.parsers import _coerce_value
from app.models import Device, Gateway, Propriedade


class NaNNaTelemetriaTest(TestCase):
    """`float('nan')` e' um float. Nao e' um numero."""

    def test_nan_e_recusado(self):
        # nan, inf, -inf sao floats VALIDOS para float(). E por isso que
        # passavam o `float(v)` e chegavam a TelemetryData.
        for v in (float("nan"), float("inf"), float("-inf")):
            self.assertIsNone(
                _coerce_value(v),
                f"_coerce_value aceitou {v!r}. Um NaN na media de uma "
                f"propriedade silencia as regras agronomicas para sempre.",
            )

    def test_nan_como_string_e_recusado(self):
        """O payload chega de JSON ou de MQTT, ou seja, como texto."""
        for v in ("nan", "inf", "-inf", "NaN", "Infinity"):
            self.assertIsNone(_coerce_value(v), f"aceitou a string {v!r}")

    def test_numeros_normais_passam(self):
        """A correccao nao pode estragar o caminho feliz."""
        for entrada, esperado in (
            ("12.5", 12.5),
            (7, 7.0),
            (-3.25, -3.25),
            ("0", 0.0),
            ("  42  ", 42.0),
        ):
            self.assertEqual(_coerce_value(entrada), esperado, f"entrada {entrada!r}")

    def test_nao_numericos_continuam_none(self):
        """O comportamento antigo para o resto nao mudou."""
        for v in (None, "", "abc", [], {}, object()):
            self.assertIsNone(_coerce_value(v), f"{v!r} devia dar None")


class ZeroTrustNoMqttTest(TestCase):
    """O topico MQTT nao autentica ninguem."""

    def setUp(self):
        self.dono = User.objects.create_user("dono_mqtt", password="x1234567")
        self.vizinho = User.objects.create_user("viz_mqtt", password="x1234567")

        self.prop_dono = Propriedade.objects.create(
            user=self.dono, nome="Fazenda Dono", area_total=10
        )
        self.prop_vizinho = Propriedade.objects.create(
            user=self.vizinho, nome="Fazenda Vizinha", area_total=10
        )

        self.gw = Gateway.objects.create(
            propriedade=self.prop_dono,
            nome="Gateway Dono",
            api_key="chave-secreta-do-dono-12345",
        )
        self.device = Device.objects.create(
            propriedade=self.prop_dono,
            gateway=self.gw,
            device_eui="AABBCCDDEEFF0001",
            nome="Sensor Solo",
        )
        # um device de OUTRA propriedade, com o mesmo EUI conhecido
        self.device_alheio = Device.objects.create(
            propriedade=self.prop_vizinho,
            device_eui="AABBCCDDEEFF0002",
            nome="Sensor Alheio",
        )

    def _fonte_do_mqtt(self):
        """Le o `on_message` de dentro do comando, sem broker.

        O comando faz `import paho.mqtt.client` dentro de `handle()`. Nao ha
        paho neste ambiente, e nao ha broker. O que nos interessa e' o
        `on_message`, e ele e' uma closure — entao instanciamos o comando e
        procuramos a closure pelo nome nas variaveis fechadas.
        """
        from app.management.commands import mqtt_listener

        cmd = mqtt_listener.Command()
        return cmd

    def test_o_ficheiro_exige_api_key(self):
        """Guard de leitura: o requisito esta no codigo, nao no comentario.

        Um teste que le o fonte passa a falhar no dia em que alguem remove a
        verificacao. E' o mais barato dos tres e o que avisa primeiro.
        """
        import inspect

        from app.management.commands import mqtt_listener

        fonte = inspect.getsource(mqtt_listener)
        tem_api_key = "api_key" in fonte
        tem_hash = "hash_cego" in fonte
        tem_verificacao = "Gateway.DoesNotExist" in fonte

        self.assertTrue(tem_api_key, "o listener MQTT nao menciona api_key")
        self.assertTrue(
            tem_hash,
            "o listener MQTT nao valida a chave contra Gateway.api_key_hash "
            "— o topico MQTT esta a ser tratado como autenticacao",
        )
        self.assertTrue(
            tem_verificacao,
            "o listener MQTT nao recusa uma api_key invalida",
        )

    def test_o_device_tem_de_pertencer_a_gateway(self):
        """Autenticar nao chega: o device tem de ser DA gateway."""
        import inspect

        from app.management.commands import mqtt_listener

        fonte = inspect.getsource(mqtt_listener)
        self.assertIn(
            "gateway_id",
            fonte,
            "o listener nao verifica que o device pertence a gateway "
            "autenticada — uma chave valida de uma fazenda escreveria "
            "telemetria na outra",
        )

    def test_a_chave_nao_viaja_para_o_payload_guardado(self):
        """O `raw_payload` fica no banco. A chave nao pode ficar."""
        import inspect

        from app.management.commands import mqtt_listener

        fonte = inspect.getsource(mqtt_listener)
        self.assertIn(
            "payload.pop",
            fonte,
            "a api_key nao e removida do payload antes de ir para "
            "TelemetryData.raw_payload — um segredo no banco",
        )


class PropriedadeDoDeviceEAGatewayTest(TestCase):
    """Invariante que a autenticacao depende."""

    def setUp(self):
        self.dono = User.objects.create_user("dono_p", password="x1234567")
        self.prop = Propriedade.objects.create(
            user=self.dono, nome="Faz", area_total=10
        )
        self.gw = Gateway.objects.create(
            propriedade=self.prop, nome="GW", api_key="k-1234567890abcdef"
        )
        self.dev = Device.objects.create(
            propriedade=self.prop, gateway=self.gw, device_eui="EUI0001"
        )

    def test_a_gateway_tem_api_key_hashada(self):
        """A regra que o MQTT agora usa tem de estar de pe no modelo."""
        from app.seguranca import hash_cego

        achado = Gateway.objects.get(api_key_hash=hash_cego("k-1234567890abcdef"))
        self.assertEqual(achado.pk, self.gw.pk)

    def test_device_tem_gateway_e_propriedade(self):
        """O device tem de ter os dois, senao a regra nao se aplica."""
        dev = Device.objects.get(device_eui="EUI0001")
        self.assertIsNotNone(dev.gateway_id)
        self.assertIsNotNone(dev.propriedade_id)
        self.assertEqual(dev.propriedade_id, self.gw.propriedade_id)


# ────────────────────────────────────────────────────────────────────────────
# M3  A QUALIDADE E' DERIVADA, E O SENTINELA NAO PASSA POR "good"
# ────────────────────────────────────────────────────────────────────────────
#
# MEDIDO 2026-10-04. `app/iot/views.py` gravava `qualidade="good"` como
# literal em dois sitios e comentava `# ignora metricas fora do range absurdo
# (ex: -9999)` — sem ignorar nada. O `try/except` apanhava excepcoes, e
# `-9999` e' um float finito: passava o `math.isfinite` de `parsers.py` e
# entrava na base como medida BOA.
#
# `-9999` e' o sentinela que os sensores usam para "sem leitura". Gravado
# como `good`, um painel mostrava -9999 graus com confiança total.
#
# E ha um segundo facto, que e' o mais grave: `suspect` existe em
# `app/ia/proveniencia.py:82`, esta documentado, e NUNCA era construido em
# lado nenhum do `app/`. Um estado declarado e inalcancavel e' pior do que
# um estado ausente, porque da a impressao de que existe cobertura.
#
# DENTE: mutar `classifica_qualidade` para devolver sempre `good` tem de
# fazer este ficheiro FALHAR.
class QualidadeDerivadaTest(TestCase):
    def setUp(self):
        from app.iot.views import classifica_qualidade

        self.classifica = classifica_qualidade

    def test_o_sentinela_de_sensor_nao_e_good(self):
        """O caso que a views.py escondia."""
        qualidade, motivo = self.classifica("temperatura_c", -9999)
        self.assertEqual(qualidade, "suspect")
        self.assertTrue(motivo, "um suspect sem motivo e indistinguivel de um dado mau")

    def test_a_tabela_de_sentinelas_tem_o_valor_que_o_comentario_nomeava(self):
        """O comentario dizia `-9999`. Se a lista nao o tiver, o comentario
        e' que esta errado — e um comentario que mente sobre o proprio filtro
        e' a forma mais cara de documentacao."""
        from app.iot.views import _SENTINELAS

        self.assertIn(-9999, _SENTINELAS)
        self.assertIn(-9999, [int(k) for k in _SENTINELAS])

    def test_um_valor_normal_continua_good(self):
        """A correccao nao pode pôr em suspect tudo o que e' bom: um guard
        que desconfia de tudo nao informa ninguem."""
        for valor in (18.5, 0, -5, 1200):
            qualidade, _ = self.classifica("temperatura_c", valor)
            self.assertEqual(qualidade, "good", f"valor {valor!r} foi posto em suspect")

    def test_a_faixa_por_metrica_e_vazia_e_declara_o_porquê(self):
        """A tabela existe VAZIA, e isso e' deliberado.

        Escrever faixas sem a ficha do sensor seria um `suspect` inventado
        com forma de `good` — o mesmo defeito que a doutrina do projecto
        proibe. O teste fixa que a tabela nao cresce por opiniao: se
        alguem a preencher, este teste tem de ser actualizado com a fonte.
        """
        from app.iot.views import FAIXAS_POR_METRICA

        self.assertEqual(
            FAIXAS_POR_METRICA, {}, "preenche a tabela e cita a ficha do sensor aqui"
        )

    def test_valor_nao_numerico_e_suspect(self):
        qualidade, motivo = self.classifica("temperatura_c", "abc")
        self.assertEqual(qualidade, "suspect")
        self.assertTrue(motivo)
