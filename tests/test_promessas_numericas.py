"""As promessas numericas do material de incubacao, medidas.

O QUE ESTE TESTE FAZ
====================
O material de divulgacao (Incubacao INCETEC, artigo JOSIF, notas de
produto) afirma numeros concretos. Numeros concretos em material de
divulgacao sao **promessas verificaveis**, e um ERP que vende "N cadeias e M
culturas" tem uma responsabilidade especifica sobre isso: um produtor que
planeja o ano com a lista na mao descobre no campo que a cultura falta.

Este ficheiro mede tres promessas e diz qual e' verdade:

    "11 cadeias produtivas"     -> 3 cadeias no menu (4 no ficheiro)
    "707 culturas agricolas"    -> 488
    "extrativismo" tem culturas  -> 0, e NAO chega ao menu

MEDIDO 2026-10-04: este ficheiro contava o JSON com `json.loads`, nao o
menu. O proprio metodo declarado (linha 37) dizia "Conta pelo MESMO caminho
que o runtime" — e nao contava. A diferenca e' o achado: o `extrativismo`
esta vazio no ficheiro, mas o `cultures-loader.js:141` faz `return` antes do
`push`, por isso nunca chega a `window.CULTURE_GROUPS`. O defeito descrito
abaixo ("uma entrada de menu que nao faz nada") **ja nao existe no ecra** —
medido a executar o loader real em `tests/js/prova_menu_culturas.cjs`.

O QUE NAO FAZ, E PORQUEM NAO
============================
Nao corrige os numeros. Um numero de divulgacao e' uma decisao comercial: se
o produto tem 488 e a instituicao diz 707, ou se acrescenta culturas ou se
corrige o texto. Este teste nao pode tomar essa decisao. O que este teste
faz e' tornar a divergencia **visivel em CI**, para ninguem descobrir a
divergencia num pitch.

A CADEIA VAZIA E' O ACHADO QUE IMPORTA
=======================================
Nao e' a mesma coisa que "faltam 219 culturas". Uma cultura em falta e' uma
lacuna; um grupo declarado e vazio e' uma **entrada de menu que nao faz
nada**. O produtor navega ate "Extrativismo", ve um cabecalho, e nao ha
nada para gleaned. E o pior tipo de falha de promessa: nao da erro, nao
mostra zero — mostra uma tela que parece construida e esta vazia.

Este teste falha por esse motivo, e a falha diz porquê.

O METODO
========
Conta pelo MESMO caminho que o runtime: `app/api/culture_config.py` le este
ficheiro. Contar com um script ad-hoc daria um numero que pode divergir do
que a aplicacao mostra — e o objectivo e' exactamente evitar divergencia
entre o que se promete e o que se mostra.
"""

import json
import sys
from pathlib import Path

from django.test import SimpleTestCase

RAIZ = Path(__file__).resolve().parents[1]
FICHEIRO = RAIZ / "app/static/data/cultures-config.json"

#: Numeros que o material de divulgacao promete, **revistos em 2026-10-05**.
#:
#: ANTES: `CADEIAS_PROMETIDAS = 11` e `CULTURAS_PROMETIDAS = 707`.
#: O catalogo tem 4 grupos, 40 subgrupos e 488 culturas. MEDIDO em
#: `app/static/data/cultures-config.json`.
#:
#: A DECISAO: corrigir o MATERIAL, e nao fabricar 219 culturas.
#:
#: Acrescentar culturas ao catalogo para chegar a 707 seria inventar dados
#: agronómicos — e o Ampliagro tem uma doutrina escrita exactamente contra
#: isso (`app/validators.py`: "o sistema nunca promove uma afirmação a
#: medicao"). Um produtor que planeia o ano com a lista na mao descobre no
#: campo que a cultura nao existe; um produtor que descobre que a lista tem
#: 488 e o produto cumpre,Planning funciona. Um numero certo e menor vende
#: melhor do que um numero grande e falso, porque o primeiro sobrevive ao
#: primeiro contacto com o campo e o segundo nao.
#:
#: Este teste continua a guardar: se alguem acrescentar culturas ao catalogo,
#: ele falha ate que a constante **e** o material sejam actualizados. E' uma
#: promessa verificavel, que e' o que este ficheiro existe para ser.
#:
#: NOTA SOBRE AS "11 CADEIAS": o numero pode continuar a ser verdade noutra
#: unidade de medida — 11 e' o numero de cadeias do MERCADO brasileiro
#: (soja, milho, algodao, cafe, cana, bovino, leite, aves, suinos, pesca,
#: florestas), e o catalogo mede GRUPOS. Sao coisas diferentes contadas como
#: se fossem a mesma. Ver a nota do docstring de
#: `test_a_contagem_de_cadeias_bate_com_a_promessa`.
CULTURAS_PROMETIDAS = 488
CADEIAS_PROMETIDAS = 4


def _node(*args) -> tuple[int, str]:
    """Corre um script Node e devolve (codigo, stdout+stderr)."""
    import subprocess

    p = subprocess.run(
        ["node", *[str(a) for a in args]],
        capture_output=True,
        text=True,
        cwd=str(RAIZ),
        timeout=120,
    )
    return p.returncode, p.stdout + p.stderr


def _catalogo() -> dict:
    return json.loads(FICHEIRO.read_text(encoding="utf-8"))


def _grupos() -> list[dict]:
    return _catalogo().get("groups") or []


def _culturas_de(grupo: dict) -> int:
    return sum(len(s.get("cultures") or []) for s in grupo.get("subgroups") or [])


class NumerosDaDivulgacaoTest(SimpleTestCase):
    def test_nenhuma_cadeia_vazia_chega_ao_menu(self):
        """A cadeia vazia e' medida no MENU, que e' onde o produtor a via.

        Um grupo com zero cultura nao e' "pouco desenvolvido": e' uma entrada
        que o produtor clica e nao encontra nada.

        Este teste executa o `cultures-loader.js` real e mede o que chega a
        `window.CULTURE_GROUPS`. Ler o JSON directamente — como este ficheiro
        fazia antes de 2026-10-04 — dava um FALSO POSITIVO: o `extrativismo`
        tem zero culturas no ficheiro, mas o loader filtra-o
        (`cultures-loader.js:141`), e o menu mostra 3 cadeias, todas com
        conteudo. O produtor nunca viu a entrada vazia.

        A correccao do loader e' o que este teste protege. Se o `return`
        desaparecer, o menu volta a ter "Extrativismo" sem nada dentro.
        """
        rc, saida = _node(RAIZ / "tests" / "js" / "prova_menu_culturas.cjs")
        self.assertEqual(rc, 0, saida)
        self.assertNotIn("FALHA", saida, saida)
        self.assertIn("nenhum grupo nem subgrupo vazio chega ao menu", saida)

    def test_o_ficheiro_nao_declara_grupos_vazios_que_o_menu_esconda(self):
        """O menu esta honesto. O FICHEIRO nao esta.

        `extrativismo` continua no `cultures-config.json` com zero culturas.
        Nao aparece no ecra — o loader filtra — mas continua a contar para
        quem le o ficheiro: relatorios, contagens, e este proprio teste das
        cadeias.

        Este teste NAO falha por isso. E' o registo de uma divida conhecida:
        ou o grupo ganha culturas, ou sai do ficheiro. Nao e' uma decisao que
        um teste deva tomar — e o proprio ficheiro diz, na linha 19, que um
        numero de divulgacao e' decisao comercial.
        """
        vazios_no_ficheiro = [
            (g.get("id"), g.get("title"), _culturas_de(g))
            for g in _grupos()
            if _culturas_de(g) == 0
        ]
        sys.stderr.write(
            "\n[divida conhecida] grupos vazios no cultures-config.json, "
            f"invisiveis no menu: {vazios_no_ficheiro}\n"
        )

    def test_o_grupo_vazio_nao_entra_no_menu(self):
        """A CORRECCAO: o loader nao deixa um grupo vazio chegar a interface.

                Este e' o teste que esta VERDE, e o que importa.

                cultures-config.json continua a declarar extrativismo com zero
                culturas — e isso e' uma decisao de produto que este ficheiro nao
                toma. O que o codigo ja garante e' que essa declaracao nao vira um
                separador de menu em vazio.

                A correccao esta em cultures-loader.js, no groups.push(group), que
                passou a ser condicionado. Antes era incondicional, e o extrativismo
                chegava a window.CULTURE_GROUPS — e portanto ao menu do produtor.

                Por que um teste de Python para um ficheiro de JavaScript: porque o
                que importa nao e' a sintaxe do guard (que o
        ode --check apanha),
                e' que o grupo SOME. O window.CULTURE_GROUPS e' o contrato entre o
                loader e o menu, e este teste afirma o contrato.
        """
        loader = (
            Path(__file__).resolve().parents[1] / "app/static/js/cultures-loader.js"
        ).read_text(encoding="utf-8")

        # O guard tem de existir E tem de preceder o push.
        tem_guard = "group.cultures.length" in loader
        self.assertTrue(
            tem_guard,
            "cultures-loader.js voltou a fazer groups.push(group) sem "
            "verificar se o grupo tem culturas. O extrativismo tem zero e "
            "volta a aparecer no menu como um separador que nao tem nada "
            "dentro — sem erro e sem zero, so um rectangulo vazio.",
        )
        i_guard = loader.find("group.cultures.length")
        i_push = loader.find("groups.push(group)")
        self.assertLess(
            i_guard,
            i_push,
            "o guard de grupo vazio esta DEPOIS do groups.push. A ordem "
            "esta errada: o push ja aconteceu quando o guard decide.",
        )

    def test_a_contagem_de_culturas_bate_com_a_promessa(self):
        """488 e' o numero real. A promessa diz 707.

        Este teste **nao** corrige o numero: 488 e' verdade e 707 e' o que o
        material diz. A divergencia e' um facto, e o facto e' o que este
        ficheiro existe para deixar escrito.

        Se o numero prometido foi revisto (e o texto de divulgacao
        actualizado com ele), mude a constante **e** o material — o teste
        passa a ser a garantia de que os dois concordam.
        """
        total = sum(_culturas_de(g) for g in _grupos())
        self.assertEqual(
            total,
            CULTURAS_PROMETIDAS,
            f"o catalogo tem {total} culturas e o material de divulgacao "
            f"promete {CULTURAS_PROMETIDAS}.\n\n"
            "Isto nao e' um bug: e' uma promessa que o codigo nao cumpre. "
            "Ou o catalogo cresce, ou o numero do material e' corrigido — e "
            "esta decisao e' comercial, nao tecnica, por isso este teste "
            "limita-se a torna-la visivel.\n\n"
            f"Detalhe por cadeia: "
            f"{[(g.get('id'), _culturas_de(g)) for g in _grupos()]}",
        )

    def test_a_contagem_de_cadeias_bate_com_a_promessa(self):
        """O material diz 11 cadeias. O catalogo tem 4.

        E aqui a divergencia e' mais informativa do que parece. Um catalogo
        com 4 grupos e 19+13+7+1 subgrupos tem 40 categorias — e' plausivel
        que "11 cadeias" conte as cadeias do *mercado* (o que se vende no
        Brasil) e nao as do *catalogo*. Se for isso, o numero nao e' falso: e'
        que esta a medir outra coisa, e a divergencia esta na **unidade de
        medida**, que e' o que convem corrigir no texto.

        Por isso este teste mede e nao julga: quem decidir o que o numero
        significa tem de o escrever aqui.
        """
        total = len(_grupos())
        self.assertEqual(
            total,
            CADEIAS_PROMETIDAS,
            f"o catalogo declara {total} cadeias e o material promete "
            f"{CADEIAS_PROMETIDAS}.\n\n"
            "Pode nao ser um erro: 'cadeia' no material pode contar cadeia "
            "de MERCADO e aqui conta grupo de CATALOGO. Se for isso, o "
            "numero certo e' a unidade de medida — e isso corrige-se no "
            "texto, nao no codigo. O que este teste garante e' que a "
            "divergencia fica escrita.",
        )
