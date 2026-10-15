"""Inventario exacto das dependencias de CDN, com o contexto de cada linha.

O objectivo nao e so contar: e' ver **o que** cada referencia carrega e
**como** esta escrita. Duas coisas mudam o trabalho a fazer:

1. `<link rel="preconnect" href="https://fonts.gstatic.com">` nao descarrega
   nada. E' uma dica ao browser para abrir a ligacao mais depressa. Se a
   origem nao for preciso, a linha pode ficar como esta — o `preconnect`
   para um dominio que nunca e' contactado e' inofensivo e nao e' uma
   dependencia. Confundir as duas coisas leva a "vendorizar" ficheiros que
   ninguem pediu.

2. Uma URL **sem versao** (`.../npm/chart.js`) e' uma dependencia que muda
   sozinha com o tempo. Nao e' so um problema de offline: e' a porta que
   o plano de vendorizacao fecha por acidente e por uma razao melhor.

Este script imprime a linha completa de cada referencia, para a decisao
ser tomada sobre o que esta la e nao sobre o que se supoe.
"""

from __future__ import annotations

import re
from pathlib import Path


def _raiz() -> Path:
    """Sobe até encontrar `manage.py` + `app/`.

    Contar níveis com `.parent.parent.parent` dá `ampliagro-app/` — e é um
    número que mente em silêncio quando a pasta ganha um nível. Já o paguei
    duas vezes nesta fase.
    """
    aqui = Path(__file__).resolve().parent
    for candidato in (aqui, *aqui.parents):
        if (candidato / "manage.py").is_file() and (candidato / "app").is_dir():
            return candidato
    raise SystemExit("raiz do repositório não encontrada")


RAIZ = _raiz()
APP = RAIZ / "app"

CDN = re.compile(
    r"https?://"
    r"(?:unpkg\.com|cdn\.jsdelivr\.net|cdnjs\.cloudflare\.com|"
    r"fonts\.googleapis\.com|fonts\.gstatic\.com|esm\.run|"
    r"[a-z0-9.-]*huggingface\.co|"
    r"api\.open-meteo\.com|servicodados\.ibge\.gov\.br|"
    r"nominatim\.openstreetmap\.org|agrodocai\.com\.br)",
    re.I,
)

linhas: list[tuple[str, int, str, str]] = []

for pasta, sufixo in ((APP / "templates", ".html"), (APP / "static", ".js")):
    for ficheiro in sorted(pasta.rglob(f"*{sufixo}")):
        try:
            texto = ficheiro.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for n, linha in enumerate(texto.splitlines(), 1):
            for m in CDN.finditer(linha):
                linhas.append(
                    (
                        str(ficheiro.relative_to(RAIZ)).replace("\\", "/"),
                        n,
                        m.group(0),
                        linha.strip(),
                    )
                )

print(f"REFERENCIAS DE CDN: {len(linhas)}\n")
print("=" * 100)

# --- agrupar por URL, para ver versões diferentes do mesmo pacote ---
por_url: dict[str, list[tuple[str, int, str]]] = {}
for ficheiro, n, url, ctx in linhas:
    por_url.setdefault(url, []).append((ficheiro, n, ctx))

print("\n### POR URL (versoes diferentes do mesmo pacote saltam aos olhos)\n")
for url, usos in sorted(por_url.items(), key=lambda kv: -len(kv[1])):
    ficheiros = sorted({u[0] for u in usos})
    marca = (
        "SEM VERSAO"
        if re.search(r"/npm/[^/@]+$", url)
        or url.rstrip("/").split("/")[-1].count(".") < 1
        else ""
    )
    print(f"[{len(usos)}x] {url}")
    if marca:
        print(f"      ^^ {marca} — esta URL muda de conteudo com o tempo")
    print(f"      em: {', '.join(ficheiros)}")
    print()

print("\n" + "=" * 100)
print("### LINHAS INTEIRAS (para ver preconnect vs carga real)\n")
for ficheiro, n, url, ctx in linhas:
    if len(ctx) > 150:
        ctx = ctx[:150] + "..."
    print(f"{ficheiro}:{n}")
    print(f"    {ctx}")
    print()
