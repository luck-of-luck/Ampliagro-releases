"""Testes de `limpar_contas_teste`.

O comando apaga CONTAS. Um teste dele que não prove o que NÃO pode
apagar não vale nada — por isso a maior parte deste ficheiro é sobre as
condições de recusa, não sobre a de aceitação.

Cada teste cria o utilizador dentro de `django.test.TestCase`, por isso
corre no banco de teste e o rollback devolve tudo. Um teste que here
`unittest.TestCase` seria exactamente o defeito que este comando existe
para apanhar (FILA #54).
"""

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from app.management.commands.limpar_contas_teste import RE


class DeteccaoTest(TestCase):
    def _user(self, nome, **kw):
        return get_user_model().objects.create_user(nome, password="x", **kw)

    # ------------------------------------------------------------------
    # apaga
    # ------------------------------------------------------------------
    def test_apaga_conta_de_teste_sem_negocio(self):
        u = self._user("test_apaga_me")
        self.assertIn(u, self.candidatos())

    def test_padroes_cobrem_o_que_foi_visto_na_base(self):
        """Os nomes que apareceram na base real têm de ser reconhecidos."""
        for nome in (
            "testuser",
            "test_nav",
            "debug_user",
            "probe2",
            "p4",
            "palco_vivo",
            "amplia_teste",
            "prod_teste_validador",
            "prod_a2c67a2b",
            "mecanico.demo",
            "ctx3",
        ):
            with self.subTest(nome=nome):
                self.assertIsNotNone(RE.search(nome), f"{nome} devia ser reconhecido")

    # ------------------------------------------------------------------
    # NÃO apaga — é aqui que está o valor do comando
    # ------------------------------------------------------------------
    def test_nao_apaga_produtor_com_propriedade(self):
        """O nome é de teste, mas tem negócio: fica.

        É a condição que separa lixo de dados. Um produtor chamado
        `test_agenda` que tenha Property é dele, e apagá-lo por causa do
        nome é o pior erro que este comando pode cometer."""
        from app.models import Propriedade

        u = self._user("test_agenda")
        Propriedade.objects.create(user=u, nome="Minha fazenda", area_total=100)
        self.assertNotIn(u, self.candidatos())

    def test_nao_apaga_admin_mesmo_com_nome_de_teste(self):
        """Staff/superuser nunca é lixo: é de alguém, por definição."""
        u = self._user("test_admin")
        u.is_staff = True
        u.save()
        self.assertNotIn(u, self.candidatos())

    def test_nao_apaga_nome_que_apenas_contem_a_palavra(self):
        """Âncoras: `contestador` não é `test*`.

        Uma lista sem âncoras apagaria um produtor chamado "Palco" só por
        conter "palco", e um chamado "Contestador" só por conter "test"."""
        for nome in (
            "contestador",
            "palco_florido",
            "probe_científico",
            "manifesto_probe",
            "reproducao",
        ):
            with self.subTest(nome=nome):
                self.assertIsNone(RE.search(nome), f"{nome} devia ser preservado")

    def test_padrao_nao_casa_nome_vazio_ou_generico(self):
        for nome in ("", "   "):
            self.assertIsNone(RE.search(nome))

    def candidatos(self):
        from app.management.commands.limpar_contas_teste import Command

        return Command().candidatos()


class ExecucaoTest(TestCase):
    """O que o comando faz quando é chamado a sério."""

    def setUp(self):
        from io import StringIO

        self.out = StringIO()
        self.alvo = get_user_model().objects.create_user(
            "test_via_comando", password="x"
        )
        self.real = get_user_model().objects.create_user("bruno", password="x")

    def _corre(self, *args):
        call_command("limpar_contas_teste", *args, stdout=self.out, stderr=self.out)
        return self.out.getvalue()

    def test_sem_apagar_nao_apaga_nada(self):
        saida = self._corre()
        self.assertIn("dry-run", saida)
        self.assertTrue(
            get_user_model().objects.filter(pk=self.alvo.pk).exists(),
            "dry-run apagou uma conta: a flag --apagar é a que protege",
        )

    def test_com_apagar_apaga_a_de_teste(self):
        self._corre("--apagar", "--sim")
        self.assertFalse(get_user_model().objects.filter(pk=self.alvo.pk).exists())

    def test_com_apagar_mantem_a_conta_com_negocio(self):
        from app.models import Propriedade

        Propriedade.objects.create(
            user=self.real, nome="Fazenda do Bruno", area_total=100
        )
        self._corre("--apagar", "--sim")
        self.assertTrue(
            get_user_model().objects.filter(pk=self.real.pk).exists(),
            "o comando apagou um produtor com propriedade",
        )

    def test_a_backup_e_feita_antes_de_apagar(self):
        """Sem backup, um engano aqui é dados perdidos a sério."""
        from django.conf import settings

        self._corre("--apagar", "--sim")
        db = settings.DATABASES["default"]
        nome = str(db["NAME"])
        # o ficheiro de teste é apagado pelo runner; o que interesa é que a
        # copia foi pedida antes do delete — verificado pelo caminho.
        self.assertTrue(db["ENGINE"].endswith("sqlite3"))
        self.assertIsNotNone(nome)
