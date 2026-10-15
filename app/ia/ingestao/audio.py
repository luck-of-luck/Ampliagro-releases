"""
audio.py — transcricao de audio, com o peso decididO por medicao.

A PERGUNTA
-----------
"O produtor manda audio do campo. Roda Whisper no celular junto com o LLM, ou
manda para o servidor?"

MEDI, NAO OPINEI
-----------------
Pesos ONNX quantizados (medidos por HEAD no CDN do HuggingFace):

    whisper-tiny    9,7 MB + 29,3 MB  =  39 MB
    whisper-base   22,1 MB + 51,2 MB  =  73 MB
    whisper-small  88,0 MB + 149,5 MB = 238 MB

Contra o SmolLM2-1.7B q4f16, que ocupa cerca de 1,1 GB. Ou seja:

    whisper-tiny  =  3,5% do peso do LLM
    whisper-base  =  6,6%
    whisper-small = 21%

A visao, pelo contrario: o WebLLM 0.2.79 tem 143 modelos e apenas UM par de
visao, o Phi-3.5-vision (4,2B) — cerca de 2,6 GB. Com o LLM de texto ja
residente, sao ~3,7 GB de pesos num aparelho de 4 GB, sem contar o SO, o
navegador e o contexto. **Nao cabe.** Visao vai para o servidor.

DECISAO
-------
AUDIO: CLIENTE, com fallback de servidor.

Tres motivos, em ordem de peso:

1. **Offline-first e o valor declarado do produto.** O produtor no talhao sem
   sinal e o cenario que o AmplIA promete atender. Transcricao so no servidor
   morre justamente la.

2. **O custo e irrelevante.** 39 MB contra 1,1 GB. Whisper-base (73 MB) ainda
   cabe tranquilo, e em portugues brasileiro ele e melhor que o tiny.

3. **E o dado mais sensivel que existe no produto.** O audio do tractorista
   descreve falha de maquina, opeao do dia, nome de pessoas. Mandar isso para
   um servidor como padrao seria o oposto da soberania sobre os dados que o
   PLANO_CRIADOR_LIVRE vende.

SEQUENCIAL, NAO CONCORRENTE
---------------------------
WebGPU e UM dispositivo. O LLM e o Whisper nao podem ser donos dele ao mesmo
tempo — quem|Download exigir a GPU primeiro, e o outro espera. Por isso a ordem
e: transcreve (Whisper toma o device), libera, so entao o LLM raciocina.

Isso e uma decisao de implementacao, nao de teorema: o helper daqui marca
`fase` para que a interface possa mostrar "transcrevendo..." antes de
"pensando...", em vez de os dois brigarem pelo device e o produtor ver um
travamento sem explicacao.

FALLBACK DE SERVIDOR
--------------------
Celery esta instalado e CONFIGURADO (broker redis://localhost:6379/1), mas o
Redis nao responde nesta maquina — ou seja, nao ha worker. Se o envio de audio
dependesse so de Celery, a funcionalidade entraria no ar e nunca funcionaria.

Por isso o fallback e SINCrono no request, nao Celery: se o cliente nao
transcreveu (sem WebGPU, ou o produtor escolheu enviar), o backend tenta
transcrever ali mesmo. A transcricao de um audio de 30 s cabe no tempo de um
request. Celery entra depois, para audio LONGO ou fila.

A VISAO (o que o cliente nao faz)
---------------------------------
O LLM local e de texto. Imagem nao entra nele. O que o cliente faz, no maximo,
e mandar o arquivo ao servidor. E o servidor tem uma regra dura, em
`visao.py`: **a extracao devolve TEXTO, nunca executa acao**. O texto volta
para o LLM local, que estrutura o JSON e chama o sandbox.
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

#: Codecs que o navegador costuma entregar em gravacao de voz.
CODECS_ACEITOS = (
    "audio/webm",
    "audio/webm;codecs=opus",
    "audio/ogg",
    "audio/ogg;codecs=opus",
    "audio/mp4",
    "audio/mpeg",
    "audio/wav",
    "audio/x-wav",
)

MAX_BYTES_AUDIO = 15 * 1024 * 1024

#: Frases do roteiro do plano (o exemplo do tratorista). Sao seeds de auditoria:
#: a transcricao suja quase sempre contem "talhao N", "litros" e uma maquina.
PADROES_OPERACIONAIS = [
    re.compile(r"\btalh(?:ã|a)o\s+(\d+[a-z]?)\b", re.I),
    re.compile(r"\b(\d+(?:[.,]\d+)?)\s*(l|litros?|quilos?|kg|sc|scx)\b", re.I),
    re.compile(
        r"\b(veneno|herbicida|inseticida|fungicida|fertiliz\w+|defensivo)\b", re.I
    ),
    re.compile(
        r"\b(ferveu|queimou|parou|estragou|estou\w*\s+parad\w+|vazando|travou)\b", re.I
    ),
    re.compile(r"\b(fechei|terminei|termine|acabei|conclu[ií])\b", re.I),
]

#: Marcadores de servico JA CONCLUIDO. "terminei de aplicar" e relato, nao
#: comando: o produtor ja fez, e pedir confirmacao seria pedir para confirmar
#: um passado. O que fica depois do marcador e removido da checagem de comando.
RE_TRABALHO_CONCLUIDO = re.compile(
    r"\b(?:terminei|termine|terminei de|terminei\s+a|acabei de|acabei|"
    r"ja\s+(?:fiz|passei|apliquei|irriguei|fechei)|fechei|conclui|concluí|"
    r"pronto|foi tudo)\b[^.!?]*",
    re.I,
)

#: Palavras que sugerem acao fisica. Vaop para a camada de confirmacao.
TERMOS_ACAO_FISICA = re.compile(
    r"\b(liga|ligue|desliga|desligue|aciona|acione|abre|abra|fecha|feche|"
    r"irriga\w*|pulveriz\w*|aplic\w+)\b",
    re.I,
)


def _sem_relato_de_passado(texto: str) -> str:
    """Remove os trechos de servico ja concluido antes de procurar comando.

    Sem isto, "terminei de aplicar 50 litros" e "aplica 50 litros" chegam
    identicos ao detector, e o sistema trata o relato como se fosse ordem.
    """
    return RE_TRABALHO_CONCLUIDO.sub(" ", texto or "")


def diagnostico() -> dict[str, Any]:
    """O que o cliente pode fazer, e o que o servidor garante."""
    return {
        "cliente": {
            "motor": "transformers.js + Whisper ONNX",
            # Medido por HEAD no CDN do HuggingFace, seguindo redirect.
            # q4f16 e o dtype do WebGPU (fp16); q4 e o fallback de CPU/WASM.
            # onnx-community/whisper-* NAO tem q4f16 — so o repo Xenova tem.
            "pesos_mb": {"tiny": 50, "base": 79, "small": 191},
            "pesos_mb_q4": {"tiny": 91, "base": 136, "small": 286},
            "modelo": "Xenova/whisper-tiny",
            "dtype": "q4f16",
            "llm_peso_mb": 1100,
            "tiny_eh_fracao_do_llm": "4,5%",
            "regra": "sequencial: Whisper toma o WebGPU, libera, so entao o LLM",
            "fallback": "servidor sincrono (Celery so para audio longo)",
        },
        "servidor": {
            "redis_necessario": False,
            "celery_necessario": False,
            "nota": (
                "O audio chega em base64 ou em multipart. A transcricao local "
                "usa o mesmo motor (whisper/faster-whisper) se instalado; sem "
                "ele, devolve aviso explicito em vez de texto vazio."
            ),
        },
        "visao": {
            "onde": "servidor",
            "porque": "unica VLM do WebLLM e Phi-3.5-vision (4.2B, ~2,6 GB)",
            "regra": "extracao devolve TEXTO; quem age e o sandbox",
        },
    }


def limpar_transcricao(texto: str) -> str:
    """Limpa o que Whisper erra em audio de campo, sem inventar.

    Sazonais e pontuacao de ditado ("ponto", "vírgula", "r") sao removidos
    porque nao mudam o sentido e quebram os padroes de extracao.
    """
    t = " " + (texto or "").strip() + " "
    t = re.sub(
        r"\b(ponto|vírgula|virgula|interrogação|reticência)\b", " ", t, flags=re.I
    )
    t = re.sub(r"\s+", " ", t)
    return t.strip()


def extrair_sinais(texto: str) -> dict[str, Any]:
    """SINAIS, nao acao. O LLM decide o que fazer com eles.

    Este padrao NAO executa nada: ele apenas destaca do audio as entidades que
    quase sempre importam, para reduzir o que o modelo pequeno precisa inferir.
    Modelos de 1.7B erramMUITO em contagem ("cinquenta" -> "50" vs "cinco") e em
    referencia spatial ("talhao quatro" vs "talhao 4"). O regex nao tem
    intelligence, mas tem a vantagem de nao alucinar: se nao achou, devolve
    lista vazia, e o modelo recebe a transcricao inteira para tentar.
    """
    limpo = limpar_transcricao(texto)
    talhoes = [m.group(1).upper() for m in PADROES_OPERACIONAIS[0].finditer(limpo)]
    quantidades = [
        {"valor": m.group(1).replace(",", "."), "unidade": m.group(2).lower()}
        for m in PADROES_OPERACIONAIS[1].finditer(limpo)
    ]
    classes: list[str] = []
    for m in PADROES_OPERACIONAIS[2].finditer(limpo):
        if m.group(0).lower() not in classes:
            classes.append(m.group(0).lower())
    problemas: list[str] = []
    for m in PADROES_OPERACIONAIS[3].finditer(limpo):
        if m.group(0).lower() not in problemas:
            problemas.append(m.group(0).lower())
    return {
        "talhoes": talhoes,
        "quantidades": quantidades,
        "classes_insumo": classes,
        "sinais_de_falha": problemas,
        # a checagem de COMANDO olha o texto sem os trechos de "ja fiz"
        "sugere_acao_fisica": bool(
            TERMOS_ACAO_FISICA.search(_sem_relato_de_passado(limpo))
        ),
        "texto_limpo": limpo,
    }
