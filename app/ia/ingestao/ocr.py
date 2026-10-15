"""
ocr.py — a camada de OCR, com HONESTIDADE sobre o que esta disponivel.

O PROBLEMA QUE ESTE MODULO CORRIGE
----------------------------------
Ja existia um fluxo de imagem em `app/ia/views.py` (`imagem_estoque`), e ele
funcionava assim:

    try:
        import pytesseract
        texto = pytesseract.image_to_string(img, lang="por+eng")
    except Exception:
        texto = ""            # <-- some com a causa

Neste projeto, `pytesseract` NAO esta instalado e o binario `tesseract` nao
esta no PATH. Entao o `except` disparava sempre, e o produtor recebia um
rascunho com **uma unica linha**: "imagem JPEG 800x600". Zero itens. Nenhum
aviso, nenhum log, nenhum erro. A degradacao era silenciosa, e um bug que se
esconde e um bug que nao se corrige.

Este modulo troca `except: silenciar` por `except: registrar`. A diferenca nao
e estetica: e a diferenca entre um produtor que sabe que o sistema nao leu a
nota e um produtor que acredita que a nota estava em branco.

O QUE CADA MOTOR FAZ BEM (e porque a escolha nao e arbitraria)
--------------------------------------------------------------
* `nfe_xml`  — nota fiscal **eletronica em XML**: o XML ja vem estruturado.
               Nem precisa de OCR. E o caso que o produtor mais usa e o mais
               facil de acertar. Confianca 1.0, deterministico.
* `tesseract` — documento **impresso**: NFe em PDF/imagem, nota de fornecedor.
               OCR deterministico e exatamente a ferramenta certa para fonte
               impressa de alto contraste. Offline, gratis, privado.
* `nenhum`   — caligrafia. OCR deterministico aqui e lixeira: produz garbage
               confiante, que e pior que nao produzir nada. E o caso que
               justifica visao assistida no servidor (ver `visao.py`).

Ordem: XML antes de imagem. Descarregar XML e procurar numero de chave em
texto faz o trabalho duas vezes e com pior resultado.
"""

from __future__ import annotations

import io
import logging
import os
import re
from typing import Any

logger = logging.getLogger(__name__)

#: Limite defensivo. Uma foto de celular tem 3-12 MB; acima disso, o
#: PIL decodifica e o Tesseract pode estourar RAM num servidor pequeno.
MAX_BYTES = 12 * 1024 * 1024
MAX_PIXELS = 24_000_000
OCR_TIMEOUT = 30

_CACHE_PILLOW: dict[str, bool] = {}


# --------------------------------------------------------------------------
# Disponibilidade — com cache, mas SEM cachear erro
# --------------------------------------------------------------------------


def _modulo_disponivel(nome: str) -> Any | None:
    """Importa o módulo e devolve None se faltar. Cacheia so o sucesso.

    Cachear o fracasso seria um segundo bug: instalar o pacote durante o
    processo nao reverteria o cache, e o OCR continuaria "indisponivel" ate o
    restart.
    """
    if nome in _CACHE_PILLOW:
        return True
    try:
        __import__(nome)
    except Exception:  # noqa: BLE001
        return None
    _CACHE_PILLOW[nome] = True
    return True


def limpar_cache() -> None:
    _CACHE_PILLOW.clear()


def tesseract_disponivel() -> bool:
    """Tem pytesseract E o binário? Ambos são necessários.

    `import pytesseract` succeeding não quer dizer nada: o pacote só chama o
    executável externo, que numa imagem de container costuma não existir. Se o
    binário faltar, `image_to_string` levanta `TesseractNotFoundError` — que é
    exatamente o que o `except` antigo engolia.
    """
    if _modulo_disponivel("pytesseract") is None:
        return False
    try:
        import pytesseract  # type: ignore

        _configurar_tesseract(pytesseract)
        pytesseract.get_tesseract_version()
        return True
    except Exception as e:  # noqa: BLE001
        logger.info(
            "OCR: pytesseract instalado mas o binario tesseract nao responde (%s). "
            "Ingestao de imagem impressa caira para rascunho manual.",
            e.__class__.__name__,
        )
        return False


def _configurar_tesseract(pytesseract: Any) -> None:
    """O caminho informado pelo operador também precisa valer na execução."""
    comando = os.getenv("TESSERACT_CMD")
    if comando:
        pytesseract.pytesseract.tesseract_cmd = comando


def idiomas_disponiveis() -> list[str]:
    try:
        import pytesseract  # type: ignore

        _configurar_tesseract(pytesseract)
        return sorted(pytesseract.get_languages(config=""))
    except Exception as e:  # noqa: BLE001
        logger.info("OCR: nao foi possivel consultar idiomas (%s)", e.__class__.__name__)
        return []


def diagnostico() -> dict[str, Any]:
    """Para o health check e para a tela de configuracao da IA.

    O campo `nota` explica o efeito pratico, nao a causa tecnica: quem le isto
    e o produtor (ou o suporte dele), e a pergunta que ele tem e "vai ler minha
    nota?", nao "o modulo pytesseract importou?".
    """
    tem_pillow = _modulo_disponivel("PIL") is not None
    tem_tess = tesseract_disponivel()
    idiomas = idiomas_disponiveis() if tem_tess else []
    pronto = tem_pillow and tem_tess and "por" in idiomas
    if pronto:
        nota = "OCR de documento impresso disponivel."
    elif tem_tess and "por" not in idiomas:
        nota = (
            "OCR sem o idioma portugues (por). Instale os dados desse idioma "
            "ou envie a NFe em XML."
        )
    else:
        nota = (
            "Sem OCR instalado: imagem impressa nao vira texto automaticamente. "
            "Envie a NFe em XML (ja vem estruturado, nao precisa de OCR) ou "
            "digite os numeros. O rascunho mostra um aviso, nao um erro mudo."
        )
    return {
        "pillow": tem_pillow,
        "tesseract": tem_tess,
        "idiomas": idiomas,
        "portugues_disponivel": "por" in idiomas,
        "pronto": pronto,
        "tesseract_cmd": os.getenv("TESSERACT_CMD", "tesseract"),
        "modo_padrao": "nfe-xml+tesseract" if pronto else "nfe-xml",
        "nota": nota,
    }


# --------------------------------------------------------------------------
# Deteccao de tipo
# --------------------------------------------------------------------------

#: Chave de acesso de NFe: 44 digitos. O padrao mais forte de "isto e nota".
RE_CHAVE_ACESSO = re.compile(r"\b\d{44}\b")
#: CNPJ: 14 digitos com pontuacao opcional.
RE_CNPJ = re.compile(r"\b\d{2}\.?\d{3}\.?\d{3}\.?\d{4}-?\d{2}\b")
#: XML de NFe e auto-evidente pelo prologo.
RE_XML_NFE = re.compile(rb"<\?xml|<nfeProc|<infNFe", re.IGNORECASE)


def parece_nfe_xml(bruto: bytes) -> bool:
    return bool(RE_XML_NFE.search(bruto[:4000]))


# --------------------------------------------------------------------------
# Extracao
# --------------------------------------------------------------------------


def extrair_texto(bruto: bytes, *, lang: str = "por+eng") -> dict[str, Any]:
    """Texto de uma imagem impressa. PDF precisa ser rasterizado antes.

    Devolve sempre `{texto, linhas, motor, aviso, confianca}`.

    `aviso` é a peça que faltava: quando o motor não roda, o aviso diz o quê
    e por quê, e o rascunho que o produtor vê carrega essa mensagem.
    """
    if not bruto:
        return _vazio("arquivo-vazio", "Nenhum arquivo recebido.")

    if len(bruto) > MAX_BYTES:
        return _vazio(
            "arquivo-grande",
            f"Arquivo de {len(bruto) // (1024 * 1024)} MB excede o limite de "
            f"{MAX_BYTES // (1024 * 1024)} MB. Tire a foto com menos zoom.",
        )

    if bruto.lstrip().startswith(b"%PDF-"):
        return _vazio(
            "pdf-nao-suportado",
            "Envie a NFe em XML ou uma imagem da pagina. "
            "A leitura direta de PDF ainda nao esta disponivel neste fluxo.",
        )

    try:
        from PIL import Image, ImageOps
    except Exception as e:  # noqa: BLE001
        logger.error("OCR: Pillow ausente — %s", e)
        return _vazio(
            "sem-pillow",
            "O servidor nao tem processador de imagem (Pillow). "
            "Envie o texto digitado ou a NFe em XML.",
        )

    try:
        with Image.open(io.BytesIO(bruto)) as original:
            # O tamanho comprimido não limita a RAM necessária para decodificar.
            if original.width * original.height > MAX_PIXELS:
                return _vazio(
                    "imagem-grande",
                    "A imagem tem resolucao muito alta. Reduza para ate 24 megapixels "
                    "ou envie a NFe em XML.",
                )
            meta = f"imagem {original.format or ''} {original.width}x{original.height}".strip()
            original.load()
            img = ImageOps.exif_transpose(original)
            # Transparência vira papel branco, sem apagar texto preto.
            if "A" in img.getbands() or "transparency" in img.info:
                rgba = img.convert("RGBA")
                fundo = Image.new("RGBA", rgba.size, "white")
                img = Image.alpha_composite(fundo, rgba)
            img = img.convert("RGB")
    except Exception as e:  # noqa: BLE001
        logger.warning("OCR: imagem ilegivel — %s: %s", e.__class__.__name__, e)
        return _vazio("imagem-invalida", "Nao consegui abrir a imagem. Envie uma foto valida ou a NFe em XML.")

    if not tesseract_disponivel():
        img.close()
        return {
            "texto": "",
            "linhas": [meta],
            "motor": "sem-ocr",
            "aviso": (
                "Este servidor nao tem OCR instalado, entao a foto nao foi lida. "
                "Copie os numeros ou envie a NFe em XML — o XML ja vem "
                "estruturado e nao precisa de OCR. Modo rascunho."
            ),
            "confianca": 0.0,
            "requer_revisao": True,
        }

    idiomas = idiomas_disponiveis()
    solicitados = [idioma for idioma in lang.split("+") if idioma]
    if not solicitados or solicitados[0] not in idiomas:
        img.close()
        return _vazio(
            "idioma-indisponivel",
            "O idioma principal do documento nao esta instalado no OCR. "
            "Instale o idioma portugues (por) ou envie a NFe em XML.",
        )
    selecionados = [idioma for idioma in solicitados if idioma in idiomas]

    try:
        import pytesseract  # type: ignore

        # Documento completo pode ter colunas e tabelas; PSM 6 assume bloco único.
        config = "--psm 3"
        texto = (
            pytesseract.image_to_string(
                img, lang="+".join(selecionados), config=config, timeout=OCR_TIMEOUT
            ) or ""
        ).strip()
    except Exception as e:  # noqa: BLE001
        logger.error("OCR: tesseract falhou — %s: %s", e.__class__.__name__, e)
        return {
            "texto": "",
            "linhas": [meta],
            "motor": "tesseract-falhou",
            "aviso": f"O OCR falhou ({e.__class__.__name__}). Rascunho manual.",
            "confianca": 0.0,
            "requer_revisao": True,
        }
    finally:
        img.close()

    linhas = [l.strip() for l in texto.splitlines() if l.strip()]
    if not linhas:
        return {
            "texto": "",
            "linhas": [meta],
            "motor": "tesseract-vazio",
            "aviso": (
                "A foto chegou sem texto legivel. Pode ser imagem muito clara, "
                "suja demais, ou o servidor precisa de OCR instalado. Rascunho manual."
            ),
            "confianca": 0.0,
            "requer_revisao": True,
        }

    return {
        "texto": texto,
        "linhas": linhas,
        "motor": "tesseract",
        "aviso": "Confira os itens, quantidades e valores antes de gravar. Prefira a NFe em XML quando disponivel.",
        "confianca": 0.6,  # impresso: bom, mas nao confiavel para gravar direto
        "requer_revisao": True,
        "idioma": "+".join(selecionados),
    }


def _vazio(motor: str, aviso: str) -> dict[str, Any]:
    return {"texto": "", "linhas": [], "motor": motor, "aviso": aviso, "confianca": 0.0, "requer_revisao": True}
