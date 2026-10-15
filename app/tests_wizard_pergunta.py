"""Um wizard não grava a própria pergunta, nem fabrica a data que não ouviu.

POR QUE ESTE FICHEIRO EXISTE
============================
`app/static/js/ia-local/ia-local.js` é JavaScript, e a suite Python não o
executa. Os defeitos abaixo são reais e Ninguém os apanhava: um wizard que
grava a mensagem do produtor num campo sem passar por `wizEhPergunta`, e um
passo que grava `wizHoje()` quando não sabe a data.

São as duas coisas que o `MERGED.md` classificou como P0 — *"a IA inventa
dados que parecem certos"* — e a razão pela qual são o achado mais perigoso
da lista: **não parecem erro**. Uma data de admissão plausível entra no
cadastro e ninguém a questiona durante meses. Um talhão chamado "como voces
chamam esse talhao?" é visível — mas o que propaga é o efeito: o talhão
errado entra em safras, aplicações, custo por hectare e rastreabilidade.

O QUE ESTE TESTE PROMETE, E O QUE NÃO PROMETE
=============================================
Promete: que a guarda `wizEhPergunta` está escrita **antes** da atribuição
em cada passo que grava texto livre, e que `wizHoje()` não é fallback de
nenhuma data.

Não promete: que o wizard funcione em runtime. Isso precisa de browser, e
um teste que precisa de browser para ser verdade é um teste que ninguém
corre. Estes testes são sobre o **texto do fonte** — e isso é honesto, e é
melhor do que nada.

A ordem importa e o teste verifica-a: uma guarda **depois** da atribuição
não guarda nada, porque o valor já está no campo quando o `if` corre.
"""

import re
from pathlib import Path

import pytest
from django.test import SimpleTestCase

RAIZ = Path(__file__).resolve().parent.parent
IA = RAIZ / "app" / "static" / "js" / "ia-local" / "ia-local.js"


def _linhas():
    return IA.read_text(encoding="utf-8", errors="replace").split("\n")


def _bloco_de_step(linhas, expr, max_linhas=45):
    """O bloco `if (x.step === '...')` até ao próximo `if (...step ===`.

    Uma janela de N linhas fixas mede o passo vizinho quando o ficheiro cresce
    — e foi exactamente o que aconteceu à primeira versão deste teste: com 40
    linhas apanhava `prod_data` e passava sem estar a medir `admissao`.

    Procura a **linha que abre o if**, não a que menciona: um comentário
    "ver a nota longa em `f.step === 'admissao'`" casa a busca e devolve o
    bloco errado — que é o que a segunda versão fazia.
    """
    padrao = re.compile(
        r"^\s*if\s*\(\s*\w+\.step\s*===\s*" + re.escape(expr) + r"\s*\)\s*\{"
    )
    inicio = next((i for i, l in enumerate(linhas) if padrao.search(l)), None)
    if inicio is None:
        return None
    fim = min(len(linhas), inicio + max_linhas)
    for j in range(inicio + 1, fim):
        if re.search(r"if\s*\(\s*\w+\.step\s*===", linhas[j]):
            fim = j
            break
    return "\n".join(linhas[inicio:fim])


class WizzardNaoGravaAPerguntaTest(SimpleTestCase):
    """Cada `campo = t` tem de ter `wizEhPergunta` a olhar para a mesma frase."""

    maxDiff = None

    def _portas(self):
        linhas = _linhas()
        achados = []
        for i, linha in enumerate(linhas):
            m = re.match(r"^\s*(\w+)\.(\w+)\s*=\s*t;\s*$", linha)
            if not m:
                continue
            inicio = i
            for j in range(i, max(-1, i - 30), -1):
                if re.search(r"if\s*\(\s*\w+\.step\s*===", linhas[j]):
                    inicio = j
                    break
            achados.append((i + 1, m.group(1), m.group(2), linhas[inicio : i + 1]))
        return achados

    def test_existe_pelo_menos_uma_porta_para_auditar(self):
        """Se isto passa sem encontrar portas, o `ia-local.js` mudou de forma e
        o teste deixou de medir. Um guarda que não encontra nada é um guarda
        que não protege — e é o estado que dá a falsa confiança."""
        self.assertGreater(
            len(self._portas()),
            3,
            "esperava as portas de `campo = t;`; encontrei "
            f"{len(self._portas())}. O ficheiro mudou de forma e este teste "
            "deixou de medir.",
        )

    def test_nenhuma_porta_grava_a_pergunta_como_resposta(self):
        """`wizEhPergunta(t)` tem de estar no bloco, ANTES da atribuição."""
        # As guardas aceitaveis, por ordem de forall.
        #
        # MEDIDO 2026-10-04: este teste so aceitava a string `wizEhPergunta`,
        # e reprovava `wizNaoEhValor` — que e' `wizEhPergunta(t) ||
        # wizEhInstrucao(t)`, ou seja, **mais forte**. As linhas 2349 e 2672
        # (`f.nome`) estavam guardadas e o teste dizia "(sem guarda)".
        #
        # Um teste que falha uma correccao e' pior do que um teste que nao
        # existe:/traina a ignorar o sinal, e o proximo defecto real passa
        # por cima do "ja se complainou deste ficheiro".
        GUARDAS = ("wizEhPergunta", "wizNaoEhValor")

        sem_guarda = []
        for linha, variavel, campo, bloco in self._portas():
            texto = "\n".join(bloco)
            # A guarda tem de ser a ULTIMA antes da atribuicao: o que
            # interessa e' o que passou por ela, nao o que passou algures
            # acima no bloco.
            melhor = -1
            melhor_qual = None
            for guarda in GUARDAS:
                idx = texto.rfind(guarda)
                if idx > melhor:
                    melhor = idx
                    melhor_qual = guarda
            if melhor < 0:
                sem_guarda.append(
                    f"L{linha}  {variavel}.{campo}  (sem guarda de pergunta)"
                )
                continue
            linha_guarda = texto[:melhor].count("\n")
            if linha_guarda >= len(bloco) - 1:
                sem_guarda.append(
                    f"L{linha}  {variavel}.{campo}  (guarda DEPOIS da "
                    f"atribuicao; usa {melhor_qual})"
                )
        self.assertEqual(
            sem_guarda,
            [],
            "passos que gravam a mensagem do produtor sem passar por\n"
            "`wizEhPergunta(t)`. O produtor responde com a pergunta e o cadastro\n"
            "grava a pergunta:\n  " + "\n  ".join(sem_guarda),
        )

    def test_wiz_eh_pergunta_existe_e_esta_definida(self):
        """Se alguém a apagar, os 16 usos ficam `undefined is not a function`
        em produção — e isso só aparece no browser."""
        self.assertIn(
            "function wizEhPergunta",
            "\n".join(_linhas()),
            "`wizEhPergunta` nao existe — e ha 16 sitios que a usam.",
        )


class WizzardNaoFabricaDataTest(SimpleTestCase):
    """`wizHoje()` como fallback de uma data é uma medição fabricada.

    O padrão que se procura é `x.data = d.length ? d[0] : wizHoje();`. A
    correção certa não é inventar outro valor — é **perguntar**.
    """

    def _linhas_vivas(self):
        """Só as linhas que não são comentário. Um `wizHoje()` numa nota
        explicativa é documentação; o mesmo `wizHoje()` em código vivo é um
        bug. Confundir os dois torna o teste inútil nos dois sentidos."""
        return [l for l in _linhas() if not l.strip().startswith("//")]

    def test_wizhoje_nao_e_fallback_de_nenhuma_data(self):
        vivas = "\n".join(self._linhas_vivas())
        self.assertNotIn(
            ": wizHoje()",
            vivas,
            "`wizHoje()` voltou a ser fallback de um campo de data. Uma data "
            "que o produtor nao disse e' uma medicao fabricada — e entra em "
            "custo de producao, DRE e rastreabilidade.",
        )

    def test_o_passo_admissao_pergunta_quando_nao_entende(self):
        bloco = _bloco_de_step(_linhas(), "'admissao'")
        self.assertIsNotNone(
            bloco, "o passo `admissao` do wizard de funcionario nao existe"
        )
        self.assertIn(
            "Nao encontrei a data",
            bloco,
            "quando a data nao e' legivel, o passo tem de PERGUNTAR de novo.",
        )
        # "pular" NAO pode ser oferecido aqui, e oferecer era o erro.
        #
        # `Funcionario.data_admissao` e' `models.DateField()` sem `null=True`
        # e sem `blank=True` (app/models/equipe.py:296) — logo e' NOT NULL. Um
        # "pular" deixaria o campo em branco, o POST voltaria com 400, e o
        # produtor ficaria a ver uma pergunta cuja saida declarada nao existe.
        # A saida honesta e dizer que o campo e' obrigatorio.
        #
        # Este teste foi corrigido por OUTRA sessao depois de escrever: a
        # primeira versao exigia "pular", que era o comportamento errado.
        self.assertIn(
            "obrigatorio",
            bloco,
            "a pergunta tem de dizer que o campo e' obrigatorio — `pular` "
            "nao pode funcionar num campo NOT NULL, e oferecer uma saida que "
            "da 400 e' pior que nao oferecer saida nenhuma.",
        )
        # O `wizHoje()` nao pode estar no CODIGO do passo. Esta mede codigo:
        # o comentario que explica a correccao CITA o `wizHoje()` antigo, e um
        # teste que mede prosa em vez de codigo falha com "voltou a fabricar"
        # quando o que voltou foi a frase que documenta a correccao. Mesma
        # classe de erro que `_corpo_sem_docstring` em Python.
        codigo = "\n".join(
            l for l in bloco.split("\n") if not l.strip().startswith("//")
        )
        self.assertNotIn(
            ": wizHoje()",
            codigo,
            "o passo `admissao` voltou a fabricar a data de hoje.",
        )

    def test_o_passo_data_do_aquatico_pergunta_quando_nao_entende(self):
        """O passo do povoamento. Este grava **e faz POST** — um `wizHoje()`
        aqui fabricava a data de povoamento de um lote inteiro."""
        linhas = _linhas()
        alvo = None
        for i, l in enumerate(linhas):
            if l.strip() == "if (q.step === 'data') {":
                alvo = i
                break
        self.assertIsNotNone(
            alvo, "o passo `data` do wizard aquatico nao existe (linha 'q.step')"
        )
        bloco = "\n".join(linhas[alvo : alvo + 30])
        self.assertIn(
            "Nao encontrei a data",
            bloco,
            "o povoamento sem data legivel tem de PERGUNTAR, e oferecer "
            "`pular` — nao assumir hoje.",
        )
        self.assertIn("pular", bloco)

    def test_o_passo_desp_data_pergunta_quando_nao_entende(self):
        """A despesca. Uma despesca sem data legível não é uma despesca de
        hoje — é uma despesca sem data."""
        bloco = _bloco_de_step(_linhas(), "'desp_data'")
        self.assertIsNotNone(bloco, "o passo `desp_data` do wizard aquatico nao existe")
        self.assertIn("Nao encontrei a data", bloco)
        self.assertIn("pular", bloco)


def _corpo_sem_docstring(fonte):
    """O corpo da função, sem a docstring.

    O docstring de `h_concluir_tarefa` cita o `.first()` antigo **para
    explicar porque o tirou**. Um teste que procura essa string no
    `inspect.getsource` inteiro casa com a explicação e falha — e a falha
    diz "voltou" quando o que voltou foi a frase que o documenta. Medir o
    código e não a prosa sobre o código.
    """
    return fonte.split('"""', 2)[-1]


# MEDIDO 2026-10-05. `test_o_intent_nao_tem_cache` verifica que
# `concluir_tarefa` esta em `sandbox.INTENTS_NAO_CACHEAVEIS` — ou seja, mede a **decisao de
# nao cachear**, que e' o objecto do teste. A fixture `limpar_cache_entre_testes`
# do `conftest.py` (autouse) foi criada para acabar com a contaminacao de
# ordem e nao interfere com a leitura de um frozenset estatico — mas o marker
# deixa a intencao explicita, para que ninguem remova a fixture por achar que
# e' ela que quebra este teste.
@pytest.mark.keep_cache
class ConcluirTarefaNaoEscreveSemConfirmacaoTest(SimpleTestCase):
    """`concluir_tarefa` escrevia por substring, sem `needs_confirm`.

    Este é o caminho que contorna o gate de `sandbox.py`: o gate existe, e
    está bem feito — mas só governa quem passa por ele. Um intent que escreve
    por fora não tem confirmação nem linha em `IAExecucao`.
    """

    def test_o_intent_exige_confirmacao(self):
        from app.ia.registro import REGISTO

        spec = REGISTO.get("concluir_tarefa")
        self.assertIsNotNone(spec, "o intent `concluir_tarefa` nao esta no registo")
        self.assertTrue(
            spec.get("requires_confirmation"),
            "um intent que CONCLUI uma tarefa tem de pedir confirmacao. O gate "
            "de `sandbox.py` existe, mas so para intents com "
            "`requires_confirmation` — e este nao tinha.",
        )

    def test_o_intent_nao_tem_cache(self):
        from app.ia.sandbox import INTENTS_NAO_CACHEAVEIS

        self.assertIn(
            "concluir_tarefa",
            INTENTS_NAO_CACHEAVEIS,
            "um intent que escreve nao pode ter TTL: o segundo pedido "
            "repetiria a escrita.",
        )

    def test_a_ambiguidade_pergunta_em_vez_de_escolher(self):
        """`icontains` + `.first()` fecha a tarefa errada sem o produtor ver.

        O caso que mata: "concluí a pulverização" com "Pulverização de
        herbicida" e "Repulso de pulverização" pendentes. `.first()` devolve
        uma das duas sem o produtor saber qual, e a resposta é escrita depois
        da escrita — logo não pode avisar.

        A resposta certa é `ok: false` com a lista. Um `ok: true` a completar
        a tarefa errada é pior do que um erro: o modelo repete, o produtor vê
        a peça antiga e ninguém percebe porquê — a lição de `registro.py`.
        """
        import inspect

        from app.ia import intents as mod

        corpo = _corpo_sem_docstring(inspect.getsource(mod.h_concluir_tarefa))
        self.assertIn(
            "candidatos",
            corpo,
            "o handler tem de distinguir 'casa com uma' de 'casa com varias'. "
            "Sem isso, `.first()` decide por quem a tarefa e.",
        )
        self.assertNotIn(
            't = qs.filter(nome__icontains=params["titulo"]).first()',
            corpo,
            "o `.first()` directo sobre `icontains` voltou — e e' a escolha "
            "silenciosa que fecha a tarefa errada.",
        )
