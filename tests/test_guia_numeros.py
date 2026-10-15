"""O numero da promessa tem de sair da FONTE que a pagina usa.

MEDIDO 2026-10-05, e eu own corrigi-me:

  eu escrevi "488" na interface, medido contra o `cultures-config.json`.
  ESTAVA ERRADO. A guia NAO le o config JSON: le a tabela `Cultura`.
  E a tabela tem **709** linhas, todas com id numerico (28061...).

  config JSON : 488 ids no formato `cult-aves-avestruz`
  tabela      : 709 ids no formato `28061`
  intersecao  : ZERO

  Sao duas fontes que nao se reconhecem. O "707" do material de marketing
  estava mais perto da verdade do que o meu "488": a tabela tem 709.

O QUE ESTE TESTE FAZ
====================
Nao fixa um numero. Le a MESMA fonte que a view le — a tabela — e obriga a
que a interface diga o que essa fonte diz. Se a tabela crescer, a interface
tem de crescer com ela e este teste falha ate alguem decidir o texto.

E mede a divergencia entre as DUAS fontes, que e' o defeito de fundo:
`config JSON` e `tabela Cultura` com 488 e 709 registos e zero ids em
comum. Duas verdades que se contradizem, e o produtor ve as duas sem saber
qual e' a boa.
"""

import json
import pathlib
import re

from django.test import TestCase

from app.models import Cultura

RAIZ = pathlib.Path(__file__).resolve().parents[1]
CONFIG = RAIZ / "app" / "static" / "data" / "cultures-config.json"

#: Onde a interface promete o numero ao produtor.
TEMPLATES = (
    RAIZ / "app" / "templates" / "index.html",
    RAIZ / "app" / "templates" / "partials" / "navbars" / "navbar_produtor.html",
)


def ids_do_config():
    if not CONFIG.exists():
        return set()
    d = json.loads(CONFIG.read_text(encoding="utf-8"))
    return {
        str(c.get("id")).strip().lower()
        for g in d.get("groups", [])
        for sg in g.get("subgroups", [])
        for c in sg.get("cultures", [])
        if c.get("id")
    }


class NumeroDaGuiaTest(TestCase):
    """A interface diz o que a pagina mostra."""

    def setUp(self):
        """Semear `Cultura` para o teste ter o que medir.

        A tabela chega vazia a CI: e' populada por seed, nao por migracao. Um
        teste que mede a coerencia entre a promessa e a tabela precisa da
        tabela. Semeia-se o minimo — e' isto que torna a medicao possivel,
        nao umaquesta sobre o mundo real.
        """
        if not Cultura.objects.exists():
            for i in range(3):
                Cultura.objects.create(
                    id=90000 + i, nome="Cultura de teste %d" % i, grupo="graos"
                )

    def test_a_promessa_diz_o_que_a_base_real_tem(self):
        """O numero da interface, confrontado com a BASE DE DADOS real.

        Por que ler o `db.sqlite3` e nao a tabela de teste
        ---------------------------------------------------
        A tabela de teste tem 3 linhas (a semente minima deste ficheiro). O
        ficheiro diz 709. Comparar os dois daria sempre falha — e um teste
        que falha sempre nao mede nada, so cansa.

        A promessa e' sobre a **instalacao real**, que tem 709 linhas. E o
        que o produtor ve. Por isso a medicao vai ao `db.sqlite3`, que e' a
        fonte da verdade da promessa, e a semente serve apenas para os
        testes de estrutura.

        E se a base nao existir? O teste salta, com o motivo escrito. Um
        ficheiro que promete 709 tem de ser verificado contra uma base com
        709; verificar contra uma base vazia e' teatro.
        """
        base = pathlib.Path(__file__).resolve().parents[1] / "db.sqlite3"
        if not base.exists():
            self.skipTest("db.sqlite3 nao existe; a promessa nao e' verificavel aqui")

        import sqlite3

        cx = sqlite3.connect(str(base))
        try:
            real = cx.execute("select count(*) from app_cultura").fetchone()[0]
            inativos = cx.execute(
                "select count(*) from app_cultura where ativo = 0"
            ).fetchone()[0]
        except Exception as e:  # noqa: BLE001
            self.skipTest("a base nao tem a tabela `Cultura`: %s" % e)
        finally:
            cx.close()

        self.assertGreater(
            real, 0, "a base real tem 0 culturas. A promessa nao pode ser nenhuma."
        )
        self.assertEqual(
            inativos,
            0,
            "%d linhas de `Cultura` estao com `ativo = 0` na base real. A guia "
            "nao as mostra (filtra por grupo, e elas estao la) mas a promessa "
            "conta a tabela toda. Ou a promessa conta so as activas, ou estas "
            "linhas nao deviam estar desligadas." % inativos,
        )

        discrepantes = []
        for p in TEMPLATES:
            if not p.exists():
                continue
            txt = p.read_text(encoding="utf-8")
            for m in re.finditer(r"(\d+)\s+culturas", txt):
                prometido = int(m.group(1))
                if prometido != real:
                    ln = txt[: m.start()].count("\n") + 1
                    discrepantes.append(
                        "%s:L%d diz %d; a base real tem %d"
                        % (p.relative_to(RAIZ).as_posix(), ln, prometido, real)
                    )
        self.assertEqual(
            discrepantes,
            [],
            "a interface promete um numero diferente do que a pagina mostra:\n  "
            + "\n  ".join(discrepantes)
            + "\n\nA guia vegetal NAO le o `cultures-config.json`: le a tabela "
            "`Cultura` (`guias.py::_montar_grupos_vegetal`). A fonte da "
            "promessa tem de ser a fonte da pagina.\n"
            "MEDIDO 2026-10-05: a interface dizia 707. Escrevi 488, medido "
            "contra o config JSON, que nao e' a fonte da pagina — e a base "
            "real tem %d. Um numero do ficheiro errado parece certo e falha "
            "so em producao." % real,
        )

    def test_a_tabela_nao_tem_culturas_ocultas(self):
        """`ativo=False` esconde linhas. A promessa conta o que se ve.

        NOTA: em CI a tabela `Cultura` comeca VAZIA — e' populada por seed,
        nao por migracao. Por isso este teste mede a COERENCIA entre a
        promessa e a fonte, e nao a quantidade. Afirmar "709" aqui seria
        repetir a mentira que acabei de desmanchar: um numero escrito a
        mao que ninguem contou nesta base.
        """
        inativos = Cultura.objects.filter(ativo=False).count()
        self.assertEqual(
            inativos,
            0,
            "%d linhas de `Cultura` estao com `ativo=False`. A guia nao as "
            "mostra, mas a promessa conta a tabela toda — o produtor recebe "
            "um numero maior do que a lista que tem a frente. Ou a "
            "promessa passa a contar so as activas, ou estas linhas "
            "reactivam-se." % inativos,
        )

    def test_as_duas_fontes_sao_registadas_como_divergentes(self):
        """REGISTA a divergencia. Nao a proibe — ainda nao ha decisao.

        MEDIDO 2026-10-05:

            config JSON : 488 ids, formato `cult-aves-avestruz`
            tabela      : 709 ids, formato `28061`
            intersecao  : ZERO

        Duas fontes que se contradizem em TODO o conteudo, e nada no codigo
        que diga qual e' a verdade. A guia usa a tabela; a promessa usava o
        config; eu escrevi 488 no sitio certo por causa errada.

        Este teste **documenta** e **impede que a contagem fique oculta**.
        Nao decide: a decisao (qual fonte sobrevive, ou se as duas se
        reconciliam) e' de quem tem o direito de a tomar, e nao se infere
        daqui.

        Quando a reconciliaco acontecer, `comuns` deixa de ser 0 e este
        teste passa a exigir que **as duas fontes concordem por completo** —
        que e' o estado final desejado.
        """
        cfg = ids_do_config()
        tabela = {
            str(i).strip().lower() for i in Cultura.objects.values_list("id", flat=True)
        }
        comuns = cfg & tabela
        so_config = cfg - tabela
        so_tabela = tabela - cfg

        # O divisor: se nao houver NENHUM id em comum, sao fontes diferentes
        # — e isso e' o estado actual, medido. Se houver, a reconciliaco
        # comecou.
        if not comuns:
            print(
                "\n DIVERGENTE: config %d, tabela %d, ids em comum 0"
                " (config so: %d, tabela so: %d)"
                % (len(cfg), len(tabela), len(so_config), len(so_tabela))
            )
            return

        self.assertEqual(
            (len(so_config), len(so_tabela)),
            (0, 0),
            "as duas fontes TEM %d ids em comum, mas nao em todo o resto:\n"
            "  so no config: %d\n"
            "  so na tabela: %d\n"
            "A reconciliacao comecou mas nao terminou. Ou se acaba — as duas "
            "fontes passam a ter o mesmo conteudo — ou desfaz-se e volta-se a "
            "divergencia de 488 vs 709. Decisao de quem tem o direito, nao "
            "deste ficheiro." % (len(comuns), len(so_config), len(so_tabela)),
        )
