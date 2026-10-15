"""BUILD 5 — as vistas do palco: renderizar, avaliar, clonar.

FICHEIRO ISOLADO, DE PROPÓSITO
==============================
`app/api/views/user.py` e `app/api/urls.py` estão a ser editados por outra
sessão neste momento. Tocar neles seria uma colisão, e colisões resolvem-se
sempre com alguém a perder trabalho. Este módulo não importa nada deles, não
mexe em nada deles, e regista-se em `app/amplia_mcp/urls.py` — que já é meu,
desde a BUILD 4. Os dois lados podem mudar em paralelo.

ONDE O TENANT É APLICADO, LINHA A LINHA
=======================================
Estas três vistas recebem `widgets` do utilizador — o que uma IA escreveu, e IA
escreve o que lhe pedem. Cada `get(...)` e cada `filter(...)` é por
`request.user`. Não por disciplina, mas porque um `get(pk=...)` sem filtro é a
forma mais curta de um vazamento entre produtores, e em dados agronómicos isso
não dá erro: dá uma mesa de operação com a chuva do vizinho, que o produtor lê
como a sua e age em cima. Um dashboard bonito e errado é pior do que um 500.

NÃO HÁ `get_object_or_404(AssinaturaPalco, pk=...)`
===================================================
Esse atalho aceita o `pk` e confia no `pk`. Bastava o produtor trocar o número
no pedido para adotar a assinatura de outro — e, no `clonar`, para apontar o
dashboard dele à assinatura de outro. A pertença é verificada com comparação
explícita, e o teste cobre exatamente esse ataque.
"""

from __future__ import annotations

import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils.text import slugify
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_POST

from app.ia import chamado as _chamado
from app.ia import palco
from app.models import AssinaturaPalco, ChamadoAmplia, PalcoIA, PresetPalco

#: O preset tem de nascer com `custom-` para o dashboard existente o aceitar
#: (ver `app/presets.py`): sem o prefixo, a mesa é criada e nunca mais aparece
#: no menu — um botão que parece funcionar e não faz nada.
PREFIXO_PRESET = "custom-"


def _corpo(request) -> dict:
    """Lê o JSON do corpo sem rebentar.

    Um corpo inválido não é um erro 500: é um cliente a falar mal. Devolve `{}`
    e deixa cada vista dizer o que não recebeu, em vez de uma traceback no meio
    do chat.
    """
    try:
        dados = json.loads(request.body or b"{}")
    except (ValueError, TypeError):
        return {}
    return dados if isinstance(dados, dict) else {}


def _erro(mensagem: str, status: int = 400) -> JsonResponse:
    return JsonResponse({"ok": False, "erro": mensagem}, status=status)


# =============================================================================
# 1. RENDER — a IA manda montar a mesa
# =============================================================================
@login_required
@require_POST
def palco_render(request):
    """Valida o que a IA propose e devolve a mesa normalizada.

    Não grava nada. A mesa é efemérica: o que persiste é o que o produtor
    aprova, no `avaliar` e no `clonar`. Gravar aqui transformaria cada
    pergunta numa mesa permanente, e o dashboard de amanhã abriria com a
    resposta de ontem sem ninguém ter pedido.
    """
    dados = _corpo(request)
    widgets, descartados = palco.validar_estrutura(dados.get("widgets"))

    if not widgets:
        return _erro(
            "nenhum widget reconhecido no que a IA enviou",
            status=422,
        )

    intent = str(dados.get("intent") or "")[:2000]
    return JsonResponse(
        {
            "ok": True,
            "palco": palco.SLUG_PALCO,
            "widgets": widgets,
            "layout": palco.normalizar_layout(dados.get("layout")),
            "assinatura": palco.assinatura_do_intent(intent),
            "intent": intent,
            # Os descartados vão de volta para o produtor ver. Uma IA que
            # inventa id precisa de ser corrigível; esconder o erro faz o
            # motor parecer mais burro do que é.
            "descartados": descartados,
        }
    )


# =============================================================================
# 2. AVALIAR — Like / Dislike, e a consolidation da assinatura
# =============================================================================
@login_required
@require_POST
def palco_avaliar(request):
    """Grava (pergunta → estrutura) e o veredito. É o dataset do ML.

    `get_or_create` sobre (user, assinatura) é o que consolida: milhares de
    parecidas com o mesmo Like não são mil linhas, são a MESMA linha de treino
    a ser reforçada. E o veredito é substituído, nunca acumulado — o último
    veredito é o que vale, senão um Like antigo continua a ensinar uma estrutura
    que o produtor já rejeitou.
    """
    dados = _corpo(request)
    assinatura = str(dados.get("assinatura") or "").strip()[:160]
    if not assinatura:
        return _erro("assinatura ausente: nao sei o que estou a avaliar")

    veredito = dados.get("veredito")
    if veredito not in ("like", "dislike"):
        return _erro("veredito invalido", status=422)

    widgets, _ = palco.validar_estrutura(dados.get("estrutura", {}).get("widgets"))
    estrutura = {
        "widgets": widgets,
        "layout": palco.normalizar_layout(dados.get("estrutura", {}).get("layout")),
    }

    registro, criado = AssinaturaPalco.objects.get_or_create(
        user=request.user,
        assinatura=assinatura,
        defaults={
            "intent_texto": str(dados.get("intent") or "")[:4000],
            "estrutura": estrutura,
            "veredito": veredito,
            "lacuna": str(dados.get("lacuna") or "")[:2000],
            "contexto": dados.get("contexto")
            if isinstance(dados.get("contexto"), dict)
            else {},
        },
    )
    if criado:
        # Sinais de conteúdo precisam do header CSRF; o token da página chega em
        # cookie, e o fetch já o leva. Aka: os dados passam; o sinal, não.
        _marcar_csrf(request, registro)
    else:
        registro.registrar_veredito(
            veredito,
            lacuna=str(dados.get("lacuna") or "")[:2000],
            estrutura=estrutura if widgets else None,
        )

    return JsonResponse(
        {
            "ok": True,
            "criado": criado,
            "assinatura": registro.assinatura,
            "veredito": registro.veredito,
            "historico": registro.historico or [],
        }
    )


def _marcar_csrf(request, registro: AssinaturaPalco) -> None:
    """Regista o User-Agent que assinou o veredito.

     Um Like é um sinal de treinamento. De onde veio importa quando se começa a
    optimizar o modelo com eles: um sinal colado à mão pelo benchmarking vale
     muito mais do que o mesmo sinal num laço automático. Um `User-Agent: curl`
     numa fazenda é um sinal, e um sinal que vale a pena conseguir nomear.
    """
    ua = (request.META.get("HTTP_USER_AGENT") or "")[:200]
    if ua:
        registro.contexto = {**(registro.contexto or {}), "user_agent": ua}
        registro.save(update_fields=["contexto"])


# =============================================================================
# 3. CLONAR — "Salvar como meu Dashboard"
# =============================================================================
@login_required
@require_POST
def palco_clonar(request):
    """Efetiva a mesa efemera num Preset pessoal do produtor.

    O preset é SEMPRE do `request.user`. Não há campo para o cliente dizer de
    quem é, e a `origem` só é aceite se a assinatura também for do mesmo
    produtor — comparar a pertença é mais barato do que tentar provar a
    invenção, e é o que impede a adoção da assinatura de outro.
    """
    dados = _corpo(request)
    widgets, _ = palco.validar_estrutura(dados.get("estrutura", {}).get("widgets"))
    if not widgets:
        return _erro("nao ha mesa para salvar", status=422)

    nome = str(dados.get("nome") or "Minha mesa").strip()[:80] or "Minha mesa"
    estrutura = {
        "widgets": widgets,
        "layout": palco.normalizar_layout(dados.get("estrutura", {}).get("layout")),
        "origem_palco": palco.SLUG_PALCO,
    }

    origem = None
    assinatura = str(dados.get("assinatura") or "").strip()[:160]
    if assinatura:
        origem = (
            AssinaturaPalco.objects.do_produtore(request.user)
            .filter(assinatura=assinatura)
            .first()
        )

    preset, criado = PresetPalco.objects.get_or_create(
        user=request.user,
        slug=_slug_livre(request.user, nome),
        defaults={
            "nome": nome,
            "estrutura": estrutura,
            "origem": origem,
            "fixado": bool(dados.get("fixado", True)),
        },
    )
    if not criado:
        # Clicar duas vezes em "Salvar" não pode ser um erro. O preset já
        # existente é atualizado e devolvido: o segundo momento é o mesmo
        # pedido, e tratá-la como conflito faria o botão parecer quebrado.
        preset.nome = nome
        preset.estrutura = estrutura
        preset.save(update_fields=["nome", "estrutura"])

    return JsonResponse(
        {
            "ok": True,
            "criado": criado,
            "preset": {
                "slug": preset.slug,
                "nome": preset.nome,
                "fixado": preset.fixado,
                "widgets": len(widgets),
            },
        },
        status=201 if criado else 200,
    )


def _slug_livre(user, nome: str) -> str:
    """O slug `custom-` que este clique corresponde.

    Duas ordens importam, e a ordem errada cria um botão que parece partido:

    1. Se o produtor JÁ tem um preset com este nome, é esse que se actualiza.
       Clicar duas vezes em "Salvar" é o mesmo pedido, não dois. Se o segundo
       clique inventasse "Minha-2", o produtor veria a mesma mesa duplicada no
       menu e concluiria que o botão não funciona.

    2. Só para um nome NOVO se procura um slug livre. E dois produtores PODEM
       chamar "custom-custo" às suas mesas: a unicidade é por produtor, e por
       isso os dois recebem, em vez de o segundo levar um erro por uma escolha
       que é dele.
    """
    ja_existe = PresetPalco.objects.do_produtore(user).filter(nome=nome).first()
    if ja_existe:
        return ja_existe.slug

    base = slugify(nome)[:40].strip("-") or "mesa"
    candidato = f"{PREFIXO_PRESET}{base}"
    n = 2
    while PresetPalco.objects.do_produtore(user).filter(slug=candidato).exists():
        candidato = f"{PREFIXO_PRESET}{base}-{n}"
        n += 1
        if n > 50:  # patologico: 50 mesas com o mesmo nome
            break
    return candidato


# =============================================================================
# 5. O CHAMADO — a peça que a IA escreve, lida para a widget-bar
# =============================================================================
@login_required
@require_http_methods(["GET"])
@never_cache
def palco_chamado(request):
    """A peça deste produtor, com o `fonte_dado` de cada bloco.

    SÓ LEITURA, e por uma razão que não é estilo: a escrita da IA passa por
    `sandbox.executar`, que é o caminho único que audita e que pede confirmação
    ao produtor. Um `POST` de escrita aqui seria um segundo caminho — que é
    exactamente o bug que `app/amplia_mcp/` existe para fechar, e que o teste
    `InvarianteDeFonteTest` traverse o código por AST para apanhar.

    A widget-bar precisa de ler para desenhar; não precisa de escrever. O que
    escreve é a IA, pelo sandbox, e o produtor confirma.

    `fonte_dado` vem por bloco. Um bloco de texto que afirma um número que
    nenhuma tabela sustenta desce a `sem_dado` — e o painel pinta-o como tal.
    Sem isso, o produtor lê uma afirmação com a mesma cara de uma medição.
    """
    peca = ChamadoAmplia.objects.do_produtore(request.user).first()
    if peca is None:
        return JsonResponse(
            {
                "ok": True,
                "chamado": {
                    "existe": False,
                    "slug": _chamado.SLUG_CHAMADO,
                    "nome": _chamado.NOME_CHAMADO,
                },
                "zona_escrita": {
                    "preset": _chamado.SLUG_CHAMADO,
                    "regra": "a IA escreve aqui e só aqui; nos outros presets só lê",
                },
            }
        )

    # Os números são CONSULTADOS aqui, com o produtor no filtro, e não lidos de
    # um campo guardado. A peça guarda a receita (que fonte, que filtros); o
    # banco responde. É o que garante que nada que a IA escreveu fica gravado
    # como se fosse medido, e o que impede a peça de envelhecer.
    corpo = _chamado.aplicar_fontes(request.user, list(peca.corpo or []))
    corpo = _chamado.aplicar_fonte_dado(corpo)
    return JsonResponse(
        {
            "ok": True,
            "chamado": {
                "existe": True,
                "slug": peca.slug,
                "nome": peca.nome,
                "estado": peca.estado,
                "versao": peca.versao,
                "preset": peca.preset.slug if peca.preset_id else None,
                "blocos": corpo,
                "total": len(corpo),
                "sem_dado": [b["id"] for b in corpo if b["fonte_dado"] == "sem_dado"],
                "numeros_sem_apoio": _chamado.rastrear_numeros(corpo),
                "numeros_descartados": sum(
                    int(b.get("numeros_descartados") or 0) for b in corpo
                ),
                "atualizado_em": peca.atualizado_em.isoformat(),
            },
            "zona_escrita": {
                "preset": _chamado.SLUG_CHAMADO,
                "operacoes": list(_chamado.OPERACOES),
                "regra": "a IA escreve aqui e só aqui; nos outros presets só lê",
            },
        }
    )


# =============================================================================
# 4. O PALCO — a configuração pública, para o JS saber o que existe
# =============================================================================
@login_required
def palco_info(request):
    """O que o palco é, e o que o produtor já tem guardado.

    Consultado no arranque da tela, para o botão "Salvar" saber se está a criar
    ou a atualizar, e para a barra de presets ter o que mostrar sem adivinhar.
    """
    palco_reg = PalcoIA.objects.filter(slug=palco.SLUG_PALCO, ativo=True).first()
    return JsonResponse(
        {
            "ok": True,
            "palco": {
                "slug": palco_reg.slug if palco_reg else palco.SLUG_PALCO,
                "nome": palco_reg.nome if palco_reg else "Amplia",
                "fluido": True,
            },
            # O catalogo INTEIRO, com a fonte de cada widget. E' o que
            # permite ao JS construir a instrucao sem ter uma lista propria —
            # e uma lista propria era como o palco chegou a oferecer ids que
            # a camada de dados nunca conheceu.
            "catalogo": {
                k: {
                    "descricao": v.get("descricao", ""),
                    "fonte": v.get("fonte", "servidor"),
                }
                for k, v in palco.CATALOGO_IA.items()
            },
            # A `estrutura` vem aqui porque o cliente precisa dela para DESENHAR.
            #
            # MEDIDO 2026-10-09: antes eram só `slug`, `nome` e `fixado`, e
            # `meus_presets` não era lido por nenhum JavaScript. Um preset
            # guardado — pela IA ou pelo botão "Salvar como meu Dashboard" —
            # aparecia por nome e não desenhava. Era um registo na base de
            # dados, não uma feature.
            #
            # Os ids que a IA grava são todos do `WIDGET_CATALOG` do
            # dashboard (medido: os 17 de `CATALOGO_IA` existem lá), o que
            # torna a composição desenhável. A PONTE é no JS
            # (`palco-amplia.js::registarPresetsGuardados`): o formato do
            # dashboard é um objecto indexado por id, com geometria de
            # grelha, e o da IA é uma lista. Traduzir é trabalho do cliente,
            # que é onde a grelha vive.
            "meus_presets": list(
                PresetPalco.objects.do_produtore(request.user)
                .order_by("-fixado", "-criado_em")
                .values("slug", "nome", "fixado", "estrutura")
            ),
            # A ZONA DE ESCRITA, anunciada no arranque.
            #
            # O JS precisa disto para não montar um botão de "editar" no preset
            # errado. E precisa do `slug` exacto, porque `preset_permitido()`
            # só aceita o que está em `app.presets.PRESETS_SISTEMA` — e um slug
            # inventado aqui produz um preset que a limpeza de presets fantasma
            # apaga no momento em que o produtor grava o estado. É a mesma
            # armadilha que a docstring do `palco_clonar` descreve.
            "zona_escrita": {
                "preset": _chamado.SLUG_CHAMADO,
                "nome": _chamado.NOME_CHAMADO,
                "regra": (
                    "A IA escreve SÓ neste preset. Nos teus dashboards, só "
                    "lê — a não ser que peças para guardar esta tela aí, e "
                    "mesmo assim pergunta primeiro. A recusa vem com o motivo "
                    "e o caminho alternativo."
                ),
            },
            "meu_chamado": (
                {
                    "existe": True,
                    "estado": peca.estado,
                    "versao": peca.versao,
                    "blocos": len(peca.corpo or []),
                }
                if (peca := ChamadoAmplia.objects.do_produtore(request.user).first())
                else {"existe": False}
            ),
        }
    )
