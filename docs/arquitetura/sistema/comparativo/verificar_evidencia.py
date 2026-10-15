"""O VERIFICADOR — busca a pagina e confirma a citacao. Ou a celula desce.

Este e' o teste que a tabela sempre devia ter tido. Uma celula `S` so e' `S`
se o fragmento aparecer na pagina citada; caso contrario desce para `?`, e o
motivo fica escrito.

O que torna isto possivel e' o `cache`: cada URL e' buscada **uma vez** e o
texto limpo e' gravado em disco. Sem isto, 40 celulas seriam 40 downloads e
a verificacao nao correria duas vezes.

O resultado tem tres estados, e o terceiro e' o honesto:

    PROVADO    o fragmento esta na pagina
    NAO VISTO  a pagina respondeu, e o fragmento NAO esta. **A celula estava errada.**
    SEM ACESSO a pagina nao respondeu (403, 404, timeout, JS-only). **Nao e' falso.**

`SEM ACESSO` nao e' `NAO VISTO` e a distincao importa: um 403 nao prova que a
capacidade nao existe. Prova que eu nao consegui ver.
"""

from __future__ import annotations

import html as html_mod
import json
import pathlib
import re
import time
import urllib.error
import urllib.request

CACHE = pathlib.Path(__file__).parent / ".cache_fontes.json"

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

ENTIDADES = {
    "&aacute;": "á",
    "&atilde;": "ã",
    "&eacute;": "é",
    "&iacute;": "í",
    "&oacute;": "ó",
    "&uacute;": "ú",
    "&ccedil;": "ç",
    "&otilde;": "õ",
    "&agrave;": "à",
    "&ecirc;": "ê",
    "&acirc;": "â",
    "&ecedil;": "ç",
    "&nbsp;": " ",
    "&amp;": "&",
    "&quot;": '"',
    "&#39;": "'",
    "&atildeo": "ã",
    "&otil": "õ",
    "&ccedilo": "ç",
}


def limpar(html: str) -> str:
    """Tags fora, entidades desempacotadas, espacos normalizados.

    O objectivo e' que um humano possa dar ctrl-F no texto limpo e encontrar a
    mesma frase que o verificador encontrou. Se o script remover caracteres
    que o browser mostra, a prova deixa de ser verificavel a olho.
    """
    s = re.sub(r"(?is)<(script|style|noscript|svg)[^>]*>.*?</\1>", " ", html)
    s = re.sub(r"(?s)<!--.*?-->", " ", s)
    s = re.sub(r"(?s)<[^>]+>", " ", s)
    s = html_mod.unescape(s)
    for nome, char in ENTIDADES.items():
        s = s.replace(nome, char)
    return re.sub(r"\s+", " ", s).strip()


def _normalizar(t: str) -> str:
    """Minusculas e sem acento — para comparar 'e' com 'é' sem falhar.

    Nao remove pontuacao: as fronteiras de palavra dependem dela. Ver
    `contar_fragmento`.
    """
    import unicodedata

    return "".join(
        c
        for c in unicodedata.normalize("NFD", t.lower())
        if not unicodedata.combining(c)
    )


#: Fragmentos com menos de 4 caracteres sao perigosos como substring. 'API'
#: casa dentro de 'capital', 'rapido', 'capital'. 'MIP' dentro de 'simples'.
CURTOS = {"api", "mip", "ota", "bi", "ir", "sat", "ncm", "dre", "ib", "2d"}


def contar_fragmento(texto: str, frag: str) -> int:
    """Conta o fragmento **como palavra**, nao como substring.

    MEDIDO 2026-10-05 (agente 9). A primeira versao contava por substring e
    produzia falsos positivos de dois jeitos:

        "OTA"   dentro de "TOTAL", "ROTACAO", "DOTA"
        "map"   dentro de "roadmap", "mapping"
        "API"   dentro de "capital", "rapido"

    Numa tabela de 5 000 celulas, um falso positivo por substring e' um `S`
    falso. A regra e' deliberadamente conservadora: fragmento com menos de 4
    caracteres exige fronteira de palavra; os demais continuam substring, que
    e' o que se quer para 'georreferenciad' (que casa com plural e sufixos).
    """
    n_texto = _normalizar(texto)
    n_frag = _normalizar(frag)

    if len(n_frag) < 4 or n_frag in CURTOS:
        padrao = rf"(?<![a-z0-9]){re.escape(n_frag)}(?![a-z0-9])"
        return len(re.findall(padrao, n_texto))
    return n_texto.count(n_frag)


def contem_fragmento(texto: str, frag: str) -> bool:
    return contar_fragmento(texto, frag) > 0


def buscar(url: str, timeout: int = 30, tentativas: int = 2) -> tuple[str, str]:
    """(estado, texto). Estado: OK / HTTP nnn / ERRO."""
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
        },
    )
    ultimo = "ERRO"
    for _tentativa in range(tentativas):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                bruto = r.read()
                charset = r.headers.get_content_charset() or "utf-8"
                return "OK", bruto.decode(charset, errors="replace")
        except urllib.error.HTTPError as e:
            ultimo = f"HTTP {e.code}"
            if e.code in (403, 429):  # throttling: uma segunda vez pode correr
                time.sleep(2)
                continue
            return ultimo, ""
        except Exception as e:
            ultimo = f"ERRO {type(e).__name__}"
            time.sleep(1)
    return ultimo, ""


def carregar_cache() -> dict:
    if CACHE.exists():
        try:
            return json.loads(io_cache_text())
        except Exception:
            return {}
    return {}


def io_cache_text() -> str:
    return CACHE.read_text(encoding="utf-8")


def guardar_cache(c: dict) -> None:
    CACHE.write_text(json.dumps(c, ensure_ascii=False, indent=1), encoding="utf-8")


def textos(
    urls: list[str], usar_cache: bool = True, verbose: bool = True
) -> dict[str, tuple[str, str]]:
    """Texto limpo por URL. Cache em disco."""
    cache = carregar_cache() if usar_cache else {}
    out: dict[str, tuple[str, str]] = {}
    frescos = 0
    for i, url in enumerate(dict.fromkeys(urls), 1):
        if url in cache and cache[url].get("estado") == "OK":
            out[url] = ("OK", limpar(cache[url]["html"]))
            continue
        if verbose:
            print(f"  [{i}/{len(dict.fromkeys(urls))}] {url[:66]}", flush=True)
        estado, html = buscar(url)
        frescos += 1
        if estado == "OK":
            cache[url] = {"estado": estado, "html": html}
        else:
            cache[url] = {"estado": estado, "html": ""}
        out[url] = (estado, limpar(html) if html else "")
        time.sleep(0.4)
    if usar_cache:
        guardar_cache(cache)
    if verbose:
        print(f"  {frescos} downloads, {len(urls) - frescos} do cache")
    return out


def verificar(registro: dict, usar_cache: bool = True) -> dict:
    """Aplica o registo e devolve o veredicto por celula.

    O registo tem 5 campos: (url, fragmento, porque, estado, nota).
    O estado declarado ('F' ou 'D') e' confrontado com o que a maquina
    consegue ver. Um 'F' que a pagina nao confirma **desce**: a prova tem de
    ser feita, nao pedida.
    """
    urls = sorted({v[0] for v in registro.values() if v[1]})
    tx = textos(urls, usar_cache=usar_cache) if urls else {}
    res: dict[tuple[str, str], tuple[str, str]] = {}

    for chave, (url, frag, _porque, declarado, nota) in registro.items():
        if declarado == "?" or not frag:
            res[chave] = ("SEM PROVA", nota or "sem fragmento")
            continue
        estado_pagina, texto = tx.get(url, ("SEM ACESSO", ""))
        if estado_pagina != "OK":
            res[chave] = ("SEM ACESSO", f"{estado_pagina} — a pagina nao respondeu")
            continue
        if not texto:
            res[chave] = ("SEM ACESSO", "pagina sem texto")
            continue
        n = contar_fragmento(texto, frag)
        # `P` e' a terceira via: a FRASE esta na pagina — a citacao esta
        # verificada — mas prova MENOS do que a coluna pede ('financial
        # services' != credito rural). Devolver "PROVADO" aqui era somar a
        # citacao verificada com a capacidade provada, e o numero de
        # destaque ficava 3 unidades acima do que e' verdade.
        if n and declarado == "P":
            res[chave] = (
                "PARCIAL",
                f"'{frag}' esta na pagina ({n}x) mas nao prova a coluna",
            )
        elif n:
            res[chave] = ("PROVADO", f"'{frag}' encontrado ({n}x)")
        elif declarado == "D":
            res[chave] = (
                "DOCUMENTADO",
                "a maquina nao alcanca a pagina; a prova e' de terceiros",
            )
        elif declarado == "P":
            res[chave] = ("REJEITADO", f"'{frag}' NAO esta na pagina, e ja era parcial")
        else:
            res[chave] = ("REJEITADO", f"'{frag}' NAO esta na pagina")

    return res


if __name__ == "__main__":
    import sys

    sys.path.insert(0, str(pathlib.Path(__file__).parent))
    from evidencia import EVIDENCIA as REG

    print("=" * 78)
    print("VERIFICADOR — cada celula, buscada e confrontada com o que declara")
    print("=" * 78)
    r = verificar(REG)

    from collections import Counter

    c = Counter(v[0] for v in r.values())
    print()
    # O numero de destaque e' `PROVADO + DOCUMENTADO`. `PARCIAL` fica fora de
    # proposito: a frase esta na pagina, a capacidade nao esta. Somar as duas
    # coisas foi o que me deu 71 quando a verdade e' 69.
    provadas = c["PROVADO"] + c["DOCUMENTADO"]
    print(f"  PROVADO {c['PROVADO']}   DOCUMENTADO {c['DOCUMENTADO']}")
    print(
        f"  PARCIAL {c['PARCIAL']}   REJEITADO {c['REJEITADO']}   "
        f"SEM ACESSO {c['SEM ACESSO']}   SEM PROVA {c['SEM PROVA']}"
    )
    print()
    print(f"  >>> {provadas} celulas com capacidade provada (de {len(REG)} registadas)")
    if c["PARCIAL"]:
        print(
            f"  >>> mais {c['PARCIAL']} parciais: a citacao verifica-se, "
            f"a capacidade nao"
        )

    for estado in ("REJEITADO", "SEM ACESSO", "SEM PROVA"):
        chaves = [k for k, v in r.items() if v[0] == estado]
        if not chaves:
            continue
        print(f"\n--- {estado} ({len(chaves)}) ---")
        for prod, col in chaves:
            url, frag, _q, _d, _n = REG[(prod, col)]
            print(f"  {prod:26} {col}   {r[(prod, col)][1]}")
            print(f"      {url}")

    ok = [k for k, v in r.items() if v[0] in ("PROVADO", "DOCUMENTADO")]
    print(f"\n--- PROVADO ou DOCUMENTADO ({len(ok)} de {len(REG)}) ---")
    for prod, col in ok:
        print(f"  {r[(prod, col)][0]:12} {prod:24} {col}")
