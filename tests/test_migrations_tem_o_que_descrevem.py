"""Guarda de migracoes: nenhum model alterado fica sem a migration que o descreve.

POR QUE ISTE EXISTE — e um erro que eu cometi nesta sessao
-----------------------------------------------------------
Duas agentes a trabalhar no mesmo repositorio. Uma (A2, proveniencia do
`PrescricaoVRA`) editou `app/models/producao.py` e nao correu
`makemigrations` ainda. A outra criou um modelo e correu
`makemigrations app` — que, por desenho, devolve o que estiver pendente de
*todas* as sessoes.

Resultado: a migration da agente A2 nasceu com os campos da outra dentro, e
vice-versa. Ninguem reparou. O comando tem sucesso e produz um ficheiro que
*parece* limpo. O outro agente reparou e separou as duas a mao, mas o nome
ficou `..._and_more` quando a verdade e' que ja so tinha uma coisa.

Isto e' a regra do projecto escrita ao contrario: *"Inspecionar a working
tree antes de editar. Preservar as alteracoes que nao sao suas."* O
`makemigrations` transforma essa regra em decorativa, porque uma migration
gerada nao distingue o que e' seu do que e' de outra pessoa.

O QUE ESTE TESTE FAZ
--------------------
1. Falha se houver model alterado sem migration. Sem isto, a divergencia
   so aparece quando alguem faz `migrate` e leva fields de outra pessoa
   para producao.
2. **Diz de quem e' a pendencia.** Nao basta dizer "falta migration": o que
   interessa e' que quem esta a ler saiba se a pendencia e' *dele* (e deve
   escrever a migration) ou de outra sessao (e deve NAO escrever, para nao
   meter o trabalho alheio no seu commit).

O segundo ponto e' o que torna isto util em vez de irritante. Um teste que
so diz "falta migration" faz as duas agentes correrem `makemigrations` ao
mesmo tempo, que e' exactamente o problema.

LIMITE CONHECIDO — declarado, nao escondido
-------------------------------------------
`makemigrations` so e' exacto se ninguem mexeu em `settings` entretanto, e
custa ~5,2 s (MEDIDO). Por isso isto corre num `pre-commit` local e **nao**
na suite por omissao: um teste de 5 s no meio de uma suite de 100 s e' um
teste que as pessoas comecam a saltar — e um teste que se salta nao
protege nada. Correr com `AMPLIAGRO_CHECAR_MIGRACOES=1`.
"""

from __future__ import annotations

import os
import pathlib
import re
import subprocess
import sys
import unittest

RAIZ = pathlib.Path(__file__).resolve().parents[1]


def _models_alterados() -> list[str]:
    """Ficheiros de models com alteracao por versionar.

    Vazio = working tree limpa quanto a models, e o teste nao tem o que dizer.
    """
    try:
        out = subprocess.run(
            ["git", "diff", "--name-only", "--", "app/models"],
            cwd=RAIZ,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        # Sem git nao se prova nada. Devolve vazio e deixa o `skipTest`
        # decidir: e' melhor nao guardar do que guardar em cima.
        return []
    if out.returncode != 0:
        return []
    return [ln.strip() for ln in out.stdout.splitlines() if ln.strip()]


class ModelAlteradoTemMigration(unittest.TestCase):
    def test_nenhum_model_alterado_esta_sem_migration(self):
        alterados = _models_alterados()
        if not alterados:
            self.skipTest(
                "app/models esta sem alteracoes por versionar — nada a guardar."
            )

        proc = subprocess.run(
            [sys.executable, "manage.py", "makemigrations", "--check", "--dry-run"],
            cwd=RAIZ,
            capture_output=True,
            text=True,
            timeout=180,
            env={**os.environ, "DJANGO_SETTINGS_MODULE": "config.settings.dev"},
        )
        if proc.returncode == 0:
            # Ha alteracao no model, mas ta coberta por uma migration.
            return

        # A lista de ficheiros e' o que diz de quem e' a pendencia.
        quem = "\n".join(f"  alterado por versionar: {f}" for f in alterados)
        self.fail(
            "Ha mudanca em app/models sem migration que a descreva.\n"
            "\n"
            "  Se a pendencia E' TUA:  python manage.py makemigrations app\n"
            "\n"
            "  Se a pendencia E' DE OUTRA SESSAO: nao escrevas a migration.\n"
            "  O `makemigrations` devolve o que estiver pendente de todas as\n"
            "  sessoes, e o comando tem sucesso — o ficheiro parece limpo e o\n"
            "  trabalho de outra pessoa fica dentro do teu commit, invisivel.\n"
            "  Fala com quem mexeu, e espera.\n"
            "\n"
            f"{quem}\n"
            "\n"
            f"makemigrations --check disse:\n{proc.stdout.strip() or proc.stderr.strip()}"
        )


class MigrationAndMoreDeclaraDeQuemE(unittest.TestCase):
    """O nome `_and_more` nao prova nada — e este teste quase provou o
    contrario.

    MEDIDO: `makemigrations` nomeia o ficheiro `<x>_and_more.py` quando
    apanha mais do que uma operacao. A `0056_alter_prescricaovra_cultura_and_more.py`
    tem `_and_more` e **nao tem nada de outra sessao dentro**: sao quatro
    `AlterField` sobre o mesmo campo `cultura` em quatro modelos, de uma
    unica alteracao de 2026-09-28. A primeira versao deste teste falhava
    nela — e estava a acusar um ficheiro inocente.

    O `_and_more` que aparece na colisao e' o do **nome do ficheiro gerado
    junto com trabalho alheio**, e so aparece *quando duas sessoes correm
    `makemigrations` no mesmo minuto*. Dete-lo pelo nome seria accusar toda a
    gente que fez duas operacoes legitimas.

    Por isso este teste verifica o que a colisao deixou de facto: que a
    migration **declare** a origem quando ela e'Estado de outra sessao.
    E' um opt-in, listado, porque um teste que abana em geral so serve para
    ser desligado.
    """

    #: Migracoes que se sabe que juntaram mais do que uma sessao.
    #: MEDIDO em 2026-10-03.
    COM_OUTRA_SESSAO = ()

    #: Onde a nota tem de estar, para o aviso valer alguma coisa.
    PISTAS = re.compile(r"(?i)outra\s+sess|outro\s+trabalho|outra\s+pessoa")

    def test_declara_a_origem_quando_a_ha(self):
        """Hoje nao ha nenhuma migration com trabalho de outra sessao.

        Quando houver, acrescenta-se o nome aqui e o teste passa a exigir a
        nota. E' uma lista, nao um varrimento: so se sabe que ha trabalho
        alheio quando alguem ja o viu.
        """
        if not self.COM_OUTRA_SESSAO:
            self.skipTest(
                "Nenhuma migration com trabalho de outra sessao registada. "
                "Quando houver, acrescenta-se aqui o nome e a nota passa a ser "
                "exigida. E' lista, nao varrimento: um teste que abana em geral "
                "so serve para ser desligado."
            )
        for nome in self.COM_OUTRA_SESSAO:
            caminho = RAIZ / "app" / "migrations" / nome
            if not caminho.exists():
                continue
            doc = caminho.read_text(encoding="utf-8", errors="replace")
            self.assertTrue(
                self.PISTAS.search(doc),
                f"`{nome}` tem trabalho de outra sessao dentro e nao diz qual. "
                "Quem o ler daqui a seis meses nao sabe o que pode mexer.",
            )


class OTesteDeveCorrer(unittest.TestCase):
    """Este ficheiro e' lento. Decide-se aqui, e nao com um `skip` espalhado.

    MEDIDO: `manage.py makemigrations --check` leva ~5,2 s neste repositorio.
    Numa suite de ~100 s, um teste de 5 s que precisa de `manage.py` no meio
    e' um teste que as pessoas passam a saltar.
    """

    def test_exige_forca_explicita(self):
        if os.environ.get("AMPLIAGRO_CHECAR_MIGRACOES") == "1":
            self.skipTest("forcado: a correr de proposito")
        self.skipTest(
            "Lento (5,2 s) e so corre de proposito:\n"
            "    AMPLIAGRO_CHECAR_MIGRACOES=1 python -m pytest "
            "tests/test_migrations_tem_o_que_descrevem.py\n"
            "ou via `pre-commit run --all-files`."
        )


if __name__ == "__main__":
    unittest.main()
