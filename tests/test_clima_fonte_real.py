"""O clima do painel tem de ser uma MEDIÇÃO, ou uma ausência declarada.

O DEFEITO
=========
`_get_real_weather` (app/api/views/utils.py) tinha esta ordem:

    INMET -> OpenWeatherMap (se houvesse chave) -> 28/26/23 °C escritos à mão

Verificada no ambiente real (Primavera do Leste/MT, 2026-10-01), NENHUMA das
duas primeiras fontes respondia:

  * o INMET devolvia ``404 E_ROUTE_NOT_FOUND`` para
    ``/previsao/MT/Primavera%20do%20Leste`` — a rota não resolve cidade com
    espaço, e `Propriedade.cidade` é texto livre;
  * o OpenWeatherMap exige ``OPENWEATHER_API_KEY``, que não existe no `.env`.

Logo TODA propriedade caía no terceiro bloco: 28 °C, "Ensolarado", com
``fonte: "simulado"``. O nome era honesto; o efeito não. O cartão dizia
exactamente o mesmo no Cerrado e no litoral, com a confiança de quem mediu.
E a fonte real estava ligada — ``FonteDadosExterno`` tipo ``OPEN_METEO``,
``ativo=True`` — e nunca era consultada por este caminho. A IA consultava-a
pelo serviço canônico de coordenadas e acertava: 31.7 °C medidos contra
28 °C inventados, para a mesma fazenda, no mesmo minuto.

O QUE ESTE TESTE TRAVA
======================
1. O fallback de 28/26/23 °C não volta. Se não há fonte, a resposta é
   ``sem_fonte`` com ``temp: None`` — ausência, não número.
2. Quando o Open-Meteo responde, é ele que responde — e a origem das
   coordenadas viaja com o número, para que a incoerência seja auditável.
3. `fonte: "open-meteo"` é uma das fontes REAIS, para o painel não marcar
   "Simulada" por baixo de uma medição verdadeira.
"""

from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase

from app.models import Propriedade

User = get_user_model()


class ClimaEhMedicaoOuAusencia(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user("clima_t", "clima_t@t.com", "x")
        self.prop = Propriedade.objects.create(
            user=self.user,
            nome="Fazenda do Teste",
            cidade="Primavera do Leste",
            uf="MT",
            area_total=Decimal("1200"),
        )

    # ───────────────────────────────────────────────────────────────────
    # 1. O fallback inventado não pode voltar
    # ───────────────────────────────────────────────────────────────────
    def test_sem_nenhuma_fonte_a_resposta_e_ausencia_e_nao_28_grandes(self):
        """Nenhuma fonte responde -> `sem_fonte` com temperatura None.

        Este é o teste que impede a regressão que aconteceu. O número 28
        não é proibido por ser raro: é proibido porque era CONSTANTE. Uma
        temperatura que não muda de valor com a fazenda, com a estação e
        com a hora não é uma medição — é um número de catálogo.
        """
        from app.api.views import utils

        with (
            mock.patch.object(utils, "_WEATHER_CACHE", {}),
            mock.patch.object(utils, "_clima_open_meteo", return_value=None),
            mock.patch("requests.get", side_effect=Exception("sem rede")),
        ):
            clima = utils._get_real_weather(self.prop)

        self.assertIsNotNone(clima, "sem fonte ainda tem de devolver uma resposta")
        self.assertEqual(clima["fonte"], "sem_fonte")
        self.assertIsNone(
            clima["atual"]["temp"],
            "sem fonte a temperatura tem de ser None. Um número aqui é uma "
            "medição que ninguém fez, e um produtor decide irrigar por ela.",
        )
        self.assertEqual(clima["previsao"], [])
        # O motivo diz o que fazer, não só que faltou.
        self.assertIn("motivo", clima)
        self.assertIn("Primavera do Leste", clima["motivo"])

    def test_a_constante_28_grau_nao_existe_mais_no_fallback(self):
        """Trava a forma do defeito, não só o seu efeito.

        Um teste que só verifica `temp is None` passa se alguém reescrever o
        fallback com OUTRO número inventado. Este falha no código, e por isso
        apanha a reintrodução antes de ela chegar ao produtor.
        """
        import inspect

        from app.api.views import utils

        fonte = inspect.getsource(utils._get_real_weather)
        bloco_sem_fonte = fonte.split("sem_fonte", 1)[-1]

        for sintético in ('"temp": 28', '"temp": 26', '"temp": 23', '"umidade": 65'):
            self.assertNotIn(
                sintético,
                bloco_sem_fonte,
                f"o fallback voltou a inventar {sintético} quando não há fonte",
            )

    # ───────────────────────────────────────────────────────────────────
    # 2. Quando há fonte real, ela responde — e explica-se
    # ───────────────────────────────────────────────────────────────────
    def test_open_meteo_e_a_primeira_fonte_e_traz_a_origem(self):
        """A fonte real do sistema responde, e a origem viaja com o número.

        A coordenada tem de ir na resposta. Um clima sem origem explicada é
        um clima que ninguém pode corrigir: se o produtor confirmar que a
        fazenda não é aí, não há nada no payload que diga de onde saiu o
        número.
        """
        from app.api.views import utils

        medido = {
            "cidade": "Primavera do Leste/MT",
            "fonte": "open-meteo",
            "coordenadas": [-15.4905, -54.2465],
            "coordenadas_origem": "georef:talhoes:4 (media)",
            "aviso": None,
            "atual": {
                "dia": "Hoje",
                "icone": "bi-cloud-drizzle",
                "temp": 32,
                "umidade": 45,
                "chuva_mm": 0.1,
                "descricao": "Garoa fraca",
            },
            "previsao": [],
        }

        with (
            mock.patch.object(utils, "_WEATHER_CACHE", {}),
            mock.patch.object(utils, "_clima_open_meteo", return_value=medido),
            # Qualquer chamada de rede a partir daqui é um erro: a fonte real
            # já respondeu, e ir ao INMET seria ignorar a medição.
            mock.patch("requests.get", side_effect=AssertionError("rede chamada")),
        ):
            clima = utils._get_real_weather(self.prop)

        self.assertEqual(clima["fonte"], "open-meteo")
        self.assertEqual(clima["atual"]["temp"], 32)
        self.assertIsNotNone(clima["coordenadas"])
        self.assertIsNotNone(clima["coordenadas_origem"])

    def test_open_meteo_constrói_a_resposta_a_partir_da_api(self):
        """`_clima_open_meteo` traduz o payload real, e não inventa campos.

        O `weather_code` do Open-Meteo é um NÚMERO (WMO). Sem traduzir, o
        cartão mostraria "51" ao produtor no lugar de "Garoa fraca" — o mesmo
        defeito do `fonte: "google clima"`, com outra roupa.
        """
        from app.api.views import utils

        payload = {
            "current": {
                "temperature_2m": 31.7,
                "relative_humidity_2m": 45,
                "precipitation": 0.1,
                "weather_code": 51,
            },
            "daily": {
                "time": ["2026-10-01", "2026-10-02", "2026-10-03"],
                "weather_code": [51, 61, 3],
                "temperature_2m_max": [33.0, 28.1, 30.2],
                "temperature_2m_min": [21.0, 20.4, 20.9],
                "precipitation_probability_max": [96, 80, 12],
            },
        }

        with (
            mock.patch(
                "app.services.coordenadas.resolver",
                return_value=mock.Mock(
                    ok=True, lat=-15.49, lon=-54.24, fonte="cidade", aviso=None
                ),
            ),
            mock.patch(
                "app.ia.fontes.fetch_permitido",
                return_value=(payload, "api.open-meteo.com"),
            ),
        ):
            clima = utils._clima_open_meteo(self.prop)

        self.assertEqual(clima["fonte"], "open-meteo")
        self.assertEqual(clima["atual"]["temp"], 32)  # 31.7 arredondado
        self.assertEqual(clima["atual"]["descricao"], "Garoa fraca")
        self.assertNotEqual(clima["atual"]["icone"], "bi-sun")
        # A chance de chuva é a informação que decide pulverizar.
        self.assertEqual(clima["previsao"][0]["chuva_prob"], 96)
        # Três dias, e nenhum deles repete o dia de hoje.
        self.assertEqual(len(clima["previsao"]), 3)
        self.assertEqual(
            [d["dia"] for d in clima["previsao"]], ["Hoje", "Amanhã", "Depois"]
        )

    def test_codigos_desconhecidos_nao_viram_sol(self):
        """Um `weather_code` que não está no dicionário é nublado, não sol.

        O `bi-sun` é o ícone de "ensolarado", e é o que o fallback antigo
        usava sempre. Um código novo que a fonte acrescente não pode
        aparecer como um dia de sol em plena €.
        """
        from app.api.views import utils

        self.assertEqual(utils._om_icon(0), "bi-sun")
        self.assertEqual(utils._om_descricao(0), "Ensolarado")
        # Chuva torrencial não é "parcialmente nublado".
        self.assertNotEqual(utils._om_icon(65), utils._om_icon(2))
        # Código desconhecido: existe ícone, mas não é sol.
        self.assertNotEqual(utils._om_icon(9999), "bi-sun")
        self.assertIsNone(utils._om_descricao(9999))

    # ───────────────────────────────────────────────────────────────────
    # 3. O painel reconhece a fonte real
    # ───────────────────────────────────────────────────────────────────
    def test_a_fonte_real_esta_na_lista_de_fontes_reais_do_painel(self):
        """O allowlist do front tem de incluir `open-meteo`.

        O `index.html` documenta — com razão — que usar `fonte !== 'simulado'`
        faz qualquer valor novo passar como verdadeiro. Por isso usa uma
        allowlist. Mas uma allowlist que não conhece a fonte real marca a
        estação como "Simulada" por baixo de uma medição verdadeira: o
        inverso do defeito original, e igualmente enganador.
        """
        import pathlib

        # MEDIDO 2026-10-05. Este teste lia `app/templates/index.html`.
        # A allowlist das fontes reais esta em `pagina-index.js` (4 ocorrencias
        # de `open-meteo` no JS, **zero** no template), desde o refactor que
        # extraiu a logica da folha de calculo. O `index.html:1714` carrega
        # o JS, portanto quem abre a pagina ve a allowlist — o teste e' que
        # ficou a olhar para o ficheiro morto.
        #
        # Confirmei antes de mexer que a allowlist sobreviveu: `open-meteo` e
        # o rotulo `Open-Meteo` estao la. Um teste que passa por ler o vazio
        # nao protege nada, e um teste que falha porque o codigo esta num
        # ficheiro diferente tambem nao — por isso se muda o ficheiro e a
        # verificacao continua a ser a mesma.
        caminho = (
            pathlib.Path(__file__).resolve().parents[1]
            / "app"
            / "static"
            / "js"
            / "pagina-index.js"
        )
        html = caminho.read_text(encoding="utf-8")
        self.assertIn(
            "'open-meteo'",
            html,
            "o painel não conhece a fonte real do sistema: uma medição "
            "verdadeira seria marcada como 'Simulada'.",
        )
        # E o rótulo tem de ser legível por quem lê o cartão.
        self.assertIn("Open-Meteo", html)
