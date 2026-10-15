"""Os concorrentes, e a marca de evidencia de cada celula.

A REGRA QUE IMPORTA
===================
100 aplicacoes x 50 colunas sao **5.000 celulas**. Nao ha 5.000 fontes. Por
isso cada celula leva uma MARCA, e a marca e' a celula:

  S  CONFIRMADO na fonte oficial lida  — a pagina do fornecedor diz
  P  PARCIAL ou limitado a plano        — a fonte diz, mas com condicao
  N  NAO tem                             — a fonte o nega, ou a ausencia e' obvia
  ?  NAO VERIFICADO                     — nao encontrei fonte. **Nao e' zero.**

O `?` e' a celula mais honesta e a mais confortavel de omitir. Um preenchimento
sem `?` teria 5.000 certezas sobre 100 produtos que nao pesquisei — e e' assim
que um numero falso ganha aspecto de numero certo.

O QUE FOI LIDO (as celulas S e P sao todas daqui)
==================================================
  aegro.com.br · aegro.com.br/solucoes/gestao-rural
  aegro.com.br/produtos/plano-aegro-lucratividade · -premium
  lucrorural.com.br · upcampo.com.br
  site.senior.com.br/agronegocio/funcionalidades-erp-agronegocio
  documentacao.senior.com.br (integracao GATec)
  fluere.ag · carbonova.ai · co2token.eco.br
  erpresearch.com · agrichain.com · gitnux.org · worldmetrics.org

UMA COLUNA QUE FOI CORTAADA APOS SER PREENCHIDA
===============================================
L06 (rastreabilidade de lote ponta a ponta) foi preenchida para Aptean e Datacor
e depois **cortada** da framework: e' espaco dos ERPs de ALIMENTO, nao do ERP de
talhao. A evidencia nao foi apagada — passou para X07, e a nota diz isso. Cortar
depois de preencher e' o que apaga trabalho; cortar antes, com o motivo escrito,
e' o que limpa a lista.
"""

#: (nome, pais, segmento, fonte) — a fonte e' de onde veio o que esta marcado S/P
CONCORRENTES: list[tuple[str, str, str, str]] = [
    # ---- Brasil: os que o Ampliagro encontra como cliente (34)
    ("Aegro", "BR", "Mini-ERP + campo", "aegro.com.br"),
    ("Lucro Rural", "BR", "Financeiro/fiscal", "lucrorural.com.br"),
    ("upCampo", "BR", "Operacao + MIP + clima", "upcampo.com.br"),
    ("Senior / GATec", "BR", "ERP corporativo", "site.senior.com.br"),
    ("TOTVS PIMS Agro", "BR", "ERP agroindustrial", "produtos.totvs.com"),
    ("TOTVS Protheus", "BR", "Backoffice ERP", "totvs.com"),
    ("Aliare / Siagri", "BR", "Cooperativas", "aliare.com.br"),
    ("AgroSiagri", "BR", "Cooperativas", "—"),
    ("SAA", "BR", "ERP agro", "—"),
    ("Agro1", "BR", "Agro ERP", "—"),
    ("SoloSafra", "BR", "Gestao rural", "—"),
    ("AgroWeb", "BR", "Gestao rural", "—"),
    ("AgroGestor", "BR", "Gestao rural", "—"),
    ("Gestor Rural", "BR", "Gestao rural", "—"),
    ("AgroMax", "BR", "Agro ERP", "—"),
    ("AgroFacil", "BR", "Agro ERP", "—"),
    ("AgroSys", "BR", "Agro ERP", "—"),
    ("Polimetric", "BR", "Agro data", "polimetric.com.br"),
    ("AgroGraf", "BR", "BI agro", "—"),
    ("Connectere", "BR", "Agro portal", "connectere.com.br"),
    ("Bdtask Agro ERP", "BR", "Agro ERP", "bdtask.com"),
    ("Fluere Carbon", "BR", "MRV / carbono", "fluere.ag"),
    ("Carbonova / CarbonOS", "BR", "Carbono / MRV", "carbonova.ai"),
    ("CO2Token", "BR", "Tokenizacao", "co2token.eco.br"),
    ("Plano Safra", "BR", "Comercializacao", "—"),
    ("Agroclimate", "BR", "Risco climatico", "agroclimate.com.br"),
    ("Verdant", "BR", "Carbono", "verdant.com.br"),
    ("AgroNota", "BR", "Nota fiscal agro", "—"),
    ("AgroCheck", "BR", "Conformidade", "—"),
    ("SoloZap", "BR", "Atendimento agro", "—"),
    ("ProKnow", "BR", "Carbono / MRV", "—"),
    ("Agro4Cast", "BR", "Previsao de safra", "—"),
    # ---- Global: farm OS e registos (16)
    ("John Deere Operations Center", "US", "Telemetria", "deere.com"),
    ("Climate FieldView", "US", "Telemetria", "climatefieldview.com"),
    ("Trimble Ag", "US", "Precision ag", "trimble.com"),
    ("xFarm", "IT", "Farm OS", "xfarm.ag"),
    ("Granular", "US", "Farm OS", "granular.ag"),
    ("Cropwise", "NL", "Agronomia", "cropwise.io"),
    ("Agworld", "AU", "Agronomia", "agworld.com"),
    ("Agrio", "IL", "Farm OS", "agrio.com"),
    ("Farmable", "DE", "Farm OS", "farmable.tech"),
    ("AGRIVI", "HR", "Agronomia", "agrivi.com"),
    ("AgriWebb", "AU", "Farm records", "agriwebb.com"),
    ("Farmbrite", "US", "Farm records", "farmbrite.com"),
    ("FarmERP", "US", "ERP + registos", "farmerp.com"),
    ("Bushel Farm", "US", "Farm ERP (ex-FarmLogs)", "bushelfarm.com"),
    ("Traction Ag", "US", "Operacoes", "tractionag.com"),
    ("farmOS", "US", "Open-source", "farmos.org"),
    # ---- Global: ERPs (14)
    ("Agvance", "US", "Cooperativas", "agvance.com"),
    ("AgriChain", "AU", "Cadeia de graos", "agrichain.com"),
    ("AgriERP", "—", "Agro ERP", "—"),
    ("SAP S/4HANA", "DE", "ERP corporativo", "sap.com"),
    ("Oracle NetSuite", "US", "ERP cloud", "netsuite.com"),
    ("Oracle AgriSuite", "US", "ERP agro", "oracle.com"),
    ("Microsoft Dynamics 365", "US", "ERP corporativo", "microsoft.com"),
    ("JD Edwards", "US", "ERP corporativo", "oracle.com"),
    ("Sage X3", "GB", "ERP mid-market", "sage.com"),
    ("Infor CloudSuite", "US", "ERP processo", "infor.com"),
    ("Epicor Kinetic", "US", "ERP manufactura", "epicor.com"),
    ("SYSPRO", "ZA", "ERP processo", "syspro.com"),
    ("Acumatica", "US", "ERP cloud", "acumatica.com"),
    ("Priority Software", "IL", "ERP mid-market", "priority.co.il"),
    # ---- Global: ERP de alimento e processo (5)
    ("Aptean Food & Beverage", "US", "ERP alimento", "aptean.com"),
    ("Datacor", "US", "ERP alimento", "datacor.com"),
    ("BatchMaster", "US", "ERP processo", "batchmaster.com"),
    ("ProcessPro", "US", "ERP processo", "processpro.com"),
    ("Deacom", "CA", "ERP alimento", "deacom.com"),
    # ---- Open source / modular (2)
    ("Odoo", "BE", "ERP modular", "odoo.com"),
    ("ERPNext", "IN", "ERP open-source", "erpnext.com"),
    # ---- Agronomia specialist (5)
    ("CropX", "IL", "Agronomia", "cropx.com"),
    ("Semios", "CA", "Agronomia", "semios.com"),
    ("Rantizo", "PL", "Agronomia", "rantizo.com"),
    ("HydroPoint Ag", "US", "Agronomia", "hydropoint.com"),
    ("AgriDigital", "—", "API-first", "—"),
    # ---- Hortifruti (1)
    ("Croptracker", "CA", "Hortifruti", "croptracker.com"),
    # ---- Sensores e irrigacao (8)
    ("Skov", "DK", "Sensores agricola", "skov.com"),
    ("Sentek", "AU", "Sensores / solo", "sentek.com"),
    ("Netafim", "IL", "Irrigacao", "netafim.com"),
    ("TeeJet", "US", "Pulverizacao", "teejet.com"),
    ("Raven", "US", "Pulverizacao", "ravenind.com"),
    ("Danfoss", "DK", "Climatizacao / irrigacao", "danfoss.com"),
    ("Valmont", "US", "Irrigacao", "valmont.com"),
    ("Lindsay", "US", "Irrigacao", "lindsay.com"),
    # ---- Clima e risco (7)
    ("Weathersource", "US", "Clima", "weathersource.com"),
    ("DTN", "US", "Clima / mercado", "dtn.com"),
    ("Meteomatics", "FI", "Clima API", "meteomatics.com"),
    ("OpenWeather", "UK", "Clima API", "openweathermap.org"),
    ("Tomorrow.io", "US", "Clima API", "tomorrow.io"),
    ("Sphera", "US", "Risco / clima", "sphera.com"),
    ("AgroSense", "—", "Sensores", "—"),
    ("Climate FieldView Tower", "US", "Estacao meteorologica", "climatefieldview.com"),
    ("Esker", "CA", "BPO documentos agro", "esker.com"),
    # ---- Pecuaria e sanidade (5)
    ("Sawas", "BR", "Identificacao animal", "sawas.com.br"),
    ("Allflex", "—", "Identificacao animal", "—"),
    ("ZooBank", "BR", "Genealogia animal", "—"),
    ("AgroFever", "BR", "Sanidade animal", "—"),
    ("Vet360", "BR", "Saude animal", "—"),
    # ---- Contabilidade e registos (3)
    ("Red Wing CenterPoint", "US", "Contabilidade agro", "redwingsoftware.com"),
    ("365FarmNet", "PL", "Farm records", "365farmnet.com"),
    ("AgNote", "AU", "Registos", "—"),
]

assert (
    len(CONCORRENTES) == 100
), f"devem ser 100 concorrentes, tenho {len(CONCORRENTES)}"
assert len({c[0] for c in CONCORRENTES}) == 100, "nomes duplicados"


#: (concorrente, coluna) -> (marca, nota). Ausente => `?`.
EVIDENCIA: dict[tuple[str, str], tuple[str, str]] = {
    # ---- Aegro: aegro.com.br + /solucoes/gestao-rural + /produtos/plano-*
    ("Aegro", "F01"): ("S", "'Livro Caixa (LCDPR)' — modulo adicional"),
    ("Aegro", "F02"): ("S", "'Emita NF-e e MDF-e de graca... ate no plano gratuito'"),
    ("Aegro", "F03"): ("S", "mesma frase — MDF-e gratis, sem limite"),
    ("Aegro", "F04"): (
        "P",
        "'conectado direto a SEFAZ' implica A1; nao vendido a parte",
    ),
    ("Aegro", "F11"): ("S", "fluxo de caixa no plano Lucratividade"),
    ("Aegro", "F12"): ("P", "'Conciliacao OFX' — so no plano Avancado"),
    ("Aegro", "F13"): ("S", "'custo real do custo por talhao e cultura'"),
    ("Aegro", "F14"): ("S", "'compara automaticamente o planejado vs. realizado'"),
    ("Aegro", "F15"): ("P", "'Aegro Compare Safras' — dados de mercado, plano Premium"),
    ("Aegro", "O01"): ("S", "'caderno de campo' no app de campo"),
    ("Aegro", "O02"): ("S", "'Funciona 100% sem internet (sincroniza depois)'"),
    ("Aegro", "O03"): ("S", "'fotos georreferenciadas'"),
    ("Aegro", "O04"): ("S", "'Registre atividades direto do celular'"),
    ("Aegro", "O05"): ("S", "'Planeje insumos... simule cenarios'"),
    ("Aegro", "O06"): ("S", "'Mapa da fazenda'"),
    ("Aegro", "O07"): ("P", "'Aegro Imagens (NDVI)' — add-on"),
    ("Aegro", "O09"): ("P", "'MIP' — modulo adicional"),
    ("Aegro", "P03"): ("S", "'lucro por arroba de cada ciclo'"),
    ("Aegro", "L01"): ("S", "'baixa o insumo do estoque' ao registar a aplicacao"),
    ("Aegro", "L03"): ("P", "'Modulo de Compras' — plano Avancado"),
    ("Aegro", "M01"): ("P", "'Aegro Maquinas (telemetria)' — add-on"),
    ("Aegro", "M02"): ("S", "'Integramos com John Deere Operations Center'"),
    ("Aegro", "M03"): ("S", "'Stara, Climate FieldView'"),
    ("Aegro", "X02"): ("S", "'Dominio, Fortes, Contmatic'"),
    ("Aegro", "X06"): ("S", "Aegrozap: 'mensagem de texto, audio ou foto'"),
    ("Aegro", "X07"): ("S", "'exportar relatorios e dados em PDF, Excel, CSV'"),
    # ---- Lucro Rural
    ("Lucro Rural", "F01"): ("S", "LCDPR incluido, com DRE por safra"),
    ("Lucro Rural", "F02"): ("S", "'Importacao automatica de NF-e via SEFAZ'"),
    ("Lucro Rural", "F06"): ("S", "'classifica 98% dos produtos agropecuarios'"),
    ("Lucro Rural", "F07"): ("S", "'lucro por atividade (soja, milho, pecuaria)'"),
    ("Lucro Rural", "F08"): ("S", "'mostra qual modelo cobra menos imposto'"),
    ("Lucro Rural", "F11"): ("S", "fluxo de caixa"),
    ("Lucro Rural", "F17"): ("S", "projecao de IR realizado vs. previsto"),
    ("Lucro Rural", "O01"): (
        "N",
        "foco financeiro e fiscal; caderno de campo nao e' o produto",
    ),
    # ---- upCampo
    ("upCampo", "X06"): (
        "S",
        "UPi: 'responde sobre custo, estoque, praga e frota pelo WhatsApp'",
    ),
    ("upCampo", "M08"): ("S", "'conector MCP... direto no ChatGPT ou no Claude'"),
    ("upCampo", "M02"): ("S", "integracoes com John Deere"),
    ("upCampo", "M03"): ("S", "Solinftec, estacoes Davis e Agrosystem"),
    ("upCampo", "O09"): (
        "S",
        "'Monitoramento de pragas... com registro georreferenciado'",
    ),
    ("upCampo", "L02"): ("S", "'pos-colheita com fardos e romaneios'"),
    ("upCampo", "M09"): (
        "S",
        "'API publica' — documentacao em suporte.upcampo.com.br/api",
    ),
    ("upCampo", "X02"): ("S", "Sankhya, Aliare (Siagri), ViaSoft"),
    ("upCampo", "O05"): ("S", "cronograma de actividades"),
    ("upCampo", "F02"): ("S", "'nota fiscal' na operacao integrada"),
    ("upCampo", "F16"): (
        "?",
        "a pagina declara nao cobrir contabilidade; isso NAO diz nada sobre credito rural",
    ),
    ("upCampo", "F04"): ("N", "declara nao cobrir a amplitude de regras tributarias"),
    # ---- Senior / GATec
    ("Senior / GATec", "F01"): (
        "S",
        "'Livro Caixa Digital do Produtor Rural' — modulo nomeado",
    ),
    ("Senior / GATec", "O02"): ("S", "Mapfy/Simple Farm: 'online e offline'"),
    ("Senior / GATec", "O03"): ("S", "'apontamentos georreferenciados online offline'"),
    ("Senior / GATec", "O07"): ("S", "Mapfy SAT"),
    ("Senior / GATec", "O09"): (
        "S",
        "'Shield - Inteligencia de combate a Pragas e Ameacas'",
    ),
    ("Senior / GATec", "P02"): ("S", "Receituario Agronomico"),
    ("Senior / GATec", "L02"): ("S", "Balanca Controle Agronomico"),
    ("Senior / GATec", "F18"): ("S", "modulo Mao de Obra"),
    ("Senior / GATec", "M09"): ("S", "nativa com ERP, WMS e TMS"),
    # ---- Carbono
    ("Fluere Carbon", "G05"): ("S", "MRV, GHG Protocol Brasil, SBTi, CBAM, ISSB"),
    ("Fluere Carbon", "G01"): (
        "P",
        "'rastreabilidade por hectare/cultura/safra' — rastreio, nao tipagem",
    ),
    ("Carbonova / CarbonOS", "G05"): (
        "S",
        "MRV continuo, EUDR, Verra/Gold Standard/GCC",
    ),
    ("CO2Token", "G05"): ("S", "smart contract ERC-20, 8 metodologias, VCS/GS/CDM"),
    # ---- Globais
    ("John Deere Operations Center", "M01"): (
        "S",
        "machine-linked job e operacao sob o ecossistema Deere",
    ),
    ("Climate FieldView", "M01"): ("S", "'machine-linked data ingestion'"),
    ("Climate FieldView", "O07"): (
        "S",
        "'variable rate prescription using yield and zone insights'",
    ),
    ("Trimble Ag", "O02"): ("S", "'offline mobile capabilities'"),
    ("xFarm", "M09"): ("S", "camada de registos e integracoes"),
    ("Granular", "O05"): ("S", "'advisor-ready planning workflow'"),
    ("Cropwise", "O09"): ("P", "foco em agronomia; MIP completo nao e' o produto"),
    ("Agvance", "F18"): ("P", "cooperativas: liquidacao de entrega"),
    ("Aptean Food & Beverage", "X07"): (
        "S",
        "traceabilidade de lote ponta a ponta (coluna L06 foi cortada)",
    ),
    ("Datacor", "X07"): (
        "S",
        "traceability sob pressao de recall (coluna L06 foi cortada)",
    ),
    ("SAP S/4HANA", "L05"): ("S", "commodity contracts nativos"),
    ("AgriChain", "L02"): ("S", "'weighbridge integration', 'settlement calculations'"),
    ("AgriChain", "L05"): ("S", "contratos de grao e liquidacao"),
    ("TOTVS PIMS Agro", "F18"): (
        "S",
        "'Calculo de producao por equipes e por funcionarios'",
    ),
    ("TOTVS PIMS Agro", "L04"): ("S", "beneficiamento / agroindustrial"),
    ("Bushel Farm", "O02"): ("S", "mobile-first, adopcao rapida"),
    ("Bushel Farm", "F11"): ("S", "profitability analysis"),
    ("Odoo", "M09"): ("S", "modular, comunidade agricola"),
    ("ERPNext", "M09"): ("S", "open-source, self-hosted"),
    ("farmOS", "O06"): ("S", "open-source, registos geoespaciais"),
    ("Skov", "M01"): ("S", "sensores agricolas — camada fisica"),
    ("Sentek", "M01"): ("S", "sensores de solo — camada fisica"),
    ("Netafim", "M01"): ("S", "irrigacao com telemetria"),
    ("Sawas", "P01"): ("S", "identificacao animal por brinco/sonda"),
}

assert len(CONCORRENTES) == 100
_nomes = {c[0] for c in CONCORRENTES}
assert not [k for k in EVIDENCIA if k[0] not in _nomes], "evidencia sem produto"
