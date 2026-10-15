"""Um painel, todas as fazendas. Um `.first()` não chega.

## O defeito

`dashboard_data` recebia **uma** propriedade — `get_propriedade_optimizada()`,
que faz `.first()`. Um produtor com duas fazendas via o painel inteiro
calculado sobre uma delas, **sem qualquer aviso**: números reais, errados, e
nada na interface a dizer que faltava a outra metade.

E o pior: `Propriedade.user` é uma `FK` sem unicidade, e **não existe conceito
de "propriedade activa" em lado nenhum do sistema**. Não havia uma intenção de
design a respeitar — era `.first()`, que devolve a que a base de dados calçar
primeiro, e isso pode mudar com o plano de execução.

Um painel que mostra números plausíveis e errados é pior do que um painel
vazio: o vazio convida a investigar.

## O que este ficheiro fixa

1. Os totais são de TODAS as propriedades visíveis, não de uma.
2. A área é a soma — hectares somam-se.
3. O clima NÃO se agrega (é meteorologia de um sítio) e o payload diz de qual.
4. A lista de propriedades viaja, para o painel poder dizer o que cobre.
5. Uma propriedade sem área não "contamina" as que têm área medida.
"""

from datetime import date

from django.contrib.auth.models import User
from django.core.cache import cache
from rest_framework.test import APIRequestFactory, APITestCase, force_authenticate

from app.api.views import dashboard_data
from app.models import Animal, Funcionario, LancamentoFinanceiro, Propriedade, Talhao


class MultiPropriedadeTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="multi-prop", password="test")
        self.grande = Propriedade.objects.create(
            user=self.user, nome="Fazenda Grande", area_total=100, uf="SP"
        )
        self.pequena = Propriedade.objects.create(
            user=self.user, nome="Fazenda Pequena", area_total=50, uf="MG"
        )
        cache.clear()
        self.factory = APIRequestFactory()

    def _painel(self):
        request = self.factory.get("/api/dashboard/")
        force_authenticate(request, user=self.user)
        response = dashboard_data(request)
        self.assertEqual(response.status_code, 200)
        return response.data

    def _lancar(self, prop, tipo, valor, desc):
        return LancamentoFinanceiro.objects.create(
            propriedade=prop,
            tipo=tipo,
            categoria="Teste",
            valor=valor,
            data=date.today(),
            descricao=desc,
        )

    def test_saldo_soma_as_duas_fazendas(self):
        self._lancar(self.grande, "RECEITA", 3000, "Granda")
        self._lancar(self.pequena, "RECEITA", 2000, "Pequena")

        painel = self._painel()

        # Antes, via 3000 ou 2000 conforme o `.first()` — nunca 5000.
        self.assertEqual(painel["fluxo_caixa"], 5000)
        self.assertEqual(painel["financeiro"]["total_receitas"], 5000)

    def test_area_e_a_soma_das_fazendas(self):
        painel = self._painel()
        self.assertEqual(painel["area_total"], 150.0)
        self.assertTrue(painel["area_medida"])

    def test_custo_por_hectare_usa_a_area_total(self):
        self._lancar(self.grande, "DESPESA", 1000, "Gran")
        self._lancar(self.pequena, "DESPESA", 500, "Peq")

        painel = self._painel()

        # 1500 de despesa em 150 ha. Com o `.first()` (100 ha) dava 15,00.
        self.assertEqual(painel["custo_ha"], 10.0)

    def test_roi_agrega_as_duas_fazendas(self):
        self._lancar(self.grande, "RECEITA", 2000, "a")
        self._lancar(self.grande, "DESPESA", 1000, "b")
        self._lancar(self.pequena, "RECEITA", 1000, "c")
        self._lancar(self.pequena, "DESPESA", 1000, "d")

        painel = self._painel()

        # Saldo 1000 sobre 2000 de despesa = +50%.
        self.assertEqual(painel["roi"], 50.0)

    def test_a_fazenda_principal_e_a_de_maior_area(self):
        painel = self._painel()
        # O clima vem de um sítio só. A maior área é a que domina o painel.
        self.assertEqual(painel["propriedade"]["id"], self.grande.id)
        self.assertEqual(painel["propriedade"]["nome_fazenda"], "Fazenda Grande")

    def test_o_painel_diz_que_propriedades_cobre(self):
        painel = self._painel()
        self.assertEqual(painel["total_propriedades"], 2)
        nomes = {p["nome"] for p in painel["propriedades"]}
        self.assertEqual(nomes, {"Fazenda Grande", "Fazenda Pequena"})
        # E diz quais têm área medida, para o produtor não supor que 150 ha
        # estão medidos se uma das fazendas não tem área lançada.
        medidas = {p["nome"]: p["area_medida"] for p in painel["propriedades"]}
        self.assertEqual(medidas["Fazenda Grande"], True)
        self.assertEqual(medidas["Fazenda Pequena"], True)

    def _funcionario(self, prop, nome):
        """Campos exigidos pelo modelo (`salario`, `data_admissao`, ...).

        Só o que o painel conta interessa — mas o `Funcionario` tem
        `NOT NULL` sem default em vários campos, e um `create` a meio falha
        antes de chegar ao que queremos provar.
        """
        return Funcionario.objects.create(
            propriedade=prop,
            nome=nome,
            cargo="Temporário",
            salario=1000,
            data_admissao=date(2020, 1, 1),
            telefone="000",
            email=f"{nome.lower()}@exemplo.com",
            nome_fazenda_login=nome.lower(),
            ativo=True,
        )

    def _animal(self, prop, especie, qtd):
        return Animal.objects.create(
            propriedade=prop,
            especie=especie,
            raca="Nelore",
            quantidade=qtd,
            observacao="",
        )

    def test_conta_funcionarios_e_animais_de_todas(self):
        self._funcionario(self.grande, "A")
        self._funcionario(self.pequena, "B")
        self._animal(self.grande, "Bovino", 10)
        self._animal(self.pequena, "Bovino", 5)

        painel = self._painel()
        self.assertEqual(painel["resumo"]["total_funcionarios"], 2)
        self.assertEqual(painel["resumo"]["total_animais"], 15.0)

    def test_talhoes_de_ambas_as_fazendas(self):
        Talhao.objects.create(
            propriedade=self.grande, nome="T1", area_hectare=10, tipo_solo="Latossolo"
        )
        Talhao.objects.create(
            propriedade=self.pequena, nome="T2", area_hectare=20, tipo_solo="Latossolo"
        )

        painel = self._painel()
        self.assertEqual(painel["resumo"]["total_talhoes"], 2)

    def test_uma_fazenda_sem_area_nao_arrasta_as_outras(self):
        """A fazenda sem área não pode baixar o custo/ha de quem tem área.

        Uma fazenda sem `area_total` acrescenta 0 hectares ao total — não
        inventa hectares, e não divide as despesas de ninguém por uma área
        que não existe. O custo/ha é o das 100 ha medidas, e o painel diz que
        uma das três não tem área.
        """
        Propriedade.objects.create(
            user=self.user, nome="Sem Medir", area_total=0, uf="PR"
        )
        self._lancar(self.grande, "DESPESA", 2000, "Gran")

        painel = self._painel()

        # A fazenda sem área acrescenta 0 hectares — não inventa hectares.
        # 100 (grande) + 50 (pequena) + 0 (sem medir) = 150.
        self.assertEqual(painel["area_total"], 150.0)
        # 2000 em 150 ha = 13,33/ha. O que se está a provar aqui não é o valor,
        # é que a área total continua a ser a soma das areas REALMENTE medidas:
        # a fazenda sem `area_total` não injecta um denominador falso.
        self.assertEqual(painel["custo_ha"], 13.33)
        self.assertEqual(painel["propriedades_sem_area"], 1)
        # E o painel continua a listar a fazenda sem medir — escondê-la seria
        # repetir o defeito antigo noutro sítio.
        nomes = {p["nome"] for p in painel["propriedades"]}
        self.assertIn("Sem Medir", nomes)
        sem_area = [p for p in painel["propriedades"] if p["nome"] == "Sem Medir"][0]
        self.assertFalse(sem_area["area_medida"])


class PropriedadeAlheiaNaoEntraTest(APITestCase):
    """A agregação não pode transformar-se numa fuga de dados.

    Somar "tudo o que é visível" só é seguro se "visível" for mesmo restrito.
    A propriedade de outro produtor tem de ficar de fora — e, pela mesma
    razão, a de um servidor que não está vinculado a este painel.
    """

    def setUp(self):
        cache.clear()
        self.factory = APIRequestFactory()
        self.dono = User.objects.create_user(username="dono", password="test")
        self.vizinho = User.objects.create_user(username="vizinho", password="test")

        self.minha = Propriedade.objects.create(
            user=self.dono, nome="A minha", area_total=10, uf="SP"
        )
        self.dele = Propriedade.objects.create(
            user=self.vizinho, nome="A do vizinho", area_total=9999, uf="MG"
        )
        LancamentoFinanceiro.objects.create(
            propriedade=self.dele,
            tipo="RECEITA",
            categoria="Segredo",
            valor=999999,
            data=date.today(),
            descricao="Do vizinho",
        )

    def _painel_de(self, user):
        request = self.factory.get("/api/dashboard/")
        force_authenticate(request, user=user)
        return dashboard_data(request).data

    def test_painel_nao_inclui_propriedade_de_outro_produtor(self):
        painel = self._painel_de(self.dono)

        self.assertEqual(painel["fluxo_caixa"], 0)
        self.assertEqual(painel["area_total"], 10.0)
        self.assertEqual(painel["total_propriedades"], 1)
        self.assertEqual([p["nome"] for p in painel["propriedades"]], ["A minha"])

    def test_o_proprio_vizinho_ve_o_seu(self):
        painel = self._painel_de(self.vizinho)
        self.assertEqual(painel["fluxo_caixa"], 999999)
        self.assertEqual(painel["total_propriedades"], 1)


def test_escolher_propriedade_principal_prefere_maior_area():
    """O critério é explícito e testado: maior área medida."""
    from app.painel_agregado import escolher_propriedade_principal

    class Fake:
        def __init__(self, id, area):
            self.id = id
            self.area_total = area

    pequena = Fake(1, 10)
    grande = Fake(2, 500)
    sem_area = Fake(3, 0)

    assert escolher_propriedade_principal([pequena, grande, sem_area]).id == 2
    # Sem áreas medidas, a ordem de chamada decide — mas tem de devolver uma
    # para o `clima` nunca receber `None`.
    assert escolher_propriedade_principal([pequena, sem_area]) in (pequena, sem_area)


def test_meses_do_ano_nao_estao_trocaveis():
    """Um mês trocado de lugar é um gráfico que mente calmo.

    `MESES_PT` é indexado por `enumerate(..., start=1)` e comparado com
    `TruncMonth(...).month`. Se "Mai" vier antes de "Abr", Abril aparece
    como Maio no gráfico — e nada mais denuncia.
    """
    from app.painel_agregado import MESES_PT

    assert MESES_PT == [
        "Jan",
        "Fev",
        "Mar",
        "Abr",
        "Mai",
        "Jun",
        "Jul",
        "Ago",
        "Set",
        "Out",
        "Nov",
        "Dez",
    ]
