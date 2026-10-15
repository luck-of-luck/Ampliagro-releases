"""REGISTO DE EVIDENCIA — cada celula `S` com a citacao que a prova, e o seu estado.

ESTE FICHEIRO SUBSTITUI OS SNIPPETS
====================================
A primeira versao marcava `S` a partir de **snippets de pesquisa**. Um snippet
e' um resumo do motor de busca, nao a fonte — e o verificador
(`verificar_evidencia.py`) provou que isso erra:

    upCampo F16   "nao faz contabilidade"   -> a pagina diz "nao faz **e**"
                                                contabilidade". Rejeitada.
    Carbonova G05 "MRV"                      -> a pagina nunca escreve "MRV".
                                                Escreve "Inventario de Emissoes",
                                                "Escopos 1, 2 e 3". Rejeitada.
    CO2Token  G05 "ERC-20"                   -> a pagina devolve 9 caracteres:
                                                SPA. Rejeitada.
    Lucro Rural  "NCM", "presumido", "DRE"  -> nao estao na homepage. Estao em
                                                /produtor. Rejeitadas e corrigidas.
    Fluere      "fluere.ag"                 -> 404 ao fetch. Ver §O CASO FLUERE.

AS TRES MARCAS
==============
  F  PROVADO por fetch — a citacao foi buscada e esta na pagina neste momento
  D  DOCUMENTADO — a citacao existe, mas **nao da para provar por fetch** (a
     pagina e' JavaScript, ou bloqueia, ou o texto vive noutro sitio). A
     evidencia e' real; a maquina nao a alcanca. A razao esta escrita.
  ?  SEM EVIDENCIA — nao encontrei fonte. **Nao e' zero.**

`D` nao e' um `F` fraco. Um comunicado de bolsa e' prova **mais forte** do que
a pagina do fornecedor: e' a companhia a confirmar, nao o fornecedor a
prometer. Ver o caso Fluere.
"""

from __future__ import annotations

#: chave (produto, coluna) -> (url, fragmento, porque_prova, estado, nota)
EVIDENCIA: dict[tuple[str, str], tuple[str, str, str, str, str]] = {
    # =============================================== AEGRO — 16 celulas PROVADAS
    ("Aegro", "F02"): (
        "https://aegro.com.br/",
        "NF-e e MDF-e de graça",
        "a frase liga NF-e, MDF-e, gratuidade e SEFAZ numa so",
        "F",
        "",
    ),
    ("Aegro", "F03"): (
        "https://aegro.com.br/",
        "MDF-e de graça",
        "MDF-e com preco zero, sem limite",
        "F",
        "",
    ),
    ("Aegro", "F04"): (
        "https://aegro.com.br/",
        "SEFAZ",
        "conexao directa a SEFAZ implica certificado A1",
        "F",
        "inferencia: a pagina nao vende A1, mas nao ha emissao sem ele",
    ),
    ("Aegro", "F11"): (
        "https://aegro.com.br/",
        "fluxo de caixa",
        "'Veja o fluxo de caixa futuro e controle o dinheiro' — 3 ocorrencias",
        "F",
        "CORRIGIDO: o verificador rejeitou na /solucoes/gestao-rural/, onde a "
        "frase dao 0 ocorrencias. Esta na homepage.",
    ),
    # NOTA: hubo aqui uma entrada `("Aegro", "F16")` com o fragmento "pagar".
    # "'contas e pagar' NAO prova credito rural" — e' a coluna errada com a
    # citacao certa, que e' a forma mais silenciosa de mentir numa tabela.
    # Removida. `credito rural` e `seguro` dao 0 ocorrencias na Aegro.
    ("Aegro", "F13"): (
        "https://aegro.com.br/produtos/plano-aegro-lucratividade/",
        "custo de produção",
        "custo por talhao e produtividade, escritos",
        "F",
        "",
    ),
    ("Aegro", "F14"): (
        "https://aegro.com.br/solucoes/gestao-rural/",
        "planejado vs. realizado",
        "a comparacao orcado/realizado com os dois termos",
        "F",
        "",
    ),
    ("Aegro", "F15"): (
        "https://aegro.com.br/produtos/plano-aegro-premium/",
        "Compare Safras",
        "comparacao com o mercado — o dado que nao se compra",
        "F",
        "plano Premium",
    ),
    ("Aegro", "F12"): (
        "https://aegro.com.br/produtos/plano-aegro-lucratividade/",
        "OFX",
        "conciliacao por OFX, escrita",
        "F",
        "plano Avancado",
    ),
    ("Aegro", "O01"): (
        "https://aegro.com.br/solucoes/gestao-rural/",
        "talhão",
        "o caderno de campo e' por talhao",
        "F",
        "",
    ),
    ("Aegro", "O02"): (
        "https://aegro.com.br/",
        "sem internet",
        "o app declara funcionar sem rede",
        "F",
        "",
    ),
    ("Aegro", "O03"): (
        "https://aegro.com.br/produtos/plano-aegro-lucratividade/",
        "fotos georreferenciadas",
        "foto com coordenada, escrita no plural do texto",
        "F",
        "",
    ),
    ("Aegro", "O05"): (
        "https://aegro.com.br/solucoes/gestao-rural/",
        "orçamento",
        "planeamento de safra por orcamento",
        "F",
        "",
    ),
    ("Aegro", "O06"): (
        "https://aegro.com.br/",
        "talhão",
        "a unidade de custo e' o talhao",
        "F",
        "",
    ),
    ("Aegro", "O07"): (
        "https://aegro.com.br/solucoes/gestao-rural/",
        "NDVI",
        "indice de vegetacao por satelite",
        "F",
        "add-on 'Aegro Imagens'",
    ),
    ("Aegro", "O09"): (
        "https://aegro.com.br/produtos/plano-aegro-premium/",
        "MIP",
        "MIP nomeado no plano Premium",
        "F",
        "modulo adicional",
    ),
    ("Aegro", "L01"): (
        "https://aegro.com.br/solucoes/gestao-rural/",
        "baixa o insumo",
        "baixa automatica de estoque no acto da aplicacao",
        "F",
        "",
    ),
    ("Aegro", "L03"): (
        "https://aegro.com.br/",
        "Insumos",
        "controlo de insumos; o modulo de compras e' do plano Avancado",
        "F",
        "parcial: a pagina principal cita insumos, nao o modulo",
    ),
    ("Aegro", "P03"): (
        "https://aegro.com.br/",
        "arroba",
        "lucro por arroba de cada ciclo — a unidade economica real",
        "F",
        "",
    ),
    ("Aegro", "M01"): (
        "https://aegro.com.br/produtos/plano-aegro-premium/",
        "telemetria",
        "'Aegro Maquinas (telemetria)'",
        "F",
        "modulo opcional",
    ),
    ("Aegro", "M02"): (
        "https://aegro.com.br/solucoes/gestao-rural/",
        "John Deere",
        "integracao com Deere nomeada",
        "F",
        "",
    ),
    ("Aegro", "M03"): (
        "https://aegro.com.br/solucoes/gestao-rural/",
        "Stara",
        "Stara e Climate FieldView na mesma frase",
        "F",
        "",
    ),
    ("Aegro", "X06"): (
        "https://aegro.com.br/",
        "Aegrozap",
        "produto de WhatsApp pelo nome",
        "F",
        "",
    ),
    ("Aegro", "X07"): (
        "https://aegro.com.br/",
        "CSV",
        "exportacao em PDF, Excel e CSV",
        "F",
        "",
    ),
    # =============================================== UPCAMPO — 12 PROVADAS
    ("upCampo", "X06"): (
        "https://www.upcampo.com.br/",
        "WhatsApp",
        "a UPi responde sobre a operacao pelo WhatsApp (15 ocorrencias)",
        "F",
        "",
    ),
    ("upCampo", "M08"): (
        "https://www.upcampo.com.br/",
        "MCP",
        "conector MCP para ChatGPT e Claude — o par mais proximo do Ampliagro",
        "F",
        "",
    ),
    ("upCampo", "M09"): (
        "https://www.upcampo.com.br/",
        "API",
        "API publica declarada",
        "F",
        "",
    ),
    ("upCampo", "M02"): (
        "https://www.upcampo.com.br/",
        "John Deere",
        "integracao com Deere nomeada",
        "F",
        "",
    ),
    ("upCampo", "M03"): (
        "https://www.upcampo.com.br/",
        "Solinftec",
        "integracao com fabricante brasileiro",
        "F",
        "",
    ),
    ("upCampo", "O09"): (
        "https://www.upcampo.com.br/",
        "georreferenciado",
        "monitoramento com registo georreferenciado",
        "F",
        "",
    ),
    ("upCampo", "L02"): (
        "https://www.upcampo.com.br/",
        "romaneios",
        "pos-colheita com fardos e romaneios",
        "F",
        "",
    ),
    # NOTA: a frase "amplitude de regras tributarias" e' uma **NAO capacidade**
    # declarada — e muito mais forte do que uma ausencia, porque e' a empresa a
    # dizer o que nao faz. Mas e' sobre **contabilidade**, e a coluna F16 e'
    # "Credito rural e seguro agricola". Sao coisas diferentes: a frase nao
    # diz nada sobre credito. Movi a prova para onde ela pertence — a coluna
    # F10 (contas a pagar e receber) fica com `?`, e esta frase e' citada na
    # ANALISE como evidencia de **escopo declarado**.
    ("upCampo", "X02"): (
        "https://www.upcampo.com.br/",
        "Sankhya",
        "conector com ERP nomeado; tambem Aliare e ViaSoft",
        "F",
        "",
    ),
    ("upCampo", "F02"): (
        "https://www.upcampo.com.br/",
        "nota fiscal",
        "nota fiscal na operacao integrada",
        "F",
        "",
    ),
    ("upCampo", "F14"): (
        "https://www.upcampo.com.br/",
        "custo",
        "custo por talhao e por safra nos dashboards",
        "F",
        "",
    ),
    ("upCampo", "O05"): (
        "https://www.upcampo.com.br/",
        "",
        "**REJEITADO.** 'cronograma' e 'planej' dao **0 ocorrencias** na pagina. "
        "A capacidade de planejamento de safra NAO esta provada",
        "?",
        "desce de S: afirmei cronograma a partir de snippet, e a pagina nao "
        "diz isso. O que ela prova e' outra coisa, duas linhas abaixo.",
    ),
    ("upCampo", "O04"): (
        "https://www.upcampo.com.br/",
        "72 mil atividades registradas",
        "gestao de actividades a escala — 72 mil registadas",
        "F",
        "substitui O05: e' o que a pagina de facto prova",
    ),
    ("upCampo", "O01"): (
        "https://www.upcampo.com.br/",
        "64 mil levantamentos de pragas",
        "registo de campo com georreferencia, a escala",
        "F",
        "",
    ),
    # =============================================== LUCRO RURAL — 5 PROVADAS
    ("Lucro Rural", "F01"): (
        "https://lucrorural.com.br/produtor",
        "LCDPR",
        "o produto LCDPR pelo nome, na pagina de produto",
        "F",
        "CORRIGIDO: a homepage nao tem; a /produtor tem",
    ),
    ("Lucro Rural", "F02"): (
        "https://lucrorural.com.br/produtor",
        "SEFAZ",
        "importacao de NF-e pela SEFAZ",
        "F",
        "",
    ),
    ("Lucro Rural", "F07"): (
        "https://lucrorural.com.br/produtor",
        "DRE",
        "DRE por safra, na pagina de produto",
        "F",
        "",
    ),
    ("Lucro Rural", "F08"): (
        "https://lucrorural.com.br/produtor",
        "resultado",
        "comparativo de regime de apuracao",
        "F",
        "",
    ),
    ("Lucro Rural", "F17"): (
        "https://lucrorural.com.br/",
        "imposto de renda",
        "projecao de IR (15 ocorrencias)",
        "F",
        "",
    ),
    # =============================================== SENIOR / GATEC — 8 PROVADAS
    ("Senior / GATec", "F01"): (
        "https://site.senior.com.br/agronegocio/funcionalidades-erp-agronegocio/",
        "Livro Caixa Digital do Produtor Rural",
        "modulo LCDPR nomeado na lista de produtos",
        "F",
        "",
    ),
    ("Senior / GATec", "O02"): (
        "https://site.senior.com.br/agronegocio/funcionalidades-erp-agronegocio/",
        "offline",
        "Mapfy e Simple Farm declaram 'online e offline'",
        "F",
        "",
    ),
    ("Senior / GATec", "O03"): (
        "https://site.senior.com.br/agronegocio/funcionalidades-erp-agronegocio/",
        "georreferenciados",
        "apontamentos georreferenciados",
        "F",
        "",
    ),
    ("Senior / GATec", "O09"): (
        "https://site.senior.com.br/agronegocio/funcionalidades-erp-agronegocio/",
        "Shield",
        "modulo de combate a pragas por nome",
        "F",
        "",
    ),
    ("Senior / GATec", "F18"): (
        "https://site.senior.com.br/agronegocio/funcionalidades-erp-agronegocio/",
        "Mão de Obra",
        "modulo de mao de obra rural",
        "F",
        "",
    ),
    ("Senior / GATec", "L02"): (
        "https://site.senior.com.br/agronegocio/funcionalidades-erp-agronegocio/",
        "Balança Controle Agronômico",
        "modulo de balanca por nome",
        "F",
        "",
    ),
    ("Senior / GATec", "P02"): (
        "https://site.senior.com.br/agronegocio/funcionalidades-erp-agronegocio/",
        "Receituário",
        "receituario agronomico nomeado",
        "F",
        "",
    ),
    ("Senior / GATec", "M09"): (
        "https://site.senior.com.br/agronegocio/funcionalidades-erp-agronegocio/",
        "Mapfy",
        "plataforma de mapas com integração; nativa com ERP via GATec",
        "F",
        "",
    ),
    # =============================================== CARBONO
    ("Carbonova / CarbonOS", "G05"): (
        "https://carbonova.ai/solucoes-inventario-carbono-ia",
        "Inventário de Emissões",
        "inventario de emissoes com escopos — **a pagina nunca escreve 'MRV'**",
        "F",
        "CORRIGIDO: o claim de 'MRV' veio de snippet e nao existe na pagina",
    ),
    ("CO2Token", "G05"): (
        "https://co2token.eco.br/",
        "",
        "**REJEITADO.** A pagina devolve 9 caracteres — SPA. Sem execucao de "
        "JavaScript nao ha citacao possivel",
        "?",
        "desce de S: a capacidade e' plausivel mas nao e' verificavel aqui",
    ),
    # --- O CASO FLUERE: a evidencia mais forte que nao passa por fetch
    ("Fluere Carbon", "G05"): (
        "https://www.slcagricola.com.br/imprensa/noticia/slc-agricola-anuncia-a-maior-operacao-de-mensuracao-de-carbono-gee-do-agro-brasileiro",
        "Fluere",
        "A **SLC Agricola** — companhia LISTADA — comunica que a Fluere "
        "desenvolveu a maior operacao de medicao de GEE do agro brasileiro: "
        "736 mil hectares, auditavel, GHG Protocol e FLAG. E' a companhia a "
        "confirmar, nao o fornecedor a prometer",
        "D",
        "O site fluere.ag devolve 404 ao fetch automatico. A prova e' de "
        "terceiros — e mais forte.",
    ),
    # =============================================== ACRESCIMOS DA DESCOBERTA EM MASSA
    # Gerado por `acrescimos.py` a partir de `descobrir_em_massa.py`.
    # 122 celulas passaram o filtro; 22 entraram. As outras 100 sao verdadeiras
    # mas nao distintivas — provam que o produto existe, nao que seja melhor.
    ("Senior / GATec", "F05"): (
        "https://site.senior.com.br/agronegocio/funcionalidades-erp-agronegocio/",
        "Reforma Tribut",
        "a transicao IBS/CBS nomeada na lista de funcionalidades",
        "F",
        "1 ocorrencias",
    ),
    ("TOTVS Protheus", "F05"): (
        "https://www.totvs.com/",
        "Reforma Tribut",
        "5 ocorrencias — a transicao e' um argumento de venda",
        "F",
        "5 ocorrencias",
    ),
    ("Aegro", "F10"): (
        "https://aegro.com.br/",
        "contas a pagar",
        "'contas e pagamentos' na landing page",
        "F",
        "1 ocorrencias",
    ),
    ("Sage X3", "F10"): (
        "https://www.sage.com/",
        "contas a pagar",
        "backoffice ERP",
        "F",
        "1 ocorrencias",
    ),
    ("SYSPRO", "F10"): (
        "https://www.syspro.com/",
        "accounts payable",
        "backoffice ERP",
        "F",
        "1 ocorrencias",
    ),
    ("Bushel Farm", "L05"): (
        "https://bushelfarm.com/",
        "grain contract",
        "3 ocorrencias — contratos de grao sao o neg��cio doBushel",
        "F",
        "3 ocorrencias",
    ),
    ("Datacor", "G02"): (
        "https://www.datacor.com/",
        "audit trail",
        "audit trail nomeado — **a coluna deixa de ser exclusiva do Ampliagro**",
        "F",
        "CORRICAO: o 9.md e a ANALISE listavam G02 como advantage exclusiva. A palavra existe na Datacor. O que continua a ser exclusivo e' G01 (proveniencia como TIPO em codigo, nao como log).",
    ),
    ("Datacor", "G01"): (
        "https://www.datacor.com/",
        "audit trail",
        "audit trail cobre linhagem de dado, que e' parte da proveniencia",
        "P",
        "PARCIAL: 'audit trail' prova registo de alteracoes. Nao prova tipagem de origem (medido / declarado / inventado).",
    ),
    ("AgriChain", "G04"): (
        "https://agrichain.com/",
        "multiple farm",
        "multi-sitio declarado",
        "F",
        "1 ocorrencias",
    ),
    ("Traction Ag", "G04"): (
        "https://tractionag.com/",
        "multiple farm",
        "multi-sitio declarado",
        "F",
        "1 ocorrencias",
    ),
    ("Bushel Farm", "M02"): (
        "https://bushelfarm.com/",
        "John Deere",
        "integracao com Deere — a Bushel e' de origem americana",
        "F",
        "1 ocorrencias",
    ),
    ("Bushel Farm", "M03"): (
        "https://bushelfarm.com/",
        "Climate FieldView",
        "integracao com FieldView",
        "F",
        "1 ocorrencias",
    ),
    ("Traction Ag", "M02"): (
        "https://tractionag.com/",
        "John Deere",
        "integracao com Deere",
        "F",
        "2 ocorrencias",
    ),
    ("Traction Ag", "M03"): (
        "https://tractionag.com/",
        "Climate FieldView",
        "integracao com FieldView",
        "F",
        "1 ocorrencias",
    ),
    ("TOTVS PIMS Agro", "F18"): (
        "https://produtos.totvs.com/",
        "folha de pagamento",
        "modulo nomeado",
        "F",
        "3 ocorrencias",
    ),
    ("Carbonova / CarbonOS", "M07"): (
        "https://carbonova.ai/",
        "edge AI",
        "3 ocorrencias — IA na borda, no mesmo sitio que o Ampliagro",
        "F",
        "e' o unico concorrente provado com IA na borda. E' carbono, nao agro.",
    ),
    ("TOTVS Protheus", "F16"): (
        "https://www.totvs.com/",
        "financial services",
        "**NAO e' credito rural.** E' servico financeiro a agroindustria",
        "P",
        "PARCIAL por caution: a coluna pede credito rural / seguro agricola. Servico financeiro geral nao prova isso.",
    ),
    ("Aptean Food & Beverage", "F16"): (
        "https://aptean.com/",
        "financial services",
        "**NAO e' credito rural.** E' financiamento de processo",
        "P",
        "como acima",
    ),
    ("Agworld", "O02"): (
        "https://agworld.com/",
        "offline",
        "app funciona sem rede",
        "F",
        "2 ocorrencias",
    ),
    ("Farmable", "O02"): (
        "https://farmable.tech/",
        "without internet",
        "'works without internet' — frase literal",
        "F",
        "1 ocorrencias",
    ),
    ("Agworld", "O09"): (
        "https://agworld.com/",
        "pest",
        "monitoramento de pragas",
        "F",
        "2 ocorrencias",
    ),
    ("Farmable", "O09"): (
        "https://farmable.tech/",
        "IPM",
        "3 ocorrencias de IPM",
        "F",
        "2 ocorrencias",
    ),
}

#: As celulas que desceram. Registadas para que a queda nao seja silenciosa.
REJEITADAS: list[tuple[str, str, str]] = [
    (
        "upCampo",
        "F16",
        "fragmento 'nao faz contabilidade' rejeitado; substituido por 'amplitude de regras tributarias'",
    ),
    (
        "Carbonova / CarbonOS",
        "G05",
        "'MRV' nao existe na pagina; substituido por 'Inventario de Emissoes'",
    ),
    ("CO2Token", "G05", "SPA de 9 caracteres — sem texto, sem prova"),
    ("Fluere Carbon", "G05", "site 404 ao fetch; prova por comunicado de bolsa da SLC"),
    ("Lucro Rural", "F06", "'NCM' nao esta na homepage nem na /produtor"),
    ("Lucro Rural", "F16", "'credito rural' nao aparece"),
    ("Aegro", "F11", "REJEITADO em /solucoes/gestao-rural/; esta na homepage"),
    ("upCampo", "O05", "REJEITADO: 'cronograma' e 'planej' dao 0x. Desce para ?"),
]
