"""A guia mostra o ciclo OBSERVADO, e nao um zero nem um numero inventado.

O QUE ESTE TESTE PROVA, E POR QUE CADA PARTE
=============================================
A guia vegetal mostrava 709 **nomes** e nada mais. A tabela `Cultura` tem a
agronomia vazia (MEDIDO 2026-10-05):

    janela_plantio_inicio   0/709    0.0%
    ciclo_dias             2/709    0.3%

O que se passou a mostrar vem das SAFRAS do produtor. Tres coisas precisam
de ser provadas, e cada uma tem um modo diferente de falhar:

1. **A cultura com safra mostra o ciclo real.** Se o template nao passar o
   historico, o cartao fica vazio — e um cartao vazio parece um bug.

2. **A cultura sem safra mostra "registar safra", NAO "0 dias".** Esta e' a
   parte que mais importa. `0` e' uma affirmacao sobre o produtor ("fez
   zero ciclos"). "Ainda nao registou" e' uma affirmacao sobre o registo.
   Sao coisas diferentes, e um numero nao e' uma delas.

3. **A cultura com datas spreadidas mostra o aviso e NAO o ciclo.** O cafe
   da base tem safras de 60 a 461 dias: e' data mal posta, e a media seria
   264 dias — um numero que nunca existiu em nenhuma lavoura. Se o cartao
   mostrar esse numero, o produtor compara com o vizinho e descobre que e'
   falso.

POR QUE UM TESTE DE TEMPLATE E' NECESSARIO
==========================================
O servico tem os seus testes (`test_historico_cultura.py`). Falta provar
que o **template usa o servico** — e um servico correcto, ligado a nada,
nao muda o ecra. E' o mesmo que o `3.md` chama de *"duas implementacoes do
mesmo objecto, e a correccao vai a uma delas"*.
"""

from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from app.models import Cultura, Propriedade, Safra


class GuiaMostraHistoricoTest(TestCase):
    def setUp(self):
        self.u = User.objects.create_user("guia_hist", password="x1234567")
        self.prop = Propriedade.objects.create(
            user=self.u, nome="Fazenda do Ciclo", area_total=Decimal("100")
        )
        # as DUAS linhas de cafe que a base real tem
        self.cafe = Cultura.objects.create(id=850, nome="Café", grupo="graos")
        self.soja = Cultura.objects.create(id=851, nome="Soja", grupo="oleaginosas")
        self.milho = Cultura.objects.create(id=852, nome="Milho", grupo="graos")
        self.nunca = Cultura.objects.create(
            id=853, nome="Cultura Nunca Plantada", grupo="hortalicas"
        )
        # A vista tem `@login_required`. Sem isto o middleware devolve 302 e
        # o teste mede a pagina de login — que passa em quase todos os
        # `assertContains` e nao prova nada sobre a guia.
        self.client.force_login(self.u)

    def _abrir(self):
        """Abre a guia pelo URL e devolve o `HttpResponse`.

        **Pelo URL**, e nao chamando a funcao. Um teste que chama
        `guia_vegetal_view(req)` mede a funcao; um que faz `client.get()`
        mede a pagina. A distincao aqui valeu um bug inteiro: uma correcao
        do N+1 deixou `TypeError: unhashable type: 'set'` na vista, a pagina
        dava 500 em TODOS os pedidos, e os testes do N+1 passavam — porque
        mediavam queries e a excecao acontece ANTES do `render`.
        """
        r = self.client.get(reverse("guia-vegetal"))
        self.assertEqual(
            r.status_code,
            200,
            "a guia vegetal devolveu %s em vez de 200. "
            "MEDIDO 2026-10-05: uma correcao do N+1 introduzia um "
            "`TypeError: unhashable type: 'set'` e a pagina dava 500 em todos "
            "os pedidos." % r.status_code,
        )
        # a STRING, e nao a response: `assertIn` procura numa str. Com a
        # response, comparava com o `repr` dela e nunca encontrava nada —
        # um teste que passa porcomparar a coisa errada.
        return r.content.decode("utf-8")

    def _html(self):
        return self._abrir().content.decode("utf-8")

    # ------------------------------------------------------------------
    # 1) A cultura com safra mostra o ciclo REAL
    # ------------------------------------------------------------------
    def test_a_soja_mostra_o_ciclo_que_o_produtor_registou(self):
        Safra.objects.create(
            propriedade=self.prop,
            cultura=self.soja,
            ano=2024,
            data_plantio="2024-10-15",
            data_colheita="2025-02-20",
            produtividade=Decimal("65.3"),
            area_plantada=Decimal("420"),
        )
        html = self._abrir()

        self.assertIn("128 dias", html)
        # e a amostra, porque uma safra nao e' um ciclo
        self.assertIn("1 safra", html)
        self.assertIn("65,3", html)

    # ------------------------------------------------------------------
    # 2) A cultura sem safra convida — e nao afirma zero
    # ------------------------------------------------------------------
    def test_a_cultura_sem_safra_convida_e_nao_diz_zero(self):
        # `assertIn` e nao `assertContains`: a palavra aparece uma vez por
        # cartao sem safra, e sao varias. `assertContains` conta e falha se
        # nao for exactamente 1 — o que nao e' o que este teste quer dizer.
        html = self._abrir()

        self.assertIn(
            "registar safra",
            html,
            "A cultura sem safra nao mostra o convite. Sem isso o cartao "
            "fica vazio e parece um bug da pagina.",
        )
        self.assertNotIn(
            "0 dias",
            html,
            "Um cartao diz '0 dias'. Isso afirma que o produtor fez zero "
            "ciclos — ele nao fez nenhum: ainda nao plantou. '0' e' uma "
            "affirmacao sobre a pessoa, 'nao registou' e' uma sobre o registo.",
        )

    # ------------------------------------------------------------------
    # 3) As datas spreadidas: aviso SIM, ciclo NAO
    # ------------------------------------------------------------------
    def test_o_cafe_mostra_o_aviso_e_nao_o_ciclo(self):
        """O cafe da base real tem safras de 60 a 461 dias.

        A amplitude de 401 dias nao e' variacao de cultura — 60 dias e'
        curto demais para um perene. A media seria 264 dias, e 264 nao e'
        o ciclo de nenhum destes talhoes.
        """
        for ano, fim, prod in (
            (2023, "2023-06-30", "35"),
            (2024, "2025-07-10", "30"),
            (2024, "2025-07-22", "33"),
            (2024, "2025-08-05", "32"),
        ):
            Safra.objects.create(
                propriedade=self.prop,
                cultura=self.cafe,
                ano=ano,
                data_plantio="2024-05-01" if ano == 2024 else "2023-05-01",
                data_colheita=fim,
                produtividade=Decimal(prod),
                area_plantada=Decimal("20"),
            )

        html = self._abrir()

        self.assertIn(
            "datas a rever",
            html,
            "O cafe com datas spreadidas nao mostra aviso nenhum. O produtor "
            "vê um ciclo que nunca existiu e nao sabe que o problema sao as "
            "datas.",
        )
        # 264 e' a media dos ciclos — o numero que nao pode aparecer
        self.assertNotIn(
            "264 dias",
            html,
            "Apareceu '264 dias': a media de uma serie em que uma safra tem "
            "60 dias e outra tem 461. Nao e' o ciclo de nenhum talhao — e' "
            "uma media de dados errados, que e' pior do que nao mostrar nada.",
        )

    # ------------------------------------------------------------------
    # 4) O isolamento — o que a guia mostra e' da SUA fazenda
    # ------------------------------------------------------------------
    def test_a_guia_mostra_apenas_o_que_e_deste_produtor(self):
        """O historico vem do filtro de tenancy, nao de um parametro.

        Um produtor que ve o ciclo de outro e' um problema de isolamento de
        dados, nao dedisplay. Este teste existe porque o servico recebe a
        query ja filtrada: e' a unica coisa que impede o erro, e nao ha
        assinatura que o torne mais obvio.
        """
        outro = User.objects.create_user("guia_outro", password="x1234567")
        prop_outro = Propriedade.objects.create(
            user=outro, nome="Fazenda do Vizinho", area_total=Decimal("50")
        )
        Safra.objects.create(
            propriedade=prop_outro,
            cultura=self.milho,
            ano=2025,
            data_plantio="2025-02-28",
            data_colheita="2025-06-20",
            produtividade=Decimal("75"),
            area_plantada=Decimal("50"),
        )

        html = self._abrir()

        self.assertNotIn(
            "112 dias",
            html,
            "A guia deste produtor mostra o ciclo do vizinho. O historico "
            "tem de vir da query ja filtrada por propriedade — e nao de um "
            "parametro que o chamador possa esquecer.",
        )
        self.assertIn(
            "registar safra",
            html,
            "O milho existe na base mas sem safra DESTE produtor: o cartao "
            "tem de convidar a registar, e nao mostrar o ciclo do vizinho.",
        )
