"""Vendoriza as bibliotecas de terceiros para `app/static/vendor/`.

Fase 2. O objectivo e que o desktop arranque e funcione sem rede — e, no
caminho, que o browser deixe de executar código que um CDN escolhe.

Uso:
    python backend/vendorizar.py            # descarrega o que falta
    python backend/vendorizar.py --verificar  # só confere checksums
    python backend/vendorizar.py --relatorio  # imprime o inventário

--------------------------------------------------------------------------
PORQUÊ ISTO TAMBÉM É UMA CORRECÇÃO DE SEGURANÇA
--------------------------------------------------------------------------
No momento em que isto foi escrito, `app/templates/financeiro/cashflow.html`
carregava:

    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>

Sem versão. O que essa linha executa é o que o jsDelivr decidir servir
**naquele momento** — e o produtor não tem voto. O mesmo valia para
`html5-qrcode`. Isto é uma dependência de execução resolvida em tempo de
execução, contra a política do projecto (ver `requirements.txt`, que fixa
versões com comentários a explicar cada pin).

Vendorizar resolve as duas coisas com o mesmo gesto: o desktop fica
offline **e** a porta fecha. A versão passa a estar escrita no código.

--------------------------------------------------------------------------
O QUE NÃO É VENDORIZÁVEL, E PORQUÊ
--------------------------------------------------------------------------
`api.open-meteo.com`, `nominatim.openstreetmap.org`, os tiles do
OpenStreetMap e `agrodocai.com.br` são **serviços**, não bibliotecas.
Clima e geocodificação não existem offline: não há ficheiro para
descarregar que os substitua. Ficam de fora, e o que o desktop faz sem
eles está escrito na Fase 2 do plano.

`esm.run` e `huggingface.co` (WebLLM e Whisper) também ficam de fora: os
pesos do modelo são centenas de MB e são pack opcional, não instalação.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

# ---------------------------------------------------------------------------
# ONDE FICA TUDO
# ---------------------------------------------------------------------------


def _raiz() -> Path:
    aqui = Path(__file__).resolve().parent
    for candidato in (aqui, *aqui.parents):
        if (candidato / "manage.py").is_file() and (candidato / "app").is_dir():
            return candidato
    raise SystemExit("raiz do repositório não encontrada")


RAIZ = _raiz()
DESTINO = RAIZ / "app" / "static" / "vendor"
MANIFESTO = DESTINO / "manifesto.json"

#: Tempo máximo por download. Um CDN lento que não responde tem de dar
#: erro, não travar o script durante a noite.
TIMEOUT = 60

# ---------------------------------------------------------------------------
# A LISTA — tudo com versão, sempre
# ---------------------------------------------------------------------------
# `destino` é relativo a `app/static/vendor/`.
#
# `Chart.js` entra **uma vez**, na 4.4.7. Havia três versões em uso
# (4.4.0, 4.4.7, e uma sem versão) em páginas diferentes; unificar é uma
# decisão do dono do projecto, não uma consequência de vendorizar. Ver
# `PLAN.md`, Fase 2.
#
# `bootstrap-icons` entra na 1.11.3 (a mais recente das duas em uso).

BIBLIOTECAS: list[dict] = [
    # --- Bootstrap (operário) ---
    {
        "nome": "bootstrap",
        "versao": "5.3.2",
        "licenca": "MIT",
        "ficheiros": [
            (
                "https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css",
                "bootstrap-5.3.2.min.css",
            ),
            (
                "https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js",
                "bootstrap-5.3.2.bundle.min.js",
            ),
        ],
    },
    # --- Bootstrap Icons ---
    {
        "nome": "bootstrap-icons",
        "versao": "1.11.3",
        "licenca": "MIT",
        "ficheiros": [
            (
                "https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css",
                "bootstrap-icons-1.11.3.min.css",
            ),
            # O CSS `@font-face` aponta para `fonts/bootstrap-icons.woff2`
            # e `.woff`. O nome e a pasta TEM de ser o do CSS: um ficheiro
            # com o nome certo na pasta errada dá 404, o ícone não
            # aparece, e não há erro nenhum — o CSS é servido, o browser
            # simplesmente não tem o que desenhar dentro.
            (
                "https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/fonts/bootstrap-icons.woff2",
                "fonts/bootstrap-icons.woff2",
            ),
            (
                "https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/fonts/bootstrap-icons.woff",
                "fonts/bootstrap-icons.woff",
            ),
        ],
    },
    # --- Chart.js (UNIFICADO) ---
    {
        "nome": "chart.js",
        "versao": "4.4.7",
        "licenca": "MIT",
        "ficheiros": [
            (
                "https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js",
                "chart.umd-4.4.7.min.js",
            ),
        ],
    },
    # --- htmx ---
    {
        "nome": "htmx",
        "versao": "1.9.10",
        "licenca": "BSD-2-Clause",
        "ficheiros": [
            ("https://unpkg.com/htmx.org@1.9.10", "htmx-1.9.10.min.js"),
        ],
    },
    # --- Leaflet + Leaflet Draw (mapa) ---
    {
        "nome": "leaflet",
        "versao": "1.9.4",
        "licenca": "BSD-2-Clause",
        "ficheiros": [
            ("https://unpkg.com/leaflet@1.9.4/dist/leaflet.js", "leaflet-1.9.4.js"),
            (
                "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css",
                "leaflet-1.9.4.css",
            ),
            # `marker-icon.png` e `marker-shadow.png`: o `@font-face` do
            # CSS pede-os por caminho relativo. Sem eles, o mapa carrega
            # SEM o marcador (foi o que a CSP de `img-src` já documenteva
            # em `base.py`).
            #
            # `layers.png` e `layers-2x.png` faltavam na primeira
            # vendorização: o `leaflet.css` pede-os no bloco do controlo de
            # camadas, e sem eles o botão de camadas aparece sem imagem.
            # Só se descobre lendo o CSS à procura de `url(...)` — o
            # `vendorizar.py --verificar` faz isso agora automaticamente.
            (
                "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
                "images/marker-icon.png",
            ),
            (
                "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
                "images/marker-shadow.png",
            ),
            (
                "https://unpkg.com/leaflet@1.9.4/dist/images/layers.png",
                "images/layers.png",
            ),
            (
                "https://unpkg.com/leaflet@1.9.4/dist/images/layers-2x.png",
                "images/layers-2x.png",
            ),
        ],
    },
    {
        "nome": "leaflet-draw",
        "versao": "1.0.4",
        "licenca": "MIT",
        "ficheiros": [
            (
                "https://unpkg.com/leaflet-draw@1.0.4/dist/leaflet.draw.js",
                "leaflet-draw-1.0.4.js",
            ),
            (
                "https://unpkg.com/leaflet-draw@1.0.4/dist/leaflet.draw.css",
                "leaflet-draw-1.0.4.css",
            ),
            (
                "https://unpkg.com/leaflet-draw@1.0.4/dist/images/spritesheet.png",
                "images/spritesheet.png",
            ),
            # `spritesheet.svg` tambem: o `leaflet.draw.css` aponta para
            # ele numa das variantes. So `.png` deixa um botao de desenho a
            # usar a folha errada.
            (
                "https://unpkg.com/leaflet-draw@1.0.4/dist/images/spritesheet.svg",
                "images/spritesheet.svg",
            ),
            (
                "https://unpkg.com/leaflet-draw@1.0.4/dist/images/spritesheet-2x.png",
                "images/spritesheet-2x.png",
            ),
        ],
    },
    # --- SweetAlert2 ---
    {
        "nome": "sweetalert2",
        "versao": "11.22.4",
        "licenca": "MIT",
        "ficheiros": [
            (
                "https://cdn.jsdelivr.net/npm/sweetalert2@11.22.4/dist/sweetalert2.all.min.js",
                "sweetalert2-11.22.4.all.min.js",
            ),
        ],
    },
    # --- QR ---
    {
        "nome": "qrcodejs",
        "versao": "1.0.0",
        "licenca": "MIT",
        "ficheiros": [
            (
                "https://cdn.jsdelivr.net/npm/qrcodejs@1.0.0/qrcode.min.js",
                "qrcodejs-1.0.0.min.js",
            ),
        ],
    },
    {
        "nome": "html5-qrcode",
        "versao": "2.3.8",
        "licenca": "Apache-2.0",
        "ficheiros": [
            (
                "https://unpkg.com/html5-qrcode@2.3.8/html5-qrcode.min.js",
                "html5-qrcode-2.3.8.min.js",
            ),
        ],
    },
]

# ---------------------------------------------------------------------------
# IMAGENS DECORATIVAS
# ---------------------------------------------------------------------------
# Estas NÃO apareceram no inventário inicial, que só varria `.html` e
# `.js`. Apareceram porque o gate da Fase 2 as viu a ser pedidas — e é
# exactamente para isso que o gate existe: um inventário feito à partida
# só encontra o que se pensou em procurar.
#
# São quatro fundos da página de login, em duas resoluções (1000 px e
# 600 px) para ecrãs pequenos e grandes. São a ÚNICA coisa que a página de
# login pede a um servidor externo — o resto já é todo local.
#
# `q=80` e `fit=crop` já vêm na URL: o que se guarda é a imagem já
# comprimida, não um original de 4 MB.

IMAGENS: list[tuple[str, str]] = [
    (
        "https://images.unsplash.com/photo-1586771107445-d3ca888129ff?q=80&w=1000&auto=format&fit=crop",
        "fundos/login-1000.jpg",
    ),
    (
        "https://images.unsplash.com/photo-1512314889357-e157c22f938d?q=80&w=600&auto=format&fit=crop",
        "fundos/login-600.jpg",
    ),
    (
        "https://images.unsplash.com/photo-1551288049-bebda4e38f71?q=80&w=1000&auto=format&fit=crop",
        "fundos/telemetria-1000.jpg",
    ),
    (
        "https://images.unsplash.com/photo-1555421689-491a97ff2040?q=80&w=600&auto=format&fit=crop",
        "fundos/telemetria-600.jpg",
    ),
]

# ---------------------------------------------------------------------------
# FONTES DO GOOGLE — o caso especial
# ---------------------------------------------------------------------------
# O `fonts.googleapis.com/css2?...` devolve um CSS que, por sua vez,
# aponta para ficheiros `.woff2` em `fonts.gstatic.com`. Vendorizar só o
# CSS não chega: o browser ia buscá-los à rede de qualquer maneira.
#
# Por isso o download é em duas fases: primeiro o CSS, depois os ficheiros
# que ele referencia, e o CSS é reescrito para apontar para o caminho local.
#
# As famílias que os templates pedem estão reunidas aqui. Estão escritas
# por extenso porque o pedido de uma família tem de ser feito uma vez só:
# descarregar três `css2` separados traria os mesmos ficheiros duas vezes.
#
# `IBM+Plex+Sans` é o nome **codificado para URL** (espaço → `+`), e é por
# isso que este mapa existe: o `+` já está dentro do nome da família e não
# pode servir de separador.

FONTES = {
    "Inter": "Inter:wght@300;400;500;600;700",
    "Sora": "Sora:wght@500;600;700;800",
    "IBM Plex Sans": "IBM+Plex+Sans:wght@400;500;600;700",
    "JetBrains Mono": "JetBrains+Mono:wght@500;600;700",
}

#: O `css2` separa famílias com `&family=`, **não** com `+`. Juntar com `+`
#: produz `IBM+Plex+Sans+wght@400;...` e o Google responde `HTTP 400
#: Bad Request` — que foi o que aconteceu na primeira execução.
FAMILIAS_CSS = "&".join(f"family={v}" for v in FONTES.values())


def _sha256(dados: bytes) -> str:
    return hashlib.sha256(dados).hexdigest()


def _baixar(url: str) -> bytes:
    pedido = urllib.request.Request(
        url, headers={"User-Agent": "Ampliagro-Desktop-Vendor/1.0"}
    )
    with urllib.request.urlopen(pedido, timeout=TIMEOUT) as r:
        return r.read()


def vendorizar(verificar_so: bool = False) -> int:
    DESTINO.mkdir(parents=True, exist_ok=True)
    registo: list[dict] = []
    falhas: list[str] = []

    # ---------------- bibliotecas ----------------
    for lib in BIBLIOTECAS:
        for url, relativo in lib["ficheiros"]:
            destino = DESTINO / relativo
            destino.parent.mkdir(parents=True, exist_ok=True)
            chave = f"{lib['nome']}@{lib['versao']}/{relativo}"

            if destino.is_file() and not verificar_so:
                # Já existe de uma corrida anterior: não se volta a
                # descargar. Guardar o hash que já está no manifesto é
                # mais barato do que refazer o request.
                registo.append(
                    {
                        "chave": chave,
                        "ficheiro": relativo,
                        "url": url,
                        "bytes": destino.stat().st_size,
                        "reutilizado": True,
                    }
                )
                continue

            try:
                dados = _baixar(url)
            except (urllib.error.URLError, OSError, TimeoutError) as e:
                falhas.append(f"{url} — {e}")
                print(f"  [FALHA] {url}\n          {e}")
                continue

            destino.write_bytes(dados)
            registo.append(
                {
                    "chave": chave,
                    "ficheiro": relativo,
                    "url": url,
                    "bytes": len(dados),
                    "sha256": _sha256(dados),
                    "licenca": lib["licenca"],
                    "versao": lib["versao"],
                }
            )
            print(
                f"  [ok] {lib['nome']}@{lib['versao']}  {relativo}  {len(dados) / 1024:.0f} KB"
            )

    # ---------------- imagens decorativas ----------------
    for url, relativo in IMAGENS:
        destino = DESTINO / relativo
        destino.parent.mkdir(parents=True, exist_ok=True)
        if destino.is_file() and not verificar_so:
            registo.append(
                {
                    "chave": f"imagem/{relativo}",
                    "ficheiro": relativo,
                    "url": url,
                    "bytes": destino.stat().st_size,
                    "reutilizado": True,
                }
            )
            continue
        try:
            dados = _baixar(url)
        except (urllib.error.URLError, OSError) as e:
            falhas.append(f"{url} — {e}")
            print(f"  [FALHA] {url}\n          {e}")
            continue
        destino.write_bytes(dados)
        registo.append(
            {
                "chave": f"imagem/{relativo}",
                "ficheiro": relativo,
                "url": url,
                "bytes": len(dados),
                "sha256": _sha256(dados),
                "licenca": "Unsplash License",
                "nota": "Fundo decorativo. Vendorizado porque é a única "
                "coisa da página de login que pedia rede.",
            }
        )
        print(f"  [ok] fundo  {relativo}  {len(dados) / 1024:.0f} KB")

    # ---------------- fontes ----------------
    registo += _vendorizar_fontes()

    # ---------------- manifesto ----------------
    if falhas:
        print(
            f"\n{len(falhas)} descarga(s) falharam — o manifesto NÃO foi actualizado."
        )
        return 1

    total = sum(r.get("bytes", 0) for r in registo)
    MANIFESTO.write_text(
        json.dumps(
            {
                "gerado_em": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "total_bytes": total,
                "entradas": registo,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print(
        f"\nTotal vendorizado: {total / 1024 / 1024:.1f} MB em {len(registo)} ficheiros"
    )
    print(f"Manifesto: {MANIFESTO.relative_to(RAIZ)}")
    return 0


def _vendorizar_fontes() -> list[dict]:
    """Descarrega o CSS das fontes E os `.woff2` que ele pede.

    O truque está em `-H 'User-Agent: …'`: o `fonts.googleapis.com` devolve
    CSS **diferente** conforme o browser. Com um User-Agent antigo recebe-se
    `truetype`; com um moderno, `woff2`. Pedir `woff2` e depois reescrever
    o CSS para caminhos locais é o que fecha mesmo a última ida à rede.
    """
    registo: list[dict] = []
    pasta_fontes = DESTINO / "fonts"
    pasta_fontes.mkdir(parents=True, exist_ok=True)

    # `FAMILIAS_CSS` já traz `family=` em cada parte. Prefixar outro
    # `family=` aqui produz `css2?family=family=Inter:...`, e o Google
    # responde `HTTP 400 Bad Request` — ao passo que o `curl` na MESMA
    # URL devolveria 200, porque o `curl` não tem este bug.
    url_css = f"https://fonts.googleapis.com/css2?{FAMILIAS_CSS}&display=swap"

    try:
        pedido = urllib.request.Request(
            url_css,
            headers={
                # User-Agent de browser moderno: é o que faz o Google
                # devolver `woff2` em vez de `truetype`.
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                )
            },
        )
        with urllib.request.urlopen(pedido, timeout=TIMEOUT) as r:
            css = r.read().decode("utf-8")
    except (urllib.error.URLError, OSError) as e:
        print(f"  [FALHA] CSS das fontes: {e}")
        return registo

    # URLs dentro do CSS: `https://fonts.gstatic.com/s/...woff2`
    urls_css = sorted(
        set(re.findall(r"url\((https://fonts\.gstatic\.com/[^)]+)\)", css))
    )
    substit: dict[str, str] = {}

    for i, url in enumerate(urls_css):
        nome = url.rsplit("/", 1)[-1].split("?")[0]
        # Um prefixo por família evita 40 ficheiros com o mesmo nome.
        local = f"f{i:03d}-{nome}"
        destino = pasta_fontes / local
        try:
            dados = _baixar(url)
        except (urllib.error.URLError, OSError) as e:
            print(f"  [FALHA] {url}: {e}")
            continue
        destino.write_bytes(dados)
        substit[url] = f"fonts/{local}"
        registo.append(
            {
                "chave": f"fonte/{local}",
                "ficheiro": f"fonts/{local}",
                "url": url,
                "bytes": len(dados),
                "sha256": _sha256(dados),
                "licenca": "OFL-1.1",
            }
        )

    for url, local in substit.items():
        css = css.replace(url, local)

    css_local = DESTINO / "fontes.css"
    # `write_bytes`, não `write_text`.
    #
    # `write_text` abre em modo texto, e no Windows o modo texto traduz
    # `\n` para `\r\n` ao escrever. O hash era calculado sobre o `css`
    # em memória (com `\n`) e o ficheiro em disco ficava com `\r\n` — o
    # `--verificar` acusava `[ALTERADO] fontes.css` logo a seguir, sem
    # que nada tivesse mudado.
    #
    # Escrever bytes é o que garante que o que se hasheia é exactamente o
    # que fica em disco, nos três SOs.
    css_bytes = css.encode("utf-8")
    css_local.write_bytes(css_bytes)
    registo.append(
        {
            "chave": "fontes/css",
            "ficheiro": "fontes.css",
            "url": url_css,
            "bytes": len(css_bytes),
            "sha256": _sha256(css_bytes),
            "licenca": "OFL-1.1",
            "nota": "CSS reescrito: os url() apontam para fonts/ locais",
        }
    )
    print(f"  [ok] fontes: {len(substit)} .woff2 + CSS reescrito")

    return registo


def verificar_url_css() -> int:
    """Todo o `url(...)` de um CSS vendorizado tem de existir no disco.

    Esta verificação não existia na primeira versão e devia ter existido.

    O sintoma de um `url()` partido é o pior possível: o CSS é servido
    com 200, o browser aplica-o, e o que falta — uma fonte, uma imagem de
    um sprite — simplesmente não aparece. Não há 404 no painel, não há
    erro no consola, e o produtor vê um ícone ou um botão sem desenho e
    diz "o estilo está mal".

    Foi o que aconteceu duas vezes na primeira vendorização:

    - `bootstrap-icons.min.css` pede `fonts/bootstrap-icons.woff2`, e o
      ficheiro tinha sido posto na raiz de `vendor/` com outro nome. Os
      ícones apareciam como caixas vazias.
    - `leaflet.css` pede `images/layers.png` e `images/layers-2x.png`,
      que não tinham sido descarregados. O controlo de camadas do mapa
      aparecia sem imagem.

    Nenhum dos dois aparece numa lista de ficheiros: o CSS estava lá, o
    `url()` estava lá. Só a comparação com o disco o revela.
    """
    problema = 0
    # `url(#default#VML)` é uma referência interna do IE dentro do SVG do
    # Leaflet, não um ficheiro.
    padrao = re.compile(r"url\(['\"]?([^'\")#][^'\")]*)['\"]?\)")

    for css in sorted(DESTINO.rglob("*.css")):
        texto = css.read_text(encoding="utf-8", errors="replace")
        for alvo in sorted(set(padrao.findall(texto))):
            # Tira a query string: `?v=1` não faz parte do nome.
            limpo = alvo.split("?")[0].strip()
            if not limpo or limpo.startswith(("data:", "http")):
                continue
            resolvido = (css.parent / limpo).resolve()
            if not resolvido.is_file():
                print(f"  [PARTIDO] {css.name} -> {limpo}  (não existe)")
                problema += 1

    if problema:
        print(f"\n{problema} referencia(s) de CSS a ficheiros que não existem.")
    else:
        print("Todos os url() dos CSS vendorizados resolvem para ficheiros reais.")
    return 1 if problema else 0


def verificar() -> int:
    if not MANIFESTO.is_file():
        print("sem manifesto — correr `vendorizar.py` primeiro")
        return 1
    dados = json.loads(MANIFESTO.read_text(encoding="utf-8"))
    mau = 0
    for entrada in dados["entradas"]:
        if "sha256" not in entrada:
            continue
        caminho = DESTINO / entrada["ficheiro"]
        if not caminho.is_file():
            print(f"  [FALTA] {entrada['ficheiro']}")
            mau += 1
            continue
        actual = _sha256(caminho.read_bytes())
        if actual != entrada["sha256"]:
            print(f"  [ALTERADO] {entrada['ficheiro']}")
            mau += 1
    total = len(dados["entradas"])
    print(f"\n{total} entradas, {mau} com problema")

    # Os checksums dizem que os ficheiros não mudaram desde o download.
    # Não dizem que as referências internas do CSS estão certas — é um
    # ficheiro válido, a apontar para um ficheiro que não existe.
    print()
    rc_url = verificar_url_css()
    return 1 if (mau or rc_url) else 0


def relatorio() -> int:
    """Lista do que a CSP ainda tem de permitir, e do que já não precisa."""
    if MANIFESTO.is_file():
        dados = json.loads(MANIFESTO.read_text(encoding="utf-8"))
        print(f"VENDORIZADO: {dados['total_bytes'] / 1024 / 1024:.1f} MB")
        print(f"  gerado em {dados['gerado_em']}\n")
        for e in dados["entradas"]:
            print(f"  {e['ficheiro']:<48}{e.get('bytes', 0) / 1024:>8.0f} KB")
    else:
        print("AINDA NAO VENDORIZADO")

    print("\n\nSERVICOS QUE NAO SAO VENDORIZAVEIS (ficam de fora, de propósito):")
    for s in (
        "api.open-meteo.com        — clima (servico)",
        "nominatim.openstreetmap.org — geocodificacao reversa (servico)",
        "*.tile.openstreetmap.org  — tiles do mapa (servico)",
        "agrodocai.com.br          — cotacoes (servico)",
        "esm.run / huggingface.co  — WebLLM e Whisper (pack opcional, Fase 4)",
    ):
        print(f"  {s}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Vendoriza as CDN para app/static/vendor")
    ap.add_argument("--verificar", action="store_true", help="Confere os checksums")
    ap.add_argument("--relatorio", action="store_true", help="Imprime o inventário")
    args = ap.parse_args()

    if args.verificar:
        return verificar()
    if args.relatorio:
        return relatorio()
    return vendorizar()


if __name__ == "__main__":
    sys.exit(main())
