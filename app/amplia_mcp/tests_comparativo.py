"""O comparativo medido NAO pode mentir. Estes testes sao essa garantia.

Tres classes de teste, e a terceira e' a que interessa:

  1. A sonda encontra o que existe, e so isso
  2. O catalogo expoe os quatro estados, e nao um estado "boa"
  3. **Nenhuma capacidade e' promovida a `verificada` sem um teste que a
     exercite.** Este e' o teste que impede o modulo de publicar "somos
     melhores em 43 de 50" sem evidencia.

MEDIDO 2026-10-05: o `.xlsx` esta' 98,6% por medir (4 928 de 5 000 celulas
sao `?`). Um modulo que publicasse posicao de concorrentes a partir disso
seria exactamente o defeito que `proveniencia.py` existe para impedir.
"""

import os
import unittest

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.test")

from app.amplia_mcp import comparativo as C  # noqa: E402


class SondasEncontramOQueExisteTest(unittest.TestCase):
    """1. A sonda e' uma sonda, nao um oraculo."""

    def test_encontra_o_gerador_do_lcdpr(self):
        """MEDIDO: `lcdpr_export.py` existe. A sonda tem de achar a definicao."""
        ev = C._procurar("LCDPRGenerator")(C.RAIZ)
        self.assertIsNotNone(ev, "LCDPRGenerator existe no codigo — a sonda falhou")
        self.assertRegex(ev, r"\.py:\d+$", "a evidencia tem de ser ficheiro:linha")

    def test_encontra_o_registro_de_intents(self):
        """`wizTalhaoStep` vive em `.js`. Este teste foi escrito DEPOIS de a
        sonda dar `ausente` para sempre — porque so procurava em `.py`, e
        um falso `ausente` e' pior do que um falso `parcial`: diz que nao ha
        codigo, e quem le acredita.
        """
        ev = C._procurar("wizTalhaoStep", extensions=(".js", ".py"))(C.RAIZ)
        self.assertIsNotNone(ev, "wizTalhaoStep esta' em ia-local.js — a sonda falhou")
        self.assertTrue(ev.endswith(".js:") or ".js:" in ev, ev)

    def test_nao_encontra_o_que_nao_existe(self):
        """A parte que importa: a sonda tem de dizer NAO quando e' NAO.

        Uma sonda que devolve sempre uma string transforma o catalogo num
        gerador de afirmacoes. Este teste e' o que a impede.
        """
        self.assertIsNone(C._procurar("def_nao_existe_este_simbolo")(C.RAIZ))
        self.assertIsNone(C._procurar("NotaCampoQueNaoExiste")(C.RAIZ))


class OsQuatroEstadosTest(unittest.TestCase):
    """2. Os estados existem e significam o que dizem."""

    def test_os_quatro_estados(self):
        """Sao quatro VALORES distintos, e nenhum deles e' 'tudo bem'."""
        valores = {C.VERIFICADA, C.PARCIAL, C.AUSENTE, C.NAO_VERIFICADA}
        self.assertEqual(
            len(valores), 4, "os estados tem de ser distintos: %s" % valores
        )
        for v in valores:
            self.assertTrue(v and isinstance(v, str))

    def test_nome_do_estado_nao_promete(self):
        """O nome do estado de 'existe codigo' nao pode ser 'completa'."""
        self.assertNotIn("complet", C.PARCIAL.lower())
        self.assertNotIn("completo", C.VERIFICADA.lower())


class NinguemPromovidoSemTesteTest(unittest.TestCase):
    """3. O teste que impede a mentira.

    Qualquer capacidade que chegue a `verificada` tem de ter um teste
    REAL que a exercite. Hoje nao ha nenhum — e por isso `verificada` tem
    de estar vazia. Se um dia alguem a promover, este teste obriga a
    dizer qual o teste.
    """

    #: mapa: capability_id -> nome do teste que a exercita
    PROVAS = {
        # Deliberadamente VAZIO. Nenhuma capacidade tem, hoje, um teste que
        # a exercite de ponta a ponta. Quando alguem escrever esse teste,
        # lista-o aqui — e o comentario tem de dizer o que o teste prova.
    }

    def test_nenhuma_capacidade_sem_prova_e_verificada(self):
        medidas = C.medir_ampliagro()["capacidades"]
        sem_prova = [
            c["id"]
            for c in medidas
            if c["estado"] == C.VERIFICADA and c["id"] not in self.PROVAS
        ]
        self.assertEqual(
            sem_prova,
            [],
            "capacidades promovidas a `verificada` sem teste que as exercite: %s.\n"
            "Ou escreve o teste e lista-o em PROVAS, com o que ele prova, ou\n"
            "volta a capacidade a `parcial`. `verificada` sem prova e' a\n"
            "afirmacao sem medicao que este projecto nao aceita." % sem_prova,
        )

    def test_a_tabela_de_provas_nao_declara_mais_do_que_existe(self):
        for cid in self.PROVAS:
            medidas = C.medir_ampliagro()["capacidades"]
            ids = [c["id"] for c in medidas]
            self.assertIn(
                cid, ids, "PROVAS declara %s, que nao e' uma capacidade" % cid
            )


class OQueOModuloNaoAfirmaTest(unittest.TestCase):
    """4. O modulo tem de recusar a escrever o que nao sabe.

    A tentacao, com um ficheiro que tem 100 empresas e 50 features a dizer
    'F' numa percentagem, e' summar um score. E' o que transformaria esta
    lista de capacidades num ranking nao verificado.
    """

    def test_o_catalogo_avisa_que_a_matriz_esta_por_medir(self):
        cat = C.catalogo_comparativo()
        self.assertIn("aviso", cat)
        self.assertIn("98,6%", cat["aviso"])
        self.assertIn("NAO diz a posicao de ninguem", cat["aviso"])

    def test_nao_existe_um_score_de_posicao(self):
        """Nao ha `score`, `posicao`, `ranking` ou `primeiro_lugar`.

        Se alguem os acrescentar, este teste falha — e a falha e' o aviso.
        """
        cat = C.catalogo_comparativo()
        proibidos = ("score", "posicao", "ranking", "primeiro_lugar", "melhor_que")
        for chave in cat:
            for proibido in proibidos:
                self.assertNotIn(
                    proibido,
                    chave.lower(),
                    "'%s' na chave '%s' — este modulo nao afere posicao de "
                    "ninguem" % (proibido, chave),
                )

    def test_a_dimension_vem_do_ficheiro(self):
        caps = C.medir_ampliagro()["capacidades"]
        self.assertEqual(len(caps), 50, "a folha COLUNAS tem 50 capacidades")
        grupos = {c["grupo"] for c in caps}
        self.assertIn("A. Fiscal", grupos)
        self.assertIn("H. Dados", grupos)

    def test_filtra_por_grupo(self):
        so_fiscal = C.catalogo_comparativo(grupo="fiscal")
        self.assertTrue(so_fiscal["capacidades"])
        for c in so_fiscal["capacidades"]:
            self.assertIn("fiscal", str(c["grupo"]).lower())


if __name__ == "__main__":
    unittest.main()
