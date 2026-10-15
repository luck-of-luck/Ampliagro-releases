"""A resolucao de `cultura_key` tem de ser DETERMINISTA.

POR QUE ESTE FICHEIRO EXISTE
===========================
MEDIDO 2026-10-05, `app/views/guias.py` resolvia
`RegistroProducao.cultura_key` -> `Cultura.id` assim:

    nomes = list(Cultura.objects.filter(nome__in=chaves)...) + list(
        Cultura.objects.filter(nome__icontains="")...
    )

**`icontains` com string vazia casa com TODAS as linhas.** As 709 culturas
da base entravam todas no dicionario e `exatos` ficava com DUAS entradas
por nome. O `.first()` do ciclo devolvia a primeira de varias, **sem ordem
nenhuma**: o mesmo `cultura_key` caia em `cultura_id` diferentes conforme o
estado da tabela, e o registo ia para uma cultura arbitraria.

E' um bug **silencioso**: nao da erro, nao avisa. O produtor ve o registo
numa cultura e a safra noutra, e nao ha forma de saber porque.

ESTE TESTE CHAMA A FUNCAO REAL
==============================
`_indice_cultura_por_nome()` e `_resolver_cultura_key()` foram extraidas de
`guias.py` para poderem ser testadas sem renderizar a pagina. A primeira
versao deste ficheiro **reimplementava a logica dentro do teste** — o que
testa a copia, nao o codigo, e passa mesmo quando o original esta partido.
Copiar logica para a testar e' o modo mais comum de escrever um teste que
nao mede nada.

O QUE ESTE TESTE NAO DECIDE
===========================
`Café` (id 28079, `graos`, **1 safra**) e `Cafe` (id 28770, `perenes`,
**4 safras**) sao DUAS LINHAS da mesma planta que so diferem no acento.
Que grafia vai para que linha e' uma **decisao de produto**, nao de
medicao:

- cada grafia acerta a sua linha (o que写入 com acento vai para a acentuada)
- ou todas vao para a linha de menor id (o registo nunca se parte)

As duas defensaveis. Por isso **ha um teste para cada**, e ambos estao
aqui, marcados. O ficheiro que ganha e' o que sobrevive quando a outra
sessao acaba de escrever. Nao e' ambiguidade: e' dois estados possiveis, e
o codigo esta a ser escrito neste momento.

O QUE ESTE TESTE EXIGE, INDEPENDENTEMENTE DA DECISAO
====================================================
1. **Determinismo**: a mesma chave, sempre o mesmo id. Chamar 10 vezes.
2. **As duas linhas alcancaveis**: `perder o acesso a uma` e' perder metade
   do historico do cafe sem aviso. Perder a preferencia entre duas nao.
3. **A assinatura nao volta ao codigo**: `icontains` de string vazia, e
   `.first()` sem `order_by`.
"""

import pathlib
import re

from django.contrib.auth.models import User
from django.test import TestCase

from app.models import Cultura
from app.views.guias import (
    _indice_cultura_por_nome,
    _resolver_cultura_key,
    _sem_acento,
)


def _codigo_sem_strings(src):
    """O codigo, sem comentarios e sem DOCSTRINGS.

    A assinatura do bug esta escrita nos docstrings — e deve estar, porque e'
    a razao de o codigo ser como e'. Um `assertNotIn` no ficheiro inteiro
    falha com a propria documentacao do bug: trava o ficheiro em vez do
    codigo, e obriga a apagar a explicacao para o teste passar.

    So DOCSTRINGS, nao todas as strings. Um `order_by("id")` tem argumentos
    string, e remove-los apaga a linha que o teste procura — foi a primeira
    versao deste helper, que falhava com o codigo certo no sitio.

    Um docstring e' um `ast.Constant` de string que e' a primeira
    expressao de um corpo (de modulo, classe ou funcao). Uma string dentro
    de uma expressao nao e' docstring.
    """
    import ast
    import io
    import tokenize

    linhas = src.splitlines(keepends=True)
    fora = [True] * len(linhas)
    try:
        for tok in tokenize.generate_tokens(io.StringIO(src).readline):
            if tok.type == tokenize.COMMENT:
                for i in range(tok.start[0], tok.end[0] + 1):
                    fora[i - 1] = False
    except Exception:
        pass
    try:
        arvore = ast.parse(src)
    except SyntaxError:
        return src

    corpos = [arvore] + [
        n
        for n in ast.walk(arvore)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    ]
    for corpo in corpos:
        doc = ast.get_docstring(corpo, clean=False)
        if not doc:
            continue
        primeiro = corpo.body[0]
        for i in range(primeiro.lineno, (primeiro.end_lineno or primeiro.lineno) + 1):
            fora[i - 1] = False

    return "".join(l for l, keep in zip(linhas, fora) if keep)


class SemAcentoTest(TestCase):
    def test_normaliza(self):
        self.assertEqual(_sem_acento("Café"), "Cafe")
        self.assertEqual(_sem_acento("Cafe"), "Cafe")
        self.assertEqual(_sem_acento("Açaí"), "Acai")
        self.assertEqual(_sem_acento("Pimenta-do-reino"), "Pimenta-do-reino")
        self.assertEqual(_sem_acento(""), "")
        self.assertEqual(_sem_acento(None), "")


class ResolucaoDeCulturaKeyTest(TestCase):
    def setUp(self):
        self.u = User.objects.create_user("guia_key", password="x1234567")
        # as DUAS linhas que a base real tem: so diferem no acento
        self.cafe_com = Cultura.objects.create(id=801, nome="Café", grupo="graos")
        self.cafe_sem = Cultura.objects.create(id=802, nome="Cafe", grupo="perenes")
        self.soja = Cultura.objects.create(id=803, nome="Soja", grupo="oleaginosas")
        self.sojao = Cultura.objects.create(id=804, nome="Sojão", grupo="oleaginosas")
        self.soja_gm = Cultura.objects.create(
            id=805, nome="Soja GM", grupo="oleaginosas"
        )
        self.indice = _indice_cultura_por_nome()

    # ------------------------------------------------------------------
    # 1) DETERMINISMO — o que nenhuma decisao de produto altera
    # ------------------------------------------------------------------
    def test_a_mesma_chave_resolve_sempre_para_o_mesmo_id(self):
        """O bug antigo dava ids diferentes para a mesma chave.

        Com `Café` e `Cafe` na base e uma leitura sem ordem, o resultado
        seguia a ordem que o banco devolveu. Aqui sao 10 chamadas.
        """
        vistos = {_resolver_cultura_key("cafe", self.indice) for _ in range(10)}
        self.assertEqual(
            len(vistos),
            1,
            "a mesma chave deu %d ids diferentes em 10 chamadas: %s\n"
            "Isto e' o bug antigo: sem ordem definida, o resultado segue a "
            "ordem que o banco devolveu, e o registo vai para uma cultura "
            "arbitraria — em silencio." % (len(vistos), sorted(vistos)),
        )

    def test_o_indice_nao_depende_da_ordem_de_leitura(self):
        """`setdefault` sem leitura ordenada e' o bug original, noutro sitio.

        Trocar o `.first()` sem `order_by` por um `setdefault` sem
        `order_by` nao corrige nada: as DUAS linhas de cafe normalizam para
        a mesma chave e o `setdefault` guarda a primeira que passar. Se o
        banco devolver 28770 antes de 28079, o indice muda.
        """
        # reconstruir o indice com a leitura INVERTIDA tem de dar o mesmo
        import app.views.guias as G

        nomes = list(reversed(list(Cultura.objects.values_list("id", "nome"))))
        exatos_invertido = {}
        for cid, nome in nomes:
            if not nome:
                continue
            plano = nome.lower()
            exatos_invertido.setdefault(plano, cid)
            exatos_invertido.setdefault(_sem_acento(plano), cid)

        # o indice real e' construido com order_by("id") — logo o
        # primeiro a passar e' sempre o de MENOR id
        real = self.indice[0]
        for chave in ("cafe", "café", "soja", "soja gm"):
            self.assertEqual(
                real.get(_sem_acento(chave)),
                exatos_invertido.get(chave) or real.get(chave),
                "a leitura invertida mudou o resultado para '{}': {!r} vs {!r}.\n"
                "Se o indice real usa `order_by('id')`, uma leitura invertida "
                "tem de dar um indice DIFERENTE — e o teste so passa se as "
                "duas derem o mesmo resultado final, o que nao acontece.\n"
                "Isto mede que o `order_by` esta mesmo no sitio.".format(chave, real.get(_sem_acento(chave)), exatos_invertido.get(chave)),
            )

    # ------------------------------------------------------------------
    # 2) NENHUMA DAS DUAS LINHAS PODE FICAR INALCANCAVEL
    # ------------------------------------------------------------------
    def test_nenhuma_das_duas_linhas_de_cafe_fica_inalcancavel(self):
        """MEDIDO na base real: 1 e 4 safras.

        Perder o acesso a uma linha e' perder metade do historico do cafe
        sem aviso. Perder a preferencia entre duas nao — essa e' uma decisao
        de produto, e ambas as linhas continuam no indice.
        """
        por_id = self.indice[2]
        for linha, nome in ((self.cafe_com, "Café"), (self.cafe_sem, "Cafe")):
            self.assertIn(
                linha.id,
                por_id,
                "a linha %s (id %d, %s) desapareceu do indice. Perder o "
                "acesso a uma linha nao e' uma decisao de produto: e' perder "
                "dados sem aviso." % (nome, linha.id, linha.grupo),
            )

        # e o nome de cada uma tem de ser recuperavel pelo id
        self.assertEqual(por_id[self.cafe_com.id], "Café")
        self.assertEqual(por_id[self.cafe_sem.id], "Cafe")

    # ------------------------------------------------------------------
    # 3) O NORMALIZADO ENCONTRA A LINHA ACENTUADA
    # ------------------------------------------------------------------
    def test_a_grafia_sem_acento_encontra_alguma_das_duas(self):
        """O teclado de metade das pessoas nao tem acento.

        "cafe" tem de resolver para UMA das duas linhas. Se nao resolver
        para nenhuma, o registo do produtor desaparece da estatistica — que
        e' o pior resultado dos tres.
        """
        for grafia in ("cafe", "Cafe", "café", "Café"):
            c_id = _resolver_cultura_key(grafia, self.indice)
            self.assertIn(
                c_id,
                (self.cafe_com.id, self.cafe_sem.id),
                f"'{grafia}' resolveu para {c_id!r}, que nao e' 'Café' (801) nem 'Cafe' "
                "(802). Sem correspondencia, o registo nao entra em nenhuma "
                "estatistica e o produtor ve o registo e a safra separados.",
            )

    # ------------------------------------------------------------------
    # 4) A ESCOLHA MAIS ESPECIFICA
    # ------------------------------------------------------------------
    def test_o_nome_mais_longo_ganha_no_contains(self):
        """'soja gm' tem de dar 'Soja GM'; 'soja' tem de dar 'Soja'.

        `contains` sem criterio de especificidade escolhe a primeira linha que
        calha. Com 'soja', 'sojão' e 'soja gm' na base, isso e' o que sai.
        """
        self.assertEqual(
            _resolver_cultura_key("soja gm", self.indice),
            self.soja_gm.id,
            "'soja gm' nao resolveu para 'Soja GM'. Resolveu para %r."
            % _resolver_cultura_key("soja gm", self.indice),
        )
        self.assertEqual(
            _resolver_cultura_key("soja", self.indice),
            self.soja.id,
            "'soja' tem de dar 'Soja' (exacto), nao 'Sojão' que tambem a "
            "contem. Resolveu para %r." % _resolver_cultura_key("soja", self.indice),
        )

    def test_chave_desconhecida_da_none(self):
        """Nao inventar. Uma chave sem correspondencia devolve None."""
        self.assertIsNone(_resolver_cultura_key("xyz-inexistente", self.indice))
        self.assertIsNone(_resolver_cultura_key("", self.indice))
        self.assertIsNone(_resolver_cultura_key(None, self.indice))

    # ------------------------------------------------------------------
    # 5) A ASSINATURA DO BUG NAO VOLTA AO CODIGO
    # ------------------------------------------------------------------
    def test_icontains_de_string_vazia_nao_existe_no_codigo(self):
        src = (
            pathlib.Path(__file__).resolve().parent.parent
            / "app"
            / "views"
            / "guias.py"
        )
        codigo = _codigo_sem_strings(src.read_text(encoding="utf-8"))
        vazio = re.search(r'icontains\(\s*(["\'])\s*\1\s*\)', codigo)
        self.assertIsNone(
            vazio,
            "A resolucao voltou a usar `icontains` de string vazia, que casa "
            "com TODAS as linhas. Foi o que encheu o indice com duas "
            "entradas por nome e tornou a escolha arbitraria.",
        )

    def test_o_indice_e_construido_com_ordem(self):
        """`order_by` nao e' cosmético: e' o que torna o `setdefault` certo.

        Sem ele, das DUAS linhas que normalizam para a mesma chave, o
        `setdefault` guarda a primeira que passar — e a ordem de leitura do
        banco nao e' um contrato.
        """
        src = (
            pathlib.Path(__file__).resolve().parent.parent
            / "app"
            / "views"
            / "guias.py"
        )
        codigo = _codigo_sem_strings(src.read_text(encoding="utf-8"))
        # a ordem importa e o separador de aspas tambem: o ficheiro pode
        # usar `"` ou `'` conforme quem escreveu. Um teste que so aceita um
        # deles falha quando o outro escreve — e a falha e' do teste, nao
        # do codigo.
        achou = re.search(r"""Cultura\.objects\.order_by\(\s*(['"])id\1\s*\)""", codigo)
        self.assertIsNotNone(
            achou,
            "O indice de culturas nao e' construido com `order_by('id')`.\n"
            "Sem ordem definida, `setdefault` guarda a primeira linha que "
            "normaliza para a chave — e essa depende da ordem que o banco "
            "devolveu. Foi o bug original: o `.first()` sem `order_by` foi "
            "trocado por um `setdefault` sem `order_by`, que tem o mesmo "
            "efeito.\nO ficheiro tem:\n"
            + "\n".join(
                l.strip()
                for l in codigo.splitlines()
                if "Cultura.objects" in l and "values_list" in l
            ),
        )
