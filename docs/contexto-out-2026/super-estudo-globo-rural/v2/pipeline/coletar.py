#!/usr/bin/env python3
"""
COLETOR V2 — Super Estudo Globo Rural
=====================================
Coleta o acervo REAL e o congela. Sem fallback sintetico. Sem preenchimento.

Fontes (ambas verificadas como acessiveis em 2026-10-03):
  A) globorural.globo.com  -> artigos editoriais completos (fonte de PROFUNDIDADE)
  B) globoplay.globo.com/v/<id> -> metadados oficiais de episodio/trecho
                                  (fonte de ESPINEIRA: titulo, data, duracao, resumo)

Regras inviolaveis desta v2:
  1. Falha de HTTP ou texto curto => REGISTRA O FALHO e nao inventa nada.
  2. Todo texto guardado tem SHA256 do HTML bruto, para auditoria.
  3. Todo item do inventario guarda a URL de origem. Sem URL, nao entra.
  4. O script NUNCA escreve prosa. So coleta e grava. A prosa vem depois,
     em arquivo por episodio, com citacao obrigatoria.

Uso:
  python coletar.py --fase both --max-artigos 400 --max-trechos 400
  python coletar.py --fase artigos --max-artigos 50       # teste rapido
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent
BRUTO = BASE / "bruto"  # HTML bruto, para auditoria
INV_PATH = BASE / "inventario.json"

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0 Safari/537.36 Ampliagro-V2/2.0"
)
# Pausa educada. Este site e comercial; nao vamos martelar.
PAUSA = 1.2
TIMEOUT = 30

# ---------------------------------------------------------------- utilidades


def agora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256(txt: str) -> str:
    return hashlib.sha256(txt.encode("utf-8", "replace")).hexdigest()


def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def buscar(url: str) -> tuple[str | None, str]:
    """Baixa a URL. Devolve (html, erro). Nunca levanta, nunca substitui."""
    req = urllib.request.Request(
        url, headers={"User-Agent": UA, "Accept-Language": "pt-BR,pt;q=0.9"}
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            if r.status != 200:
                return None, f"HTTP {r.status}"
            raw = r.read()
            for enc in ("utf-8", "latin-1"):
                try:
                    return raw.decode(enc), None
                except UnicodeDecodeError:
                    continue
            return raw.decode("utf-8", "replace"), None
    except urllib.error.HTTPError as e:
        return None, f"HTTP {e.code}"
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"


def limpar(html: str) -> str:
    """Remove script/style/nav e colapsa espaco. Conserva o texto editorial."""
    html = re.sub(
        r"(?is)<(script|style|noscript|svg|header|footer|nav|form)[^>]*>.*?</\1>",
        " ",
        html,
    )
    return re.sub(r"(?s)<[^>]+>", " ", html)


# O corpo do artigo no globorural.globo.com fica em containers especificos.
# Sem isolar isso, entra a pagina inteira: nav, anuncios, noticias relacionadas
# -- e o "texto" vira ~146.000 caracteres de ruido. Foi assim que a v1 poluiu.
# O corpo do artigo. ANCORA PRINCIPAL = <main>, que aparece exatamente 1 vez.
#
# POR QUE NAO USAR O NOME DA CLASSE: "mc-article-body" aparece 17 vezes na
# pagina (o repete em cada caixa de relacionada). Um regex nao-greedy que corta
# no primeiro </div></div> capturava um fragmento vazio, e 61 paginas que TEMIAM
# conteudo real foram registradas como "zero paragrafo aproveitavel".
# 61 conteudos perdidos por um regex guloso. Por isso: ancora unica, <main>.
_ANCORAS = [
    ("main", re.compile(r"(?is)<main\b[^>]*>(.*?)</main>")),
    ("article", re.compile(r"(?is)<article\b[^>]*>(.*?)</article>")),
    (
        "body-class",
        re.compile(
            r'(?is)<div[^>]+class="[^"]*mrf-article-body[^"]*"[^>]*>(.*?)</footer'
        ),
    ),
    ("body-sem", re.compile(r"(?is)<body\b[^>]*>(.*?)</body>")),
]

MAX_CORPO = 60_000  # acima disso ainda ha poluicao: e falha, nao texto


def isolar_corpo(html: str) -> str:
    """Devolve so o HTML do miolo. Maior ancora primeiro; "" se nenhuma servir."""
    for _nome, rx in _ANCORAS:
        m = rx.search(html)
        if not m:
            continue
        corpo = m.group(1)
        if len(corpo) > 300:
            return corpo
    return ""


# O primeiro <p> do miolo costuma ser o MENU inteiro colado
# ("Carregando... Acesse sua conta ... Home Ultimas noticias"), 3.000+ chars.
# E um paragrafo, mas nao e texto de artigo.
_NAV_COMECO = re.compile(
    r"(?i)(carregando\.\.\.|acesse sua conta|cadastre-se|ultimas not[ií]cias|"
    r"previs[aã]o do tempo|menu|buscar|entrar|newsletter|assine o|"
    r"compartilh|facebook|instagram|whatsapp|veja tamb[eé]m)"
)

# Corta o miolo no inicio da lista de relacionadas, para nao embeutar o link de
# outra materia como se fosse o corpo desta.
# ATENCAO: nao usar "compartilh" aqui. A barra de COMPARTILHAR aparece cedo no
# artigo e o corte derrubava o corpo inteiro -> "zero paragrafo aproveitavel".
# So marcador de bloco de relacionadas, e nunca antes de 3.000 chars.
_TERMINADOR = re.compile(
    r"(?is)(not[ií]cias relacionadas|outras not[ií]cias|leia tamb[eé]m o que|"
    r"mais lidas d(a|o)|continue lendo a mat[eé]ria)"
)

_RUIDO = re.compile(
    r"(?i)^(leia (mais|tambem)|saiba mais|veja (mais|tambem)|fonte:|foto:|"
    r"cr[eé]dito|entregue por|publicado por|continue lendo)"
)


def _limpa_paragrafo(b: str) -> str:
    t = re.sub(r"(?s)<[^>]+>", " ", b)
    t = re.sub(r"&nbsp;?", " ", t)
    t = re.sub(r"&[a-z]+;", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def extrair_texto(html: str) -> tuple[str, str]:
    """
    Extrai SO o texto do artigo. Devolve (texto, motivo_de_falha_se_houver).
    """
    corpo = isolar_corpo(html)
    if not corpo:
        return "", "sem container de corpo"
    corpo = re.sub(
        r"(?is)<(script|style|noscript|svg|form|iframe)[^>]*>.*?</\1>", " ", corpo
    )

    # recorta no inicio de "noticias relacionadas", se vier cedo
    tm = _TERMINADOR.search(corpo, 3000)
    if tm and tm.start() > 3000:
        corpo = corpo[: tm.start()]

    blocos = re.findall(r"(?is)<p[^>]*>(.*?)</p>", corpo)

    # o menu costuma vir em 1 paragrafo gigante logo no comeco: pula ate 3
    skip_nav = 0
    for b in blocos[:3]:
        t = _limpa_paragrafo(b)
        if len(t) > 400 and len(_NAV_COMECO.findall(t)) >= 3:
            skip_nav += 1
        else:
            break

    partes: list[str] = []
    for i, b in enumerate(blocos):
        if i < skip_nav:
            continue
        t = _limpa_paragrafo(b)
        if len(t) <= 60:
            continue
        if _RUIDO.match(t):
            continue
        partes.append(t)

    texto = "\n\n".join(partes)
    if not texto:
        return "", "zero paragrafo aproveitavel"
    if len(texto) > MAX_CORPO:
        return "", f"texto suspectsamente longo ({len(texto)}c) - poluicao"
    return texto, ""


# ------------------------------------------------------------------ relevancia

# Sem isto, o rastreio do Globoplay entra em futebol, "Enem" e escorpiao.
AGRO = re.compile(
    r"(?i)\b(agr[ií]c|agropecu|agr[uó]neg|produtor|rural|fazenda|safra|plantio|"
    r"colheita|lavoura|talh[aã]o|gado|boi\b|leite\b|vac[aá]|su[ií]no|aves|"
    r"avicult|frango|ovo\b|cafe|algod|soja|milho|trigo|arroz|cana\b|feij[aã]o|"
    r"mandioca|cacau|laranja|ma[cç][aã]|banana|uva\b|cebola|mam[aã]o|urucum|"
    r"pequi|erva-mate|aquicult|peixe|til[aá]pia|camar[aã]o|ostra|jacar[eé]|"
    r"biodigest|biogas|compost|fertiliz|adub|calcar|herbicid|pesticid|defensiv|"
    r"irrigac|semente|variedade|h[ií]brid|manejo|sanit[aá]rio|veterin|"
    r"cinco|quilo|boi gordo|leiteira|frigor|abate|exporta[cç]|cota[cç][aã]o|"
    r"pecuar|suinocult|av[ií]cult|cunicult|apicult|orgânico|biodin[âa]m|"
    r"regenerativ|agroflorest|sustent)"
)

# Marcas de assunto nao agricola, mesmo dentro do portal da Globo.
NAO_AGRO = re.compile(
    r"(?i)\b(fluminense|vasco|futebol|champions|enem|concursos? p[uú]blico|"
    r"escorpi|viuvinha|pol[ií]cia|assassinato|sequestr|\bstf\b|wesley|"
    r"carnaval|torcida|goleiro|tranfer|transfer[eê]ncia)"
)


def agro_relevante(titulo: str, texto: str) -> tuple[bool, str]:
    """Heuristica conservadora: em duvida, entra."""
    t = f"{titulo}\n{texto[:4000]}"
    a = len(AGRO.findall(t))
    n = len(NAO_AGRO.findall(t))
    if n >= 3 and a < 5:
        return False, f"nao-agro ({n} marcas sports/generico vs {a} agro)"
    if a == 0:
        return False, "zero termo agro"
    return True, f"agro={a} naoagro={n}"


def titulo_de(html: str, url: str) -> str:
    m = re.search(r"(?is)<h1[^>]*>(.*?)</h1>", html)
    if m:
        t = re.sub(r"(?s)<[^>]+>", "", m.group(1))
        t = re.sub(r"\s+", " ", t).strip()
        if t:
            return t
    m = re.search(r'(?is)<meta[^>]+property="og:title"[^>]+content="([^"]+)"', html)
    if m:
        return m.group(1).strip()
    return (
        urllib.parse.urlparse(url)
        .path.rsplit("/", 1)[-1]
        .replace("-", " ")
        .replace(".ghtml", "")
    )


def data_de(html: str) -> str:
    for pat in (
        r'(?is)<meta[^>]+property="article:published_time"[^>]+content="([^"]+)"',
        r'(?is)"datePublished"\s*:\s*"([^"]+)"',
        r'(?is)<time[^>]+datetime="([^"]+)"',
    ):
        m = re.search(pat, html)
        if m:
            return m.group(1).strip()
    return ""


# ------------------------------------------------------- fonte A: globorural

RE_CATEG = re.compile(
    r'href="(https://globorural\.globo\.com/(?:[a-z0-9\-]+/)+noticia/\d{4}/\d{2}/[^"]+\.ghtml)"'
)


def fase_artigos(max_artigos: int) -> tuple[list[dict], list[dict], list[dict]]:
    """
    Coleta artigos editoriais do globorural.globo.com.
    Devolve (itens, falhas, descartados). Descartado != falha: foi lido e
    rejeitado por nao ser agro. Registrar os dois e o que impede a v1.
    """
    BRUTO.mkdir(parents=True, exist_ok=True)
    vistos: set[str] = set()
    itens: list[dict] = []
    falhas: list[dict] = []
    descartados: list[dict] = []

    sementes = [
        "https://globorural.globo.com/",
    ]
    # termos de campo, para cobrir o espectro do programa
    TERMOS = [
        "frango",
        "gado",
        "cafe",
        "soja",
        "milho",
        "laranja",
        "suino",
        "leite",
        "tilapia",
        "aquicultura",
        "algodao",
        "pecuaria",
        "aviario",
        "maca",
        "mandioca",
        "cacau",
        "cannabis",
        "banana",
        "requeijao",
        "trigo",
        "sorgo",
        "biogas",
        "solar",
        "irrigacao",
        "vinhos",
        "oliva",
        "cafe especial",
        "vaca leiteira",
        "frango corte",
        "postura",
        "suinocultura",
        "aquicultura orgânica",
        "agrofloresta",
    ]
    for termo in TERMOS:
        sementes.append(
            "https://globorural.globo.com/busca/?q=" + urllib.parse.quote(termo)
        )

    fila = list(sementes)
    log(f"artigos: {len(sementes)} sementes, alvo {max_artigos}")

    while fila and len(itens) < max_artigos:
        url = fila.pop(0)
        html, err = buscar(url)
        if err or not html:
            falhas.append({"url": url, "erro": err or "vazio"})
            continue

        # sitemap/paginas: achar links de artigo
        achados = set(RE_CATEG.findall(html))
        achados |= set(
            re.findall(r'href="(/[a-z0-9\-/]+noticia/\d{4}/\d{2}/[^"]+\.ghtml)"', html)
        )
        achados = {
            a if a.startswith("http") else "https://globorural.globo.com" + a
            for a in achados
        }

        novos = [a for a in achados if a not in vistos]
        for a in achados:
            vistos.add(a)
        fila.extend(novos[:60])

        # Tambem tentar usar a propria pagina como artigo, se for um
        if re.search(r"/noticia/\d{4}/\d{2}/", url) and url not in vistos:
            vistos.add(url)

        # Ja coletadosEnough nesta passagem: so acumular seeds e seguir
        for art in list(novos)[: (max_artigos - len(itens))]:
            if len(itens) >= max_artigos:
                break
            ah, aerr = buscar(art)
            if aerr or not ah:
                falhas.append({"url": art, "erro": aerr or "vazio"})
                continue
            txt, why = extrair_texto(ah)
            if why or len(txt) < 400:
                falhas.append({"url": art, "erro": why or f"texto curto ({len(txt)}c)"})
                continue
            tit = titulo_de(ah, art)
            ok, motivo = agro_relevante(tit, txt)
            if not ok:
                descartados.append({"url": art, "titulo": tit, "motivo": motivo})
                continue
            slug = re.sub(r"[^a-zA-Z0-9]+", "-", urllib.parse.urlparse(art).path)[-90:]
            BRUTO.joinpath(f"art_{slug}.html").write_text(ah, encoding="utf-8")
            BRUTO.joinpath(f"art_{slug}.txt").write_text(txt, encoding="utf-8")
            itens.append(
                {
                    "id": f"ART-{len(itens) + 1:05d}",
                    "fonte": "globorural.globo.com",
                    "tipo": "artigo",
                    "url": art,
                    "titulo": tit,
                    "data": data_de(ah),
                    "duracao": None,
                    "resumo_oficial": "",
                    "chars": len(txt),
                    "paragrafos": txt.count("\n\n") + 1,
                    "relevancia": motivo,
                    "sha256_html": sha256(ah),
                    "sha256_texto": sha256(txt),
                    "coletado_em": agora(),
                    "status": "real",
                }
            )
            log(
                f"  ART {len(itens)}/{max_artigos} | {len(txt)}c | "
                f"{itens[-1]['titulo'][:58]}"
            )
            time.sleep(PAUSA)

    log(
        f"artigos: {len(itens)} coletados, {len(falhas)} falhas, "
        f"{len(descartados)} descartados por nao-agro"
    )
    return itens, falhas, descartados


# ------------------------------------------------------ fonte B: globoplay

RE_VID = re.compile(r"/v/(\d{4,12})")


def extrair_jsonld(html: str) -> list[dict]:
    out = []
    for b in re.findall(
        r"(?is)<script[^>]*application/ld\+json[^>]*>(.*?)</script>", html
    ):
        try:
            d = json.loads(b.strip())
        except Exception:
            continue
        for it in d if isinstance(d, list) else [d]:
            if isinstance(it, dict) and ("duration" in it or "name" in it):
                out.append(it)
    return out


def duracao_iso(iso: str | None) -> str:
    if not iso:
        return ""
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:([\d.]+)S)?", iso)
    if not m:
        return iso
    h, mi, s = m.groups()
    return f"{int(h or 0):02d}:{int(mi or 0):02d}:{int(float(s or 0)):02d}"


def fase_trechos(max_trechos: int) -> tuple[list[dict], list[dict]]:
    """
    Percorre a malha de trechos do Globo Rural no Globoplay.
    Cada /v/<id> devolve JSON-LD oficial: nome, descricao, data, duracao.
    Sem login: so metadata. (O video exige assinatura; o texto NAO e inventado.)
    """
    BRUTO.mkdir(parents=True, exist_ok=True)
    itens: list[dict] = []
    falhas: list[dict] = []
    descartados: list[dict] = []
    vistos: set[str] = set()

    raizes = ["https://globoplay.globo.com/globo-rural/t/xyFHtZytj2/cenas/"]
    fila = list(raizes)
    ids_coletados: set[str] = set()

    log(f"trechos: arraste a partir de {len(raizes)} raiz, alvo {max_trechos}")

    while fila and len(itens) < max_trechos:
        url = fila.pop(0)
        if url in vistos:
            continue
        vistos.add(url)
        html, err = buscar(url)
        if err or not html:
            falhas.append({"url": url, "erro": err or "vazio"})
            continue

        # enfilebrar vizinhos para ramificar
        for vid in RE_VID.findall(html):
            link = f"https://globoplay.globo.com/v/{vid}/"
            if link not in vistos and len(fila) < 900:
                fila.append(link)

        # se for a propria pagina de video, registrar
        if re.search(r"/v/\d+/?$", url):
            blocos = extrair_jsonld(html)
            vo = next(
                (b for b in blocos if b.get("type") == "VideoObject" and b.get("name")),
                None,
            )
            if not vo:
                falhas.append({"url": url, "erro": "sem JSON-LD VideoObject"})
                continue
            vid = re.search(r"/v/(\d+)", url).group(1)
            tit = (vo.get("name") or "").strip()
            desc = (vo.get("description") or "").strip()
            # A malha do Globoplay vaza para o catalogo inteiro da Globo:
            # futebol, Enem, escorpiao. Sem este filtro, entra tudo.
            ok, motivo = agro_relevante(tit, desc)
            if not ok:
                descartados.append({"url": url, "titulo": tit, "motivo": motivo})
                continue
            ids_coletados.add(vid)
            BRUTO.joinpath(f"vid_{vid}.html").write_text(html, encoding="utf-8")
            BRUTO.joinpath(f"vid_{vid}.txt").write_text(
                f"{tit}\n\n{desc}", encoding="utf-8"
            )
            itens.append(
                {
                    "id": f"TRE-{len(itens) + 1:05d}",
                    "fonte": "globoplay.globo.com",
                    "tipo": "trecho",
                    "globoplay_id": vid,
                    "url": vo.get("url") or url,
                    "titulo": tit,
                    "data": (vo.get("datePublished") or "").strip(),
                    "duracao": duracao_iso(vo.get("duration")),
                    "resumo_oficial": desc,
                    "chars": len(tit) + len(desc),
                    "relevancia": motivo,
                    "sha256_html": sha256(html),
                    "sha256_texto": sha256(f"{tit}\n\n{desc}"),
                    "coletado_em": agora(),
                    "status": "real",
                }
            )
            log(
                f"  TRE {len(itens)}/{max_trechos} | {itens[-1]['data'][:10]} "
                f"| {itens[-1]['titulo'][:58]}"
            )
            time.sleep(PAUSA)

    log(
        f"trechos: {len(itens)} coletados, {len(falhas)} falhas, "
        f"{len(descartados)} descartados por nao-agro"
    )
    return itens, falhas, descartados


# ------------------------------------------------------------------- main


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fase", default="both", choices=["artigos", "trechos", "both"])
    ap.add_argument("--max-artigos", type=int, default=400)
    ap.add_argument("--max-trechos", type=int, default=400)
    args = ap.parse_args()

    log("=" * 66)
    log("COLETOR V2 — coleta real, sem preenchimento. Falha e registrada.")
    log("=" * 66)

    itens: list[dict] = []
    falhas: list[dict] = []
    descartados: list[dict] = []

    if args.fase in ("artigos", "both"):
        a, fa, da = fase_artigos(args.max_artigos)
        itens += a
        falhas += fa
        descartados += da
    if args.fase in ("trechos", "both"):
        t, ft, dt = fase_trechos(args.max_trechos)
        itens += t
        falhas += ft
        descartados += dt

    payload = {
        "gerado_em": agora(),
        "versao": "2.1",
        "regra": "Todo item tem URL real e SHA256 do HTML bruto. "
        "Nenhum item foi gerado, inventado ou preenchido.",
        "limite_conhecido": "Globoplay exige assinatura para o VIDEO. "
        "Coletamos apenas metadata oficial publica "
        "(JSON-LD). Nenhuma transcricao foi inventada.",
        "total_itens": len(itens),
        "por_tipo": {
            "artigo": sum(1 for i in itens if i["tipo"] == "artigo"),
            "trecho": sum(1 for i in itens if i["tipo"] == "trecho"),
        },
        "total_falhas": len(falhas),
        "total_descartados_nao_agro": len(descartados),
        "itens": itens,
        "falhas": falhas,
        "descartados": descartados,
    }
    INV_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    log(f"INVENTARIO gravado: {INV_PATH}")
    log(f"  itens={len(itens)} falhas={len(falhas)} descartados={len(descartados)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
