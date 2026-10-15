# Nichos 1–10 — Genética, sementes e biotecnologia

> Escopo: o gene/evento/química é marca (fora). Replicável: ficha cultivar, lote semente, ensaio.

## Padrão G-01: ficha de cultivar (nichos 1, 2, 5, 6, 9)

Campos que GDM/TMG/DonMario/Brasmax/Nidera/Pioneer/KWS exibem:

- nome_comercial, obtentor, espécie (FK Cultura)
- evento_biotecnologico (texto/null: RR2 PRO, Intacta, Convencional)
- tecnica_obtencao: [convencional, transgenia, edicao_genica, hibridacao]
- grupo_maturacao (decimal), ciclo_dias_min/max, habito [determinado, indeterminado]
- densidade_mil_plantas_ha, tolerancia_seca/salinidade [alta, media, baixa]
- resistencias (lista), janela_plantio por UF (liga ZARC)

Status Ampliagro: ⚠️ Parcial. `Cultura` é espécie, não cultivar. Sem entidade cultivar.
Gap: criar `Cultivar` FK→Cultura + FK opcional em `Safra`. 1 model + serializer + `cadastro-cultivar.html`.

## Padrão G-02: lote semente + TSI (nichos 4, 7)

Extensão de `RastroItem`:

- cultivar (FK G-01), categoria [S1,S2,C1,C2,fiscalizada]
- germinacao_pct, vigor_pct, pureza_pct, peneira
- tratamento_tsi: produto, dose_ml_100kg, funcao [fungicida, inseticida, nematicida], prestador, data
- revestimento [nu, grafite, polimero, pellet]

Status: ⚠️ Parcial. `RastroItem` tem lote/NF/validade/QR/saldo. Falta camada semente.
Gap: model `LoteSemente` 1-1→RastroItem. Laudo MAPA e dose mL/100kg são públicos.

## Padrão G-03: ensaio cultivares (nicho 3) — ❌ Gap

- Ensaio {safra, talhao, data_plantio, testemunha FK Cultivar}
- Faixas {cultivar, repeticao, area_m2, produtividade_sc_ha, umidade_pct} → ranking vs testemunha
- `Experimento` A/B existe, sem repetição/testemunha. Método Embrapa público.

## Padrão G-04: viveiro/muda clonal (nicho 8) — ❌ Gap

- `Viveiro` {nome, tipo [in_vitro, estaquia, enxertia], protocolo}
- `LoteMuda` {origem_matriz, qtd, repique, aclimatacao, expedicao, talhao_destino FK, sobrevivencia_pct}

## G-05 alerta safrinha (nicho 9) — ⚠️ só código

- Regra: `limite = fim_janela_ZARC - ciclo_dias`; alerta se `hoje+ciclo > fim_janela`. Campos existem.

## G-06 mix forrageiro (nicho 10) — ⚠️

- `MixPastagem` {piquete FK, especies [{cultura, pct}], taxa_kg_ha}. `Piquete` existe.
