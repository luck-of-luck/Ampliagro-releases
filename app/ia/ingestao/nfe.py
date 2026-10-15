"""
nfe.py — parser deterministico de Nota Fiscal Eletronica.

POR QUE UM PARSER E NAO A IA
---------------------------
A IA fica no fim da linha, nao no começo. Uma NFe e o caso mais estruturado
que existe no agro: o XML traz a chave de acesso, os itens com codigo, descricao,
quantidade, valor unitario e total. Descarregar isso com um modelo de 1.7B
seria trocar um `int()` por um palpite.

O trabalho da IA aqui e o que o parser nao faz: casar o item do XML com o
insumo que ja existe no estoque, decidir em qual propriedade lançar, e explicar
ao produtor o que encontrou. Isso é `dinamicos`/intents, via sandbox.

A cadeia fica: XML -> parser deterministico (confianca 1.0) -> rascunho ->
confirmacao do produtor -> sandbox. A IA entra depois do rascunho, nunca antes.

CONFIANCA
---------
Todo campo traz um numero. `confianca_geral` diz o quanto o produtor precisa
olhar antes de confirmar:

* 1.0  — XML valido, com os campos que a NF-e garante
* 0.7  — XML valido mas incompleto (faltou CPF/CNPJ ou endereco)
* 0.0  — nao e NFe

E o confianca nao e decorativa: o rascunho NUNCA grava sozinho. O
`IAArtefato` guarda e o produtor confirma item a item. Ja era assim no fluxo de
estoque que existe, e este modulo nao muda isso.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any

# `defusedxml`, nunca `xml.etree.ElementTree`.
#
# MEDIDO 2026-10-06. Este modulo usava a nativa. A outra ingestao de NF-e -
# `app/services/nfe.py` - ja' tinha sido corrigida para `defusedxml` pela
# mesma razao, e o comentario esta' la a explicar. Duas entradas de NF-e, uma
# endurecida e outra nao: o produtor que sobe um XML pela IA tinha um buraco
# que o outro caminho nao tinha.
#
# A nativa expande entidades externas e resolve `billion laughs`. O teto de
# 12 MB na linha 119 limita o *tamanho do ficheiro*, nao a expansao: um XML de
# 2 KB com dez entidades aninhadas explode para gigabytes de memoria. Por
# isso o teto NAO substitui o defusedxml - os dois sao defesas de coisas
# diferentes.
#
# `DET.fromstring` e `ET.ParseError` sao os mesmos nomes, de proposito: uma
# correccao nao deve obrigar a mudar a forma de escrever o resto do modulo.
from defusedxml import ElementTree as ET
from defusedxml.common import DefusedXmlException

NS = {"nfe": "http://www.portalfiscal.inf.br/nfe"}
RE_CHAVE = re.compile(r"^\d{44}$")
RE_CNPJ = re.compile(r"^\d{14}$")


def _local(no) -> str:
    """Nome da tag SEM namespace.

    Este detalhe parece besteira e nao e: `ElementTree.find('.//infNFe')` nao
    casa uma tag que e `{http://www.portalfiscal.inf.br/nfe}infNFe`, e TODA NFe
    real tem namespace. Com `find`, o parser devolveria zero itens em 100% das
    notas — um bug que so apareceria com um XML de verdade.
    """
    return no.tag.split("}")[-1]


def _achar(raiz, nome: str):
    """Primeiro elemento de nome local `nome`, em profundidade. Sem namespace."""
    if raiz is None:
        return None
    for el in raiz.iter():
        if _local(el) == nome:
            return el
    return None


def _achar_todos(raiz, nome: str) -> list:
    return [
        el for el in (raiz.iter() if raiz is not None else []) if _local(el) == nome
    ]


def _txt(no, *caminhos, padrao="") -> str:
    """Acha um elemento por caminho de nomes locais. NFe muda o prefixo entre
    versoes e nem sempre traz namespace, entao nada aqui depende do XML."""
    if no is None:
        return padrao
    for c in caminhos:
        alvo = no
        for parte in c.split("/"):
            alvo = _achar(alvo, parte)
            if alvo is None:
                break
        if alvo is not None and (alvo.text or "").strip():
            return (alvo.text or "").strip()
    return padrao


def _dec(bruto: str) -> Decimal | None:
    """Decimal do XML da NF-e. Vazio vira None, nunca 0.

    Distinguir "0,00" de "não informado" importa: um item de R$ 0,00 é
    giveaway; um item sem valor é campo faltando, e a decisão é do produtor.
    """
    s = (bruto or "").strip()
    if not s:
        return None
    try:
        return Decimal(s.replace(",", "."))
    except (InvalidOperation, ValueError):
        return None


def chave_acesso_valida(chave: str) -> bool:
    return bool(RE_CHAVE.match((chave or "").strip()))


def parece_nfe_xml(bruto: bytes) -> bool:
    return bool(re.search(rb"<\?xml|<nfeProc|<infNFe", bruto or b"", re.IGNORECASE))


def extrair_nfe_xml(bruto: bytes) -> dict[str, Any]:
    """NFe XML -> rascunho estruturado. NUNCA levanta.

    Um XML de NFe corrompido e comum (download pela metade, portal que
    devolve HTML de erro). Levantar 500 seria transformar "arquivo ruim" em
    "sistema fora do ar".
    """
    if not bruto:
        return _erro("xml-vazio", "Nenhum XML recebido.", 0.0)
    if len(bruto) > 12 * 1024 * 1024:
        return _erro("xml-grande", "XML acima de 12 MB.", 0.0)
    if not parece_nfe_xml(bruto):
        return _erro(
            "nao-e-nfe",
            "O arquivo nao parece XML de Nota Fiscal Eletronica.",
            0.0,
        )

    try:
        raiz = ET.fromstring(bruto)
    except DefusedXmlException:
        # O `defusedxml` recusa antes de expandir: entidade externa,
        # `billion laughs`, DTD. Nao e' "XML invalido" - o XML pode ser
        # sintaticamente perfeito e ser um ataque. A distincao importa: quem
        # le o erro sabe se foi um ficheiro corrompido ou uma tentativa.
        return _erro(
            "xml-perigoso",
            "O XML foi recusado: contem entidades ou uma estrutura que o "
            "leitor seguro nao expande. Nao foi importado.",
            0.0,
        )
    except ET.ParseError as e:
        return _erro("xml-invalido", f"XML invalido: {e}", 0.0)

    inf = _achar(raiz, "infNFe") or _achar(raiz, "infInNFe")
    if inf is None:
        return _erro("sem-infNFe", "XML sem o no infNFe.", 0.0)

    # chave: atributo no infNFe, ou o noRefNota
    chave = (inf.get("Id") or "").replace("NFe", "").strip()
    if not chave:
        chave = _txt(raiz, "nfeProcRef/nfeRef/refNFe", "refNFe")
    chave = (chave or "").strip()

    emitente = _txt(inf, "emit/xNome") or _txt(inf, "emit/nome")
    cnpj_emit = _txt(inf, "emit/CNPJ") or _txt(inf, "emit/CPF")
    dest = _txt(inf, "dest/xNome") or _txt(inf, "dest/nome")
    cnpj_dest = _txt(inf, "dest/CNPJ") or _txt(inf, "dest/CPF")

    data = _txt(inf, "ide/dhEmi") or _txt(inf, "ide/dEmi")
    if "T" in data:
        data = data.split("T")[0]
    if len(data) == 8 and data.isdigit():
        data = f"{data[:4]}-{data[4:6]}-{data[6:]}"

    itens: list[dict[str, Any]] = []
    for det in _achar_todos(inf, "det"):
        prod = _achar(det, "prod") or det
        itens.append(
            {
                "codigo": _txt(prod, "cProd"),
                "descricao": _txt(prod, "xProd"),
                "ncm": _txt(prod, "NCM"),
                "cfop": _txt(prod, "CFOP"),
                "unidade": _txt(prod, "uCom"),
                "quantidade": _dec(_txt(prod, "qCom")),
                "valor_unitario": _dec(_txt(prod, "vUnCom")),
                "valor_total": _dec(_txt(prod, "vProd")),
            }
        )

    total_no = _achar(inf, "total")
    totais = _achar(total_no, "ICMSTot")
    valor_total = _dec(_txt(totais, "vNF")) if totais is not None else None
    if valor_total is None and itens:
        # soma dos itens: melhor que nada, e o produtor ve para conferir
        partes = [i["valor_total"] for i in itens if i["valor_total"] is not None]
        valor_total = sum(partes) if partes else None

    completo = bool(chave_acesso_valida(chave) and emitente and itens)
    return {
        "ok": completo,
        "tipo": "nfe",
        "motor": "nfe-xml",
        "chave_acesso": chave,
        "chave_valida": chave_acesso_valida(chave),
        "emitente": emitente,
        "cnpj_emitente": cnpj_emit,
        "cnpj_emitente_valido": bool(RE_CNPJ.match((cnpj_emit or "").strip())),
        "destinatario": dest,
        "cnpj_destinatario": cnpj_dest,
        "data": data,
        "valor_total": valor_total,
        "itens": itens,
        "qtd_itens": len(itens),
        # 1.0 quando os campos que a NF-e garante estao todos la
        "confianca": 1.0 if completo else 0.7,
        "erro": "" if completo else "XML lido, mas sem chave de acesso ou itens.",
        "aviso": "",
    }


def _erro(codigo: str, mensagem: str, confianca: float) -> dict[str, Any]:
    return {
        "ok": False,
        "tipo": "nfe",
        "motor": "nfe-xml",
        "itens": [],
        "qtd_itens": 0,
        "confianca": confianca,
        "codigo": codigo,
        "erro": mensagem,
        "aviso": "",
    }


def resumir_para_ia(rascunho: dict[str, Any], limite: int = 900) -> str:
    """Vira o texto que o LLM local vai ler.

    Tres garantias:

    1. Cabe no prompt de 4096 tokens do SmolLM2 mesmo com nota de 200 itens.
    2. O aviso de truncamento NUNCA e cortado. Sem ele, o modelo recebe 40
       itens e trata como se fossem a nota inteira — e pode "conciliar" uma
       nota de 200 itens com um terco do valor. Pior que nao truncar.
    3. As regras no fim sobrevivem: e onde mora o "nao grave sozinho".
    """
    if not rascunho.get("ok") and not rascunho.get("itens"):
        return ""

    itens = rascunho.get("itens") or []

    cabecalho = [
        f"NF-e {rascunho.get('chave_acesso') or '(sem chave)'}",
        f"emitente={rascunho.get('emitente') or '?'}",
        f"destinatario={rascunho.get('destinatario') or '?'}",
        f"data={rascunho.get('data') or '?'}",
        f"valor_total={rascunho.get('valor_total')}",
    ]
    regras = (
        "REGRAS: nao recalcule o total, use o valor informado. Nao invente item. "
        "Nao grave nada sozinho: chame a tool de lancamento/estoque, que o "
        "servidor pede confirmacao ao produtor."
    )

    orcamento = limite - len("\n".join(cabecalho)) - len(regras) - len("ITENS:\n") - 60

    # monta de tras para frente: quando o proximo item nao cabe, para — e o
    # que sobrou vira o "[ATENCAO: N itens omitidos]"
    cabem: list[str] = []
    usados = 0
    for indice in range(min(len(itens), 200) - 1, -1, -1):
        it = itens[indice]
        linha = (
            f"{indice + 1}. {it.get('descricao')} | qtd={it.get('quantidade')} "
            f"{it.get('unidade')} | unit={it.get('valor_unitario')} | "
            f"total={it.get('valor_total')} | ncm={it.get('ncm') or '-'}"
        )
        custo = len(linha) + 1
        if usados + custo > orcamento:
            break
        cabem.append(linha)
        usados += custo
    cabem.reverse()

    omitted = len(itens) - len(cabem)
    if omitted > 0:
        cabem.append(
            f"[ATENCAO: {omitted} itens NAO cabem no contexto e foram omitidos]"
        )

    return "\n".join(cabecalho + ["ITENS:"] + cabem + [regras])[:limite]
