"""A conta de teste principal é de quem preenche a base, e não de quem escreve código.

Existe um comando, `criar_conta_demo`, que a cria. Estes testes existem para
que ninguém — nem uma sessão futura com boas intenções, nem um "já agora
normalizo o username" às três da manhã — consiga alterá-la.

A regra é simples de dizer e fácil de quebrar sem dar por isso: a conta vale o
que vale porque a senha e os dados são do dono. Um `set_password()` de exemplo
num comando de seed estraga a conta e não estraga nada visível: a app continua
a funcionar, os testes continuam verdes, e o produtor perde o acesso ao
próprio histórico.
"""

from __future__ import annotations

import json
from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import Client, TestCase

from app.management.commands.criar_conta_demo import USUARIO
from app.models import Propriedade


class ContaDemoNaoSeToca(TestCase):
    """`criar_conta_demo` cria uma vez. Depois disso, só relata."""

    def _cria(self, *args, **opts):
        out = StringIO()
        call_command("criar_conta_demo", *args, stdout=out, **opts)
        return out.getvalue()

    def test_cria_a_conta_e_a_fazenda_em_muzambinho(self):
        saida = self._cria()
        user = User.objects.get(username=USUARIO)

        self.assertIn(USUARIO, saida)
        # A senha aparece uma vez, na criação. O teste garante que a que vai
        # para a consola é mesmo a que fica guardada — senão quem lê a
        # consola fica com uma credencial que não abre a conta.
        senha = saida.split("palavra-passe : ")[1].split("\n")[0].strip()
        self.assertTrue(
            user.check_password(senha),
            "A senha mostrada na consola nao abre a conta criada.",
        )

        prop = Propriedade.objects.get(user=user)
        self.assertEqual(prop.cidade, "Muzambinho")
        self.assertEqual(prop.uf, "MG")
        # A área real não é inventada por este comando: entra 0, que o
        # relatório diz ser "por preencher". Um hectares inventado aqui
        # atravessa todos os KPIs por área sem ninguém dar por isso.
        self.assertEqual(float(prop.area_total), 0.0)

    def test_correr_de_novo_nao_altera_a_senha(self):
        self._cria()
        user = User.objects.get(username=USUARIO)
        hash_antes = user.password

        segunda = self._cria()

        user.refresh_from_db()
        self.assertEqual(
            user.password,
            hash_antes,
            "A senha foi recalculada. Esta conta é do dono: o comando não "
            "volta a definir a senha, nem com a mesma senha.",
        )
        # E a senha não é reescrita na consola: mostrar uma credencial duas
        # vezes transforma-a em segredo partilhado, e é o caminho para ficar
        # num log.
        self.assertNotIn("palavra-passe :", segunda)

    def test_correr_de_novo_nao_altera_o_nome_nem_a_propriedade(self):
        self._cria()
        user = User.objects.get(username=USUARIO)
        prop = Propriedade.objects.get(user=user)
        antes = (
            user.first_name,
            prop.nome,
            prop.cidade,
            prop.uf,
            float(prop.area_total),
        )

        self._cria()
        self._cria(senha="outra-coisa", area="9999")

        user.refresh_from_db()
        prop.refresh_from_db()
        self.assertEqual(
            (user.first_name, prop.nome, prop.cidade, prop.uf, float(prop.area_total)),
            antes,
            "Uma segunda corrida alterou a identidade da conta. `--senha` e "
            "`--area` só valem na CRIAÇÃO; depois disso são ignorados de "
            "propósito, e um pedido de alteração tem de ser recusado, não "
            "atendido.",
        )

    def test_nao_inventa_safras_nem_lancamentos(self):
        """Dados inventados estragam o teste mais do que dados em falta.

        Quem preenche a base sabe o que e' real. Se este comando criasse
        uma safra de exemplo, o proximo bug a aparecer seria indistinguivel
        de um dado inventado - e depurar isso custa dias.
        """
        from app.models import LancamentoFinanceiro, Safra

        self._cria()
        user = User.objects.get(username=USUARIO)
        self.assertEqual(Safra.objects.filter(propriedade__user=user).count(), 0)
        self.assertEqual(
            LancamentoFinanceiro.objects.filter(propriedade__user=user).count(), 0
        )


class ContaDemoAbreNoLogin(TestCase):
    """A conta tem de ABRIR. Uma conta de teste que nao entra nao e' uma conta."""

    def _entra(self):
        out = StringIO()
        call_command("criar_conta_demo", stdout=out)
        senha = out.getvalue().split("palavra-passe : ")[1].split("\n")[0].strip()
        c = Client()
        r = c.post("/login/", {"usuario": USUARIO, "senha": senha}, follow=True)
        return c, r

    def test_entra_e_ve_a_app(self):
        c, r = self._entra()
        self.assertEqual(r.status_code, 200)
        self.assertIn("_auth_user_id", c.session, "A conta criada nao abre no login.")
        self.assertEqual(c.get("/").status_code, 200)
        self.assertEqual(c.get("/api/dashboard/").status_code, 200)
        self.assertEqual(c.get("/api/amplia/palco/info/").status_code, 200)

    def test_entra_vazia_e_nao_com_numeros_fabricados(self):
        """Vazia e' o estado honesto. Cheia de exemplos seria mentira.

        Sem dados, os numeros de GESTAO tem de ser zero — e nao um KPI
        inventado para a conta parecer viva. Quem preenche a base e' quem sabe
        o que e' real; ate la, o ecra esta em branco, e diz isso.
        """
        c, _ = self._entra()
        d = json.loads(c.get("/api/dashboard/").content.decode())

        for chave in ("roi", "custo_ha", "fluxo_caixa"):
            self.assertEqual(
                float(d[chave] or 0), 0.0, f"{chave} veio preenchido sem dados."
            )
        self.assertEqual(d["financeiro"]["total_receitas"], 0.0)
        self.assertEqual(d["financeiro"]["total_despesas"], 0.0)
        self.assertEqual(d["safras"], [])
        self.assertEqual(d["resumo"]["total_talhoes"], 0)

    def test_o_clima_traz_a_fonte_declarada(self):
        """O clima tem de ser ATRIBUIVEL, e nao tem de ser sempre simulado.

        Este teste vivia a afirmar `clima_fonte == "simulado"` e passou a
        falhar no dia em que a instalacao ganhou credencial de previsao do
        tempo. Passou verde, depois vermelho, sem que nada no codigo mudasse —
        porque a fonte do clima depende de configuracao, nao de codigo.

        Depender disso e' depender do ambiente. O que NAO depende do ambiente,
        e o que importa, e' o contrato: o clima nunca vem sem dizer de onde
        veio. Um painel que mostra 28 graus e nao diz se foi medido ou gerado
        e' o defeito; o valor 28 ser medido ou nao, nao e'.
        """
        c, _ = self._entra()
        d = json.loads(c.get("/api/dashboard/").content.decode())

        # 1. A fonte e' sempre declarada — nunca vazia, nunca ausente.
        fonte = str(d.get("clima_fonte") or "").strip()
        self.assertTrue(
            fonte,
            "O clima veio sem fonte. Um numero sem origem nao e' um dado, "
            "e' uma opiniao com casas decimais.",
        )
        # 2. A fonte repete-se dentro do bloco, para quem le so o bloco.
        self.assertEqual(str(d.get("clima", {}).get("fonte") or "").strip(), fonte)
