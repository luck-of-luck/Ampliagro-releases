"""NF-e: ler, deduplicar e gravar. O motor que a view e o canal automatico partilham.

POR QUE ESTE FICHEIRO EXISTE
=============================
MEDIDO 2026-10-05 (agente 7). `app/views/nfe_auto.py:38 nfe_import` funciona —
XML endurecido, `defusedxml`, teto de 5 MB, `Insumo`/`EstoqueItem`/
`LancamentoFinanceiro` gravados — mas e' uma **view**, e uma view nao se
invoca de outra parte. O que a concorrencia promete e' o canal automatico:

  Aegro:  "importacao de compras directamente da SEFAZ... automatica, sem
           erros de digitacao"
  Lucro Rural: "busca de notas automaticamente na SEFAZ"

E e' o eixo **mais repetido de toda a pesquisa de `docs/sistema/7.md` §10.7**,
e o Ampliagro tinha **zero** de canal automatico (`grep sefaz` = 0 em `app/`).
Falta o canal. Este ficheiro e' o que torna o canal possivel sem duplicar o
parser: o que sabe ler um XML passa a ser uma funcao que qualquer entrada
chama.

OS TRES DEFECTOS QUE ESTE FICHEIRO CORRIGE
==========================================
Todos medidos no codigo anterior, todos do mesmo tipo — **o sistema affirmava
uma coisa que nao tinha feito**.

1. REENVIO DUPLICAVA TUDO. Nao havia nada que identificasse a nota. O mesmo
   XML carregado duas vezes criava dois `EstoqueItem` e dois
   `LancamentoFinanceiro` para a mesma compra. `EstoqueItem.local` era
   `f"NF-e {emissao:%d/%m/%Y}"` — a **data**, que nao distingue duas notas do
   mesmo dia, muito menos duas vezes a mesma nota.

   A identidade de uma NF-e e' a **chave de acesso**: 44 digitos, 23 campos,
   emitida pela SEFAZ e unica por documento. E' ela que vai para
   `NotaFiscalImportada`, e a segunda importacao da mesma chave devolve
   "ja importada" sem gravar uma linha.

2. UMA NOTA, VARIOS LANCAMENTOS. O codigo antigo estava **dentro** do
   `for det in itens[:20]`, e criava um `LancamentoFinanceiro` por item. Uma
   NF-e de 12 itens gerava 12 lancamentos de "NF-e <produto>", cada um com
   `preco * qtd`. O produtor via doze despesas onde houve uma compra. E o
   `:20` cortava a meio: os itens 21 em diante sumiam do estoque **e nao**
   falhavam — o silencio de um `[:20]` e' pior que um erro.

3. DINHEIRO EM `float`. `valor=preco * qtd`, com `float(str(qCom).replace(",", "."))`.
   Este repositorio ja corrigiu a virgula decimal do LCDPR; o caminho de
   entrada da NF-e mantinha `float`. `Decimal` a partir de texto, com o mesmo
   cuidado: `"1.234,56"` e' 1234.56 e nao 1.23456.

O QUE ESTE CODIGO **NAO** FAZ, E DE PROPOSITO
==============================================
- Nao chama a SEFAZ. `ClienteDFe` fica com o `TODO` explicito e a
  documentacao do que exige (certificado A1, CNPJ, endpoint por UF). Um
  stub que devolvesse notas inventadas seria exactamente o defeito que o
  `erp_externo.py` foi corrigido por ter.
- Nao adivinha fornecedor, centro de custo nem talhao. A nota entra com o
  que traz: descricao, valor, data. O que nao veio, nao e' inventado.
- Nao emite NF-e. Isso e' P0-1 e precisa de certificado A1 e assinatura XML;
  ver `docs/sistema/7.md` §11 P0-1.
"""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation

from defusedxml import ElementTree as DET
from defusedxml.common import DefusedXmlException
from defusedxml.ElementTree import ParseError
from django.db import transaction
from django.utils import timezone

#: A chave de acesso tem 44 digitos. Validar o comprimento e' o que separa
#: "chave de acesso" de "um numero qualquer que o produtor escreveu no campo
#: do numero do documento" — e um numero errado aqui faz a deduplicacao
#: silenciosamente falhar, que e' o pior modo de falhar que existe.
CHAVE_NF_LEN = 44

#: A NF-e tem alguns KB. 5 MB e' folgado, e o mesmo teto que a view usava.
XML_MAX_BYTES = 5 * 1024 * 1024

NS = {"nfe": "http://www.portalfiscal.inf.br/nfe"}


class NFeInvalida(ValueError):
    """O XML nao e' uma NF-e que este sistema saiba ler.

    Existe para o chamador poder responder "o ficheiro esta mal" em vez de
    deixar a excecao stranger subir e virar 500.
    """


@dataclass
class ItemNota:
    descricao: str
    quantidade: Decimal
    valor_unitario: Decimal

    @property
    def total(self) -> Decimal:
        return (self.quantidade * self.valor_unitario).quantize(Decimal("0.01"))


@dataclass
class NotaLida:
    chave: str
    emissao: date
    fornecedor_doc: str = ""
    fornecedor_nome: str = ""
    numero: str = ""
    itens: list[ItemNota] = field(default_factory=list)

    @property
    def total(self) -> Decimal:
        return sum((i.total for i in self.itens), Decimal("0.00"))


def decimal_pt(valor, padrao=Decimal("0")) -> Decimal:
    """ "1.234,56" -> Decimal("1234.56"). Nunca `float` pelo caminho.

    O `float` deste caminho ja custou dinheiro noutro sitio (o LCDPR): uma
    virgula mal lida nao da erro de sintaxe, da um numero plausivel e
    errado. Aqui a regra e' unica e testada: ponto e' separador de milhar
    quando ha virgula; sem virgula, o ponto e' decimal.
    """
    texto = str(valor or "").strip()
    if not texto:
        return padrao
    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    try:
        return Decimal(texto)
    except (InvalidOperation, ValueError):
        return padrao


def _texto(el, caminho, default=""):
    if el is None:
        return default
    achado = el.find(caminho, NS)
    if achado is None:
        achado = el.find(caminho.split(":")[-1])
    if achado is None or achado.text is None:
        return default
    return achado.text.strip()


def ler_nota(xml_bytes: bytes) -> NotaLida:
    """Le um XML de NF-e. Levanta `NFeInvalida` se nao conseguir."""
    if xml_bytes is None:
        raise NFeInvalida("Conteudo vazio.")
    if len(xml_bytes) > XML_MAX_BYTES:
        raise NFeInvalida(
            f"XML de {len(xml_bytes)} bytes excede o limite de {XML_MAX_BYTES}."
        )

    try:
        # `defusedxml`, nunca `xml.etree.ElementTree`: a nativa expande
        # entidades internas e um "billion laughs" cabe em 2 KB.
        root = DET.fromstring(xml_bytes)
    except ParseError as e:
        raise NFeInvalida(f"XML malformado: {e}") from e
    except DefusedXmlException as e:
        raise NFeInvalida(
            "XML recusado: contem entidades, DTD ou referencias externas."
        ) from e

    chave = _texto(root, ".//nfe:infNFe/nfe:ide/nfe:chNFe")
    if not chave:
        chave = _texto(root, ".//chNFe")
    digitos = "".join(c for c in chave if c.isdigit())
    if len(digitos) != CHAVE_NF_LEN:
        raise NFeInvalida(
            "O XML nao tem uma chave de acesso de NF-e com 44 digitos. "
            f"Veio com {len(digitos)}. Sem a chave nao ha como saber se esta "
            "nota ja foi importada — por isso o import e' recusado em vez de "
            "duplicar o estoque."
        )

    d_emi = _texto(root, ".//nfe:infNFe/nfe:ide/nfe:dEmi")[:8]
    try:
        emissao = date(int(d_emi[:4]), int(d_emi[4:6]), int(d_emi[6:8]))
    except (ValueError, IndexError):
        emissao = timezone.localdate()

    emit = root.find(".//nfe:infNFe/nfe:emit", NS) or root.find(".//emit")
    fornecedor_nome = _texto(emit, "nfe:xNome") if emit is not None else ""
    fornecedor_doc = (
        _texto(emit, "nfe:CNPJ") or _texto(emit, "nfe:CPF") if emit is not None else ""
    )
    numero = _texto(root, ".//nfe:infNFe/nfe:ide/nfe:nNF")

    itens = []
    for det in root.findall(".//nfe:det", NS) or root.findall(".//det"):
        prod = det.find("nfe:prod", NS) or det.find("prod")
        if prod is None:
            continue
        nome = _texto(prod, "nfe:xProd") or "(item sem descricao)"
        qtd = decimal_pt(_texto(prod, "nfe:qCom"))
        preco = decimal_pt(_texto(prod, "nfe:vUnCom"))
        itens.append(ItemNota(descricao=nome, quantidade=qtd, valor_unitario=preco))

    if not itens:
        raise NFeInvalida("A NF-e nao tem itens com produto.")

    return NotaLida(
        chave=digitos,
        emissao=emissao,
        fornecedor_doc="".join(c for c in fornecedor_doc if c.isdigit()),
        fornecedor_nome=fornecedor_nome,
        numero=numero,
        itens=itens,
    )


@transaction.atomic
def importar_nota(propriedade, nota: NotaLida) -> dict:
    """Grava uma nota lida. Idempotente pela chave de acesso.

    **Uma** nota = **um** `LancamentoFinanceiro` pelo total, mais um
    `EstoqueItem` por item. A segunda importacao da mesma chave nao grava
    nada e diz-o.
    """
    from app.models import (
        EstoqueItem,
        Insumo,
        LancamentoFinanceiro,
        NotaFiscalImportada,
    )

    ja_importada = NotaFiscalImportada.objects.filter(
        propriedade=propriedade, chave=nota.chave
    ).first()
    if ja_importada:
        return {
            "ok": True,
            "duplicado": True,
            "chave": nota.chave,
            "importada_em": ja_importada.importada_em.isoformat(),
            "mensagem": (
                f"Esta NF-e ja foi importada em "
                f"{ja_importada.importada_em:%d/%m/%Y}. Nada foi gravado."
            ),
        }

    criados = []
    for item in nota.itens:
        insumo, _ = Insumo.objects.get_or_create(
            propriedade=propriedade,
            nome__iexact=item.descricao,
            defaults={
                "nome": item.descricao,
                "categoria": "OUTRO",
                "unidade": "unidade",
                "quantidade": Decimal("0"),
                "valor_unitario": item.valor_unitario,
            },
        )
        EstoqueItem.objects.create(
            propriedade=propriedade,
            categoria="INSUMO",
            nome=item.descricao,
            quantidade=item.quantidade,
            unidade=insumo.unidade,
            valor_unitario=item.valor_unitario,
            # A chave entra no `local`: e' o que distingue esta nota das
            # demais. Antes era a data, que nao distingue nada.
            local=f"NF-e {nota.numero or nota.chave[:8]}",
        )
        criados.append(item.descricao)

    lancamento = LancamentoFinanceiro.objects.create(
        propriedade=propriedade,
        tipo="DESPESA",
        categoria="INSUMO",
        descricao=f"NF-e {nota.numero or nota.chave[:8]}"
        + (f" - {nota.fornecedor_nome}" if nota.fornecedor_nome else ""),
        valor=nota.total,
        data=nota.emissao,
        participante=nota.fornecedor_nome,
        participante_doc=nota.fornecedor_doc,
        tipo_documento_lcdpr="1",
        tipo_lancamento_lcdpr="",
        numero_documento=nota.numero or nota.chave[:20],
        comprovante=f"chave {nota.chave}",
    )

    NotaFiscalImportada.objects.create(
        propriedade=propriedade,
        chave=nota.chave,
        numero=nota.numero,
        fornecedor_doc=nota.fornecedor_doc,
        fornecedor_nome=nota.fornecedor_nome,
        emissao=nota.emissao,
        total=nota.total,
        itens=len(nota.itens),
    )

    return {
        "ok": True,
        "duplicado": False,
        "chave": nota.chave,
        "criados": criados,
        "total": str(nota.total),
        "lancamentos": 1,
        "lancamento_id": lancamento.pk,
        "proxima_acao": "Confira a classificação fiscal e registre o pagamento quando realizado.",
        "itens": len(nota.itens),
    }


def importar_xml(propriedade, xml_bytes: bytes) -> dict:
    """Atalho: ler + gravar, com os erros ja traduzidos em resultado."""
    try:
        nota = ler_nota(xml_bytes)
    except NFeInvalida as e:
        return {"ok": False, "erro": str(e)}
    return importar_nota(propriedade, nota)


class ClienteDFe:
    """Canal automatico com a SEFAZ. NAO IMPLEMENTADO, e diz-se.

    MEDIDO 2026-10-05. Existe para o sitio onde o canal vai entrar estar
    escrito, e para ninguem inventingar um stub que "ja funciona".

    O que a SEFAZ exige, e que o Ampliagro ainda nao tem:
      1. Certificado digital **A1** (arquivo `.pfx` + senha) para assinar o
         pedido. `cryptography` no `requirements.txt` serve para Fernet, nao
         para PKCS#12.
      2. CNPJ e inscricao estadual do produtor.
      3. Endpoint por UF — cada estado tem o seu, e o endereco muda.
      4. Uma library de assinatura XML (`signxml`/`xmlsec`), que nao existe no
         `requirements.txt`.

    Um stub aqui devolveria numeros plausiveis sem consultar nada — o mesmo
    defeito de `erp_externo.py:webhook_jbs_abate`, que devolvia
    `cabecas=10721000` copiado de um artigo de jornal. Por isso esta classe
    **levanta**. Uma excepcao honesta agora vale mais do que um numero falso
    em Abril.
    """

    #: Endpoint por UF. Vazio de proposito: um URL inventado e' pior do que
    #: nenhum, porque falha em producao e ninguem sabe porquê.
    ENDPOINTS_POR_UF = {}

    def __init__(self, uf, cnpj, certificado_pfx=None, senha=None):
        self.uf = uf.upper()
        self.cnpj = "".join(c for c in str(cnpj or "") if c.isdigit())
        self.certificado_pfx = certificado_pfx
        self.senha = senha

    def buscar_documentos(self, data_inicial, data_final):
        """Levanta `NotImplementedError` com o que falta. Sempre."""
        falta = []
        if self.uf not in self.ENDPOINTS_POR_UF:
            falta.append(f"endpoint da SEFAZ para {self.uf} (nao configurado)")
        if not self.cnpj:
            falta.append("CNPJ do produtor")
        if not self.certificado_pfx:
            falta.append("certificado digital A1")

        raise NotImplementedError(
            "Consulta automatica a SEFAZ nao implementada. Falta: "
            + ("; ".join(falta) or "configuracao")
            + ". Enquanto isso, use a importacao manual de XML "
            "(POST /api/nfe/import/), que usa o mesmo motor deste modulo."
        )
