"""Testes de autenticação — login, cadastro, recuperação de senha e demo.

Por que este arquivo existe
---------------------------
Antes deste arquivo, o endpoint `/login/` não tinha NENHUM teste: uma busca por
`client.post("/login/")` em todo o repositório não retornava nada. Foi por isso
que dois defeitos de produção sobreviveram sem ninguém perceber:

1. **Cadastro quebrado (500).** `login(request, user)` é chamado com um `User`
   recem-criado por `create_user`, que não tem o atributo `backend`. Com três
   backends configurados (axes + ModelBackend + allauth —
   `config/settings/base.py:98`), o Django levanta
   `ValueError: You have multiple authentication backends...`. O usuário era
   gravado no banco e a tela recebia 500 — ou seja, ninguém conseguia se
   cadastrar.

2. **Recuperação de senha com 500 e sessão órfã.** Depois de `login()`, a view
   fazia `del request.session["recovery_code"]`. O `login()` rotaciona a
   session key e descarta o restante da sessão, então o `del` estourava
   `KeyError`. Como a falha vinha DEPOIS do `login()`, o usuário ficava
   autenticado sem nunca ver a tela de sucesso.

Os testes abaixo travam o comportamento correto de cada endpoint. Execute com:

    .\\.venv\\Scripts\\python.exe -m pytest app/views/tests_auth.py -v
"""

import os
from datetime import timedelta
from unittest import mock

from django.contrib.auth.models import User
from django.core import mail
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from app.hierarquia import pode_acessar, pode_ver_financeiro
from app.models import Funcionario, PerfilUsuario, Propriedade
from app.views.auth import RECOVERY_MAX_TENTATIVAS, RECOVERY_TTL_SEGUNDOS

SENHA_FORTE = "Cafe#Agro2026"


def _produtor(username="jose", **kw):
    """Usuário produtor com uma propriedade — o estado normal do sistema."""
    user = User.objects.create_user(
        username=username, password=SENHA_FORTE, email=f"{username}@faz.com", **kw
    )
    # O sinal post_save já cria o perfil; `update_or_create` só confirma o papel.
    PerfilUsuario.objects.update_or_create(
        user=user, defaults={"tipo_usuario": "produtor"}
    )
    Propriedade.objects.create(
        user=user, nome="Faz Boa Vista", area_total=100, uf="MT", cidade="Primavera"
    )
    return user


class CadastroTest(TestCase):
    """Regressão do `ValueError` de múltiplos backends."""

    def test_cadastro_cria_usuario_e_autentica(self):
        c = Client()
        r = c.post(
            reverse("login"),
            {
                "acao": "cadastro",
                "usuario": "novo",
                "senha": SENHA_FORTE,
                "email": "novo@faz.com",
            },
        )
        self.assertEqual(
            r.status_code, 302, "cadastro deve redirecionar, não estourar 500"
        )
        self.assertRedirects(r, reverse("onboarding"), fetch_redirect_response=False)

        user = User.objects.get(username="novo")
        self.assertTrue(user.check_password(SENHA_FORTE))
        self.assertTrue(user.perfil, "perfil de produtor deve ser criado junto")
        # A sessão precisa existir: era exatamente isso que o 500 impedia.
        self.assertEqual(int(c.session["_auth_user_id"]), user.pk)

    def test_cadastro_nao_deixa_usuario_orfao_quando_falha(self):
        """Se o passo de login falhar, a transação reverte o usuário criado.

        Regressão do defeito original: `create_user` gravava a conta e só depois
        o `login()` estourava — o produtor ficava com um usuário órfão que nunca
        conseguia entrar.
        """
        import app.views.auth as authmod

        with (
            mock.patch.object(
                authmod, "login", side_effect=RuntimeError("falha no login")
            ),
            self.assertRaises(RuntimeError),
        ):
            Client().post(
                reverse("login"),
                {
                    "acao": "cadastro",
                    "usuario": "orfao",
                    "senha": SENHA_FORTE,
                    "email": "orfao@faz.com",
                },
            )
        self.assertFalse(
            User.objects.filter(username="orfao").exists(),
            "cadastro que falhou não pode deixar usuário órfão no banco",
        )

    def test_senha_fraca_rejeitada(self):
        """AUTH_PASSWORD_VALIDATORS existe no settings mas `create_user` não
        roda os validadores — o cadastro aceitava senha '1'."""
        for fraca in ["1", "123", "password", "12345678"]:
            with self.subTest(senha=fraca):
                r = Client().post(
                    reverse("login"),
                    {
                        "acao": "cadastro",
                        "usuario": "x",
                        "senha": fraca,
                        "email": "x@x.com",
                    },
                )
                self.assertEqual(r.status_code, 200, "deve reexibir o formulário")
                self.assertIn("senha", r.context["form_cadastro"].errors)
                self.assertFalse(User.objects.filter(username="x").exists())

    def test_usuario_duplicado_nao_cria_segundo(self):
        _produtor("jose")
        antes = User.objects.count()
        r = Client().post(
            reverse("login"),
            {
                "acao": "cadastro",
                "usuario": "JOSE",  # case-insensitive
                "senha": SENHA_FORTE,
                "email": "outro@faz.com",
            },
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(User.objects.count(), antes)


class LoginProdutorTest(TestCase):
    def setUp(self):
        self.user = _produtor("jose")

    def test_login_valido(self):
        c = Client()
        r = c.post(
            reverse("login"),
            {
                "acao": "login",
                "tipo_acesso": "produtor",
                "usuario": "jose",
                "senha": SENHA_FORTE,
            },
        )
        self.assertEqual(r.status_code, 302)
        self.assertEqual(int(c.session["_auth_user_id"]), self.user.pk)

    def test_senha_errada_nao_autentica(self):
        c = Client()
        r = c.post(
            reverse("login"),
            {
                "acao": "login",
                "tipo_acesso": "produtor",
                "usuario": "jose",
                "senha": "errada",
            },
        )
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("_auth_user_id", c.session)

    def test_next_externo_bloqueado(self):
        """`startswith('/')` deixava passar `/\\evil.com`; o browser normaliza
        `\\` para `/` e o usuário é levado ao site atacante."""
        for malicioso in [
            "https://evil.com",
            "//evil.com",
            "/\\evil.com",
            "///evil.com",
            "http://evil.com/x",
        ]:
            with self.subTest(next=malicioso):
                c = Client()
                r = c.post(
                    reverse("login"),
                    {
                        "acao": "login",
                        "tipo_acesso": "produtor",
                        "usuario": "jose",
                        "senha": SENHA_FORTE,
                        "next": malicioso,
                    },
                )
                destino = r.get("Location", "")
                self.assertNotIn("evil.com", destino, f"open redirect em {malicioso!r}")
                self.assertTrue(destino.startswith("/"), destino)

    def test_next_interno_preservado(self):
        c = Client()
        r = c.post(
            reverse("login"),
            {
                "acao": "login",
                "tipo_acesso": "produtor",
                "usuario": "jose",
                "senha": SENHA_FORTE,
                "next": "/financeiro/dre/",
            },
        )
        self.assertEqual(r.get("Location"), "/financeiro/dre/")

    def test_login_ignora_email_decorativo(self):
        """O formulário antigo mandava `email_produtor`, que o backend nunca
        validava. O campo foi removido; o login não deve depender dele."""
        c = Client()
        r = c.post(
            reverse("login"),
            {
                "acao": "login",
                "tipo_acesso": "produtor",
                "usuario": "jose",
                "senha": SENHA_FORTE,
                "email_produtor": "falso@inexistente.com",
            },
        )
        self.assertEqual(r.status_code, 302)


class LoginServidorTest(TestCase):
    def setUp(self):
        self.prod = _produtor("jose")
        self.serv = User.objects.create_user(
            username="mecanico.demo", password=SENHA_FORTE, email="mec@faz.com"
        )
        # O sinal post_save já criou o perfil como produtor; aqui se defines
        # o papel de servidor com a área e a propriedade vinculada.
        PerfilUsuario.objects.update_or_create(
            user=self.serv,
            defaults={
                "tipo_usuario": "servidor",
                "area_servidor": "MECANICA",
                "propriedade_vinculada": self.prod.propriedades.first(),
            },
        )

    def test_login_servidor_com_fazenda_correta(self):
        c = Client()
        r = c.post(
            reverse("login"),
            {
                "acao": "login",
                "tipo_acesso": "servidor",
                "nome_fazenda": "Faz Boa Vista",
                "usuario": "mecanico.demo",
                "senha": SENHA_FORTE,
            },
        )
        self.assertEqual(r.status_code, 302)
        self.assertEqual(int(c.session["_auth_user_id"]), self.serv.pk)
        self.assertEqual(r.get("Location"), "/servidor/")

    def test_fazenda_errada_nao_autentica(self):
        c = Client()
        r = c.post(
            reverse("login"),
            {
                "acao": "login",
                "tipo_acesso": "servidor",
                "nome_fazenda": "Fazenda de Outro",
                "usuario": "mecanico.demo",
                "senha": SENHA_FORTE,
            },
        )
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("_auth_user_id", c.session)

    def test_servidor_desativado_bloqueado(self):
        self.serv.perfil.ativo_servidor = False
        self.serv.perfil.save()
        c = Client()
        r = c.post(
            reverse("login"),
            {
                "acao": "login",
                "tipo_acesso": "servidor",
                "nome_fazenda": "Faz Boa Vista",
                "usuario": "mecanico.demo",
                "senha": SENHA_FORTE,
            },
        )
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("_auth_user_id", c.session)

    def test_produtor_nao_entra_painel_de_servidor(self):
        """Um produtor não é servidor: logar como 'servidor' exige perfil de
        servidor, senão ele cairia no painel restrito."""
        c = Client()
        r = c.post(
            reverse("login"),
            {
                "acao": "login",
                "tipo_acesso": "servidor",
                "nome_fazenda": "Faz Boa Vista",
                "usuario": "jose",
                "senha": SENHA_FORTE,
            },
        )
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("_auth_user_id", c.session)


class RecuperarSenhaTest(TestCase):
    """Regressão do KeyError e do código devolvido no corpo HTTP."""

    def setUp(self):
        self.user = _produtor("jose")
        self.dados = {
            "acao": "recuperar_senha",
            "fazenda": "Faz Boa Vista",
            "usuario": "jose",
            "email": "jose@faz.com",
        }

    def _solicitar(self, client=None, **over):
        c = client or Client()
        dados = {**self.dados, **over}
        return c, c.post(reverse("login"), dados)

    def test_fluxo_completo_autentica(self):
        c, r = self._solicitar()
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["ok"])
        codigo = c.session["recovery_code"]
        r2 = c.post(reverse("login"), {"acao": "verificar_codigo", "codigo": codigo})
        self.assertEqual(r2.status_code, 200)
        self.assertTrue(r2.json()["ok"])
        self.assertEqual(int(c.session["_auth_user_id"]), self.user.pk)

    def test_funciona_com_sessao_previa(self):
        """Regressão do KeyError: `del session['recovery_code']` depois do
        `login()` estourava 500 sempre que já havia sessão (usuário logado,
        troca de conta, ou logo após /demo/)."""
        outro = User.objects.create_user(username="outro", password=SENHA_FORTE)
        c = Client()
        c.force_login(outro)
        _, r = self._solicitar(c)
        self.assertEqual(r.status_code, 200)
        codigo = c.session["recovery_code"]
        r2 = c.post(reverse("login"), {"acao": "verificar_codigo", "codigo": codigo})
        self.assertEqual(
            r2.status_code, 200, "não pode dar 500 com sessão preexistente"
        )
        self.assertTrue(r2.json()["ok"])
        self.assertEqual(int(c.session["_auth_user_id"]), self.user.pk)

    @override_settings(DEBUG=False)
    def test_codigo_nao_volta_no_http_em_producao(self):
        """O código é uma credencial. Devolvê-lo no corpo HTTP transformava
        'recuperar senha' em 'entrar sem senha'."""
        c = Client()
        r = c.post(reverse("login"), self.dados)
        corpo = r.json()
        self.assertTrue(corpo["ok"])
        self.assertNotIn(
            "code", corpo, "código não pode viajar na resposta em produção"
        )

    @override_settings(DEBUG=True)
    def test_debug_sozinho_nao_expoe_o_codigo(self):
        """DEBUG deixou de ser o portão, e este teste é a razão.

        `config/settings/dev.py` faz
            DEBUG = os.environ.get("DEBUG", "True")
        — em dev o default é LIGADO. Um portão cuja condição default é
        "mostrar" não é um portão: é uma constante de configuração que
        alguém esquece que existe, e uma máquina de dev alcançável pela rede
        entrega o código de recuperação de qualquer conta.

        O código agora só sai com `AMPLIA_DEV_MOSTRAR_CODIGO=1`, que ninguém
        liga por acidente. Este teste falla se alguém voltar a `settings.DEBUG`.
        """
        c = Client()
        r = c.post(reverse("login"), self.dados)
        self.assertNotIn(
            "code",
            r.json(),
            "DEBUG não pode expor o código de recuperação: "
            "o default de dev é DEBUG=True e isso é alcançável pela rede",
        )

    @override_settings(DEBUG=True)
    def test_codigo_sai_so_com_a_env_var_explicita(self):
        """O lado positivo do portão: com a variável ligada, o código sai.

        Existe para provar que o teste anterior não passa porque o caminho
        morreu — passa porque o portão fechou.
        """
        with mock.patch.dict(os.environ, {"AMPLIA_DEV_MOSTRAR_CODIGO": "1"}):
            c = Client()
            r = c.post(reverse("login"), self.dados)
        self.assertIn(
            "code",
            r.json(),
            "com AMPLIA_DEV_MOSTRAR_CODIGO=1 o código tem de aparecer "
            "(fluxo de desenvolvimento local)",
        )

    @override_settings(DEBUG=True)
    def test_env_var_ausente_nao_e_o_default(self):
        """O default tem de ser NÃO mostrar.

        Um teste que passa porque a variável está desligada não prova nada
        sobre o default — prova que alguém a desligou. Aqui verifica-se a
        ausência explícita.
        """
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("AMPLIA_DEV_MOSTRAR_CODIGO", None)
            c = Client()
            r = c.post(reverse("login"), self.dados)
        self.assertNotIn("code", r.json())

    def test_codigo_expirado_recusado(self):
        """Sem TTL, um código emitido de manhã valia a noite inteira — a sessão
        vive 24h (SESSION_COOKIE_AGE)."""
        c, _ = self._solicitar()
        codigo = c.session["recovery_code"]
        # Avança o relógio do servidor além da janela de validade.
        futuro = timezone.now() + timedelta(seconds=RECOVERY_TTL_SEGUNDOS + 60)
        with mock.patch("app.views.auth.timezone.now", return_value=futuro):
            r = c.post(reverse("login"), {"acao": "verificar_codigo", "codigo": codigo})
        self.assertFalse(r.json()["ok"], "código expirado precisa ser recusado")
        self.assertNotIn("_auth_user_id", c.session, "código expirado não autentica")

    def test_teto_de_tentativas_bloqueia_forca_bruta(self):
        c, _ = self._solicitar()
        codigo = c.session["recovery_code"]
        for _ in range(RECOVERY_MAX_TENTATIVAS):
            r = c.post(
                reverse("login"), {"acao": "verificar_codigo", "codigo": "AAAAAA"}
            )
            self.assertFalse(r.json()["ok"])
        # código correto agora é recusado: o estado foi limpo
        r = c.post(reverse("login"), {"acao": "verificar_codigo", "codigo": codigo})
        self.assertFalse(r.json()["ok"])
        self.assertNotIn("_auth_user_id", c.session)

    def test_resposta_generica_nao_enumera_usuarios(self):
        """Usuário inexistente e fazenda errada devem responder igual ao
        sucesso, senão a rota revela quais contas existem."""
        _, r_ok = self._solicitar()
        _, r_inexistente = self._solicitar(usuario="naoexiste", email="ninguem@x.com")
        _, r_fazenda = self._solicitar(fazenda="Fazenda de Outro")
        a, b, c2 = r_ok.json(), r_inexistente.json(), r_fazenda.json()
        self.assertEqual(a["ok"], b["ok"], "resposta deve ser genérica")
        self.assertEqual(b, c2, "inexistente e fazenda errada são indistinguíveis")

    def test_email_recebe_o_codigo(self):
        mail.outbox.clear()
        self._solicitar()
        self.assertEqual(len(mail.outbox), 1, "código deve ser enviado por e-mail")
        self.assertIn(self.user.email, mail.outbox[0].to)

    def test_falha_de_email_nao_vira_500(self):
        """`except Exception: return str(e)` expunha traceback em produção."""
        c = Client()
        with override_settings(
            EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend"
        ):
            r = c.post(reverse("login"), self.dados)  # SMTP inexistente
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("Traceback", r.content.decode())

    def test_sem_sessao_recuperacao_recusado(self):
        r = Client().post(
            reverse("login"), {"acao": "verificar_codigo", "codigo": "ABC123"}
        )
        self.assertFalse(r.json()["ok"])


class DemoLoginTest(TestCase):
    @override_settings(DEBUG=False, AMPLIAGRO_DEMO_ENABLED=False)
    def test_demo_bloqueado_em_producao(self):
        """`/demo/` criava e autenticava 'demo'/'demo123' para qualquer visitante
        anônimo — backdoor de produção."""
        r = Client().get("/demo/")
        self.assertEqual(r.status_code, 302)
        self.assertIn("/login/", r.get("Location") or "")
        self.assertFalse(
            User.objects.filter(username="demo").exists(),
            "não pode criar usuário demo com o portão fechado",
        )

    @override_settings(DEBUG=True)
    def test_demo_libera_em_debug(self):
        r = Client().get("/demo/")
        self.assertEqual(r.status_code, 302)
        self.assertTrue(User.objects.filter(username="demo").exists())

    @override_settings(DEBUG=False, AMPLIAGRO_DEMO_ENABLED=True)
    def test_flag_explicita_liga_o_demo(self):
        """Portão de exceção para rodar a demo em staging com DEBUG desligado."""
        r = Client().get("/demo/")
        self.assertEqual(r.status_code, 302)
        self.assertTrue(User.objects.filter(username="demo").exists())

    @override_settings(DEBUG=True)
    def test_demo_bloqueia_next_externo(self):
        r = Client().get("/demo/?next=//evil.com")
        self.assertNotIn("evil.com", r.get("Location") or "")


class LogoutTest(TestCase):
    def setUp(self):
        self.user = _produtor("jose")

    def test_logout_por_post(self):
        c = Client()
        c.force_login(self.user)
        r = c.post(reverse("logout"))
        self.assertEqual(r.status_code, 302)
        self.assertNotIn("_auth_user_id", c.session)

    def test_logout_por_get_recusado(self):
        """Logout por GET permite deslogar a vítima com `<img src="/logout/">`."""
        c = Client()
        c.force_login(self.user)
        r = c.get(reverse("logout"))
        self.assertEqual(r.status_code, 405)
        self.assertIn(
            "_auth_user_id", c.session, "sessão não pode ser encerrada por GET"
        )

    def test_limpar_flag_exige_post_e_login(self):
        c = Client()
        r = c.get(reverse("limpar_flag_recuperacao"))
        self.assertEqual(r.status_code, 405)
        self.assertEqual(
            Client().post(reverse("limpar_flag_recuperacao")).status_code, 302
        )


class PerfilObrigatorioTest(TestCase):
    """Conta sem `PerfilUsuario` não pode herdar permissão de produtor."""

    def test_sinal_cria_perfil_em_toda_conta(self):
        """Cobre o caminho SSO (django-allauth) e o admin, que criavam
        `User` sem perfil."""
        u = User.objects.create_user(username="sso", password=SENHA_FORTE)
        self.assertTrue(hasattr(u, "perfil"), "toda conta criada deve ter perfil")
        self.assertEqual(u.perfil.tipo_usuario, "produtor")

    def test_conta_sem_perfil_nao_acessa_area_do_produtor(self):
        u = User.objects.create_user(username="sem_perfil", password=SENHA_FORTE)
        PerfilUsuario.objects.filter(user=u).delete()  # simula o dado faltando
        u.refresh_from_db()
        self.assertFalse(pode_acessar(u, "cadastro-propriedade"))
        self.assertFalse(
            pode_ver_financeiro(u), "financeiro nunca é assumido sem perfil"
        )

    def test_sinal_nao_sobrescreve_perfil_existente(self):
        u = User.objects.create_user(username="mec", password=SENHA_FORTE)
        PerfilUsuario.objects.filter(user=u).update(
            tipo_usuario="servidor", area_servidor="MECANICA"
        )
        User.objects.filter(pk=u.pk).update(username="mec2")  # força novo post_save
        u.refresh_from_db()
        self.assertEqual(u.perfil.tipo_usuario, "servidor")


class OperarioLoginTest(TestCase):
    def setUp(self):
        self.prod = _produtor("jose")
        hoje = timezone.now().date()
        self.func = Funcionario.objects.create(
            nome="Joao Mecanico",
            propriedade=self.prod.propriedades.first(),
            cargo="MECANICO",
            salario=2500,
            data_admissao=hoje,
            ativo=True,
        )
        self.c = Client()
        self.c.force_login(self.prod)

    def _criar(self, senha):
        return self.c.post(
            reverse("operario-criar-login"),
            data=f'{{"funcionario_id": {self.func.pk}, "username": "joao", "senha": "{senha}"}}',
            content_type="application/json",
        )

    def test_cria_login_de_servidor(self):
        r = self._criar(SENHA_FORTE)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["ok"])
        user = User.objects.get(username="joao")
        self.assertEqual(user.perfil.tipo_usuario, "operario")
        self.assertEqual(user.perfil.propriedade_vinculada_id, self.func.propriedade_id)

    def test_senha_fraca_recusada(self):
        r = self._criar("1")
        self.assertEqual(r.status_code, 400)
        self.assertFalse(User.objects.filter(username="joao").exists())

    def test_servidor_nao_cria_login_de_funcionario_alheio(self):
        """Escopo por propriedade: um produtor não pode criar login em
        funcionário de outra fazenda."""
        outro = _produtor("outro_prod")
        func_alheio = Funcionario.objects.create(
            nome="Fulano",
            propriedade=outro.propriedades.first(),
            cargo="MECANICO",
            salario=2000,
            data_admissao=timezone.now().date(),
            ativo=True,
        )
        r = self.c.post(
            reverse("operario-criar-login"),
            data=f'{{"funcionario_id": {func_alheio.pk}, "username": "x", "senha": "{SENHA_FORTE}"}}',
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 404)
        self.assertFalse(User.objects.filter(username="x").exists())
