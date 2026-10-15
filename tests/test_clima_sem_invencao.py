"""O clima não pode inventar um número — e não pode tê-lo em duas cópias.

ESTE TESTE NASCE DE UM ITEM DA FILA QUE ESTAVA FECHADO E NÃO ESTAVA
-----------------------------------------------------------------
A FILA marcava o achado #9 como «resolvido no bloco 1»: o INMET injectava
25 °C e 60 % de humidade com o carimbo `"fonte": "inmet"`. E estava.

A correcção tinha sido feita — em `app/api/views/utils.py`, e está lá, com o
raciocínio escrito no comentário. Mas `/api/weather/` nunca usou essa cópia.

`scripts/split_api_views.py` tinha copiado `_get_real_weather` de `utils.py`
para `iot.py`. Duas cópias. A de `utils.py` corrigida. A de `iot.py` com o
`or 25` / `or 60` intactos — e `iot.py` é a que a rota usa, porque uma
definição no módulo vence o `from .utils import *`.

Resultado, medido antes da correcção:

    >>> import app.api.views.iot as iot, app.api.views.utils as U
    >>> iot._get_real_weather.__code__.co_firstlineno
    120
    >>> iot._get_real_weather is U._get_real_weather
    False

Ou seja: o defeito foi arrumado num sítio onde ninguém o vê, e o Producer
continuava a receber 25 °C com o nome do INMET por cima. Um item fechado com
um defeito vivo é pior do que um item aberto: é um item em que ninguém vai
voltar.

POR QUE UM TESTE E NÃO SÓ A CORRECÇÃO
------------------------------------
Porque a duplicação foi criada por um SCRIPT, e scripts correm outra vez. O
`split_api_views.py` está no repositório. Da próxima vez que alguém o correr,
volta a haver duas `_get_real_weather`, e a do `iot.py` nasce outra vez com o
`or 25` — a não ser que alguém se lembre. Um teste que afirma «há uma só
implementação» é o que se lembra por nós.

E porque o outro lado do mesmo problema continua aberto: mesmo com a cópia
corrigida no sítio certo, o `/api/weather/` diz `fonte: "simulado"` quando
não tem INMET nem chave, e o formatador do chat da AmplIA não lê esse
carimbo. O produtor lê «temp: 28, descricao: Ensolarado» sem qualquer
indício de que ninguém mediu isso. Isso é o segundo teste desta classe.
"""

from __future__ import annotations

import ast
import inspect
import pathlib
from decimal import Decimal
from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase

#: Constantes que, apanhadas num `or`, significam "se o INMET não disse,
#: inventa isto". 25 °C e 60 % são os que estavam lá; a lista é o critério,
#: não o conteúdo, para o teste continuar a valer se o número mudar.
NUMEROS_SINTETICOS = {25, 60}


def _or_de_constantes(fonte: str) -> list[tuple[int, int]]:
    """Constantes usadas como `ou`-fallback, com a linha.

    Por AST e não por texto: o número `25` aparece legitimamente em
    comentários e docstrings que EXPLICAM o defeito, e uma busca por texto
    acusaria o próprio ficheiro que o documenta. É o mesmo motivo da
    decisão D7 do `COORDENACAO_IA.md`.
    """
    achados: list[tuple[int, int]] = []
    for no in ast.walk(ast.parse(fonte)):
        if isinstance(no, ast.BoolOp) and isinstance(no.op, ast.Or):
            for v in no.values:
                if isinstance(v, ast.Constant) and v.value in NUMEROS_SINTETICOS:
                    achados.append((v.value, no.lineno))
    return achados


class ClimaNaoInventa(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="clima", password="x")

    # ------------------------------------------------------------------
    # 1. Uma só implementação
    # ------------------------------------------------------------------
    def test_a_rota_usa_a_implementacao_unica(self):
        """`iot._get_real_weather` tem de SER a de `utils`, não uma cópia.

        Este é o teste que apanha a deriva que causou o defeito. Sem ele,
        corrigir uma das cópias é uma jogo de soma-zero: fica a parecer
        arrumado enquanto a rota continua na outra.
        """
        from app.api.views import iot, utils

        self.assertIs(
            iot._get_real_weather,
            utils._get_real_weather,
            "iot.py voltou a definir _get_real_weather. Se o split_api_views.py "
            "correu outra vez, apague a cópia — não a deixes ganhar do import.",
        )

    def test_nenhuma_das_copias_inventa_25_ou_60(self):
        """Nenhum `ou 25` / `ou 60` sobrevive em qualquer dos dois ficheiros."""
        for nome in ("app/api/views/iot.py", "app/api/views/utils.py"):
            caminho = pathlib.Path(__file__).resolve().parents[1] / nome
            achados = _or_de_constantes(caminho.read_text(encoding="utf-8"))
            self.assertEqual(
                achados,
                [],
                f"{nome} inventa {NUMEROS_SINTETICOS} quando a fonte cala: {achados}",
            )

    # ------------------------------------------------------------------
    # 2. Quando o INMET cala, o campo é None — não 25
    # ------------------------------------------------------------------
    def test_inmet_sem_temperatura_devolve_none_e_nao_25(self):
        """Três casos num payload só, porque os três já correram mal.

        O INMET devolve strings e às vezes omite o campo. O `or` é a
        armadilha: `0.0 or 25` dá 25, porque zero é falsy em Python. Um 0 °C
        é uma temperatura perfeitamente válida, e o `or` transformava-a em
        25 °C — inventados, com o nome do INMET por cima.

        Os dias do payload:

        1. `temp_max: ""`, `temp_min: "0"` — a fonte diz zero. A resposta
           certa é `0.0`; o que estava errado era virar 25.
        2. sem `temp_max`, `temp_min: ""` — a fonte calou. A resposta certa é
           `None`, que o painel sabe mostrar como «sem dado».
        3. `umidade_max` ausente em todos — humidade é sempre `None`.
        """
        from app.api.views import utils

        resposta = mock.Mock(ok=True)
        resposta.json.return_value = {
            "Muzambinho": [
                {"dia": "Zero valido", "resumo": "", "temp_max": "", "temp_min": "0"},
                {"dia": "Campo ausente", "resumo": "", "temp_min": ""},
            ]
        }
        resposta.text = ""

        from app.models import Propriedade

        prop = Propriedade.objects.create(
            user=self.user,
            nome="Fazenda",
            cidade="Muzambinho",
            uf="MG",
            area_total=Decimal("1200"),
        )

        with (
            mock.patch.object(utils, "_WEATHER_CACHE", {}),
            # O Open-Meteo é a PRIMEIRA fonte desde que passou a ser a que a
            # instalação tem ativa, e esta largura toda é o comportamento que
            # este teste quer travar: o INMET a responder com campos vazios.
            # Sem esta excepção, o Open-Meteo responde primeiro (e bem) e o
            # INMET nunca chega a ser chamado — o teste passava a verde sem
            # nunca exercitar o ramo que descreve.
            mock.patch.object(utils, "_clima_open_meteo", return_value=None),
            mock.patch("requests.get", return_value=resposta),
        ):
            clima = utils._get_real_weather(prop)

        self.assertIsNotNone(clima)
        self.assertEqual(clima["fonte"], "inmet")

        por_dia = {d["dia"]: d for d in clima["previsao"]}

        # 1. um zero real continua zero, e nunca vira 25
        zero = por_dia["Zero valido"]
        self.assertNotEqual(zero["temp"], 25, "um 0 °C do INMET virou 25 °C")
        self.assertEqual(
            zero["temp"], 0.0, "o INMET disse 0 e o número tem de ser 0, não 25"
        )

        # 2. um campo que a fonte não deu é None, não um número plausível
        self.assertIsNone(
            por_dia["Campo ausente"]["temp"],
            "campo ausente virou número; None é o que o painel sabe mostrar "
            "como «sem dado»",
        )

        # 3. humidade e descrição nunca foram inventadas, em nenhum dia
        for dia in clima["previsao"]:
            self.assertNotEqual(dia["umidade"], 60, f"{dia['dia']}: 60 injectado")
            self.assertIsNone(dia["umidade"])
            self.assertNotEqual(dia["temp"], 25, f"{dia['dia']}: 25 injectado")
            self.assertIsNone(
                dia["descricao"],
                "descrição inventada: «parcialmente nublado» é uma previsão, "
                "e não veio de lado nenhum",
            )

    # ------------------------------------------------------------------
    # 3. O carimbo de simulado tem de sobreviver à conversa
    # ------------------------------------------------------------------
    def test_o_formato_do_clima_e_o_que_a_ia_le(self):
        """O contrato entre o que o servidor devolve e o que o chat lê.

        As três fontes — INMET, OpenWeatherMap e o fallback — devolvem a
        MESMA forma: `{cidade, fonte, atual, previsao}`. E o ramo `clima` de
        `formatarDadosNatural` lê `temperatura_max`, `temp_max`,
        `precipitacao`... campos que não existem em lado nenhum desta resposta.

        Consequência, que não é teórica: com `previsao` a ser uma lista, o
        formatador não encontra nenhum campo, e devolve um despejo de JSON
        cru. Foi o que se mediu no chat da AmplIA:

            Previsao do clima: [dia: Hoje, icone: bi-sun, temp: 28,
            umidade: 65, descricao: Ensolarado, ...]

        Duas coisas erradas no mesmo texto: estáParts tortas, e — no caso do
        fallback — os 28 °C são inventados sem qualquer marca, porque o
        `fonte: "simulado"` do servidor nunca é lido.

        Este teste fixa a FORMA do contrato. Não verifica o JavaScript (que
        exigiria browser) — verifica que a forma que o servidor promete é a
        forma que o resto do sistema assume, e que o carimbo existe.
        """
        from app.api.views import utils

        src = inspect.getsource(utils._get_real_weather)

        for no in ast.walk(ast.parse(src)):
            if not isinstance(no, ast.FunctionDef):
                continue
            # cada `result = {...}` tem de ter as quatro chaves
            for d in ast.walk(no):
                if isinstance(d, ast.Dict):
                    chaves = [
                        k.value
                        for k in d.keys
                        if isinstance(k, ast.Constant) and isinstance(k.value, str)
                    ]
                    if "cidade" in chaves and "previsao" in chaves:
                        self.assertIn(
                            "fonte",
                            chaves,
                            "a resposta do clima tem de dizer de onde veio; sem "
                            "`fonte`, o consumidor não pode carimbar nada",
                        )
                        self.assertIn("atual", chaves)
