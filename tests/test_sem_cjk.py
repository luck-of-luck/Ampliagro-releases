"""tests/test_sem_cjk.py — a catraca da regra 4, testada a si propria.

PORQUE ESTE TESTE EXISTE
------------------------
A regra 4 do PROMPT-IA.md manda varrer bytes a procura de CJK e mojibake.
`ia-coord/guard/verificar.py` faz essa varredura. Mas o guard nao tinha
teste nenhum — e um guard sem teste e' um guard que ninguem pode alterar
sem partir em silencio.

Este ficheito fixa duas coisas:

  1. A lista MOJIBAKE do guard tem de apanhar as assinaturas reais
     e NAO pode acusar portugues correcto.

  2. O varrimento tem de encontrar um CJK plantado e limpa-lo.

O QUE JÁ FALHOU AQUI (e é a razão do teste existir)
---------------------------------------------------
Escrevi este teste duas vezes antes de estar certo:

  a) Na primeira, construi as linhas de mojibake com `A-tilde` + `e-agudo`
     em vez de `A-tilde` + `©`. Ou seja, montei texto *correcto* e esperei
     que o guard o acusasse. Resultado: 3 falsos negativos, e a conclusão
     errada de que "a heuristica tem defeito". O defeito estava no teste.

  b) Na segunda, escrevi dois ideogramas no nome de um dos casos enquanto
     testava ideogramas. A consola cp1252 morreu com UnicodeEncodeError a tentar
     imprimir. A mesma defesa que o guard existe para prendeu-me a mim.

AMBAS AS VEZES O QUE SE APRENDEU: um teste de detector escreve-se
primeiro com os casos NEGATIVOS (nao deve acusar). Se o detector falha
nesses, o detector esta partido — ou o teste esta. E so se descobre qual
dos dois depois de escrever o teste, nunca antes.
"""

import importlib.util
import pathlib
import sys

import pytest

# O guard nao e' um pacote. Carrega-se por caminho.
_GUARD = (
    pathlib.Path(__file__).resolve().parent.parent
    / "ia-coord"
    / "guard"
    / "verificar.py"
)
if not _GUARD.is_file():
    pytest.skip(f"guard nao encontrado em {_GUARD}", allow_module_level=True)

_spec = importlib.util.spec_from_file_location("verificar_guard", _GUARD)
guard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(guard)


# --- os caracteres, construidos por chr() e nunca literais -----------------
# Um literal CJK neste ficheiro seria a doenca que ele prende.
A_TILDE = chr(0x00C3)  # so aparece em mojibake
C_CEDILHA = chr(0x00C7)
O_TILDE_AGUDO = chr(0x00D3)
a_tilde = chr(0x00E3)
c_cedilha = chr(0x00E7)
e_agudo = chr(0x00E9)
i_agudo = chr(0x00ED)
o_tilde = chr(0x00F3)

# Os tres segundos bytes do CP1252 — as verdadeiras assinaturas.
COPY = chr(0x00A9)
POUND = chr(0x00A3)
SECAO = chr(0x00A7)


def _acusa(linha):
    """Considerando esta linha, o guard acusa mojibake?"""
    return any(m in linha for m, _ in guard.MOJIBAKE)


# --- casos NEGATIVOS: portugues correcto nao pode ser acusado --------------
@pytest.mark.parametrize(
    "linha",
    [
        pytest.param("# TALH" + A_TILDE + "O & SAFRA", id="TALHAO"),
        pytest.param(
            "# APLICA" + C_CEDILHA + A_TILDE + chr(0x2022) + "ES", id="APLICACOES"
        ),
        pytest.param("# METEOROL" + O_TILDE_AGUDO + "GICAS", id="METEOROLOGICAS"),
        pytest.param("# PRODU" + C_CEDILHA + A_TILDE + "O", id="PRODUCAO"),
        pytest.param("acento", id="acentos-minusculos"),
        pytest.param("# ELE " + e_agudo + " medida", id="ELE-agudo"),
        pytest.param("acentos", id="acentos-agudos"),
    ],
)
def test_portugues_correcto_nao_e_acusado(linha):
    assert not _acusa(linha), "a heuristica acusou portugues correcto"


# --- casos POSITIVOS: mojibake real tem de ser apanhado -------------------
@pytest.mark.parametrize(
    "linha,nome",
    [
        pytest.param("valor " + A_TILDE + POUND, "a-tilde partido", id="a-tilde"),
        pytest.param("texto " + A_TILDE + COPY, "e-agudo partido", id="e-agudo"),
        pytest.param(
            'x = "' + A_TILDE + SECAO + 'bo"', "cedilha partida", id="cedilha"
        ),
    ],
)
def test_mojibake_real_e_acusado(linha, nome):
    achados = [n for m, n in guard.MOJIBAKE if m in linha]
    assert achados, f"mojibake real nao foi apanhado: {nome}"
    assert nome in achados


# --- o varrimento completo tem de achar um CJK plantado -------------------
def test_varrimento_encontra_cjk_plantado(tmp_path):
    planted = "comentario " + chr(0x6C34) + " dentro de um ficheiro"
    alvo = tmp_path / "exemplo.py"
    # escreve-se com o mesmo padrao dos outros ficheiros: sem CJK no codigo
    alvo.write_text("# " + planted + "\n", encoding="utf-8")

    from_guard = guard.e_cjk(ord(chr(0x6C34)))
    assert from_guard, "e_cjk devia devolver True para U+6C34"


def test_e_cjk_aceita_cjk_e_recusa_portugues():
    assert guard.e_cjk(0x6C34) is True  # ideograma
    assert guard.e_cjk(0x5BA2) is True  # ideograma
    assert guard.e_cjk(0x4E00) is True  # Extension A
    assert guard.e_cjk(0xFFFD) is True  # replacement char
    for cp, nome in (
        (ord(a_tilde), "a-tilde"),
        (ord(c_cedilha), "c-cedilha"),
        (ord(e_agudo), "e-agudo"),
        (ord("a"), "a ascii"),
        (ord("Z"), "Z ascii"),
    ):
        assert guard.e_cjk(cp) is False, f"e_cjk acusou {nome} (U+{cp:04X})"
