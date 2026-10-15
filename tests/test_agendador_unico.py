"""
Onda 0.5 — **um agendador, nao dois.**

O problema
----------
O projecto tem **dois** mecanismos para correr a varredura proactiva:

| # | Mecanismo | Como arma | Onde |
|---|---|---|---|
| A | Agendador do Windows (duas tarefas) | `tools/bat/setup_tarefa_proativa.bat` | `AmplIA Varredura Proativa - Manha 0712`, `... Tarde 1712` |
| B | Celery BEAT | `AMPLIA_CELERY_BEAT=1` no ambiente | `app/ia/proativo_tasks.py:274` |

**A e' a escolha documentada** — e o proprio `.bat` argumenta isso, na seccao
*"POR QUE O AGENDADOR E NAO O CELERY"*: broker para um job de segundos e'
infraestrutura a mais, Redis nao tem build oficial no Windows, e cada "o alerta
nao veio" vira "o Redis caiu".

Porque isto ainda e' um risco
----------------------------
Porque **B continua disponivel**. E o perigo nao e' a duplicacao visivel — e' a
duplicacao **invisivel**:

> Se `AMPLIA_CELERY_BEAT=1` estiver ligado **e** as duas tarefas do Windows
> estiverem instaladas, a varredura corre **duas vezes**. O dedup segura o
> alerta duplicado — e **e por isso que o defeito e' PERIGOSO e nao visivel**:
> parece funcionar.

O que este ficheiro faz
-----------------------
1. Prova que **B esta desligado por defeito** (hoje esta; se alguem ligar, o
   teste diz logo).
2. Prova que `AMPLIA_CELERY_BEAT` esta **documentado** no `.env.example` com o
   aviso — para quem o ligar saber que a alternativa ja esta instalada.
3. **Falha se os dois estiverem armados ao mesmo tempo.**

Regra de nao-poluir
-------------------
Se (3) estivesse sempre a falhar — porque os dois *ficheiros* existem — seria o
defeito que este projecto ja Pagou uma vez: um teste vermelho por uma divida
conhecida habitua a ler-se a vermelho **sem ler**. Por isso (3) falha **so em
conflito real**, e hoje passa. Os testes (1) e (2) sao os que mordem hoje.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_EXAMPLE = BASE_DIR / ".env.example"

# Os nomes exactos, como estao em `tools/bat/setup_tarefa_proativa.bat` (set T1/T2).
TAREFAS_WINDOWS = (
    "AmplIA Varredura Proativa - Manha 0712",
    "AmplIA Varredura Proativa - Tarde 1712",
)

CELERY_GATE = "AMPLIA_CELERY_BEAT"


def _env_exemplo_texto() -> str:
    return ENV_EXAMPLE.read_text(encoding="utf-8") if ENV_EXAMPLE.exists() else ""


def _celery_armado_no_ambiente() -> bool:
    return os.environ.get(CELERY_GATE, "") == "1"


def _tarefas_windows_instaladas() -> list[str]:
    """Nomes das tarefas AmplIA que o Windows tem agendadas. Vazio se nao houver."""
    if not sys.platform.startswith("win"):
        return []
    try:
        r = subprocess.run(
            ["schtasks", "/query", "/fo", "CSV", "/nh"],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except Exception:
        return []
    if r.returncode != 0:
        return []
    encontradas = []
    for linha in r.stdout.splitlines():
        for tarefa in TAREFAS_WINDOWS:
            if tarefa.lower() in linha.lower():
                encontradas.append(tarefa)
    return sorted(set(encontradas))


# ─────────────────────────────────────────────────────────────────────────────


def test_o_celery_beat_esta_desligado_por_defeito():
    """O caminho B tem de estar OFF sem ninguem mandar.

    Se este teste falhar, alguem ligou `AMPLIA_CELERY_BEAT=1` no ambiente de
    producao sem desligar o Agendador — e as duas varreduras correm.
    """
    assert not _celery_armado_no_ambiente(), (
        f"{CELERY_GATE}=1 no ambiente deste processo. O `BEAT_SCHEDULE` esta "
        "armado (app/ia/proativo_tasks.py:274). Se as tarefas do Windows "
        "tambem estiverem instaladas, a varredura corre duas vezes. Escolhe UM: "
        "ou desligas o Celery, ou corres `setup_tarefa_proativa.bat --remove`."
    )


def test_amplia_celery_beat_esta_documentado_no_env_exemplo():
    """Quem ligar a porta B tem de encontrar a advertencia de la.

    Sem isto, `AMPLIA_CELERY_BEAT=1` e' um flag sem documentacao num projecto
    que faz do "nao prometer o que nao se mede" a doutrina. E a forma mais
    barata de evitar o conflito: quem liga, le o aviso antes.
    """
    texto = _env_exemplo_texto()
    assert CELERY_GATE in texto, (
        f"`{CELERY_GATE}` nao aparece no .env.example. E' o flag que arma o "
        "BEAT_SCHEDULE (app/ia/proativo_tasks.py:274) e nao esta documentado "
        "em lado nenhum. Declara-o com valor default desligado e o aviso."
    )

    linha = next(
        (ln for ln in texto.splitlines() if ln.strip().startswith(CELERY_GATE)),
        "",
    )
    # O aviso pode estar **acima** ou **abaixo** da declaracao — e num ficheiro
    # .env a convencao e' comentario acima. Por isso le-se a janela toda em
    # volta, e nao so o que vem a seguir. (A primeira versao deste teste so
    # olhava para a frente e reprovava um .env.example correcto.)
    pos = texto.find(CELERY_GATE)
    janela = texto[max(0, pos - 1200) : pos + 800]
    tem_aviso = any(
        termo in janela.lower()
        for termo in ("agendador", "windows", "setup_tarefa_proativa", "duas vezes")
    )
    assert tem_aviso, (
        f"`{CELERY_GATE}=1` esta no .env.example mas sem aviso de que o "
        "Agendador do Windows ja faz a mesma varredura "
        "(`tools/bat/setup_tarefa_proativa.bat`, tarefas "
        f"{TAREFAS_WINDOWS[0]!r} e {TAREFAS_WINDOWS[1]!r}). Liga os dois e a "
        "varredura corre duas vezes — e o dedup esconde isso. Acrescenta o aviso "
        f"a proxima de {CELERY_GATE}."
    )
    assert (
        linha
    ), f"a linha de {CELERY_GATE} no .env.example nao esta no inicio da linha"


@pytest.mark.skipif(
    not sys.platform.startswith("win"), reason="o Agendador e' especifico do Windows"
)
def test_nao_ha_dois_agendadores_armados_ao_mesmo_tempo():
    """O guarda de conflito. **Falha so quando os dois estao de facto armados.**

    Hoje passa, e tem de passar: os dois *ficheiros* sempre existiram, e um
    teste que estivesse sempre vermelho seria o ruido que entrena a ignorar.
    """
    celery = _celery_armado_no_ambiente()
    windows = _tarefas_windows_instaladas()

    if celery and windows:
        pytest.fail(
            "DOIS AGENDADORES ARMADOS. "
            f"Celery BEAT ({CELERY_GATE}=1) e {len(windows)} tarefa(s) do "
            f"Agendador do Windows ({'; '.join(windows)}). A varredura proativa "
            "corre duas vezes por dia. O dedup segura o alerta duplicado, e por "
            "isso isto nao se ve — parece funcionar. Escolhe UM:\n"
            "  * Agendador do Windows (o .bat argumenta porque e' o certo): "
            "`tools\\bat\\setup_tarefa_proativa.bat --remove` e NAO ligues o "
            f"{CELERY_GATE}.\n"
            "  * Celery BEAT: remove as tarefas do Windows e liga o flag."
        )

    # -documenta o estado, para quem le a falha de outro teste saber qual era
    estado = f"celery={celery} windows={len(windows)}"
    assert celery != bool(windows) or not (
        celery and windows
    ), f"estado de agendadores incoerente: {estado}"
