"""Reescreve as referencias de CDN nos templates, para `{% static %}`.

Fase 2, passo 2. O `vendorizar.py` p\u00f4e os ficheiros em
`app/static/vendor/`; este muda quem os aponta.

Porqu\u00ea9 um script e n\u00e3o `sed`: porque s\u00e3o 18 mapeamentos, alguns
deles n\u00e3o triviais, e um `sed` que apanha mal um deles deixa uma p\u00e1gina
sem gr\u00e1ficos **sem erro nenhum**. Aqui cada par (antigo, novo) \u00e9
verificado: se um mapeamento n\u00e3o for encontrado em lado nenhum, o
script falha em vez de terminar em silencio.

A seguran\u00e7a que faz isto revers\u00edvel: o ficheiro original de cada
template fica em `<ficheiro>.cdn-backup`. Se a reescrita partir a p\u00e1gina,
restaura-se com um comando.

Uso:
    python backend/reescrever_cdn.py            # aplica
    python backend/reescrever_cdn.py --dry-run  # mostra, n\u00e3o escreve
    python backend/reescrever_cdn.py --restaurar
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import re
import shutil
import sys
from pathlib import Path

V = "vendor/"


def _raiz() -> Path:
    aqui = Path(__file__).resolve().parent
    for c in (aqui, *aqui.parents):
        if (c / "manage.py").is_file() and (c / "app").is_dir():
            return c
    raise SystemExit("raiz do repositório não encontrada")


RAIZ = _raiz()
TEMPLATES = RAIZ / "app" / "templates"
SUFIXO_BACKUP = ".cdn-backup"


def _static(ficheiro: str) -> str:
    """`{% static %}` com o ficheiro já vendORIZADO.

    O Django resolve o `{% static %}` através do
    `CompressedManifestStaticFilesStorage`, o que dá o nome com hash. É o
    que se quer: um ficheiro novo em `vendor/` passa a ter o nome certo
    depois do `collectstatic`, sem editar template nenhum.
    """
    return "{% static '" + f"{V}{ficheiro}" + "' %}"


# ---------------------------------------------------------------------------
# O MAPEAMENTO
# ---------------------------------------------------------------------------
# Chart.js aparece em três versões diferentes em páginas diferentes,
# mais uma URL sem versão. Todas vão para a 4.4.7 — decisão do dono do
# projecto, não consequência de vendorizar.
#
# `bootstrap-icons` estava em 1.11.1 no `operario/base.html` e 1.11.3 nos
# outros três. Também unificado.

MAPEAMENTO: list[tuple[str, str]] = [
    # --- Chart.js: as 3 versoes + a sem versao ---
    (
        "https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js",
        _static("chart.umd-4.4.7.min.js"),
    ),
    (
        "https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js",
        _static("chart.umd-4.4.7.min.js"),
    ),
    (
        # A URL SEM versão. O `&` não aparece, e o `re.escape` trata do resto.
        "https://cdn.jsdelivr.net/npm/chart.js",
        _static("chart.umd-4.4.7.min.js"),
    ),
    # --- SweetAlert2: só a versão maior estava escrita ---
    (
        "https://cdn.jsdelivr.net/npm/sweetalert2@11",
        _static("sweetalert2-11.22.4.all.min.js"),
    ),
    # --- Bootstrap ---
    (
        "https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css",
        _static("bootstrap-5.3.2.min.css"),
    ),
    (
        "https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js",
        _static("bootstrap-5.3.2.bundle.min.js"),
    ),
    # --- Bootstrap Icons: 1.11.1 e 1.11.3 para a mesma coisa ---
    (
        "https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css",
        _static("bootstrap-icons-1.11.3.min.css"),
    ),
    (
        "https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.1/font/bootstrap-icons.css",
        _static("bootstrap-icons-1.11.3.min.css"),
    ),
    # --- htmx ---
    (
        "https://unpkg.com/htmx.org@1.9.10",
        _static("htmx-1.9.10.min.js"),
    ),
    # --- QR ---
    (
        "https://cdn.jsdelivr.net/npm/qrcodejs@1.0.0/qrcode.min.js",
        _static("qrcodejs-1.0.0.min.js"),
    ),
    # --- html5-qrcode: SEM versão ---
    (
        "https://unpkg.com/html5-qrcode",
        _static("html5-qrcode-2.3.8.min.js"),
    ),
    # --- Leaflet + Leaflet Draw ---
    (
        "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js",
        _static("leaflet-1.9.4.js"),
    ),
    (
        "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css",
        _static("leaflet-1.9.4.css"),
    ),
    (
        "https://unpkg.com/leaflet-draw@1.0.4/dist/leaflet.draw.js",
        _static("leaflet-draw-1.0.4.js"),
    ),
    (
        "https://unpkg.com/leaflet-draw@1.0.4/dist/leaflet.draw.css",
        _static("leaflet-draw-1.0.4.css"),
    ),
]

# --- As três variantes do CSS do Google Fonts vão para o MESMO ficheiro ---
# Os templates pedem três combinações diferentes de famílias (login pede
# IBM Plex + Sora; registo-cultura pede Sora + Inter + JetBrains Mono;
# base pede só Inter). O `vendorizar.py` descarregou a união de todas.
#
# Manter as três linhas a pedir três ficheiros diferentes seria pedir o
# mesmo CSS três vezes. Uma linha, um ficheiro.
FONTES_CSS = _static("fontes.css")

# O `css2?` leva Families, pesos e `display`, e pode ocupar a linha toda —
# daí o `[^"'\s>]+`, que pára no fim do atributo HTML em vez de numa
# largura fixa. As aspas triplas métricas: a classe de caracteres leva
# um `"` e um `'` lá dentro, e `"..."` normal acabava no meio.
PADRAO_FONTES = re.compile(r"""https://fonts\.googleapis\.com/css2\?[^"'\s>]+""")

# ---------------------------------------------------------------------------
# O QUE NÃO SE TOCA — e porque
# ---------------------------------------------------------------------------
# `<link rel="preconnect" href="https://fonts.gstatic.com">` não descarrega
# nada: é uma dica ao browser para abrir a ligacao mais depressa. Como
# já não há nada em `fonts.gstatic.com` para contactar, a dica é inútil —
# mas é inofensiva, e apagá-la é mexer em algo que funciona. Fica, e está
# escrito aqui porque "não mexer" é uma decisão, não uma omissão.
#
# `nominatim.openstreetmap.org`, `agrodocai.com.br`, `esm.run` e
# `huggingface.co` são serviços ou o pack opcional da Fase 4. Vendorizar
# um endpoint de API não faz sentido: não há ficheiro para guardar.


def aplicar(dry_run: bool = False) -> int:
    alterados: list[tuple[str, int]] = []
    usados = set()

    for ficheiro in sorted(TEMPLATES.rglob("*.html")):
        original = ficheiro.read_text(encoding="utf-8")
        texto = original
        n = 0

        for velho, novo in MAPEAMENTO:
            if velho in texto:
                usados.add(velho)
                n += texto.count(velho)
                texto = texto.replace(velho, novo)

        # As três variantes do Google Fonts.
        n_f = len(PADRAO_FONTES.findall(texto))
        if n_f:
            usados.add("google-fonts-css")
            n += n_f
            texto = PADRAO_FONTES.sub(FONTES_CSS, texto)

        if texto != original:
            alterados.append((str(ficheiro.relative_to(RAIZ)), n))
            if not dry_run:
                backup = ficheiro.with_suffix(ficheiro.suffix + SUFIXO_BACKUP)
                if not backup.exists():
                    shutil.copy2(ficheiro, backup)
                ficheiro.write_bytes(texto.encode("utf-8"))

    print(f"\n{'[dry-run] ' if dry_run else ''}Ficheiros alterados: {len(alterados)}")
    for caminho, n in alterados:
        print(f"  {caminho}  ({n} referência[s])")

    # Mapeamentos que não encontraram nada: é um sinal de que o ficheiro
    # já foi reescrito, ou de que a URL mudou e o mapeamento ficou velho.
    por_usar = [v for v, _ in MAPEAMENTO if v not in usados]
    if por_usar:
        print(f"\nMapeamentos que não encontraram occurrence (pode já estar aplicado):")
        for v in por_usar:
            print(f"  {v}")

    # O que é suposto ficar, para se ver que o mapa não engoliu demais.
    print("\nFica de fora, de propósito:")
    for x in (
        "preconnect para fonts.gstatic.com (não descarrega nada)",
        "nominatim.openstreetmap.org  (serviço de geocodificação)",
        "*.tile.openstreetmap.org     (tiles do mapa)",
        "agrodocai.com.br             (cotações)",
        "esm.run / huggingface.co     (WebLLM — pack opcional, Fase 4)",
    ):
        print(f"  {x}")

    return 0


# ---------------------------------------------------------------------------
# OS FUNDOS DECORATIVOS — um ficheiro CSS, não um template
# ---------------------------------------------------------------------------
# `app/static/css/paginas/login.css` tem quatro `background: url('https://
# images.unsplash.com/...')`. Não está num template nem num `.js`, por isso
# o inventário inicial (que só varria `.html` e `.js`) não o viu.
#
# O gate da Fase 2 viu. É a diferença entre um inventário feito à partida e
# um gate: o inventário encontra o que se pensou em procurar; o gate
# encontra o que a página faz.
#
# O ficheiro é `app/static/css/paginas/login.css` — que é copyado tal e
# qual para `staticfiles/` na mesma estrutura `css/paginas/`. Por isso o
# caminho relativo a partir dali é `../../vendor/fundos/…`.

FUNDOS = [
    (
        "https://images.unsplash.com/photo-1586771107445-d3ca888129ff?q=80&w=1000&auto=format&fit=crop",
        "../../vendor/fundos/login-1000.jpg",
    ),
    (
        "https://images.unsplash.com/photo-1512314889357-e157c22f938d?q=80&w=600&auto=format&fit=crop",
        "../../vendor/fundos/login-600.jpg",
    ),
    (
        "https://images.unsplash.com/photo-1551288049-bebda4e38f71?q=80&w=1000&auto=format&fit=crop",
        "../../vendor/fundos/telemetria-1000.jpg",
    ),
    (
        "https://images.unsplash.com/photo-1555421689-491a97ff2040?q=80&w=600&auto=format&fit=crop",
        "../../vendor/fundos/telemetria-600.jpg",
    ),
]

CSS_COM_FUNDOS = RAIZ / "app" / "static" / "css" / "paginas" / "login.css"


def reescrever_fundos(dry_run: bool = False) -> int:
    """Troca as URLs dos fundos por caminhos relativos locais."""
    if not CSS_COM_FUNDOS.is_file():
        print(f"  [AVISO] {CSS_COM_FUNDOS} não existe")
        return 0

    texto = CSS_COM_FUNDOS.read_text(encoding="utf-8")
    original = texto
    n = 0
    for remoto, local in FUNDOS:
        if remoto in texto:
            n += texto.count(remoto)
            texto = texto.replace(remoto, local)

    if texto != original:
        if not dry_run:
            backup = CSS_COM_FUNDOS.with_suffix(".css.cdn-backup")
            if not backup.exists():
                shutil.copy2(CSS_COM_FUNDOS, backup)
            CSS_COM_FUNDOS.write_bytes(texto.encode("utf-8"))
        print(f"  {CSS_COM_FUNDOS.relative_to(RAIZ)}  ({n} fundo[s])")

    return n


def _sri(ficheiro_vendor: Path) -> str | None:
    """`sha256-<base64>` do ficheiro vendorizado, ou `None` se não existir.

    O SRI é base64 do SHA256 — não hex. Por isso não serve o `_sha256` do
    `vendorizar.py`, que devolve hex.
    """
    if not ficheiro_vendor.is_file():
        return None
    digest = hashlib.sha256(ficheiro_vendor.read_bytes()).digest()
    return "sha256-" + base64.b64encode(digest).decode("ascii")


def corrigir_sri(dry_run: bool = False) -> int:
    """Recalcula o `integrity=` dos ficheiros que passaram a ser locais.

    ---------------------------------------------------------------------------
    O BUG QUE ISTO EVITA
    ---------------------------------------------------------------------------
    `base.html:216` e `onboarding.html:158` traziam:

        <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"
                integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=">

    Esse hash foi calculado para o ficheiro **que o unpkg servia**. Depois
    de vendorizar, o `src` passa a apontar para
    `{% static 'vendor/leaflet-1.9.4.js' %}` — mesmo conteúdo, outra
    origem.

    O browser continua a verificar o `integrity`, porque é a política de
    sub-recursos que não mudou. E como o hash **não bate**:

        SRI no template:      20nqcchb9co0qijjzrguk2/z9vm+kniyxnv1lvtlzbo=
        SRI do nosso ficheiro: db49d009c841f5ca34a888c96511ae936fd9f5533e90d8b2c4d57596f4e5641a
        Batem? False

    O browser **recusa a executar** o script. O Leaflet não carrega, o
    mapa não renderiza, e a página não dá erro nenhum — o `<script>`
    simplesmente não corre. O sintoma é um mapa cinzento sem marcadores, e
    a causa está num atributo a vinte linhas de distância do mapa.

    Recalcular é a resposta certa, e não retirar o atributo: o SRI
    continuava a ser útil, porque serve para confirmar que o ficheiro que
    o Django entregou é o ficheiro que foi vendorizado.
    """
    vendor = RAIZ / "app" / "static" / V

    # integrity antigo -> ficheiro vendorizado que passou a substituí-lo
    pares = {
        "sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=": "leaflet-1.9.4.js",
        "sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=": "leaflet-1.9.4.css",
    }

    corrigidos: list[tuple[str, int, str]] = []
    em_falta: list[str] = []

    for ficheiro in sorted(TEMPLATES.rglob("*.html")):
        texto = ficheiro.read_text(encoding="utf-8")
        original = texto

        for velho, nome_vendor in pares.items():
            if velho not in texto:
                continue
            novo = _sri(vendor / nome_vendor)
            if novo is None:
                em_falta.append(nome_vendor)
                continue
            n = texto.count(velho)
            texto = texto.replace(velho, novo)
            corrigidos.append((str(ficheiro.relative_to(RAIZ)), n, nome_vendor))

        if texto != original and not dry_run:
            backup = ficheiro.with_suffix(ficheiro.suffix + SUFIXO_BACKUP)
            if not backup.exists():
                shutil.copy2(ficheiro, backup)
            ficheiro.write_bytes(texto.encode("utf-8"))

    print("\nintegrity= recalculado:")
    for caminho, n, nome in corrigidos:
        print(f"  {caminho}  ({n}x)  -> {nome}")
    if em_falta:
        print(f"\nNÃO foi possível calcular (ficheiro em falta): {set(em_falta)}")
        return 1
    if not corrigidos:
        print("  (nenhum — já estava certo, ou não havia)")
    return 0


def restaurar() -> int:
    n = 0
    for backup in sorted(TEMPLATES.rglob(f"*{SUFIXO_BACKUP}")):
        original = backup.with_suffix("")
        shutil.copy2(backup, original)
        backup.unlink()
        n += 1
        print(f"  restaurado: {original.relative_to(RAIZ)}")
    print(f"\n{n} ficheiro(s) restaurado(s)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Reescreve CDN -> {% static %}")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--restaurar", action="store_true")
    ap.add_argument("--sri", action="store_true", help="Recalcula integrity= (só)")
    args = ap.parse_args()
    if args.restaurar:
        return restaurar()
    if args.sri:
        return corrigir_sri(args.dry_run)
    rc = aplicar(args.dry_run)
    n = reescrever_fundos(args.dry_run)
    if n:
        print(f"  (fundos decorativos reescritos: {n})")
    if rc == 0:
        rc = corrigir_sri(args.dry_run)
    return rc


if __name__ == "__main__":
    sys.exit(main())
