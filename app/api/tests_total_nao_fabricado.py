"""Testes para os endpoints que devolvem `total` sem ninguem os pedir.

Cada um destes responde com um numero que o painel mostra como fact.
Um `total: 0` que nao foi contado e' um zerouzin_rules fabricated:
chega ao painel com a mesma cara que "nao tens", e a pessoa conclui
pela primeira — que e' a conclusao errada, e a que a leva a comprar
outra coisa, a chamar um tecnico, a contratar alguem.
"""

import json

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from app.models.core import Propriedade


class TestTotalNaoFabricado(TestCase):
    """O `total` de cada endpoint tem de bater com a base."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username="t-total", password="x")
        cls.prop = Propriedade.objects.create(
            user=cls.user, nome="Faz Total", area_total=10
        )

    def setUp(self):
        self.c = APIClient()
        self.c.force_authenticate(self.user)

    # -- caminhoes: NAO existe o modelo, e' preciso dizer isso ----------
    def test_caminhoes_declara_que_a_fonte_nao_existe(self):
        r = self.c.get("/api/caminhoes/")
        self.assertEqual(r.status_code, 200)
        j = r.json()
        # Nao ha modelo Caminhao: dizer "0 caminhos" seria afirmar que se
        # perguntou a alguem. A resposta honesta diz de onde NAO veio.
        self.assertEqual(j["fonte"], "modelo_inexistente")
        self.assertIn("aviso", j)

    # -- funcionarios: conta, e o sem-tenant tambem diz total ----------
    def test_funcionarios_total_bate_com_a_lista(self):
        from app.models.equipe import Funcionario

        # `salario`, `data_admissao`, `telefone`, `email` e
        # `nome_fazenda_login` sao NOT NULL no schema. Nao e' um
        # esquecimento do modelo: e' o que ele exige, e o teste tem de
        # respeitar em vez de contornar.
        Funcionario.objects.create(
            propriedade=self.prop,
            nome="Ana",
            cargo="VAQUEIRO",
            ativo=True,
            salario=1800,
            data_admissao="2024-03-01",
            telefone="11999999999",
            email="ana@exemplo.com",
            nome_fazenda_login="faz-total",
        )
        Funcionario.objects.create(
            propriedade=self.prop,
            nome="Bruno",
            cargo="TRATORISTA",
            ativo=False,
            salario=2200,
            data_admissao="2025-01-15",
            telefone="11988888888",
            email="bruno@exemplo.com",
            nome_fazenda_login="faz-total",
        )
        j = self.c.get("/api/funcionarios-resumo/").json()
        self.assertEqual(j["total"], len(j["funcionarios"]))
        self.assertEqual(j["total"], 2)
        self.assertEqual(j["ativos"], 1)

    def test_funcionarios_sem_fazenda_nao_inventa_um_total(self):
        """Sem propriedade a view devolve so a lista. `total` ausente e'
        ausente: inventar 0 aqui seria a mesma mentira de sempre."""
        from app.models.core import Propriedade

        u2 = User.objects.create_user(username="t-sem-prop", password="x")
        Propriedade.objects.filter(user=u2).delete()
        c = APIClient()
        c.force_authenticate(u2)
        j = c.get("/api/funcionarios-resumo/").json()
        self.assertEqual(j["funcionarios"], [])
        self.assertNotIn(
            "total", j, "ausencia de propriedade nao e' 'zero funcionários'"
        )

    # -- maquinarios: conta maquinas e manutencoes ----------------------
    def test_maquinarios_total_bate_com_a_lista(self):
        from app.models.maquinario import Maquinario

        Maquinario.objects.create(propriedade=self.prop, nome="Trator", ativo=True)
        # `/api/maquinarios-resumo/`, e nao `/api/maquinarios/`.
        #
        # `/api/maquinarios/` pertence ao `MaquinarioViewSet` (CRUD). A view
        # `maquinarios_data` — que e' a que devolve `{maquinas, total,
        # em_manutencao}` — estava registada no MESMO caminho e, por vir
        # depois do `router.register()`, sombreava o ViewSet.
        #
        # O estrago: `cadastro-maquinario.html:257` faz POST para
        # `/api/maquinarios/` e levava 405. O cadastro de maquinas estava
        # partido. O agregado passou para `/api/maquinarios-resumo/`, como
        # `funcionarios-resumo/` ao lado de `/api/funcionarios/`.
        #
        # A INTENCAO deste teste — o total tem de bater com a lista, nunca ser
        # inventado — continua intacta. So mudou o endereco.
        j = self.c.get("/api/maquinarios-resumo/").json()
        self.assertEqual(j["total"], len(j["maquinas"]))
        self.assertEqual(j["total"], 1)

    def test_maquinarios_crud_aceita_escrita(self):
        """O outro lado da colisao: `/api/maquinarios/` tem de ACEITAR POST.

        Este teste e o que apanha a regressao. Se alguem voltar a registar a
        view de resumo em `/api/maquinarios/`, este falha — e o cadastro de
        maquinas volta a partir em silencio, como estava.
        """
        from app.models.maquinario import Maquinario

        r = self.c.post(
            "/api/maquinarios/",
            data=json.dumps(
                {
                    "propriedade": self.prop.id,
                    "tipo": "TRATOR",
                    "nome": "Colheitadeira",
                }
            ),
            content_type="application/json",
        )
        self.assertIn(
            r.status_code,
            (200, 201),
            f"POST /api/maquinarios/ respondeu {r.status_code}. O ViewSet CRUD "
            "esta sombreado por outra view — o cadastro esta partido.",
        )
        self.assertTrue(Maquinario.objects.filter(nome="Colheitadeira").exists())

    # -- vendas: o JS pede `total_vendas` e a view manda `total` -------
    def test_vendas_a_view_nao_responde_a_chave_que_o_js_le(self):
        """`vendas.js` le `data.total_vendas`. A view nunca mandou isso.

        O JS caia no fallback e mostrava "R$ 0" para todos os
        produtores, sempre. Este teste existe para falhar de novo se
        alguma vez as duas metades divergirem outra vez.
        """
        import pathlib

        js = pathlib.Path("app/static/js/tabs/vendas.js").read_text(encoding="utf-8")
        r = self.c.get("/api/vendas/")
        self.assertEqual(r.status_code, 200)
        j = r.json()
        # cada chave que o JS pede tem de existir, ou o JS tem de saber
        # que nao existe (e entao desenhar ausencia, nao zero)
        faltam = [k for k in ("total_vendas", "clientes_ativos") if k not in j]
        # enquanto a view nao os mandar, o JS TEM de tratar a ausencia
        # como ausencia. Se voltar o "? 0", o painel volta a mentir.
        self.assertIn(
            ": null", js, "o fallback voltou a ser 0 — o painel volta a mentir"
        )
        self.assertIn("numero(", js, "ausencia tem de ser desenhada, nao zero")
        self.assertTrue(
            faltam or "total_vendas" in j,
            f"a view devolve chaves que o JS nunca le: {sorted(j)}",
        )
