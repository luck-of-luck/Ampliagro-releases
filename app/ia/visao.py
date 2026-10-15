"""Visão — a IA VÊ a imagem de verdade (Gemini multimodal), sem OCR.

POR QUE ESTE MÓDULO EXISTE
--------------------------
O "Selecionar área" entrega um PNG da página — gráficos do dashboard
incluídos. OCR (`app/ia/ingestao/ocr.py`) extrai TEXTO, e texto não lê
gráfico: cor, forma, tendência e estado visual morrem na extração. O pedido
é explícito: a IA tem de VER a imagem, não ler um texto tirado dela. Por
isso este caminho NÃO passa pelo OCR em nenhum ponto.

A CHAVE
-------
Primeiro a DA PROPRIEDADE (`ChaveIA`, registrada na engrenagem pelo
produtor) — é a decisão consciente dele e tem precedência. Depois a do
SERVIDOR (`GEMINI_API_KEY` no settings ou no ambiente). Nunca vai ao
browser, nunca é logada, nunca entra em URL (vai no header
`x-goog-api-key`, para não vazar em log de acesso). Sem nenhuma, o retorno
é `sem_chave` com a instrução — e não uma tentativa que queimaria quota.

O QUE NÃO SE GUARDA
-------------------
A imagem não é persistida: nem artefato, nem log de bytes, nem evento com
payload. Visão custa quota e expõe tela do produtor — o dado atravessa e
some. O que fica é a resposta em texto, na conversa, como qualquer outra.

CONTRATO
--------
`ver_imagem()` NUNCA levanta (mesma regra do `llm_gateway.chamar()`).
Devolve sempre:

    {
      "ok": bool,
      "resposta": str,    # texto do modelo, ou "" se falhou
      "provedor": str,    # "gemini" | "nenhum"
      "motivo": str,      # "" se ok; senão o código para a UI mapear
      "erro": str,        # frase honesta em pt-BR para mostrar
    }
"""

from __future__ import annotations

import base64
import binascii
import json
import logging
import os
import urllib.error
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)

#: Modelo default: gratuito, multimodal, rápido. Troca por
#: settings GEMINI_VISION_MODEL ou env com o mesmo nome.
#: O catálogo gira (2.0-flash e 2.5-flash saíram para chaves novas em
#: 2026): verificado via GET /v1beta/models com chave real, que também
#: recomenda a Interactions API no lugar da v1beta.
MODELO_PADRAO = "gemini-3.8-flash"

#: Bytes decodificados além disto são recusados antes de gastar quota.
#: Uma área de dashboard em PNG passa folgada; tela cheia em 2x também.
TAMANHO_MAX_B = 4_000_000

#: Timeout da chamada. Visão gera mais tokens que texto e o modelo às vezes
#: acorda devagar: 45s com uma nova tentativa cobre o transitório sem travar
#: a interface para sempre.
TIMEOUT_PADRAO_S = 45.0


def _ler_chave() -> str:
    """Chave do Gemini: settings primeiro, ambiente como fallback."""
    try:
        from django.conf import settings as _s

        v = getattr(_s, "GEMINI_API_KEY", "") or ""
        if v:
            return v.strip()
    except Exception:
        pass
    return (os.getenv("GEMINI_API_KEY") or "").strip()


def _ler_modelo() -> str:
    try:
        from django.conf import settings as _s

        v = getattr(_s, "GEMINI_VISION_MODEL", "") or ""
        if v:
            return v.strip()
    except Exception:
        pass
    return (os.getenv("GEMINI_VISION_MODEL") or "").strip() or MODELO_PADRAO


def _chave_da_propriedade(user) -> str:
    """Chave registrada na engrenagem para a propriedade do usuário, ou "".

    Tem precedência sobre a do ambiente. Nunca levanta: sem usuário, sem
    propriedade, sem registro ou sem cifra legível, devolve "" e o chamador
    cai para a chave do ambiente.
    """
    try:
        if user is None or not getattr(user, "is_authenticated", False):
            return ""
        prop = user.propriedades.first()
        if prop is None:
            return ""
        from app.models.ia import ChaveIA

        registro = ChaveIA.objects.filter(propriedade=prop).first()
        if registro is None:
            return ""
        chave = getattr(registro, "chave", "") or ""
        return chave.strip() if isinstance(chave, str) else ""
    except Exception:
        return ""


def _extrair_bytes(imagem: str) -> tuple[bytes | None, str, str]:
    """Valida o dataURL/b64 e devolve (bytes, mime, erro).

    Recusa antes de gastar quota: base64 inválido, vazio, grande demais ou
    com assinatura que não é imagem (PNG/JPEG/WEBP/GIF).
    """
    s = (imagem or "").strip()
    if not s:
        return None, "", "vazia"
    if "," in s:
        cabeca, s = s.split(",", 1)
        cabeca = cabeca.strip().lower()
        if "data:" not in cabeca or ";base64" not in cabeca:
            return None, "", "formato"
    else:
        cabeca = ""
    try:
        bruto = base64.b64decode(s, validate=True)
    except (binascii.Error, ValueError):
        return None, "", "base64"
    if not bruto:
        return None, "", "vazia"
    if len(bruto) > TAMANHO_MAX_B:
        return None, "", "grande"
    mime = ""
    if bruto[:8] == b"\x89PNG\r\n\x1a\n":
        mime = "image/png"
    elif bruto[:3] == b"\xff\xd8\xff":
        mime = "image/jpeg"
    elif bruto[:4] == b"RIFF" and bruto[8:12] == b"WEBP":
        mime = "image/webp"
    elif bruto[:4] in (b"GIF8",):
        mime = "image/gif"
    if not mime:
        # O dataURL pode declarar; confia nele só se for imagem.
        for cand in ("image/png", "image/jpeg", "image/webp", "image/gif"):
            if cand in cabeca:
                mime = cand
                break
    if not mime:
        return None, "", "formato"
    return bruto, mime, ""


def _texto_da_resposta(payload: Any) -> str:
    """Junta os trechos de texto da resposta do Gemini."""
    try:
        partes = payload["candidates"][0]["content"]["parts"]
    except (KeyError, IndexError, TypeError):
        return ""
    textos = [
        str(p.get("text") or "")
        for p in partes
        if isinstance(p, dict) and p.get("text")
    ]
    return "\n".join(textos).strip()


def _motivo_bloqueio(payload: Any) -> str:
    try:
        return str((payload.get("promptFeedback") or {}).get("blockReason") or "")
    except AttributeError:
        return ""


def _falha(motivo: str, erro: str) -> dict[str, Any]:
    return {
        "ok": False,
        "resposta": "",
        "provedor": "nenhum",
        "motivo": motivo,
        "erro": erro,
    }


def validar_chave_nuvem(chave: str, *, timeout_s: float = 15.0) -> dict[str, Any]:
    """Testa uma chave AINDA NÃO salva: válida, inválida ou erro de rede?

    Nunca persiste nada e nunca levanta. A pergunta mais barata possível
    (lista 1 modelo) — provar autenticação, não gastar quota de geração.
    Devolve sempre {ok, valido, motivo, erro, modelos}.
    """
    chave = (chave or "").strip()
    if not chave:
        return {
            "ok": False,
            "valido": False,
            "motivo": "sem_chave",
            "erro": "Cole a chave antes de testar.",
            "modelos": 0,
        }
    req = urllib.request.Request(
        "https://generativelanguage.googleapis.com/v1beta/models?pageSize=1",
        headers={"x-goog-api-key": chave},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as r:
            payload = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detalhe = ""
        try:
            detalhe = exc.read().decode("utf-8", "replace")[:2000]
        except Exception:
            detalhe = ""
        codigo = getattr(exc, "code", 0) or 0
        logger.warning("visao: validar chave HTTP %s", codigo)
        if codigo in (400, 403) and "API key" in detalhe:
            return {
                "ok": True,
                "valido": False,
                "motivo": "chave_invalida",
                "erro": "A nuvem recusou essa chave. Confira se copiou inteira.",
                "modelos": 0,
            }
        return {
            "ok": False,
            "valido": False,
            "motivo": "falha_nuvem",
            "erro": "Não consegui falar com a nuvem agora. Tente de novo.",
            "modelos": 0,
        }
    except Exception as exc:  # noqa: BLE001 — deliberado: ver docstring
        nome = exc.__class__.__name__
        logger.warning("visao: validar chave %s", nome)
        if "timed out" in str(exc) or "Timeout" in nome:
            motivo, erro = (
                "tempo_esgotado",
                "A nuvem demorou demais. Tente de novo.",
            )
        else:
            motivo, erro = (
                "falha_nuvem",
                "Não consegui falar com a nuvem agora. Tente de novo.",
            )
        return {
            "ok": False,
            "valido": False,
            "motivo": motivo,
            "erro": erro,
            "modelos": 0,
        }
    try:
        n = len(payload.get("models") or [])
    except AttributeError:
        n = 0
    return {"ok": True, "valido": True, "motivo": "", "erro": "", "modelos": n}


def _mapeia_http(codigo: int, detalhe: str, nome_modelo: str) -> dict[str, Any]:
    """Traduz um HTTPError do Gemini para motivo + frase honesta."""
    # 401 UNAUTHENTICATED entra aqui também: chave expirada, revogada ou
    # de formato que o gateway não aceita mais dão 401, não 403.
    if codigo == 401 or (codigo in (400, 403) and "API key" in detalhe):
        return _falha(
            "chave_invalida",
            "A chave do Gemini foi recusada. Fale com o administrador.",
        )
    if codigo == 404:
        return _falha(
            "modelo",
            f"O modelo {nome_modelo} não existe ou não está liberado. "
            "Fale com o administrador.",
        )
    if codigo == 429:
        return _falha(
            "limite",
            "A nuvem pediu calma (limite de uso). Tente de novo em instantes.",
        )
    if codigo == 400:
        return _falha(
            "pedido_recusado",
            "A nuvem recusou o pedido. Tente outra área ou reformule a pergunta.",
        )
    return _falha(
        "falha_nuvem",
        "A nuvem falhou agora. Tente de novo em instantes.",
    )


def _post_gemini(
    url: str, corpo: bytes, chave: str, timeout_s: float
) -> tuple[Any, Any]:
    """POST com UMA nova tentativa em timeout/5xx. Nunca levanta.

    Devolve (payload, None) no sucesso ou (None, falha), onde falha é
    ("http", codigo, detalhe) | ("tempo", texto) | ("rede", nome, texto).
    Quem chama mapeia para o seu contrato — este nível não decide mensagem.
    """
    req = urllib.request.Request(
        url,
        data=corpo,
        headers={"Content-Type": "application/json", "x-goog-api-key": chave},
    )
    # Uma nova tentativa em timeout/5xx: a primeira chamada costuma pagar
    # o "cold start" (TLS + modelo frio) e cair, com a segunda passando.
    # Só nesses casos — 4xx volta direto, sem gastar quota à toa.
    for tentativa in (1, 2):
        try:
            with urllib.request.urlopen(req, timeout=timeout_s) as r:
                return json.loads(r.read().decode("utf-8")), None
        except urllib.error.HTTPError as exc:
            # ANTES de URLError: HTTPError é subclasse e cairia no ramo
            # errado (tentaria de novo até em 400 de chave inválida).
            codigo = getattr(exc, "code", 0) or 0
            if codigo >= 500 and tentativa == 1:
                logger.warning("gemini: tentativa 1, HTTP %s; tentando de novo", codigo)
                try:
                    exc.read()
                except Exception:
                    pass
                continue
            detalhe = ""
            try:
                detalhe = exc.read().decode("utf-8", "replace")[:2000]
            except Exception:
                detalhe = ""
            logger.warning("gemini: HTTP %s", codigo)
            return None, ("http", codigo, detalhe)
        except (TimeoutError, urllib.error.URLError) as exc:
            texto = (
                str(exc.reason) if isinstance(exc, urllib.error.URLError) else str(exc)
            )
            nome = exc.__class__.__name__
            logger.warning("gemini: tentativa %s, %s: %s", tentativa, nome, texto[:200])
            if tentativa == 2:
                if "timed out" in texto or "Timeout" in nome:
                    return None, ("tempo", texto)
                return None, ("rede", nome, texto)
            continue
        except Exception as exc:  # noqa: BLE001 — deliberado: ver docstring
            nome = exc.__class__.__name__
            texto = str(exc)
            logger.warning("gemini: falha %s: %s", nome, texto[:200])
            return None, ("rede", nome, texto)
    return None, ("rede", "Esgotado", "")


def ver_imagem(
    imagem_b64: str,
    pergunta: str,
    *,
    modelo: str | None = None,
    timeout_s: float = TIMEOUT_PADRAO_S,
    user=None,
) -> dict[str, Any]:
    """Manda a imagem + pergunta ao Gemini e devolve o que ele VIU. Nunca levanta."""
    chave = _chave_da_propriedade(user) or _ler_chave()
    if not chave:
        return _falha(
            "sem_chave",
            "A visão está desligada: falta a chave do Gemini — registre na "
            "engrenagem (Agente da nuvem) ou configure GEMINI_API_KEY no "
            "servidor. Com ela, eu vejo a imagem de verdade.",
        )
    bruto, mime, problema = _extrair_bytes(imagem_b64)
    if bruto is None or problema == "vazia" or problema == "base64":
        return _falha(
            "imagem_invalida",
            "A imagem veio ilegível. Selecione a área outra vez.",
        )
    if problema == "grande":
        return _falha(
            "imagem_grande",
            "A imagem ficou grande demais. Selecione uma área menor.",
        )
    if problema:
        return _falha(
            "imagem_invalida",
            "Isso não é um PNG/JPEG válido. Selecione a área outra vez.",
        )
    pergunta = (pergunta or "").strip()[:2000] or (
        "O que você vê nesta imagem? Descreva os números, gráficos e o estado geral."
    )
    instrucao = (
        "Você é a AmplIA, assistente do agronegócio brasileiro. "
        "Responda em português, direto e prático. "
        "Descreva SÓ o que está visível na imagem. "
        "Se não houver nada útil, diga isso — nunca invente números."
    )
    corpo = json.dumps(
        {
            "contents": [
                {
                    "parts": [
                        {"text": instrucao + "\n\nPergunta do produtor: " + pergunta},
                        {
                            # ATENÇÃO ao casing: a API REST fala camelCase.
                            # snake_case é da biblioteca Python, e com ele a
                            # nuvem devolve 400 "Invalid JSON payload".
                            "inlineData": {
                                "mimeType": mime,
                                "data": base64.b64encode(bruto).decode(),
                            }
                        },
                    ]
                }
            ],
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 400},
        }
    ).encode()
    nome_modelo = (modelo or "").strip() or _ler_modelo()
    # A chave vai no HEADER, nunca na URL: URL aparece em log de acesso.
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{nome_modelo}:generateContent"
    payload, falha = _post_gemini(url, corpo, chave, timeout_s)
    if falha is not None:
        if falha[0] == "http":
            _, codigo, detalhe = falha
            return _mapeia_http(codigo, detalhe, nome_modelo)
        if falha[0] == "tempo":
            return _falha(
                "tempo_esgotado",
                "A nuvem demorou demais. Tente de novo, com uma área menor.",
            )
        return _falha(
            "falha_nuvem",
            "Não consegui falar com a nuvem agora. Tente de novo em instantes.",
        )
    if payload is None:
        return _falha(
            "falha_nuvem",
            "Não consegui falar com a nuvem agora. Tente de novo em instantes.",
        )
    bloqueado = _motivo_bloqueio(payload)
    if bloqueado:
        return _falha(
            "bloqueado",
            "A nuvem recusou esta imagem por segurança. Tente outra área.",
        )
    texto = _texto_da_resposta(payload)
    if not texto:
        return _falha(
            "resposta_vazia",
            "A nuvem não descreveu nada. Tente outra área ou reformule a pergunta.",
        )
    return {
        "ok": True,
        "resposta": texto,
        "provedor": "gemini",
        "motivo": "",
        "erro": "",
    }
