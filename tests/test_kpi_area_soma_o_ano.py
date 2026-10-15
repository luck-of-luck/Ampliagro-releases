"""O cartão de área tem de responder à pergunta que faz, e denunciar o que não bate.

O DEFEITO
=========
`kpi-area` fazia ``safras.order_by("-ano").first()`` e devolvia a área de
UMA safra. A pergunta do cartão é "quanto terreno tenho neste ano", e a
resposta honesta é a SOMA das safras do ano.

O `.first()` sem desempate deixava o SQLite escolher a linha, e a escolha
mudava com o plano de execução. Na Fazenda Modelo (Primavera do Leste/MT)
isto significava:

    ordem A -> Feijão-carioca, 45.000 ha  (safra id=13, talhão de 15 ha)
    ordem B -> Trigo,             180 ha

O mesmo cartão, o mesmo banco, o mesmo produtor, dois números — e nenhum
dos dois era "a área da fazenda". Um produtor que lê 45.000 ha numa
propriedade de 1.240 ha tem de concluir que a app está louca; a app
responde que está certa.

O QUE ESTE TESTE TRAVA
======================
1. O cartão soma as safras do ANO, não uma linha solta.
2. O ano escolhido é DETERMINÍSTICO (o mais recente com safras registadas).
3. A área não soma entre anos — 210 ha não viram 630 ha.
4. Uma safra registada sem área não apaga a área das outras, e é contada.
5. Quando a soma das safras não bate com a área dos talhões, o cartão DIZ
   — com os dois números, para quem vai corrigir saber o que corrigir.
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from app.ia.palco import validar_estrutura
from app.ia.palco_dados import enriquece
from app.models import Cultura, Propriedade, Safra, Talhao

User = get_user_model()


class KpiAreaRespondeAPergunta(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("area_t", "area_t@t.com", "x")
        self.prop = Propriedade.objects.create(
            user=self.user,
            nome="Fazenda",
            cidade="Muzambinho",
            uf="MG",
            area_total=Decimal("1240.00"),
        )
        self.c_soja = Cultura.objects.create(nome="Soja")
        self.c_trigo = Cultura.objects.create(nome="Trigo")
        self.c_milho = Cultura.objects.create(nome="Milho")
        self.talhao = Talhao.objects.create(
            propriedade=self.prop, nome="Talhão A", area_hectare=Decimal("500.00")
        )

    def _safra(self, cultura, ano, area, talhao=None, colhida=None):
        return Safra.objects.create(
            propriedade=self.prop,
            cultura=cultura,
            ano=ano,
            area_plantada=Decimal(str(area)),
            area_colhida=Decimal(str(colhida)) if colhida is not None else None,
            talhao=talhao,
        )

    def _kpi_area(self):
        ws = validar_estrutura([{"tipo": "kpi-area"}])[0]
        out = enriquece(self.user, [dict(w) for w in ws], prop=self.prop)
        return out[0].get("config") or {}

    # ───────────────────────────────────────────────────────────────────
    # 1. Soma o ano, não uma linha
    # ───────────────────────────────────────────────────────────────────
    def test_soma_as_safras_do_ano_e_nao_devolve_uma_linha(self):
        """Dez culturas no mesmo ano são um total, não a primeira da lista.

        Este é o teste que apanha o defeito. Com uma safra só, tanto a soma
        como o `.first()` dão o mesmo número — e é por isso que o bug
        passou com a suíte verde.
        """
        self._safra(self.c_soja, 2026, 200.0, self.talhao)
        self._safra(self.c_trigo, 2026, 180.0, self.talhao)
        self._safra(self.c_milho, 2026, 150.5, self.talhao)

        cfg = self._kpi_area()
        self.assertEqual(
            cfg["area_plantada"],
            530.5,
            "o cartão tem de somar as safras do ano, não devolver uma delas",
        )
        self.assertEqual(cfg["ano"], 2026)
        self.assertEqual(cfg["safras_no_ano"], 3)

    def test_um_valor_absurdo_nao_e_o_unico_que_aparece(self):
        """A safra corrompida de 45.000 ha não pode ser a resposta.

        Este é o caso real da Fazenda Modelo: uma safra de 45.000 ha apontada
        para um talhão de 15 ha. Antes, o cartão dizia 45.000. Agora diz a
        soma — que inclui o valor corrompido, porque o cartão não decide o
        que é verdade — e DIZ QUE HÁ DIVERGÊNCIA, para que a linha má
        possa ser encontrada e corrigida por quem conhece a fazenda.
        """
        self._safra(self.c_soja, 2026, 45_000.0, self.talhao)
        self._safra(self.c_trigo, 2026, 180.0, self.talhao)

        cfg = self._kpi_area()
        self.assertEqual(cfg["area_plantada"], 45_180.0)
        # E a divergência contra o talhão (500 ha) tem de estar lá.
        self.assertIsNotNone(
            cfg.get("divergencia_area"),
            "45.180 ha de safras contra 500 ha de talhão, e o cartão não "
            "disse nada. O produtor fica com um número impossível e nenhum "
            "aviso.",
        )
        div = cfg["divergencia_area"]
        self.assertEqual(div["area_safras"], 45_180.0)
        self.assertEqual(div["area_talhoes"], 500.0)
        self.assertIn("errada", div["aviso"])

    # ───────────────────────────────────────────────────────────────────
    # 2. O ano é determinístico
    # ───────────────────────────────────────────────────────────────────
    def test_o_ano_escolhido_e_o_mais_recente_com_safras(self):
        self._safra(self.c_soja, 2024, 420.0, self.talhao)
        self._safra(self.c_milho, 2025, 380.0, self.talhao)
        self._safra(self.c_trigo, 2026, 180.0, self.talhao)

        cfg = self._kpi_area()
        self.assertEqual(cfg["ano"], 2026)
        self.assertEqual(cfg["area_plantada"], 180.0)

    def test_o_ano_escolhido_nao_depende_da_ordem_do_banco(self):
        """Criar as safras por ordem decrescente não muda a resposta.

        Sem um desempate explícito no `order_by`, "o ano mais recente" podia
        mudar com o plano de execução. Este teste grava a safras por ordem
        inversa à cronológica — que é a ordem em que um `.first()` sem
        critério erra.
        """
        self._safra(self.c_soja, 2026, 180.0, self.talhao)
        self._safra(self.c_milho, 2025, 380.0, self.talhao)
        self._safra(self.c_trigo, 2024, 420.0, self.talhao)

        cfg = self._kpi_area()
        self.assertEqual(cfg["ano"], 2026)
        self.assertEqual(cfg["area_plantada"], 180.0)

    # ───────────────────────────────────────────────────────────────────
    # 3. A área não se acumula entre anos
    # ───────────────────────────────────────────────────────────────────
    def test_a_area_nao_soma_entre_anos(self):
        """210 ha de café em três anos continuam a ser 210 ha.

        Este é o contrato que o `kpi-area` já honrava e que a correção não
        pode perder: terreno não se acumula. A mesma terra colhida três anos
        seguidos é a mesma terra.
        """
        self._safra(self.c_soja, 2024, 210.0, self.talhao)
        self._safra(self.c_soja, 2025, 210.0, self.talhao)
        self._safra(self.c_soja, 2026, 210.0, self.talhao)

        cfg = self._kpi_area()
        self.assertEqual(
            cfg["area_plantada"],
            210.0,
            "a área somou entre anos: 210 ha viraram 630. A mesma terra "
            "três vezes é a mesma terra.",
        )

    # ───────────────────────────────────────────────────────────────────
    # 4. Registos incompletos
    # ───────────────────────────────────────────────────────────────────
    def test_o_ano_de_refincia_ignora_safras_com_ano_nulo(self):
        """Uma safra sem ano não pode decidir qual é o ano de referência.

        `Safra.ano` é NOT NULL, então o caso não nasce por INSERT — mas
        `_calcula` filtra `exclude(ano=None)` justamente porque um `NULL`
        pode entrar por importação, por `bulk_create` sem validação, ou por
        uma migração. Sem esse filtro, `order_by("-ano")` em SQLite põe o
        NULL primeiro ou por último conforme a versão, e o cartão mudava de
        ano conforme a instalação.
        """
        import inspect

        from app.ia.palco_dados import _calcula

        fonte = inspect.getsource(_calcula)
        self.assertIn(
            "exclude(ano=None)",
            fonte,
            "a escolha do ano deixou de ignorar safras sem ano: o cartão "
            "pode passar a responder por um ano que não é o mais recente.",
        )

    def test_a_area_do_ano_soma_todas_as_safras_registadas(self):
        """A soma tem de incluir as safras com `area_plantada` a zero.

        `area_plantada` é NOT NULL, mas pode ser 0.00 (uma safra aberta sem
        área preenchida). Esconder a linha faria o total do ano descer sem
        que ninguém soubesse porquê — e `safras_no_ano` existe precisamente
        para tornar isso auditável.
        """
        self._safra(self.c_soja, 2026, 200.0, self.talhao)
        self._safra(self.c_trigo, 2026, 0.0, self.talhao)
        self._safra(self.c_milho, 2026, 180.0, self.talhao)

        cfg = self._kpi_area()
        self.assertEqual(cfg["area_plantada"], 380.0)
        self.assertEqual(
            cfg["safras_no_ano"],
            3,
            "uma safra registada desapareceu da contagem.",
        )

    # ───────────────────────────────────────────────────────────────────
    # 5. A divergência só grita quando é grande
    # ───────────────────────────────────────────────────────────────────
    def test_arredondamento_nao_e_acusado_de_erro(self):
        """Diferenças de centésimos não são divergência.

        Se o cartão gritasse por 0,02 ha o produtor learnia a ignorar o
        aviso — e o aviso que importa (44.985 ha) deixava de ser lido.
        """
        self.talhao.area_hectare = Decimal("200.02")
        self.talhao.save(update_fields=["area_hectare"])
        self._safra(self.c_soja, 2026, 200.0, self.talhao)

        cfg = self._kpi_area()
        self.assertIsNone(
            cfg.get("divergencia_area"),
            "uma diferença de centésimos foi tratada como cadastro errado.",
        )

    def test_safras_sem_talhao_nao_produzem_uma_area_de_talhoes_inventada(self):
        """Sem talhão ligado, não há contra-o-que conferir.

        Dizer "a área dos talhões é 0" seria uma afirmação: a área é zero, e
        isso faria o produtor suspectar do cadastro inteiro. O que se sabe é
        que não há talhão — e isso é `None`, não 0.
        """
        self._safra(self.c_soja, 2026, 200.0, None)

        cfg = self._kpi_area()
        self.assertIsNone(cfg.get("area_talhoes"))
        self.assertIsNone(cfg.get("divergencia_area"))

    # ───────────────────────────────────────────────────────────────────
    # 6. Ausência continua a ser ausência
    # ───────────────────────────────────────────────────────────────────
    def test_sem_safras_o_cartao_nao_inventa_zero(self):
        """Sem safras, `sem_dado` — não 0 ha.

        Um 0 ha num cartão de área afirma que a fazenda está vazia. A
        verdade é que ninguém registou safra.
        """
        cfg = self._kpi_area()
        self.assertNotIn("area_plantada", cfg)
        self.assertEqual(cfg.get("fonte_dado"), "sem_dado")
