"""As guias ANIMAL e AQUATICA mostram o registo que o produtor fez.

POR QUE ABRE-SE PELO URL
========================
Um teste que chama `guia_animal_view(req)` mede a funcao. Um que faz
`client.get()` mede a **pagina**. A distincao ja valeu um bug inteiro: uma
correcao do N+1 deixou `TypeError: unhashable type: 'set'` na guia vegetal,
a pagina dava **500 em todos os pedidos**, e os testes do N+1 passavam —
porque mediavam queries, e a excecao acontece ANTES do `render`.

O ERRO QUE ESTES TESTES TRAVAM
===============================
A guia filtra `Cultura.grupo IN ('bovinos', 'suinos', ...)` e o produtor
escreve `RegistroProducao.grupo = 'animal'`. **Nenhuma das duas colunas
esta ligada a outra.** A ponte e' o `cultura_id`, que esta preenchido em
100% dos registos (MEDIDO 2026-10-05 em `db.sqlite3`).

A contagem por `grupo` dava **zero**, e a leitura correcta seria "o
produtor nao registou nada" — quando ele tinha registado 8 vezes. E' a
mesma classe de erro que o `icontains=""` e que o ciclo de 112 dias em vez
de 116: **a busca pelo campo errado, lida como ausencia de dado.**

O QUE CADA TESTE PROVA
======================
1. O registo aparece, pela ponte.
2. A cultura sem registo convida — e **nao** diz "0 registos".
3. O `status` conta: activos e distintos do total quando ha inactivos.
4. O tenancy: o registo do vizinho nao aparece.
5. A aquatica tambem — a mesma ligacao, outra guia.
"""

from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from app.models import Cultura, Propriedade, RegistroProducao


class GuiaAnimalMostraRegistosTest(TestCase):
    def setUp(self):
        self.u = User.objects.create_user("guia_ani", password="x1234567")
        self.client.force_login(self.u)
        self.prop = Propriedade.objects.create(
            user=self.u, nome="Fazenda do Gado", area_total=Decimal("100")
        )
        # as raças que a base real tem registadas
        self.ayrshire = Cultura.objects.create(
            id=28533, nome="Ayrshire", grupo="bovinos"
        )
        self.angus = Cultura.objects.create(id=28548, nome="Angus", grupo="bovinos")
        self.nunca = Cultura.objects.create(id=28599, nome="Gir", grupo="bovinos")

    def _registo(self, cultura, data="2026-05-06", status="ativo", user=None):
        RegistroProducao.objects.create(
            user=user or self.u,
            cultura=cultura,
            cultura_id=cultura.id,
            grupo="animal",  # o que o PRODUTOR escreve
            nome=cultura.nome,
            status=status,
            data_registro=data,
            quantidade=1,
        )

    def _abrir(self):
        r = self.client.get(reverse("guia-animal"))
        self.assertEqual(
            r.status_code,
            200,
            "a guia animal devolveu %s. Ver `tests/test_guia_vegetal_queries.py` "
            "para o caso analogue que deu 500 em todos os pedidos." % r.status_code,
        )
        return r.content.decode("utf-8")

    # ------------------------------------------------------------------
    # 1) O registo aparece, pela ponte
    # ------------------------------------------------------------------
    def test_o_registro_aparece_na_raca(self):
        for _ in range(3):
            self._registo(self.ayrshire)
        self._registo(self.angus)

        html = self._abrir()
        self.assertIn(
            "3 registos",
            html,
            "A Ayrshire tem 3 registos e o cartao nao diz. A ponte "
            "`cultura_id` esta preenchida — se nao aparece, e' porque se "
            "contou por `grupo` ('animal') e a guia filtra `bovinos`.",
        )
        self.assertIn("1 registo", html)  # Angus

    # ------------------------------------------------------------------
    # 2) Sem registo convida — e NAO diz zero
    # ------------------------------------------------------------------
    def test_a_raca_sem_registo_convida_e_nao_diz_zero(self):
        html = self._abrir()

        self.assertIn(
            "registar",
            html,
            "A raca sem registo nao mostra o convite. Sem isso o cartao "
            "fica vazio e parece um bug da pagina.",
        )
        self.assertNotIn(
            "0 registos",
            html,
            "'0 registos' afirma que o produtor foi ate a tela, viu o boi e "
            "decidiu nao registar. Ele nunca abriu a tela. '0' e' uma "
            "affirmacao sobre a pessoa; 'nao registou' e' sobre o registo.",
        )

    # ------------------------------------------------------------------
    # 3) O status conta
    # ------------------------------------------------------------------
    def test_os_activos_sao_distinguidos_do_total(self):
        self._registo(self.ayrshire, status="ativo")
        self._registo(self.ayrshire, status="arquivado")
        self._registo(self.ayrshire, status="ativo")

        html = self._abrir()
        self.assertIn("3 registos", html)
        self.assertIn(
            "2 activos",
            html,
            "Com 3 registos e 2 activos, o cartao tem de mostrar os dois "
            "numeros. Mostrar so '3' esconde que um foi arquivado.",
        )

    # ------------------------------------------------------------------
    # 4) O tenancy
    # ------------------------------------------------------------------
    def test_o_registro_do_vizinho_nao_aparece(self):
        outro = User.objects.create_user("guia_vizinho", password="x1234567")
        self._registo(self.ayrshire, user=outro)  # o AYRSHIRE do vizinho
        # e um registo meu, de outra raca, para o "registar" aparecer
        self._registo(self.angus)

        html = self._abrir()

        self.assertIn(
            "1 registo",
            html,
            "o registo deste produtor (Angus) nao aparece.",
        )
        self.assertNotIn(
            "Ayrshire",
            html.split('data-cultura-nome="Ayrshire"')[1][:400]
            if 'data-cultura-nome="Ayrshire"' in html
            else "inexistente",
            "O cartao da Ayrshire mostra o registo do VIZINHO. O historico "
            "tem de vir de `RegistroProducao.objects.filter(user=request.user)` "
            "— e nao de um parametro que o chamador pudesse esquecer.",
        )

    # ------------------------------------------------------------------
    # 5) A aquatica, que e' a outra guia
    # ------------------------------------------------------------------
    def test_a_guia_aquatica_mostra_o_seu_registro(self):
        tilapia = Cultura.objects.create(id=28709, nome="Tilápia", grupo="peixes")
        RegistroProducao.objects.create(
            user=self.u,
            cultura=tilapia,
            cultura_id=tilapia.id,
            grupo="aquatica",
            nome="Tilápia",
            status="ativo",
            data_registro="2026-02-02",
        )

        r = self.client.get(reverse("guia-aquatica"))
        self.assertEqual(r.status_code, 200)
        html = r.content.decode("utf-8")
        self.assertIn(
            "1 registo",
            html,
            "a Tilápia tem 1 registo e o cartao nao diz. A aquatica usa a "
            "mesma ponte — se nao mostra, ou a guia nao a usa, ou `grupo` "
            "voltou a ser o criterio.",
        )
