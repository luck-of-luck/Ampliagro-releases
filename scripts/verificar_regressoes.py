"""Verifica o CODIGO em HEAD, nao os comentarios.

A primeira versao acusava falsos positivos: `cotacoes.py` e `ndvi.py` trazem
em PROPRIO docstring o `random.uniform` e o `max(0.4, min(0.88, ...))` para
explicar o defeito que corrigiram. Ler o ficheiro inteiro e perguntar "ainda
tem isto?" da "sim" por causa da explicacao. Depois de corrigir isso, tres
linhas ficaram com a condicao invertida e o verificador voltou a mentir ao
contrario — que e' pior: acusa um defeito que nao existe.

Daqui em diante cada linha escreve a CONDICAO ao lado do resultado, para o
resultado poder ser conferido sem correr isto.
"""

import ast
import pathlib
import re
import subprocess

FICHEIROS = [
    "app/services/cotacoes.py",
    "app/services/ndvi.py",
    "app/api/views/utils.py",
    # iot.py tinha uma COPIA do gerador de metricas inventadas. Corrigir
    # um irmao e deixar o outro e' como o defeito volta.
    "app/api/views/iot.py",
    "app/services/top_globais.py",
    "app/middleware.py",
    "app/api/views/agronomia.py",
    "app/api/views/cultures.py",
    # bloco 1 da IA-A
    "app/services/recomendacao_solo.py",
    "app/services/erp_externo.py",
]


def em_head(caminho):
    """Lê o índice (stage), não o HEAD.

    Ler o HEAD obriga a commitar antes de verificar, e aí o verificador
    passa a responder a uma pergunta que ninguém fez: "o que é que já foi
    publicado?". O que interessa é "o que está no meu commit?" — e isso
    é o stage.

    Quando acabei de corrigir cinco defeitos, o verificador reportou
    sete DEFEITO, porque nenhum deles estava em HEAD ainda. A regra
    estava a dar a resposta errada, e o sinal era de que o trabalho não
    estava feito.
    """
    r = subprocess.run(
        ["git", "show", ":" + caminho],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if r.returncode != 0:
        # não está no índice: o HEAD é a melhor aproximação
        r = subprocess.run(
            ["git", "show", "HEAD:" + caminho],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    return r.stdout


def so_codigo(fonte):
    arvore = ast.parse(fonte)
    for no in ast.walk(arvore):
        corpo = getattr(no, "body", None)
        if not isinstance(corpo, list) or not corpo:
            continue
        primeiro = corpo[0]
        if (
            isinstance(primeiro, ast.Expr)
            and isinstance(primeiro.value, ast.Constant)
            and isinstance(primeiro.value.value, str)
        ):
            corpo.pop(0)
    return ast.unparse(arvore)


cod = {f: so_codigo(em_head(f)) for f in FICHEIROS}


# `perigo` = o defeito esta no codigo. `ok` = a correccao esta no codigo.
_verificacoes = [0, 0]  # [total, defeitos]


def show(perigo, nome, cond):
    estado = "DEFEITO" if perigo else "ok"
    _verificacoes[0] += 1
    if perigo:
        _verificacoes[1] += 1
    print(f"    {nome:<38} {estado:<7}   se: {cond}")


c = cod["app/services/cotacoes.py"]
print("  COTACOES")
for frag, nome in (
    ("import random", "importa random"),
    ("_fetch_b3_mock", "chama _fetch_b3_mock"),
    ("uniform", "sorteia com uniform"),
):
    show(frag in c, nome, repr(frag) + " in codigo")
show(
    "tem_preco" not in c,
    "fonte calculada, nao comparada",
    "'tem_preco' in codigo",
)

n = cod["app/services/ndvi.py"]
print("  NDVI")
for frag, nome in (
    ("import hashlib", "importa hashlib"),
    ("0.88", "tecto inventado 0.88"),
):
    show(frag in n, nome, repr(frag) + " in codigo")
a = cod["app/api/views/agronomia.py"]
show("Sem NDVI" not in a, "heatmap sem caminho sem NDVI", "'Sem NDVI' in codigo")

m = cod["app/middleware.py"]
print("  TENANCY")
# `ast.unparse` normaliza aspas duplas para simples. Procurar por
# '"talhao_id"' dava "NAO" numa correccao que estava la. Procura-se o nome
# sem aspas, que e' o que interessa.
for p in ("propriedade_id", "fazenda_id", "talhao_id", "device_id"):
    frag = "'" + p + "'"
    show(frag not in m, p + " verificado", frag + " in codigo")
show(
    bool(re.search(r"except Exception:\s*\n\s*pass", m)),
    "recusa engolida por except pass",
    "re.search(..., 'except Exception: pass')",
)

u = cod["app/api/views/utils.py"]
print("  FALLBACK IBGE")
show("random.Random" in u, "sorteia historico", "'random.Random' in codigo")
show(
    bool(re.search(r"def _gen_fallback_metrics.*?return \[dict", u, re.S)),
    "_gen_fallback_metrics serve dados",
    "re.search('def _gen_fallback_metrics ... return [dict')",
)

# O gerador de metricas inventadas existia em DOIS ficheiros. Corrigiram-se
# o de utils.py e ficou o de iot.py — que ninguem importava, mas que fabricava
# igual. Um check que so olha para um sitio nao apanha o irmao.
for _f in (
    "app/api/views/utils.py",
    "app/api/views/iot.py",
    "app/api/views/cultures.py",
    "app/api/views/user.py",
):
    _c = cod.get(_f, "")
    _nome = _f.split("/")[-1]
    show(
        "random.Random" in _c,
        f"{_nome} sorteia historico",
        f"'random.Random' in {_f}",
    )
    show(
        # so a funcao VIVA. `_gen_fallback_history_antigo` existe de
        # proposito em utils.py: `tests_fallback_sem_invencao.py` importa-a
        # para provar que ja nao serve dados. Apanhar essa era acusar a
        # prova do defeito.
        bool(re.search(r"def _gen_fallback_history\(", _c))
        and "return {}" not in _c.split("def _gen_fallback_history(")[-1][:400],
        f"{_nome} mantem gerador de historico",
        "def _gen_fallback_history( ... sem 'return {}' logo a seguir",
    )

cu = cod["app/api/views/cultures.py"]
show(
    "indisponivel" not in cu,
    "view responde indisponivel",
    "'\"indisponivel\"' in codigo",
)

t = cod["app/services/top_globais.py"]
print("  WIDGETS QUE MULTIPLICAVAM O HASH")
for frag, nome in (
    ('"dose": 180', "prescreve 180 kg"),
    ("credencial presente", "marca real por credencial"),
    ('"tempo_real": True', "balanca em tempo real"),
):
    show(frag in t, nome, repr(frag) + " in codigo")

# --- bloco 1 da IA-A (16:20) ---------------------------------------------
print("  IA-A bloco 1 — os que multiplicavam hash ou afirmavam sem medir")
for frag, nome in (
    ("culturas = [", "detecta cultura por indice de hash"),
    ("Sentinel-2 AI deterministico", "carimba Sentinel-2 sem imagem"),
    ('"acao": "Pulverizar"', "recomenda pulverizar"),
    ('"precisao_cm": 2.5', "precisao de aplicacao a mao"),
    ('"km_total": 0', "rota de ceifa com zeros"),
):
    show(frag in t, nome, repr(frag) + " in codigo")

s = cod["app/services/recomendacao_solo.py"]
show('"estado_ph": "Bom"' in s, "diz solo Bom sem pH", "estado_ph fixo 'Bom'")
show("300kg/ha de 04-14-08" in s, "recomenda 300 kg placeholder", "recomendacao fixa")

e = cod["app/services/erp_externo.py"]
show("cabecas=10721000" in e, "stub devolve cabecas de jornal", "default 10721000")
show("recorde=True" in e, "default afirma um recorde", "recorde=True")

u = cod["app/api/views/utils.py"]
for frag, nome in (
    ("or 25", "temperatura injectada pelo INMET"),
    ("or 60", "humidade injectada pelo INMET"),
    ('"Parcialmente nublado"', "descricao inventada na previsao"),
):
    show(frag in u, nome, repr(frag) + " in codigo")


# ---------------------------------------------------------------------------
# COBERTURA — porque "0 defeitos" sem este bloco nao quer dizer nada
# ---------------------------------------------------------------------------
# A tabela AGORA citava este script como "18 verificacoes, 0 defeitos" e
# usava isso como prova de que nada tinha voltado. Sao 30 verificacoes, e
# elas cobrem 9 ficheiros de 223.
#
# Estes checks sao um MUSEU: cada um existe porque alguem ja encontrou
# aquele defeito uma vez. Nenhum foi escrito para uma classe de defeito,
# porque nao ha procura por classe — ha uma lista de palavras. Um defeito
# novo nao e' detectado, porque nao ha nada que o procure.
#
# A razao de estar aqui, em vez de so mudar a AGORA: um check que mede
# zero e' indistinguivel de um check limpo. Se o script diz "0 defeitos"
# e nao diz "nestes 9 ficheiros, destes 223", quem o cita esta a citar
# uma medida sem denominador — que e' a forma exacta de um teste
# passar por estar a falhar calado.
#
# O que este bloco NAO faz: nao torna o verificador melhor. Cobre 4% dos
# ficheiros .py, zero ficheiros .js, e nenhum ficheiro alterado depois
# do dia em que foi escrito. Ele diz-o, para ninguem o citar sem o ler.


def _cobertura():
    try:
        todos = {
            str(p).replace("\\", "/")
            for p in pathlib.Path("app").rglob("*.py")
            if "tests" not in str(p) and "migrations" not in str(p)
        }
    except OSError:
        return
    js = list(pathlib.Path("app").rglob("*.js"))
    js_cob = 0

    print("")
    print("  COBERTURA  (leia antes de citar '0 defeitos')")
    n, d = _verificacoes
    print(f"    verificacoes corridas ............ {n} ({d} DEFEITO)")
    print(f"    ficheiros .py de app/ cobertos ... {len(FICHEIROS)} de {len(todos)}")
    print(f"    ficheiros .js cobertos ......... {js_cob} de {len(js)}")
    print("    tipo de prova .................. presenca de uma PALAVRA no")
    print("                                    codigo-fonte lido do indice")
    print("                                    do git. Nao executa nada.")
    print("    nao cobre ...................... nada escrito depois de")
    print("                                    2026-10-01. Os defeitos de")
    print("                                    hoje nao estao aqui.")
    print(
        f"    '0 defeitos' quer dizer: '0 defeitos NESTES {len(FICHEIROS)} FICHEIROS'."
    )


_cobertura()
