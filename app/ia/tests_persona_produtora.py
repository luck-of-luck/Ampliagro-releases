"""A simulação de um produtor real encontrou coisas que os testes não apanham.

Estes quatro testes existem porque um produtor de café em Muzambinho, com
três safras registadas, encontrou quatro defeitos que nenhuma suite unidade
via. Nenhum deles é exótico: são o tipo de coisa que acontece quando alguém
não pensou no ano errado.

O que os une é a mesma pergunta, feita de quatro maneiras: **este número é
dele?**

  1. Um ficheiro com 468 métricas inventadas servidas como suas, com a
     CLAUSULA de que qualquer falha de rede as servia.
  2. A área da fazenda somada entre anos: 210 ha viravam 630.
  3. Apagar uma cultura do catálogo levava as safras em silêncio.
  4. Números de exemplo escondidos em `getWidgetDataFromAPI`.
"""

from __future__ import annotations

import json
import pathlib
import re
from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.db.models import ProtectedError
from django.test import TestCase

from app.ia.palco_dados import enriquece

RAIZ = pathlib.Path(__file__).resolve().parents[2]


def _cafe():
    """A cultura 'Café', criada aqui e não importada do catálogo.

    Depender de dados semeados por uma migration é depender de outra pessoa.
    A base de teste não tem as 708 culturas da base de desenvolvimento, e um
    `next(...)` sem resultado dá `StopIteration` — uma falha que aponta para
    o catálogo em vez de apontar para o código.
    """
    from app.models import Cultura

    nome = "Caf" + "é"
    c, _ = Cultura.objects.get_or_create(nome=nome, defaults={"grupo": "graos"})
    return c


# ---------------------------------------------------------------------------
# 1. A FÁBRICA DE NÚMEROS
# ---------------------------------------------------------------------------
class NaoSeInventamMetricas(TestCase):
    """A simulação: um produtor de café viu "Receita Estimada: R$ 18,5 M".

    Esse número vinha de `culture-metrics-fallback.json` — 79 culturas, 468
    valores — e havia DOIS caminhos que o serviam. O que importa é o segundo:
    o `catch` do pedido real. Uma falha de rede, um timeout, um 500, uma
    sessão expirada: qualquer um deles transformava-se num painel de números
    inventados com a mesma aparência dos verdadeiros.

    Um `catch` que enche o vazio com números plausíveis é a pior classe de
    defeito que existe, porque não dá erro — dá uma decisão errada.
    """

    def test_o_ficheiro_dos_numeros_inventados_nao_existe(self):
        f = RAIZ / "app/static/data/culture-metrics-fallback.json"
        self.assertFalse(
            f.exists(),
            "O ficheiro de métricas de exemplo voltou. Ele servia 468 números "
            "fixos como se fossem da fazenda de quem está a ver.",
        )

    def test_o_caminho_de_erro_nao_devolve_numeros(self):
        t = (RAIZ / "app/static/js/data-provider.js").read_text(encoding="utf-8")
        # `getFallbackMetrics` tem de devolver `null`, sempre.
        m = re.search(
            r"function getFallbackMetrics\(cultureId\)\s*\{\s*return ([^;]+);", t
        )
        self.assertIsNotNone(m, "getFallbackMetrics sumiu ou mudou de forma")
        self.assertEqual(
            m.group(1).strip(),
            "null",
            "getFallbackMetrics voltou a devolver métricas de exemplo.",
        )
        # e nenhuma das funções que as servia pode existir
        for nome in ("loadFallback", "fallbackData", "getGenericDefaultMetrics"):
            self.assertNotIn(
                nome,
                t,
                f"{nome} voltou: era parte da cadeia que servia números inventados.",
            )

    def test_ha_um_estado_para_indisponivel(self):
        """Não ler não é a mesma coisa que não haver.

        "Sem dados" diz ao produtor que vá ao cadastro — e é accionável.
        "Não consegui ler" diz que o problema é da ligação, e mostrar "sem
        dados" seria MENTIR-LHE que o trabalho dele desapareceu.
        """
        t = (RAIZ / "app/static/js/data-provider.js").read_text(encoding="utf-8")
        self.assertIn("buildUnavailableResult", t)
        self.assertIn("indisponivel", t)

    def test_o_ultimo_recurso_inline_tambem_saiu(self):
        """`CULTURE_METRICS.default` no template era o último recurso.

        Estava no `index.html` que TODOS carregam, e era o número de exemplo
        de qualquer cultura quando a API falhava.

        MEDIDO 2026-10-05. `var CULTURE_METRICS = {}` esta em
        `pagina-index.js:1563`, e no `index.html` sao **zero** ocorrencias —
        a logica saiu do template no mesmo refactor que levou
        `_filtrarParaProdutor` e `clonePresetWidgets`. O `index.html:1714`
        carrega o JS, portanto a proteccao continua a valer para quem abre a
        pagina.

        Os numeros `1.450,00` e `12.750` aparecem no JS, mas **dentro de
        comentarios** que documentam a remocao. E' para isso que o filtro de
        comentarios abaixo existe: um teste que lesse o texto cru acusaria o
        proprio registo da correccao.
        """
        h = (RAIZ / "app/static/js/pagina-index.js").read_text(encoding="utf-8")
        self.assertIn("var CULTURE_METRICS = {}", h)
        # fora do comentario que documenta a remocao: o numero vive la como
        # prova do que saiu, e um teste que le a nota falha sem que exista
        # nenhum numero.
        codigo = "\n".join(
            l for l in h.splitlines() if not l.strip().startswith(("//", "*", "/*"))
        )
        for numero in ("18,5M", "12.750", "1.450,00"):
            self.assertNotIn(
                numero,
                codigo,
                f"'{numero}' voltou ao template. Havia um número de exemplo "
                f"em todas as linhas do recurso final.",
            )

    def test_get_widget_data_nao_tem_numeros_de_exemplo(self):
        """O segundo foco, noutro ficheiro.

        `getWidgetDataFromAPI` tinha `|| '12,5%'`, `|| 'R$ 450'`, `|| '28°C'`.
        O `||` dispara quando a API não traz o widget — e o resultado é um
        número plausível com a cara de um número medido.
        """
        t = (RAIZ / "app/static/js/tabs/dashboard-desktop.js").read_text(
            encoding="utf-8"
        )
        corpo = t[t.index("window.getWidgetDataFromAPI") :][:2600]
        # fora do comentário que documenta a remoção
        sem_comentario = "\n".join(
            l for l in corpo.splitlines() if not l.strip().startswith(("*", "/*", "//"))
        )
        for numero in ("12,5%", "R$ 450", "28°C", "R$ 8,2K", "0 alertas", "0 OS"):
            self.assertNotIn(
                numero,
                sem_comentario,
                f"getWidgetDataFromAPI voltou a ter {numero!r} como resposta.",
            )


# ---------------------------------------------------------------------------
# 2. A ÁREA SOMADA ENTRE ANOS
# ---------------------------------------------------------------------------
class AreaNaoSeSomaEntreAnos(TestCase):
    """210 ha de café, três safras registadas, e a página dizia 630.

    `_soma(safras, "area_plantada")` somava a área de todas as safras.
    Terreno não se acumula: a mesma terra, três anos, é a mesma terra. E
    `area_downtime` passava a ser uma métrica inventada (630 − 456 = 174 ha
    "em downtime") que não existe em lado nenhum.

    Isto só aparece com mais de uma safra. Um teste com um ano só passa — e
    é por isso que só uma persona com histórico real o apanha.
    """

    def setUp(self):
        from app.models import Propriedade, Safra

        self.u = User.objects.create_user(username="cafe", password="x")
        self.p = Propriedade.objects.create(
            user=self.u,
            nome="Sítio",
            cidade="Muzambinho",
            uf="MG",
            area_total=Decimal("340"),
        )
        self.cafe = _cafe()
        for ano, prod, colhida in (
            (2024, 62_000, 228),
            (2025, 58_500, 228),
            (2026, None, 0),
        ):
            Safra.objects.create(
                propriedade=self.p,
                cultura=self.cafe,
                ano=ano,
                area_plantada=Decimal("210"),
                area_colhida=Decimal(str(colhida)),
                producao_total=Decimal(str(prod)) if prod else None,
                data_colheita=date(ano, 7, 15) if prod else None,
            )

    def _widget(self, tipo):
        return enriquece(self.u, [{"tipo": tipo}])[0].get("config") or {}

    def test_a_area_plantada_e_a_da_ultima_safra(self):
        cfg = self._widget("kpi-area")
        self.assertEqual(
            cfg.get("area_plantada"),
            210.0,
            f"A área foi somada entre anos: {cfg.get('area_plantada')}. O "
            f"produtor tem 210 ha, não 630.",
        )

    def test_a_area_colhida_tambem(self):
        cfg = self._widget("kpi-area")
        self.assertEqual(
            cfg.get("area_colhida"),
            0.0,
            f"A área colhida foi somada entre anos: {cfg.get('area_colhida')}. A "
            f"de 2026 é zero porque ainda não se colheu.",
        )

    def test_a_area_diz_de_que_ano_e(self):
        """Sem o ano, "210 ha" não quer dizer nada."""
        cfg = self._widget("kpi-area")
        self.assertEqual(cfg.get("ano"), 2026)

    def test_downtime_nasce_de_um_numero_que_existe(self):
        """A métrica derivada tem de sair de duas áreas reais.

        Com a soma, `downtime` era 174 ha — uma diferença entre dois números
        inventados, que é a pior das instruções: parece medida, não é.
        """
        cfg = self._widget("kpi-area")
        if cfg.get("area_downtime") is not None:
            plantada = cfg.get("area_plantada")
            colhida = cfg.get("area_colhida")
            self.assertAlmostEqual(
                cfg["area_downtime"], max(0.0, plantada - colhida), places=2
            )

    def test_a_producao_continua_a_somar(self):
        """A produção SOMA-SE. A área, não.

        62.000 + 58.500 são 120.500 kg em dois anos — uma soma com resposta.
        Tratar as duas com a mesma regra é que produz o 630 ha.
        """
        cfg = self._widget("kpi-produtividade")
        self.assertEqual(cfg.get("producao_total"), 120_500.0)

    def test_a_area_do_periodo_nao_se_confunde_com_a_da_fazenda(self):
        """Dois widgets, mesmo nome de campo, significados diferentes.

        O produtor via "228 ha" no cartão de área e "456 ha" no de
        produtividade, e nenhum dos dois mentia — mas nenhum se explicava.
        Por isso o campo do período chama-se `area_colhida_periodo`.
        """
        cfg = self._widget("kpi-produtividade")
        self.assertEqual(cfg.get("area_colhida_periodo"), 456.0)
        self.assertNotIn(
            "area_colhida",
            cfg,
            "O nome voltou a ser o da fazenda, que é o que se confundia.",
        )
        self.assertEqual(cfg.get("anos"), [2024, 2025])


# ---------------------------------------------------------------------------
# 3. A CASCATA QUE APAGAVA SAFRAS
# ---------------------------------------------------------------------------
class ApagarCulturaNaoApagaSafra(TestCase):
    """Um `admin` apagava "Café" da lista e levava três anos de colheita.

    `Safra.cultura` estava em `CASCADE`. Sem aviso, sem cópia, sem como
    desfazer — e `Talhao.cultura_atual` estava em `SET_NULL`, o oposto, para a
    mesma relação. A incoerência entre as duas é o que torna o bug plausível
    durante anos: ninguém lê um `CASCADE` e duvida, e ninguém sabe qual dos
    dois lados do par está certo sem ir ver.
    """

    def setUp(self):
        from app.models import Propriedade, Safra

        self.u = User.objects.create_user(username="cafe2", password="x")
        self.p = Propriedade.objects.create(
            user=self.u,
            nome="Sítio",
            cidade="Muzambinho",
            uf="MG",
            area_total=Decimal("340"),
        )
        self.cafe = _cafe()
        self.safra = Safra.objects.create(
            propriedade=self.p,
            cultura=self.cafe,
            ano=2025,
            area_plantada=Decimal("210"),
        )

    def _todas_as_relacoes_que_apagam(self):
        from django.apps import apps

        destrutivas = []
        for model in apps.get_models():
            for f in model._meta.get_fields():
                # Uma relacao ManyToMany — ou o lado INVERSO dela — nao tem
                # `on_delete`: a ligacao passa por uma tabela intermediaria.
                # E o lado inverso e' traiçoeiro: o `rd.on_delete` dele
                # DELEGA ao campo que aponta, e o campo e' uma M2M que tambem
                # nao tem. Perguntar directamente levanta
                # `AttributeError: 'ManyToManyField' object has no attribute
                # 'on_delete'`, e o teste morre com uma excepcao em vez de
                # dizer o que ia dizer.
                #
                # Filtrar por `isinstance` nao serve: `get_fields()` devolve o
                # `ManyToManyRel` e nao o `ManyToManyField`, e um filtro
                # contra a classe errada passa ao lado em silencio — o que e'
                # pior do que nao filtrar. O `try` e' a unica pergunta que o
                # Django responde sem depender de saberes que classe te deu.
                try:
                    nome = f.remote_field.on_delete.__name__
                    alvo = f.remote_field.model._meta.label
                except AttributeError:
                    continue
                if alvo == "app.Cultura" and nome == "CASCADE":
                    destrutivas.append(f"{model._meta.model_name}.{f.name}")
        return destrutivas

    def test_nenhuma_relacao_para_cultura_apaga_registos(self):
        self.assertEqual(
            self._todas_as_relacoes_que_apagam(),
            [],
            "Uma relação voltou a CASCADE. Apagar uma cultura do catálogo não "
            "pode apagar a safra de ninguém.",
        )

    def test_apagar_a_cultura_em_uso_e_recusado(self):
        from app.models import Safra

        with self.assertRaises(ProtectedError):
            self.cafe.delete()
        # e a safra continua lá
        self.assertTrue(Safra.objects.filter(pk=self.safra.pk).exists())

    def test_uma_cultura_sem_registos_ainda_se_apaga(self):
        """PROTECT não pode transformar o catálogo em intocável."""
        from app.models import Cultura

        inquebrada = Cultura.objects.create(nome="CULTURA-SEM-REGISTOS", grupo="teste")
        inquebrada.delete()
        self.assertFalse(Cultura.objects.filter(nome="CULTURA-SEM-REGISTOS").exists())


# ---------------------------------------------------------------------------
# 4. O QUE A SIMULAÇÃO VIU, E O QUE ELA NÃO PROVOU
# ---------------------------------------------------------------------------
class OQueFicouPorProvar(TestCase):
    """A honestidade de um relatório de defeitos.

    A simulação mostrou widgets rotulados "Milho (Fazenda)", "Soja" e
    "Trigo" num painel de um produtor que planta café. A API estava limpa —
    `/api/widget-data/` não continha nenhuma dessas culturas — o que localiza o
    defeito no renderizador, não no backend.

    Onde nasce a lista de widgets por defeito NÃO foi localizado. O layout
    vive em `localStorage` (`matrix-widgets-layout`) e sobreviveu a limpar o
    storage, o que aponta para um conjunto por defeito no código, mas a
    busca não o encontrou.

    Este teste não trava um defeito que nao esta localizado. Serve para deixar o
    facto escrito onde alguém vai procurar: a próxima pessoa a ver
    "Produtividade Milho" num painel de café sabe que a origem é esta, e não
    volta a procurar do zero.
    """

    def test_a_api_nao_menciona_culturas_que_o_produtor_nao_tem(self):
        from app.models import Propriedade, Safra

        u = User.objects.create_user(username="cafe3", password="x")
        p = Propriedade.objects.create(
            user=u,
            nome="Sítio",
            cidade="Muzambinho",
            uf="MG",
            area_total=Decimal("340"),
        )
        cafe = _cafe()
        Safra.objects.create(
            propriedade=p, cultura=cafe, ano=2025, area_plantada=Decimal("210")
        )

        from django.test import Client

        c = Client()
        c.login(username="cafe3", password="x")
        corpo = c.get("/api/widget-data/").content.decode()
        for outra in ("Milho", "Soja", "Trigo", "Arroz"):
            self.assertNotIn(
                outra,
                corpo,
                f"A API voltou a mencionar {outra!r}. O backend tem de falar "
                f"só das culturas do produtor.",
            )
        self.assertIn("Café", corpo)
