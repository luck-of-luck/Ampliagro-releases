# AmplIA SKI - Financas (hedge B3, benchmark FBN, LCDPR/SPED, custo/ha, seguro)
name: amplia-finance
description: Skill financas para AmplIA - hedge B3 real, benchmark FBN, LCDPR/SPED, custo por ha, seguro.
version: 1.1.0
triggers: ["hedge", "benchmark", "lcdpr", "seguro chuva", "custo/ha"]
# handlers: intents que EXISTEM no registo. Conferidas a cada chamada por
# `catalogo_skis()`. Um nome aqui que nao exista e' uma tool inventada.
handlers: ["automatizar_hedge", "gerar_lcdpr", "simular_cenario", "avaliar_cenario", "lucro_talhao", "resumo_financeiro", "saldo_contas", "contas_a_pagar", "fretes_abertos", "ordens_compra", "criar_ordem_compra"]
# sem_intent: existe e nao e' chamavel. Dito como promessa nao cumprida, e nao
# como capacidade.
sem_intent:
  hedge_b3_real: "cotacao B3 real vive em app/services/cotacoes.py; o caminho publico e' automatizar_hedge."
  benchmark_fbn: "app/services/top_globais.py. Nenhuma intent expoe — resumo_financeiro e' o mais perto."
  lcdpr_sped: "existe como gerar_lcdpr, com outro nome. O nome antigo nao existe."
  seguro_chuva_param: "app/services/top_globais.py. Nenhuma intent expoe."
  simular_hedge: "existe como simular_cenario + automatizar_hedge. O nome antigo nao existe."
performance: {cache: 120, flags: ["fin.read", "campo.read"]}
