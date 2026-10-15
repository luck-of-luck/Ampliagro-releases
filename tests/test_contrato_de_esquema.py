"""Contrato de esquema: um campo que promete e ninguem le.

MEDIDO 2026-10-05 (agente 7). Este ficheiro existe por causa de **quatro bugs
da mesma familia**, que encontrei em dias diferentes sem se ligarem:

    1. `NotificacaoTemplate.canais` — JSONField, o help_text diz
       `Ex: ['push', 'email', 'whatsapp']`, e **nada no codebase iterava a
       lista**. O dispatcher mandava sempre `push`. Um template com
       `canais: ["email"]` registava no painel e nunca mandava email.

    2. `Propriedade.bioma` — seis biomas em `choices`, e
       `ComplianceAmbientalService` usava `percentual_exigido = 0.20`
       fixo, com um comentario a admitir o problema. O dado existia; o
       codigo nao o lia. Resultado: "Regular" numa propriedade da
       Amazonia que a lei exige com 80% de Reserva Legal.

    3. `LancamentoDetalhado` — o custo por talhao existia no modelo e o
       servico de custos nao o lia.

    4. `FotoNota.offline_id` — a ligacao foto->nota pelo `offline_id`
       estava especificada e nao implementada.

A raiz comum nao e' esquecimento. E' um **esquema desenhado antes da logica**,
e nada no projecto detecta a divaria. O campo tem `choices`, tem `help_text`,
aparece no admin, aparece no serializer, e portanto *parece* funcionar. O
produtor descobre que nao funciona quando precisa — que, num produto de campo,
e' a peor altura possivel.

O QUE ESTE TESTE FAZ
====================
Para cada campo que **promete** comportamento, procura em todo o codigo
(excepto migrations e admin) uma leitura. Se nao ha nenhuma, o campo e'
orfao de leitura: o esquema afirma uma capacidade que nao existe.

    promessa = JSONField                (nao tipado: nada obriga a ler)
            | tem `choices`            (vocabulario fechado = comportamento)
            | tem `help_text` util     (o help promete)

O TRIPICO DE HONESTIDADE DESTE FICHEIRO
=======================================
Um teste de "nao ha orfaos" falha de duas maneiras, e uma delas e' passar a
fazer nada:

    - um analisador partido que devolve zero orfaos faria o teste passar;
    - um baseline que so cresce e nunca encolhe torna-se um cemiterio.

Por isso ha quatro testes, e os dois do fim sao sobre o **analisador**, nao
sobre o schema:

    `test_o_analisador_encontra_um_orfao_inventado`  — planta um orfao e
        exige que seja encontrado. Se isto falha, os outros tres nao provam
        nada.

    `test_a_baseline_so_encolhe` — cada entrada da baseline tem de continuar
        orfa. Se alguem implementou a leitura e esqueceu de remover a entrada,
        o teste falha. Uma entrada que ja nao e' verdade e' mentira.

E a baseline guarda **o motivo** de cada orfao, para que a proxima pessoa
saiba se aquilo e' um esquecimento ou uma decisao.
"""

import pathlib
import re

from django.apps import apps
from django.db import models
from django.test import TestCase

RAIZ = pathlib.Path(__file__).resolve().parent.parent

#: Ficheiros que **nao** cumprem uma promessa. As migrations so' dizer que o
#: campo existe; o admin gera interface automaticamente. Nenhum dos dois e'
#: comportamento entregue ao produtor.
IGNORADOS = {"migrations", "admin.py", "__pycache__", ".venv", "node_modules"}

#: `app/models/` e' excluido, e esta e' a correccao mais importante deste
#: ficheiro.
#:
#: MEDIDO. A primeira versao dava **0 orfaos** — o que e' exactamente o modo
#: de falha que o `test_o_analisador_encontra_um_orfao_inventado` existe para
#: apanhar. Causa: o corpus de busca incluía `app/models/`, onde o campo esta
#: **declarado**. `area_rl` aparece em `AreaPreservacao.area_rl = ...`, isso
#: conta como correspondencia, e todo o campo casa consigo proprio. Um teste
#: que passa porque o analisador ve o que ele proprio escreveu nao prova nada.
#:
#: O custo: um campo lido apenas por um `save()`/propriedade no proprio modelo
#: passa a contar como orfao. Aceito — e' um falso positivo que o output do
#: teste mostra e alguem corrige, contra o falso negativo invisivel de antes.
IGNORADOS.add("models")

#: `fallback_data.py` e' 3.842 linhas de dados **inventados** que ja nao sao
#: servidos (ver `app/ia/tests_fallback_sem_invencao.py`). Fica de fora para
#: que os nomes das culturas la nao contem como "alguem leu este campo".
IGNORADOS.add("fallback_data.py")


def _ficheiros_do_corpus():
    """Todos os ficheiros onde uma promessa pode ser cumprida."""
    out = []
    for padrao in ("app/**/*.py", "app/**/*.html", "app/**/*.txt", "app/**/*.js"):
        for p in RAIZ.glob(padrao):
            partes = set(p.parts)
            if partes & IGNORADOS:
                continue
            out.append(p)
    return sorted(out)


def _codigo_do_projecto():
    """O texto do corpus. Separado de `_ficheiros_do_corpus` para os testes
    poderem verificar *que ficheiros* entram, e nao so o texto final."""
    out = []
    for p in _ficheiros_do_corpus():
        try:
            out.append(p.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
    return out


def _padroes(modelo: str, campo: str):
    """As escritas pelas quais um campo pode ser lido.

    Deliberadamente largo: `campo` nu cobre `obj.campo`, `data["campo"]`,
    `get(campo)`; `get_campo`/`set_campo` cobrem o acesso a chave que o
    `JSONField` costuma ter; `modelo__campo` cobre a travessia de relacao.

    E' largo de proposito. Um falso negativo (campo marcado como orfao
    despite ser lido) e' **barato**: aparece no output do teste e alguem
    corrige o nome. Um falso positivo (campo lido classificado como orfao) e'
    caro: obriga a manter entradas na baseline, e a baseline cresce ate
    deixar de valer alguma coisa.

    O LIMITE CONHECIDO, MEDIDO
    --------------------------
    A busca e' **por nome**, e nomes genericos em portugues dao falso
    negativo. MEDIDO: a primeira plantacao deste ficheiro usou um campo
    chamado `mes`, e o teste **nao** o apanhou — `mes` (e `mês`) aparece em
    dezenas de ficheiros, num `{% trans %}` ou numa frase de medico, e o
    padrao `\bmes\b` casa. Nao e' o detector a falhar: e' a limitacao do
    metodo, e e' por isso que `test_a_plantacao_e_apanhada` usa um nome
    inequivoco.

    Isto significa que **um orfao com nome comum passa**. Nao ha como
    resolver sem analise de fluxo de dados, que e' um projecto diferente. O
    que este teste garante e' a direccao que interessa: *campo novo, nome
    especifico, sem leitura* — que e' exactamente como os quatro bugs
    apareceram.
    """
    return (
        re.compile(r"\b%s\b" % re.escape(campo)),
        re.compile(r"\b%s__%s\b" % (re.escape(modelo.lower()), re.escape(campo))),
        re.compile(r"\b[gs]et_%s\b" % re.escape(campo)),
    )


def _campos_que_prometem():
    """(modelo, campo, motivo) para cada campo que promete comportamento."""
    achados = []
    for modelo in apps.get_models():
        if modelo._meta.app_label != "app":
            continue
        for f in modelo._meta.get_fields():
            if not getattr(f, "concrete", False):
                continue
            motivo = None
            if isinstance(f, models.JSONField):
                motivo = "JSONField: nada obriga a ler"
            elif f.choices:
                motivo = "choices: vocabulario fechado"
            elif f.help_text and len(f.help_text.strip()) > 12:
                motivo = "help_text promete comportamento"
            if motivo:
                achados.append((modelo.__name__, f.name, motivo))
    return sorted(achados)


def _orfaos(campos=None, textos=None):
    """Campos que prometem e nao tem leitura nenhuma no codigo."""
    campos = campos if campos is not None else _campos_que_prometem()
    textos = textos if textos is not None else _codigo_do_projecto()
    orfaos = []
    for modelo, campo, motivo in campos:
        padroes = _padroes(modelo, campo)
        if not any(any(p.search(t) for p in padroes) for t in textos):
            orfaos.append((modelo, campo, motivo))
    return sorted(orfaos)


#: Orfaos **conhecidos**, com o motivo. Baseline, nao desculpa.
#:
#: ESTE DICCIONARIO TEM DE ENCOLHER. Cada entrada aqui e' um orfao que
#: alguem ainda nao implementou. `test_a_baseline_so_encolhe` falha se uma
#: entrada deixar de ser verdade — implementar a leitura e' obrigatorio a
#: remover a entrada, ou o teste diz que fixaste algo que nao existe.
#:
#: Formato: "Modelo.campo" -> porque e' orfao.
#:
#: As entradas estao em duas familias, e a distincao importa porque se
#: resolvem de maneiras diferentes.
BASE_CONHECIDOS = {
    # ── FAMILIA A: o help_text promete um COMPORTAMENTO que nao existe ───
    #
    # O produtor le a ajuda, preenche o campo, e nada acontece. E' o bug
    # mais caro dos dois: ele **contou com aquilo**.
    "BiomassaEucalipto.volume_m3_ha": (
        "A help_text diz literalmente '<180 = alerta'. Nenhum alerta existe "
        "sobre biomassa: o campo e' lido por ninguem. Ou se implementa o "
        "limiar, ou a help_text deixa de prometer."
    ),
    "LancamentoFinanceiro.saldo_lcdpr": (
        "A help_text diz 'apenas para arquivo do LCDPR'. O servico de LCDPR "
        "calcula o saldo ele proprio e nunca le este campo: e' um numero que "
        "o produtor pode preencher errado sem que nada o contradiga."
    ),
    "AnaliseSolo.potassio_k": (
        "K e' nutriente maior. `recomendacao_solo.py` so' le `calcio_ca` e "
        "`aluminio_al` — K nunca chega a conta. A ferramenta "
        "`recomendacao_adubacao` anuncia que 'le analise de solo', e le duas "
        "colunas de cinco."
    ),
    "AnaliseSolo.magnesio_mg": (
        "Mesmo caso: Mg nunca entra na recomendacao. Junto a K, sao os dois "
        "nutrientes que faltam para a analise ter significado agronomico."
    ),
    "BovinoDigestao.abomaso_pct": (
        "Campo de referencia ('Abomaso 8% → total 4 estomagos'). Nao e' um "
        "erro: e' conhecimento estatico. Mas entao nao precisa de `choices` "
        "nem de `help_text` com promessa de calculo."
    ),
    "Agrofloresta.consorcio": (
        "Tem `choices` (consorcios validos) e ninguem valida contra elas. "
        "Aceita-se qualquer texto."
    ),
    # ── FAMILIA B: a help_text e' uma MANCHETE, nao documentacao ─────────
    #
    # Estas nao sao bugs de comportamento: o campo existe, e' lido ou nao, e
    # nao promete nada. O que e' errado e' o `help_text` ter sido usado como
    # um arquivo de recorte de imprensa do Globo Rural. Uma ajuda de schema
    # nao muda; estas mudam com a noticia.
    "Agrofloresta.investimento_bilhoes": (
        "FAMILIA B: a help_text e' a manchete 'Globo Rural 2026-09: "
        "agroflorestas atraem bilhetes'. Uma ajuda de campo nao e' uma "
        "edicao de jornal. O campo nao precisa dela."
    ),
    "CultivoOrquidea.livro_ref": (
        "FAMILIA B: help_text e' 'Livro \"como cultivarorquideas\" Globo Rural "
        "2026-09'. O mesmo problema: a documentacao do schema foi escrito por "
        "cima com conteudo de recorte."
    ),
    "PosColheitaJaca.mofada": (
        "FAMILIA B: help_text e' 'GR Responde: como evitar jaca mofada'. "
        "Nao e' documentacao de campo."
    ),
    "RestauracaoMombak.valor_rs": (
        "FAMILIA B: help_text e' 'Mombak R$1 bi Amazonia'. Manchete de "
        "mercado, nao documentacao."
    ),
    "ContaAReceber.cliente_doc": (
        "ENTROU na baseline a 2026-10-05. `ContaAReceber` ganhou o campo e "
        "ficou orfao de leitura. Nao e' um bug conhecido: e' um campo recem-"
        "criado cuja leitura ainda nao existe. Sai daqui quando alguem o ler."
    ),
    # ── RETIRADAS ──────────────────────────────────────────────────────
    #
    # `Agrofloresta.carbono_t` SAIU da baseline a 2026-10-05: passou a ter
    # leitura, e `test_a_baseline_so_encolhe` obrigou a remover a entrada. Uma
    # entrada que deixa de ser verdade e' pior do que nunca ter estado — faz o
    # ficheiro dizer "isto nao e' lido" sobre algo que ja e'.
    #
    # O valor de uma baseline e' ver as entradas desaparecerem. Por isso ha um
    # registo das que sairam, mesmo sem entrada:
    #
    #   Agrofloresta.carbono_t  -> implementada, entrada removida
    #
}


class InventarioTest(TestCase):
    def test_o_inventario_nao_e_vazio(self):
        """O corpus tem de ter campos a prometer, ou os testes sao vacuos.

        Se um dia `apps.get_models()` deixar de devolver modelos `app`, os tres
        testes abaixo passam a verde sem verificar nada. Este e' o alarme.
        """
        campos = _campos_que_prometem()
        self.assertGreater(
            len(campos),
            100,
            "o inventario colapsou. A deteccao de `app_label != 'app'`, ou um "
            "campo parou de ter help_text/choices e a promessa sumiu.",
        )

    def test_todo_o_inventario_tem_motivo(self):
        """Cada orfao sabe *porque* promete. Sem motivo, e' um achado sem dono."""
        for modelo, campo, motivo in _campos_que_prometem():
            with self.subTest(modelo=modelo, campo=campo):
                self.assertTrue(motivo.strip(), "campo listado sem motivo")


class OrfaosDeLeituraTest(TestCase):
    def test_nao_ha_orfao_fora_da_baseline(self):
        """O teste que este ficheiro existe para ter.

        Um `JSONField`, um campo com `choices` ou com um `help_text` que
        promete comportamento, e' lido por algum lado do codigo. Se nao e',
        o esquema afirma uma capacidade que nao existe — e o produtor descobre
        isso quando precisa.
        """
        orfaos = _orfaos()
        desconhecidos = [
            "%s.%s" % (m, c)
            for m, c, _ in orfaos
            if "%s.%s" % (m, c) not in BASE_CONHECIDOS
        ]

        self.assertEqual(
            desconhecidos,
            [],
            "campo(s) que prometem e ninguem le. Ou implementa a leitura, ou "
            "tira a promessa (help_text/choices) do schema, ou declara a "
            "excecao em BASE_CONHECIDOS com o motivo. Nao ha terceira via: um "
            "campo orfao e' uma capacidade que o produtor vai contar ter.\n"
            + "\n".join("  - %s" % d for d in desconhecidos),
        )

    def test_a_baseline_so_encolhe(self):
        """Cada entrada tem de continuar orfa.

        Sem este teste, `BASE_CONHECIDOS` e' um cemiterio: alguem implementa a
        leitura, esquece de remover a entrada, e o ficheiro continua a dizer
        "isto nao e' lido" sobre algo que ja e'. Uma baseline que mente e'
        pior do que nao ter baseline — porque esconde a correccao.
        """
        orfaos = {"%s.%s" % (m, c) for m, c, _ in _orfaos()}
        obsoletas = sorted(set(BASE_CONHECIDOS) - orfaos)

        self.assertEqual(
            obsoletas,
            [],
            "entrada(s) da baseline que ja nao sao orfaas: a leitura foi "
            "implementada. Remove a entrada — o teste diria que fixaste "
            "algo que nao existe.\n" + "\n".join("  - %s" % o for o in obsoletas),
        )

    def test_toda_a_basline_tem_motivo_escrito(self):
        """Uma excecao sem razao escrita e' uma excecao sem dono."""
        for chave, razao in BASE_CONHECIDOS.items():
            with self.subTest(chave=chave):
                self.assertIn(
                    ".",
                    chave,
                    "a chave tem de ser 'Modelo.campo', senao nao se sabe o "
                    "que e' que deixou de ser lido",
                )
                self.assertGreater(
                    len(razao.strip()),
                    40,
                    "motivo demasiado curto para justificar uma excecao",
                )


class OAnalisadorTest(TestCase):
    def test_a_plantacao_e_apanhada(self):
        """Prova de que o teste principal tem dentes, feita dentro da suite.

        A primeira versao plantava um campo chamado `mes` e **nao** era
        apanhada — `mes` casa com `{% trans %}`, com `mês`, com dezenas de
        frases de medico. A prova de dentes passou sem provar nada, e passou
        verde, que e' a pior forma de isso acontecer.

        Aqui o nome e' inequivoco, e o teste passa com a lista **nao vazia**.
        Se um dia `_orfaos` deixar de detectar orfaos, este falha — e falha
        antes de `test_nao_ha_orfao_fora_da_baseline` passar a verde por
        vacuidade.
        """
        orfaos = _orfaos(
            campos=[("Qualquer", "zz_campo_inequivoco_de_teste", "sintetico")],
            textos=["nada aqui menciona o campo"],
        )
        self.assertEqual(
            [c for _, c, _ in orfaos],
            ["zz_campo_inequivoco_de_teste"],
            "um orfao inequivoco nao foi detectado. Os testes de orfaos "
            "passam a verde sem verificar nada.",
        )

    """Os testes que auditam o analisador.

    Um teste de "nao ha orfaos" passa de duas maneiras, e uma delas e' passar
    a nao fazer nada. Estes dois fecham o impossivel.

    MEDIDO. A primeira versao deste ficheiro dava **zero** orfaos com 260
    campos no inventario — porque o corpus de busca incluía `app/models/`,
    onde o campo casa com a sua propria declaracao. Os testes de "nao ha
    orfaos" e "a baseline so encolhe" passavam, ambos, sobre um analisador
    cego. Este e' o teste que teria apanhado isso.
    """

    def test_o_analisador_encontra_um_orfao_inventado(self):
        """Planta um orfao sintetico e exige que seja encontrado.

        Se isto falha, nenhum dos testes de cima prova nada: um analisador que
        devolve sempre lista vazia passa "nao ha orfaos" e "a baseline so
        encolhe" sem olhar para o schema.
        """
        orfaos = _orfaos(
            campos=[("Agrofloresta", "zz_planta_sintetica_aaa", "sintetico")],
            textos=["# este ficheiro nao menciona o campo"],
        )
        self.assertEqual(
            [c for _, c, _ in orfaos],
            ["zz_planta_sintetica_aaa"],
            "o analisador deixou passar um orfao plantado: estao cegos, e os "
            "testes de cima sao vacuos.",
        )

    def test_o_analisador_encontra_um_campo_que_e_lido(self):
        """O outro lado: um campo que 'e' lido nao pode ser orfao.

        Sem este, um analisador que classificasse *tudo* como orfao tambem
        passaria o teste anterior, e o baseline cresceria ate ser inutil.
        """
        orfaos = _orfaos(
            campos=[("Agrofloresta", "carbono_t", "sintetico")],
            textos=["def f(o):\n    return o.carbono_t\n"],
        )
        self.assertEqual(
            orfaos,
            [],
            "o analisador marcou como orfao um campo que o codigo le em "
            "`.campo_t`. A deteccao e' demasiado agressiva.",
        )

    def test_o_corpus_nao_inclui_as_declaracoes_dos_models(self):
        """A correccao que este ficheiro precisa, em forma de teste.

        `area_rl = models.DecimalField(...)` **nao e' ler** `area_rl`. E' o que
        fez a primeira versao devolver zero orfaos sobre 260 campos: o corpus
        de busca incluía `app/models/`, e todo o campo casava com a sua propria
        declaracao. Os outros dois testes passavam, ambos, sobre um analisador
        cego.

        Este teste fixa a exclusao. Se alguem tirar `"models"` de `IGNORADOS`
        — achando que e' mais correcto —, este falha antes de o resto ficar
        silenciosamente verde.
        """
        self.assertIn(
            "models",
            IGNORADOS,
            "`models` tem de estar em IGNORADOS: e' onde o campo e' "
            "DECLARADO, nunca onde e' lido.",
        )

        ficheiros = _ficheiros_do_corpus()
        em_models = [f for f in ficheiros if "models" in f.parts]
        self.assertEqual(
            em_models,
            [],
            "o corpus inclui ficheiros de app/models/: toda a declaracao de "
            "campo passa a contar como leitura, e os testes ficam vacuos.",
        )

    def test_o_corpus_inclui_o_codigo_que_cumpre_promessas(self):
        """O outro lado: excluir `models/` nao pode esvaziar o corpus.

        Um corpus vazio da "nao ha orfaos" a verde por omissao — o mesmo modo
        de falha pelo outro lado.
        """
        ficheiros = _ficheiros_do_corpus()
        self.assertGreater(
            len(ficheiros),
            100,
            "o corpus do analisador esta vazio ou quase. Ou o glob esta "
            "errado, ou `IGNORADOS` comeu coisas de mais.",
        )
        em_views = [f for f in ficheiros if "views" in f.parts]
        em_services = [f for f in ficheiros if "services" in f.parts]
        self.assertTrue(em_views and em_services, "o corpus perdeu views/ ou services/")
