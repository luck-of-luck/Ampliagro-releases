"""Todos os intents de escrita perigosa pedem confirmacao antes de escrever.

A REGRA
=======
`app/ia/intents3.py:5` diz, em uma linha: **"toda escrita tem
`requires_confirmation`"**. E `intents.py:1644` tem o comentario que explica
porque a regra existe — `h_concluir_tarefa` casa a tarefa por **substring**
(`nome__icontains`) e depois faz `t.concluida = True`. Sem o gate, a escrita
acontece antes de `sandbox.py:516` poder perguntar.

Isto e' mais perigoso do que parece:

    "concluir a tarefa de adubar o milho"
    "concluir a tarefa de adubar o milho e plantar soja"

O segundo nome e' uma **substring** do primeiro. `icontains` casa o talhao
errado — e o gate de confirmacao e' a unica coisa que estava entre a frase do
produtor e o `UPDATE` na fazenda errada. Um intent de escrita que casa por
substring sem gate e' o `sandbox.py` inteiro contornado.

PORQUE QUE ESTE TESTE NAO E' "NENHUM ESCRITA SEM GATE"
========================================================
Porque essa formulacao e' a correccao ingenua, e ela esta errada.

MEDIDO 2026-10-04: sete intents de escrita nao declaram `requires_confirmation`.
A correccao ingenua e' meter um gate em todos. Isso e' **pior** em dois
casos:

`emitir_alerta_proativo` — cria UM alerta. E' o que o produtor precisa de
ver AGORA. Um gate aqui e' um atraso entre o acontecimento e o aviso, e o painel
inunda-se de pedidos de confirmacao que o produtor ja respondia com "sim".

`feedback` — guarda uma opiniao sobre a IA. O pior caso e' um texto de
prompt numa tabela de opinioes. Nao ha o que confirmar.

O que separa um gate que protege de um gate que atrapalha e' **o que acontece
se errar**, e nao o facto de o intent escrever:

    reversivel   -> apagar desfaz. Gate e' nice-to-have.
    acumulativo  -> cada execucao soma. Gate e' obrigatorio: sem ele, N
                    execucoes fazem dano cumulativo que ninguem desfaz.
    externo      -> escreve FORA da fazenda (um device, um endpoint). Gate
                    e' obrigatorio, e o aviso tem de dizer o que mudou.

Este e' o mesmo principio que o relatorio aplica ao `.catch(function(){})`
do `data-sync.js`: um erro visivel corrige-se, um erro silencioso propaga-se.
E o mesmo que `intents3.py` aplica ao resto do registo.

O QUE ESTE TESTE FAZ
====================
Afirma que **os intents de gravidade `externo` e `acumulativo`** tem gate.
Estes sao os que naoYNao devem ficar sem gate, e a lista esta medida em
`scratch/gravidade_intents.py`.

NAO FAZ, E PORQUEM NAO
======================
Nao chama handlers. Nao cria objectos. So mede a **declaracao** do registo.

E nao exige gate nos reversiveis porque essa e' uma **decisao de produto**,
nao uma verdade tecnica. Quem decide se `criar_entidade` pergunta ao
produtor e' quem conhece o produto; o que este teste garante e' que a pergunta
**nao pode ser esquecida** nos casos em que errar tem consequencia.
"""

from django.test import SimpleTestCase

from app.ia.intents import INTENTS

#: Gravidade que obriga a gate. Medidas em `scratch/gravidade_intents.py`,
#: onde cada uma tem o porque escrito ao lado do nome.
SOB_GUARDA_OBRIGATORIA = {
    # EXTERNO — escreve fora da fazenda.
    # Errou o alvo, um sensor passa a reportar para a conta errada e continua
    # a reportar ate alguem reparar. E' a razao de o §VI do manifesto Agro 5.0
    # falar em Zero-Trust: a garantia e' sobre o dispositivo, e nao ha gate.
    "provisionar_endpoint_iot",
    "revogar_endpoint_iot",
    # ACUMULATIVO — e o produtor NAO pediu cada execucao.
    # Ligar a proatividade poe `emitir_alerta_proativo` a correr em ciclo, e
    # ai nao ha gate porque o ciclo e' precisamente o que se autorizou.
    "ligar_proatividade",
}

#: Intent de escrita SEM gate, por decisao medida, nao por esquecimento.
#:
#: `emitir_alerta_proativo` e' o caso que obriga a escrever esta lista. A
#: correccao ingenua — "toda escrita pergunta" — partiria aqui, e partia MAL:
#:
#:   1. Este intent e' a SAIDA do motor proativo. `proativo_tasks.py:20` diz
#:      que o resultado volta por `amplia_emitir_alerta_proativo`, "a MESMA
#:      porta governada". Um gate aqui transformava cada alerta em pedido de
#:      confirmacao — e o produtor teria de autorizar, um a um, os avisos que
#:      ELE MESMO LIGOU para receber. E' aConfirmar que nao se quer.
#:
#:   2. O accumulation que este intent tem JA TEM TETO, e medido:
#:      `proativo.py:77 MAX_USUARIOS_POR_VARRAGURA = 100`,
#:      `proativo.py:82 MAX_ALERTAS_FROTA_POR_VARRAGURA = 50`, e
#:      `proativo.py:455 pode_emitir()` com dedup por fingerprint + teto
#:      diario + teto semanal. `proativo_tasks.py:36-48` chama a isto "o que
#:      impede o loop" e lista os tres.
#:
#: Ou seja: o dano que um gate evitaria aqui ja esta travado por tres tetos
#: independentes, e o custo do gate seria transformar o motor proativo num
#: incitante de pedidos de confirmacao.
#:
#: A asymetria com `ligar_proatividade` e' o ponto: LIGAR o motor pergunta.
#: EMITIR o resultado de o motor estar ligado, nao. A pergunta e' uma vez, e
#: e' sobre o efeito que dura — nao sobre cada iteracao.
ESCRITA_GUARDADA_POR_TETOS = {
    "emitir_alerta_proativo",
}


def _escreve(flags) -> bool:
    """Este intent muda estado?

    Uma flag que acaba em `.write` escreve. Uma flag de leitura
    (`pecuaria.read`) nao escreve, mesmo que o handler faca um `create` — e
    se algum fizer, isso e' um achado que a coerencia do MCP apanha, nao
    este.
    """
    return any(f.endswith(".write") for f in flags)


class EscritaPerigosaPerguntaTest(SimpleTestCase):
    def test_todo_intent_externo_tem_gate(self):
        """Escrever FORA da fazenda sem o produtor ver e' o caso grave.

        Um endpoint de telemetria errado nao se desfaz sozinho: o sensor
        continua a mandar para o sitio errado. E o produtor nao tem nenhuma
        forma de saber, porque do ponto de vista dele o sistema funciona.
        """
        sem_gate = [
            nome
            for nome in sorted(SOB_GUARDA_OBRIGATORIA)
            if nome in INTENTS
            and INTENTS[nome].get("flags")
            and _escreve(INTENTS[nome]["flags"])
            and not INTENTS[nome].get("requires_confirmation")
        ]
        self.assertEqual(
            sem_gate,
            [],
            f"intents que escrevem FORA da fazenda sem gate: {sem_gate}\n\n"
            "Um endpoint IoT provisioned ou revoked no alvo errado nao se "
            "desfaz: o sensor continua a reportar para a conta errada, ou "
            "cala, e o produtor nao tem como saber. O gate aqui nao e' "
            "formalidade — e' a unica coisa entre a frase e o dispositivo.",
        )

    def test_todo_intent_acumulativo_tem_gate(self):
        """Cada execucao soma e o dano nao tem rollback — mas so ate LIGAR.

        Este e' o caso onde a correccao ingenua estragava o produto.
        `emitir_alerta_proativo` cria um alerta por execucao e parece o mesmo
        caso que `ligar_proatividade`. Nao e':

        `ligar_proatividade` e' o PRODUTOR a pedir um efeito que dura, e por
        isso pergunta. `emitir_alerta_proativo` e' o motor a entregar um
        resultado que o produtor JA autorizou quando ligou — e o seu
        accumulation ja tem tres tetos medidos (`proativo.py:77`, `:82`,
        `:455`). Um gate aqui transformava cada aviso num pedido de
        confirmacao, e o produtor teria de autorizar um a um os alertas que
        ele mesmo ligou para receber.
        """
        acumulativos = {"ligar_proatividade"}
        sem_gate = [
            nome
            for nome in sorted(acumulativos)
            if nome in INTENTS
            and INTENTS[nome].get("flags")
            and _escreve(INTENTS[nome]["flags"])
            and not INTENTS[nome].get("requires_confirmation")
        ]
        self.assertEqual(
            sem_gate,
            [],
            f"intents ACUMULATIVOS sem gate: {sem_gate}\n\n"
            "Ligar o motor poe `emitir_alerta_proativo` a correr em ciclo. "
            "A pergunta e' sobre o EFEITO que dura, e e' feita uma vez — nao "
            "sobre cada iteracao. Ver ESCRITA_GUARDADA_POR_TETOS.",
        )

    def test_a_escrita_guardada_por_tetos_realmente_tem_tetos(self):
        """A excepcao so vale se os tetos existirem.

        Este e' o teste que impede a excepcao de ficar so escrita.
        `emitir_alerta_proativo` fica sem gate porque `proativo.py` tem teto
        de frota, teto diario e teto semanal. Se um dia esses tetos forem
        removidos, o intent tem de voltar a perguntar — e este teste falha no
        dia em que isso acontecer, em vez de seis meses depois.
        """
        import app.ia.proativo as P

        for nome in (
            "MAX_USUARIOS_POR_VARRAGURA",
            "MAX_ALERTAS_FROTA_POR_VARRAGURA",
        ):
            self.assertTrue(
                hasattr(P, nome) and getattr(P, nome) > 0,
                f"`proativo.{nome}` desapareceu. `emitir_alerta_proativo` "
                "justifica nao ter gate porque tem teto; sem o teto, volta a "
                "precisar de `requires_confirmation`.",
            )
        self.assertTrue(
            callable(getattr(P, "pode_emitir", None)),
            "`proativo.pode_emitir` desapareceu — e' o dedup por fingerprint "
            "com teto diario e semanal, a segunda barreira do motor. Ver "
            "proativo_tasks.py:36-48.",
        )
        self.assertTrue(
            ESCRITA_GUARDADA_POR_TETOS & set(INTENTS),
            "a lista de excepcoes esta vazia ou aponta para intents "
            "inexistentes. Se `emitir_alerta_proativo` foi apagado ou "
            "renomeado, a justificativa desta excepcao caiu com ele.",
        )

    def test_a_lista_medida_bate_com_o_registro(self):
        """A lista de gravidade nao pode ter intents que nao existem.

        Um nome apagado do registo e' a forma mais facil de um teste de
        guarda passar a verde sem proteger nada. Este teste falla se a
        lista e' do registo divergirem — em qualquer sentido.
        """
        inexistentes = sorted(set(SOB_GUARDA_OBRIGATORIA) - set(INTENTS))
        self.assertEqual(
            inexistentes,
            [],
            f"a lista de gravidade cita intents que nao existem: "
            f"{inexistentes}. Ou o intent foi renomeado (e a proteccao "
            "desapareceu com ele), ou a lista esta desatualizada.",
        )

    def test_todo_intem_com_gate_tem_pergunta(self):
        """Gate sem pergunta nao confirma — atrasa.

        `intents.py:1631` tem `prompt_confirmacao` no `concluir_tarefa`: o
        texto que o produtor ve antes de autorizar. E' esse texto que faz do
        gate uma confirmacao em vez de um atraso — e um gate sem ele obriga a
        confirmar sem saber o que se esta a confirmar.
        """
        sem_pergunta = [
            nome
            for nome, spec in sorted(INTENTS.items())
            if spec.get("requires_confirmation")
            and not (spec.get("prompt_confirmacao") or "").strip()
        ]
        self.assertEqual(
            sem_pergunta,
            [],
            f"intents com gate e sem `prompt_confirmacao`: {sem_pergunta}\n\n"
            "O gate existe mas nao diz ao produtor o que vai acontecer. "
            "Confirmar sem saber o que se confirma nao e' confirmacao.",
        )

    def test_todo_intem_de_escrita_tem_handler(self):
        """Uma escrita sem handler nao escreve — e nao sabe.

        Um `spec` com flag de escrita e `handler: None` nao e' um intent
        inerte: o `sandbox` pode despacha-lo como "executado" e o produtor
        ve um sucesso que nao aconteceu. E' o mesmo formato de mentira do
        "salvo com sucesso" que o `data-sync.js` tinha.
        """
        sem_handler = [
            nome
            for nome, spec in sorted(INTENTS.items())
            if _escreve(spec.get("flags") or ()) and spec.get("handler") is None
        ]
        self.assertEqual(
            sem_handler,
            [],
            f"intents de ESCRITA sem handler: {sem_handler}. "
            "O sandbox pode despacho-los como executados.",
        )


class OSubstringNaoPodeEscolherAFazendaErradaTest(SimpleTestCase):
    """O caso concreto que `intents.py:1636` descreve, verificado por nome.

    Este nao mede o handler — mede que o unico intent que casa por substring
    tem o gate. A regra geral acima cobre os novos; este cobre O QUE JÁ
    EXISTE, e fica por nome porque o nome e' o que tem o handler.
    """

    def test_concluir_tarefa_manda_confirmar(self):
        spec = INTENTS.get("concluir_tarefa")
        self.assertIsNotNone(spec, "o intent `concluir_tarefa` desapareceu")
        self.assertTrue(
            spec.get("requires_confirmation"),
            "`concluir_tarefa` casa a tarefa por `nome__icontains` e depois "
            "escreve. Sem este gate, um nome que seja substring de outro "
            "fecha a tarefa errada — e nao ha erro para o produtor ver.",
        )
        self.assertTrue(
            (spec.get("prompt_confirmacao") or "").strip(),
            "o gate existe mas nao pergunta. Ver o motivo em intents.py:1631.",
        )
