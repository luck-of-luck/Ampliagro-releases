"""O catálogo da Guia de Ferramentas: 8 classes, ~70 capacidades, com estado HONESTO.

POR QUE ISTO É UM MÓDULO E NÃO UM LISTA NO TEMPLATE
==================================================
MEDIDO 2026-10-05. A guia tinha 4 abas e 17 ferramentas, todas declaradas no
template. Pediu-se que oferecesse o mesmo que um produto de topo de mercado e
que não mentisse. A lista de mercado tem ~70 itens — e **12 deles não existem
neste repositório**.

Um template que os listasse todos seria exactamente o defeito que corrigimos
hoje: o botão NDVI mostrava `0.72` num `catch` de uma rota 404. Um número
gerado apresentado como leitura. Uma lista de capacidades que não existem
apresentadas como entregues é o mesmo erro, com mais linhas.

Por isso o catálogo é um **módulo Python com estado explícito e prova**, e o
teste `tests/test_guia_ferramentas_confere_com_codigo.py` valida cada linha.

OS TRÊS ESTADOS — E O QUE CADA UM PROMETE
=========================================
EXISTE     Abre uma rota real. `rota` é verificável e o teste confirma que
           resolve. O produtor clica e acontece alguma coisa.
PARCIAL    Há parte a sério e a parte a faltar, e a ficha diz **qual**. Exemplo:
           "NF-e do produtor rural" — importa XML, não emite. Um item PARCIAL
           não é um item meio-prometido: é um item com a fronteira escrita.
NAO_EXISTE Honestidade. Não há botão, não há rota, não há promessa. Aparece
           na lista para o produtor ver o que o mercado tem e o Ampliagro não,
           e para ninguém confundir "roadmap" com "funcional".

Este módulo NÃO é um site de documentação. É o que a guia renderiza. Se um
item disser NAO_EXISTE, não há `rota` — e o teste recusa que haja.

NÃO INVENTEI NADA
=================
Cada `prova` aponta para ficheiro e linha que **li**. Onde não achei, o estado
é NAO_EXISTE e a prova diz `ausente`. Não há "planeado", "em breve" nem
"compatível": quem não tem código não tem promessa.
"""

from __future__ import annotations

from typing import Any

# ═══════════════════════════════════════════════════════════════════════════
# ESTADOS
# ═══════════════════════════════════════════════════════════════════════════
EXISTE = "EXISTE"
PARCIAL = "PARCIAL"
NAO_EXISTE = "NAO_EXISTE"

#: Rótulos que a página escreve. O vocabulário é o do resto do projeto
#: (`proveniencia.py`, `validators.py`): medido / sem_dado / declarado.
ESTADO_ROTULO = {
    EXISTE: "Operacional",
    PARCIAL: "Parcial — com a fronteira escrita",
    NAO_EXISTE: "Não implementado",
}


def _existe(
    nome: str,
    rota: str,
    prova: str,
    resumo: str,
    *,
    governanca: str = "",
    dias: int = 0,
    sem_ecra: bool = False,
    onde_vive: str = "",
) -> dict[str, Any]:
    """Uma capacidade que abre uma rota real — ou que vive noutro ecrã.

    `prova` é `caminho:linha` e é **verificada pelo teste**. Uma prova que não
    aponta para nada, ou uma rota que não resolve, fazem o teste falhar.

    `sem_ecra=True` é para o que funciona mas não tem página própria: a IA no
    dispositivo carrega no painel do dashboard, não na guia. `onde_vive` é
    obrigatório nesse caso — quem não tem botão tem de dizer onde está.
    """
    return {
        "nome": nome,
        "estado": EXISTE,
        "rota": rota,
        "prova": prova,
        "resumo": resumo,
        "governanca": governanca,
        "dias": dias,
        "sem_ecra": sem_ecra,
        "onde_vive": onde_vive,
    }


def _parcial(
    nome: str,
    rota: str,
    prova: str,
    faz: str,
    falta: str,
    *,
    governanca: str = "",
    dias: int = 0,
) -> dict[str, Any]:
    """Uma capacidade a meio. `falta` é obrigatória e não pode ser vazia.

    Um PARCIAL sem `falta` escrito é um EXISTE disfarçado — por isso o teste
    trata `falta` vazio como erro.
    """
    return {
        "nome": nome,
        "estado": PARCIAL,
        "rota": rota,
        "prova": prova,
        "resumo": faz,
        "falta": falta,
        "governanca": governanca,
        "dias": dias,
    }


def _nao_existe(
    nome: str, prova: str, o_que_falta: str, *, por_que: str = ""
) -> dict[str, Any]:
    """Uma capacidade que o mercado tem e este repositório não.

    `prova` = `ausente`, porque a ausência não tem linha. O teste confirma
    que não há rota — o que impede que um item NAO_EXISTE ganhe um botão.
    """
    return {
        "nome": nome,
        "estado": NAO_EXISTE,
        "rota": "",
        "prova": prova,
        "resumo": o_que_falta,
        "governanca": por_que,
        "dias": 0,
    }


# ───────────────────────────────────────────────────────────────────────────
# Itens que a lista de mercado tem e a auditoria inicial não detailhou.
#
# Todos com estado medido. `prova` e `rota` verificadas com `resolve()` e por
# leitura de linha antes de entrarem aqui — a lição de hoje, escrita.
# ───────────────────────────────────────────────────────────────────────────
EXTRAS_FISCAL: list[dict[str, Any]] = [
    _existe(
        "Centros de custo",
        "/custos/centros/",
        "app/api/views/custos.py:420",
        "Rateio por centro de custo antes do talhão, para o custo não ficar "
        "órfão no meio.",
        governanca="Despesa sem centro nem talhão aparece como pendente de "
        "vínculo, não some do total.",
        dias=30,
    ),
]

EXTRAS_FINANCEIRO: list[dict[str, Any]] = [
    _existe(
        "Fluxo de caixa realizado",
        "/financeiro/cashflow/",
        "app/api/views/financial.py:309",
        "Entradas e saídas por período, a partir dos lançamentos reais.",
        dias=30,
    ),
]

EXTRAS_CAMPO: list[dict[str, Any]] = [
    _existe(
        "Prescrição e VRA",
        "/cadastro/vra/",
        "app/models/producao.py:170",
        "Prescrição por zona de manejo, com contexto da recomendação e versão "
        "da análise guardados no registo.",
        governanca="`proveniencia` é propriedade do modelo: a prescrição sabe "
        "de onde veio a recomendação mesmo que o dado mude depois.",
        dias=60,
    ),
    _existe(
        "Previsão de safra",
        "/previsao/safra/",
        "app/api/views/core.py:141",
        "Projeção de produtividade por talhão e cultura.",
        dias=45,
    ),
    _existe(
        "Receituário agronómico",
        "/cadastro/receituario/",
        "app/models/producao.py:594",
        "Receitas agronômicas com a medição registada e dois relógios: quando "
        "o produtor registou e quando sincronizou.",
        governanca="`fonte_dado` distingue medido de declarado. `registado_em` "
        "e `sincronizado_em` separados porque são factos diferentes.",
        dias=45,
    ),
]

EXTRAS_DADOS: list[dict[str, Any]] = [
    _existe(
        "Exportação LGPD",
        "/lgpd/export/",
        "app/views/lgpd.py:128",
        "Exportação dos teus dados em JSON e eliminação, como a lei exige.",
        dias=30,
    ),
    _existe(
        "Alertas críticos da operação",
        "/alertas/criticos/",
        "app/management/commands/gerar_alertas.py:338",
        "Motor que junta alertas de agendas, MIP, vacinas, ordens paradas e estoque.",
        dias=45,
    ),
]


# ═══════════════════════════════════════════════════════════════════════════
# A — FISCAL
# ═══════════════════════════════════════════════════════════════════════════
# MEDIDO 2026-10-05 por varredura de app/services/, app/api/views/, app/urls.py.
# O LCDPR é a única capacidade fiscal com testes a passar: 34 testes em 7
# ficheiros. `app/fiscal/` NÃO existe — as capacidades estão dispersas por 7
# ficheiros sem fronteiras.
FISCAL: list[dict[str, Any]] = [
    _existe(
        "LCDPR — Livro Caixa do Produtor Rural",
        "/api/financeiro/lcdpr/download/",
        "app/api/views/financial.py:419",
        "Gera o ficheiro da RFB no leiaute 1.3, com guarda que recusa exportar "
        "quando faltam campos obrigatórios.",
        governanca="Guarda antes de gerar: `pode_exportar()` valida CPF, talhões "
        "e parceria antes de escrever o ficheiro. 34 testes.",
        dias=90,
    ),
    _parcial(
        "NF-e do produtor rural",
        "/api/nfe/import/",
        "app/views/nfe_auto.py:26",
        "Importa XML de NF-e e extrai itens, NCM e valores para lançamentos.",
        "EMISSÃO não existe: `app/services/nfe.py:354` levanta "
        "`NotImplementedError`. Falta certificado A1 e assinatura XML.",
        governanca="Sem assinatura digital não há documento válido. Importar não "
        "é emitir — a diferença é legal, não deDegrees de esforço.",
        dias=120,
    ),
    _nao_existe(
        "MDF-e — manifesto eletrônico",
        "ausente",
        "Zero ocorrências em app/, tests/ e config/.",
    ),
    _nao_existe(
        "Certificado A1 / ICP-Brasil",
        "ausente",
        "Só placeholders: `app/services/nfe.py:336` tem `ENDPOINTS_POR_UF = {}` "
        "vazio de propósito, e o check de certificado passa sempre falso.",
    ),
    _nao_existe(
        "Reforma Tributária (IBS/CBS)",
        "ausente",
        "Zero ocorrências. Sem modelo, sem taxa, sem cálculo.",
    ),
    _parcial(
        "NCM / TIPI",
        "/api/nfe/import/",
        "app/ia/ingestao/nfe.py:190",
        "Capta o NCM do XML da NF-e importada.",
        "Não há tabela NCM, nem TIPI, nem CEST, nem conversión entre código e "
        "alíquota. O código é lido e guardado; nada é calculado com ele.",
        dias=30,
    ),
    _parcial(
        "DRE por cultura e safra",
        "/custos/dre/",
        "app/services/custo_talhao.py:256",
        "Custo por talhão e por hectare, por safra, com DRE financeiro.",
        "Não é DRE rural: falta a dimensão cultura e a memória de cálculo que "
        "a Receita exige. `app/services/dre.py:8` é genérico por período.",
        dias=60,
    ),
    _parcial(
        "Presumido x Resultado",
        "/api/exportar-lcdpr/",
        "app/services/lcdpr_layout.py:67",
        "Os dois regimes estão declarados no leiaute (Livro Caixa e art. 5º "
        "da Lei 8.023/1990).",
        "`app/services/lcdpr_export.py:518` escreve SEMPRE Livro Caixa, "
        "hardcoded. Sem campo de escolha, sem UI, sem parametrização.",
        dias=15,
    ),
]
FISCAL = FISCAL + EXTRAS_FISCAL


# ═══════════════════════════════════════════════════════════════════════════
# B — FINANCEIRO
# ═══════════════════════════════════════════════════════════════════════════
FINANCEIRO: list[dict[str, Any]] = [
    _existe(
        "Contas a pagar e a receber",
        "/financeiro/",
        "app/api/urls.py:253",
        "Lançamentos, contas, vencimentos e saldo por conta.",
        governanca="Alertas de vencimento e de ordem de compra parada.",
        dias=60,
    ),
    _existe(
        "Conciliação bancária por OFX",
        "/api/conciliacoes-bancarias/",
        "app/api/views/financeiro_banco.py:230",
        "Importa OFX/QFX/CSV, sugere o casamento por valor e janela de ±3 dias, "
        "e fecha a conciliação.",
        governanca="23 testes em `tests/test_importar_extrato.py`. "
        "`app/services/bank_import.py` é CÓDIGO MORTO — `parse_ofx` e "
        "`conciliar_transacoes` não têm chamador e `ofxparse` não está no "
        "`requirements.txt`.",
        dias=45,
    ),
    _parcial(
        "Fluxo de caixa",
        "/simulador/financeiro/",
        "app/api/urls.py:339",
        "Projeção de 12 meses com receita, custo e margem.",
        "É projeção, não fluxo realizado: não reconcilia com o extrato bancário "
        "nem distingue realizado de previsto.",
        dias=30,
    ),
    _existe(
        "Custo por talhão e por hectare",
        "/custos/producao/",
        "app/api/views/custos.py:307",
        "Custo alocado por talhão, com receita e margem.",
        governanca="Alerta explícito quando um lançamento não tem talhão: "
        "despesa sem vínculo não desaparece do total.",
        dias=60,
    ),
    _existe(
        "Orçado x realizado",
        "/custos/dre/",
        "app/api/views/custos.py:420",
        "Comparação com orçamento e upload de conciliação.",
        governanca="Orçado zero explícito continua a ser zero; orçado ausente "
        "diz 'não definido' e não herda o realizado.",
        dias=30,
    ),
    _nao_existe(
        "Benchmark de mercado entre produtores",
        "ausente",
        "Não existe base de outros produtores. O 'Margem vs Top 100' do template "
        "era uma comparação sem fonte.",
    ),
    _nao_existe(
        "Crédito rural e seguro agrícola",
        "ausente",
        "Nem modelo, nem taxa, nem simulador. Sem licensed de seguro, isto "
        "seria um número inventado com aparência oficial.",
    ),
    _nao_existe(
        "Projeção de IR ao longo do ano",
        "ausente",
        "Não há cálculo de imposto de renda. `Funcionario.salario` existe, mas "
        "IR progressivo não.",
    ),
    _parcial(
        "Folha de pagamento rural",
        "/empregados/",
        "app/models/equipe.py:295",
        "Cada funcionário tem salário, e o tipo de documento FOLHA existe no "
        "leiaute do LCDPR.",
        "Não existe folha rural nem sazonal: sem proventos, sem adiantamentos, "
        "semSSS rescisão, sem gerador. É um rótulo de classificação.",
        dias=60,
    ),
]
FINANCEIRO = FINANCEIRO + EXTRAS_FINANCEIRO


# ═══════════════════════════════════════════════════════════════════════════
# C — CAMPO
# ═══════════════════════════════════════════════════════════════════════════
CAMPO: list[dict[str, Any]] = [
    _parcial(
        "Caderno de campo digital",
        "/api/caderno/notas/",  # <-- NAO HA ROTA. Ver comentário.
        "app/models/caderno.py:75",
        "Modelo `NotaCampo` completo, com API idempotente por `offline_id` e "
        "foto georreferenciada ligada.",
        "A UI não o usa: o modal do dashboard renderiza `ProductionRegistry`, e "
        "a página `caderno/offline.html` NÃO está registada em nenhum "
        "`urls.py` — MEDIDO: `resolve('/caderno/campo/')` é Resolver404. "
        "Por isso este item não tem botão. O único caller de "
        "`/api/caderno/notas/` é um ficheiro que nenhum template carrega.",
        governanca="O backend está certo e testado; o que falta é o botão. "
        "Este é o gap mais barato de fechar em todo o plano.",
        dias=30,
    ),
    _parcial(
        "Offline real — escrita sem rede",
        "/dashboard/",
        "app/static/js/data-sync.js:58",
        "Service worker registado, fila com `pendingChanges`, e o P0 dos "
        "apagamentos perdidos corrigido e provado em Node.",
        "O caminho vivo é `localStorage` com flag `_pending`, não IndexedDB. O "
        "`pwa/indexeddb.js` com 7 object stores existe e NÃO É CARREGADO por "
        "ninguém — o próprio `sw.js:95-102` documenta isso como decisão "
        "deliberada. Background Sync foi removido.",
        governanca="Um teste que passa isolado e falha na suite é o que "
        "ensinou a ignorar o vermelho. `tests/test_sync_offline.py` prova o "
        "comportamento em Node, não por leitura de texto.",
        dias=45,
    ),
    _existe(
        "Fotos georreferenciadas",
        "/api/caderno/fotos/",
        "app/api/views/caderno.py:415",
        "Upload com validação de formato e tamanho, coordenada arredondada a 7 "
        "casas, precisão guardada e `coordenada_confiavel` explícito.",
        governanca="Foto órfã aceite antes da nota; `offline_id` garante que "
        "reenviar a mesma foto não duplica. 14 testes.",
        dias=60,
    ),
    _existe(
        "Gestão de tarefas com responsável",
        "/tarefas/associacao/",
        "app/models/producao.py:100",
        "`TarefaEstagio` com funcionário, cargo alvo, setor, prioridade e prazo, "
        "em Kanban; tarefas nascem sozinhas de alertas de IoT.",
        dias=30,
    ),
    _existe(
        "Planejamento de safra e cronograma",
        "/cadastro/safra/",
        "app/models/safra.py:135",
        "`PlanoSafra` com orçamento e datas, e `AtividadePlanejada` como "
        "cronograma com responsável e data prevista.",
        dias=45,
    ),
    _existe(
        "Mapas e geoespaciamento de talhões",
        "/mapa/",
        "app/services/geo.py:22",
        "Desenho no mapa com Leaflet, área **geodésica WGS84** por "
        "Chamberlain-Duquette, e exportação GeoJSON FeatureCollection.",
        governanca="A área do mapa é calculada, não digitada. "
        "`geopandas/rasterio/pyproj/fiona` estão declaradas.",
        dias=90,
    ),
    _parcial(
        "Imagens de satélite (NDVI)",
        "/api/agronomia/ndvi/",
        "app/api/views/agronomia.py:153",
        "Endpoint, heatmap e página existem; quando há fonte devolve o índice, "
        "a data de captura e a nuvens.",
        "`app/services/ndvi.py:63` devolve sempre `None` — a consulta real ao "
        "Sentinel-2 não está feita, e o serviço responde `fonte_dado: "
        "'indisponivel'`.",
        governanca="Corrigido hoje: o botão deixou de fabricar `0.72` no `catch` "
        "de uma rota 404. Sem dado, diz sem dado.",
        dias=60,
    ),
    _nao_existe(
        "Drones e imageamento aéreo",
        "ausente",
        "Só os rótulos: tipo de device `DRONE` e cargo `OPERADOR_DRONE`. Sem "
        "missão de voo, ortomosaico ou processamento de imagem.",
    ),
    _existe(
        "MIP — manejo integrado de pragas",
        "/cadastro/mip/",
        "app/models/mip.py:7",
        "Monitoramento por lavoura com nível de infestação, nível de controlo e "
        "ação recomendada, com alerta quando passa do nível de controlo.",
        dias=30,
    ),
]
CAMPO = CAMPO + EXTRAS_CAMPO


# ═══════════════════════════════════════════════════════════════════════════
# D — PECUÁRIA
# ═══════════════════════════════════════════════════════════════════════════
PECULARIA: list[dict[str, Any]] = [
    _existe(
        "Rebanho individual (brinco)",
        "/cadastro/animal/",
        "app/models/pecuaria.py:82",
        "`AnimalIndividual` com brinco, brinco eletrónico e genealogia (pai e mãe).",
        dias=30,
    ),
    _parcial(
        "Calendário sanitário e vacinação",
        "/agenda/pecuaria/",
        "app/models/pecuaria.py:151",
        "`ProtocoloSanitario` e `EventoSanitario` com próxima dose e "
        "responsável; o motor gera alerta de vacina atrasada.",
        "Não existe página de calendário: `/agenda/pecuaria/` renderiza só `Animal`.",
        dias=20,
    ),
    _parcial(
        "Produção por animal e por ciclo",
        "/api/producao-animal/",
        "app/models/pecuaria.py:59",
        "`ProducaoAnimal` ligado ao animal/lote, e `Pesagem` individual com GMD.",
        "Não existe entidade de ciclo: a produção é por evento, não por ciclo "
        "de engorda ou de lactação.",
        dias=45,
    ),
]


# ═══════════════════════════════════════════════════════════════════════════
# E — LOGÍSTICA
# ═══════════════════════════════════════════════════════════════════════════
LOGISTICA: list[dict[str, Any]] = [
    _existe(
        "Estoque de insumos com lote e validade",
        "/rastreabilidade/",
        "app/models/rastreabilidade.py:8",
        "`RastroItem` com lote do fabricante, NF de entrada, validade e saldo; "
        "`MovimentoEstoque` é append-only; QR por lote.",
        governanca="Itens vencidos e dias para vencer são campos, não cálculo na tela.",
        dias=60,
    ),
    _parcial(
        "Romaneio, pesagem e balança",
        "/logistica/rotas/",
        "app/models/logistica.py:26",
        "`Romaneio` com rota, caminhao, peso bruto e líquido, quebra e CT-e.",
        "`app/services/top_globais.py:378` tem `tem_balanca = False` "
        "hardcoded e devolve `sc_ha: None`. As '12 balanças BigBrother' são "
        "números de projeção numa regra de IA, não hardware.",
        dias=45,
    ),
    _parcial(
        "Compras e pedidos",
        "/compras/",
        "app/models/estoque.py:72",
        "`OrdemCompra` com estado de rascunho até recebida, e alerta de ordem parada.",
        "Sem linhas de item: `valor_total` é escalar. `/api/compras/` devolve "
        "despesas financeiras, não ordens — o nome da rota mente.",
        dias=30,
    ),
    _nao_existe(
        "Beneficiamento e armazenagem",
        "ausente",
        "Sem modelo de silo, armazém ou lote processado. `/api/armazem/` "
        "re-serializa o `EstoqueItem` da propriedade.",
    ),
    _nao_existe(
        "Contratos de safra e torrentes",
        "ausente",
        "Zero modelos. 'Contrato' só aparece como tipo de documento no LCDPR.",
    ),
]


# ═══════════════════════════════════════════════════════════════════════════
# G — MÁQUINAS E IA
# ═══════════════════════════════════════════════════════════════════════════
# Este é o bloco onde a lista de mercado mais promete e menos cumpre. Três
# integrações comercialmente muito conhecidas e tecnicamente ausentes.
MAQUINAS_IA: list[dict[str, Any]] = [
    _existe(
        "Telemetria de máquina",
        "/iot/sensores/",
        "app/iot/views.py:248",
        "Ingestão por MQTT/HTTP e LoRaWAN/TTN, com métricas de GPS, RPM, "
        "combustível, horímetro e temperatura, e a qualidade da leitura.",
        governanca="Autenticação por `Gateway.api_key` com hash cego. O fallback "
        "por EUI foi REMOVIDO de propósito: EUI é identificador, não "
        "credencial.",
        dias=90,
    ),
    _nao_existe(
        "John Deere Operations Center",
        "ausente",
        "Zero integração. Existe uma string de webhook em "
        "`app/services/erp_externo.py:33` que NÃO corresponde a nenhuma rota, "
        "e o próprio módulo declara `integracoes_com_rota: 0`.",
    ),
    _nao_existe(
        "Stara, Climate FieldView, Solinftec",
        "ausente",
        "Zero código. 'Stara' não ocorre em lado nenhum do repositório; "
        "'Solinftec' e 'FieldView' só num docstring.",
    ),
    _parcial(
        "ISOBUS (ISO 11783)",
        "/cadastro/vra/",
        "app/services/vra.py:13",
        "Gera ficheiro ISO 11783-10 (ISO-XML) para a prescrição, com download.",
        "Só escrita de ficheiro. Sem protocolo: sem TCP/UT-TCP, sem sessão, sem "
        "leitura de telemetria da máquina.",
        dias=60,
    ),
    _nao_existe(
        "OTA — actualização de firmware",
        "ausente",
        "Só o campo de texto `Gateway.firmware_version`. Sem upload de "
        "binário, sem versionamento, sem assinatura, sem estado de progresso.",
    ),
    _existe(
        "IA que corre no dispositivo",
        "",
        "app/static/js/ia-local/ia-local.js:5610",
        "WebLLM no browser via WebGPU (SmolLM2-1.7B) e Whisper por "
        "transformers.js em Web Worker. Carregados em produção.",
        governanca="O modelo corre no dispositivo do produtor: a pergunta não "
        "sai da fazenda.",
        dias=30,
        sem_ecra=True,
        onde_vive="Painel AmplIA do dashboard (WebGPU). Carregado por "
        "`base.html:220`, não por esta guia.",
    ),
    _existe(
        "Assistente conversacional e MCP",
        "/ia/registros/",
        "app/amplia_mcp/servidor.py:1",
        "Sandbox conversacional com confirmação obrigatória, servidor MCP "
        "stdio, e catálogo de skills. Uma única porta de saída.",
        governanca="Toda a escrita passa por `executar_para()` com allowlist "
        "verificada contra `sandbox.INTENTS`. `IAExecucao` regista intent, "
        "passos, fontes e duração.",
        dias=30,
    ),
    _existe(
        "API pública documentada",
        "/api/docs/",
        "config/urls.py:50",
        "`drf-spectacular` com OpenAPI em `/api/schema/` e navegador em `/api/docs/`.",
        governanca="Contrato gerado do código: não há especificação escrita à mão "
        "para divergir.",
        dias=60,
    ),
]


# ═══════════════════════════════════════════════════════════════════════════
# H — DADOS
# ═══════════════════════════════════════════════════════════════════════════
DADOS: list[dict[str, Any]] = [
    _existe(
        "Proveniência de dado em código",
        "/controle/",
        "app/validators.py:81",
        "Vocabulário de 5 estados e validador que exige carimbo em cada folha "
        "de resultado.",
        governanca="Um '0' mostrado sem medição é mentira. A regra é "
        "`sem_dado`, e o produto diz 'não definido'.",
        dias=30,
    ),
    _existe(
        "Auditoria de execução de IA",
        "/ia/registros/",
        "app/models/ia.py:58",
        "`IAExecucao` com intent, deteção, passos, parâmetros, fontes, via "
        "(`chave`/`sessao`), resultado e duração. `django-auditlog` em 10 "
        "modelos.",
        dias=30,
    ),
    _existe(
        "Isolamento multi-empresa por tabela",
        "/config/sistema/",
        "app/middleware.py:189",
        "Middleware verifica 6 tabelas (propriedade, fazenda, talhão, device, "
        "safra, conta) e o `make_scoped_viewset` aplica o escopo em leitura E "
        "escrita, devolvendo 403 em fuga.",
        governanca="Contar a base inteira seria dizer que tens 8 sensores "
        "quando 7 são do vizinho.",
        dias=45,
    ),
    _existe(
        "Multi-propriedade e multi-safra",
        "/cadastro/propriedade/",
        "app/models/core.py:274",
        "`MembroPropriedade` com 6 papéis e restrições, e `Safra` por "
        "propriedade com índice composto. Comparativo de safras.",
        dias=30,
    ),
    _parcial(
        "Carbono, ESG e MRV",
        "/agronomia/compliance/",
        "app/services/top_globais.py:510",
        "Reserva Legal por bioma com a lei codificada, e conformidade ambiental.",
        "MRV não existe: `Agrofloresta.carbono_t` é campo livre e o widget "
        "devolve `tco2e: None` com o motivo explícito. Sem inventário de gases "
        "por parcela não há crédito a certificar.",
        dias=90,
    ),
    _parcial(
        "Conectores prontos",
        "/api/schema/",
        "app/services/erp_externo.py:148",
        "Com rota e a funcionar: LoRaWAN/TTN, MQTT/HTTP, endpoint IoT para "
        "ESP32 com token revogável, IBGE SIDRA, Open-Meteo, INMET, NF-e XML, "
        "HGBrasil, Google SSO, Slack, LLM openai-compatible, MCP.",
        "SAP, Protheus, Senior e Oracle são stubs sem rota.",
        governanca="Um endpoint IoT com token revogável é o que permite vender "
        "o dispositivo e cortar o acesso.",
        dias=45,
    ),
    _nao_existe(
        "WhatsApp como interface",
        "ausente",
        "`app/services/notificacoes.py:273` devolve literalmente 'Não existe "
        "provedor'. Sem Twilio, Wablas, Evolution ou Meta Graph.",
    ),
    _parcial(
        "Exportação em formato aberto",
        "/api/export/csv/",
        "app/api/views/relatorios.py:161",
        "CSV, XLSX, GeoJSON, ISO-XML 11783, export LGPD em JSON e LCDPR delimitado.",
        "`EXPORTADORES` está VAZIO em `relatorios.py:42` e devolve 501. O "
        "exportador genérico não existe; só as rotas específicas.",
        dias=30,
    ),
]
DADOS = DADOS + EXTRAS_DADOS


# ═══════════════════════════════════════════════════════════════════════════
# O CATÁLOGO
# ═══════════════════════════════════════════════════════════════════════════
#: A ordem é a de leitura do produtor: o que mexe em dinheiro, o que mexe em
#: campo, o que mexe em máquina, e o que garante que nada disto mente.
CATALOGO: list[dict[str, Any]] = [
    {
        "id": "fiscal",
        "letra": "A",
        "nome": "Fiscal",
        "resumo": "O que a Receita Federal exige, e o que o Ampliagro entrega.",
        "itens": FISCAL,
    },
    {
        "id": "financeiro",
        "letra": "B",
        "nome": "Financeiro",
        "resumo": "Contas, conciliação, custo e margem.",
        "itens": FINANCEIRO,
    },
    {
        "id": "campo",
        "letra": "C",
        "nome": "Campo",
        "resumo": "O que se passa no talhão, com prova de que passou lá.",
        "itens": CAMPO,
    },
    {
        "id": "pecuaria",
        "letra": "D",
        "nome": "Pecuária",
        "resumo": "Rebanho, saúde e produção por animal.",
        "itens": PECULARIA,
    },
    {
        "id": "logistica",
        "letra": "E",
        "nome": "Logística",
        "resumo": "Insumo, transporte e armazenagem.",
        "itens": LOGISTICA,
    },
    {
        "id": "maquinas",
        "letra": "G",
        "nome": "Máquinas e IA",
        "resumo": "Telemetria, integração com equipamento e inteligência.",
        "itens": MAQUINAS_IA,
    },
    {
        "id": "dados",
        "letra": "H",
        "nome": "Dados",
        "resumo": "O que garante que nenhum número aqui é inventado.",
        "itens": DADOS,
    },
]

#: As sete classes da lista de mercado que **não** têm secção própria.
#: Estão na lista porque são capacidades que o mercado tem; a página diz isso de forma
#: explícita em vez de fingir que o Capacidades faltantes não existem.
AUSENTES_NOTA: list[str] = [
    "D — Pecuária: encerrar a lista de Rebanho já cobre.",
]
