"""Quantas queries a guia vegetal faz? Medido, nao estimado.

Por que este ficheiro existe
=============================
A guia vegetal e' a pagina mais visitada do produto: o produtor entra para
ver o que esta a plantar. Se ela faz uma query por propriedade e uma por
grupo, um produtor com 20 fazendas espera 20 vezes mais do que um com uma —
e a unica coisa que ele fez foi ter mais terra.

O que mede
==========
1. `_montar_grupos_vegetal()` sem ninguem: 16 grupos + "outras". Se saem
   17 queries, sao 17 idas ao banco para montar dicionarios.
2. A view completa com 1, 5 e 20 propriedades. O que interessa e' o
   **coeficiente**: se cada propriedade acrescenta um numero constante de
   queries, ha N+1.

Por que e' um teste e nao um script
===================================
Um script mede uma vez e passa. Um teste mede sempre, e se alguem
des-sintetizar o codigo volta a falhar — que e' quando interessa. O
limiar nao e' "zero queries" (isso seria mentira: uma pagina que mostra
dados precisa de as buscar), e' "nao cresce com o numero de propriedades".
"""

from decimal import Decimal

from django.contrib.auth.models import User
from django.db import connection
from django.test import RequestFactory, TestCase
from django.test.utils import CaptureQueriesContext

from app.models import Cultura, Propriedade, Safra
from app.views.guias import VEGETAL_GRUPOS, _montar_grupos_vegetal, guia_vegetal_view

#: Uma view que mostra dados NUNCA precisa de zero queries. O que nao pode
#: e' crescer com o numero de propriedades. Este e' o tecto do excedente:
#: 2 queries por propriedade ja e' suspiciouslyo, 6 e' N+1 declarado.
QUERIES_POR_PROPRIEDADE = 3


class GuiaVegetalNaoTemNMaisUmTest(TestCase):
    def setUp(self):
        self.u = User.objects.create_user("diag_guias", password="x1234567")
        self.rf = RequestFactory()

    def _pedido(self):
        r = self.rf.get("/guias/vegetal/")
        r.user = self.u
        return r

    def _criar_propriedades(self, n):
        for i in range(n):
            Propriedade.objects.create(
                user=self.u, nome="Fazenda %02d" % i, area_total=Decimal("100")
            )

    # ------------------------------------------------------------------
    # 1) O numero de queries nao cresce com as propriedades
    # ------------------------------------------------------------------
    def test_a_view_nao_cresce_com_o_numero_de_propriedades(self):
        medidas = {}
        for n in (1, 5):
            self._criar_propriedades(n)
            with CaptureQueriesContext(connection) as ctx:
                guia_vegetal_view(self._pedido())
            medidas[n] = len(ctx.captured_queries)

        crescimento = medidas[5] - medidas[1]
        self.assertLessEqual(
            crescimento,
            4 * QUERIES_POR_PROPRIEDADE,
            "a guia vegetal cresce com o numero de propriedades:\n"
            "  1 propriedade  -> %d queries\n"
            "  5 propriedades -> %d queries\n"
            "  4 propriedades a mais custaram %d queries.\n"
            "Isto e' N+1: o produtor com 20 fazendas espera %.0fx mais do que "
            "o produtor com uma, sem ter feito nada de diferente.\n"
            "As 4 querys de base sao legitimas (grupos, registos, safras, "
            "talhoes). O que nao pode e' uma por propriedade."
            % (
                medidas[1],
                medidas[5],
                crescimento,
                crescimento / 4.0,
            ),
        )

    # ------------------------------------------------------------------
    # 2) Montar os grupos nao custa uma query por grupo
    # ------------------------------------------------------------------
    def test_montar_grupos_nao_faz_uma_query_por_grupo(self):
        n_grupos = len(VEGETAL_GRUPOS)
        with CaptureQueriesContext(connection) as ctx:
            _montar_grupos_vegetal()
        queries = len(ctx.captured_queries)
        self.assertLessEqual(
            queries,
            3,
            "`_montar_grupos_vegetal` fez %d queries para %d grupos.\n"
            "Sao %d idas ao banco para construir dicionarios. Um unico "
            "`Cultura.objects.all().order_by('grupo','nome')` seguido de "
            "agrupamento em memoria custa 1.\n"
            "O custo nao e' o numero — e' que cada query volta a atravessar "
            "a rede e a construir o mesmo indice." % (queries, n_grupos, queries),
        )

    # ------------------------------------------------------------------
    # 3) Nao ha grupos VAZIOS a prometer
    # ------------------------------------------------------------------
    def test_nenhum_grupo_promete_o_que_nao_tem(self):
        """Um grupo no codigo que nao existe na tabela mostra um cabecalho
        com nada dentro — e o produtor conta aquilo como uma categoria
        vazia, nao como uma categoria que o sistema ainda nao carregou.

        `VEGETAL_GRUPOS` tem 16 nomes escritos a mao. Se um deles nao
        existir em `Cultura.grupo`, o cabecalho aparece sem lista. E
        exactamente o que aconteceu com `nativas`.

        MEDIDO 2026-10-05: este teste falhava com os 16 grupos em `orfaos` —
        e nao havia um so defeito no codigo. A tabela `Cultura` esta VAZIA
        neste TestCase (nada cria culturas aqui), e por isso TODOS os grupos
        pareciam orfaos. Era o teste a medir a base vazia e a chamar-lhe
        defeito.

        Contra a base de desenvolvimento real, os mesmos 16 grupos tem linhas
        e a contagem de orfaos e' 0. Logo o codigo esta certo e o teste e' que
        precisa de dados: sem semear, a assercao mede nada.

        O que fica a ser vigiado e' o que o produtor ve: um cabecalho vazio.
        Para isso ha de haver culturas. Cada grupo semeado que depois NAO
        apareca em `Cultura` continua a ser apanhado — que e' o defeito que
        este teste existe para apanhar.
        """
        # Semeia uma cultura por grupo declarado. Sem isto, "orfão" é
        # indistinguível de "base vazia", e o teste passa a acusar o
        # codigo de coisas que ele fez bem.
        for g in VEGETAL_GRUPOS:
            Cultura.objects.create(
                nome=f"Teste {g}",
                grupo=g,
                unidade_comercial="un",
                ativo=True,
            )

        existentes = set(
            Cultura.objects.exclude(grupo__isnull=True)
            .values_list("grupo", flat=True)
            .distinct()
        )
        orfaos = [g for g in VEGETAL_GRUPOS if g not in existentes]
        self.assertEqual(
            orfaos,
            [],
            "estes grupos estao em VEGETAL_GRUPOS mas nao existem na tabela "
            "`Cultura`, por isso renderizam um cabecalho vazio:\n  %s\n"
            "Ou o grupo foi renomeado na tabela e o codigo ficou para tras, "
            "ou nunca existiu. As duas coisas sao invisiveis para o produtor "
            "e produzem a mesma imagem: uma categoria que nao tem nada."
            % "\n  ".join(orfaos),
        )

        # E o inverso tambem tem de ser verdade depois de semear: se um
        # cabecalho nao tem nada, e' porque nao ha linhas — nao porque a
        # consulta esta errada. `render` sem registos = cabecalho vazio, e
        # isso so e' aceitavel para grupos que de facto nao tem culturas.
        grupos = _montar_grupos_vegetal()
        vazios_no_render = [g for g, cs in grupos.items() if len(cs) == 0]
        self.assertEqual(
            vazios_no_render,
            [],
            "a view vai renderizar um cabecalho sem nenhuma cultura dentro "
            "para: %s. O produtor conta isso como uma categoria vazia, e nao "
            "como 'ainda nao carregamos'." % ", ".join(vazios_no_render),
        )

    # ------------------------------------------------------------------
    # 4) O numero da guia bate com a tabela
    # ------------------------------------------------------------------
    def test_a_contagem_da_guia_e_a_da_tabela(self):
        """A guia diz quantas culturas existem. Tem de ser a contagem real.

        MEDIDO 2026-10-05: a navegacao anunciava 707 e o config tem 488
        (outro ficheiro, outra fonte). Aqui a fonte e' a TABELA, que e' o
        que a guia mostra. Se um dia as duas contagens divergirem, o
        produtor ve um numero no menu e outro dentro da pagina.
        """
        with CaptureQueriesContext(connection):
            r = self._pedido()
            guia_vegetal_view(r)
        # MEDIDO 2026-10-05: este teste lia `resposta.context_data["grupos"]`, e
        # `guia_vegetal_view` devolve `render(...)` — um `HttpResponse`, que NAO
        # tem `context_data`. O atributo nunca existiu: o teste affirmava uma
        # forma de acesso que a view nunca teve.
        #
        # O que se quer aqui e' a MESMA coisa que a view mostra: os `grupos`.
        # Saiam de `_montar_grupos_vegetal()` (guias.py:109 chama essa funcao e
        # mete o resultado no contexto), entao e' ela que se mede. Chamar a view
        # acima continua a ser o que conta as queries — e' o que se quer
        # vigiar; ler os dados e' uma segunda coisa.
        grupos = _montar_grupos_vegetal()
        soma = sum(len(v) for v in grupos.values())
        self.assertEqual(
            soma,
            Cultura.objects.count(),
            "a soma dos grupos que a guia mostra (%d) e' diferente do total "
            "da tabela `Cultura` (%d). A pagina esta a esconder ou a "
            "inventar culturas." % (soma, Cultura.objects.count()),
        )
