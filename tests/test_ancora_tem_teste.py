"""As ancoras `C` que apontam para testes tem de estar registadas aqui.

MEDIDO 2026-10-05 (agente 9). Na auditoria dos `E` promovi 10 celulas a `C` e
escrevi no documento que se apoiam em "83 testes verdes". Esse era um numero
que eu tinha medido **numa corrida** — nada o guardava. Quebrar
`test_caderno_fotos.py` deixava a tabela a dizer `C` com a mesma tranquilidade.

Este ficheiro nao executa os testes (isso e' o trabalho da suite). Garante que
o mapa `ancora -> teste` esta completo e sem lixas: se alguem ancorar uma `C`
nova a um teste novo, este guard falha ate o teste entrar na lista — e entrar
na lista significa que a suite o corre.

Os testes ancorados correm na suite normal do projecto. Aqui so se verifica a
coerencia do mapa.
"""

from __future__ import annotations

import pathlib
import sys
import unittest

RAIZ = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "docs" / "arquitetura" / "sistema" / "comparativo"))

from vereditos import VEREDITOS  # noqa: E402

#: Ficheiros de teste que sustentam pelo menos uma ancora `C`. A suite do
#: projecto corre-os; este guard garante que a lista nao diverge do `VEREDITOS`.
TESTES_ANCORADOS = [
    "tests/test_fila_offline_aceita_escrita.py",
    "tests/test_caderno_fotos.py",
    "tests/test_telemetria_zero_trust.py",
]


def ancoras_em_teste() -> dict[str, list[str]]:
    """{ficheiro de teste: [celsulas `C` que apontam para ele]}"""
    saida: dict[str, list[str]] = {}
    for cid, (estado, evidencia, _nota) in VEREDITOS.items():
        if estado != "C" or not evidencia:
            continue
        ficheiro = evidencia.split(":")[0]
        if "test" not in pathlib.Path(ficheiro).name.lower():
            continue
        saida.setdefault(ficheiro, []).append(cid)
    return saida


class AncorasEmTesteTest(unittest.TestCase):
    def test_toda_ancora_C_em_teste_esta_registada(self):
        for ficheiro, cids in ancoras_em_teste().items():
            with self.subTest(ficheiro=ficheiro):
                celulas = ", ".join(sorted(cids))
                self.assertIn(
                    ficheiro,
                    TESTES_ANCORADOS,
                    f"{celulas} ancorado em {ficheiro}, que nao esta na lista "
                    f"deste guard. Ou a suite o corre e adiciona-se a lista, ou "
                    f"muda-se a ancora para a linha de codigo.",
                )

    def test_a_lista_nao_tem_lixas(self):
        orfaos = [t for t in TESTES_ANCORADOS if t not in ancoras_em_teste()]
        self.assertEqual(
            orfaos,
            [],
            f"estes ficheiros nao sustentam nenhuma ancora `C`: {orfaos}",
        )

    def test_os_ficheiros_da_lista_existem(self):
        for ficheiro in TESTES_ANCORADOS:
            with self.subTest(ficheiro=ficheiro):
                self.assertTrue(
                    (RAIZ / ficheiro).exists(),
                    f"{ficheiro} nao existe — a lista aponta para o vazio",
                )


if __name__ == "__main__":
    unittest.main()
