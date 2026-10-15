import base64
import hashlib
import json
import logging
from datetime import date
from decimal import Decimal, InvalidOperation

from defusedxml.ElementTree import ParseError
from defusedxml.ElementTree import fromstring as defused_fromstring
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils import timezone

from app.models import (
    EstoqueItem,
    Insumo,
    ItemTributario,
    LancamentoFinanceiro,
    Propriedade,
    Safra,
)
from app.services.cfop import classificar as classificar_cfop

logger = logging.getLogger(__name__)

NS = {"nfe": "http://www.portalfiscal.inf.br/nfe"}


def _txt(no, caminho, ns=NS):
    if no is None:
        return ""
    el = no.find(caminho, ns)
    return (el.text or "").strip() if el is not None and el.text else ""


def _extrair_tributos(det) -> dict:
    """Os tributos de um `<det>` da NF-e.

    **Só extrai o que está verificado.** As tags vêm de
    `tests/fixtures/nfe_sample.xml` — o ficheiro de teste do próprio projecto.
    O grupo 9906 (`IBSCBS`) da reforma **não** é extraído: não há nenhuma nota
    com esse grupo neste repositório, e escrever as tags de memória seria
    inventar o layout. Fica `None` com motivo, que é a verdade.

    Um `CST` vazio dentro de `<ICMS00>` não é CST zero: é nota sem
    tributação declarada, e os dois são coisas diferentes.
    """
    imp = det.find("nfe:imposto", NS) or det.find("imposto")
    vazio = {
        "regime": "DESCONHECIDO",
        "base_calculo": None,
        "icms_cst": "",
        "icms_origem": "",
        "icms_aliquota": None,
        "valor_icms": None,
        "ipi_cst": "",
        "valor_ipi": None,
        "pis_cst": "",
        "valor_pis": None,
        "cofins_cst": "",
        "valor_cofins": None,
        "cbs_codigo": "",
        "ibs_codigo": "",
        "motivo": "",
    }
    if imp is None:
        vazio["motivo"] = (
            "a nota não traz grupo de tributos neste item — o imposto é "
            "desconhecido, não zero"
        )
        return vazio

    icms = imp.find("nfe:ICMS", NS) or imp.find("ICMS")
    # A forma é um dos filhos: ICMS00, ICMS10, ICMS20… Cada um é um wrapper
    # com os mesmos campos. Procuro o primeiro que exista, e não o ICMS00
    # à partida — uma nota com ICMS10 é comum e buscá-la só no ICMS00
    # perderia o imposto inteiro.
    grupo_icms = None
    if icms is not None:
        for filho in icms:
            if _txt(filho, "nfe:CST", NS) or _txt(filho, "CST"):
                grupo_icms = filho
                break

    ipi = imp.find("nfe:IPI", NS) or imp.find("IPI")
    pis = imp.find("nfe:PIS", NS) or imp.find("PIS")
    cofins = imp.find("nfe:COFINS", NS) or imp.find("COFINS")

    out = dict(vazio)
    out["base_calculo"] = (
        _decimo(_txt(grupo_icms, "nfe:vBC", NS)) if grupo_icms is not None else None
    )
    out["icms_cst"] = (
        _txt(grupo_icms, "nfe:CST", NS)[:4] if grupo_icms is not None else ""
    )
    out["icms_origem"] = (
        _txt(grupo_icms, "nfe:orig", NS)[:2] if grupo_icms is not None else ""
    )
    out["icms_aliquota"] = (
        _decimo(_txt(grupo_icms, "nfe:pICMS", NS)) if grupo_icms is not None else None
    )
    out["valor_icms"] = (
        _decimo(_txt(grupo_icms, "nfe:vICMS", NS)) if grupo_icms is not None else None
    )
    out["ipi_cst"] = (
        _txt(ipi, "nfe:IPINT/nfe:CST", NS)[:4]
        or _txt(ipi, "nfe:IPIINT/nfe:CST", NS)[:4]
    )
    out["pis_cst"] = _txt(pis, "nfe:PISNT/nfe:CST", NS)[:4]
    out["cofins_cst"] = _txt(cofins, "nfe:COFINSNT/nfe:CST", NS)[:4]

    tem_algum = any(
        out[k] not in (None, "")
        for k in (
            "base_calculo",
            "icms_cst",
            "valor_icms",
            "ipi_cst",
            "pis_cst",
            "cofins_cst",
        )
    )
    if tem_algum:
        out["regime"] = "ICMS_IPI"
    else:
        out["motivo"] = (
            "grupo <imposto> presente mas sem nenhum tributo preenchido — "
            "verifique a nota; o imposto não está apurável"
        )
    return out


def _decimo(bruto: str | None) -> Decimal | None:
    """XML da NF-e usa ponto decimal, mas um produtor que digitalizou pode ter
    mandado vírgula. `Decimal` e não `float`: um lançamento financeiro não
    passa por binário.
    """
    if bruto is None:
        return None
    txt = str(bruto).strip().replace(",", ".")
    if not txt:
        return None
    try:
        return Decimal(txt)
    except InvalidOperation:
        return None


def _data_emissao(root):
    """Data de emissão da NF-e (dEmi, YYYYMMDD) ou hoje."""
    el = root.find(".//nfe:infNFe/nfe:ide/nfe:dEmi", NS)
    if el is None or not el.text:
        return timezone.localdate()
    txt = el.text.strip()[:8]
    try:
        return date(int(txt[:4]), int(txt[4:6]), int(txt[6:8]))
    except ValueError:
        return timezone.localdate()


@login_required
def nfe_import(request):
    """Importa itens de uma NF-e (XML) para estoque + financeiro.

    O sinal do lançamento vem do **CFOP**, não do tipo de item. A versão
    anterior importava tudo como `DESPESA`/`INSUMO` sem olhar o CFOP, e uma
    nota de venda de soja a R$ 78.000 entrava como despesa — o sinal invertido,
    visível no DRE e no crédito.

    O que NÃO fazemos com um item: adivinhar. Um CFOP fora da tabela do
    sistema é **descartado e nomeado** na resposta, porque o sinal errado num
    lançamento é mais caro que o item em falta. O produtor ainda tem o XML.

    O original passava campos que não existem em EstoqueItem
    (`insumo`, `preco_unitario`, `origem`) e criava Insumo sem a FK
    obrigatória `propriedade` — todo POST estourava TypeError/IntegrityError.
    """
    if request.method != "POST" or not request.FILES.get("xml"):
        return JsonResponse(
            {"ok": False, "erro": "Envie XML via POST file 'xml'"}, status=400
        )
    xml_file = request.FILES["xml"]

    # `defusedxml`, não `xml.etree`: o XML vem de um ficheiro carregado pelo
    # utilizador, e o parser nativo aceita entidades externas (XXE, CWE-611)
    # e "billion laughs" (DoS). Severidade do scanner: ERROR, impacto MEDIUM
    # — mas o input é não confiável por definição, e a correcção é uma linha.
    try:
        root = defused_fromstring(xml_file.read())
    except ParseError:
        # XML partido é erro do **cliente**, não do servidor: o produtor
        # mandou um ficheiro que não é NF-e. Um 500 aqui diz ao cliente que a
        # aplicação avariou, e costuma aparecer como alarme em monitorização.
        return JsonResponse(
            {
                "ok": False,
                "erro": "XML inválido. Confirme que o ficheiro é o XML da NF-e "
                "e não o PDF ou o DANFE.",
            },
            status=400,
        )
    except (ValueError, OSError) as e:
        # Ficheiro ilegível, ou XML que o `defusedxml` recusa por DOCTYPE /
        # entidade externa — que é o XXE a ser bloqueado, não uma avaria.
        logger.warning("nfe_import: XML recusado (%s)", type(e).__name__)
        return JsonResponse(
            {
                "ok": False,
                "erro": "O ficheiro não pôde ser lido como XML de NF-e.",
            },
            status=400,
        )

    try:
        itens = root.findall(".//nfe:det", NS) or root.findall(".//det")
        criados = []
        recusados = []
        ignorados = []

        prop = Propriedade.objects.filter(user=request.user).first()
        if not prop:
            return JsonResponse(
                {"ok": False, "erro": "Nenhuma propriedade cadastrada"},
                status=400,
            )

        emissao = _data_emissao(root)

        for det in itens[:20]:
            prod = det.find("nfe:prod", NS) or det.find("prod")
            if prod is None:
                continue
            xProd = (
                prod.findtext("nfe:xProd", default="", namespaces=NS)
                or prod.findtext("xProd")
                or "Insumo NF-e"
            ).strip()
            cfop_txt = (
                prod.findtext("nfe:CFOP", default="", namespaces=NS)
                or prod.findtext("CFOP")
                or ""
            ).strip()
            qCom = (
                prod.findtext("nfe:qCom", default="0", namespaces=NS)
                or prod.findtext("qCom")
                or "0"
            )
            vUnCom = (
                prod.findtext("nfe:vUnCom", default="0", namespaces=NS)
                or prod.findtext("vUnCom")
                or "0"
            )
            qtd = _decimo(qCom)
            preco = _decimo(vUnCom)
            uCom = (
                prod.findtext("nfe:uCom", default="", namespaces=NS)
                or prod.findtext("uCom")
                or ""
            ).strip()

            # `None` aqui é **ilegível**, que é diferente de zero. `_decimo`
            # devolve `Decimal("0")` quando a nota diz 0 (medição) e `None`
            # quando não consegue ler (ausência). O `or Decimal("0")` que
            # aqui estava tratava os dois igual, e um item ilegível entrava
            # com `valor = preço × 0 = R$ 0,00` — uma linha de zero numa
            # ledger fiscal, que é pior que uma linha em falta: a em falta
            # avisa o produtor, e a de zero afirma que o item vale nada.
            if qtd is None or preco is None:
                recusados.append(
                    {
                        "produto": xProd,
                        "cfop": cfop_txt,
                        "motivo": (
                            "quantidade "
                            + ("ilegível" if qtd is None else "ok")
                            + f" ({qCom!r}), preço unitário "
                            + ("ilegível" if preco is None else "ok")
                            + f" ({vUnCom!r}) — o valor do item não é fiável, "
                            "por isso não foi lançado"
                        ),
                    }
                )
                continue

            # --- O sinal vem do CFOP ---
            cat, motivo = classificar_cfop(cfop_txt)

            if cat is None:
                recusados.append({"produto": xProd, "cfop": cfop_txt, "motivo": motivo})
                continue

            if cat.classe == "apuracao":
                # Apuração não é compra nem venda: não entra, mas o produtor
                # precisa de saber que foi vista e deixada de fora.
                ignorados.append(
                    {
                        "produto": xProd,
                        "cfop": cfop_txt,
                        "motivo": f"CFOP de apuração ({cat.descricao}) — não gera lançamento",
                    }
                )
                continue

            if cat.mexe_estoque:
                insumo, _ = Insumo.objects.get_or_create(
                    propriedade=prop,
                    nome__iexact=xProd,
                    defaults={
                        "nome": xProd,
                        "categoria": "OUTRO",
                        "unidade": uCom[:20] or "unidade",
                        "quantidade": 0,
                        "valor_unitario": preco,
                    },
                )
                EstoqueItem.objects.create(
                    propriedade=prop,
                    categoria="INSUMO",
                    nome=xProd,
                    quantidade=qtd,
                    # `uCom` da nota, não `insumo.unidade`: o `Insumo` já pode
                    # existir de outra nota com outra unidade, e o estoque
                    # deste item tem a unidade **deste** item.
                    unidade=uCom[:20] or insumo.unidade,
                    valor_unitario=preco,
                    local=f"NF-e {emissao:%d/%m/%Y}",
                )

            # A quantidade e a unidade **ficam**. Sem elas, a NF-e diz "20 KG
            # de café a R$ 38,90" e o sistema guardava só R$ 778,00 — a
            # quantidade morria na fronteira, e sem quantidade não há preço
            # por unidade nem rede de preços (§21.5).
            lanc = LancamentoFinanceiro.objects.create(
                propriedade=prop,
                tipo=cat.tipo_lancamento,
                categoria=cat.categoria,
                descricao=f"NF-e {xProd} (CFOP {cfop_txt})",
                valor=(preco * qtd).quantize(Decimal("0.01")),
                data=emissao,
                comprovante=f"CFOP {cfop_txt}",
                quantidade=qtd,
                unidade=uCom[:12],
                cfop=cfop_txt[:4],
            )

            # O grupo `<imposto>` também fica. Antes era deitado fora: uma
            # venda de R$ 13.750 com R$ 1.650 de ICMS entrava no ledger sem o
            # imposto, e o produtor comparava o preço com um custo incompleto
            # sem nunca saber que estava incompleto.
            tributos = _extrair_tributos(det)
            tributos["lancamento"] = lanc
            tributos["descricao"] = xProd[:255]
            tributos["ncm"] = (
                prod.findtext("nfe:NCM", default="", namespaces=NS)
                or prod.findtext("NCM")
                or ""
            ).strip()[:12]
            ItemTributario.objects.create(**tributos)

            criados.append(xProd)

        return JsonResponse(
            {
                "ok": True,
                "criados": criados,
                "total": len(criados),
                "recusados": recusados,
                "ignorados": ignorados,
            }
        )
    except Exception:
        logger.exception("nfe_import: falha ao importar XML")
        # sem str(e) na resposta: vaza caminho/integrity detail pro cliente
        return JsonResponse(
            {"ok": False, "erro": "Falha ao processar o XML da NF-e"}, status=500
        )


@login_required
def lote_qr(request, lote_id):
    """Gera hash e QR data para lote (safra/talhão) — só do próprio usuário."""
    try:
        safra = Safra.objects.get(id=lote_id, propriedade__user=request.user)
    except Safra.DoesNotExist:
        return JsonResponse({"ok": False, "erro": "Lote não encontrado"}, status=404)

    payload = {
        "lote": safra.id,
        "cultura": str(safra.cultura),
        "talhao": str(safra.talhao),
        "hash": hashlib.sha256(
            f"{safra.id}{safra.cultura}{safra.talhao}".encode()
        ).hexdigest()[:12],
    }
    qr_data = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()
    return JsonResponse(
        {
            "ok": True,
            "qr": qr_data,
            "payload": payload,
            "url": f"/rastreabilidade/{qr_data}",
        }
    )
