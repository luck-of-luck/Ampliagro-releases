"""
Testes da BUILD 3 (compliance) e da BUILD 4 (Ponte IoT).

Os invariantes, em ordem de gravidade:

BUILD 3
  1. termo sensível BLOQUEIA a criação, e a recusa vai para a trilha de
     auditoria com o termo, o lugar e a base legal;
  2. termo legítimo NÃO bloqueia (falso positivo em compliance custa produtor);
  3. a compliance roda ANTES da confirmação — pedir "crio?" e só depois recusar
     treina o produtor a confirmar sem ler.

BUILD 4
  4. o token NUNCA mais aparece depois do provisionamento;
  5. token revogado não publica, e a resposta não diz se o token existe;
  6. o evento de dispositivo passa pela MESMA validação do registro digitado;
  7. cross-tenant: nem provisionar, nem revogar, nem publicar no outro.
"""

import json

from django.contrib.auth.models import User
from django.test import Client, TestCase

from app.ia import compliance, iot
from app.ia import dinamico_intents as di
from app.ia import iot_intents as ii
from app.ia.dinamicos import ErroDinamico
from app.models import (
    DynamicApp,
    DynamicRecord,
    IAEvento,
    IotEndpoint,
    IotEvento,
)

CAMPOS = [
    {"rotulo": "Temperatura", "tipo": "DECIMAL", "obrigatorio": True},
    {"rotulo": "Umidade", "tipo": "NUMERO", "obrigatorio": False},
]


def criar(user, nome="Controle de Geladeira", campos=None):
    return di.h_criar_entidade(
        user, {"nome": nome, "campos": campos or CAMPOS, "confirm": True}, {}
    )


# =============================================================================
# BUILD 3
# =============================================================================


class ComplianceUnitTest(TestCase):
    """A blocklist é pura. Testá-la direto é o certo: é regra, não integração."""

    def test_bloqueia_termos_citados_no_enunciado(self):
        casos = [
            ("Desmatamento", [{"rotulo": "Hectares", "tipo": "NUMERO"}]),
            ("Controle", [{"rotulo": "Madeira_Ilegal", "tipo": "TEXTO"}]),
            ("Monitor", [{"rotulo": "queimada_oculta", "tipo": "BOOLEANO"}]),
        ]
        for nome, campos in casos:
            with self.subTest(nome=nome):
                r = compliance.analisar(nome, campos)
                self.assertTrue(r["bloqueado"])
                self.assertTrue(r["termo"])
                self.assertTrue(r["base_legal"], "todo bloqueio cita a base legal")

    def test_nao_bloqueia_termo_legitimo_do_agro(self):
        """FALSO POSITIVO é o custo real de uma blocklist.

        "queimada de pasto" e manejo conservacionista legalizado. "app" e o
        nome do produto — bloquear "app" bloquearia toda ferramenta.
        """
        casos = [
            ("Controle de Geladeira", [{"rotulo": "Alimento", "tipo": "TEXTO"}]),
            (
                "Registro de Queima de Pasto",
                [{"rotulo": "Area queimada", "tipo": "NUMERO"}],
            ),
            ("App Floresta", [{"rotulo": "Umidade", "tipo": "NUMERO"}]),
            ("Controle de APP e CAR", [{"rotulo": "Area desmatada", "tipo": "NUMERO"}]),
        ]
        for nome, campos in casos:
            with self.subTest(nome=nome):
                self.assertFalse(
                    compliance.analisar(nome, campos)["bloqueado"],
                    f"{nome!r} nao pode ser bloqueado — e uso legitimo",
                )

    def test_normalizacao_barra_contorno_por_digitacao(self):
        """Madeira_Ilegal = madeira ilegal = MADEIRA-ILLEGAL = MADEIRA ILEGAL."""
        for variante in (
            "madeira_ilegal",
            "madeira ilegal",
            "MADEIRA-ILEGAL",
            "Madeira  Ilegal",
        ):
            with self.subTest(variante=variante):
                self.assertTrue(
                    compliance.analisar("X", [{"rotulo": variante}])["bloqueado"]
                )

    def test_termo_relatado_e_legivel(self):
        """A recusa não pode mostrar o regex escapado ('madeira\\\\ ilegal')."""
        r = compliance.analisar("X", [{"rotulo": "Madeira_Ilegal"}])
        self.assertNotIn("\\", r["termo"])

    def test_acha_no_rotulo_e_na_chave(self):
        """Verificar só o nome é contornável: o campo é onde a ameaça mora."""
        self.assertTrue(
            compliance.analisar("X", [{"rotulo": "Desmatamento"}])["bloqueado"]
        )
        self.assertTrue(
            compliance.analisar("X", [{"rotulo": "Y", "chave": "desmatamento"}])[
                "bloqueado"
            ]
        )

    def test_diz_ONDE_disparou(self):
        """Sem dizer qual campo, o produtor renomeia o nome e esbarra no mesmo muro."""
        r = compliance.analisar(
            "Controle", [{"rotulo": "Área desmatada", "tipo": "NUMERO"}]
        )
        # "Area desmatada" (participio) NAO bloqueia — ver docstring. Testa com
        # um termo que bloqueia mesmo, pra validar o "onde".
        r2 = compliance.analisar(
            "Controle", [{"rotulo": "Desmatamento", "tipo": "NUMERO"}]
        )
        self.assertIn("rotulo", r2["onde"])
        self.assertEqual(r["bloqueado"], False)


class ComplianceIntegracaoTest(TestCase):
    """A blocklist ligada na tool de verdade."""

    def setUp(self):
        self.u = User.objects.create_user("ana", "a@x.com", "p")

    def test_criacao_bloqueada_gera_auditoria(self):
        r = criar(self.u, "Desmatamento", [{"rotulo": "Hectares", "tipo": "NUMERO"}])
        self.assertFalse(r["ok"])
        self.assertIn("BLOQUEADA", r["erro"])
        self.assertIn("9.605", r["erro"], "a recusa cita a base legal")

        evento = IAEvento.objects.filter(user=self.u, tipo="compliance").first()
        self.assertIsNotNone(evento, "a recusa PRECISA ir para a trilha de auditoria")
        self.assertEqual(evento.dados["termo"], "desmatamento")
        self.assertEqual(evento.dados["bloqueio"], "compliance_ambiental")
        self.assertIn("9.605", evento.dados["base_legal"])

    def test_bloqueio_nao_cria_ferramenta(self):
        criar(self.u, "Desmatamento", [{"rotulo": "Hectares", "tipo": "NUMERO"}])
        self.assertEqual(DynamicApp.objects.filter(user=self.u).count(), 0)

    def test_compliance_roda_ANTES_da_confirmacao(self):
        """Pedir 'crio?' e só então recusar treina o produtor a confirmar sem ler."""
        r = di.h_criar_entidade(
            self.u,
            {
                "nome": "Desmatamento",
                "campos": [{"rotulo": "Hectares", "tipo": "NUMERO"}],
            },
            {},
        )
        self.assertFalse(r["ok"])
        self.assertNotIn(
            "needs_confirm", r, "nao pode pedir confirmacao para o que sera recusado"
        )

    def test_ferramenta_legitima_passa_e_nao_gera_auditoria(self):
        r = criar(self.u)
        self.assertTrue(r["ok"], r.get("erro"))
        self.assertFalse(
            IAEvento.objects.filter(user=self.u, tipo="compliance").exists()
        )


# =============================================================================
# BUILD 4
# =============================================================================


class ProvisionamentoTest(TestCase):
    def setUp(self):
        self.u = User.objects.create_user("ana", "a@x.com", "p")
        self.slug = criar(self.u)["dados"]["slug"]

    def _provisionar(self, confirm=True, **extra):
        p = {
            "entity_slug": self.slug,
            "nome": "Valvula talhao 4",
            "campo_destino": "temperatura",
        }
        p.update(extra)
        if confirm:
            p["confirm"] = True
        return ii.h_provisionar_endpoint_iot(self.u, p, {})

    def test_provisionamento_exige_confirmacao(self):
        r = self._provisionar(confirm=False)
        self.assertTrue(r["needs_confirm"])
        self.assertEqual(IotEndpoint.objects.filter(user=self.u).count(), 0)

    def test_topico_no_formato_pedido(self):
        r = self._provisionar()
        self.assertTrue(r["ok"], r.get("erro"))
        ep = IotEndpoint.objects.get(user=self.u)
        self.assertTrue(
            ep.topico.startswith(f"ampliagro/user_{self.u.pk}/{self.slug}/")
        )
        # o token é o último segmento
        self.assertEqual(
            ep.topico.split("/")[-1], r["dados"]["escopo_tecnico"]["token"]
        )

    def test_token_guardado_so_como_hash(self):
        """O que e' verdade, e o que o hash realmente compra.

        `token_hash` e' SHA-256 do token: 64 hex, e a busca de autenticacao e'
        por ele. E' o que impede um dump do banco de virar lista de credenciais
        no caminho de autenticacao.

        E o outro lado, que este teste NOMEIA em vez de esconder: como o
        formato de topico pedido e' ".../{token}", o token aparece em claro na
        coluna `topico`, e um dump do banco le a credencial por ali tambem.
        Isso e' consequencia do formato, nao defeito — e e' exatamente por isso
        que existe revogacao, e por isso a variante `cpp_esp32_modo_seguro`
        usa topico publico com o segredo no header.

        A primeira versao deste teste afirmava "nunca em claro" e FALHOU. Ele
        foi reescrito em vez de ajustado, porque um teste que afirma o
        impossivel e' removido no primeiro "arrume" — e a garantia real (o
        hash) ficaria sem cobertura nenhuma.
        """
        r = self._provisionar()
        token = r["dados"]["escopo_tecnico"]["token"]
        ep = IotEndpoint.objects.get(user=self.u)

        # 1) o hash NAO e' o token
        self.assertNotEqual(ep.token_hash, token)
        self.assertEqual(len(ep.token_hash), 64, "sha256 em hex")
        self.assertEqual(ep.token_hash, iot.hash_token(token))

        # 2) o token nao aparece em nenhum campo, exceto o topico
        for campo in ep._meta.fields:
            if campo.name == "topico":
                continue
            valor = str(getattr(ep, campo.attname, ""))
            self.assertNotIn(token, valor, f"token em claro no campo {campo.name}")

        # 3) e o topico expoe — o preco do formato pedido
        self.assertIn(token, ep.topico)

    def test_token_aparece_uma_vez_so(self):
        """Depois do provisionamento, só o prefixo — em toda leitura."""
        self._provisionar()
        ep = IotEndpoint.objects.get(user=self.u)
        d = ep.como_descrever()
        self.assertIn("token_prefixo", d)
        self.assertNotIn("token", d)
        self.assertNotIn("token_hash", d)

        r = ii.h_consultar_endpoints_iot(self.u, {}, {})
        self.assertNotIn('token"', r["resposta"])
        self.assertIn(ep.token_prefixo, r["resposta"])

    def test_escopo_cpp_pronto_para_colar(self):
        r = self._provisionar()
        escopo = r["dados"]["escopo_tecnico"]
        cpp = escopo["cpp_esp32"]
        self.assertIn("#include <PubSubClient.h>", cpp)
        self.assertIn(escopo["token"], cpp, "o token ja vem preenchido")
        self.assertIn(escopo["broker"]["topico_publicado"], cpp)
        self.assertIn("ATENCAO", cpp, "o aviso de exposicao viaja com o artefato")

    def test_modo_seguro_nao_tem_segredo_no_topico(self):
        """A variante recomendada: topico publico, segredo no header."""
        r = self._provisionar()
        seguro = r["dados"]["escopo_tecnico"]["cpp_esp32_modo_seguro"]
        self.assertNotIn(r["dados"]["escopo_tecnico"]["token"], seguro)
        self.assertIn("MODO SEGURO", seguro)

    def test_campo_destino_precisa_existir_no_schema(self):
        r = self._provisionar(campo_destino="idade_da_vaca")
        self.assertFalse(r["ok"])
        self.assertIn("temperatura", r["erro"], "o erro lista os campos validos")

    def test_provisionar_em_tool_alheia_recusa(self):
        bob = User.objects.create_user("bob", "b@x.com", "p")
        with self.assertRaises(ErroDinamico):
            iot.provisionar(bob, self._app(), nome="X", campo_destino="temperatura")
        self.assertEqual(IotEndpoint.objects.filter(user=bob).count(), 0)

    def _app(self):
        return DynamicApp.objects.get(user=self.u, slug=self.slug)


class TokenEAutenticacaoTest(TestCase):
    def setUp(self):
        self.u = User.objects.create_user("ana", "a@x.com", "p")
        self.slug = criar(self.u)["dados"]["slug"]
        self.p = ii.h_provisionar_endpoint_iot(
            self.u,
            {
                "entity_slug": self.slug,
                "nome": "Valvula",
                "campo_destino": "temperatura",
                "confirm": True,
            },
            {},
        )
        self.token = self.p["dados"]["escopo_tecnico"]["token"]

    def test_token_aleatorio_a_cada_provisionamento(self):
        tokens = {self.token}
        for i in range(3):
            r = ii.h_provisionar_endpoint_iot(
                self.u,
                {
                    "entity_slug": self.slug,
                    "nome": f"Valvula {i}",
                    "campo_destino": "temperatura",
                    "confirm": True,
                },
                {},
            )
            tokens.add(r["dados"]["escopo_tecnico"]["token"])
        self.assertEqual(len(tokens), 4, "token nao pode se repetir")

    def test_token_ausente_ou_errado_nao_autentica(self):
        for ruim in ("", "   ", "x" * 40, self.token[:-1], self.token + "x"):
            with self.subTest(token=ruim[:12]):
                self.assertIsNone(iot.autenticar(ruim))

    def test_evento_valido_grava_registro(self):
        r = iot.receber_evento(self.token, {"valor": 22.5})
        self.assertTrue(r["ok"], r)
        reg = DynamicRecord.objects.get(pk=r["registro_id"])
        self.assertEqual(str(reg.dados["temperatura"]), "22.5")

    def test_evento_herda_a_validacao_estrita_do_registro(self):
        """O dispositivo nao tem via mais permissiva que um dedo do produtor.

        Valor de tipo errado e recusado pelo MESMO `registrar()` que a BUILD 2
        endureceu. Se este modulo tivesse o proprio INSERT, existiria um
        segundo lugar onde chave arbitraria entraria — e e sempre o segundo
        lugar que ninguem revisa.
        """
        r = iot.receber_evento(self.token, {"valor": "quente"})
        self.assertFalse(r["ok"])
        self.assertEqual(r["motivo"], "campo_invalido")
        self.assertIn("temperatura", r["erro"])
        self.assertEqual(DynamicRecord.objects.count(), 0)

    def test_evento_recusa_guarda_rastro(self):
        """Um dispositivo que publica e nao ve nada, sem rastro, e um
        dispositivo que o produtor vai culpar por 'nao funcionar'."""
        iot.receber_evento(self.token, {"valor": "quente"})
        ev = IotEvento.objects.filter(motivo="campo_invalido").first()
        self.assertIsNotNone(ev)
        self.assertIn("temperatura", ev.detalhe)

    def test_revogacao_corta_o_acesso(self):
        ep = IotEndpoint.objects.get(user=self.u)
        r = iot.receber_evento(self.token, {"valor": 22.5})
        self.assertTrue(r["ok"])

        self.assertTrue(
            ii.h_revogar_endpoint_iot(
                self.u, {"endpoint_id": ep.pk, "confirm": True}, {}
            )["ok"]
        )
        depois = iot.receber_evento(self.token, {"valor": 23.0})
        self.assertFalse(depois["ok"])
        self.assertEqual(depois["motivo"], "revogado")

    def test_revogacao_e_idempotente(self):
        ep = IotEndpoint.objects.get(user=self.u)
        ii.h_revogar_endpoint_iot(self.u, {"endpoint_id": ep.pk, "confirm": True}, {})
        r = ii.h_revogar_endpoint_iot(
            self.u, {"endpoint_id": ep.pk, "confirm": True}, {}
        )
        self.assertTrue(r["ok"])
        self.assertFalse(r["dados"]["mudou"], "revogar duas vezes nao e erro")

    def test_revogacao_exige_confirmacao(self):
        ep = IotEndpoint.objects.get(user=self.u)
        r = ii.h_revogar_endpoint_iot(self.u, {"endpoint_id": ep.pk}, {})
        self.assertTrue(r["needs_confirm"])
        self.assertEqual(IotEndpoint.objects.get(pk=ep.pk).estado, "ATIVO")

    def test_revogar_endpoint_alheio_recusa(self):
        bob = User.objects.create_user("bob", "b@x.com", "p")
        ep = IotEndpoint.objects.get(user=self.u)
        r = ii.h_revogar_endpoint_iot(bob, {"endpoint_id": ep.pk, "confirm": True}, {})
        self.assertFalse(r["ok"], "revogar endpoint alheio e DoS em cima de outro")
        self.assertEqual(IotEndpoint.objects.get(pk=ep.pk).estado, "ATIVO")

    def test_payload_grande_recusado(self):
        r = iot.receber_evento(self.token, {"valor": "x" * (iot.MAX_PAYLOAD + 100)})
        self.assertFalse(r["ok"])
        self.assertEqual(r["motivo"], "excedido")

    def test_payload_nao_objeto_recusado(self):
        for ruim in ([1, 2, 3], "texto", 42, None):
            with self.subTest(payload=repr(ruim)[:20]):
                r = iot.receber_evento(self.token, ruim)
                self.assertFalse(r["ok"])


class WebhookHttpTest(TestCase):
    """O unico endpoint PUBLICO do Amplia. A postura mora aqui."""

    def setUp(self):
        self.u = User.objects.create_user("ana", "a@x.com", "p")
        self.slug = criar(self.u)["dados"]["slug"]
        p = ii.h_provisionar_endpoint_iot(
            self.u,
            {
                "entity_slug": self.slug,
                "nome": "Valvula",
                "campo_destino": "temperatura",
                "confirm": True,
            },
            {},
        )
        self.token = p["dados"]["escopo_tecnico"]["token"]
        self.ep = IotEndpoint.objects.get(user=self.u)
        self.c = Client()

    def url(self):
        return "/api/iot/dinamico/evento/"

    def post(self, payload, token=None):
        return self.c.post(
            self.url(),
            data=json.dumps(payload),
            content_type="application/json",
            **({"HTTP_AUTHORIZATION": f"Bearer {token}"} if token else {}),
        )

    def test_sem_token_401(self):
        self.assertEqual(self.post({"valor": 1}).status_code, 401)

    def test_token_valido_201(self):
        r = self.post({"valor": 22.5}, self.token)
        self.assertEqual(r.status_code, 201)
        self.assertTrue(r.json()["ok"])

    def test_token_nao_distingue_inexistente_de_revogado(self):
        """401 que distingue 'nao existe' de 'revogado' e' oraculo de enumeracao."""
        inexistente = self.post({"valor": 1}, "token-que-nao-existe-000")
        self.ep.revogar()
        revogado = self.post({"valor": 1}, self.token)

        self.assertEqual(inexistente.status_code, revogado.status_code)
        self.assertEqual(inexistente.json(), revogado.json())

    def test_valor_fora_do_schema_422(self):
        """422 e' 'a requisicao esta certa, o valor nao e' — que e o que o
        firmware precisa. 400 diria 'arrume a requisicao'."""
        r = self.post({"valor": "quente"}, self.token)
        self.assertEqual(r.status_code, 422)
        self.assertIn("temperatura", r.json()["erro"])

    def test_json_invalido_400_sem_500(self):
        r = self.c.post(
            self.url(),
            data="nao e json",
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(r.status_code, 400)

    def test_binario_no_corpo_nao_derruba(self):
        """Payload binario levantaria UnicodeDecodeError se o body fosse
        parseado direto — e um 500 derruba o endpoint inteiro."""
        r = self.c.post(
            self.url(),
            data=b"\xff\xfe\x00\x01binario",
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertIn(r.status_code, (400, 401, 422))

    def test_get_recusado(self):
        self.assertEqual(self.c.get(self.url()).status_code, 405)
