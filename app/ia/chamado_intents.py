"""As intents do Chamado Amplia — o que a IA pode fazer, e onde.

A TRAVA VIVE AQUI, NÃO NUM `if` DISCRETO
========================================
`chamado.pode_escrever` é chamado **dentro de cada handler de escrita**, antes de
qualquer coisa ser tocada. Não num middleware, não num permiso, não na view: no
handler, à vista de quem lê.

A razão é uma lição que o produto já pagou: houve um handler "desligado" em
comentário com dois POSTs vivos a `/api/iot/comandos/` (ver `MCP_AMPLIA.md`, §
"o que havia por baixo dela"). Uma restrição que depende de alguém se lembrar de
a aplicar é uma restrição que uma sessão cansada burla. Uma restrição que está na
primeira linha do handler é lida por quem abre o ficheiro.

E o teste correspondente não confia no handler: `tests_chamado_api.py` parte o
sistema de propósito e confirma que escrever fora da zona falha.

O QUE A IA FAZ E O QUE NÃO FAZ
==============================
`criar`    monta a peça a partir do catálogo de blocos. É a única que cria.
`editar`   muda a peça por DELTA. É a única que altera.
`ler`     mostra o que está lá. Não pede confirmação — é leitura.
`publicar` fecha ou reabre. Arquivar é a forma de o produtor fechar a porta sem
           apagar o que a IA lhe fez.

Nenhuma delas aceita um `user`: o produtor é o `user` que vem do sandbox, e um
campo de produtor no corpo do pedido é o forma mais curta de um vazamento entre
contas.
"""

from __future__ import annotations

from typing import Any

from app.ia import chamado as ch

# --------------------------------------------------------------------------
# AJUDANTES
# --------------------------------------------------------------------------


def _recusa(motivo: str, **extra: Any) -> dict:
    """A resposta de uma escrita recusada. `ok: False` e NADA foi tocado."""
    return {"ok": False, "erro": motivo, "dados": dict(extra)}


def _do_produtore(user):
    """A peça deste produtor, ou `None`.

    `do_produtore` e não `filter(pk=...)`: aceitar um id do corpo e depois
    comparar a pertença é mais um passo em que alguém se engana. Aqui não há
    id para enganar — só há UM Chamado por produtor, e ele é deste.
    """
    from app.models import ChamadoAmplia

    return ChamadoAmplia.objects.do_produtore(user).first()


def _prescrever(user, nome: str | None = None):
    """Garante que a peça tem preset na widget-bar, e devolve-o.

    A peça sem preset é invisível: existe na base, a IA consegue lê-la, e o
    produtor nunca a vê. É a mesma falha de `palco_clonar` — "a mesa é criada e
    nunca mais aparece no menu" — e por isso o preset é criado AQUI, no mesmo
    passo que a peça, e não numa visita posterior que pode não vir.
    """
    from app.models import ChamadoAmplia, PresetPalco

    peca = _do_produtore(user)
    if peca is None:
        return None
    if peca.preset_id:
        return peca.preset

    preset, _ = PresetPalco.objects.get_or_create(
        user=user,
        slug=ch.SLUG_CHAMADO,
        defaults={
            "nome": nome or ch.NOME_CHAMADO,
            "estrutura": {"widgets": [], "layout": "grid-mixed"},
            "fixado": True,
        },
    )
    peca.preset = preset
    peca.save(update_fields=["preset"])
    return preset


def _publicar_no_preset(user, peca):
    """Espelha a peça no preset, para a widget-bar mostrar o que existe."""
    from app.models import PresetPalco

    preset = peca.preset or _prescrever(user)
    if preset is None:
        return None
    preset.nome = peca.nome or ch.NOME_CHAMADO
    preset.estrutura = {
        "chamado": True,
        "slug": ch.SLUG_CHAMADO,
        "blocos": len(peca.corpo or []),
        "versao": peca.versao,
        "estado": peca.estado,
    }
    preset.fixado = True
    preset.save(update_fields=["nome", "estrutura", "fixado"])
    return preset


def _resumo(peca, user=None) -> dict:
    """O estado da peça, no formato que a IA e o painel leem.

    `fonte_dado` vem POR BLOCO e nunca por peça. Uma peça é medida ou não? Essa
    pergunta não tem resposta honesta — uma peça pode ter uma tabela medida e um
    parágrafo que afirma. O carimbo por bloco é o que permite ao painel pintar o
    bloco certo e ao produtor saber qual é qual.

    E os números são calculados AQUI, na leitura, e não vêm guardados. A peça
    guarda a RECEITA (que fonte, que filtros) e o servidor pergunta ao banco
    cada vez que alguém a abre. Duas consequências, ambas Wanted: nada que a IA
    escreveu fica gravado como se fosse dado, e a peça não envelhece — o número
    de ontem já não é o número de hoje.
    """
    corpo = list(peca.corpo or [])
    if user is not None:
        corpo = ch.aplicar_fontes(user, corpo)
    corpo = ch.aplicar_fonte_dado(corpo)
    sem_rastreio = ch.rastrear_numeros(corpo)
    descartados = sum(int(b.get("numeros_descartados") or 0) for b in corpo)
    return {
        "chamado": ch.SLUG_CHAMADO,
        "nome": peca.nome,
        "estado": peca.estado,
        "versao": peca.versao,
        "blocos": corpo,
        "total": len(corpo),
        "sem_dado": [b["id"] for b in corpo if b["fonte_dado"] == "sem_dado"],
        "numeros_sem_apoio": sem_rastreio,
        "numeros_descartados": descartados,
    }


def _conta_linhas(corpo: list[dict]) -> int:
    """Quantas linhas a IA mandou nos blocos de DADO, antes de `_guarda` as tirar.

    É este o número que o produtor precisa ouvir: é a diferença entre "a peça
    está vazia porque não há registo" e "a peça está vazia porque o que a IA
    escreveu foi descartado".
    """
    total = 0
    for b in corpo:
        if b.get("tipo") in ch.BLOCOS_DADO:
            total += len((b.get("config") or {}).get("linhas") or [])
    return total


def _guarda(corpo: list[dict]) -> list[dict]:
    """O que vai PARA a base: a receita, nunca os números.

    Guardar as linhas que a IA escreveu seria gravar um número inventado como se
    fosse uma medição — e a peça deixaria de ser uma pergunta ao banco para ser
    uma fotografia do que o modelo disse numa tarde. A base guarda o que se
    PERGUNTA; a leitura responde.
    """
    guardado = []
    for b in corpo:
        cfg = dict(b.get("config") or {})
        # Quantas linhas a IA mandou neste bloco. A contagem é TIRADA antes de as
        # linhas irem embora, porque depois já não há como saber.
        #
        # Antes, `numeros_descartados` era descartado com as linhas e a `_resumo`
        # limitava-se a somar o que finda nos blocos guardados — logo devolvia
        # SEMPRE zero, em qualquer peça, para sempre. Não era um número que
        # media o descarte: era um número que não media nada. O produtor lia
        # "0 números descartados" numa peça onde a IA tinha mandado quatro, e a
        # leitura dizia o contrário da verdade.
        #
        # Agora a contagem viaja no bloco. É metadata, não é um número do
        # produtor a ser disfarçado de medição: quantos números FORAM
        # descartados é um facto sobre a escrita, não sobre os dados.
        linhas = cfg.pop("linhas", None)
        descartadas = len(linhas) if isinstance(linhas, list) else 0
        cfg.pop("motivo", None)
        novo = {
            k: v
            for k, v in b.items()
            if k not in ("config", "fonte_dado", "texto_apoio")
        }
        novo["config"] = cfg
        if descartadas:
            novo["numeros_descartados"] = descartadas
        guardado.append(novo)
    return guardado


def _aviso_sem_dado(resumo: dict) -> str:
    """A frase que vai no `resposta`, e que o produtor lê.

    Só aparece quando há algo a dizer. Uma peça bem apoiada que volta com um
    aviso sobre nada aprendido obriga o produtor a ler um aviso para poder
    confirmar que não há aviso — que é o inverso do que ele precisa.
    """
    partes: list[str] = []
    if resumo["sem_dado"]:
        partes.append(
            "sem número que sustente: "
            + ", ".join(resumo["sem_dado"])
            + " (aparecem como 'sem dado', não como zero)"
        )
    if resumo["numeros_sem_apoio"]:
        numeros = ", ".join(sorted({a["numero"] for a in resumo["numeros_sem_apoio"]}))
        partes.append(
            f"números escritos no texto que nenhum bloco sustenta: {numeros}. "
            "Vê o que está a afirmar antes de levar a decisão."
        )
    if not partes:
        return ""
    return " Atenção — " + "; ".join(partes) + "."


# --------------------------------------------------------------------------
# 1. LER — a única sem confirmação
# --------------------------------------------------------------------------


def h_chamado_ler(user, params, ctx):
    """Mostra a peça. Não escreve, não pede confirmação, não levanta."""
    peca = _do_produtore(user)
    if peca is None:
        return {
            "ok": True,
            "resposta": (
                f"Ainda não há {ch.NOME_CHAMADO}. Se quiseres um, diz o que queres "
                "ver e eu monto-o."
            ),
            "dados": {"chamado": ch.SLUG_CHAMADO, "existe": False},
        }

    resumo = _resumo(peca, user)
    ids = ", ".join(f"{b['id']}:{b['tipo']}" for b in resumo["blocos"]) or "vazio"
    return {
        "ok": True,
        "resposta": (
            f"{ch.NOME_CHAMADO} — {peca.estado}, versão {peca.versao}, "
            f"{resumo['total']} blocos ({ids})." + _aviso_sem_dado(resumo)
        ),
        "dados": {"existe": True, **resumo},
    }


# --------------------------------------------------------------------------
# 2. CRIAR
# --------------------------------------------------------------------------


def h_chamado_criar(user, params, ctx):
    """Monta a peça. `blocos` é a lista do catálogo `amplia_chamado_blocos`."""
    # Se o produtor disser EM QUE preset quer a peça, esse preset passa pela
    # trava. Não se o `preset` for omitido: criar é por definição a zona — só há
    # uma peça possível, e a `UniqueConstraint` no banco garante que não há
    # segunda. O que não pode é vir um preset ALHEIO e ser aceite em silêncio,
    # que era o que a versão anterior fazia.
    pedido = params.get("preset")
    if pedido is not None and str(pedido).strip():
        pode, motivo = ch.pode_escrever(user, pedido)
        if not pode:
            return _recusa(motivo, zonas_escrita=[ch.SLUG_CHAMADO])

    corpo, descartados = ch.validar_blocos(params.get("blocos"))
    if not corpo:
        return _recusa(
            "nenhum bloco reconhecido. Chame `amplia_chamado_blocos` para ver os "
            "tipos e os campos de cada um, e não tente um tipo novo.",
            tipos_validos=sorted(ch.CATALOGO_BLOCOS),
        )

    from app.models import ChamadoAmplia

    nome = str(params.get("nome") or ch.NOME_CHAMADO).strip()[:120] or ch.NOME_CHAMADO
    # Contado AQUI, antes de `_guarda` limpar. Depois já não há linhas para
    # contar, e o número sairia sempre zero — o que é pior que não dizer nada,
    # porque parece que não havia números para descartar.
    numeros_ia = _conta_linhas(corpo)

    peca, criado = ChamadoAmplia.objects.get_or_create(
        user=user,
        slug=ch.SLUG_CHAMADO,
        defaults={
            "nome": nome,
            "corpo": _guarda(corpo),
            "estado": "rascunho",
            "contexto": {
                "pergunta": str(params.get("pergunta") or ctx.get("pergunta", ""))[
                    :2000
                ]
            },
        },
    )
    if criado:
        peca.preset = _prescrever(user, nome)
        peca.save(update_fields=["preset"])
    else:
        # Pedir "cria o chamado" quando ele já existe não é erro — é o produtor
        # a querer recomeçar. Substituir é o que ele quis dizer, e devolver um
        # erro obriga-o a dizer "substitui", que é uma volta a mais para ele e
        # um turno a mais para a IA.
        peca.nome = nome
        peca.corpo = _guarda(corpo)
        peca.estado = "rascunho"
        peca.save(update_fields=["nome", "corpo", "estado", "atualizado_em"])

    _publicar_no_preset(user, peca)
    resumo = _resumo(peca, user)
    resumo["numeros_descartados"] = numeros_ia
    return {
        "ok": True,
        "resposta": (
            ("Criei o " if criado else "Reescrevi o ")
            + f"{ch.NOME_CHAMADO} com {resumo['total']} blocos: "
            + ", ".join(b["tipo"] for b in resumo["blocos"])
            + "."
            + _aviso_sem_dado(resumo)
            + (
                f" Escreveste {numeros_ia} número(s) nos blocos e foram "
                "descartados: números são lidos do banco, não escritos. "
                "Cita uma fonte (ver `amplia_catalogos.fontes`)."
                if numeros_ia
                else ""
            )
            + (
                f" ({len(descartados)} descartados: {', '.join(descartados[:4])})"
                if descartados
                else ""
            )
        ),
        "dados": {"criado": criado, "descartados": descartados, **resumo},
    }


# --------------------------------------------------------------------------
# 3. EDITAR — o delta, e a trava
# --------------------------------------------------------------------------


def h_chamado_editar(user, params, ctx):
    """Muda a peça por delta. É aqui que a trava é consultada."""
    # O `preset` vai CRU, sem `or ch.SLUG_CHAMADO`.
    #
    # Esse `or` era o bug mais perigoso que este ficheiro já teve: com um preset
    # vazio — ou ausente, ou `"0"`, ou o que um modelo envia quando não sabe —
    # a expressão caía no slug da zona e a trava passava. Um `preset` que não se
    # consegue ler tem de ser um `preset` que NÃO pode escrever. É a diferença
    # entre uma trava e uma sugestão, e o teste
    # `test_editar_sem_preset_indica_o_certo` existe para a manter.
    pode, motivo = ch.pode_escrever(user, params.get("preset"))
    if not pode:
        return _recusa(motivo, zonas_escrita=[ch.SLUG_CHAMADO])

    peca = _do_produtore(user)
    if peca is None:
        return _recusa(
            f"ainda não há {ch.NOME_CHAMADO}. Pede para o criar primeiro.",
            zonas_escrita=[ch.SLUG_CHAMADO],
        )
    if peca.somente_leitura_para_ia:
        return _recusa(
            f"o {ch.NOME_CHAMADO} está arquivado — a IA só lê. Pede para o "
            "publicar de novo se quiseres que eu escreva."
        )

    # O `versao` é o que impede a IA de editar em cima de uma edição que não
    # viu. Sem ele, duas edições a partir da mesma leitura sobrepõem-se uma
    # à outra: a segunda escreve o corpo antigo por cima do novo, e o produtor
    # vê uma alteração sua desaparecer sem ninguém a ter tocado.
    versao = params.get("versao")
    if versao is not None:
        try:
            pedida = int(versao)
        except (TypeError, ValueError):
            return _recusa(f"versao invalida: {versao!r}")
        if pedida != peca.versao:
            return _recusa(
                f"o {ch.NOME_CHAMADO} mudou entretanto (está na v{peca.versao}, "
                f"tu liaste a v{pedida}). Lê outra vez antes de editar.",
                versao_atual=peca.versao,
            )

    corpo_novo, avisos = ch.aplicar_delta(list(peca.corpo or []), params.get("delta"))
    if corpo_novo == list(peca.corpo or []):
        return _recusa(
            "nada mudou. As operações são: "
            + ", ".join(ch.OPERACOES)
            + " — e cada uma precisa do `id` do bloco, que `amplia_chamado_ler` dá.",
            ids=[b.get("id") for b in (peca.corpo or [])],
            operacoes=list(ch.OPERACOES),
            avisos=avisos,
        )

    # `numeros_ia` conta as linhas que a IA mandou NESTE delta, antes de
    # `_guarda` as tirar. Sem esta linha o handler rebentava com
    # `name 'numeros_ia' is not defined` ao responder — e o produtor via
    # "falha interna" numa edição que tinha sido aceite e gravada.
    numeros_ia = _conta_linhas(corpo_novo)
    peca.corpo = _guarda(corpo_novo)
    peca.versao = int(peca.versao) + 1
    peca.save(update_fields=["corpo", "versao", "atualizado_em"])

    _publicar_no_preset(user, peca)
    resumo = _resumo(peca, user)
    resumo["numeros_descartados"] = numeros_ia
    return {
        "ok": True,
        "resposta": (
            f"{ch.NOME_CHAMADO} agora na v{peca.versao}, {resumo['total']} blocos: "
            + ", ".join(f"{b['id']}:{b['tipo']}" for b in resumo["blocos"])
            + "."
            + _aviso_sem_dado(resumo)
            + (
                f" Descartados {numeros_ia} número(s) escritos por ti: números "
                "são lidos do banco, não escritos."
                if numeros_ia
                else ""
            )
        ),
        "dados": {"avisos": avisos, **resumo},
    }


# --------------------------------------------------------------------------
# 4. PUBLICAR / ARQUIVAR — a porta que o produtor fecha
# --------------------------------------------------------------------------


def h_chamado_publicar(user, params, ctx):
    """Fecha a peça (arquiva) ou reabre. É o que devolve a escrita à IA."""
    peca = _do_produtore(user)
    if peca is None:
        return _recusa(f"ainda não há {ch.NOME_CHAMADO}.")

    acao = str(params.get("acao") or "publicar").strip().lower()
    if acao in ("arquivar", "fechar"):
        novo = "arquivado"
    elif acao in ("publicar", "reabrir", "rascunho"):
        novo = "publicado" if acao != "rascunho" else "rascunho"
    else:
        return _recusa(
            f"acao invalida: {acao!r}. Use 'publicar', 'arquivar' ou 'rascunho'."
        )

    peca.estado = novo
    peca.versao = int(peca.versao) + 1
    peca.save(update_fields=["estado", "versao", "atualizado_em"])
    _publicar_no_preset(user, peca)

    return {
        "ok": True,
        "resposta": (
            f"{ch.NOME_CHAMADO} agora está {novo} (v{peca.versao}). "
            + (
                "A IA pode escrever nele outra vez."
                if novo != "arquivado"
                else "A IA só o lê a partir de agora; o conteúdo fica."
            )
        ),
        "dados": {"estado": novo, "versao": peca.versao},
    }


# --------------------------------------------------------------------------
# O REGISTO
# --------------------------------------------------------------------------

INTENTS_CHAMADO = {
    "chamado_criar": {
        "descricao": (
            "INSTRUÇÃO IA: use quando o produtor pedir uma peça — 'monta um "
            "chamado', 'faz um resumo', 'põe isto numa tela', 'quero ver X, Y e "
            "Z juntos'. Monta o Chamado Amplia com blocos do catálogo.\n\n"
            "Chame `amplia_chamado_blocos` ANTES, para saber os tipos e os "
            "campos de cada um. Não inventes tipos.\n\n"
            "É o ÚNICO preset onde pode escrever. Se o produtor pedir para "
            "mudar outro preset, não o faça: explique que naquele preset a IA "
            "só lê, e ofereça fazer a mudança no Chamado Amplia.\n\n"
            "Se o bloco de texto citar um número, esse número tem de estar numa "
            "linha de algum bloco de dado. Se não estiver, o bloco fica "
            "'sem_dado' e o produtor vê o aviso."
        ),
        "exemplos": [
            "monta um chamado com a produção e o custo",
            "faz um resumo da safra deste ano",
            "põe o custo por hectare e a margem lado a lado",
            "quero ver as safras e o caixa juntos",
        ],
        "flags": ["chamado.create"],
        "required_fields": ["blocos"],
        "requires_confirmation": True,
        "prompt_confirmacao": ("Criar este chamado?"),
        "handler": h_chamado_criar,
    },
    "chamado_editar": {
        "descricao": (
            "INSTRUÇÃO IA: use para MUDAR o Chamado Amplia que já existe — "
            "'acrescenta uma tabela', 'tira o gráfico', 'reescreve o "
            "parágrafo', 'põe a tabela em primeiro'.\n\n"
            "Aceita um `delta`: uma operação, ou uma lista. Operações: "
            + ", ".join(ch.OPERACOES)
            + ". Cada uma precisa do `id` do bloco — chame `amplia_chamado_ler` "
            "para os ter.\n\n"
            "Use `delta`, NÃO a lista inteira de blocos: reenviar tudo obriga a "
            "repetir o que já está feito e perde-se conteúdo sem querer.\n\n"
            "`preset` é OBRIGATÓRIO e tem de ser `"
            + ch.SLUG_CHAMADO
            + "`. Não o omitas: um preset que não se consegue ler é um preset "
            "onde não se pode escrever, e a chamada é recusada. Noutro preset, "
            "esta chamada não faz nada — a IA só os lê.\n\n"
            "Manda a `versao` que leste. Se a peça mudou entretanto, o pedido é "
            "recusado e tu lês de novo."
        ),
        "exemplos": [
            "acrescenta uma tabela de despesas",
            "tira o gráfico do meio",
            "reescreve o parágrafo para ser mais curto",
            "põe a tabela em primeiro",
        ],
        "flags": ["chamado.write"],
        "required_fields": ["preset", "delta"],
        # O schema DECLARADO, que tem precedência sobre o deduzido dos
        # exemplos. E o `enum` é o ponto: um schema que só diz "string" obriga a
        # IA a descobrir qual é o preset certo — e uma descoberta que falha é
        # uma escrita recusada, ou pior, uma escrita no sítio errado. Com o
        # `enum` há um único valor que o schema aceita, e a restrição é
        # legível por máquina em vez de ser uma nota que se pode não ler.
        "params_schema": {
            "preset": {
                "type": "string",
                "enum": [ch.SLUG_CHAMADO],
                "description": (
                    "O preset onde a IA escreve. Só existe este valor — nos "
                    "outros presets a AmplIA só lê."
                ),
            },
            "delta": {
                "type": "object",
                "description": (
                    "A alteração. {op: adicionar|remover|substituir|reordenar|"
                    "reescrever_texto, id, ...}. Lista de blocos em "
                    "`amplia_chamado_blocos`."
                ),
            },
            "versao": {
                "type": "integer",
                "description": "A versão que leste. Se mudar entretanto, recusa.",
            },
            "nome": {
                "type": "string",
                "description": "Nome do bloco novo, em `adicionar`.",
            },
        },
        "requires_confirmation": True,
        "prompt_confirmacao": ("Alterar este chamado?"),
        "handler": h_chamado_editar,
    },
    "chamado_ler": {
        "descricao": (
            "INSTRUÇÃO IA: use para ver o que o Chamado Amplia tem agora, com "
            "os `id` de cada bloco. Chame antes de `amplia_chamado_editar` — é "
            "daqui que saem os ids, e sem eles o delta não tem alvo.\n\n"
            "Também mostra os blocos sem número que os sustente. É leitura: não "
            "pede confirmação."
        ),
        "exemplos": [
            "o que tem no chamado",
            "mostra o que está no chamado",
            "que blocos tem",
        ],
        "flags": ["chamado.read"],
        "handler": h_chamado_ler,
    },
    "chamado_publicar": {
        "descricao": (
            "INSTRUÇÃO IA: use quando o produtor fechar ou reabrir a peça — "
            "'arquiva o chamado', 'fecha', 'abre de novo'. Arquivado, a IA só "
            "lê: o conteúdo fica, a escrita para.\n\n"
            "Ações: 'publicar', 'arquivar', 'rascunho'."
        ),
        "exemplos": [
            "arquiva o chamado",
            "fecha o resumo",
            "abre o chamado outra vez",
        ],
        "flags": ["chamado.write"],
        "required_fields": ["acao"],
        "requires_confirmation": True,
        "prompt_confirmacao": ("Publicar este chamado? Fica visível para os outros."),
        "handler": h_chamado_publicar,
    },
}
