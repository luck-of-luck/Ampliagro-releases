"""
ERP externo — resolve 2 dos 12 "com restrições" (JBS J&F + Eurochem)
Stub para integração SAP / Protheus / Senior via webhook + Fila

Vídeos:
- J&F JBS companhia aberta → precisa espelhar abate, estoque, financeiro no SAP
- Eurochem 450 suspensos falta enxofre → precisa alerta insumo + cotação alternativa
"""

from decimal import Decimal

ERP_TIPOS = [
    ("SAP", "SAP S/4HANA"),
    ("PROTHEUS", "Protheus TOTVS"),
    ("SENIOR", "Senior"),
    ("ORACLE", "Oracle Agro"),
]

MAP_ERP_VIDEO = {
    "J&F JBS": {
        "erp": "SAP",
        "fluxo": "abate 10.721M cabeças/trim → estoque → financeiro → B3",
        "webhook": "/api/erp/jbs/abate/",
    },
    "Eurochem": {
        "erp": "PROTHEUS",
        "fluxo": "falta enxofre Serra do Salitre → 450 suspensos → cotação alternativa Yara",
        "webhook": "/api/erp/eurochem/insumo/",
    },
    "John Deere IA": {
        "erp": "ORACLE",
        "fluxo": "dados máquina → IA → recomendação",
        "webhook": "/api/erp/johndeere/telemetria/",
    },
}


def payload_erp(tipo, evento, dados):
    """Gera payload padronizado para ERP externo."""
    return {
        "erp": tipo,
        "evento": evento,
        "dados": dados,
        "ampliagro_version": "5.0",
        "hash": f"{tipo}:{evento}:{dados.get('id', '')}",
    }


def webhook_jbs_abate(cabecas=None, trimestre=None, recorde=None):
    """STUB. NÃO TEM ROTA — confirmado na auditoria de 2026-09-29.

    Antes tinha `cabecas=10721000` e `recorde=True` por omissão, com a
    fonte escrita como "Globo Rural 2026-09 abates recorde" e o estado
    "Feito (stub) — pronto para conectar SAP real".

    Três coisas erradas ao mesmo tempo, mesmo sendo stub:

    1. O default era um número copiado de um artigo de jornal. Quem
       chamasse isto sem argumentos recebia 10 721 000 cabeças como se
       fossem a base de dados da empresa.

    2. `recorde=True` é uma afirmação sobre o mundo, não um default. Um
       default não pode afirmar um facto.

    3. `"fonte": "Globo Rural ..."` com `"status": "Feito"` faz o payload
       parecer um registo feito. A referência é citável, mas não é a fonte
       de um dado que este sistema mediu.

    Um stub que devolve numeros plausiveis e' mais perigoso do que um stub
    que devolve `None`: o primeiro pode ser ligado sem ninguem reparar que esta
    a inventar, e ninguem repara porque os numeros sao realistas.

    NOTA: `webhook_eurochem_insumo` (`:96`) ainda mantem defaults fixos —
    `suspensos=450`, `local="Serra do Salitre"` — e `"alternativa"` citando
    "Globo Rural 2026-09" como se fosse um dado. Nao corrigi aqui porque a
    correccao e' a MESMA do SAP (defaults `None`, `fonte: None`, sem numero de
    jornal) e quero a mudanca medida e isolada, num commit so, com o health
    check a provar. Fica registado na §11 P1-5 do `docs/sistema/7.md`.

    Quando este for ligado a um SAP de verdade, a contagem de cabecas vem
    do sistema que gere o rebanho, e o trimestre vem do calendario. Se o
    valor nao vier, nao ha valor.
    """
    return payload_erp(
        "SAP",
        "abate_bovino",
        {
            "cabecas": cabecas,
            "trimestre": trimestre,
            "recorde": recorde,
            "status": (
                "stub — integração SAP não implementada. "
                "Este payload não tem origem de dados: não consultou "
                "rebanho, não consultou calendário, e não consultou "
                "nenhuma fonte primária."
            ),
            "fonte": None,
            "integracao": "Ampliagro → SAP via webhook (não implementado)",
        },
    )


def webhook_eurochem_insumo(falta=None, suspensos=None, local=None):
    """Insumo em falta: defaults a `None`, e a alternativa nao se inventa.

    MEDIDO 2026-10-04. Antes: `falta="enxofre"`, `suspensos=450`,
    `local="Serra do Salitre"`, `"alternativa": "Yara biológicos (Globo Rural
    2026-09)"` e `"status": "✅ Feito (stub)"`.

    Tres coisas erradas ao mesmo tempo, e as tres do mesmo tipo:

      1. Os DEFAULTS eram o payload. Um chamar sem argumentos gravava
         uma propriedade alheia como se o produtor a tivesse dito. E' o
         mesmo modo de falha do `talhao_id` do Caderno — uma resposta certa
         no sitio errado — e aqui o sitio errado e' a assinatura da funcao.
      2. A alternativa vinha com nome e data de um mercado concreto. O
         `health_check` abaixo diz "3 stubs", e `docs/sistema/7.md` §11 P1-5
         ja o registava. Nao se recomenda um fornecedor sem consultar o
         cadastro de insumos do proprio produtor.
      3. `"✅ Feito"` e' a mentira mais cara: o status de um payload que nao
         consultou nada. `payload_erp` ja tem `fonte: None` para isto; o
         stub escrevia "Feito" ao lado.

    A correccao e' a MESMA do SAP acima, e o docstring deste modulo ja o
    pedia ("a correccao e' a MESMA do SAP, num commit so"). Feito.
    """
    return payload_erp(
        "PROTHEUS",
        "falta_insumo",
        {
            "insumo": falta,
            "suspensos": suspensos,
            "local": local,
            "alternativa": None,
            "acao": "Ampliagro dispara alerta + cotacao alternativa",
            "status": (
                "stub — integracao PROTHEUS nao implementada. "
                "Este payload nao tem origem de dados: nao consultou "
                "estoque, nao consultou cadastro de insumos, e nao "
                "consultou nenhuma fonte primaria."
            ),
            "fonte": None,
            "integracao": "Ampliagro -> PROTHEUS via webhook (nao implementado)",
        },
    )


def health_check():
    """Estado real deste modulo, sem elogio.

    MEDIDO 2026-10-04. Devolvia `"erp_externo": "✅ operacional (3 webhooks
    stub)"`. Tres coisas erradas numa linha:

    1. **"operacional"** e' um veredicto sobre um mundo exterior. Nao ha SAP
       ligado: `webhook_jbs_abate` e' um stub com defaults `None` (`:77`), e o
       proprio docstring diz "NAO TEM ROTA".
    2. **"3 webhooks"** e' uma contagem de funcoes que existem, e nao de
       webhooks que responderam. Uma funcao que ninguem chama conta igual a
       uma que responde.
    3. O **✅** e' o green check que o §1 do `docs/sistema/7.md`_probe diz para
       nunca escrever sobre stub. Um health check que da verde em cima de
       stub e' a pior das duas metades: e' o componente que existe
       precisamente para-nesse CASO nao enganar ninguem.

    Um health check honesto aqui e' quase todo "ligado: nao". Se algum dia um
    SAP responder, muda-se a linha — e e' a prova de que mudou.
    """
    return {
        "erp_externo": "⚠️ NÃO LIGADO — 0 integrações com rota; 3 stubs",
        "ligado": False,
        "integracoes_com_rota": 0,
        "stubs": [
            "webhook_jbs_abate (SAP) — sem rota, defaults None",
            "webhook_eurochem_insumo (Protheus) — sem rota, defaults fixos",
            "webhook_safra_* — ver o resto do modulo",
        ],
        "nota": (
            "Nenhum destes le ou escreve num ERP externo. A contagem de "
            "stubs acima e' de funcoes que EXISTEM, nao de integracoes que "
            "responderam. Nao ha SAP, Protheus ou JBS ligado ao Ampliagro."
        ),
        "videos_cobertos": list(MAP_ERP_VIDEO.keys()),
    }
