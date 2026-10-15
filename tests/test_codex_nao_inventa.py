"""O Codex nao inventa datas, e nenhuma escrita acontece sem confirmacao.

DE ONDE VEM ISTO
================
Um relatorio de arquitectura afirmava que os "wizards" da IA de borda
fabricavam datas -- cinco instancias de `wizHoje()` em `ia-local.js`, uma por
campo. E afirmava que `concluir_tarefa` escrevia na base contornando o
`needs_confirm`.

VERIFIQUEI OS DOIS.

1. `wizHoje()` -- JA CORRIGIDO. As linhas citadas (2610, 2710, 2929) sao
   COMENTARIOS que documentam a correccao, escrevendo literalmente "o que nao
   pode voltar a acontecer e' o `wizHoje()`".

2. `concluir_tarefa` -- JA CORRIGIDO. Tem `requires_confirmation: True`, e um
   comentario que explica que o gate existe para intents com essa flag e que
   este nao tinha.

MAS ENCONTREI OUTRO. Escrevi um teste que percorre todos os intents a
escrever e pergunta "exiges confirmacao?". Quatro responderam que nao:

    criar_entidade          criador_livre.write
    inserir_registro        criador_livre.write
    emitir_alerta_proativo  proativo.write
    feedback                ml.write

E o mais grave: o handler `h_criar_entidade` tem um DOCSTRING que diz
"ESCRITA, e por isso pede confirmacao" -- e a ficha nao tinha a flag. A
intencao estava escrita; o codigo ficou de fora.

PORQUE ESTE FICHEIRO EXISTE
===========================
Porque uma correccao sem teste que a fixe NAO e' uma correccao -- e' uma
intencao. Daqui a um mes alguem faz um find/replace, o `wizHoje()` volta ao
fallback, e o payload passa a chamar-se `medido` outra vez. Nenhum scanner
apanha: um ternario com `wizHoje()` de fallback e' um bug silencioso e
PERFEITAMENTE VALIDO em JavaScript.

Estes testes leem o fonte. Nao e' a prova mais bonita, mas e' a que sobrevive
a um editor que nao sabe o que esta a fazer.
"""

import pathlib
import re

from django.test import SimpleTestCase

RAIZ = pathlib.Path(__file__).resolve().parents[1]
IA_JS = RAIZ / "app" / "static" / "js" / "ia-local" / "ia-local.js"

PADRAO_USO = r"(>|>=|<|<=)\s*wizHoje\(\)" r"|=\s*wizHoje\(\)" r"|\(\s*wizHoje\(\)\s*,"


def _linhas():
    return IA_JS.read_text(encoding="utf-8", errors="replace").splitlines()


class AiaNaoInventaDatasTest(SimpleTestCase):
    """`wizHoje()` pode ler o relogio. O que nao pode e' responder 'quando?'."""

    def test_nao_ha_ternario_com_wizhoje_como_fallback(self):
        """O padrao perigoso: `algo ? x : wizHoje()`.

        E' o que fazia "quando ele entrou?" devolver a data de hoje quando o
        produtor nao disse nada. Passava despercebida porque `wizHoje()` e' uma
        funcao perfeitamente legitima noutros contextos.
        """
        achados = []
        for i, l in enumerate(_linhas(), 1):
            s = l.strip()
            if s.startswith("//") or s.startswith("*"):
                continue
            if re.search(r"\?\s*[^:]{1,60}:\s*wizHoje\(\)", s):
                achados.append((i, s))
            if re.search(r"\|\|\s*wizHoje\(\)", s):
                achados.append((i, s))
        self.assertEqual(
            achados,
            [],
            "um `wizHoje()` voltou a ser o fallback de uma pergunta. Grava a "
            "data de HOJE num registo que o produtor nunca preencheu, e ela "
            "chega ao painel como `medido`: "
            + "; ".join(f"L{i} {s}" for i, s in achados),
        )

    def test_wizhoje_so_aparece_em_contexto_legitimo(self):
        """Onde ela PODE aparecer.

        Tres usos legitimos, todos medidos em `ia-local.js`:

        1. a DEFINICAO -- `function wizHoje() {` nao e' um uso, e' a origem
        2. COMPARACAO -- `if (dataIso > wizHoje())`, que REJEITA datas
           futuras. E' o oposto de inventar.
        3. ARITMETICA -- `wizSomarDias(wizHoje(), -1)`, dentro de
           `wizDataRelativa`, que so corre quando o produtor JA disse uma
           data.

        Um quarto uso, `algo = wizHoje()`, tambem e' legitimo: e' a atribuicao
        que alimenta a aritmetica do ponto 3.
        """
        legitimos = 0
        for l in _linhas():
            s = l.strip()
            if "wizHoje" not in s or s.startswith("//") or s.startswith("*"):
                continue
            if s.startswith("function wizHoje"):
                legitimos += 1
                continue
            if re.search(PADRAO_USO, s):
                legitimos += 1
            else:
                self.fail(f"uso de wizHoje() nao reconhecido: {s[:70]}")

        self.assertGreaterEqual(
            legitimos,
            6,
            "wizHoje() desapareceu ou mudou de forma. A comparacao de datas "
            "futuras (L1775, L2146) e a aritmetica de `wizDataRelativa` "
            "(L2263, L3631-3642) sao o que impede datas inventadas, e sao os "
            "usos legitimos. Se desapareceram, a proteccao foi com eles.",
        )

    def test_wizdatarerelativa_devolve_null_quando_nao_ha_data(self):
        """E' AQUI que a alucinacao acontecia.

        Medido em `ia-local.js:2259-2278`: a funcao parseia a data dita, usa
        `wizHoje()` como BASE para calcular "amanha" e "semana que vem", e
        termina em `return null`.

        O `return null` do fim E' a guarda. Sem ele, qualquer texto que nao
        mencionasse uma data devolveria a data de hoje.

        A primeira versao deste teste procurava `if (!t)`, que nao existe. A
        guarda e' o `return null`. Escrevi a partir do que supunha, nao do que
        li -- foi o mesmo erro do `_parse_value`.
        """
        L = _linhas()
        ini = next(i for i, l in enumerate(L) if "function wizDataRelativa" in l)
        fim = ini
        for j in range(ini + 1, min(ini + 30, len(L))):
            if L[j].rstrip() == "}":
                fim = j
                break
        corpo = "\n".join(L[ini : fim + 1])

        self.assertIn(
            "return null",
            corpo,
            "`wizDataRelativa` deixou de devolver `null` quando o produtor nao "
            "diz uma data. E' aqui que a alucinacao acontecia.",
        )
        h_idx = corpo.find("wizHoje()")
        guarda_idx = corpo.find("return null")
        self.assertGreater(
            guarda_idx,
            h_idx,
            "o `return null` tem de vir DEPOIS de `wizHoje()` -- senao a funcao "
            "devolve a data de hoje em vez de nada.",
        )


class EscritaSempreConfirmadaTest(SimpleTestCase):
    """Nenhum intent que escreve chega ao handler sem o produtor dizer 'sim'."""

    def test_todos_os_intents_que_escrevem_exigem_confirmacao(self):
        """A regra: se o intent tem flag de escrita, tem de ter confirmacao.

        `concluir_tarefa` foi o primeiro buraco deste tipo: tinha
        `tarefa.write` mas nao `requires_confirmation`, e o handler fazia
        `t.concluida = True`. O gate do sandbox so existe para intents com a
        flag -- sem ela, nao tinha por onde perguntar.

        Encontrei mais tres pelo mesmo teste: `criar_entidade`,
        `inserir_registro` e `emitir_alerta_proativo` gravavam schemas,
        registos e alertas sem perguntar nada.
        """
        from app.ia.intents import INTENTS

        violacoes = []
        for nome, ficha in INTENTS.items():
            flags = ficha.get("flags") or []
            escreve = any(
                f.endswith(".write") or f in ("escrita", "acao_fisica") for f in flags
            )
            if not escreve:
                continue
            if not ficha.get("requires_confirmation"):
                violacoes.append((nome, flags))
        self.assertEqual(
            violacoes,
            [],
            f"intents que escrevem sem exigir confirmacao: {violacoes!r}. Um handler "
            "desses corre ANTES de o gate poder perguntar alguma coisa.",
        )

    def test_os_quatro_corrigidos_tem_confirmacao(self):
        """Os quatro que eu corrigi, nome a nome."""
        from app.ia.intents import INTENTS

        for nome in (
            "criar_entidade",
            "inserir_registro",
            "emitir_alerta_proativo",
            "feedback",
        ):
            ficha = INTENTS.get(nome)
            self.assertIsNotNone(ficha, f"o intent {nome} desapareceu")
            self.assertTrue(
                ficha.get("requires_confirmation"),
                f"{nome} voltou a escrever sem confirmacao",
            )
            self.assertTrue(
                (ficha.get("prompt_confirmacao") or "").strip(),
                f"{nome} escreve sem prompt. `texto.py:113` cai entao na descricao, "
                "que e' escrita PARA O MODELO -- o produtor le a instrucao da "
                "maquina em vez do aviso.",
            )

    def test_concluir_tarefa_exige_confirmacao(self):
        """O caso concreto que o relatorio acusou."""
        from app.ia.intents import INTENTS

        ficha = INTENTS.get("concluir_tarefa")
        self.assertIsNotNone(ficha, "o intent concluir_tarefa desapareceu")
        self.assertTrue(
            ficha.get("requires_confirmation"),
            "concluir_tarefa voltou a escrever sem confirmacao. O handler faz "
            "`t.concluida = True` -- uma frase do produtor passa a facto.",
        )
