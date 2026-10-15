# Nichos 21–30 — Manejo, operações e colheita especial

## G-15 cobertura SPDP (21) — ❌ Gap

- `CoberturaSolo` {safra/talhao, especie FK, biomassa_t_ha, dessecacao {produto FK, data}, barbecho_dias}. Método Embrapa público.

## G-16 práticas + CO2e (22) — ⚠️

- `PraticaRegenerativa` {talhao, ano, pratica [plantio_direto, bioinsumo, composto, terraco], area_ha, fonte_dado}
- `EstimativaCO2e` {pratica FK, fator IPCC público, total_t}. Só `carbono_t` pontual existe.

## G-17 ILPF (23) — ⚠️

- `ArranjoILPF` {nome, lavoura FK Safra, pecuaria FK Piquete, floresta {especie, espacamento, ano_plantio, ciclo}, area_ha}. Entidades isoladas existem.

## G-18 hortifrúti (24) — ⚠️

- `ColheitaHortifruti` {safra/talhao, data, responsavel, lote FK RastroItem, calibre, categoria [extra,I,II], defeitos_pct}. Padrão CEAGESP público.

## G-19 citros HLB (25) — ❌ Gap

- `InspecaoCitros` {talhao, rua, planta_n, data, severidade 0-5, sintoma, erradicada, psilideo_qtd}. Protocolo Fundecitrus público.

## G-20 café (26) — ❌ Gap

- `BeneficiamentoCafe` {safra, via [seca, lavada], secagem {local, temp, umidade_final}, peneira, prova {nota_0_100, bebida}, lote FK, sacas}. Metodologia SCA pública.

## G-21 cacau (27) — ❌ Gap

- `FermentacaoCacau` {lote_origem FK, cocho, inicio, revolvimentos [{data}], dias, umidade_amendoa, lote_final FK}.

## G-22 cana CCT (28) — ⚠️

- `BoletimCorte` {safra/talhao, frente, variedade FK Cultivar, brix, atr, impurezas veg/min, romaneio FK existente, toneladas}. CONSECANA público.

## G-23 algodão HVI (29) — ❌ Gap

- `FardoAlgodao` {lote FK, peso, hvi {comprimento, micronaire, resistencia, uniformidade, cor}}. Padrão HVI/USDA público.

## G-24 contrato grãos (30) — ⚠️

- `ContratoGrao` {numero, comprador, tipo [disponivel, futuro, barter], cultura, sacas, preco, vencimento, status, entregas [{romaneio FK, sacas}] → baixa financeiro FK}.
