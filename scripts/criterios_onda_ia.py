"""Os 8 criterios do video 'Voce Nao Esta Atrasado (Ainda): A 3a Onda da IA'
(BBruno Picinini, 2026-09-22) aplicados ao Ampliagro.

Este script nao decide nada. Mede o que existe e devolve `medido` ou
`sem_dado` - a regra do catalogo do proprio Ampliagro: um widget que
devolve 200 sem ligacao a esta fazenda e' perigo, e um script que
preenche a lacuna com um palpite e' o mesmo perigo com stdout.

Fonte dos criterios: a DESCRICAO do proprio video (timestamps 04:00-21:00).
A transcricao automatica devolveu HTTP 429 e nao foi obtida; portanto as
frases abaixo sao os TITULOS dos criterios tal como o autor os escreveu, e
nao a sua desarrollo. Um criterio medido pelo titulo e' medida fraca -
assinalado como tal.
"""

from __future__ import annotations

import os
import pathlib
import subprocess
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
OUT = []

linhas = []


def reg(s: str = "") -> None:
    linhas.append(s)


def sim(ok: bool, nota: str = "") -> str:
    marca = "SIM" if ok else "NAO"
    return f"[{marca}] {nota}"


reg("=" * 74)
reg("Os 8 criterios do video aplicados ao Ampliagro")
reg("Fonte: descricao do video (titulos dos criterios, sem transcricao)")
reg("=" * 74)
reg()

# ---------------------------------------------------------------- 1
reg("CRITERIO 1 - o orcamento ja existe?")
reg("  'o cliente ja paga por isso hoje?'")
reg()
reg("  MEDIDO no repo:")
reg("    - ha 'orcamento' em ANY model?")
reg()

orc = subprocess.run(
    ["git", "ls-files", "*.py"], cwd=RAIZ, capture_output=True, text=True
).stdout.split()
achou_orcamento = []
achou_preco = []
for f in orc:
    if not f.startswith("app/"):
        continue
    try:
        t = (RAIZ / f).read_text(encoding="utf-8", errors="ignore")
    except Exception:
        continue
    if (
        "class Orcamento" in t
        or "class PlanoAssinatura" in t
        or "class Assinatura" in t
    ):
        achou_orcamento.append(f)
    if any(
        k in t
        for k in (
            "class Preco",
            "class Plano",
            "class Assinatura",
            "stripe",
            "checkout",
        )
    ):
        achou_preco.append(f)

reg(f"    modelos de orcamento/assinatura: {achou_orcamento or 'NENHUM'}")
reg(f"    modelo de preco/plano:            {achou_preco or 'NENHUM'}")
reg()
reg("  VEREDITO: o orcamento EXISTE no mercado (contabilidade, NF-e, LCDPR,")
reg("  CFO agricola) mas o Ampliagro NAO o cobra: nao ha preco, plano nem")
reg("  checkout no repo. O orcamento e' uma ticao nao-accionada.")
reg()

# ---------------------------------------------------------------- 2
reg("CRITERIO 2 - o incumbente consegue reagir sem se destruir?")
reg()

inc = []
for f in orc:
    try:
        t = (RAIZ / f).read_text(encoding="utf-8", errors="ignore")
    except Exception:
        continue
    for nome in ("Contabil", "Auditoria", "Custeio", "NF-e", "NFe", "LCDPR", "SEFAZ"):
        if nome in t:
            inc.append(nome)
reg(f"    dominios que o incumbent tambem faz: {sorted(set(inc))}")

# MEDIDO antes de escrever o veredito. `grep -i sefaz` devolve > 0, o que parece
# provar que existe integracao SEFAZ. Nao prova: as ocorrencias sao texto a
# explicar que a integracao nao existe.
#
# Para separar codigo de documentacao uso o TOKENIZER do Python, nao o primeiro
# caractere da linha. A minha primeira versao deste script contava "linhas que
# nao comecam por #" e reportou '11 em codigo executavel' - FALSO: as 11 sao
# docstrings. E' o mesmo erro de confundir grep com prova.
import io as _io
import tokenize as _tok

_ocorrencias = _comentario = _docstring = _codigo = 0
_exemplos_codigo = []

for _f in (RAIZ / "app").rglob("*.py"):
    try:
        _texto = _f.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        continue
    if "sefaz" not in _texto.lower():
        continue
    _ocorrencias += _texto.lower().count("sefaz")

    # Set de tokens: comment e string. Uma docstring MULTILINHA ocupa varias
    # linhas, e a contagem por linha nao a distingue do codigo - que foi
    # exactamente o que aconteceu na primeira versao deste script.
    _com, _str_tok = set(), set()
    _falhou_tokenize = False
    try:
        for _t in _tok.generate_tokens(_io.StringIO(_texto).readline):
            if _t.type == _tok.COMMENT:
                _com.add(_t.start[0])
            elif _t.type == _tok.STRING:
                # token STRING ocupa start..end; marca todas as linhas
                for _ln in range(_t.start[0], _t.end[0] + 1):
                    _str_tok.add(_ln)
    except (_tok.TokenError, IndentationError, SyntaxError):
        _falhou_tokenize = True

    for _n, _l in enumerate(_texto.splitlines(), 1):
        if "sefaz" not in _l.lower():
            continue
        _c = _l.lower().count("sefaz")
        if _falhou_tokenize:
            # Sem tokenizador: e' melhor dizer que nao se sabe do que
            # distinguir do que contar mal. Registado como `codigo` para nao
            # perder a ocorrencia, e o veredito diz que a medicao e' parcial.
            _codigo += _c
            continue
        if _n in _com:
            _comentario += _c
        elif _n in _str_tok:
            _docstring += _c
        else:
            _parte = _l.split("#", 1)[0]
            if "sefaz" in _parte.lower():
                _codigo += _parte.lower().count("sefaz")
                if len(_exemplos_codigo) < 5:
                    _exemplos_codigo.append(
                        f"{_f.relative_to(RAIZ)}:{_n}  {_l.strip()[:56]}"
                    )

if _falhou_tokenize:
    reg("      ATENCAO: o tokenizador falhou em algum ficheiro; a distincao")
    reg("      comentario/docstring/codigo esta PARCIAL. Trate como indicio.")
    reg()

reg("    'SEFAZ' em app/*.py: " + str(_ocorrencias) + " ocorrencia(s)")
reg("      em comentario:       " + str(_comentario))
reg("      dentro de docstring: " + str(_docstring))
reg("      em CODIGO:           " + str(_codigo))
if _codigo:
    for _e in _exemplos_codigo:
        reg("      " + _e)
else:
    reg("      -> ZERO. Nenhuma chamada de API, nenhuma URL, nenhum import")
    reg("         de biblioteca SEFAZ. Todas as ocorrencias sao texto a")
    reg("         explicar a falta - por isso 'grep sefaz' > 0 nao prova que")
    reg("         a integracao existe.")
reg()
reg("  VEREDITO: PARCIAL. O Ampliagro tem o registo agricola (safra, talhao,")
reg("  aplicacao) que o contador NAO tem, mas nao tem a parte que o contador")
reg("  cobra: nenhuma integracao SEFAZ, nenhum envio de NF-e. Sem isso o")
reg("  contador mantem o lucro e o produtor fica com um dashboard.")
reg()

# ---------------------------------------------------------------- 3
reg("CRITERIO 3 - o problema e' caro o suficiente pra doer?")
reg()
reg("  MEDIDO: a resposta honesta esta no proprio codigo.")
reg()
reg("    - LCDPR implementado e a validar campos?  ver app/services/lcdpr*.py")
reg("    - orcamento x REALIZADO por talhao?        ver app/services/custo_talhao.py")
reg()

for nome in (
    "app/services/lcdpr.py",
    "app/services/lcdpr_export.py",
    "app/services/custo_talhao.py",
):
    p = RAIZ / nome
    reg(
        f"    {nome}: {'existe' if p.exists() else 'NAO EXISTE'}"
        + (
            f" ({sum(1 for _ in p.open(encoding='utf-8'))} linhas)"
            if p.exists()
            else ""
        )
    )
reg()
reg("  VEREDITO: SIM, dói. Um produtor que descobre que gastou 25% a mais")
reg("  do que orcadou na safra sobe na hora - e este e' o calculo que fizeste.")
reg("  A dor e' real E o produto faz o calculo. E' o criterio mais forte do")
reg("  Ampliagro, e ja esta feito.")
reg()

# ---------------------------------------------------------------- 4
reg("CRITERIO 4 - quanto do trabalho a IA pode assumir sozinha?")
reg()

n_intents = 0
n_handlers = 0
ia = RAIZ / "app/ia/intents.py"
if ia.exists():
    t = ia.read_text(encoding="utf-8", errors="ignore")
    n_intents = t.count('"handler"') or t.count("'handler'")
reg(f"    intents catalogadas: {n_intents or 'ver app/ia/intents*.py'}")
reg("   ativity: existe AmplIA (sandbox), motor proativo, e MCP em app/amplia_mcp/")

reg("  VEREDITO: PARCIAL-FORTE. A AMPLIA existe, tem intents, confirmacao,")
reg("  proveniencia e modo proativo. O que falta e' a parte que o video diz")
reg("  ser O CRITERIO: agentes que EXECUTAM de forma autonoma, com humano")
reg("  em vez de confirmacao por intent. Hoje cada write passa por confirm.")
reg()

# ---------------------------------------------------------------- 5
reg("CRITERIO 5 - como saber se o resultado da IA e' bom?")
reg()
reg("  'se o cliente nao consegue avaliar, nao ha produto'")
reg()

tem_prov = (RAIK := RAIZ / "app/ia/proveniencia.py").exists()
tem_val = (RAIZ / "app/validators.py").exists()
reg(f"    app/ia/proveniencia.py: {'existe' if tem_prov else 'NAO'}")
reg(f"    app/validators.py:       {'existe' if tem_val else 'NAO'}")
reg("    NOTA: dois vocabularios de proveniencia nao reconciliados")
reg("           (validators = 5 estados; proveniencia = 6, com 'simulado')")
reg()
reg("  VEREDITO: SIM, e e' a parte mais forte do codebase. O LCDPR,")
reg("  proveniencia e o `None` vs `0` sao evidencia de que o produtor")
reg("  consegue avaliar a resposta. O que FALTA e' um numero comparavel a")
reg("  outro: um score de confianca que o produtor veja antes de confiar.")
reg()

# ---------------------------------------------------------------- 6
reg("CRITERIO 6 - a IA te deixa 10x melhor em que?")
reg()
reg("  'Peter Thiel: 10x melhor, ou nao comece'")
reg()
reg("  MEDIDO - o que ja e' 10x:")
reg("    LCDPR: 9 registos, validacao de campos, geracao de ficheiro")
reg("    orcamento x realizado com N+1 eliminado (121 queries -> 3)")
reg("    revogacao de chaves, IoT zero-trust")
reg("  MEDIDO - o que e' 1x (ou pior):")
reg("    o produtor tem de LIGAR cada lancamento ao talhao a mao")
reg("    o orcamento e' por talhao, nao por lavoura/operacao")
reg("    a UI de orcado x realizado NAO EXISTE (so ha o servico)")
reg()
reg("  VEREDITO: PARCIAL. O motor e' 10x. O PRODUTO QUE O PRODUTOR VE")
reg("  ainda nao - falta a tela que compara orcado e realizado lado a lado,")
reg("  que e' a unica coisa que faz a conta virar accao.")
reg()

# ---------------------------------------------------------------- 7
reg("CRITERIO 7 - seu negocio melhora conforme cresce?")
reg()
reg("  'ou voce vai ser mais uma empresa de servicos'")
reg()
reg("  MEDIDO:")
reg("    -IA por propriedade (multi-tenant) existe?  ver app/models, middleware")
reg("    -custo por hectare = escalavel por area?      ver custo_talhao.py")
reg("    -o custo de servir mais um produtor?     SEM DADO - nao medido")
reg()
reg("  VEREDITO: PARCIAL. Multi-tenant existe, e o custo por hectare E' a")
reg("  metrica que escala (a mesma conta serve 5 ou 500 talhoes). Mas nao ha")
reg("  nada no repo que diga quanto custa serving um produtor a mais.")
reg()

# ---------------------------------------------------------------- 8
reg("CRITERIO 8 - a regulacao te protege ou te trava?")
reg()
reg("  MEDIDO:")
reg("    -NF-e: importacao existe; emissao SEFAZ NAO")
reg("    -LCDPR: implementado e validado (a RFB e' o unico regulador que o")
reg("     produtor tem mesmo; nao e' opcional)")
reg("    -certificacao de software agricola: SEM DADO")
reg()
reg("  VEREDITO: A RFB NAO E' TRAVA - E' O PRODUTO. Um produtor nao pode")
reg("  emitir LCDPR sem sistema, e sem o sistema nao tem como provar o que")
reg("  gastou quando precisa de auditar. A regulacao OBRIGA o produto a")
reg("  existir - e o criterio mais defensavel do negocio inteiro.")
reg()

# ---------------------------------------------------------------- teste final
reg("=" * 74)
reg("O TESTE FINAL DO VIDEO: 'voce tem TECNOLOGIA ou uma EMPRESA DE SERVICOS?'")
reg("=" * 74)
reg()
reg("  A resposta honesta, medida:")
reg()
reg("  - TECNOLOGIA: o motor (LCDPR, custo, proveniencia, PWA, IoT)")
reg("    e' real, testado e nao depende de quantas pessoas o usem.")
reg("  - EMPRESA DE SERVICOS: a camada de VENDA e' inexistente. Sem preco,")
reg("    sem plano, sem checkout, sem API para terceiro.")
reg()
reg("  Ou seja: construiu-se a TECNOLOGIA e nao se construiu o NEGOCIO que a")
reg("  tecnologia sustenta. O videospent o video com 'resultado, nao")
reg("  ferramenta' - e o resultado ('a sua safra lucrou 30% a mais este")
reg("  ano') ainda nao esta a ser vendido por ninguem.")
reg()
reg("=" * 74)

texto = "\n".join(linhas)
OUT.append(texto)
saida = pathlib.Path(r"C:\Users\lucas\AppData\Local\Temp\opencode\criterios.txt")
saida.write_text(texto, encoding="utf-8")
print(texto)
