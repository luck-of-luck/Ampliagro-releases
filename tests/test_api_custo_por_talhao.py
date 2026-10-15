"""A porta do orcado x realizado.

O servico `app/services/custo_talhao.py` fazia a conta e nao havia caminho HTTP
para ela. Estes testes tratam a porta, e sobretudo tratam do que a porta NAO
deve deixar passar: um produtor ver a conta de outro.

`tests/test_custo_por_talhao.py` guarda a CONTA. Aqui guardo o ACESSO.
"""

from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from app.models import (
    Cultura,
    LancamentoFinanceiro,
    PlanoSafra,
    Propriedade,
    Safra,
    Talhao,
)

D = Decimal


class Base(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("ana", "ana@x.com", "s12345678")
        self.outro = User.objects.create_user("bruno", "bruno@x.com", "s12345678")
        self.prop = Propriedade.objects.create(
            user=self.user, nome="Fazenda Boa", cep="37400000", area_total=D("30")
        )
        self.cultura = Cultura.objects.create(nome="Soja")
        self.t1 = Talhao.objects.create(
            propriedade=self.prop, nome="Baixada", area_hectare=D("10")
        )
        self.t2 = Talhao.objects.create(
            propriedade=self.prop, nome="Cercado", area_hectare=D("20")
        )
        self.client.force_login(self.user)

    def despesa(self, talhao, valor, pago=True, data="2026-03-10"):
        return LancamentoFinanceiro.objects.create(
            propriedade=self.prop,
            tipo="DESPESA",
            categoria="insumo",
            valor=D(valor),
            data=data,
            talhao=talhao,
            pago=pago,
        )


class AResposta(Base):
    def test_a_url_responde_json(self):
        r = self.client.get(reverse("api_custo_por_talhao"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Content-Type"].split(";")[0], "application/json")

    def test_devolve_as_linhas_dos_talhoes(self):
        self.despesa(self.t1, "1000")
        r = self.client.get(reverse("api_custo_por_talhao"))
        d = r.json()
        self.assertEqual(len(d["linhas"]), 2)
        nomes = {l["talhao"] for l in d["linhas"]}
        self.assertEqual(nomes, {"Baixada", "Cercado"})

    def test_o_dinheiro_chega_certainho(self):
        self.despesa(self.t1, "1000")
        d = self.client.get(reverse("api_custo_por_talhao")).json()
        self.assertEqual(d["total_despesa"], 1000.0)

    def test_o_payload_sobrevive_a_json(self):
        """`json.dumps` nao conhece `Decimal`. Um `Decimal` a mais e' um 500."""
        import json

        self.despesa(self.t1, "1000")
        self.despesa(self.t2, "250.5")
        json.dumps(self.client.get(reverse("api_custo_por_talhao")).json())

    def test_tem_dados_diz_que_a_fazenda_esta_vazia(self):
        d = self.client.get(reverse("api_custo_por_talhao")).json()
        self.assertFalse(d["tem_dados"])
        self.assertEqual(d["total_despesa"], 0.0)

    def test_tem_dados_vira_verdade_quando_ha_lancamento(self):
        self.despesa(self.t1, "1000")
        d = self.client.get(reverse("api_custo_por_talhao")).json()
        self.assertTrue(d["tem_dados"])

    def test_o_orcado_via_na_mesma_resposta(self):
        """O ecrã compara os dois lados. Nao faz sentido ter de fazer 2 pedidos."""
        safra = Safra.objects.create(
            propriedade=self.prop,
            talhao=self.t1,
            cultura=self.cultura,
            ano=2026,
            area_plantada=D("10"),
            receita_estimada=D("50000"),
        )
        PlanoSafra.objects.create(safra=safra, orcamento_estimado=D("20000"))
        self.despesa(self.t1, "25000")

        linha = next(
            l
            for l in self.client.get(reverse("api_custo_por_talhao")).json()["linhas"]
            if l["talhao"] == "Baixada"
        )
        self.assertEqual(linha["orcado"], 20000.0)
        self.assertEqual(linha["desvio"], 5000.0)
        self.assertEqual(linha["desvio_pct"], 25.0)


class Pendencias(Base):
    """O bloco que diz o que falta preencher.

    Sem isto a tela mostra uma coluna vazia e o produtor nao sabe se ha
    trabalho por fazer. `None` e' honesto para quem le; para quem tem de
    preencher, e' invisivel.
    """

    def test_diz_que_falta_orcadar(self):
        self.despesa(self.t1, "1000")
        p = self.client.get(reverse("api_custo_por_talhao")).json()["pendencias"]
        self.assertEqual(sorted(p["talhoes_sem_orcado"]), ["Baixada", "Cercado"])

    def test_diz_que_ha_despesa_sem_talhao(self):
        self.despesa(None, "9000")
        p = self.client.get(reverse("api_custo_por_talhao")).json()["pendencias"]
        self.assertEqual(p["nao_alocado_registros"], 1)
        self.assertEqual(p["nao_alocado_despesa"], 9000.0)

    def test_diz_que_ha_talhoes_sem_lancamento(self):
        self.despesa(self.t1, "100")
        p = self.client.get(reverse("api_custo_por_talhao")).json()["pendencias"]
        self.assertEqual(p["talhoes_sem_lancamento"], ["Cercado"])

    def test_diz_o_que_esta_pendente_de_pagamento(self):
        self.despesa(self.t1, "5000", pago=False)
        p = self.client.get(reverse("api_custo_por_talhao")).json()["pendencias"]
        self.assertEqual(p["comprometido_total"], 5000.0)

    def test_o_pendente_nao_entra_no_realizado(self):
        self.despesa(self.t1, "5000", pago=False)
        d = self.client.get(reverse("api_custo_por_talhao")).json()
        self.assertEqual(d["total_despesa"], 0.0)


class Isolamento(Base):
    """A razao de ser deste ficheiro."""

    def test_propriedade_alheia_da_404(self):
        p_alheia = Propriedade.objects.create(
            user=self.outro, nome="Deles", area_total=D("10")
        )
        t = Talhao.objects.create(
            propriedade=p_alheia, nome="Deles", area_hectare=D("5")
        )
        LancamentoFinanceiro.objects.create(
            propriedade=p_alheia,
            tipo="DESPESA",
            categoria="x",
            valor=D("999999"),
            data="2026-03-10",
            talhao=t,
            pago=True,
        )

        r = self.client.get(reverse("api_custo_por_talhao"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["total_despesa"], 0.0)
        nomes = {l["talhao"] for l in r.json()["linhas"]}
        self.assertEqual(nomes, {"Baixada", "Cercado"})

    def test_pedir_a_propriedade_de_outro_da_403_pelo_middleware(self):
        """403, e NAO 404. A politica e' do middleware, e e' deliberada.

        Escrevi este teste a espera de 404, por ser o que costuma achar-se
        correcto. O codigo da casa diz o contrario, e com razao
        (`app/middleware.py:30`): *"404 vs 403: um id inexistente e' 404, um id
        de outra pessoa e' 403"*. Este endpoint e' de leitura, dentro de
        `/api/`, e o multi-tenant responde antes da view.

        Um 403 **nao** confirma a existencia do recurso para quem nao e' dono: so
        confirma que o pedido foi correctamente autenticado e autorizado. E o
        que esta a proteger e' o talhao, nao a propriedade - e o talhao nunca
        aparece na resposta. Escrevi 404 porque era a minha conviccao; escrevo
        403 porque e' a politica do Ampliagro e a minha conviccao nao decide
        aqui.
        """
        p_alheia = Propriedade.objects.create(
            user=self.outro, nome="Deles", area_total=D("10")
        )
        r = self.client.get(
            reverse("api_custo_por_talhao"), {"propriedade_id": p_alheia.id}
        )
        self.assertEqual(r.status_code, 403)
        # E o dado alheio nao aparece em lado nenhum.
        self.assertNotIn("Deles", r.content.decode())

    def test_propriedade_inexistente_da_200_com_a_primeira_do_produtor(self):
        """200, e nao 404. Comportamento do middleware, e e' deliberado.

        MEDIDO 2026-10-05. Escrevi este teste a espera de 404 e ele deu 200.
        A razao esta em `app/middleware.py:233-248`: quando um
        `?propriedade_id` aponta para algo que nao existe, o middleware
        APAGA o parametro e cai no fallback 'primeira propriedade do
        produtor'. `request.ids_inexistentes` fica registado para a tela.

        Escrevi 404 porque e' o que se espera de uma REST API. Esta casa
        escolheu outra coisa, e a escolha tem razao: um 404 confirmaria que
        'existe uma propriedade 7 que nao e' tua'. Um 200 com a tua
        propriedade nao diz nada sobre ninguem.

        Portanto este teste fixa o COMPORTAMENTO DE CASA, nao o meu palpite.
        Nao estou a dizer que 404 estaria errado - estou a dizer que mudar
        isso e' mexer no middleware, e nao neste endpoint.
        """
        r = self.client.get(reverse("api_custo_por_talhao"), {"propriedade_id": 999999})
        self.assertEqual(r.status_code, 200)
        nomes = {l["talhao"] for l in r.json()["linhas"]}
        self.assertEqual(nomes, {"Baixada", "Cercado"})

    def test_desligado_da_403(self):
        self.client.logout()
        r = self.client.get(reverse("api_custo_por_talhao"))
        self.assertIn(r.status_code, (401, 403))

    def test_duas_propriedades_ficam_separadas(self):
        p2 = Propriedade.objects.create(
            user=self.user, nome="Segunda", area_total=D("5")
        )
        t2 = Talhao.objects.create(propriedade=p2, nome="La", area_hectare=D("5"))
        self.despesa(self.t1, "100")
        LancamentoFinanceiro.objects.create(
            propriedade=p2,
            tipo="DESPESA",
            categoria="x",
            valor=D("700"),
            data="2026-03-10",
            talhao=t2,
            pago=True,
        )

        d = self.client.get(
            reverse("api_custo_por_talhao"), {"propriedade_id": p2.id}
        ).json()
        self.assertEqual({l["talhao"] for l in d["linhas"]}, {"La"})
        self.assertEqual(d["total_despesa"], 700.0)


class Filtros(Base):
    def test_ano_filtra(self):
        self.despesa(self.t1, "1000", data="2025-03-10")
        self.despesa(self.t1, "4000", data="2026-03-10")

        r = self.client.get(reverse("api_custo_por_talhao"), {"ano": 2026})
        self.assertEqual(r.json()["total_despesa"], 4000.0)

    def test_ano_aceita_o_mesmo_ano_de_safra(self):
        """`ano` e' o ano da safra; o filtro e' sobre a DATA do lancamento."""
        self.despesa(self.t1, "1000", data="2026-08-01")
        r = self.client.get(reverse("api_custo_por_talhao"), {"ano": 2026})
        self.assertEqual(r.json()["total_despesa"], 1000.0)

    def test_ano_invalido_da_400_e_nao_500(self):
        r = self.client.get(reverse("api_custo_por_talhao"), {"ano": "ano"})
        self.assertEqual(r.status_code, 400)
        self.assertIn("erro", r.json())

    def test_propriedade_invalida_da_400(self):
        r = self.client.get(reverse("api_custo_por_talhao"), {"propriedade_id": "abc"})
        self.assertEqual(r.status_code, 400)

    def test_ano_ausente_agrega_tudo(self):
        self.despesa(self.t1, "1000", data="2025-03-10")
        self.despesa(self.t1, "4000", data="2026-03-10")
        d = self.client.get(reverse("api_custo_por_talhao")).json()
        self.assertEqual(d["total_despesa"], 5000.0)


class SoLeitura(Base):
    """Um GET nao pode escrever. Nem um POST."""

    def test_post_da_405(self):
        self.despesa(self.t1, "1000")
        r = self.client.post(reverse("api_custo_por_talhao"), {})
        self.assertEqual(r.status_code, 405)
        self.assertEqual(LancamentoFinanceiro.objects.count(), 1)

    def test_get_nao_cria_nada(self):
        self.client.get(reverse("api_custo_por_talhao"))
        self.assertEqual(LancamentoFinanceiro.objects.count(), 0)


class NaoSombreado(Base):
    """O endpoint nao pode ficar escondido por outra rota.

    MEDIDO 2026-10-05: `path("estoque/", ...)` declarado DEPOIS de
    `router.register()` sombreava o router - a leitura funcionava e a escrita
    nao, sem nenhum erro. O sintoma era 'a API devolve 200 mas nao faz nada'.
    A mesma classe de bug aqui seria `custo-producao` a engolir `custo-talhao`.
    """

    def test_a_url_resolve_para_a_our_view(self):
        """O `__name__` do resolver e' `view` para TODAS as `@api_view` do DRF.

        MEDIDO 2026-10-05. O `@api_view` embrulha a funcao numa classe
        `WrappedAPIView`, e o `func` que o resolver devolve chama-se `view` -
        igual para aCosts de custo, a de safras e a de talhoes. Comparar
        `__name__` dava `view == view` e o teste passava sem verificar nada,
        que e' pior do que nao ter teste.

        O que distingue sao o modulo de origem e o nome da classe embrulhada.
        """
        from django.urls import resolve

        from app.api.views import custo_talhao_view

        m = resolve("/api/financeiro/custo-talhao/")
        cls = getattr(m.func, "cls", None)
        self.assertIsNotNone(cls, "o resolver nao devolveu uma view DRF")
        self.assertIs(
            cls.__module__,
            custo_talhao_view.__name__,
            "a rota aponta para outro modulo: ou o `path` foi mal colocado, "
            "ou outra view foi registada em cima desta",
        )

    def test_a_url_de_custo_producao_continua_a_ser_a_outra(self):
        from django.urls import resolve

        da_custo_talhao = resolve("/api/financeiro/custo-talhao/").func.cls
        da_custo_prod = resolve("/api/financeiro/custo-producao/").func.cls
        self.assertIsNot(
            da_custo_talhao,
            da_custo_prod,
            "`custo-talhao` e `custo-producao` estao a cair na mesma view: "
            "uma delas foi sombreada",
        )
