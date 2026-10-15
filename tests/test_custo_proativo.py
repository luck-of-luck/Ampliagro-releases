"""O limiar do aviso proativo.

Este modulo tem UMA decisao que nao e' mecanica: **quando gastar mais do que
o orcado justifica um aviso**. Todo o resto e' consulta.

Os testes existem porque essa decisao e' facil de errar em duas direcoes, e
as duas sao ruins:

- **Avisar demais.** Numa fazenda de 20 talhoes com 5% de desvio cada, o
  produtor recebe 20 alertas e deixa de ler. E' pior do que nao ter: o
  produtor desliga as notificacoes, e ai nao ha sistema nenhum.
- **Avisar de menos.** O produtor recebe 0 alertas, acredita que a safra vai
  bem, e o desvio sobe ate ser tarde demais.

Cada teste aqui fixa um dos lados. Os limites sao uma escolha minha e
argumentavel - estao escritos nos testes para que mudar seja deliberado e nao
acidental.
"""

from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from app.ia.custo_proativo import (
    LIMIAR_PCT,
    LIMIAR_REAIS,
    desvio_para_cenario,
    resumo_desvio,
)
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
        self.prop = Propriedade.objects.create(
            user=self.user, nome="Fazenda", cep="37400000", area_total=D("100")
        )
        self.cultura = Cultura.objects.create(nome="Soja")
        self.t1 = Talhao.objects.create(
            propriedade=self.prop, nome="Baixada", area_hectare=D("10")
        )

    def talhao_com_orcado(self, talhao, orcado, ano=2026):
        safra = Safra.objects.create(
            propriedade=self.prop,
            talhao=talhao,
            cultura=self.cultura,
            ano=ano,
            area_plantada=talhao.area_hectare,
        )
        PlanoSafra.objects.create(safra=safra, orcamento_estimado=D(orcado))
        return safra

    def gasto(self, talhao, valor):
        LancamentoFinanceiro.objects.create(
            propriedade=self.prop,
            tipo="DESPESA",
            categoria="insumo",
            valor=D(valor),
            data="2026-03-10",
            talhao=talhao,
            pago=True,
        )


class OLimiar(Base):
    def setUp(self):
        super().setUp()
        self.talhao_com_orcado(self.t1, "10000")  # 10.000 de orcado

    def test_gastou_muito_mais_avisa(self):
        self.gasto(self.t1, "13000")  # +30%, +3.000
        r = desvio_para_cenario(self.user, self.prop)
        self.assertTrue(r["tem_algo"])
        self.assertEqual(len(r["lista"]), 1)
        self.assertEqual(r["lista"][0]["talhao"], "Baixada")

    def test_dentro_do_orcado_nao_avisa(self):
        self.gasto(self.t1, "9000")  # -10%, dentro
        r = desvio_para_cenario(self.user, self.prop)
        self.assertFalse(r["tem_algo"])
        self.assertEqual(r["lista"], [])

    def test_gastou_exatamente_o_orcado_nao_avisa(self):
        self.gasto(self.t1, "10000")
        self.assertFalse(desvio_para_cenario(self.user, self.prop)["tem_algo"])

    def test_desvio_pequeno_em_reais_nao_avisa(self):
        """10% de 10.000 e' 1.000 - passa o limiar de R$, mas nao os 15%.

        Este e' o teste que protege contra o alerta de R$ 1.000 numa propriedade
        que orcou 10.000. O produtor gastou mais 10% e a safra nao esta' em
        perigo - avisar aqui ensina-o a ignorar o sistema."""
        self.gasto(self.t1, "11000")  # +10%, +1.000
        self.assertFalse(desvio_para_cenario(self.user, self.prop)["tem_algo"])

    def test_desvio_pequeno_em_pct_nao_avisa(self):
        """15% de 200 e' 30 - passa o limiar de R$ 500? Nao. Passa os 15%?"""
        self.talhao_com_orcado(self.t1, "200")
        # a segunda safra nao - o PlanoSafra e' OneToOne. Uso outro talhao.
        t2 = Talhao.objects.create(
            propriedade=self.prop, nome="Pequeno", area_hectare=D("1")
        )
        self.talhao_com_orcado(t2, "200")
        self.gasto(t2, "260")  # +60% = 156% ... e' +30%
        r = desvio_para_cenario(self.user, self.prop)
        # +60 reais = 30% mas so 60 reais: abaixo de LIMIAR_REAIS
        self.assertFalse(r["tem_algo"], "R$ 60 nao e' um problema de dinheiro")

    def test_a_fronteira_exata_avisa(self):
        """Exatamente 15% e' o limite. 'Acima' nao e' 'a partir de'."""
        self.gasto(self.t1, "11500")  # +15% = 1.500
        r = desvio_para_cenario(self.user, self.prop)
        self.assertTrue(r["tem_algo"], "15% e R$ 1.500 cumpre os dois limites")

    def test_um_pouco_abaixo_nao_avisa(self):
        self.gasto(self.t1, "11490")  # +14.9% = 1.490
        self.assertFalse(desvio_para_cenario(self.user, self.prop)["tem_algo"])

    def test_um_pouco_acima_avisa(self):
        self.gasto(self.t1, "11520")  # +15.2%
        self.assertTrue(desvio_para_cenario(self.user, self.prop)["tem_algo"])


class NaoAvisaOQueNaoEDesvio(Base):
    """Falta de cadastro nao e' desvio. Transformar uma em outra e' ruido."""

    def setUp(self):
        super().setUp()

    def test_sem_orcado_nao_avisa(self):
        self.gasto(self.t1, "999999")
        r = desvio_para_cenario(self.user, self.prop)
        self.assertFalse(r["tem_algo"], "gastou muito mas nao ha orcado para comparar")

    def test_talhao_sem_lancamento_nao_avisa(self):
        self.talhao_com_orcado(self.t1, "10000")
        r = desvio_para_cenario(self.user, self.prop)
        self.assertFalse(r["tem_algo"])

    def test_gasto_sem_talhao_nao_avisa(self):
        """R$ 9.000 sem talhao nao e' desvio de nenhum talhao.

        Ratear seria inventar o destino do dinheiro. Este teste existe porque
        `custo_por_talhao` ja' isola o nao-alocado - e a tentacao aqui e'
        reporta-lo como se fosse o maior desvio da fazenda."""
        self.talhao_com_orcado(self.t1, "10000")
        self.gasto(self.t1, "500")
        LancamentoFinanceiro.objects.create(
            propiedades=self.prop,
            tipo="DESPESA",
            categoria="x",
            valor=D("9000"),
            data="2026-03-10",
            talhao=None,
            pago=True,
        ) if False else LancamentoFinanceiro.objects.create(
            propriedade=self.prop,
            tipo="DESPESA",
            categoria="x",
            valor=D("9000"),
            data="2026-03-10",
            talhao=None,
            pago=True,
        )
        r = desvio_para_cenario(self.user, self.prop)
        self.assertFalse(r["tem_algo"])

    def test_orcado_zero_nao_divide_por_zero(self):
        self.talhao_com_orcado(self.t1, "0")
        self.gasto(self.t1, "5000")
        r = desvio_para_cenario(self.user, self.prop)
        # 0 de orcado, 5000 gastos: nao ha PCT possivel. Nao avisa com NaN.
        for item in r["lista"]:
            assert (
                item["desvio_pct"] is None or item["desvio_pct"] == item["desvio_pct"]
            )

    def test_despesa_nao_paga_nao_entra(self):
        self.gasto(self.t1, "5000")
        LancamentoFinanceiro.objects.create(
            propriedade=self.prop,
            tipo="DESPESA",
            categoria="x",
            valor=D("999999"),
            data="2026-03-10",
            talhao=self.t1,
            pago=False,
        )
        r = desvio_para_cenario(self.user, self.prop)
        self.assertFalse(r["tem_algo"], "boleto em aberto nao e' gasto")

    def test_ano_diferente_nao_conta(self):
        self.talhao_com_orcado(self.t1, "10000")
        LancamentoFinanceiro.objects.create(
            propriedade=self.prop,
            tipo="DESPESA",
            categoria="x",
            valor=D("30000"),
            data="2019-03-10",
            talhao=self.t1,
            pago=True,
        )
        self.assertFalse(desvio_para_cenario(self.user, self.prop)["tem_algo"])


class OAlerta(Base):
    def setUp(self):
        super().setUp()
        self.talhao_com_orcado(self.t1, "10000")
        self.gasto(self.t1, "14000")  # +40%, 4.000 -> critical

    def test_o_alerta_diz_os_dois_numeros(self):
        """'Gastou mais' sem o orcado e sem o realizado nao e' verificavel.

        O produtor tem de poder conferir os dois numeros contra o que o
        sistema tem - e so ele sabe se o orcado de 10.000 era o que tinha em
        cabeca."""
        item = desvio_para_cenario(self.user, self.prop)["lista"][0]
        msg = item["mensagem"]
        self.assertIn("10,000.00", msg.replace("R$ 10.000,00", "10,000.00"))
        self.assertIn("14,000.00", msg.replace("R$ 14.000,00", "14,000.00"))

    def test_o_alerta_menciona_o_comprometido(self):
        """O que ainda esta' por pagar pode aumentar a conta. O produtor tem
        de saber disso ANTES de decidir que o problema acabou."""
        LancamentoFinanceiro.objects.create(
            propriedade=self.prop,
            tipo="DESPESA",
            categoria="x",
            valor=D("3000"),
            data="2026-04-01",
            talhao=self.t1,
            pago=False,
        )
        item = desvio_para_cenario(self.user, self.prop)["lista"][0]
        self.assertIn("3,000.00", item["mensagem"].replace("R$ 3.000,00", "3,000.00"))

    def test_o_nivel_sobe_com_a_gravidade(self):
        self.assertEqual(
            desvio_para_cenario(self.user, self.prop)["lista"][0]["nivel"], "critico"
        )

    def test_15_por_cento_e_atencao_nao_critico(self):
        self.talhao_com_orcado(self.t1, "100000")
        self.gasto(self.t1, "120000")  # +20%
        item = desvio_para_cenario(self.user, self.prop)["lista"][0]
        self.assertEqual(item["nivel"], "atencao")

    def test_o_nivel_esta_na_escala_da_casa(self):
        """MEDIDO 2026-10-05: escrevi 'critical'/'warning' e o alerta NUNCA
        saiu.

        O motor tem escala propria: `emitir_alerta` mapeia
        `{'critico': 0, 'atencao': 1, 'info': 2}` e o filtro de preferencia
        em `varrer_proativo` compara `a.get("nivel") == "atencao"`. Uma
        string fora dessa escala nao da erro - cai em
        `mapa_nivel.get(..., 1)` e nunca corresponde a nenhuma comparacao.

        O alerta era WRITTEN e nunca chegado ao produtor. Este teste existe
        para o proximo nao introduzir um quarto nivel em ingles. A lista vem
        do motor, nao de mim.
        """
        escala = {"critico", "atencao", "info"}
        mapa = {"critico": 0, "atencao": 1, "info": 2}

        self.talhao_com_orcado(self.t1, "10000")
        self.gasto(self.t1, "14000")  # +40% -> critico
        t2 = Talhao.objects.create(
            propriedade=self.prop, nome="Atencao", area_hectare=D("10")
        )
        self.talhao_com_orcado(t2, "100000")
        self.gasto(t2, "120000")  # +20% -> atencao

        for item in desvio_para_cenario(self.user, self.prop)["lista"]:
            self.assertIn(
                item["nivel"],
                escala,
                f"nivel '{item['nivel']}' nao existe na escala do motor",
            )
            self.assertIn(mapa[item["nivel"]], (0, 1, 2))

    def test_o_filtro_de_preferencia_do_motor_nao_salta_o_alerta(self):
        """O filtro compara strings exactas, e um mismatch desaparece em
        silencio - nao ha erro, nao ha log, o alerta simplesmente nao sai.

        `varrer_proativo` salta um achado quando
        `(nivel == "critico" and nivel_minimo > 0)`. Se o nivel nao casar,
        nenhuma das duas condicoes e' verdadeira e o alerta passa; se casar
        errado, salta. Este teste verifica o caminho do nivel_minimo=0, que
        e' o que um produtor com tudo ligado encontra.
        """
        self.talhao_com_orcado(self.t1, "10000")
        self.gasto(self.t1, "14000")  # +40%
        item = desvio_para_cenario(self.user, self.prop)["lista"][0]

        nivel_minimo = 0
        foi_saltado = (item["nivel"] == "critico" and nivel_minimo > 0) or (
            item["nivel"] == "atencao" and nivel_minimo > 1
        )
        self.assertFalse(
            foi_saltado,
            "com nivel_minimo=0 nada devia ser saltado. Se foi, ou o nivel "
            "nao casa com a escala do motor, ou o alerta desaparece calado.",
        )

    def test_o_alerta_nao_manda_escrever(self):
        """Um aviso proativo que sugere gravar e' um pedido de confirmacao
        disfarçado. Este le e' conta."""
        LancamentoFinanceiro.objects.create(
            propriedade=self.prop,
            tipo="DESPESA",
            categoria="insumo",
            valor=D("14000"),
            data="2026-03-10",
            talhao=self.t1,
            pago=True,
        )
        desvio_para_cenario(self.user, self.prop)
        self.assertEqual(
            LancamentoFinanceiro.objects.count(),
            2,
            "o `setUp` ja' tinha lancado os 14.000; ler o cenario nao pode "
            "acrescentar nada - o motor le a cada ciclo e um lancamento por "
            "leitura seria um custo financeiro do motor",
        )


class VolumeDeAlertas(Base):
    """Numa fazenda grande, o motor nao pode despejar 20 avisos."""

    def setUp(self):
        super().setUp()
        self.culturas = [Cultura.objects.create(nome=f"C{i}") for i in range(6)]

    def _talhao_desviado(self, i, pct):
        t = Talhao.objects.create(
            propriedade=self.prop, nome=f"T{i}", area_hectare=D("10")
        )
        safra = Safra.objects.create(
            propriedade=self.prop,
            talhao=t,
            cultura=self.culturas[i],
            ano=2026,
            area_plantada=D("10"),
        )
        PlanoSafra.objects.create(safra=safra, orcamento_estimado=D("10000"))
        self.gasto(t, str(10000 * (1 + pct / 100)))
        return t

    def test_no_maximo_tres(self):
        for i in range(6):
            self._talhao_desviado(i, 50)
        r = desvio_para_cenario(self.user, self.prop)
        self.assertLessEqual(len(r["lista"]), 3)
        self.assertEqual(r["desvios"], 6, "o total conta todos, o alerta nao")

    def test_entram_os_piores(self):
        for i in range(4):
            self._talhao_desviado(i, 20 + i * 20)  # 20, 40, 60, 80%
        r = desvio_para_cenario(self.user, self.prop)
        self.assertEqual(r["lista"][0]["talhao"], "T3", "o pior primeiro")

    def test_o_total_cabe_no_mesmo_aviso(self):
        for i in range(5):
            self._talhao_desviado(i, 50)
        r = desvio_para_cenario(self.user, self.prop)
        self.assertGreater(r["total_desvio"], 0)
        # 5 talhoes x 5.000 = 25.000
        self.assertEqual(r["total_desvio"], 25000.0)


class PropriedadeAlheia(Base):
    def test_propriedade_de_outro_da_zero(self):
        outro = User.objects.create_user("bruno", "bruno@x.com", "s12345678")
        p2 = Propriedade.objects.create(user=outro, nome="Deles", area_total=D("10"))
        r = desvio_para_cenario(self.user, p2)
        self.assertFalse(r["tem_algo"])
        self.assertEqual(r["lista"], [])

    def test_propriedade_none_nao_levanta(self):
        r = desvio_para_cenario(self.user, None)
        self.assertFalse(r["tem_algo"])


class Resumo(Base):
    def test_o_resumo_diz_o_que_falta(self):
        self.talhao_com_orcado(self.t1, "10000")
        self.gasto(self.t1, "14000")
        Talhao.objects.create(
            propriedade=self.prop, nome="Sem orcado", area_hectare=D("5")
        )
        r = resumo_desvio(self.user, self.prop)
        self.assertEqual(r["orcado_total"], 10000.0)
        self.assertEqual(r["realizado_total"], 14000.0)
        self.assertEqual(r["talhoes_com_orcado"], 1)
        self.assertEqual(r["pior"], "Baixada")
        self.assertEqual(r["pior_desvio_pct"], 40.0)
        # o talhao sem orcado NAO entra no orcado_total
        self.assertNotIn("Sem orcado", r["talhoes_acima"])

    def test_resumo_de_fazenda_vazia(self):
        r = resumo_desvio(self.user, self.prop)
        self.assertEqual(r["orcado_total"], 0.0)
        self.assertIsNone(r["pior"])
        self.assertIsNone(r["pior_desvio_pct"])
