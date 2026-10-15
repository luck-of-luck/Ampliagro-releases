import base64
import json
import re
import secrets

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from app.ia.sandbox import catalogo, executar
from app.models.ia import ChaveIA
from app.seguranca import hash_cego


# --- OCR de imagem (Pillow; tesseract opcional se instalado) ---
def _ocr_imagem(arquivo):
    """Usa a mesma ingestão limitada e diagnosticada do restante da IA."""
    from app.ia.ingestao.ocr import MAX_BYTES, extrair_texto

    try:
        arquivo.seek(0)
        bruto = arquivo.read(MAX_BYTES + 1)
    except Exception:
        return {
            "texto": "",
            "linhas": [],
            "motor": "arquivo-invalido",
            "aviso": "Nao consegui ler o arquivo. Envie novamente ou digite os itens.",
            "confianca": 0.0,
            "requer_revisao": True,
        }
    finally:
        try:
            arquivo.seek(0)
        except Exception:
            pass
    return extrair_texto(bruto)


def _extrair_itens_estoque(texto):
    """Heurística de planilha/nota: 'NOME qtd und' por linha.

    Ex: 'Ureia 50 sc', 'Diesel 200 L', 'Milho 12,5 kg'. Retorna lista de
    {nome, quantidade, unidade}. Tolera vírgula decimal e ruído de OCR.
    """
    itens = []
    for linha in (texto or "").splitlines():
        l = re.sub(r"\s+", " ", linha.strip().strip("•-–—*|;\t"))
        if len(l) < 3:
            continue
        m = re.search(
            r"^(.+?)\s+(\d+(?:[.,]\d+)?)\s*([a-zA-Z]{1,4}|sc|saca|sacas|kg|g|t|l|un|pct|pcte|fardo|galao|galão)?\s*$",
            l,
        )
        if not m:
            continue
        nome = re.sub(r"\s+", " ", m.group(1).strip().strip(":-–—")).strip()
        if len(nome) < 2:
            continue
        try:
            qtd = float(m.group(2).replace(",", "."))
        except (TypeError, ValueError):
            continue
        und = (m.group(3) or "un").strip().lower()
        und = {"saca": "sc", "sacas": "sc", "galao": "L", "galão": "L"}.get(und, und)
        itens.append({"nome": nome[:150], "quantidade": qtd, "unidade": und[:20]})
    return itens


# Throttle do sandbox: N execuções/min por usuário (anti-loop/DDoS lógico).
# Default 60; ajuste via settings IA_THROTTLE_PER_MINUTE. Usa o cache local.
def _estourou_throttle(user):
    from django.core.cache import cache

    limite = int(getattr(settings, "IA_THROTTLE_PER_MINUTE", 60) or 60)
    if limite <= 0:
        return False
    chave = f"ia:throttle:{user.id}"
    try:
        n = cache.get(chave, 0) + 1
    except Exception:
        return False
    if n > limite:
        return True
    try:
        cache.set(chave, n, 60)
    except Exception:
        pass
    return False


def _resolve_user(request, body=None):
    """Fronteira de confiança explícita (2 vias independentes):
    - PAINEL: sessão autenticada (request.user). A chave NUNCA trafega pro JS.
    - SERVIÇO LOCAL: header X-IA-Key + user_id, MAS só se user_id estiver em
      IA_KEY_USERS (vínculo explícito no .env). Sem vínculo, a chave não age
      por ninguém — vazamento da chave NÃO vira acesso a qualquer usuário.
    """
    syskey = getattr(settings, "IA_LOCAL_KEY", "")
    key = request.headers.get("X-IA-Key", "")
    if key and syskey and secrets.compare_digest(key, syskey):
        vinculados = set(getattr(settings, "IA_KEY_USERS", []) or [])
        if body is None:
            try:
                body = json.loads(request.body.decode() or "{}")
            except Exception:
                body = {}
        try:
            uid = int(body.get("user_id") or 0)
        except (TypeError, ValueError):
            uid = 0
        if uid and uid in vinculados:
            user = User.objects.filter(id=uid, is_active=True).first()
            if user:
                return user, "chave"
        return None, None
    if request.user.is_authenticated:
        return request.user, "sessao"
    return None, None


@login_required
@require_http_methods(["GET"])
def intents_catalogo(request):
    """GET /api/ia/intents/ — instruções: o que a IA pode fazer e como."""
    return JsonResponse({"intents": catalogo()})


@login_required
@require_http_methods(["GET"])
def sessao(request):
    """GET /api/ia/sessao/ — diz ao painel se o sandbox está armado (sem expor chave)."""
    return JsonResponse(
        {
            "sandbox_armado": True,
            "chave_local_configurada": bool(getattr(settings, "IA_LOCAL_KEY", "")),
            "user": request.user.username,
        }
    )


@require_http_methods(["POST"])
def executar_intent(request):
    """POST /api/ia/executar/ {intent, params, meta?, user_id?} — sandbox auditado.
    meta = {entrada: texto bruto, deteccao: {metodo, scores, escolhido}}."""
    try:
        body = json.loads(request.body.decode() or "{}")
    except Exception:
        return JsonResponse({"ok": False, "erro": "JSON inválido"}, status=400)
    user, via = _resolve_user(request, body)
    if not user:
        return JsonResponse({"ok": False, "erro": "não autenticado"}, status=403)
    if _estourou_throttle(user):
        return JsonResponse(
            {"ok": False, "erro": "muitas requisições — aguarde um minuto"},
            status=429,
        )
    out = executar(
        user,
        body.get("intent"),
        body.get("params", {}),
        via=via,
        meta=body.get("meta", {}),
    )
    return JsonResponse(out)


@login_required
@require_http_methods(["POST"])
def evento(request):
    """POST /api/ia/evento/ {tipo, resumo, dados, execucao_id?} — console de registros.
    Tipos: acesso, entendimento, raciocinio, busca, leitura, instrucao, edicao, resposta, erro."""
    from app.models import IAEvento, IAExecucao

    try:
        body = json.loads(request.body.decode() or "{}")
    except Exception:
        return JsonResponse({"ok": False, "erro": "JSON inválido"}, status=400)
    tipos = [c[0] for c in IAEvento.TIPOS]
    tipo = body.get("tipo") or "acesso"
    if tipo not in tipos:
        return JsonResponse(
            {"ok": False, "erro": f"tipo inválido (use {tipos})"}, status=400
        )
    ex = None
    if body.get("execucao_id"):
        ex = IAExecucao.objects.filter(
            id=body["execucao_id"], user=request.user
        ).first()
    ev = IAEvento.objects.create(
        user=request.user,
        tipo=tipo,
        resumo=str(body.get("resumo") or "")[:200],
        dados=body.get("dados", {}),
        execucao=ex,
    )
    return JsonResponse({"ok": True, "id": ev.id})


@login_required
@require_http_methods(["GET", "POST"])
def artefatos(request):
    """Artifactory: GET lista (por tipo), POST cria/atualiza {chave, tipo, dados}."""
    from app.models import IAArtefato

    if request.method == "GET":
        qs = IAArtefato.objects.filter(user=request.user)
        tipo = request.GET.get("tipo")
        if tipo:
            qs = qs.filter(tipo=tipo)
        return JsonResponse(
            {
                "artefatos": [
                    {
                        "id": a.id,
                        "chave": a.chave,
                        "tipo": a.tipo,
                        "dados": a.dados,
                        "origem": a.origem,
                        "atualizado_em": a.atualizado_em.isoformat(),
                    }
                    for a in qs[:100]
                ]
            }
        )
    try:
        body = json.loads(request.body.decode() or "{}")
    except Exception:
        return JsonResponse({"ok": False, "erro": "JSON inválido"}, status=400)
    chave = (body.get("chave") or "").strip()
    if not chave:
        return JsonResponse({"ok": False, "erro": "chave obrigatória"}, status=400)
    a, _ = IAArtefato.objects.update_or_create(
        user=request.user,
        chave=chave,
        defaults={
            "tipo": body.get("tipo", "nota"),
            "dados": body.get("dados", {}),
            "origem": body.get("origem", "painel"),
        },
    )
    return JsonResponse({"ok": True, "id": a.id, "chave": a.chave})


@login_required
@require_http_methods(["POST"])
def imagem_estoque(request):
    """POST /api/ia/imagem-estoque/ — lê imagem (planilha/nota/foto) e vira rascunho.

    Fluxo honesto em 3 passos (nunca inventa número):
    1. OCR (tesseract se instalado; senão Pillow-meta + texto manual).
    2. Heurística 'NOME qtd und' por linha → itens[].
    3. Salva rascunho em IAArtefato (tipo=rascunho_estoque) e devolve para
       confirmação no chat. A gravação real usa os endpoints normais de
       estoque (após o usuário confirmar item a item).
    Body: multipart file 'imagem' (+ opcional 'texto' manual).
    """
    from app.models import IAArtefato

    arquivo = request.FILES.get("imagem")
    texto_manual = (request.POST.get("texto") or "").strip()
    if not arquivo and not texto_manual:
        return JsonResponse(
            {"ok": False, "erro": "envie file 'imagem' ou campo 'texto'"},
            status=400,
        )
    ocr = (
        _ocr_imagem(arquivo)
        if arquivo
        else {"texto": "", "linhas": [], "motor": "manual"}
    )
    texto = str(ocr.get("texto") or "")
    if texto_manual:
        texto = (texto + "\n" + texto_manual).strip()
    itens = _extrair_itens_estoque(texto)
    chave = f"rascunho-estoque/{request.user.id}/{secrets.token_hex(12)}"
    try:
        raw = arquivo.read(1024 * 64) if arquivo else b""
    except Exception:
        raw = b""
    thumb = ""
    if raw:
        try:
            thumb = base64.b64encode(raw[:6000]).decode()
        except Exception:
            thumb = ""
    a, _ = IAArtefato.objects.update_or_create(
        user=request.user,
        chave=chave,
        defaults={
            "tipo": "rascunho_estoque",
            "dados": {
                "itens": itens,
                "linhas": ocr.get("linhas", [])[:40],
                "motor": ocr.get("motor", ""),
                "texto": texto[:4000],
                "aviso": ocr.get("aviso", ""),
                "confianca": ocr.get("confianca", 0.0),
                "requer_revisao": True,
            },
            "origem": "imagem_estoque",
        },
    )
    if itens:
        linhas = [
            f"• {i['nome']} — {i['quantidade']:g} {i['unidade']}" for i in itens[:20]
        ]
        resposta = (
            f"Li {len(itens)} item(ns) da imagem (motor: {ocr.get('motor')}). "
            "Confira antes de gravar:\n"
            + "\n".join(linhas)
            + ("\n+ mais" if len(itens) > 20 else "")
            + "\nResponda 'confirmar' para gravar ou corrija ('ex: Ureia 60 sc')."
        )
    else:
        resposta = (
            "Não reconheci itens no formato 'NOME qtd unidade' "
            f"(motor: {ocr.get('motor')}). "
            "Descreva os itens (ex: 'Ureia 50 sc, Diesel 200 L') que eu monto o rascunho."
        )
    if ocr.get("aviso"):
        resposta = ocr["aviso"] + "\n\n" + resposta
    return JsonResponse(
        {
            "ok": True,
            "resposta": resposta,
            "itens": itens,
            "linhas": ocr.get("linhas", [])[:40],
            "motor": ocr.get("motor", ""),
            "aviso": ocr.get("aviso", ""),
            "confianca": ocr.get("confianca", 0.0),
            "requer_revisao": True,
            "artefato_id": a.id,
            "thumb": thumb,
        }
    )


@login_required
@require_http_methods(["POST"])
@transaction.atomic
def confirmar_estoque(request):
    """POST /api/ia/confirmar-estoque/ {artefato_id, itens?, propriedade_id?}.

    Usa o rascunho (IAArtefato tipo=rascunho_estoque) salvo por imagem-estoque,
    ou a lista enviada. Exige seleção quando há mais de uma propriedade.
    Valida todo o lote antes de gravar; falhas revertem todas as escritas.
    """
    from app.models import EstoqueItem, IAArtefato, Propriedade

    try:
        body = json.loads(request.body.decode() or "{}")
    except Exception:
        return JsonResponse({"ok": False, "erro": "JSON inválido"}, status=400)
    if not isinstance(body, dict):
        return JsonResponse({"ok": False, "erro": "Envie um objeto JSON."}, status=400)
    from rest_framework import serializers

    try:
        artefato_id = serializers.IntegerField(min_value=1).run_validation(
            body.get("artefato_id")
        )
    except serializers.ValidationError:
        return JsonResponse(
            {"ok": False, "erro": "Informe o artefato_id do rascunho revisado."},
            status=400,
        )
    r = (
        IAArtefato.objects.select_for_update()
        .filter(
            pk=artefato_id,
            user=request.user,
            tipo="rascunho_estoque",
        )
        .first()
    )
    if r is None:
        return JsonResponse(
            {"ok": False, "erro": "Rascunho não encontrado ou sem permissão."},
            status=404,
        )
    dados = r.dados if isinstance(r.dados, dict) else {}
    itens = body.get("itens", dados.get("itens", []))
    from app.ia.serializers_ingestao import ConfirmacaoEstoqueOCRSerializer

    validador = ConfirmacaoEstoqueOCRSerializer(data={**body, "itens": itens})
    if not validador.is_valid():
        return JsonResponse(
            {
                "ok": False,
                "erro": "Corrija os itens antes de gravar.",
                "campos": validador.errors,
            },
            status=400,
        )
    itens = validador.validated_data["itens"]
    prop = None
    pid = validador.validated_data.get("propriedade_id")
    if pid:
        prop = Propriedade.objects.filter(user=request.user, id=pid).first()
        if not prop:
            return JsonResponse(
                {"ok": False, "erro": "propriedade não encontrada ou sem permissão"},
                status=403,
            )
    else:
        props = list(Propriedade.objects.filter(user=request.user)[:2])
        if len(props) > 1:
            return JsonResponse(
                {
                    "ok": False,
                    "erro": "você tem mais de uma propriedade — informe propriedade_id",
                    "propriedades": [{"id": p.id, "nome": p.nome} for p in props],
                },
                status=400,
            )
        prop = props[0] if props else None
    if not prop:
        return JsonResponse(
            {"ok": False, "erro": "cadastre uma propriedade antes"}, status=400
        )
    revisados = [{**item, "quantidade": str(item["quantidade"])} for item in itens]
    confirmacao = dados.get("confirmacao")
    if confirmacao:
        if (
            confirmacao["propriedade_id"] != prop.pk
            or confirmacao["itens"] != revisados
        ):
            return JsonResponse(
                {
                    "ok": False,
                    "erro": "Este rascunho já foi confirmado com outros dados. Revise os itens existentes ou crie um novo rascunho.",
                },
                status=409,
            )
        return JsonResponse({**confirmacao["resultado"], "reutilizado": True})
    criados, pulados = [], 0
    for i in itens:
        nome = i["nome"]
        qtd = i["quantidade"]
        und = i["unidade"]
        obj = EstoqueItem.objects.create(
            propriedade=prop,
            nome=nome,
            quantidade=qtd,
            unidade=und,
            categoria="OUTRO",
            quantidade_minima=0,
            local="IA-imagem",
        )
        criados.append(
            {"id": obj.id, "nome": nome, "quantidade": str(qtd), "unidade": und}
        )
    resultado = {
        "ok": True,
        "resposta": (
            f"Gravados {len(criados)} item(ns) no estoque de {prop.nome}."
            + (f" ({pulados} ignorado(s) por nome/qtd inválidos)." if pulados else "")
        ),
        "criados": criados,
        "pulados": pulados,
        "reutilizado": False,
    }
    r.dados = {
        **dados,
        "itens": revisados,
        "confirmacao": {
            "propriedade_id": prop.pk,
            "itens": revisados,
            "resultado": resultado,
        },
    }
    r.save(update_fields=["dados", "atualizado_em"])
    return JsonResponse(resultado)


@login_required
@require_http_methods(["GET", "POST", "DELETE"])
def chave_nuvem(request):
    """GET/POST/DELETE /api/ia/chave/ — gerencia a chave da nuvem.

    - GET: retorna {tem_chave: bool, provedor: str}
    - POST: cadastra/atualiza a chave (corpo: {chave: "..."})
    - DELETE: remove a chave
    """
    propriedade = request.user.propriedades.first()
    if not propriedade:
        return JsonResponse(
            {"ok": False, "erro": "Nenhuma propriedade vinculada ao usuário."},
            status=400,
        )

    if request.method == "GET":
        chave_ia = ChaveIA.objects.filter(propriedade=propriedade).first()
        if chave_ia:
            return JsonResponse({"tem_chave": True, "provedor": chave_ia.provedor})
        return JsonResponse({"tem_chave": False, "provedor": "gemini"})

    if request.method == "DELETE":
        chave_ia = ChaveIA.objects.filter(propriedade=propriedade).first()
        if not chave_ia:
            return JsonResponse(
                {
                    "ok": False,
                    "erro": "Nenhuma chave encontrada para esta propriedade.",
                },
                status=404,
            )
        chave_ia.delete()
        return JsonResponse({"ok": True, "mensagem": "Chave removida."})

    # POST
    try:
        corpo = json.loads(request.body.decode() or "{}")
    except Exception:
        corpo = {}
    chave = corpo.get("chave")
    if not chave:
        return JsonResponse(
            {"ok": False, "erro": "Campo 'chave' é obrigatório."},
            status=400,
        )

    # Busca se já existe uma chave para esta propriedade (por hash)
    existing = ChaveIA.objects.filter(
        propriedade=propriedade, chave_hash=hash_cego(chave or "")
    ).first()

    if existing:
        existing.chave = chave
        existing.save()
        return JsonResponse(
            {"ok": True, "mensagem": "Chave atualizada.", "provedor": existing.provedor}
        )
    else:
        chave_ia = ChaveIA.objects.create(
            propriedade=propriedade, chave=chave, provedor="gemini"
        )
        return JsonResponse(
            {"ok": True, "mensagem": "Chave criada.", "provedor": chave_ia.provedor}
        )


@login_required
@require_http_methods(["POST"])
def testar_chave(request):
    """POST /api/ia/chave/testar/ {chave} — valida SEM salvar.

    A pergunta mais barata possível (lista 1 modelo): prova autenticação
    sem gastar quota de geração e sem persistir nada — nem a chave, nem
    log com ela. O modal da engrenagem chama aqui antes de habilitar o
    "Confirmar e gravar".
    """
    try:
        corpo = json.loads(request.body.decode() or "{}")
    except Exception:
        corpo = {}
    chave = (corpo.get("chave") or "").strip()
    if not chave:
        return JsonResponse(
            {
                "ok": False,
                "valido": False,
                "motivo": "sem_chave",
                "erro": "Cole a chave antes de testar.",
                "modelos": 0,
            },
            status=400,
        )
    if _estourou_throttle(request.user):
        return JsonResponse(
            {
                "ok": False,
                "valido": False,
                "motivo": "limite_local",
                "erro": "Calma — muitas tentativas em seguida. Tente de novo em instantes.",
                "modelos": 0,
            },
            status=429,
        )
    from app.ia.visao import validar_chave_nuvem as _testar

    return JsonResponse(_testar(chave))


@login_required
@require_http_methods(["POST"])
def ver_imagem(request):
    """POST /api/ia/ver-imagem/ {imagem, pergunta?} — a IA VÊ a imagem (Gemini).

    NÃO passa pelo OCR: o PNG da área selecionada vai para um modelo
    multimodal, com a pergunta do produtor, e volta a descrição do que ele
    VIU — gráficos do dashboard incluídos, que texto extraído jamais leria.

    A chave é do SERVIDOR (GEMINI_API_KEY); nunca trafega pro browser. A
    imagem não é persistida em nada: atravessa e some. Compartilha o
    throttle do sandbox (60/min por usuário) para não virar torneira de
    quota em loop.
    """
    try:
        corpo = json.loads(request.body.decode() or "{}")
    except Exception:
        corpo = {}
    imagem = (corpo.get("imagem") or "").strip()
    pergunta = (corpo.get("pergunta") or "").strip()[:2000]
    if not imagem:
        return JsonResponse(
            {
                "ok": False,
                "motivo": "imagem_invalida",
                "erro": "Envie 'imagem' (dataURL PNG/JPEG da área selecionada).",
            },
            status=400,
        )
    if _estourou_throttle(request.user):
        return JsonResponse(
            {
                "ok": False,
                "motivo": "limite_local",
                "erro": "Calma — muitas leituras em seguida. Tente de novo em instantes.",
            },
            status=429,
        )
    from app.ia.visao import ver_imagem as _ver

    r = _ver(imagem, pergunta, user=request.user)
    # Entrada malformada é 400 (como `imagem_estoque`); o resto é 200 com
    # ok:false e motivo — a falha honesta, não um erro de protocolo.
    status = 400 if r.get("motivo") in ("imagem_invalida", "imagem_grande") else 200
    return JsonResponse(r, status=status)


@login_required
@require_http_methods(["POST"])
def conversa_nuvem(request):
    """POST /api/ia/nuvem/ {mensagens: [{role, content}]} — chat na nuvem.

    É o que o switch "Usar agente da nuvem" usa de verdade: a conversa vai
    ao Gemini (texto) com a chave da propriedade ou do servidor, e a
    resposta volta. Sem chave ou com falha, o frontend cai de volta no
    motor local — por isso todo motivo aqui termina em "seguindo no motor
    local" em vez de pedir nova tentativa.
    """
    try:
        corpo = json.loads(request.body.decode() or "{}")
    except Exception:
        corpo = {}
    mensagens = corpo.get("mensagens") or []
    if not isinstance(mensagens, list) or not mensagens:
        return JsonResponse(
            {
                "ok": False,
                "motivo": "sem_pergunta",
                "erro": "Envie 'mensagens' com ao menos uma pergunta.",
            },
            status=400,
        )
    if _estourou_throttle(request.user):
        return JsonResponse(
            {
                "ok": False,
                "motivo": "limite_local",
                "erro": "Calma — muitas leituras em seguida. Tente de novo em instantes.",
            },
            status=429,
        )
    from app.ia.nuvem import conversar as _conversar

    return JsonResponse(_conversar(mensagens, user=request.user))


@login_required
@require_http_methods(["GET"])
def diagnostico(request):
    """GET /api/ia/diagnostico/ — saúde do catálogo de intents e integração.

    Usado pelo painel IA para exibir status dos catálogos, falhas de import,
    drift entre REGISTO e INTENTS, e status geral da integração.
    """
    from app.ia.registro import saude, por_origem, nomes_duplicados
    from app.ia.sandbox import INTENTS as SANDBOX_INTENTS

    health = saude()
    duplicados = nomes_duplicados()
    por_cat = por_origem()

    # Verifica se o sandbox INTENTS coincide com o REGISTO
    drift = sorted(
        set(SANDBOX_INTENTS.keys()) - set(health.get("drift_registro_intents", []))
    )

    return JsonResponse(
        {
            "integro": health.get("integro", False),
            "intents_total": health.get("intents", 0),
            "catalogos_esperados": health.get("catalogos_esperados", 0),
            "catalogos_carregados": health.get("catalogos_carregados", 0),
            "catalogos_falharam": health.get("falhou", []),
            "falhas_detalhe": health.get("falhas", {}),
            "drift_registro_sandbox": drift,
            "duplicados_diferentes": duplicados,
            "por_catalogo": por_cat,
            "sandbox_intents": len(SANDBOX_INTENTS),
        }
    )
