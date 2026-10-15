"""Guard de QUALIDADE da ancora: um `C` tem de apontar para codigo.

MEDIDO 2026-10-05 (agente 9). Este guard existe porque a auditoria dos 16 `E`
achou 9 referencias que apontavam para coisas que nao implementam capacidade:
docstrings, uma linha em branco, listas de `import`, um dicionario de permissoes
e **dados de demo**. O teste anterior so garantia que a linha existia — e uma
docstring existe.

Este e' o guard que fecha essa porta: uma ancora `C` que caia numa docstring, num
comentario, numa linha em branco ou num `import` faz o teste falhar.

Deteccao de docstring por `ast`, nao por texto: tres aspas pode ser um
delimitador OU o conteudo de uma string normal, e so a arvore sabe qual.
"""

from __future__ import annotations

import ast
import io
import pathlib
import re
import sys
import unittest

RAIZ = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "docs" / "arquitetura" / "sistema" / "comparativo"))

from vereditos import VEREDITOS  # noqa: E402


def linhas_de_docstring(ficheiro: pathlib.Path) -> set[int]:
    """Numeros de linha cobertos por uma docstring, segundo o `ast`.

    Cobre docstrings de modulo, classe e funcao — os tres sitios onde uma
    pessoa escreve em portugues sobre o que o codigo faz, em vez de o fazer.
    """
    try:
        arvore = ast.parse(ficheiro.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        return set()

    cobertura: set[int] = set()
    for node in ast.walk(arvore):
        if not isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        corpo = getattr(node, "body", [])
        if not corpo:
            continue
        primeiro = corpo[0]
        if (
            isinstance(primeiro, ast.Expr)
            and isinstance(primeiro.value, ast.Constant)
            and isinstance(primeiro.value.value, str)
        ):
            ini = primeiro.lineno
            fim = getattr(primeiro, "end_lineno", primeiro.lineno) or primeiro.lineno
            cobertura.update(range(ini, fim + 1))
    return cobertura


def eh_comentario(linha: str, ext: str) -> bool:
    s = linha.strip()
    if not s:
        return True  # linha em branco tambem nao prova nada
    if ext == ".py":
        return s.startswith("#")
    if ext in (".js", ".cjs"):
        return s.startswith(("//", "*", "/*"))
    if ext == ".html":
        return s.startswith("<!--")
    return False


def eh_import(linha: str, ext: str) -> bool:
    s = linha.strip()
    if ext == ".py":
        return s.startswith(("import ", "from ")) or re.match(r"^\w+\s*=\s*.*,$", s) is not None
    if ext in (".js", ".cjs"):
        return s.startswith("import ") or s.startswith("export ") and " from " in s
    return False


class AncoraTemCodigoTest(unittest.TestCase):
    """Nenhuma ancora `C` pode estar em prosa, comentario ou import."""

    def test_nenhuma_ancora_C_aponta_para_docstring_ou_comentario(self):
        suspeitas: list[str] = []
        for cid, (estado, evidencia, nota) in VEREDITOS.items():
            if estado != "C" or not evidencia:
                continue
            rel, _, ln_txt = evidencia.rpartition(":")
            ln = int(ln_txt)
            p = RAIZ / rel
            linhas = p.read_text(encoding="utf-8", errors="replace").splitlines()
            alvo = linhas[ln - 1]
            ext = p.suffix

            if ln in linhas_de_docstring(p):
                suspeitas.append(
                    f"{cid}: {rel}:{ln} esta DENTRO de uma docstring — "
                    f"prosa nao implementa capacidade"
                )
                continue
            if eh_comentario(alvo, ext):
                suspeitas.append(f"{cid}: {rel}:{ln} e' comentario/linha em branco")
                continue
            if eh_import(alvo, ext):
                suspeitas_msg = f"{cid}: {rel}:{ln} e' um import — prova que o nome existe"
                suspeitas.append(suspeitas_msg)
                continue

            # Uma entrada de dicionario ("ndvi-view": [...]) prova que o nome
            # existe, nao que a capacidade existe. Foi assim que F07 e O07
            # ficaram ancorados antes da auditoria.
            if re.match(r'^["\'][^"\']+["\']\s*:', alvo.strip()):
                suspeitas.append(
                    f"{cid}: {rel}:{ln} e' uma entrada de dicionario — "
                    f"prova que o nome existe, nao a capacidade"
                )
                continue

            # `E` nao e' ancorado em ficheiro de teste. Se um `C` aponta para
            # um teste, esse teste TEM de existir com uma assercao, nao uma
            # docstring que explica o que ele testa.
            if "test" in p.name.lower() and not re.search(r"\b(assert|def test_)", alvo):
                suspeitas.append(
                    f"{cid}: {rel}:{ln} aponta para um ficheiro de teste mas a "
                    f"linha nao e' uma assercao: {alvo.strip()[:60]!r}"
                )

        self.assertEqual(
            suspeitas,
            [],
            "ancoras `C` sem codigo por tras:\n  " + "\n  ".join(suspeitas),
        )

    def test_as_ancoras_E_tem_justificacao_escrita(self):
        """Um `E` sem nota explaining *why* it is weak is just an `N` with shame."""
        sem_nota = [
            cid for cid, (_e, _ev, nota) in VEREDITOS.items()
            if nota.strip().lower() in ("", "e", "-")
        ]
        self.assertEqual(sem_nota, [], f"`E` sem nota: {sem_nota}")

    def test_nenhum_N_tem_ancora(self):
        """`N` significa ausente. Se ha uma linha que aponta, `N` esta errado."""
        com_ancora = [
            (cid, ev) for cid, (estado, ev, _n) in VEREDITOS.items()
            if estado == "N" and ev
        ]
        self.assertEqual(
            com_ancora,
            [],
            f"`N` com evidencia: {com_ancora}. Ou a capacidade existe (-> C/E), "
            "ou a evidencia e' enganadora (verificar e remover).",
        )


if __name__ == "__main__":
    unittest.main()