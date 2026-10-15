"""A regra do projecto, verificada pelo caminho real.

    toda escrita tem `requires_confirmation`

POR QUE ESTE TESTE EXISTE
=========================
A equipa do Caderno encontrou um `talhao_id` que era validado num sitio e
ignorado noutro: `validate_talhao_id` existia, estava correcta, e nunca
corria. O defeito nao era a validacao — era nao haver ligacao entre a
declaracao e o caminho de execucao.

Este teste verifica essa ligacao para a confirmacao: um intent que grava tem
de ter `requires_confirmation: True` **na entrada da tabela que o
regista**, porque e' a tabela que o `sandbox.py` le. Verificar a flag dentro
do corpo da funcao seria verificar o sitio errado — foi precisamente o
erro que a equipa cometeu no `talhao_id`.

Como o `INTENTS` e' um dict literal com `"handler": h_algo`, o caminho e':
  1. extrair cada entrada e o handler a que aponta;
  2. determinar quais handlers escrevem em modelo;
  3. exigir a flag na entrada correspondente.
"""

import ast
import inspect
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
INTENTS_PY = RAIZ / "app" / "ia" / "intents.py"
SANDBOX_PY = RAIZ / "app" / "ia" / "sandbox.py"


def _fontes() -> tuple[str, str]:
    return (
        INTENTS_PY.read_text(encoding="utf-8"),
        SANDBOX_PY.read_text(encoding="utf-8"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# 1. O gate existe?
# ─────────────────────────────────────────────────────────────────────────────


def test_o_gate_de_confirmacao_existe_no_sandbox():
    """Se o `sandbox.py` deixar de ler a flag, nada abaixo importa."""
    _, sb = _fontes()
    assert "requires_confirmation" in sb, (
        "sandbox.py deixou de mencionar `requires_confirmation`. O gate "
        "sumiu; os testes abaixo passariam a nao dizer nada."
    )


# ─────────────────────────────────────────────────────────────────────────────
# 2. Os handlers que escrevem
# ─────────────────────────────────────────────────────────────────────────────


def _handlers_que_escrevem(txt: str) -> set[str]:
    """Handlers cujo corpo grava num modelo.

    Deliberadamente nao usa os *flags* da tabela: ha intents que escrevem
    sem flag (e sao esses que queremos apanhar). Detecta pelo corpo.
    """
    escrever = re.compile(r"\.(save|create|update|delete)\s*\(")
    achados = set()
    for m in re.finditer(r"^def\s+(h_\w+)\s*\(", txt, re.M):
        nome = m.group(1)
        nxt = txt.find("\ndef ", m.end())
        if nxt == -1:
            nxt = txt.find("\nINTENTS = {", m.end())
        corpo = txt[m.start() : nxt if nxt != -1 else len(txt)]
        if escrever.search(corpo):
            achados.add(nome)
    return achados


#: O mesmo detector, mas sobre o registo em memoria.
#:
#: MEDIDO 2026-10-04: `intents.py` deixou de ser o catalogo. O `sandbox.py`
#: le `from app.ia.registro import REGISTO as INTENTS` — e o `REGISTO` tem
#: **81** entradas contra as **77** de `intents.INTENTS`. As 4 a mais vivem em
#: `chamado_intents.py`, e tres delas escrevem:
#:
#:     chamado_criar     h_chamado_criar      escreve  confirm=True
#:     chamado_editar    h_chamado_editar     escreve  confirm=True
#:     chamado_publicar  h_chamado_publicar   escreve  confirm=True
#:
#: As tres estao gateadas — por sorte, nao por decisao. Este detector via texto
#: de `intents.py` e' **cego** para elas: `def h_chamado_*` nao esta' nesse
#: ficheiro. Um handler de escrita novo em `intents2`/`intents4`/`INTENTS_IOT`
#: nao seria visto, e este teste — que existe exactamente para o apanhar —
#: passaria a dizer que nao ha nada a ver.
#:
#: Ler o registo e' tambem o que torna o detector independente da orgânica dos
#: ficheiros: um catalogo novo nao precisa de ser adicionado a uma lista.
_ESCREVER = re.compile(r"\.(save|create|update|delete|bulk_create)\s*\(")


def _handlers_que_escrevem_do_registro() -> set[str]:
    """Os mesmos handlers, mas Discovery por runtime e nao por texto.

    `inspect.getsource` do handler que a TABELA aponta. Se a fonte nao estiver
    disponivel (handler montado a mao), salta-se: e' melhor nao ver esse
    handler do que inventar um veredicto sobre ele.
    """
    from app.ia.registro import REGISTO

    achados = set()
    for spec in REGISTO.values():
        if not isinstance(spec, dict):
            continue
        h = spec.get("handler")
        if not callable(h):
            continue
        try:
            src = inspect.getsource(h)
        except (OSError, TypeError):
            continue
        if _ESCREVER.search(src):
            achados.add(h.__name__)
    return achados


def _entradas_da_tabela(txt: str) -> dict[str, str]:
    r"""handler -> nome da entrada da tabela que o regista.

    Anda para tras a partir de `"handler": h_algo` ate a LINHA QUE ABRE a
    entrada (`"algo": {`) e le o nome dessa linha.

    MEDIDO 2026-10-04: procurava `"([\w:]+)"\s*:\s*\{` em qualquer posicao.
    Falha com o mesmo defeito que a `tem_flag` abaixo soIhava ja ter
    corrigido: uma chave que abre um objeto aninhado dentro da entrada
    (`"status_sensores": {`) e' tambem da forma `"..."\s*:\{`, e essa fica mais perto
    do handler do que a chave da entrada. O dicionario devolvia o nome de
    um sub-objeto como se fosse o do intent.
    """
    entradas = {}
    abre_entrada = re.compile(r'(?m)^[ \t]*"([\w:]+)"\s*:\s*\{\s*$')
    for m in re.finditer(r'"handler"\s*:\s*(h_\w+)"', txt):
        ultimo = None
        for am in abre_entrada.finditer(txt, 0, m.start()):
            ultimo = am
        if ultimo:
            entradas[m.group(1)] = ultimo.group(1)
    return entradas


def test_todo_intent_que_escreve_tem_confirmacao():
    """O teste central: quem grava, pergunta."""
    txt, _ = _fontes()

    # O detector e' o do REGISTO, com o de texto como rede. Se o do registo
    # devolver zero, isso e' o detector a falhar (ou o registo vazio), nao o
    # produto a estar limpo — e a rede de texto existe para distinguir as duas
    # coisas em vez de nos dar um falso "tudo bem".
    escribem = _handlers_que_escrevem_do_registro()
    if not escribem:
        escribem = _handlers_que_escrevem(txt)
    assert escribem, (
        "nenhum handler detectado a escrever. O detector esta errado, nao o "
        "codigo — se este teste falha aqui, corrigir o padrao antes de "
        "desconfiar dos intents."
    )

    # Um handler pode ser registado em mais do que uma tabela (INTENTS,
    # INTENTS2, INTENTS_IOT...). Procuramos a flag em qualquer entrada que
    # aponte para ele.
    #
    # MEDIDO 2026-10-04: DUAS versoes deste teste_failed, e ambas por
    # analyse de texto em vez de leitura da estrutura.
    #
    #   v1 — janela de 3000 chars: acusava `h_associar_tarefa`, que tem a
    #        flag a 3007. Dois mil e meio de comentario entre a entrada e
    #        a linha do `handler`.
    #   v2 — `rfind("\n    ")` para achar o `{` da entrada: a indentacao
    #        dentro de uma `params_schema` tambem e' de 4, e o bloco
    #        encontrado era o errado. Acusou os 5 handlers.
    #
    # Nenhuma das versoes e' uma correccao; sao deslocamentos de uma heuristica.
    # A flag vive num DICIONARIO python, e ha um dicionario em memoria que
    # diz a verdade. Parsear `INTENTS` e perguntar e' o runtime a perguntar —
    # e nao pode ficar para tras quando o comentario grows.
    #
    # E tem de ser o `REGISTO`, nao o `INTENTS`. MEDIDO: `sandbox.py:15` faz
    # `from app.ia.registro import REGISTO as INTENTS` — o runtime le o
    # registo agregado (81 entradas), nao o primeiro catalogo (77). Ler o
    # `INTENTS` aqui seria voltar ao mesmo erro um nivel acima: o teste
    # affirmava sobre um objecto que o `sandbox.py` nao consulta.
    def tem_flag(handler: str) -> bool:
        from app.ia.registro import REGISTO

        return any(
            spec.get("requires_confirmation")
            for spec in REGISTO.values()
            if isinstance(spec, dict)
            and callable(spec.get("handler"))
            and spec["handler"].__name__ == handler
        )

    sem = sorted(h for h in escribem if not tem_flag(h))

    assert not sem, (
        "handlers que escrevem sem `requires_confirmation` na tabela: "
        + ", ".join(sem)
        + ".\n\n"
        "Cada um destes grava sem perguntar nada ao produtor. A flag pode "
        "estar no corpo da funcao — se estiver, o `sandbox.py` nao a ve, "
        "porque e' a entrada da tabela que ele le. E' o mesmo erro do "
        "`talhao_id` do Caderno: uma validacao correcta, no sitio errado."
    )


# ─────────────────────────────────────────────────────────────────────────────
# 3. O caso concreto que ja esteve partido
# ─────────────────────────────────────────────────────────────────────────────


def test_o_concluir_tarefa_pergunta_quando_ha_ambiguidade():
    """ "Conclui a pulverização" com tres tarefas pendentes tem de perguntar.

    Com `.first()`, o sistema concluia a primeira e o produtor nunca soube
    que havia outras duas. Concluir a errada e' pior do que nao concluir.
    """
    txt, _ = _fontes()

    m = re.search(r"def\s+h_concluir_tarefa.*?candidatos\s*=\s*list\(", txt, re.S)
    assert m, "h_concluir_tarefa ja nao filtra candidatos"

    depois = txt[m.start() : m.start() + 4000]
    assert re.search(
        r"len\(candidatos\)\s*==\s*1", depois
    ), "h_concluir_tarefa deixou de tratar o caso de candidato unico."
    assert re.search(r"len\(candidatos\)\s*>\s*1", depois), (
        "h_concluir_tarefa nao trata a ambiguidade: com varias tarefas que "
        "casam com o titulo, tem de perguntar qual e' — nunca escolher."
    )


def test_nenhum_handler_escreve_com_o_primeiro_resultado():
    """`.first()` seguido de escrita, sem checar a ambiguidade, e' o padrao.

    A excepcao sao os casos em que o filtro **garante** unicidade — por
    exemplo `filter(pk=...)`. O teste so proibe o `.first()` quando o filtro
    era por nome/texto, que e' onde a ambiguidade aparece.
    """
    txt, _ = _fontes()
    maus = []
    # Procuramos o padrao: filtro por nome + .first() + escrita, no mesmo handler.
    for m in re.finditer(r"^def\s+(h_\w+)\s*\(", txt, re.M):
        nome = m.group(1)
        nxt = txt.find("\ndef ", m.end())
        corpo = txt[m.start() : nxt if nxt != -1 else len(txt)]

        ambiguo = re.search(r"filter\(\s*\w+__\w*(?:icontains|contains)", corpo)
        if not ambiguo:
            continue
        if ".first()" in corpo and re.search(r"\.(save|update|delete)\s*\(", corpo):
            # Ha confirmacao declarada?
            if re.search(r"requires_confirmation|candidatos|len\(", corpo):
                continue
            maus.append(nome)

    assert not maus, (
        "handlers que escolhem por `.first()` um registo filtrado por nome, "
        "sem checar ambiguidade e sem pedir confirmacao: " + ", ".join(sorted(maus))
    )
