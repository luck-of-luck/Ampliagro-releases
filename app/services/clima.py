"""Clima com captura em cache, em JSON.

Porquê este ficheiro mudou na Fase 2
------------------------------------
Antes, `get_previsao` fazia isto quando a rede não respondia:

    except Exception as e:
        return {"error": str(e), "fallback": True}

Ou seja: **não havia captura nenhuma**. O produtor via um erro, e não via
o que o céu fazia há duas horas. As três views que consomem isto
(`api/views/core.py`, `api/views/agronomia.py`, `api/views/production.py`)
traduzem a presença de `error` em HTTP 503 — portanto, sem rede, a
previsão era um ecrã de erro.

A decisão do dono do projecto: sem rede, mostrar a **última captura** com a
hora dela; e sem nunca ter havido captura, mostrar `—` com a fonte
`sem sinal`.

O que este módulo acrescenta
----------------------------
Um único ficheiro JSON, `CLIMA_CACHE_DIR/clima.json`, com as capturas
indexadas por coordenada:

    {
      "versao": 1,
      "capturas": {
        "-15.78,-47.93": {
          "capturado_em": "2026-10-12T14:23:01-03:00",
          "fonte": "open-meteo",
          "dados": { ...a resposta crua do Open-Meteo... }
        }
      }
    }

Um ficheiro, e não um por coordenada, porque o que se quer é poder abrir
um `.json` e ver tudo o que o desktop sabe sobre o tempo. Doze
propriedades são alguns kilobytes.

TRÊS REGRAS QUE O CÓDIGO RESPETA, E PORQUÊ
==========================================

**1. A escrita é atómica.** Escreve-se um `.tmp` e faz-se `os.replace`.
Uma escrita directa que é interrompida a meio deixa um JSON truncado, e
daí em diante o desktop não tem captura nenhuma — o mesmo estado que
tínhamos antes desta fase, mas com a culpa distributed. `os.replace` é
atómico no Windows e no POSIX.

**2. Um cache ilegível é um cache vazio.** Se o JSON estiver corrompido,
avisa e continua. Recusar arrancar por causa de um ficheiro de cache seria
trocar uma falha pequena por uma grande.

**3. `error` só existe quando não há mesmo nada.** Os três consumidores
traduzem `error` em HTTP 503. Se a captura de cache viesse com `error`, a
aplicação continuaria a mostrar erro — e a cache não serviria para nada.
Com uma captura, a resposta é **200 com `fonte_dados: "cache"`**, e quem
vê 22 °C consegue ler de onde veio e de quando.
"""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.cache import cache

#: Fonte mostrada quando não há rede E nunca houve captura.
SEM_SINAL = "sem-sinal"


def _diretorio() -> Path:
    """Onde vive o `clima.json`.

    Vem de um setting, e não de `MEDIA_ROOT`: um ficheiro em `MEDIA_ROOT`
    é servido pelo WhiteNoise e pelo Django. O `clima.json` diz a latitude
    e longitude da fazenda de quem o produziu, e isso não é para ir parar
    a um URL que qualquer pessoa pode adivinhar.
    """
    base = getattr(settings, "CLIMA_CACHE_DIR", None)
    if base:
        return Path(base)
    return Path(settings.BASE_DIR) / ".cache-clima"


def _caminho() -> Path:
    return _diretorio() / "clima.json"


def _chave(lat: float, lon: float) -> str:
    """Chave estável por coordenada.

    Arredondar a 4 casas (~11 m) evita que duas propriedades a 30 metros
    uma da outra recebam entradas separadas por causa de a coordenada vir
    com mais uma casa decimal noutro dia.
    """
    return f"{round(float(lat), 4):.4f},{round(float(lon), 4):.4f}"


def ler_captura(lat: float, lon: float) -> dict | None:
    """A última captura guardada para estas coordenadas, ou `None`."""
    caminho = _caminho()
    if not caminho.is_file():
        return None
    try:
        bruto = json.loads(caminho.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        # Regra 2: cache ilegível é cache vazio.
        return None
    entrada = (bruto.get("capturas") or {}).get(_chave(lat, lon))
    return entrada if isinstance(entrada, dict) else None


def gravar_captura(lat: float, lon: float, dados: dict, fonte: str) -> None:
    """Guarda a captura, sem perder as dos outros sítios."""
    caminho = _caminho()
    caminho.parent.mkdir(parents=True, exist_ok=True)

    capturas: dict = {}
    if caminho.is_file():
        try:
            capturas = (json.loads(caminho.read_text(encoding="utf-8")) or {}).get(
                "capturas"
            ) or {}
        except (json.JSONDecodeError, OSError):
            capturas = {}

    capturas[_chave(lat, lon)] = {
        # `isoformat` com fuso. Sem fuso, um `datetime.now()` gravado e lido
        # noutra máquina — ou noutro dia com o horário de Verão trocado — é
        # uma hora que não significa nada.
        "capturado_em": datetime.now().astimezone().isoformat(timespec="seconds"),
        "fonte": fonte,
        "dados": dados,
    }

    # Regra 1: escrita atómica.
    temporario = caminho.with_suffix(".json.tmp")
    temporario.write_text(
        json.dumps(
            {"versao": 1, "capturas": capturas},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    os.replace(temporario, caminho)


def _marcar(
    dados: dict, *, fonte: str, capturado_em: str | None, aviso: str | None
) -> dict:
    """Acrescenta a proveniência, sem mexer no resto da resposta.

    `fonte_dados` é distinto do `fonte` que já existia no payload (que é a
    fonte das COORDENADAS — geocode, talhão, ou o que for). Confundi-los
    seria o tipo de bug que faz o produtor ler "geocodificado" e concluir
    que o tempo também foi medido na sua fazenda.
    """
    saida = dict(dados or {})
    saida["fonte_dados"] = fonte
    saida["capturado_em"] = capturado_em
    if aviso:
        saida["aviso"] = aviso
    return saida


class ClimaService:
    """
    Serviço para busca de clima via Open-Meteo API (não requer chave).
    """

    CACHE_TIMEOUT = 3600 * 3  # Cache de 3 horas para previsão do clima

    @classmethod
    def get_previsao(cls, lat: float, lon: float) -> dict:
        """
        Busca previsão do tempo de 7 dias para lat/lon.

        Ordem: cache do Django -> rede. E quando a rede falha, **a última
        captura em JSON**, que é o que a Fase 2 pediu. Sem rede E sem
        captura anterior, devolve `error` — que é o que as três views já
        traduzem em 503, sem mudar o contrato delas.
        """
        cache_key = f"ampliagro_clima_prev_{lat}_{lon}"
        cached_data = cache.get(cache_key)
        if cached_data:
            # O cache do Django tem 3 horas e não sabe quando os dados
            # entraram. A captura em JSON sabe — e é essa a diferença
            # entre "22 °C" e "22 °C, medido às 14:23".
            captura = ler_captura(lat, lon)
            if captura:
                return _marcar(
                    cached_data,
                    fonte=captura.get("fonte", "open-meteo"),
                    capturado_em=captura.get("capturado_em"),
                    aviso=None,
                )
            return _marcar(
                cached_data,
                fonte="open-meteo",
                capturado_em=datetime.now().astimezone().isoformat(timespec="seconds"),
                aviso=None,
            )

        try:
            # Endpoint Open-Meteo para previsão
            url = (
                f"https://api.open-meteo.com/v1/forecast?"
                f"latitude={lat}&longitude={lon}&"
                f"daily=temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max&"
                f"timezone=America%2FSao_Paulo"
            )
            req = urllib.request.Request(url, headers={"User-Agent": "Ampliagro/1.0"})
            with urllib.request.urlopen(req, timeout=3) as response:
                data = json.loads(response.read().decode())
                cache.set(cache_key, data, cls.CACHE_TIMEOUT)
                gravar_captura(lat, lon, data, "open-meteo")
                agora = datetime.now().astimezone().isoformat(timespec="seconds")
                return _marcar(data, fonte="open-meteo", capturado_em=agora, aviso=None)
        except Exception as e:
            # timeout curto 3s → fallback rápido, não segura worker 10s
            captura = ler_captura(lat, lon)
            if captura:
                return _marcar(
                    captura.get("dados") or {},
                    fonte="cache",
                    capturado_em=captura.get("capturado_em"),
                    aviso=(
                        "Sem ligação à internet. A mostrar a captura de "
                        f"{captura.get('capturado_em')}."
                    ),
                )

            # Sem rede e SEM nunca ter havido captura. `error` fica, para
            # as três views continuarem a devolver 503 como já devolviam —
            # e a UI mostra `—` com fonte `sem sinal`.
            return {
                "error": str(e),
                "fallback": True,
                "fonte_dados": SEM_SINAL,
                "capturado_em": None,
            }

    @classmethod
    def get_historico(
        cls, lat: float, lon: float, start_date: str, end_date: str
    ) -> dict:
        """
        Busca histórico do tempo de 30 dias para lat/lon

        O histórico **não** vai para o `clima.json`: é consultado por
        intervalo de datas, não por "o tempo agora", e um produtor que
        abre o ficheiro de cache espera ver o tempo da sua fazenda — não
        três meses de registo histórico que só interessa a relatórios.
        """
        cache_key = f"ampliagro_clima_hist_{lat}_{lon}_{start_date}_{end_date}"
        cached_data = cache.get(cache_key)
        if cached_data:
            return cached_data

        try:
            # Endpoint Open-Meteo para histórico
            url = (
                f"https://archive-api.open-meteo.com/v1/archive?"
                f"latitude={lat}&longitude={lon}&"
                f"start_date={start_date}&end_date={end_date}&"
                f"daily=temperature_2m_max,temperature_2m_min,precipitation_sum&"
                f"timezone=America%2FSao_Paulo"
            )
            req = urllib.request.Request(url, headers={"User-Agent": "Ampliagro/1.0"})
            with urllib.request.urlopen(req, timeout=3) as response:
                data = json.loads(response.read().decode())
                # Historico guarda por mais tempo (ex 24h)
                cache.set(cache_key, data, 86400)
                return data
        except Exception as e:
            return {"error": str(e)}
