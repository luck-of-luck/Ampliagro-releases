"""A tool `amplia_estado_sistema` mede; nao adivinha.

O QUE ESTES TESTES TRAVAM
==========================
Cada um fixa uma das tres promessas que a tool faz na descricao:

  1. **Mede, nao promete.** Um item que nao deu para ler vem `ok: null`
     com o motivo. Nunca `true`. Um verificador que dissesse "tudo bem"
     sem ter lido nada seria o mesmo bug do painel que dizia "IoT: 4" com
     8 dispositivos, ao contrario — e mais perigoso, porque um painel
     mente sobre um numero e um verificador mente sobre um TODO.

  2. **Os detector de mojibake nao acusa portugues.** `Ã` e `Â` sao
     letras portuguesas (`avô`, `irmã`, `João`). O detector usa controlo
     C1 (U+0080-U+009F, que nao existe em texto nenhum) e o par `Ãƒ`.
     Sem esse cuidado, acusaria 4069 falsos positivos num so ficheiro —
     que foi o que aconteceu na primeira versao.

  3. **Aponta para a morada.** Cada item diz ONDE foi lido, para quem quiser
     confirmar sem repetir a medicao.

O QUE ESTES TESTES NAO FAZEM
============================
Nao correm o servidor nem medem o dashboard. Verificam o comportamento do
verificador sobre entradas que existem e entradas que nao — que e' o que
se pode fixar sem um servidor a correr.
"""

import pathlib
import re
import unittest

from app.amplia_mcp import NOMES_CATALOGO, TOOLS_CATALOGO, executar_catalogo
from app.amplia_mcp.estado import (
    _AE_F,
    _C1,
    VERIFICACOES,
    estado_do_sistema,
)

RAIZ = pathlib.Path(__file__).resolve().parents[1]


class ToolExisteTest(unittest.TestCase):
    def test_a_esta_registada_como_ferramenta_de_catalogo(self):
        """Tem de ser de CATALOGO, e nao de accao.

        Catalogo e' leitura de codigo: nao passa pelo sandbox e nao deixa
        linha na trilha de auditoria. Uma leitura de estado que entrasse
        pelo sandbox ia encher a trilha de ruido — e a trilha serve para
        saber o que a IA FEZ, nao o que leu.
        """
        self.assertIn("amplia_estado_sistema", NOMES_CATALOGO)
        self.assertIn(
            "amplia_estado_sistema",
            [t["name"] for t in TOOLS_CATALOGO],
        )

    def test_a_descricao_diz_o_que_nao_e(self):
        """Uma tool que so diz o que faz vende mal o que nao faz."""
        t = next(t for t in TOOLS_CATALOGO if t["name"] == "amplia_estado_sistema")
        d = t["description"]
        for frase in ("Não é um painel", "NÃO FOI MEDIDO", "Nunca `true`"):
            self.assertIn(
                frase,
                d,
                f"a descricao perdeu {frase!r}. Uma tool que promete so o que faz "
                "e' a forma de um agente prometer ao produtor mais do que o "
                "sistema pode cumprir.",
            )

    def test_o_argumento_unico_e_booleano(self):
        t = next(t for t in TOOLS_CATALOGO if t["name"] == "amplia_estado_sistema")
        props = t["inputSchema"]["properties"]
        self.assertEqual(list(props), ["so_falhas"])
        self.assertEqual(props["so_falhas"]["type"], "boolean")
        self.assertFalse(t["inputSchema"]["additionalProperties"])


class MedidoOuDesconhecidoTest(unittest.TestCase):
    def test_a_forma_do_retorno(self):
        e = estado_do_sistema()
        for chave in ("ok", "verificacoes", "falhas", "nao_medidos", "aviso"):
            self.assertIn(chave, e)
        self.assertIsInstance(e["verificacoes"], dict)

    def test_cada_verificacao_diz_onde_foi_lida(self):
        """Apontar para a morada e' o que permite confirmar sem repetir."""
        e = estado_do_sistema()
        for nome, item in e["verificacoes"].items():
            self.assertIn("ok", item, f"{nome} sem `ok`")
            self.assertIn("onde", item, f"{nome} sem `onde`")
            self.assertIn("o_que", item, f"{nome} sem `o_que`")
            self.assertTrue(
                str(item["onde"]).strip(),
                f"{nome} tem `onde` vazio",
            )

    def test_um_item_que_nao_mediu_tem_ok_nulo(self):
        """`ok: null` e' a promessa. `ok: true` sem ler seria mentira."""
        # forca uma verificacao a falhar por qualquer razao
        original = VERIFICACOES["migracoes"]

        def levanta():
            raise RuntimeError("forcado para o teste")

        VERIFICACOES["migracoes"] = levanta
        try:
            e = estado_do_sistema()
        finally:
            VERIFICACOES["migracoes"] = original

        item = e["verificacoes"]["migracoes"]
        self.assertIsNone(
            item["ok"],
            f"uma verificacao que levanta devia dar `ok: None`, e devolveu "
            f"{item['ok']!r}. Um `ok: true` aqui diria ao agente que as "
            "migracoes estao bem sem as ter lido.",
        )
        self.assertIn("migracoes", e["nao_medidos"])
        self.assertIn("migracoes", e["falhas"] + e["nao_medidos"])

    def test_nao_medidos_entra_no_aviso(self):
        """'Nao mediu' tem de aparecer no aviso. 'Tudo bem' e' que nao."""
        original = VERIFICACOES["skills"]

        def levanta():
            raise RuntimeError("x")

        VERIFICACOES["skills"] = levanta
        try:
            e = estado_do_sistema()
        finally:
            VERIFICACOES["skills"] = original

        self.assertIn("skills", e["nao_medidos"])
        self.assertNotEqual(
            e["aviso"],
            "Todas as verificacoes medidas passam.",
            "havia uma verificacao por medir e o aviso disse que todas "
            "passavam. E' a forma exacta de 'sem dado' parecer 'sem dado'.",
        )


class DetectorDeMojibakeTest(unittest.TestCase):
    """O detector que quase acusou 4069 falsos positivos."""

    def test_acusa_o_mojibake_real(self):
        """Os casos MEDIDOS no DOM antes da correccao."""
        REAIS = [
            "\u00c3\u0192\u00c2rea Total",  # sem o controlo
            "\u00c3\u0192\u00c2\u0081rea Total",  # com o controlo C1
            "dispon\u00c3\u0192\u00c2\u00advel",
            "duplica\u00c3\u0192\u00c2\u00a7\u00c3\u0192\u00c2\u00a3o",
            "prefer\u00c3\u0192\u00c2\u00aancias",
        ]
        for s in REAIS:
            self.assertTrue(
                _C1.search(s) or _AE_F.search(s),
                f"o detector NAO apanhou {s!r}. Se passa, nao detecta mojibake nenhum.",
            )

    def test_nao_acusa_portugues_legitimo(self):
        """A fronteira que quase se perdeu.

        `Ã` e `Â` SAO letras portuguesas. Um detector que as acuse nao e'
        um detector de mojibake, e' um detector de acentos — e acusaria
        `avô` e `irmã`, que aparecem em `page-index.js` legitimos.
        """
        LEGITIMOS = [
            "av\u00f4",
            "av\u00f3",
            "irm\u00e3",
            "irm\u00e3o",
            "Jo\u00e3o",
            "m\u00e3e",
            "p\u00e3o",
            "\u00e1gua",
            "cabe\u00e7a",
            "cora\u00e7\u00e3o",
            "\u00f3rg\u00e3o",
            "manh\u00e3",
            "se\u00e7\u00e3o",
            "Timor-Leste",
        ]
        for s in LEGITIMOS:
            self.assertIsNone(
                _C1.search(s), f"'{s}' tem um controlo C1? nao e' mojibake."
            )
            self.assertIsNone(_AE_F.search(s), f"'{s}' tem o par A-f? nao e' mojibake.")


class OsCincoInvariantesTest(unittest.TestCase):
    def test_sao_exatamente_os_cinco_documentados(self):
        """A lista nao cresce nem encolhe em silencio.

        Um invariante novo entra com a razao escrita; um que sai, tambem.
        """
        self.assertEqual(
            sorted(VERIFICACOES),
            ["backends", "guarda_sessao", "migracoes", "mojibake_js", "skills"],
        )

    def test_a_descricao_cita_o_que_foi_medido(self):
        """A descricao tem de bringar o numero real, nao 'pode haver'."""
        t = next(t for t in TOOLS_CATALOGO if t["name"] == "amplia_estado_sistema")
        d = t["description"]
        for medido in ("1658", "892", "sem dado", "cod_municipio"):
            self.assertIn(
                medido,
                d,
                f"a descricao deixou de citar {medido!r}. Um agente que leia a "
                "descricao tem de encontrar o numero que mediu, para "
                "saber o que está a procurar.",
            )


if __name__ == "__main__":
    unittest.main()
