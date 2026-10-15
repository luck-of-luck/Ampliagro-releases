# Nichos 31–40 — Gestão, mercado e comercialização

## G-25 orçado × realizado (31) — ⚠️

Aegro/Siagri comparam planejado × executado por talhão.

- `OrcamentoOperacao` {plano FK, operacao, insumo FK|null, qtd/custo previsto, qtd/custo real, desvio_pct}
- Tela semáforo por talhão. Base (`PlanoSafra` + `CustoProducao`) existe.

## G-26 fiscal residual (32) — ✅ quase

LCDPR/DRE/NF-e/OFX prontos. Falta: NIRF/CAR por propriedade + PDF Livro Caixa oficial.

## G-27 crédito/CPR/barter (33, 49) — ❌ Gap

- `OperacaoCredito` {tipo [cpr_fisica, cpr_financeira, custeio, barter], contraparte, valor, garantias, vencimentos [{data, valor, liquidada}], lastro {cultura, sacas}, liquidacao FK financeiro}. Lei 8.929/1994 pública. Scoring fintech é marca (fora).

## G-28 seguro (34) — ❌ Gap

- `ApoliceSeguro` {seguradora, cultura, area_ha, cobertura_pct, premio, vigencia, vistoria}
- `Sinistro` {apolice FK, data, causa [seca, granizo, geada], perda_pct, indenizacao, status}. PROAGRO/PSR públicos.

## G-29 cooperativa (35) — ❌ Gap

- `ContaCooperado` {cooperativa, matricula, movimentos [{data, tipo [entrega, fixacao, deducao, sobra], produto, qtd, valor}]}.

## G-30 lote venda/leilão (36) — ❌ Gap

- `LoteVenda` {produto, qtd, fotos, lance_inicial, incremento, encerramento, arrematante, status}. Cadastro + workflow (pregão é serviço).

## G-31 visita técnica (37) — ⚠️

- `VisitaTecnica` {talhao, data, tecnico + CREA, diagnostico, recomendacoes [{descricao, prazo, cumprida}], retorno, assinatura}. `Receituario`+ART existem.

## G-32 treinamento NR (38) — ❌ Gap

- `Treinamento` {curso, norma [NR31, NR33, defensivos], funcionario FK, data, validade, certificado, alerta reciclagem}. NRs públicas.

## G-33 checklist certificação (39) — ⚠️

- `NormaCertificacao` {nome [GlobalGAP, Organico, RTRS], versao} + `ChecklistAuditoria` {itens [{requisito, conforme, evidencia, acao, prazo}]}. Base QR/ledger/fotos existe. Selo é serviço (fora).

## G-34 inventário GEE (40) — ❌ Gap

- `InventarioGEE` {ano, diesel_l, energia_kwh, N_kg, rebanho_categorias, tco2e (fatores IPCC públicos)}.
