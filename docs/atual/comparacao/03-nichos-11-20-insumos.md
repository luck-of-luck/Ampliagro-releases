# Nichos 11–20 — Insumos, nutrição e proteção

> Padrão comum: recomendação → prescrição → aplicação → avaliação. Ampliagro tem aplicação/prescrição; falta recomendação calculada e ficha operacional.

## G-07 recomendação adubação + calagem (nichos 11–12) — ⚠️

- `RecomendacaoAdubacao` {analise_solo FK, cultivar, produtividade_esperada, N/P2O5/K2O kg/ha, NC t/ha, fonte_tabela, ART}
- `NC = (V2-V1)×CTC/100` — fórmula pública IAC/Embrapa. Base (`AnaliseSolo` completa + `AplicacaoInsumo`) existe.

## G-08 ficha de calda (nicho 14) — ❌ Gap

- `FichaCalda` {aplicacao FK, volume_l_ha, ph_agua, ordem_mistura [{produto, ordem}], adjuvante {produto, dose_pct}, condicoes {hora, temp, vento}} — pode puxar da `EstacaoMeteo`.
- Biológico (nicho 13): estender `Insumo` com cepa + classe [inoculante, biofungicida, bioinseticida].

## G-09 defensivo compliant (nicho 15) — ⚠️

- `ProdutoDefensivo` extends Insumo: registro_mapa (público AGROFIT), classe_tox, carencia_dias, epi_lista, dose_bula min/max.
- Regra: bloquear colheita antes de aplicacao+carencia. `AplicacaoInsumo` + `Receituario` existem.

## G-10 MIP por armadilha (nicho 16) — ⚠️

- `Armadilha` {talhao, tipo [feromonio, luminosa], lat/lon} + `ContagemArmadilha` {data, praga, qtd} → curva + NDE.
- `MonitoramentoPraga` existe sem armadilha/série.

## G-11 plano irrigação (nicho 17) — ⚠️

- `PlanoIrrigacao` {talhao, sistema [pivo, gotejo], Kc_estadios, lamina_mm, turno_dias, balanco {chuva ETo deficit}} — FAO-56 público. IoT/clima existem.

## G-12 missão drone (nicho 18) — ⚠️

- `MissaoDrone` {talhao polígono, device FK DRONE, altura_m, faixa_m, vazao_l_ha, piloto + registro ANAC, aplicacao FK gerada}.
- `Device` DRONE + geometria existem.

## G-13 romaneio colheita (nicho 19) — ⚠️

- `RomaneioColheita` {safra, talhao, maquina FK, operador FK, peso_bruto, umidade_pct, impureza_pct, liquido calculado, perda_kg_ha, destino}. Desconto umidade: tabela CONAB pública.

## G-14 armazenagem (nicho 20) — ❌ Gap

- `UnidadeArmazenagem` {nome, tipo [silo, secador], capacidade_t}
- `MovimentoArmazenagem` {lote FK RastroItem, operacao [entrada, secagem, aeração, expedição], umidades, temp_massa, quebra_pct}
