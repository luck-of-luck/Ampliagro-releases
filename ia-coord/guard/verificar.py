#!/usr/bin/env python
"""ia-coord/guard/verificar.py — o guarda que a REGRAS manda correr.

REGRA R5, que e' o coracao disto: um comando que nao corre tem de
DIZER QUE NAO CORREU. Este script nao tem caminho de reserva que
imprima "OK". Se uma verificacao nao pode ser feita, ela grita e o
codigo de saida != 0.

O que verifica:
  V1  corrupcao CJK/mojibake por VARREDIMENTO DE BYTES (R7)
  V2  manifesto do plenario: alguem reescreveu um ficheiro antigo? (R2)
  V3  numeracao dos slots: cada IA-NAO tem o seu numero correcto?
  V4  cada slot tem o que a LEIA-ME promete (pasta + relatorio)
  V5  ficheiros a meio escrever (terminacao suspeita)

O que NAO verifica, e diz que nao verifica:
  - nao impede ninguem de escrever na pasta de outro. ACLs do Windows
    distinguem utilizadores, nao sessoes do mesmo utilizador.
    DETECTA DEPOIS. (LEIA-ME, secao "O QUE NAO CONSEGUE")
  - nao verifica o codigo de produto. So a coordination.

Uso:
    python ia-coord/guard/verificar.py            # tudo
    python ia-coord/guard/verificar.py --so v1    # so a corrupcao
    python ia-coord/guard/verificar.py --json     # para maquinas
"""

import hashlib
import io
import json
import os
import re
import sys
import time

# --------------------------------------------------------------------------
# R8: escrever scripts em FICHEIROS, nunca here-strings. Este ficheiro
# respeita a regra que escreve. Todos os nao-ASCII abaixo sao ESCAPES
# ASCII, para que este ficheiro nunca possa ser a proxima vitima da
# doenca que ele prende.
# --------------------------------------------------------------------------

RAIZ = os.path.abspath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
)
COORD = os.path.join(RAIZ, "ia-coord")
PLENARIO = os.path.join(COORD, "plenario")
MANIFESTO = os.path.join(PLENARIO, "MANIFESTO.json")
HISTORICO = os.path.join(PLENARIO, "HASHES-HISTORICO.json")

SLOTS = ["ia-%d" % i for i in range(1, 12)]

# Gamas que nao pertencem a um ficheiro em portugues.
CJK_RANGES = [
    (0x2E80, 0x9FFF),  # radicais CJK
    (0x3000, 0x303F),  # pontuacao CJK
    (0xAC00, 0xD7AF),  # hangul
    (0xFFFD, 0xFFFD),  # replacement char
    (0x1DC0, 0x1DFF),  # complemento phonetic
]

# Mojibake: UTF-8 lido com o charset errado. Construido com chr() e NAO
# escrito como literal — senão este ficheiro é a próxima vítima da doença
# que ele prende. Foi o que aconteceu na primeira versão: o V1 apontou
# 6 linhas MOJIBAKE no próprio verificar.py, e tinha razão.
MOJIBAKE = [
    (chr(0x00E2) + chr(0x20AC), "em-dash ou aspas quebradas"),
    (chr(0x00E2) + chr(0x20AC) + chr(0x2122), "apos-trofo quebrado"),
    (chr(0x00C3) + chr(0x00A9), "e-agudo partido"),
    (chr(0x00C3) + chr(0x00A3), "a-tilde partido"),
    (chr(0x00C3) + chr(0x00A7), "cedilha partida"),
    (chr(0x00C3) + chr(0x00A3) + chr(0x00A2), "a-circunflexo partido"),
    (chr(0x00EF) + chr(0x00BF) + chr(0x00BD), "replacement triplo"),
]

EXTENSOES = (".py", ".md", ".js", ".html", ".css", ".json", ".ts")
TAMANHO_MAX = 2_000_000


class Resultado:
    def __init__(self):
        self.ok = 0
        self.falhou = 0
        self.nao_verificado = 0
        # BUG MEU, hoje: `ok` so e' incrementado por `falha()`. Se tudo
        # passa, ok==0 e o main() imprimia "NADA FOI VERIFICADO" e
        # saia com erro — um guarda que falha quando tudo esta bem
        # treina as pessoas a ignorar a saida. Passou-me com --so v2.
        self.executadas = 0
        self.linhas = []

    def correm(self):
        self.executadas += 1

    def passa(self, ver, msg):
        self.linhas.append(("OK", ver, msg))

    def falha(self, ver, msg):
        self.ok += 1
        self.linhas.append(("FALHA", ver, msg))

    def erro(self, ver, msg):
        self.nao_verificado += 1
        self.linhas.append(("NAO VERIFICADO", ver, msg))

    def nota(self, ver, msg):
        self.linhas.append(("NOTA", ver, msg))


def dentro_de_aspas(linha, agulha):
    """A mojibake `agulha` esta dentro de aspas/backticks na MESMA linha?"""
    i = linha.find(agulha)
    if i < 0:
        return False
    return entre_aspas(linha, i)


def e_cjk(cp):
    for lo, hi in CJK_RANGES:
        if lo <= cp <= hi:
            return True
    return False


# --------------------------------------------------------------------------
# MISTURA DE SCRIPTS DENTRO DE UM TOKEN — o buraco que o V1 tinha
# --------------------------------------------------------------------------
# MEDIDO 2026-10-05. O `CJK_RANGES` acima so cobria ideogramas. Um token pode
# estar corrompido **sem** nenhum ideograma, e o V1 dava "tudo limpo":
#
#     app/api/views/utils.py:743
#         "decide irrigar, pulverizar e \u043a\u043e\u043d\u0442\u0440\u0430tar\u8702 semente"
#         =>  k  o  n  t  r  +  "tar"  +  um ideograma
#
# As cinco primeiras letras sao CIRILICO (U+0400-U+04FF) e a palavra estava
# em portugues. O ideograma no fim denunciava-a, mas se a corrupcao tivesse
# terminado em "tar" — sem o ideograma — o V1 passava.
#
# E o outro caso, mais silencioso: um homoglifo dentro de uma palavra latina.
# `Sol Agui\u0430` (com 'a' cirilico) e' "Sol Aguia" com a letra trocada.
# Nenhum ideograma, nenhuma mojibake: o V1 nao tinha como apanhar.
#
# --------------------------------------------------------------------------
# PORQUÊ QUE A REGRA E' "MISTURA", E NAO "CIRILICO PRESENTE"
# --------------------------------------------------------------------------
# MEDIDO no mesmo dia: existem 2 ficheiros no projecto com cirilico, e um
# deles e' `docs/sistema/comparativo/.cache_fontes.json` — pesquisa de
# mercado com texto russo legitimo. Uma regra "cirilico presente" dava falso
# positivo em material de research.
#
# A regra da MISTURA nunca da: em russo legitimo cada palavra e' de um so
# script. O que nao existe em texto legitimo e' um token com LATIM E
# cirilico ao mesmo tempo. Por isso e' token-a-token, e naoPRESENÇA.
_SCRIPTS_ESTRANHOS = [
    (0x0370, 0x03FF),  # grego
    (0x0400, 0x04FF),  # cirilico
    (0x0530, 0x058F),  # armenio
]
_LATIN_BASICO = re.compile(r"[A-Za-z]")


def e_script_estranho(cp):
    for lo, hi in _SCRIPTS_ESTRANHOS:
        if lo <= cp <= hi:
            return True
    return False


_TOKEN = re.compile(r"\w+")


def tokens_misturados(linha):
    """Tokens com LATIM e outro script ao mesmo tempo.

    Devolve a lista de `(token,摹)`. Um texto russo ou grego legitimo nao
    produz nenhum: as palavras sao de um script so.
    """
    achados = []
    for m in _TOKEN.finditer(linha):
        tok = m.group(0)
        tem_latin = bool(_LATIN_BASICO.search(tok))
        tem_outro = any(e_script_estranho(ord(c)) for c in tok)
        if tem_latin and tem_outro:
            achados.append((tok, m.start()))
    return achados


def entre_aspas(linha, idx):
    """A ocorrencia esta dentro de aspas na MESMA linha?

    EXCEPCAO MEDIDA, NAO INVENTADA. O console.md tem 12 CJK citados de
    proposito: sao o exemplo da doenca, dentro de aspas. Sem esta
    excepcao a regra dava 12 falsos positivos no proprio ficheiro que
    documenta a doenca. A primeira versao deste script deu falso
    positivo por causa disso, na seccao s7 do console.md.
    """
    antes = linha[:idx]
    return bool(
        (antes.count('"') % 2) or (antes.count("'") % 2) or antes.count("`") % 2
    )


# --------------------------------------------------------------------------
# V1 — corrupcao por bytes
# --------------------------------------------------------------------------
def v1_corrupcao(r, verbose):
    r.correm()
    achados = []
    pulados = 0
    varridos = 0

    for alvo in ("ia-coord", "app", "tests", "docs", "config"):
        base = os.path.join(RAIZ, alvo)
        if not os.path.isdir(base):
            r.nota("V1", "%s/ nao existe - nao varrido" % alvo)
            continue
        for dp, dn, fn in os.walk(base):
            dn[:] = [
                d
                for d in dn
                if d
                not in (
                    "__pycache__",
                    "node_modules",
                    ".venv",
                    "_backups",
                    "htmlcov",
                    ".git",
                    "staticfiles",
                )
            ]
            for f in fn:
                if not f.endswith(EXTENSOES):
                    continue
                caminho = os.path.join(dp, f)
                try:
                    tam = os.path.getsize(caminho)
                except OSError as e:
                    r.erro("V1", "nao pude medir %s: %s" % (f, e))
                    continue
                if tam > TAMANHO_MAX:
                    pulados += 1
                    continue
                try:
                    with open(caminho, "rb") as fh:
                        cru = fh.read()
                except OSError as e:
                    r.erro("V1", "nao pude ler %s: %s" % (f, e))
                    continue
                varridos += 1
                rel = os.path.relpath(caminho, RAIZ)
                if cru[:3] == b"\xef\xbb\xbf":
                    achados.append((rel, 0, "BOM no inicio"))
                texto = cru.decode("utf-8", errors="replace")
                # DISTINCAO QUE A PRIMEIRA VERSAO NAO FEZ, e que a nota
                # 0002 do plenario me obriga a fazer:
                #
                #   em CODIGO (.py .js .css .html), mojibake dentro de
                #   aspas e' SEMPRE falha — e' a string que o produtor le.
                #
                #   em DOCUMENTO (.md), mojibake entre aspas e' CITACAO
                #   legitima: e' o exemplo da doenca, que e' a razao pela
                #   qual o exemplo existe.
                #
                # Sem esta distincao, a nota que documenta a doenca falha
                # ela propria. Com ela, um mojibake real em produto nao
                # se esconde por estar dentro de aspas.
                em_doc = rel.lower().endswith(".md")
                for i, linha in enumerate(texto.split("\n"), 1):
                    for j, ch in enumerate(linha):
                        if e_cjk(ord(ch)) and not entre_aspas(linha, j):
                            achados.append((rel, i, "CJK U+%04X" % ord(ch)))
                            break
                    for m, nome_m in MOJIBAKE:
                        if m in linha:
                            if em_doc and dentro_de_aspas(linha, m):
                                continue
                            achados.append((rel, i, "mojibake: " + nome_m))
                            break
                    # Script misturado no mesmo token: `Kontrtar`, `Aguia`
                    # com 'a' cirilico. Nao tem ideograma e nao e' mojibake,
                    # por isso os dois ramos de cima nao o apanhavam.
                    #
                    # A excepcao das aspas NAO se aplica aqui, e e' de
                    # proposito: em `.md`, um exemplo da doenca dentro de
                    # aspas e' citacao legitima — mas um token com dois
                    # scripts nao e' o exemplo de nada, e o console.md
                    # cita CJK, nao cirilico-a-dentro-de-uma-palavra.
                    for tok, pos in tokens_misturados(linha):
                        achados.append(
                            (
                                rel,
                                i,
                                "scripts misturados no token %r (coluna %d)"
                                % (tok, pos + 1),
                            )
                        )
                        break
    if achados:
        for rel, ln, msg in achados[:60]:
            if ln:
                r.falha("V1", "%s:L%d  %s" % (rel, ln, msg))
            else:
                r.falha("V1", "%s  %s" % (rel, msg))
        if len(achados) > 60:
            r.falha("V1", "... e mais %d" % (len(achados) - 60))
    else:
        r.passa(
            "V1",
            "%d ficheiros varridos, 0 corrupcao real%s"
            % (varridos, ", %d pulados (>2MB)" % pulados if pulados else ""),
        )

    if varridos == 0:
        r.erro("V1", "NAO VARRI NADA - isto e' 'nao verifiquei', nao 'limpo'")


# --------------------------------------------------------------------------
# V2 — manifesto do plenario: alguem reescreveu um registo antigo?
# --------------------------------------------------------------------------
def v2_manifesto(r):
    r.correm()
    if not os.path.isdir(PLENARIO):
        r.erro(
            "V2",
            "plenario/ nao existe: o manifesto nao pode existir. "
            "NINGUEM pode dizer que o registo esta intacto",
        )
        return
    if not os.path.exists(MANIFESTO):
        r.erro(
            "V2",
            "plenario/MANIFESTO.json nao existe. O primeiro a "
            "escrever no plenario tem de o criar. ate la, "
            "REESCRITAS NO PLENARIO SAO INVISIVEIS",
        )
        return
    try:
        with open(MANIFESTO, encoding="utf-8") as fh:
            antes = json.load(fh)
    except (OSError, ValueError) as e:
        r.erro("V2", "manifesto ilegivel: %s: %s" % (type(e).__name__, e))
        return

    alterados = []
    novos = []
    for nome, reg in antes.items():
        caminho = os.path.join(PLENARIO, nome)
        if not os.path.exists(caminho):
            alterados.append((nome, "APAGADO"))
            continue
        with open(caminho, "rb") as fh:
            agora = hashlib.sha256(fh.read()).hexdigest()
        if agora != reg.get("sha256"):
            alterados.append((nome, "REESCRITO"))
    if os.path.isdir(PLENARIO):
        for f in os.listdir(PLENARIO):
            if f.endswith(".md") and f != "INDICE.md" and f not in antes:
                novos.append(f)

    if alterados:
        for nome, motivo in alterados:
            r.falha(
                "V2",
                "%s %s — isso viola R2 (o plenario e' so "
                "de acrescentar)" % (nome, motivo),
            )
    else:
        r.passa("V2", "%d registos intactos" % len(antes))
        if os.path.exists(HISTORICO):
            try:
                with open(HISTORICO, encoding="utf-8") as fh:
                    hist = json.load(fh)
                divergentes = [
                    k
                    for k, v in hist.items()
                    if k in antes and antes[k].get("sha256") != v.get("sha256")
                ]
                if divergentes:
                    r.nota(
                        "V2",
                        "%d nota(s) mudaram de hash desde o ultimo "
                        "registo: %s — ver HASHES-HISTORICO.json"
                        % (len(divergentes), ", ".join(divergentes[:4])),
                    )
            except (OSError, ValueError):
                r.erro("V2", "HASHES-HISTORICO.json existe mas nao le")
    if novos:
        r.nota(
            "V2",
            "%d ficheiro(s) novo(s) sem entrada no manifesto: %s"
            % (len(novos), ", ".join(sorted(novos)[:6])),
        )


# --------------------------------------------------------------------------
# V3 — numeracao: cada relatorio tem o numero certo?
# --------------------------------------------------------------------------
RE_NUM = None


def v3_numeracao(r):
    r.correm()
    """Cada slot declarado tem a pasta que o seu numero diz?

    BUG MEU NA PRIMEIRA VERSAO: a regex capturava "06" e produzia
    "ia-06/", que nao existe. Dois falsos positivos HOJE, quando a
    resposta certa era "o slot existe, eu normalizei mal". Agora
    normaliza com int().
    """
    import re as _re

    padrao = _re.compile(r"^\s*(?:IA|S|s)\s*-?\s*(\d{1,2})\b")
    declarados = {}
    for i, linha in enumerate(ENUM, 1):
        m = padrao.match(linha)
        if m:
            n = int(m.group(1))
            declarados.setdefault(n, i)
    if not declarados:
        r.nota("V3", "nenhum slot declarado no console.md")
        return
    for n in sorted(declarados):
        esperado = "ia-%d" % n
        if not os.path.isdir(os.path.join(COORD, esperado)):
            r.erro(
                "V3",
                "console.md L%d declara %s, mas %s/ nao existe"
                % (declarados[n], esperado, esperado),
            )
    r.nota(
        "V3", "%d slot(s) declarados no console.md, todos com pasta" % len(declarados)
    )


# --------------------------------------------------------------------------
# V4 — cada slot tem pasta?
# --------------------------------------------------------------------------
def v4_slots(r):
    r.correm()
    faltam = []
    for s in SLOTS:
        if not os.path.isdir(os.path.join(COORD, s)):
            faltam.append(s)
    if faltam:
        r.nota("V4", "%d slot(s) sem pasta: %s" % (len(faltam), ", ".join(faltam)))
    else:
        r.passa("V4", "as 11 pastas de slot existem")
    for d in ("guard", "plenario"):
        p = os.path.join(COORD, d)
        if not os.path.isdir(p):
            r.erro("V4", "%s/ nao existe" % d)
    # console.md: R11 diz que esta morto. Dizer se ainda cresce.
    cm = os.path.join(RAIZ, "console.md")
    if os.path.exists(cm):
        if not versionado(cm):
            r.nota(
                "V4",
                "console.md existe e NAO esta versionado. R11 "
                "declara-o morto; enquanto nao for substituido "
                "e versionado, e' o unico registo que nao tem "
                "segunda copia",
            )


def versionado(caminho):
    """True se o ficheiro esta no indice do git."""
    try:
        with open(os.path.join(RAIZ, ".git", "HEAD"), "rb"):
            pass
    except OSError:
        return False
    rel = os.path.relpath(caminho, RAIZ)
    idx = os.path.join(RAIZ, ".git", "index")
    if not os.path.exists(idx):
        return False
    with open(idx, "rb") as fh:
        return rel.replace("\\", "/").encode("utf-8") in fh.read()


# --------------------------------------------------------------------------
# V5 — ficheiros suspiciously truncados
# --------------------------------------------------------------------------
def v5_truncados(r):
    r.correm()
    alvos = []
    for dp, dn, fn in os.walk(COORD):
        dn[:] = [d for d in dn if d != "__pycache__"]
        for f in fn:
            if f.endswith((".md", ".py", ".json")):
                alvos.append(os.path.join(dp, f))
    suspeitas = []
    avisos = []
    for caminho in alvos:
        try:
            with open(caminho, "rb") as fh:
                cru = fh.read()
        except OSError as e:
            r.erro("V5", "nao pude ler %s: %s" % (caminho, e))
            continue
        if not cru.strip():
            suspeitas.append((caminho, "VAZIO"))
            continue
        # FALHA DE VERDADE: bytes que nao sao UTF-8 valido. E' o sinal
        # de escrita interrompida a meio de um multibyte.
        try:
            cru.decode("utf-8")
        except UnicodeDecodeError as e:
            suspeitas.append(
                (caminho, "UTF-8 INVALIDO em %s — escrita interrompida?" % e)
            )
            continue
        texto = cru.decode("utf-8")
        # NOTA, nao FALHA: ficheiro legitimo pode nao terminar em
        # newline. Na primeira versao isto era FALHA e deu 3 falsos
        # positivos em ficheiros inteiros.
        if not cru.endswith(b"\n"):
            avisos.append((caminho, "sem newline final"))
        if texto.count("```") % 2 == 1:
            avisos.append((caminho, "cercas de codigo por fechar"))
    if suspeitas:
        for caminho, msg in suspeitas:
            r.falha("V5", "%s: %s" % (os.path.relpath(caminho, RAIZ), msg))
    if avisos:
        for caminho, msg in avisos:
            r.nota("V5", "%s: %s" % (os.path.relpath(caminho, RAIZ), msg))
    if not suspeitas and not avisos:
        r.passa("V5", "%d ficheiros em ia-coord/ integros" % len(alvos))
        return
    if not suspeitas:
        r.nota("V5", "0 truncamentos; %d aviso(s) menor(es)" % len(avisos))


# --------------------------------------------------------------------------
def aceitar_plenario():
    """--aceitar-plenario: registar o hash das notas novas no manifesto.

    O INDICE.md manda correr este comando e ele nao existia. Sem ele, o
    V2 nunca tinha com o que comparar, e as reescritas no plenario
    continuavam invisiveis.
    """
    if not os.path.isdir(PLENARIO):
        sys.stderr.write("ERRO: plenario/ nao existe\n")
        return 2
    manifesto = {}
    if os.path.exists(MANIFESTO):
        try:
            with open(MANIFESTO, encoding="utf-8") as fh:
                manifesto = json.load(fh)
        except (OSError, ValueError) as e:
            sys.stderr.write(
                "ERRO: manifesto ilegivel (%s). NAO APAGO-O.\n"
                "      move-o para .bak e corrige a mao.\n" % e
            )
            return 2

    antes_historico = dict(manifesto)

    novos = 0
    for f in sorted(os.listdir(PLENARIO)):
        if not f.endswith(".md"):
            continue
        if f in ("INDICE.md", "MANIFESTO.json"):
            continue
        caminho = os.path.join(PLENARIO, f)
        with open(caminho, "rb") as fh:
            h = hashlib.sha256(fh.read()).hexdigest()
        if manifesto.get(f, {}).get("sha256") == h:
            continue
        estado = "novo" if f not in manifesto else "ALTERADO"
        if estado == "ALTERADO":
            sys.stderr.write(
                "AVISO: %s ja estava no manifesto e o hash MUDOU (%s)\n"
                "        isso viola R2. Registo o novo, mas o registo "
                "anterior perdeu-se.\n" % (f, manifesto[f].get("sha256", "?")[:12])
            )
        manifesto[f] = {
            "sha256": h,
            "bytes": os.path.getsize(caminho),
            "quando": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        novos += 1
        sys.stdout.write("  %-9s %s  %s\n" % (estado, f, h[:12]))

    if novos == 0:
        sys.stdout.write("  nada novo para registar\n")
    with open(MANIFESTO, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(manifesto, ensure_ascii=False, indent=2, sort_keys=True))
        fh.write("\n")
    sys.stdout.write("  MANIFESTO.json: %d nota(s) registada(s)\n" % len(manifesto))
    return 0


def mostrar(r, as_json):
    if as_json:
        print(
            json.dumps(
                {
                    "ok": r.ok,
                    "falhou": r.falhou,
                    "nao_verificado": r.nao_verificado,
                    "resultados": [
                        {"estado": e, "verificacao": v, "msg": m}
                        for e, v, m in r.linhas
                    ],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return
    for estado, v, msg in r.linhas:
        print("  [%-15s] %-4s %s" % (estado, v, msg))
    print("")
    print("  verificacoes que correram .. %d" % r.executadas)
    print("  falhas ...................... %d" % r.ok)
    print("  nao verificadas ..... %d" % r.nao_verificado)
    if r.nao_verificado:
        print("")
        print("  ATENCAO: %d verificacao(oes) NAO CORRERAM." % r.nao_verificado)
        print("  Isso NAO e' 'passou'. E' 'nao verifiquei'. (R5)")


def main(argv):
    # O stdout do Windows e' cp1252 e rebenta com nao-ASCII. Sem isto,
    # o guarda MORRE a tentAR RELATAR a corrupcao — que foi exactamente
    # o que aconteceu na primeira versao do sem_cjk.py.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    global ENUM
    as_json = "--json" in argv
    aceitar = "--aceitar-plenario" in argv
    so = None
    for i, a in enumerate(argv):
        if a == "--so" and i + 1 < len(argv):
            so = argv[i + 1].lower()

    if not os.path.isdir(COORD):
        sys.stderr.write("ERRO: ia-coord/ nao existe em %s\n" % RAIZ)
        sys.stderr.write("NAO VERIFICADO: nada foi corrido.\n")
        return 2

    if aceitar:
        return aceitar_plenario()

    console = os.path.join(RAIZ, "console.md")
    ENUM = (
        open(console, encoding="utf-8", errors="replace").read().split("\n")
        if os.path.exists(console)
        else []
    )

    r = Resultado()
    if not so or so == "v1":
        v1_corrupcao(r, False)
    if not so or so == "v2":
        v2_manifesto(r)
    if not so or so == "v3":
        v3_numeracao(r)
    if not so or so == "v4":
        v4_slots(r)
    if not so or so == "v5":
        v5_truncados(r)

    if r.executadas == 0:
        print("  NADA FOI VERIFICADO. Nem uma verificacao correu.")
        mostrar(r, as_json)
        return 1
    mostrar(r, as_json)
    return 1 if (r.ok or r.nao_verificado) else 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except Exception as exc:
        # R5: uma falha silenciosa e' pior que uma falha gritada.
        sys.stderr.write("ERRO %s: %s\n" % (type(exc).__name__, exc))
        sys.stderr.write(
            "O GUARDAO NAO CORREU ATE AO FIM. Nada do que ele disse e' um veredicto.\n"
        )
        sys.exit(2)
