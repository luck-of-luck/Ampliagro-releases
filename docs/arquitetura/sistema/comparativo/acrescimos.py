"""Acrescenta ao registo as celulas que a descoberta em massa provou.

Escolhi **as que mudam uma conclusao**, nao as 44. Uma celula a mais que
prove o obviousio nao acrescenta leitura; uma que preenche uma coluna que eu
dizia estar vazia, sim.

O QUE MUDA COM ESTAS 22
=======================
  F05 Reforma Tributaria  -> estava em "ninguem tem evidencia". Senior e
                            TOTVS Protheus tem, com a frase no texto.
  L05 Contratos de safra  -> idem. Bushel Farm tem "grain contract" x3.
  G02 Auditoria de IA    -> eu listava como **exclusivo do Ampliagro**.
                            A Datacor tem "audit trail" — o termo, ao menos.
  G01 Proveniencia       -> idem, mesma fonte.
  F10 Contas a pagar     -> estava em "ninguem tem". Tres ERPs tem.
  F16 Credito rural      -> Protheus e Aptean listam "financial services".
                            **Atencao: isto nao e' credito rural.** E' servico
                            financeiro a agroindustria. Marquei `P`, nunca `F`.

O QUE NAO ENTROU, E PORQUE
==========================
122 celulas passaram o filtro. 22 entraram. As outras 100 sao majoritariamente
`field log`, `cash flow`, `map`, `ERP` numa landing page — verdadeiros, mas nao
distintivos: provam que o produto existe, nao que seja melhor.

Uma celula `F` tem de merecer o nome. Encher a tabela de `F` triviais
transformaria a prova em decoracao — que e' o que o `MERGED.md` §7.4 chama de
"correccao documentada como feita, e nao feita".
"""

from __future__ import annotations

#: (produto, coluna, url, fragmento, porque, estado, nota)
NOVAS: list[tuple[str, str, str, str, str, str, str]] = [
    # ---- F05: a coluna estava vazia na analise
    (
        "Senior / GATec",
        "F05",
        "https://site.senior.com.br/agronegocio/funcionalidades-erp-agronegocio/",
        "Reforma Tribut",
        "a transicao IBS/CBS nomeada na lista de funcionalidades",
        "F",
        "",
    ),
    (
        "TOTVS Protheus",
        "F05",
        "https://www.totvs.com/",
        "Reforma Tribut",
        "5 ocorrencias — a transicao e' um argumento de venda",
        "F",
        "",
    ),
    # ---- F10: contas a pagar, que eu dava como ausentes de todos
    (
        "Aegro",
        "F10",
        "https://aegro.com.br/",
        "contas a pagar",
        "'contas e pagamentos' na landing page",
        "F",
        "",
    ),
    (
        "Sage X3",
        "F10",
        "https://www.sage.com/",
        "contas a pagar",
        "backoffice ERP",
        "F",
        "",
    ),
    (
        "SYSPRO",
        "F10",
        "https://www.syspro.com/",
        "accounts payable",
        "backoffice ERP",
        "F",
        "",
    ),
    # ---- L05: contratos de grao. Bushel e uma company de comercio de graos.
    (
        "Bushel Farm",
        "L05",
        "https://bushelfarm.com/",
        "grain contract",
        "3 ocorrencias — contratos de grao sao o neg��cio doBushel",
        "F",
        "",
    ),
    # ---- G01/G02: audit trail. CORRIGE uma conclusao minha.
    (
        "Datacor",
        "G02",
        "https://www.datacor.com/",
        "audit trail",
        "audit trail nomeado — **a coluna deixa de ser exclusiva do Ampliagro**",
        "F",
        "CORRICAO: o 9.md e a ANALISE listavam G02 como advantage exclusiva. "
        "A palavra existe na Datacor. O que continua a ser exclusivo e' G01 "
        "(proveniencia como TIPO em codigo, nao como log).",
    ),
    (
        "Datacor",
        "G01",
        "https://www.datacor.com/",
        "audit trail",
        "audit trail cobre linhagem de dado, que e' parte da proveniencia",
        "P",
        "PARCIAL: 'audit trail' prova registo de alteracoes. Nao prova tipagem "
        "de origem (medido / declarado / inventado).",
    ),
    # ---- G04: multi-fazenda
    (
        "AgriChain",
        "G04",
        "https://agrichain.com/",
        "multiple farm",
        "multi-sitio declarado",
        "F",
        "",
    ),
    (
        "Traction Ag",
        "G04",
        "https://tractionag.com/",
        "multiple farm",
        "multi-sitio declarado",
        "F",
        "",
    ),
    # ---- M02/M03: integracoes com maquina. Bushel e TractionAg surprising.
    (
        "Bushel Farm",
        "M02",
        "https://bushelfarm.com/",
        "John Deere",
        "integracao com Deere — a Bushel e' de origem americana",
        "F",
        "",
    ),
    (
        "Bushel Farm",
        "M03",
        "https://bushelfarm.com/",
        "Climate FieldView",
        "integracao com FieldView",
        "F",
        "",
    ),
    (
        "Traction Ag",
        "M02",
        "https://tractionag.com/",
        "John Deere",
        "integracao com Deere",
        "F",
        "",
    ),
    (
        "Traction Ag",
        "M03",
        "https://tractionag.com/",
        "Climate FieldView",
        "integracao com FieldView",
        "F",
        "",
    ),
    # ---- F18: folha de pagamento. Territorio TOTVS e Senior.
    (
        "TOTVS PIMS Agro",
        "F18",
        "https://produtos.totvs.com/",
        "folha de pagamento",
        "modulo nomeado",
        "F",
        "",
    ),
    (
        "Senior / GATec",
        "F18b",
        "https://site.senior.com.br/agronegocio/funcionalidades-erp-agronegocio/",
        "folha de pagamento",
        "modulo Mao de Obra, mesmo com outro nome",
        "F",
        "",
    ),
    # ---- M07: edge AI. compete directamente com a nossa coluna de IA local.
    (
        "Carbonova / CarbonOS",
        "M07",
        "https://carbonova.ai/",
        "edge AI",
        "3 ocorrencias — IA na borda, no mesmo sitio que o Ampliagro",
        "F",
        "e' o unico concorrente provado com IA na borda. E' carbono, nao agro.",
    ),
    # ---- F16: CUIDADO. 'financial services' NAO e' credito rural.
    (
        "TOTVS Protheus",
        "F16",
        "https://www.totvs.com/",
        "financial services",
        "**NAO e' credito rural.** E' servico financeiro a agroindustria",
        "P",
        "PARCIAL por caution: a coluna pede credito rural / seguro agricola. "
        "Servico financeiro geral nao prova isso.",
    ),
    (
        "Aptean Food & Beverage",
        "F16",
        "https://aptean.com/",
        "financial services",
        "**NAO e' credito rural.** E' financiamento de processo",
        "P",
        "como acima",
    ),
    # ---- O02: offline, com frase
    (
        "Agworld",
        "O02",
        "https://agworld.com/",
        "offline",
        "app funciona sem rede",
        "F",
        "",
    ),
    (
        "Farmable",
        "O02",
        "https://farmable.tech/",
        "without internet",
        "'works without internet' — frase literal",
        "F",
        "",
    ),
    (
        "Agworld",
        "O09",
        "https://agworld.com/",
        "pest",
        "monitoramento de pragas",
        "F",
        "",
    ),
    (
        "Farmable",
        "O09",
        "https://farmable.tech/",
        "IPM",
        "3 ocorrencias de IPM",
        "F",
        "",
    ),
]
