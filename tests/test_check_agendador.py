"""Nao pode haver dois agendadores armados ao mesmo tempo.

O DEFECTO QUE ESTE COMANDO FECHA
================================
MEDIDO 2026-10-04 pelo `5.md` §2.1, e é a melhor frase desse documento:

    armados os dois, a varredura corre duas vezes; o dedup segura o alerta
    duplicado — "e por isso o defeito e' PERIGOSO, nao visivel: parece
    funcionar".

Há dois agendadores vivos, e ambos apontam para as mesmas horas:

  * **Celery beat** — `app/ia/proativo_tasks.py:274` só arma `BEAT_SCHEDULE`
    com `AMPLIA_CELERY_BEAT=1`.
  * **Agendador do Windows** — `tools/bat/setup_tarefa_proativa.bat`
    instala duas tarefas (07:12 e 17h12) que correm `varrer()`.

O problema não é nenhum deles estar armado. É **ninguém saber qual está
armado**. E como o dedup segura o alerta duplicado, o sintoma é "a IA avisa
duas vezes" — semanas depois, e ninguém liga as duas coisas.

POR QUE ISTO É UM COMANDO E NÃO UM TESTE
=======================================
Porque o estado depende do **ambiente**, não do código. Um teste correria
com um `schtasks` que responde o que lhe apetece. O comando é para alguém
chegar à máquina do produtor e perguntar.

Por isso o teste mede a **lógica de decisão** (a partir de estados
simulados) e o comando mede o **estado real**. São complementares, e nenhum
dos dois chega sozinho.
"""

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
CMD = RAIZ / "app" / "management" / "commands" / "check_agendador.py"
BAT = RAIZ / "tools" / "bat" / "setup_tarefa_proativa.bat"

sys.path.insert(0, str(RAIZ / "app" / "management" / "commands"))


def _modulo():
    """Importa o modulo do command sem passar pelo Django."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("check_agendador_mod", CMD)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def mod():
    return _modulo()


@pytest.fixture
def sem_celery(monkeypatch):
    monkeypatch.delenv("AMPLIA_CELERY_BEAT", raising=False)


@pytest.fixture
def com_celery(monkeypatch):
    monkeypatch.setenv("AMPLIA_CELERY_BEAT", "1")


# ─────────────────────────────────────────────────────────────────────────────
# 1. A ligação ao .bat — que é onde um rename silencioso estraga tudo
# ─────────────────────────────────────────────────────────────────────────────


def test_os_nomes_batem_com_o_script(mod):
    """Os nomes das tarefas no comando e no `.bat` têm de ser o mesmo string.

    MEDIDO 2026-10-05. Este comando mantém uma cópia dos nomes que
    `setup_tarefa_proativa.bat` define em `set "T1=..."` / `set "T2=..."`.

    Uma cópia é um segundo sítio para a verdade, e o `9.md` §0 documenta o
    que acontece quando há dois: *"eis porque a regra pétrea está escrita no
    código"* — e, pela inversa, é por isso que uma verdade duplicada tem de
    ter um teste que compare as duas. Se alguém renomear a tarefa no `.bat`
    e não aqui, `schtasks /query` devolve "não existe" para sempre e o
    comando diria, com toda a confiança, que o Agendador está desligado.
    """
    bat = BAT.read_text(encoding="utf-8", errors="replace")

    # Os nomes declarados no .bat: `set "T1=Nome"`.
    # O espaco depois de `T1` e' opcional no `set` do cmd.exe, por isso o
    # padrao aceita os dois. A primeira versao deste teste exigia o espaco e
    # deu `assert set()` contra um `.bat` correcto — que e' o pior tipo de
    # falha de teste: protege-se de si mesmo.
    declarados = set(re.findall(r'set\s+"T\d\s*=\s*(.+?)"', bat))
    assert declarados, (
        'nao encontrei `set "T1=..."` em setup_tarefa_proativa.bat. O formato '
        "mudou e este teste ja nao verifica o que diz verificar."
    )
    declarados = {d.strip().strip('"') for d in declarados}

    # Os nomes no comando.
    do_comando = set(mod.TAREFAS_WINDOWS)

    assert do_comando == declarados, (
        "os nomes das tarefas divergem:\n"
        "  so no .bat   : %s\n"
        "  so no comando: %s\n\n"
        "Um `schtasks /query` com o nome errado devolve 'nao existe' e o "
        "comando reporta o Agendador como desligado — com toda a confiança, "
        "e errado." % (sorted(declarados - do_comando), sorted(do_comando - declarados))
    )


# ─────────────────────────────────────────────────────────────────────────────
# 2. A decisão
# ─────────────────────────────────────────────────────────────────────────────


def test_nenhum_armado_e_saudavel_como_estado(mod, monkeypatch):
    """Nenhum dos dois: o estado que o comando tem de dizer em voz alta.

    Este e' o caso mais importante, e o que o comando original nao dizia.
    Em contentor efemero sem Celery nem Agendador, **a varredura proativa
    nao corre** — e o manifesto §V vende o "Caminho A" como o caminho que
    "age mesmo com o painel offline".
    """
    monkeypatch.setattr(mod, "tarefas_windows_armadas", lambda: [])
    assert mod.relatorio() == {
        "celery": False,
        "windows": [],
        "windows_consultavel": True,
        "ambos": False,
    }


def test_os_dois_armados_e_o_estado_invalido(mod, monkeypatch):
    """Este e' o defeito. Os dois armados tem de ser detectado como tal."""
    monkeypatch.setattr(
        mod,
        "tarefas_windows_armadas",
        lambda: list(mod.TAREFAS_WINDOWS),
    )
    monkeypatch.setenv("AMPLIA_CELERY_BEAT", "1")

    r = mod.relatorio()
    assert r["celery"] is True
    assert r["ambos"] is True, "os dois armados tem de ser detectado"


def test_um_so_armado_e_saudavel(mod, monkeypatch):
    for celery, win, esperado in (
        (True, [], "celery"),
        (False, ["A", "B"], "windows"),
    ):
        monkeypatch.setattr(
            mod,
            "tarefas_windows_armadas",
            lambda w=win: list(w) if w else [],
        )
        if celery:
            monkeypatch.setenv("AMPLIA_CELERY_BEAT", "1")
        else:
            monkeypatch.delenv("AMPLIA_CELERY_BEAT", raising=False)

        r = mod.relatorio()
        assert r["ambos"] is False, "%s / %s nao devia ser 'ambos'" % (celery, win)
        assert r["celery"] is celery
        assert bool(r["windows"]) == bool(win)
        assert esperado in ("celery", "windows")


def test_sem_schtasks_nao_e_o_mesmo_que_desligado(mod, monkeypatch):
    """`None` (nao consultavel) ≠ `[]` (nenhuma instalada).

    Num contentor Linux nao ha Agendador do Windows. Dizer "desligado" seria
    verdade enganadora: o produtor de contentor **nao tem** agendador, e isso
    muda a decisao. `windows_consultavel` existe para nao confundir as duas
    coisas.
    """
    monkeypatch.setattr(mod, "tarefas_windows_armadas", lambda: None)
    monkeypatch.delenv("AMPLIA_CELERY_BEAT", raising=False)

    r = mod.relatorio()
    assert r["windows"] is None
    assert r["windows_consultavel"] is False
    # E o mais importante: nunca `ambos`, porque nao sabemos.
    assert r["ambos"] is False


# ─────────────────────────────────────────────────────────────────────────────
# 3. A saida — porque um diagnostico que nao se le nao e' um diagnostico
# ─────────────────────────────────────────────────────────────────────────────


def test_o_texto_dos_dois_armados_diz_que_parECE_FUNCIONAR(mod, monkeypatch):
    """A mensagem tem de conter a razao do perigo.

    Um operador que le "os dois agendadores estao armados" e desliga o Celery
    perde a replicas. A frase que o convence e' outra: *isto nao da erro, por
    isso parece funcionar*.
    """
    monkeypatch.setattr(
        mod,
        "tarefas_windows_armadas",
        lambda: list(mod.TAREFAS_WINDOWS),
    )
    monkeypatch.setenv("AMPLIA_CELERY_BEAT", "1")

    from io import StringIO

    from django.core.management import call_command

    out = StringIO()
    with pytest.raises(SystemExit) as e:
        call_command("check_agendador", stdout=out)

    assert e.value.code == 1, (
        "os dois armados tem de sair != 0. Um comando de diagnostico que "
        "devolve 0 num estado invalido e' pior do que nao existir: o CI passa."
    )
    texto = out.getvalue()
    assert "INVALIDO" in texto
    assert "PARECE FUNCIONAR" in texto, (
        "a mensagem tem de dizer porquê que isto e' perigoso: o dedup segura "
        "o duplicado, por isso nao ha erro visivel"
    )


def test_a_variavel_consultada_e_a_que_o_codigo_le(mod):
    """O nome da variável tem de ser o de `proativo_tasks.py:274`.

    Um diagnostico que le `AMPLIA_CELERY` quando o codigo le
    `AMPLIA_CELERY_BEAT` reporta o estado ao contrario — que e' pior que nao
    reportar nada.
    """
    proativo = (RAIZ / "app" / "ia" / "proativo_tasks.py").read_text(
        encoding="utf-8", errors="replace"
    )
    assert mod.VAR_CELERY in proativo, (
        "a variavel %r nao aparece em proativo_tasks.py — o comando esta a "
        "perguntar ao ambiente por outra coisa" % mod.VAR_CELERY
    )


# ─────────────────────────────────────────────────────────────────────────────
# 4. O comando corre
# ─────────────────────────────────────────────────────────────────────────────


def test_o_command_existe_e_tem_help():
    """Um command sem `help` nao aparece na lista de comandos do Django."""
    txt = CMD.read_text(encoding="utf-8")
    assert "class Command(BaseCommand)" in txt
    assert "help =" in txt
