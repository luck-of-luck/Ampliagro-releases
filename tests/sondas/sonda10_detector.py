"""Sonda 10 — o preenchimento de campos por conversa, do lado do servidor.

Mede, não testa. É a origem de todos os números de `docs/sistema/10.md`.
Corra com o Django configurado (oProbe faz isso sozinho):

    python docs/sistema/_sonda10.py            # tudo
    python docs/sistema/_sonda10.py 2          # só a secção 2

Porque uma sonda e não um teste: um teste diz "isto passa / isto falha". Um
defeito de rota e de pontuação — "cadastrar nova safra" vai para
`cadastrar_maquina` — não é um teste que se escreva, é uma MEDIDA. A sonda
transforma a afirmação em número, e o número fica no documento para ser
confrontado por quem decidir.
"""

import ast
import inspect
import os
import re
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, RAIZ)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.test")

import django  # noqa: E402

django.setup()

from app.ia import registro as _reg  # noqa: E402
from app.ia.deteccao import _escrita_pretendida, detectar  # noqa: E402

CAT = _reg.todos()
SO = int(sys.argv[1]) if len(sys.argv) > 1 else 0


def titulo(n, txt):
    if SO in (0, n):
        print()
        print("=" * 78)
        print("%d. %s" % (n, txt))
        print("=" * 78)


# ───────────────────────────────────────────────────────────────────────────
titulo(1, "O CATALOGO, e o detector nas frases do produtor")
# ───────────────────────────────────────────────────────────────────────────
if SO in (0, 1):
    print("intents no registo: %d" % len(CAT))
    n_ex = sorted((len((CAT[n] or {}).get("exemplos") or []), n) for n in CAT)
    print(
        "exemplos por intent: min=%d (%s)  max=%d (%s)"
        % (n_ex[0][0], n_ex[0][1], n_ex[-1][0], n_ex[-1][1])
    )
    print()
    for f in [
        "qual talhao temos disponivel para plantar",
        "qual talhao a gente tem disponivel",
        "qual talhao esta disponivel para plantar?",
        "voltagem esta disponivel",
        "quais talhoes estao disponiveis?",
        "como cadastro um talhao",
    ]:
        r = detectar(f)
        top = sorted(r["scores"].items(), key=lambda x: -x[1])[:3]
        print("%r" % f)
        print(
            "   escolhido=%-22s acima=%-5s metodo=%-14s top3=%s"
            % (
                r["escolhido"],
                r["acima_do_limiar"],
                r["metodo"],
                [(n, s) for n, s in top if s > 0],
            )
        )


# ───────────────────────────────────────────────────────────────────────────
titulo(2, "PERGUNTA vs ESCRITA — e o `elif` que dá a prioridade à escrita")
# ───────────────────────────────────────────────────────────────────────────
if SO in (0, 2):
    print("deteccao.py:222   e_pergunta = texto.strip().endswith('?')")
    print("deteccao.py:229   if quer_escrever: ... elif e_pergunta: <só leitura>")
    print(
        "                  ^ `elif`: havendo verbo de escrita, a pergunta nunca é lida"
    )
    print()
    print("%-46s %-9s %-9s %s" % ("frase", "escrita?", "pergunta?", "escolhido"))
    for f in [
        "qual talhao temos disponivel para plantar",
        "qual talhao temos disponivel para plantar?",
        "voce pode excluir a safra de milho?",
        "como excluo a safra de milho?",
        "a gente pode apagar a safra 2025?",
        "qual talhao tenho que cadastrar",
    ]:
        r = detectar(f)
        print(
            "%-46s %-9s %-9s %s"
            % (f, _escrita_pretendida(f), f.strip().endswith("?"), r["escolhido"])
        )


# ───────────────────────────────────────────────────────────────────────────
titulo(3, "O SCORE NAO É COMPARÁVEL ENTRE INTENTS (a soma não é uma média)")
# ───────────────────────────────────────────────────────────────────────────
if SO in (0, 3):
    print(
        "deteccao.py:243   total += acertos / len(exemplo)   # soma por TODOS os exemplos"
    )
    print(
        "deteccao.py:246   score = round(total, 2)             # nunca divide pelo nº de exemplos"
    )
    print(
        "deteccao.py:255   metodo = 'forte' if melhor_score >= 1.0   # 1.0 = UM exemplo casado"
    )
    print()
    print(
        "=> o score máximo de uma intent é o seu nº de exemplos, e o limiar é 0.60 fixo."
    )
    print()
    for f in [
        "cadastrar nova safra",
        "cadastrar um talhao novo",
        "registrar um funcionario",
        "adicionar um insumo no estoque",
        "cria uma estacao meteorologica",
        "exclui a safra de milho",
    ]:
        r = detectar(f)
        top = sorted(((s, n) for n, s in r["scores"].items() if s > 0), reverse=True)[
            :3
        ]
        print("  %-40s -> %-24s %s" % (f, r["escolhido"], [(n, s) for s, n in top]))


# ───────────────────────────────────────────────────────────────────────────
titulo(4, "O REGISTO PEDE CONFIRMAÇÃO? O HANDLER PROTEGE?")
# ───────────────────────────────────────────────────────────────────────────
if SO in (0, 4):
    from app.ia.sandbox import _LIMIAR_ESCRITA

    print("gate M3: sandbox.py:271  _LIMIAR_ESCRITA = %s" % _LIMIAR_ESCRITA)
    print("         sandbox.py:565  só vira confirmação se o score for MENOR")
    print()

    def src_do_handler(nome):
        h = (CAT.get(nome) or {}).get("handler")
        if h is None:
            return None, None, ""
        try:
            h = inspect.unwrap(h)
        except Exception:
            pass
        alvo = h
        if h.__name__ == "<lambda>":
            try:
                codigo = inspect.getsource(h)
            except (OSError, TypeError):
                return None, None, ""
            m = re.search(r"\b(h_\w+)\s*\(", codigo)
            if not m:
                return None, None, codigo
            import importlib

            for mod in (
                "app.ia.intents",
                "app.ia.intents2",
                "app.ia.intents3",
                "app.ia.intents4",
                "app.ia.dinamico_intents",
                "app.ia.proativo_intents",
                "app.ia.iot_intents",
                "app.ia.chamado_intents",
            ):
                try:
                    alvo = getattr(importlib.import_module(mod), m.group(1), None)
                except Exception:
                    alvo = None
                if alvo is not None:
                    break
        try:
            return (
                os.path.basename(inspect.getsourcefile(alvo) or "?"),
                inspect.getsourcelines(alvo)[1],
                inspect.getsource(alvo),
            )
        except (OSError, TypeError):
            return None, None, ""

    print(
        "%-26s %-9s %-24s %-11s %s"
        % ("intent", "registo", "handler (ficheiro:linha)", "guarda?", "gate M3 fecha?")
    )
    print("-" * 104)
    for nome in [
        "excluir_safra",
        "editar_safra",
        "cadastrar_talhao",
        "ligar_irrigador",
        "desligar_irrigador",
        "criar_entidade",
        "inserir_registro",
        "provisionar_endpoint_iot",
        "revogar_endpoint_iot",
        "ligar_proatividade",
        "emitir_alerta_proativo",
        "concluir_tarefa",
        "associar_tarefa",
        "feedback",
    ]:
        spec = CAT.get(nome) or {}
        reg = bool(spec.get("requires_confirmation") or spec.get("needs_confirm"))
        ficheiro, linha, codigo = src_do_handler(nome)
        guarda = bool(re.search(r"""params\.get\(\s*['"]confirm['"]""", codigo))
        m3 = "- (o registo basta)" if reg else "- (o handler basta)"
        if not reg and not guarda:
            r = detectar(nome.replace("_", " "))
            sc = r["scores"].get(r["escolhido"]) if r["escolhido"] else None
            m3 = "NAO (score %s)" % sc if sc is None or sc >= _LIMIAR_ESCRITA else "sim"
        print(
            "%-26s %-9s %-24s %-11s %s"
            % (
                nome,
                "SIM" if reg else "nao",
                ("%s:%s" % (ficheiro, linha)) if ficheiro else "?",
                "SIM" if guarda else "** NAO **",
                m3,
            )
        )

    print()
    print("Leitura: o registo e' METADADO, o handler e' O QUE CORRE.")
    print("Onde o handler pede `confirm`, o registo so documenta.")
    print("Onde nem um nem outro pede, a unica rede e' o gate M3 — e esse fecha")
    print("quando o detector DUVIDOU, nao quando o detector ERROU com conviccao.")
    print()
    print("`emitir_alerta_proativo` nao pede `confirm` nem no registo nem no handler,")
    print("mas tem governanca propria (`emitir_alerta` -> `pode_emitir`). A coluna")
    print("`gate M3 fecha?` mede SO o M3 — e por isso diz NAO. A proteccao existe,")
    print("esta noutro sitio. E' o aviso desta tabela: uma coluna mede UMA coisa,")
    print("e 'nao protege' nela nao quer dizer 'nao esta protegido'.")
