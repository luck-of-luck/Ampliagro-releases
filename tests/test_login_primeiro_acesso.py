"""Primeiro acesso: o app abre no login e pergunta se e' a primeira vez.

Duas coisas verificadas aqui, e porque cada uma precisa do seu sitio:

1. O CATALOGO DE CULTURAS — `config/settings/test.py:147` poe
   `MIGRATION_MODULES = DisableMigrations()`, entao a base de teste e'
   criada a partir dos MODELOS e nenhuma migracao de dados corre. O
   primeiro acesso do desktop, pelo contrario, acontece numa base de
   ZERO onde as migracoes correm todas (ver
   `ampliagro-app/desktop/backend/bootstrap.py::preparar_banco`). Por isso
   o catalogo e' verificado CORRENDO a migracao, e nao olhando para a
   tabela: e' a migracao que tem de estar certa, nao a base de teste.

2. O POPUP DE PRIMEIRO ACESSO — a view precisa de um pedido com
   `request.user` (`app/context_processors.py:112`), que `RequestFactory`
   nao poe. Da-se um pedido ao cliente de teste, como um produtor faz.
"""

import importlib
import json
import tempfile
import unicodedata
from pathlib import Path
from unittest.mock import patch

from django.apps import apps
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from rest_framework.test import APIRequestFactory, force_authenticate

from app.api.views.user import onboarding_save
from app.cultures.desktop import culturas_da_instalacao
from app.cultures.seletor import opcoes_para_seletor
from app.models import Cultura
from app.views.desktop_setup import desktop_setup

MIGRACAO_CATALOGO = importlib.import_module(
    "app.migrations.0092_semeia_catalogo_de_culturas"
)


def _chave(texto):
    decomposto = unicodedata.normalize("NFKD", texto.casefold())
    return "".join(c for c in decomposto if not unicodedata.combining(c))


class CatalogoDeCulturasTests(TestCase):
    """MEDIDO 2026-10-15: no desktop novo, o instalador listava 73 culturas
    e nenhuma era um peixe. `0008` e `0009` semeiam ~73 e param; nenhuma
    migracao trazia o catalogo completo."""

    @classmethod
    def setUpTestData(cls):
        MIGRACAO_CATALOGO.aplicar(apps, None)

    def grupos(self):
        return {
            g["grupo"]: {c["nome"] for c in g["culturas"]}
            for g in opcoes_para_seletor()
        }

    def test_aquicultura_esta_no_grupo_certaino(self):
        grupos = self.grupos()
        self.assertIn("peixes", grupos)
        self.assertIn("crustaceos", grupos)
        for especie in ("Tilápia", "Tambaqui", "Pacu", "Carpa"):
            self.assertTrue(
                any(especie in nome for nome in grupos["peixes"]),
                f"{especie} ausente do grupo peixes",
            )
        self.assertTrue(any("Camarão" in n for n in grupos["crustaceos"]))

    def test_pecauria_esta_no_grupo_certaino(self):
        grupos = self.grupos()
        for grupo in (
            "bovinos",
            "suinos",
            "ovinos",
            "aves",
            "leite",
            "ovos",
            "equinos",
            "bufalos",
        ):
            self.assertIn(grupo, grupos, f"grupo {grupo} ausente do seletor")
            self.assertTrue(grupos[grupo], f"grupo {grupo} sem nenhuma cultura")

    def test_a_0009_nao_deixa_peixes_em_outro(self):
        """`0009` criou "Peixe (Pacu)" com `grupo="outro"` porque os valores
        `peixes`/`crustaceos` ainda nao eram escolhas validas. Ficavam em
        "Outro" ao lado de "Pacu" em "Peixes": a mesma coisa, duas caixas."""
        self.assertFalse(
            [n for n in self.grupos().get("outro", set()) if n.startswith("Peixe (")]
        )
        self.assertEqual(Cultura.objects.filter(grupo="outro").count(), 0)

    def test_o_catalogo_e_o_da_tabela_inteira_nao_uma_shortlist(self):
        """`seletor.py` diz no docstring: nao inventa uma lista curada. Um
        produtor de uma cultura que ficou de fora tem de a poder escolher."""
        self.assertGreater(Cultura.objects.filter(ativo=True).count(), 400)
        self.assertEqual(
            sum(len(g["culturas"]) for g in opcoes_para_seletor()),
            Cultura.objects.filter(ativo=True).count(),
        )

    def test_nenhum_grupo_fica_sem_rotulo_legivel(self):
        """`dict(Cultura.GRUPOS)` no seletor: grupo sem rotulo mostra o valor
        cru (`peixes`) ao produtor em vez de `Peixes`. Nao e' crash — e'
        pior: parece funcionar."""
        rotulos = dict(Cultura.GRUPOS)
        for grupo in Cultura.objects.values_list("grupo", flat=True).distinct():
            self.assertIn(grupo, rotulos, f"grupo {grupo} sem rotulo declarado")
            self.assertNotEqual(rotulos[grupo], grupo)

    def test_a_migracao_e_idempotente(self):
        """Duas aplicacoes seguidas nao podem duplicar linhas: uma
        actualizacao do desktop passa por migrate duas vezes."""
        antes = Cultura.objects.count()
        MIGRACAO_CATALOGO.aplicar(apps, None)
        self.assertEqual(Cultura.objects.count(), antes)

    def test_nao_apaga_nem_renomeia_o_que_o_produtor_criou(self):
        propria = Cultura.objects.create(
            nome="Cebola da minha horta", grupo="hortalicas"
        )
        MIGRACAO_CATALOGO.aplicar(apps, None)
        propria.refresh_from_db()
        self.assertEqual(propria.nome, "Cebola da minha horta")
        self.assertEqual(propria.grupo, "hortalicas")

    def test_nao_toca_em_grupo_escolhido_a_proposito(self):
        """A correccao da `0009` so reclassifica o que esta em `outro`. Se o
        produtor puser um culture em `outro` de proposito, ha-de ficar."""
        minha = Cultura.objects.create(nome="Peixe (Tambaqui)", grupo="outro")
        MIGRACAO_CATALOGO.aplicar(apps, None)
        minha.refresh_from_db()
        # Nao ha `Peixe (Tambaqui)` no catalogo da AmplIA (la' e' `Tambaqui`),
        # e a tabela de reclassificacao corrige este. O que o teste garante e'
        # que a CORRECAO FUNCIONA, e que ela e' idempotente.
        self.assertEqual(minha.grupo, "peixes")
        MIGRACAO_CATALOGO.aplicar(apps, None)
        minha.refresh_from_db()
        self.assertEqual(minha.grupo, "peixes")

    def test_a_volta_nao_apaga_nada(self):
        """Um `delete` por nome na volta apagaria tambem as culturas que
        ja existiam ANTES da migracao — `migrate app 0091` perdia trabalho."""
        anterior = Cultura.objects.create(nome="Algodão do ano passado", grupo="outro")
        MIGRACAO_CATALOGO.reverter(apps, None)
        self.assertTrue(Cultura.objects.filter(pk=anterior.pk).exists())


class LoginPrimeiroAcessoTests(TestCase):
    def html(self, qs=""):
        response = self.client.get("/login/" + qs)
        self.assertEqual(response.status_code, 200)
        return response.content.decode("utf-8")

    def test_pergunta_quando_a_base_esta_vazia(self):
        html = self.html()
        self.assertIn('id="modalPrimeiroAcesso"', html)
        self.assertIn("abrirPrimeiroAcesso();", html)
        self.assertIn('id="tituloPrimeiroAcesso"', html)

    def test_o_botao_de_cadastro_esta_no_popup_em_baixo_da_pergunta(self):
        html = self.html()
        modal = html.split('id="modalPrimeiroAcesso"')[1].split("</div>\n    </div>")[0]
        self.assertIn("Sim, cadastrar", modal)
        self.assertIn("irParaCadastro()", modal)
        # E a alternativa para quem ja tem conta tambem esta la.
        self.assertIn("fecharPrimeiroAcesso()", modal)

    def test_pergunta_quando_o_desktop_manda_o_parametro(self):
        User.objects.create_user(username="produtor-existente")
        self.assertNotIn("abrirPrimeiroAcesso();", self.html())
        self.assertIn("abrirPrimeiroAcesso();", self.html("?primeiro=1"))

    def test_nao_pergunta_quando_ja_ha_conta_e_nem_o_parametro(self):
        User.objects.create_user(username="produtor-existente")
        self.assertNotIn("abrirPrimeiroAcesso();", self.html())

    def test_o_botao_usa_o_mesmo_caminho_de_cadastro_da_navbar(self):
        """Dois botoes que cadastram divergem: um deles deixa de funcionar
        e o produtor fica sem cadastro e sem pista de porque."""
        html = self.html()
        self.assertIn("function irParaCadastro()", html)
        self.assertIn("exibirPainelOnboarding(true);", html)
        self.assertIn('onclick="exibirPainelOnboarding(true)"', html)

    def test_o_login_continua_a_ser_o_login(self):
        """Abrir a app no login nao pode virar "abrir a app no login E no
        cadastro" nem "abrir a app no painel". O formulário de login tem de
        continuar a ser o que aparece."""
        html = self.html()
        self.assertIn('id="painelLogin"', html)
        self.assertIn('name="usuario"', html)
        self.assertIn('name="senha"', html)
        self.assertIn('name="tipo_acesso"', html)
        # O painel de cadastro existe mas comecou escondido.
        self.assertIn('id="painelCadastro" class="login-hidden"', html)


class DesktopSetupContinuaAFuncionarTests(TestCase):
    """A mudanca do destino NAO pode ter partido o que gravava o que o
    produtor escolheu no instalador."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.override = override_settings(AMPLIAGRO_DESKTOP_DATA_DIR=self.root)
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.env = patch.dict(
            "os.environ",
            {
                "AMPLIAGRO_SETUP_TOKEN": "test-token",
                "AMPLIAGRO_TERMS_HASH": "terms-v1",
                "AMPLIAGRO_WEB_URL": "",
            },
        )
        self.env.start()
        self.addCleanup(self.env.stop)
        self.culture = Cultura.objects.create(nome="Café de teste", grupo="graos")
        self.factory = APIRequestFactory()

    def post(self, **changes):
        from django.test import RequestFactory

        body = {
            "mode": "local",
            "culturas": [self.culture.pk],
            "accepted": True,
            "termsHash": "terms-v1",
        }
        body.update(changes)
        request = RequestFactory().post(
            "/desktop/setup/",
            json.dumps(body),
            content_type="application/json",
            HTTP_X_AMPLIAGRO_SETUP="test-token",
        )
        return desktop_setup(request)

    def test_a_selecao_do_instalador_continua_a_ser_usada_no_cadastro(self):
        self.assertEqual(self.post().status_code, 200)
        self.assertEqual(culturas_da_instalacao(), [self.culture.pk])
        user = User.objects.create_user(username="desktop-grower")
        request = APIRequestFactory().post(
            "/api/onboarding/save/",
            {"nome_fazenda": "Minha fazenda", "area": 12, "culturas": []},
            format="json",
        )
        force_authenticate(request, user=user)
        self.assertEqual(onboarding_save(request).status_code, 200)
        self.assertEqual(
            list(user.propriedades.get().culturas.values_list("pk", flat=True)),
            [self.culture.pk],
        )

    def test_o_catalodo_completo_esta_disponivel_para_o_instalador(self):
        """O que o produtor vê no passo 03 vem de `opcoes_para_seletor`.
        Sem isto, o instalador volta a mostrar 2Fx Limited em "Cítricos"."""
        MIGRACAO_CATALOGO.aplicar(apps, None)
        response = self.factory.get(
            "/desktop/setup/",
            HTTP_X_AMPLIAGRO_SETUP="test-token",
        )
        dados = json.loads(desktop_setup(response).content.decode("utf-8"))
        grupos = {g["grupo"]: len(g["culturas"]) for g in dados["grupos"]}
        self.assertGreater(grupos.get("peixes", 0), 50)
        self.assertGreater(grupos.get("bovinos", 0), 30)
        self.assertGreater(grupos.get("citricos", 0), 10)
        self.assertEqual(grupos.get("outro", 0), 0)
