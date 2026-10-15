"""copiloto.py — o que distingue um copiloto de um chatbot.

O PEDIDO, NA PALAVRAS DO PRODUTOR
=================================
    "vai chover hoje?"  ->  "Sim, a chance e de xx%. E ha uma aplicacao de
                            pesticida marcada para quinta. Quer remarcar?"

O que existe hoje, e porque nao chega
=====================================
A regra que acha a aplicacao que a chuva estraga **ja existe**:
`app/ia/proativo.py::regras_deterministicas`. Ela cruza tarefas de aplicacao
com a previsao, e produz um alerta com nivel, evidencia e tudo.

Mas essa regra vive num **worker**. Ela empurra um alerta para um feed, e o
produtor tem de ir buscar. E o `sandbox` nunca a chama — medido: a palavra
"proativo" não aparece em `sandbox.py`.

O resultado é um sistema que sabe do problema e não fala dele na altura
certa. O produtor pergunta do tempo, recebe a temperatura, e a aplicação de
glifosato de quinta fica a lavar-se sem ninguém lhe dizer.

O QUE ESTE MÓDULO FAZ
=====================
Chama a regra **quando o produtor pergunta**, e traduz o achado numa
pergunta directa — não num alerta. A diferença entre os dois não é o
conteúdo: é que um alerta diz "houve um problema" e uma pergunta diz
"queres que eu arrume?". A segunda é um copiloto.

POR QUE NÃO COPIAR A REGRA
==========================
Porque a regra é difícil e já está escrita. `regras_deterministicas` tem a
janela de dias, os limiares de chuva em milímetros e em probabilidade, o
filtro de tarefas concluídas, e o cuidado de não alertar sobre trabalho
já feito — porque "alertar sobre tarefa concluída é o alarme que faz o
produtor desligar a notificação". Duplicar isso aqui seria ter duas
respostas à mesma chuva, e a divergem entre elas.

O QUE NÃO ESTÁ NESTE MÓDULO
============================
Não decide o que fazer. Não remarca nada. **Pergunta** — e a resposta do
produtor entra pela máquina de estados normal, com `confirm`. Um copiloto que
age sem perguntar não é um copiloto: é um sistema a decidir por alguém que
paga as consequências.
"""

from __future__ import annotations

from typing import Any

#: Os intents que são sobre o tempo. Neles é que a pergunta faz sentido: o
#: produtor perguntou se vai chover, e a resposta que importa é o que a chuva
#: estraga.
INTENTS_DE_TEMPO = frozenset(
    {
        "clima_agora",
        "vai_chover",
        "previsao_estendida",
        "melhor_pulverizar",
        "ultimas_aplicacoes",
    }
)


def _primeira_frase(texto: str) -> str:
    """A parte da resposta que já responde. O resto é o que o copiloto acrescenta."""
    for corte in (". ", "? ", "!", "\n"):
        if corte in texto:
            return texto.split(corte)[0].strip()
    return texto.strip()


def primeiro_dia_seco(previsao: dict, a_partir_de) -> str | None:
    """O primeiro dia sem chuva suficiente para lavar a aplicação. Ou `None`.

    USA OS MESMOS LIMIARES DA REGRA
    -------------------------------
    Deliberadamente. `regras_deterministicas` tem `LIMIAR_CHUVA_MM` e
    `LIMIAR_CHUVA_PROB`; se esta função tivesse os seus próprios, teríamos
    duas respostas à mesma chuva — a regraXvê chuva suficiente, o copiloto
    oferece o dia errado, e o produtor descobre a divergência no campo, com
    o agrotóxico já comprado.

    Por isso os limites são importados, não reescritos. Se alguém mudar um
    limiar, muda nos dois lados no mesmo commit, porque é o mesmo objecto.

    Devolve uma data ISO em string, para ir directamente para `params["data"]`.
    """
    try:
        from app.ia.proativo import LIMIAR_CHUVA_MM, LIMIAR_CHUVA_PROB
    except Exception:
        return None

    dias = (previsao or {}).get("dias") or []
    for d in dias:
        if not d.get("dia"):
            continue
        if str(d["dia"])[:10] <= str(a_partir_de)[:10]:
            continue
        if (d.get("mm") or 0) < LIMIAR_CHUVA_MM and (
            d.get("prob") or 0
        ) < LIMIAR_CHUVA_PROB:
            return str(d["dia"])[:10]
    return None


def _dia_da_aplicacao(achado: dict) -> str | None:
    """O dia que a tarefa tem hoje, para procurar a partir dele."""
    ev = achado.get("evidencia") or {}
    t = ev.get("tarefa") or {}
    dia = t.get("dia")
    return str(dia)[:10] if dia else None


def sugerir(user, propriedade, *, dias: int | None = None) -> dict[str, Any] | None:
    """O que oferecer ao produtor, se houver alguma coisa. Ou `None`.

    Devolve `None` — e não um "não há nada a dizer" — quando não há risco.
    Uma resposta que existe para não ter nada a dizer é ruído, e ruído é o
    que faz um produtor deixar de ler as mensagens.
    """
    try:
        from app.ia.proativo import (
            DIAS_DE_HORIZONTE,
            montar_cenario,
            regras_deterministicas,
        )
    except Exception:
        return None

    if propriedade is None:
        return None

    try:
        cenario = montar_cenario(user, propriedade, dias=dias or DIAS_DE_HORIZONTE)
        achados = regras_deterministicas(cenario)
    except Exception:
        # Uma previsão que não chegou, uma tabela nova, um device offline.
        # O copiloto cala-se e deixa a resposta normal do tempo servir.
        return None

    if not achados:
        return None

    # O mais grave primeiro. `critico` ganha a `atencao`; entre dois do mesmo
    # nível, o que chove mais. A chave anterior era
    # `max(achados, key=lambda a: a.get("nivel") == "critico")`, que devolvia
    # o PRIMEIRO da lista quando nenhum era crítico — e a lista vem por ordem
    # de data, não de gravidade. O produtor ouvia sobre a aplicação de sexta
    # quando a de quinta, a lavar, estava na mesma lista.
    ordem = {"critico": 2, "atencao": 1}
    achado = max(
        achados,
        key=lambda a: (
            ordem.get(a.get("nivel"), 0),
            ((a.get("evidencia") or {}).get("chuva") or {}).get("mm") or 0,
        ),
    )

    # A data seca só é oferecida se existir. Um "quer que eu remarque?" sem
    # dia para propor é uma pergunta que não pode ser respondida, e o
    # produtor responde "sim" para depois receber um "mas para que dia?".
    hoje = str(_dia_da_aplicacao(achado) or _dia_de_hoje())
    proposta = primeiro_dia_seco(cenario.get("previsao") or {}, hoje)

    return {
        "tarefa_id": achado.get("tarefa_id"),
        "titulo": achado.get("titulo"),
        "nivel": achado.get("nivel", "atencao"),
        "regra": achado.get("regra"),
        "data_atual": hoje,
        "data_proposta": proposta,
    }


def _dia_de_hoje() -> str:
    from django.utils import timezone

    return timezone.localdate().isoformat()


def _data_por_extenso(iso: str) -> str:
    """`2026-10-08` -> `dia 08/10`. A data em ISO é para a máquina."""
    try:
        from django.utils.dateparse import parse_date

        d = parse_date(iso[:10])
        return f"dia {d.strftime('%d/%m')}" if d else "depois da chuva"
    except Exception:
        return "depois da chuva"


def frase_de_oferta(achado: dict[str, Any], resposta_tempo: str) -> str:
    """A resposta inteira, em português de produtor.

    A estrutura é deliberada: **primeiro responde, depois oferece.** A ordem
    contrária — oferecer antes de responder — faz o produtor ler um alerta
    em vez de uma previsão, e é o que transforma um copiloto num boletim.

    E a oferta é uma PERGUNTA, não um aviso. "Quer que eu remarque?" é uma
    ação que o produtor pode recusar; "A aplicação será lavada" é um facto
    que ele só pode aceitar.

    A DATA é concreta quando existe. "Quer que eu remarque para depois da
    chuva?" obriga o produtor a uma segunda volta para saber para que dia,
    e essa volta é o ponto em que a maioria desiste. "Para o dia 08/10?"
    responde a pergunta que ele já estava a fazer de cabeça.
    """
    titulo = str(achado.get("titulo") or "a aplicação marcada").rstrip(".")
    base = _primeira_frase(resposta_tempo)
    proposta = achado.get("data_proposta")

    if proposta:
        destino = _data_por_extenso(proposta)
        pergunta = f"Quer que eu remarque para {destino}?"
    else:
        # Sem dia seco no horizonte, NÃO se oferece um vago "depois da
        # chuva": seria uma promessa que o sistema não pode cumprir. Diz-se
        # que não há dia limpo à vista, e pergunta-se o que fazer — que é o
        # que um produtor com um problema quer mesmo saber.
        pergunta = (
            "Não há dia seco à vista nos próximos dias. Quer que eu veja outra janela?"
        )

    return (
        f"{base}\n\n"
        f"Atenção: {titulo}. "
        f"Esta aplicação pode ser lavada pela chuva. "
        f"{pergunta}"
    )
