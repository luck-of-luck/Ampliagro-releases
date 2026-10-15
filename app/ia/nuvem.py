"""Conversa com a nuvem (Gemini, texto) — o que o switch usa de verdade.

POR QUE ESTE MÓDULO EXISTE
--------------------------
O modo "Usar agente da nuvem" era só um adesivo no prompt do modelo local:
dizia "consulte diretamente a nuvem", e o modelo local não tem como sair
da máquina — ou ignorava, ou fingia. Este módulo é o caminho real: a
pergunta vai ao Gemini e a resposta volta, com a chave da propriedade
(engrenagem) ou do servidor, nunca no browser.

O QUE NÃO PASSA PELA NUVEM
--------------------------
A cascata determinística (wizards, intents de dados reais, sandbox) continua
local: a nuvem não vê o banco da fazenda e inventaria números. Só o passo
de RACIOCÍNIO (`raciocinarLlm`, dúvida/pergunta ambígua) é desviado — e com
falha, cai de volta no motor local sem dizer nada ao produtor além de
responder.

CONTRATO
--------
`conversar()` NUNCA levanta. Devolve sempre
{ok, resposta, provedor, motivo, erro} — o mesmo formato do
`llm_gateway.chamar()`.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.ia.visao import (
    _chave_da_propriedade,
    _falha,
    _ler_chave,
    _ler_modelo,
    _post_gemini,
    _texto_da_resposta,
)

logger = logging.getLogger(__name__)

#: Teto da conversa enviada: últimas N mensagens, M chars cada. Contexto
#: curto de propósito — cada token de histórico é latência e quota.
MAX_MSGS = 8
MAX_TEXTO = 500


def _instrucao(fazenda: str = "") -> str:
    base = (
        "Você é a AmplIA, assistente do agronegócio brasileiro. "
        "Responda em português, direto e prático. "
        "Nunca invente números ou dados: sem dado real, diga que não tem "
        "e sugira onde consultar no sistema."
    )
    if fazenda:
        base += f" Fazenda do produtor: {fazenda}."
    return base


def _fazenda_de(user) -> str:
    try:
        if user is None or not getattr(user, "is_authenticated", False):
            return ""
        prop = user.propriedades.first()
        nome = getattr(prop, "nome", "") if prop is not None else ""
        return str(nome or "").strip()[:80]
    except Exception:
        return ""


def _normaliza(mensagens) -> list:
    """Poda e traduz papéis: a REST quer user/model, não user/assistant."""
    normais = []
    for m in mensagens or []:
        if not isinstance(m, dict):
            continue
        papel = "model" if str(m.get("role") or "") == "assistant" else "user"
        texto = str(m.get("content") or "").strip()[:MAX_TEXTO]
        if not texto:
            continue
        normais.append({"role": papel, "content": texto})
    return normais[-MAX_MSGS:]


def conversar(
    mensagens,
    user=None,
    *,
    modelo: str | None = None,
    timeout_s: float = 45.0,
) -> dict[str, Any]:
    """Manda a conversa ao Gemini e devolve a resposta. Nunca levanta."""
    normais = _normaliza(mensagens)
    if not any(m["role"] == "user" for m in normais):
        return _falha(
            "sem_pergunta",
            "Não há pergunta para mandar à nuvem.",
        )
    chave = _chave_da_propriedade(user) or _ler_chave()
    if not chave:
        return _falha(
            "sem_chave",
            "O agente da nuvem está desligado: falta a chave do Gemini — "
            "registre na engrenagem (Agente da nuvem) ou configure "
            "GEMINI_API_KEY no servidor.",
        )
    nome_modelo = (modelo or "").strip() or _ler_modelo()
    corpo = json.dumps(
        {
            "systemInstruction": {"parts": [{"text": _instrucao(_fazenda_de(user))}]},
            "contents": [
                {"role": m["role"], "parts": [{"text": m["content"]}]} for m in normais
            ],
            "generationConfig": {"temperature": 0.3, "maxOutputTokens": 500},
        }
    ).encode()
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{nome_modelo}:generateContent"
    payload, falha = _post_gemini(url, corpo, chave, timeout_s)
    if falha is not None:
        if falha[0] == "http":
            _, codigo, detalhe = falha
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
            return _falha(
                "falha_nuvem",
                "A nuvem falhou agora. Seguindo no motor local.",
            )
        if falha[0] == "tempo":
            return _falha(
                "tempo_esgotado",
                "A nuvem demorou demais. Seguindo no motor local.",
            )
        return _falha(
            "falha_nuvem",
            "Não consegui falar com a nuvem agora. Seguindo no motor local.",
        )
    if payload is None:
        return _falha(
            "falha_nuvem",
            "Não consegui falar com a nuvem agora. Seguindo no motor local.",
        )
    try:
        bloqueado = str((payload.get("promptFeedback") or {}).get("blockReason") or "")
    except AttributeError:
        bloqueado = ""
    if bloqueado:
        return _falha(
            "bloqueado",
            "A nuvem recusou essa conversa. Seguindo no motor local.",
        )
    texto = _texto_da_resposta(payload)
    if not texto:
        return _falha(
            "resposta_vazia",
            "A nuvem não respondeu. Seguindo no motor local.",
        )
    return {
        "ok": True,
        "resposta": texto,
        "provedor": "gemini",
        "motivo": "",
        "erro": "",
    }
