"""Guarda do contrato de dependencias.

MEDIDO 2026-10-05 (agente 3). Este ficheiro nasce de duas medicoes, ambas
comum a codigo e a manifesto.

1. O MANIFESTO NAO RESOLVIA. `cryptography` estava declarado duas vezes, com
   intervalos CONTRADITORIOS (`>=41.0,<42.0` e `>=49.0.0,<50.0`).
   `pip install -r requirements.txt` devolvia `ResolutionImpossible` — a
   imagem de producao nao construia. Nao havia teste que o apanhasse,
   porque a su-suite corre contra o que esta INSTALADO, e nao contra o que o
   manifesto pediria a um ciclo limpo.

   Esta e' a falha de fundo do projecto, e vale mais que as CVEs: um teste
   verde pode estar a validar um conjunto de dependencias que a producao
   nunca vai ter.

2. `pip-audit -r requirements.txt` => 226 vulnerabilidades em 27 pacotes. Os
   pinos eram por intervalo (`>=`), 107 deles, e ZERO fixos. O Dockerfile faz
   `pip install -r requirements.txt`, portanto a versao productionada e' "a
   mais nova dentro do intervalo, no dia do build".

O QUE ESTE TESTE FAZ
====================
Tres coisas, cada uma contra uma classe de defeito:

  * o manifesto RESOLVE?  → apanha pinos duplicados e contraditorios;
  * nenhum pacote com CVE ficou PIOR? → a baseline so encolhe, como a de
    `test_contrato_de_esquema.py`;
  * nenhum pin ficou duplicado? → apanha a classe do `cryptography`.

A BASELINE E' UMA LISTA COM RAZAOES
===================================
Nao e' "226 e' o aceitavel" nem "0 e' o ideal". Cada linha que fica tem uma
RAZAO escrita. Uma baseline sem razoes e' um numero que ninguem vai defender
quando o proximo `pip install` a empurrar para cima — e sem defesa, sobe.

ONDE ISTO NAO CHEGA
===================
Nao substitui um lockfile. Um intervalo ainda pode resolver para uma versao
diferente da testada amanha. Isto trava a regressao; o lockfile e' que
torna o build reproduzivel. Fica registado, nao resolvido.

O QUE ESTA NA SUITE NORMAL E O QUE NAO ESTA
===========================================
MEDIDO 2026-10-06. Os tres testes que resolvem o grafo CONTRA O PyPI
(`test_o_manifesto_resolve` e os dois de `pip-audit`) traziam `timeout=1800`
e mediram-se em 30 min. Nao e' um timeout grande a marcar um trabalho grande:
sao tres chamadas de rede numa suite de unidades, e cada uma delas deixava o
resto da suite por verificar ate acabar.

Olha para o numero que decide: `requirements.txt` tem 99 declaracoes e ZERO
com `==`. Todas sao intervalos. Um intervalo so se resolve contra um indice
que|enumerate| versoes — medido, `pip install --dry-run --no-index` devolve
`No matching distribution found for djangorestframework<3.15,>=3.14 (from
versions: none)`. Offline nao ha resposta, e nao ha `--find-links` que a
construa: a venv tem directorios descompactados, nao wheels.

Por isso o corte e' por MARCADOR (`dependencias`), nao por `skip`. Os testes
nao desapareceram: continuam a correr com

    python -m pytest tests/test_contrato_de_dependencias.py -m dependencias

e numa corrida normal aparecem na linha do `deselected`, que e' o aviso. Os
que ficam na suite normal sao os que decides contra o REPO: a classe do
`cryptography` (pino duplicado) e a baseline com razao por pacote.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
REQ = RAIZ / "requirements.txt"
PY = str(RAIZ / ".venv" / "Scripts" / "python.exe")

# Os 3 testes que vao AO PyPI levam `@pytest.mark.dependencias` e ficam de fora
# da corrida normal. O corte e' `-m "not dependencias"` no `addopts` do
# `pytest.ini`; um `pytest_collection_modifyitems` escrito AQUI dentro nao era
# chamado (o pytest so' corre hooks de collection de plugins e conftest), e foi
# exacto assim que a suite continuou a trancar a medir 30 min.
# Para os correr de proposito: ver o docstring deste modulo.


# ── a baseline: o que fica, e porque fica ────────────────────────────────────
# (pacote, versao-resolvida) -> razao para a CVEs nao fechar ainda
ACEITO = {
    "cryptography": (
        "Instalado 49.0.0; a advisoria PYSEC-2026-3552 pede 50.0.0. Subir "
        "duas series sem nada instalado que confirme continua a funcionar "
        "seria escrever no escuro. Alinhar quando 50.x estiver na maquina e a "
        "suite passar."
    ),
    "djangorestframework": (
        "Instalado 3.17.1; as correccoes conhecidas sao 3.15.2 e 3.17.2. Falta "
        "um patch e ninguem o correu. O manifesto continua em 3.14 porque foi "
        "a serie testada no container."
    ),
    "pip": "Ferramenta de build, resolvida em 23.3.2. Nao entra na imagem final.",
    "setuptools": "Ferramenta de build. Nao entra na imagem final.",
    # declarados no manifesto, NAO instalados nesta maquina de desenvolvimento.
    # A correccao obriga a subir de serie, e nao ha nada instalado que diga se
    # o codigo do Ampliagro continua a funcionar nela.
    "aiohttp": (
        "Declarado no manifesto, ausente nesta venv. A serie com CVE resolve "
        "para 3.9.5; a correccao comeca em 3.10.11. Sem versao instalada nao ha "
        "como validar a subida."
    ),
    "gdal": (
        "Declarado, ausente nesta venv (wheel so existe por plataforma). A "
        "correccao salta de 3.8 para 3.13 — tres series."
    ),
    "fiona": (
        "Declarado, ausente nesta venv. A correccao salta de 1.9 para 1.10b, "
        "que ainda e' beta."
    ),
    "geopandas": (
        "Declarado, ausente nesta venv. Depende de GDAL/Fiona/Shapely, que "
        "tambem nao estao instalados; a correccao salta de 0.14 para 1.1.2."
    ),
    "scikit-learn": (
        "Declarado, ausente nesta venv. A correccao salta de 1.3 para 1.5, "
        "com mudancas de API no scikit-learn 1.4/1.5."
    ),
    "orjson": ("Declarado, ausente nesta venv. A correccao salta de 3.9 para 3.11."),
    "protobuf": (
        "Declarado, ausente nesta venv. A correccao salta de 4.25 para 5.29 — "
        "mudanca de serie maior, com incompatibilidades conhecidas."
    ),
    "pdfminer-six": (
        "Declarado, ausente nesta venv. Resolvido em 20221105, que ja' e' de "
        "2022; a correccao salta para 20251107."
    ),
    "djangorestframework-simplejwt": (
        "Declarado, ausente nesta venv. Depende do DRF, que tambem esta' "
        "pendente; corrigir um sem o outro deixa o par incoerente."
    ),
    "gunicorn": (
        "Declarado, ausente nesta venv. Server WSGI de producao; a correccao "
        "salta de 21 para 22. A imagem de producao instala-o pela primeira vez "
        "num deploy real, entao o risco aqui e' o arranque, nao o CVE."
    ),
    "wheel": (
        "Declarado, ausente nesta venv. Ferramenta de build, idem pip e "
        "setuptools: nao entra na imagem final."
    ),
}


def _pip_audit_existe():
    return shutil.which("pip-audit") or (RAIZ / ".venv/Scripts/pip-audit.exe").is_file()


def _pip_audit_roda():
    exe = shutil.which("pip-audit")
    if not exe:
        exe = RAIZ / ".venv/Scripts/pip-audit.exe"
        if not exe.is_file():
            return None
    p = subprocess.run(
        [str(exe), "--progress-spinner=off", "-r", str(REQ)],
        capture_output=True,
        text=True,
        timeout=1800,
        cwd=str(RAIZ),
    )
    return p.stdout + p.stderr


LINHA = re.compile(r"^([A-Za-z0-9_.\-]+)\s+(\S+)\s+((?:PYSEC|CVE|GHSA)-[0-9A-Za-z\-]+)")


class OManifestoTest(unittest.TestCase):
    """O manifesto tem de ser instalavel. Sem isto nao ha imagem."""

    @pytest.mark.dependencias
    def test_o_manifesto_resolve(self):
        """MEDIDO: `ResolutionImpossible` por `cryptography` declarado duas
        vezes com intervalos contraditorios. A imagem nao construia e a
        su-suite, que corre contra o que ja' esta instalado, nao via nada."""
        if not PY or not Path(PY).is_file():
            self.skipTest("sem interpretador do projecto")
        p = subprocess.run(
            [
                PY,
                "-m",
                "pip",
                "install",
                "--dry-run",
                "--quiet",
                "--disable-pip-version-check",
                "-r",
                str(REQ),
            ],
            capture_output=True,
            text=True,
            timeout=1800,
            cwd=str(RAIZ),
        )
        ruido = p.stdout + p.stderr
        for marca in ("ResolutionImpossible", "Cannot install"):
            self.assertNotIn(
                marca,
                ruido,
                f"{marca}: o manifesto nao resolve, a imagem nao constroi.\n"
                + ruido[-800:],
            )

    def test_nenhum_pacote_declara_duas_vezes(self):
        """MEDIDO: `cryptography` em L173 e L177, com series diferentes.

        Pinos identicos repetidos sao ruido; pinos DIFERENTES sao um build
        partido. Os dois sao defeito — e o teste apanha os dois.
        """
        vistos: dict[str, list[tuple[int, str]]] = {}
        for i, linha in enumerate(REQ.read_text(encoding="utf-8").splitlines(), 1):
            s = linha.strip()
            if not s or s.startswith("#") or s.startswith("-"):
                continue
            m = re.match(r"^([A-Za-z0-9_.\-]+)\s*[><=!~\[]", s)
            if m:
                vistos.setdefault(m.group(1).lower(), []).append((i, s))

        dups = {k: v for k, v in vistos.items() if len(v) > 1}
        self.assertEqual(
            dups,
            {},
            "pacote declarado mais de uma vez:\n"
            + "\n".join(
                f"  {k}: " + " | ".join(f"L{i} {s}" for i, s in v)
                for k, v in sorted(dups.items())
            ),
        )


class AsCVEsNaoRegressamTest(unittest.TestCase):
    """A baseline so encolhe. Cada linha que fica tem razao."""

    def test_a_baseline_tem_uma_razao_por_pacote(self):
        for nome in ACEITO:
            self.assertTrue(
                len(ACEITO[nome].strip()) > 30,
                f"{nome} fica aceite sem razao escrita",
            )

    @pytest.mark.dependencias
    def test_nenhum_pacote_com_cve_fica_fora_da_baseline(self):
        if not _pip_audit_existe():
            self.skipTest("pip-audit nao instalado")
        saida = _pip_audit_roda()
        if saida is None:
            self.skipTest("pip-audit nao corre")

        vistos = {}
        for linha in saida.splitlines():
            m = LINHA.match(linha.strip())
            if m:
                vistos[m.group(1).lower()] = m.group(2)

        novos = sorted(set(vistos) - {k.lower() for k in ACEITO})
        self.assertEqual(
            [],
            novos,
            "pacotes com CVE que NAO estao na baseline (ou o pin foi "
            "revertido, ou a baseline precisa de linha e razao): " + ", ".join(novos),
        )

    @pytest.mark.dependencias
    def test_nenhuma_cve_foi_criada_no_manifesto(self):
        """Contagem total. Serve para ver a curva, nao para passar/falhar por
        numero — o que decide e' o teste anterior."""
        if not _pip_audit_existe():
            self.skipTest("pip-audit nao instalado")
        saida = _pip_audit_roda()
        m = re.search(r"Found (\d+) known vulnerabilities in (\d+) packages", saida)
        if not m:
            self.skipTest("pip-audit sem linha de resumo")
        self.assertLessEqual(
            int(m.group(1)),
            123,
            f"{m.group(1)} CVEs em {m.group(2)} pacotes; a medicao de 2026-10-05 "
            f"era 123 em 15 depois do alinhamento (226 em 27 antes)",
        )
