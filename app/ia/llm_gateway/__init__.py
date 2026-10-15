"""
llm_gateway — camada de isolamento das chamadas de LLM.

POR QUE ESTE MÓDULO EXISTE
--------------------------
Diretriz 1 do `docs/MAPA_DE_IMPLEMENTACAO_AMPLIA.md`:

    "Abstração Total de IA: Isole as chamadas de LLM (GPT, Claude, Llama) em
     uma camada `llm_gateway`. O resto do sistema não pode saber qual IA estamos
     usando hoje, para ser fácil trocar no futuro (Local vs Cloud)."

O resto do sistema fala com `chamar()`. Ninguém importa `openai` ou
`anthropic` fora daqui. Amanhã trocar de provedor é uma linha em config.

DECISÃO D1 (primeira versão): LOCAL-FIRST, LLM COMO OPT-IN
---------------------------------------------------------
Na primeira versão, o AmplIA era 100% determinístico: `app/ia/intents*.py`
tinha ~114 KB de intents locais e `app/ia/sandbox.py` já tinha allowlist de
fontes, detecção de injeção e trilha de auditoria. Não havia nenhuma chamada
de LLM no projeto.

Então o gateway nasceu com o provedor `local` como PADRÃO. Isso preserva três
coisas que importam mais que "ter IA de moda":

1. **Offline-first** (diretriz 4): sem chave, sem rede, sem chamada. O
   produtor em pé no meio do talhão continua registrando.
2. **Soberania sobre os dados** (o diferencial que o `PLANO_CRIADOR_LIVRE`
   vende): o texto do produtor não sai do servidor por padrão.
3. **Auditabilidade**: o gateway local é determinístico
   e testável.

LLMs entram como **opt-in por fonte**, na mesma linha do concept de
`app/ia/fontes.py` (allowlist explícita, negada por padrão). Um provedor de
LLM só é usado se o administrador o HABILITAR explicitamente.

CONTRATO DE `chamar()`
----------------------
`chamar()` NUNCA levanta. Devolve sempre um dicionário com as mesmas chaves.
Se o provedor falhar, a rede cair ou não houver chave, cai no local e o
sistema continua — é o requisito de resiliência, não um conveniência.

    {
      "ok": bool,
      "texto": str,
      "provedor": str,        # quem respondeu de fato
      "pedido": str,          # "local" | "remoto"
      "erro": str,            # vazio se ok
      "duracao_ms": int,
    }
"""

from __future__ import annotations

import logging
import time
from collections.abc import Iterable
from typing import Any

logger = logging.getLogger(__name__)

#: Nomes de provedores conhecidos. Um nome fora desta lista é recusado sem
#: mesmo tentar importar o módulo — allowlist fechada por padrão.
#:
#: `openai-compatible` entra na allowlist **sem** virar o default. A
#:allowlist é o que é *permitido*; o default é o que é *usado*. Mantê-los
#: separados é o que permite ter o código pronto e a decisão fechada:
#: enquanto `AMPLIA_LLM_PROVEDOR` não disser o contrário, o `local` responde
#: e o texto do produtor não sai do servidor.
#:
#: Este nome cobre a API da OpenAI e qualquer serviço compatível com ela
#: (Ollama, vLLM, LM Studio, Together, Groq) — o que torna a troca de
#: provedor uma linha de configuração em vez de um módulo novo.
PROVEDORES_CONHECIDOS = ("local", "openai-compatible", "gemini")

#: Prefixo das variáveis de ambiente que a allowlist reconhece.
ENV_PROVEDOR = "AMPLIA_LLM_PROVEDOR"
ENV_CHAVE = "AMPLIA_LLM_CHAVE"
ENV_MODELO = "AMPLIA_LLM_MODELO"
ENV_TIMEOUT = "AMPLIA_LLM_TIMEOUT_S"
ENV_BASE_URL = "AMPLIA_LLM_BASE_URL"

#: Tempo máximo de uma chamada remota. O default é curto de propósito: uma
#: chamada de IA que demora 30s trava a interface do produtor no campo.
TIMEOUT_PADRAO_S = 20.0


class ProvedorNaoPermitido(Exception):
    """Provedor fora da allowlist. Levantado só por `resolver_provedor`."""


class ProvedorIndisponivel(Exception):
    """Provedor permitido mas não utilizável agora (falta chave, etc.)."""


# --------------------------------------------------------------------------
# Provedores
# --------------------------------------------------------------------------


class Provedor:
    """Interface de um provedor. Uma subclasse precisa de `nome` e `responder`."""

    nome: str = ""
    requer_chave: bool = False

    def disponivel(self, cfg: dict[str, Any]) -> bool:
        return True

    def responder(self, prompt: str, cfg: dict[str, Any], **kwargs: Any) -> str:
        raise NotImplementedError


class ProvedorLocal(Provedor):
    """Padrão determinístico: nenhum modelo, nenhuma rede, resposta fixa.

    Não finge que é uma IA. Devolve um texto honesto dizendo que a capability
    está desligada, e devolve junto o que o sistema sabe fazer de verdade. É
    preferível a uma resposta inventada: o produtor precisa poder confiar que
    quando a AmplIA afirma algo, aquilo veio do banco dele.

    `eco` existe para teste e depuração — devolve o próprio prompt, o que
    permite verificar o caminho completo (rota, auditoria, contrato) sem
    depender de rede. Não é usado em produção.
    """

    nome = "local"
    requer_chave = False

    def responder(self, prompt: str, cfg: dict[str, Any], **kwargs: Any) -> str:
        if kwargs.get("eco"):
            return f"[local-eco] {prompt}"
        return (
            "A capacidade de geração por modelo está desligada neste "
            "instalação. O que eu consigo fazer agora, usando os dados da sua "
            "fazenda: consultar estoque, talhões, safras, clima, tarefas do "
            "Kanban e registrar lançamentos."
        )


#: Registro nome -> classe. Uma entrada por provedor habilitado.
_REGISTRO: dict[str, type] = {"local": ProvedorLocal}


class ProvedorOpenAICompativel(Provedor):
    """Qualquer endpoint compatível com a API de chat da OpenAI.

    POR QUE "COMPATÍVEL" E NÃO "OPENAI"
    ------------------------------------
    A mesma API é servida pela OpenAI, pelo Ollama na máquina do produtor,
    pelo vLLM, pelo LM Studio, pela Together, pela Groq. Suportar o formato
    e não o fornecedor é o que faz a promessa do módulo — *"amanhã trocar de
    provedor é uma linha em config"* — verdadeira de facto, e não apenas
    no que respeita a hosted.

    UMA REGRA QUE NÃO SE NEGOCIA
    ----------------------------
    Este provedor leva o texto do produtor para fora do servidor. Por isso
    é `requer_chave = True` (sem chave, `resolver_provedor` recua para o
    `local`), e por isso NENHUMA fonte o usa por omissão: quem o activa
    Passa por `AMPLIA_LLM_PROVEDOR=openai-compatible` e por uma chave, e
    ambas as coisas são uma decisão consciente.

    O `local` continua a ser a resposta honesta quando não há chave, quando
    a rede falha, ou quando o modelo demora mais do que `timeout_s`. É o
    que `chamar()` garante: nunca levanta, e o produtor nunca vê um erro de
    IA — vê a resposta sem modelo.
    """

    nome = "openai-compatible"
    requer_chave = True

    def responder(self, prompt: str, cfg: dict[str, Any], **kwargs: Any) -> str:
        import json as _json
        import urllib.request

        base = (cfg.get("base_url") or "https://api.openai.com/v1").rstrip("/")
        modelo = cfg.get("modelo") or ""
        if not modelo:
            raise ProvedorIndisponivel(
                "AMPLIA_LLM_MODELO em falta — um endpoint compativel precisa "
                "de saber QUE modelo. Sem isso, chamar() degrada para 'local'."
            )
        corpo = _json.dumps(
            {
                "model": modelo,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": float(cfg.get("temperatura") or 0.2),
                "max_tokens": int(cfg.get("max_tokens") or 400),
            }
        ).encode()
        req = urllib.request.Request(
            f"{base}/chat/completions",
            data=corpo,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {cfg.get('chave') or ''}",
            },
        )
        with urllib.request.urlopen(
            req, timeout=float(cfg.get("timeout_s") or 20)
        ) as r:
            payload = _json.loads(r.read().decode("utf-8"))
        return (payload["choices"][0]["message"]["content"] or "").strip()


_REGISTRO["openai-compatible"] = ProvedorOpenAICompativel


def registrar_provedor(nome: str, classe: type) -> None:
    """Registra um provedor novo. Usado por testes e por extensões futuras.

    Não valida `nome` contra `PROVEDORES_CONHECIDOS`: essa lista é a allowlist
    *de uso*, o registro é a allowlist *de código*. Registrar não habilita —
    habilitar é `configurar_provedor()` ou a variável de ambiente.
    """
    if not nome or not isinstance(classe, type) or not issubclass(classe, Provedor):
        raise ValueError(f"provedor invalido: {nome!r}")
    _REGISTRO[nome] = classe


def provedores_conhecidos() -> Iterable[str]:
    return tuple(sorted(_REGISTRO))


# --------------------------------------------------------------------------
# Configuração e allowlist
# --------------------------------------------------------------------------


def _ler_config() -> dict[str, Any]:
    """Lê a config do gateway de settings e do ambiente.

    Settings tem precedência sobre o ambiente: é o jeito de um ambiente
    (dev/staging/prod) fixar o provedor sem depender do `.env` da máquina.
    O ambiente é o fallback, para rodar a fonte local sem configurar nada.
    """
    import os

    from django.conf import settings

    base = getattr(settings, "LLM_GATEWAY", None) or {}
    return {
        "provedor": base.get("provedor") or os.getenv(ENV_PROVEDOR) or "local",
        "chave": base.get("chave") or os.getenv(ENV_CHAVE) or "",
        "modelo": base.get("modelo") or os.getenv(ENV_MODELO) or "",
        "base_url": base.get("base_url") or os.getenv(ENV_BASE_URL) or "",
        "timeout_s": float(
            base.get("timeout_s") or os.getenv(ENV_TIMEOUT) or TIMEOUT_PADRAO_S
        ),
    }


#: Cache do config, para não reparsear settings/env a cada chamada.
#: O gateway é chamado em request;_settings access é caro relative a um
#: dict lookup. Invalida em teste por `limpar_cache()`.
_CACHE: dict[str, Any] = {}


def limpar_cache() -> None:
    _CACHE.clear()


def config() -> dict[str, Any]:
    if "cfg" not in _CACHE:
        _CACHE["cfg"] = _ler_config()
    return _CACHE["cfg"]


def configurar_provedor(
    nome: str, *, chave: str = "", modelo: str = "", base_url: str = ""
) -> None:
    """Habilita um provedor para o processo atual. Usado por setup e testes."""
    if nome not in _REGISTRO:
        raise ProvedorNaoPermitido(
            f"provedor {nome!r} nao registrado; conhecidos: {list(_REGISTRO)}"
        )
    cfg = _ler_config()
    cfg.update(
        {"provedor": nome, "chave": chave, "modelo": modelo, "base_url": base_url}
    )
    _CACHE["cfg"] = cfg


def resolver_provedor(cfg: dict[str, Any] | None = None) -> Provedor:
    """Devolve a instância do provedor configurado, ou o local como reserva.

    Allowlist: um nome desconhecido NÃO vira `importlib` dinâmico. Rejeita e
    devolve o local. Sem chave, um provedor que a exige não é usado.
    """
    cfg = cfg or config()
    nome = cfg.get("provedor") or "local"
    classe = _REGISTRO.get(nome)
    if classe is None:
        logger.warning(
            "llm_gateway: provedor %r desconhecido; usando 'local'. "
            "Provedores registrados: %s",
            nome,
            sorted(_REGISTRO),
        )
        return ProvedorLocal()
    prov = classe()
    if prov.requer_chave and not cfg.get("chave"):
        logger.warning(
            "llm_gateway: provedor %r exige chave e nenhuma esta configurada; "
            "usando 'local'.",
            nome,
        )
        return ProvedorLocal()
    return prov


def disponivel() -> dict[str, Any]:
    """Diagnóstico para a UI de configurações e para o health check.

    Não é cacheada junto com o config porque depende de `disponivel()` do
    provedor, que pode mudar com o ambiente.
    """
    cfg = config()
    prov = resolver_provedor(cfg)
    return {
        "provedor_configurado": cfg.get("provedor") or "local",
        "provedor_efetivo": prov.nome,
        "em_nuvem": prov.nome != "local",
        "tem_chave": bool(cfg.get("chave")),
        "modelo": cfg.get("modelo") or "",
        "registrados": list(_REGISTRO),
    }


# --------------------------------------------------------------------------
# Chamada
# --------------------------------------------------------------------------


def chamar(
    prompt: str,
    *,
    provedor: str | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Pede uma resposta ao provedor configurado. Nunca levanta.

    `provedor` sobrescreve a config só para esta chamada — é como uma fonte
    específica escolhe um provedor sem mexer no default do sistema.

    Retorna sempre as mesmas chaves (ver docstring do módulo). Um provedor
    remoto que estoure é registrado e o local assume; o produtor não vê erro
    de IA, vê a resposta honesta do local.
    """
    t0 = time.perf_counter()
    cfg = config().copy()
    if provedor:
        cfg["provedor"] = provedor

    p = resolver_provedor(cfg)
    remoto = p.nome != "local"
    try:
        texto = p.responder(prompt or "", cfg, **kwargs)
        ok, erro = True, ""
    except Exception as exc:  # noqa: BLE001 — é deliberado: ver docstring
        logger.warning(
            "llm_gateway: provedor %s falhou (%s: %s); degradando para 'local'",
            p.nome,
            exc.__class__.__name__,
            exc,
        )
        p = ProvedorLocal()
        remoto = False
        texto = p.responder(prompt or "", cfg, **kwargs)
        ok, erro = False, f"{exc.__class__.__name__}: {exc}"

    return {
        "ok": ok,
        "texto": texto,
        "provedor": p.nome,
        "pedido": "remoto" if remoto else "local",
        "erro": erro,
        "duracao_ms": int((time.perf_counter() - t0) * 1000),
    }
