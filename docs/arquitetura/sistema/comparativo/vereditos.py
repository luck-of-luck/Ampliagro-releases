"""VEREDITOS — cada celula do Ampliagro adjudicada a mao, com a linha lida.

Este ficheiro existe porque `medir_ampliagro.py` deu **43/50** e esse numero
nao pode ser publicado. Quatro exemplos do que a medicao enganada encontrou:

| coluna | onde bateu | o que e' a linha |
|---|---|---|
| F14 Orcado x realizado | `app/amplia_mcp/servidor.py:24` | docstring do servidor MCP |
| F15 Benchmark de mercado | `app/api/views/amplia_palco.py:173` | docstring sobre machine learning |
| M02 John Deere | `app/ia/sandbox.py:260` | `'maquina': 'De que maquina? (ex.: trator John Deere)'` |
| M04 ISOBUS | `app/services/top_globais.py:23` | texto a descrever widgets **clonados** |

Nenhum dos quatro tem relacao com a capacidade que a coluna promete. E' a
§A.0 do `docs/sistema/9.md` outra vez — e desta vez em codigo de producao,
que e' onde um falso positivo e mais perigoso.

OS TRES ESTADOS
===============
  C  CONFIRMADO   a linha e' codigo que produz a capacidade
  E  ENFRAQUECIDO a capability existe mas a evidencia e' um campo, uma
                   constante ou um nome de view — nao uma implementacao
  N  NAO TEM      nenhum achado em codigo de execucao
"""

#: cid -> (estado, evidencia lida, nota curta)
VEREDITOS: dict[str, tuple[str, str, str]] = {
    # ---- A. Fiscal
    "F01": ("C", "app/api/views/financial.py:446", "chama o gerador e devolve o .txt"),
    "F02": (
        "C",
        "app/services/nfe.py:169",
        "valida a chave de acesso de 44 digitos e deduplica a nota — 83 testes de import passam",
    ),
    "F03": ("N", "", "zero ocorrencias"),
    "F04": (
        "N",
        "",
        "DESCARTADO de E para N apos leitura. `pkcs12`, `dsig` e `xmldsig` dao ZERO ocorrencias em toda a app; `.pfx` aparece so na docstring que explica que a SEFAZ nao e' chamada. A linha que eu apontava provava o contrario do que a coluna pede",
    ),
    "F05": ("N", "", "zero ocorrencias — sem IBS/CBS"),
    "F06": (
        "E",
        "app/ia/ingestao/bridge.py:84",
        'DESCIDO de C para E: transporta o NCM do XML da NF-e para o rascunho (`"ncm": _txt(prod, "NCM")`), mas NAO classifica fiscalmente. A coluna pede NCM/TIPI — trazer o codigo e\' outra coisa',
    ),
    "F07": (
        "E",
        "app/api/views/custos.py:87",
        "calcula receitas vs despesas, mas por SAFRA e categoria — a coluna pede 'por cultura'. E' um DRE simplificado, honesto, incompleto",
    ),
    "F08": (
        "C",
        "app/models/core.py:143",
        "FECHADO 2026-10-05. Era 'NAO TEM': o registo 0010 do LCDPR era escrito "
        "com a CONSTANTE FORMA_APURACAO_LIVRO_CAIXA e nao havia de onde "
        "escolher — o proprio comentario dizia que trocar aquilo e' decisao de "
        "configuracao, e na pratica era uma decisao que ninguem tomava. Um "
        "produtor no regime dos 20% (art. 5o da Lei 8.023/1990) gerava um "
        "ficheiro que diz a Receita que ele apurou pelo Livro Caixa: "
        "BEM FORMADO E ERRADO. Agora `Propriedade.forma_apuracao` existe, o "
        "gerador le-o, e um valor fora do dominio cai para 1 em vez de passar. "
        "Migration 0072; 6 testes em tests/test_forma_apuracao.py. "
        "Contrapartida provada por fetch: Lucro Rural",
    ),
    # ---- B. Financeiro
    "F10": (
        "C",
        "app/models/contas.py:69",
        "FECHADO 2026-10-05. Era 'NAO TEM': `h_contas_a_pagar` somava "
        "`LancamentoFinanceiro` com `pago=False` — um extrato de despesas, sem "
        "vencimento, sem contraparte, sem estado. Agora ha `ContaAPagar` e "
        "`ContaAReceber` com `vencimento`, `fornecedor`, `estado` e "
        "`fonte_dado`, e `liquidar()` escreve o LancamentoFinanceiro que o "
        "Q100 do LCDPR le. 25 testes em `app/ia/tests_contas.py`. "
        "Contrapartida provada por fetch: Aegro, Sage X3, SYSPRO",
    ),
    # `F11` reposto 2026-10-05. Comi esta entrada duas vezes a editar por
    # indice; o que fica e' a ancora que eu tinha verificado antes
    # (`projetar_fluxo_caixa` a ser CHAMADO, nao importado).
    "F11": (
        "C",
        "app/api/views/financial.py:393",
        "chama projetar_fluxo_caixa(prop_id, meses). A linha 30 era o IMPORT; "
        "o guard de ancora apanhou e eu mudei",
    ),
    "F12": (
        "C",
        "app/api/views/custos.py:432",
        "le o OFX/CSV e devolve transacoes com sugestao de match. A ancora "
        "anterior era a DOCSTRING da accao (abre na 426, prosa ate 431): o "
        "guard `test_ancora_tem_codigo` apanhou, porque descrever uma "
        "capacidade nao a implementa. A ancora e' agora a primeira linha do "
        "corpo executavel, que le o ficheiro; o parser OFX/CSV vem na 452, "
        "de `app/services/extrato`. Manter a nota alinhada com a ancora "
        "importa: um leitor que siga a nota vai procurar a linha errada e "
        "encontra a mesma prosa que o guard proibe.",
    ),
    "F13": (
        "E",
        "app/admin.py:99",
        'DESCIDO de C para E. `"custo_por_ha",` e um nome de campo numa listagem do admin — e a propria definicao de E neste ficheiro (linha 20-21): a evidencia e um campo. A capacidade existe; a prova e fraca',
    ),
    "F14": (
        "C",
        "app/api/views/custos.py:162",
        "SUBIU de N para C. `def budget_vs_realizado` compara PREVISTO vs "
        "REALIZADO por safra: o previsto e' o agregado de `CustoProducao` "
        "(`custos.py:181`, Sum de insumos/maquina/mao_de_obra/embalagem/"
        "frete/impostos/outros/custo_total/receita) e o realizado e' a soma de "
        "`LancamentoDetalhado` mapeada por `categoria_detalhada` "
        "(`custos.py:193` a `:241`); devolve budget, realizado, diferenca e "
        "percentual campo a campo (`custos.py:275`). Scoping de tenant nos dois "
        "lados: `get_queryset` filtra `safra__propriedade__user` "
        "(`custos.py:42`) e o realizado filtra "
        "`lancamento__propriedade__user | _propriedade__user = request.user` "
        "(`custos.py:194-196`). CORRECAO AO VEREDICTO ANTERIOR: era 'N' com a "
        "nota 'FALSO POSITIVO: era docstring do servidor MCP'. Esse rotulo "
        "estava errado nos dois sentidos — era um FALSO NEGATIVO, nao um falso "
        "positivo: a capacidade existe e executa. E a confusao teve origem "
        "justa no sitio que este ficheiro condena: a docstring desta mesma "
        "accao (`:163-166`) descreve a comparacao palavra por palavra, e "
        "descrever uma capacidade nao a implementa; a implementacao esta DEPOIS "
        "da docstring. A medicao viu a prosa e parou ai. Por isso a ancora e' a "
        "linha do `def` e nao a da docstring — e o mesmo raziao que fez o guard "
        "`test_ancora_tem_codigo` obrigar o F12 a reancorar.",
    ),
    "F15": ("N", "", "FALSO POSITIVO: era docstring sobre ML"),
    "F16": ("N", "", "zero ocorrencias"),
    # MEDIDO 2026-10-05 (agente 7): F17 saiu de `N` para `C`, com a ancora
    # **dentro do corpo executavel** — que e' o que `test_ancora_tem_codigo`
    # exige. Antes apontava para uma docstring sobre IRPF, e a propria folha
    # registava isso: "FALSO POSITIVO: era docstring sobre IRPF".
    #
    # O que `projecao_ir.py` faz, e porque e' isto e nao uma conta de IR:
    #
    #   projecao **mes a mes**, nao resultado do exercicio. Um ERP anual diz
    #   "fechou com lucro de 240 mil"; este diz "esse lucro entra em marco,
    #   e em marco o IR e' 18 mil". E' a pergunta que a folha atribui a um
    #   concorrente — "vale comprar o trator agora?" — e que nenhum nichado
    #   responde, porque todos fecham o ano.
    #
    # **Duas leis, e uma delas estava em falta.**
    #
    #   Lei 9.430/1996 + 11.482/2007   a tabela progressiva anual
    #   Lei 15.191/2025                deducao por dependente, desconto
    #                                  simplificado
    #   Lei 15.270/2025                a TABELA DE REDUCAO, que zera o
    #                                  imposto ate R$ 5.000 por mes
    #
    # Escrevi a tabela de memoria e **nenhum dos cinco valores estava
    # certo**. Um teste com numero de referencia acusou a diferenca, e a
    # leitura da fonte oficial resolveu. Os numeros estao em
    # `projecao_ir.FAIXAS_IR`, com a fonte escrita ao lado.
    #
    # A Lei 15.270 e' a que decide o produtor pequeno: sem ela, a projecao
    # diria que um produtor que factura 40 mil por ano paga 1.270,09 de IR
    # quando, a 3.333 por mes, **nao paga nada**. Nao e erro de centavos: e'
    # a resposta errada a pergunta.
    "F17": (
        "C",
        "app/services/projecao_ir.py:365",
        "projecao de IR mes a mes sobre os lancamentos registados, com a "
        "tabela progressiva oficial e a tabela de reducao da Lei 15.270/2025. "
        "Responde a 'vale comprar o trator agora?', que nenhum ERP anual "
        "responde. Sem dedutibilidade declarada NAO projecta: devolve "
        "bloqueios, porque o onus e' dedutivel em 35% e assumir 100% "
        "subestima o imposto. A ancora esta' no corpo de `calcular_ir`.",
    ),
    "F18": (
        "N",
        "",
        "DESCARTADO de E para N. `class FolhaPagamento`, `provento`, `salario_base`, `fgts` e `liquido_salarial`: ZERO. O 'FOLHA_PAGAMENTO' que eu apontava e' uma CATEGORIA de custo noutro metodo — classificar a despesa nao e' calcular a folha. TOTVS e Senior tem o modulo; o Ampliagro nao",
    ),
    # ---- C. Campo
    "O01": (
        "C",
        "app/api/views/caderno.py:350",
        "modelo `NotaCampo` importado e servido",
    ),
    "O02": (
        "C",
        "tests/test_fila_offline_aceita_escrita.py:60",
        "a ancora passou a ser o TESTE, nao a linha: escrita sem rede e' comportamento, e comportamento prova-se executando. A linha anterior (amplia.js:329) era um toast de 'esta offline'",
    ),
    "O03": (
        "C",
        "tests/test_caderno_fotos.py:105",
        "a linha anterior (serializers.py:969) era uma linha EM BRANCO. As fotos com coordenadas tem teste que passa",
    ),
    "O04": ("C", "app/signals.py:186", "sinal em `AtividadePlanejada`"),
    "O05": (
        "C",
        "app/api/urls.py:36",
        "REANCORADO. A linha 36 e o nome do viewset dentro do router.register; a rota e real e a capacidade existe, mas o nome sozinho seria E",
    ),
    "O06": ("C", "app/api/serializers.py:1023", "campo `geojson`"),
    "O07": (
        "C",
        "app/api/views/agronomia.py:210",
        "chama o NDVIService e, sem medicao real, devolve 'indisponivel' em vez de uma cor inventada. O dict de permissoes (hierarquia.py:121) nao provava nada",
    ),
    "O08": (
        "N",
        "",
        "DESCARTADO de E para N. 'drone' so aparece como tipo de maquina num dicionario de mapeamento. O imagery e' Sentinel-2 via NDVIService, que e' satelite, nao aereo. Nao ha captura de imagem aerea",
    ),
    "O09": ("C", "app/urls.py:211", "rota `cadastro/mip/`"),
    # ---- D. Pecuaria
    "P01": (
        "C",
        "app/ia/intents3.py:558",
        "registrar_vacina e contar_animais operam por brinco, em 11 ficheiros. A linha anterior era uma docstring que usava 'brinco' de exemplo",
    ),
    "P02": ("C", "app/ia/intents2.py:166", "`h_calendario_sanitario` e' um handler"),
    "P03": (
        "E",
        "app/admin.py:19",
        "DESCIDO de C para E. `ProducaoAnimal,` e um registo no admin, nao codigo de execucao. O modelo existe; falta evidencia de que a capacidade e servida",
    ),
    # ---- E. Logistica
    "L01": (
        "E",
        "app/admin.py:56",
        'DESCIDO de C para E. `"data_validade",` e um nome de campo. A coluna pede lote E validade — e a definicao de E (linha 20-21). Para subir a C precisa de ancorar no signal que baixa estoque ou na view que calcula o alerta',
    ),
    "L02": (
        "C",
        "app/api/urls.py:34",
        "REANCORADO. `PesagemViewSet,` no router.register — a rota existe. Mesma ressalva do O05: o nome sozinho seria E",
    ),
    "L03": (
        "C",
        "app/ia/intents3.py:591",
        "REANCORADO. O veredicto anterior estava errado por DUAS razoes, nao "
        "so por estar ancorado numa rota. (1) A ancora `app/urls.py:153` aponta "
        'para `path("financeiro/", spa_view, ...)` — a rota de FINANCEIRO, nao '
        "a de compras; a de compras e' a `:154`. A nota dizia 'rota `/compras/`' "
        "sobre uma linha que nao e' a de compras: le o nome e ia ao sitio "
        "errado. (2) Mesmo a `:154` certa so prova que existe um ecra SPA. "
        "A capacidade tem logica de compra a serio, e a ancora passa a ser o "
        "handler que a executa: `def h_criar_ordem_compra` (`:591`), registado "
        "como handler em `:1236`, valida fornecedor e valor total (`:597-602`), "
        "resolve a propriedade do utilizador (`:594`) e cria `OrdemCompra` em "
        "status RASCUNHO (`:603`). O `OrdemCompra` tem ciclo de vida de 5 "
        "estados (`models/estoque.py:72` — RASCUNHO/APROVADA/PEDIDA/RECEBIDA/"
        "CANCELADA), viewset com scoping de tenant "
        "(`api/views/faltantes.py:120`), rota em `api/urls.py:230` e alerta de "
        "ordem parada em `management/commands/gerar_alertas.py:471`. Dois "
        "testes a exercitam: `ia/tests.py:1575` cria a ordem e verifica valor e "
        "status, `:1212` lista as ordens. Mantem-se C, mas pela logica, nao "
        "pela rota.",
    ),
    "L04": (
        "N",
        "",
        "MOTIVO CORRIGIDO: escrevi antes que a unica ocorrencia de 'beneficiamento' estava em dados de demo. FALSO. `grep` por todo o `app` mostra 2 ocorrencias, ambas em `app/models/equipe.py:56` e `:233`, como CARGO de trabalhador ('Operador de Beneficiamento') mapeado para a area ESTOQUE. `armazenagem`: ZERO ocorrencias em todo o `app`. A conclusao N mantem-se - um cargo nao e' um registo agricola - mas o motivo que eu tinha escrito estava errado, e um motivo errado e' pior do que um motivo ausente: convence quem le",
    ),
    "L05": (
        "N",
        "",
        "RECONSTRUIDO apos um acidente de edicao que comeu esta entrada. Verificado no codigo: `torrente`, `torrentes`, `safra_torrente` e `contrato_safra` dao ZERO ocorrencias em `app/` e `tests/`, fora docstrings e comentarios. O Ampliagro nao tem registo de contrato de safra. Bushel Farm tem (`grain contract`, 3x)",
    ),
    "M01": (
        "C",
        "tests/test_telemetria_zero_trust.py:35",
        "RECONSTRUIDO apos um acidente de edicao. Verificado: 170 ocorrencias de `telemetria` em codigo de execucao, `RegraAlertaTelemetria` tem 30. O teste recusa NaN e nao-numericos (zero-trust). A ancora e' o teste porque telemetria honesta e' comportamento, e comportamento prova-se executando",
    ),
    "M02": ("N", "", "FALSO POSITIVO: era 'ex.: trator John Deere' num prompt"),
    "M03": (
        "E",
        "app/management/commands/importar_csv_maquinario.py:99",
        "SUBIU de N para E: existe implementacao, mas em formato mais estreito "
        "do que a coluna pede. O que ha e' um comando de gestao que importa "
        "telemetria de maquina de CSV. A ancora `:99` nomeia os tres formatos "
        "que o importador aceita — FieldView, Operations Center e Stara — e "
        "`COLUNAS` (`:101`) mapeia os aliases de cada um para "
        "`Maquinario.horas_uso`; a escrita real esta no corpo do comando "
        "(`:329`, `:354`). SOLINFTEC: nao ha integracao, e a prova disso NAO e' "
        "'zero ocorrencias', porque nao ha zero. `solinftec`, em qualquer caixa, "
        "da 6 vezes em `app/` e nenhuma e' integracao: 2 sao docstring "
        "(`services/top_globais.py:2`, `tests_top_globais.py:1`), 1 e' comentario "
        "(`static/js/top-globais-widgets.js:2`), 2 sao o proprio catalogo de "
        "guias a declarar a capacidade ausente (`guias/catalogo.py:580` e "
        "`:583`) e 1 e' um rotulo de UI (`static/js/pagina-index.js:10858`). "
        "Nao ha cliente HTTP, OAuth nem chamada a API de nenhum fabricante — o "
        "proprio modulo escreve em `:14-17` que John Deere Operations Center, "
        "Climate FieldView e Stara 'nao partilham API nenhuma'. A nota antiga "
        "('FALSO POSITIVO: era docstring sobre widgets clonados') estava "
        "CERTA sobre o nome Solinftec — era mesmo so prosa — e ERRADA sobre a "
        "coluna, porque havia uma importacao CSV a ser ignorada. Daí E e nao C: "
        "importar um ficheiro a mao e' mais estreito do que a integracao viva "
        "que a coluna promete.",
    ),
    "M04": (
        "C",
        "app/services/vra.py:13",
        "CORRIGIDO de N para C. O veredicto anterior refutou corretamente o falso positivo (ISOBUS aparecia num item de lista de widgets CLONADOS, top_globais.py:23) — mas parou ai e declarou N. A implementacao real existe: NAMESPACE http://www.iso11783.org/schemas/task_data_v4 (:13,:19,:20) e a tag ISO11783_TaskData (:25), com ValueType=ApplicationRate. Refutar uma evidencia falsa nao prova a ausencia da capacidade",
    ),
    "M05": ("N", "", "zero ocorrencias"),
    "M07": (
        "C",
        "app/static/js/ia-local/proativo-local.js:112",
        "o motor local. A linha anterior (alerta-feed.js:21) era um comentario a dizer que esse ficheiro NAO faz inferencia",
    ),
    "M08": (
        "C",
        "app/amplia_mcp/coerencia.py:104",
        "def verificar() — corrige as perguntas de todo o catalogo MCP. "
        "A linha 99 era um `import` de TOOLS_CATALOGO dentro de outra funcao",
    ),
    "M09": (
        "E",
        "app/api/views/agronomia.py:26",
        'DESCIDO de C para E. `@api_view(["GET"])` e um decorator — prova que existe uma rota, nao que a API seja "documentada", que e o que a coluna pede. Ha OpenAPI em config/urls.py; a ancora aponta para o decorator, nao para o schema',
    ),
    # ---- H. Dados
    "G01": (
        "C",
        "app/validators.py:17",
        "NOTA CORRIGIDA. `Cinco estados` era certo para validators.py:17-23 (medido, medido_com_ressalva, suspect, sem_dado, declarado) mas NAO para app/ia/proveniencia.py:80-85, que tem SEIS — acrescenta `simulado` (:84). Ha duas enumeracoes divergentes de proveniencia no mesmo codigo: validators.py NAO tem `simulado`. Alinhar as duas e tarefa aberta",
    ),
    "G02": ("C", "app/models/ia.py:58", "`class IAExecucao` com 13 campos"),
    "G03": (
        "E",
        "app/middleware.py:136",
        "CORRIGIDO E DESCIDO DE C PARA E. DOIS erros. (1) A ancora :41 aponta para `ServidorRevogadoMiddleware` — que revoga servidor, outra capacidade. O isolamento multi-empresa POR TABELA e `TenantIsolationMiddleware`, classe em :136. (2) Desce para E porque a evidencia e a propria implementacao e ela esta incompleta: :201 le request.GET ou request.POST e NUNCA request.body — nao inspeciona corpo JSON, que e o formato real da API DRF. Alem disso o `except Exception` final deixa a requisicao passar sem verificacao. Existe e nao fecha",
    ),
    "G04": (
        "C",
        "app/api/serializers.py:109",
        "campo `user` e' HiddenField(CurrentUserDefault): a guarda mais forte",
    ),
    "G05": ("N", "", "zero: sem GHG, MRV, credito, blockchain, CBAM"),
    "X02": (
        "N",
        "",
        "DESCARTADO de E para N. erp_externo.py e' um stub que no proprio codigo escreve: 'Nao ha SAP, Protheus ou JBS ligado ao Ampliagro'. A linha que eu apontava (urls.py:106) era um import de `weather_integracao` — clima e' integrado, ERP nao",
    ),
    "X06": (
        "E",
        "app/services/whatsapp.py:1",
        "SUBIU de N para E em 2026-10-05 (agente 9). Ha cliente da Meta Cloud API com template aprovado, e 18 testes. NAO e' C: a coluna pede INTERFACE, e o que existe e' alerta de SAIDA — o sistema fala, o produtor ouve. Falta `receber()`: webhook, parser de intencoes e resposta. A Aegro faz esta com a Aegrozap; aqui so' o outro sentido da conversa.",
    ),
    "X07": (
        "C",
        "app/api/views/relatorios.py:200",
        "exporta CSV e XLSX (openpyxl), mais LCDPR, GlobalGAP e ISO XML. urls.py:75 era um import",
    ),
}
