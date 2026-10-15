# PLANO SUPER — DADOS REAIS PARA COMPETIR (E VENCER) GIGANTES

> **Objetivo:** oferecer o mesmo que Orbia/Climate FieldView/John Deere Operations/Cropwise/Aegro/Strider entregam — e muito mais, com dados 100% reais, controle total e automação que eles cobram caro ou não têm. **Vegetal/Animal/Aquático/Extrativista** com fontes auditáveis, sem mock.

---

## 1. QUEM SÃO OS GIGANTES E O QUE ELES FAZEM (E COBRAM)

| Gigante | Core | Fonte real | Limite que vamos quebrar |
|---|---|---|---|
| **Climate FieldView (Bayer)** | Prescrição + imagens satélite | Satélite próprio + estações | Nosso: + IBGE PAM/PPM + CEPEA/ESALQ + INMET + MapBiomas + CAR, tudo aberto e auditável, sem lock-in de máquina |
| **John Deere Ops Center** | Telemetria + NDVI | Máquina JD | Nosso: telemetria aberta (J1939/ISOBUS) + qualquer marca + sensores LoRa baratos (R$ 80) |
| **Orbia (Bayer)** | Marketplace + crédito | Parceiros | Nosso: marketplace com preço real CEPEA + estoque real + rastreio blockchain do lote |
| **Cropwise (Syngenta)** | Recomendação + clima | Modelos Syngenta | Nosso: recomendação com LLM local + clima INMET + solo via análise real do talhão |
| **Aegro/Strider** | Gestão + caderno de campo | Digitação do produtor | Nosso: caderno auto-preenchido por NF-e + sensor + satélite (zero digitação) |

**Nossa tese:** eles vendem **software + insumo amarrado**. Nós vendemos **verdade + autonomia**: dado real, fonte citada, exportável, offline-first, dono é o produtor.

---

## 2. MAPA DE DADOS REAIS — 4 RIGS

### Vegetal — 29 → 180+ culturas com SIDRA 5457
- **Hoje:** 29 validadas (Soja 2713, Milho 2712, Café 2700...)
- **Super:** mapear **todas 5457**: 40102 arroz ... 40274 uva + 40129 abacate ... 45982 açaí + temporárias/permanentes completas. Cada cultura com `ibge_codigo` + `agrodoc_produto` + `conab_preco` + `cepea_diario`.
- **Fontes:** IBGE SIDRA PAM 5457 (produção/área/rendimento/valor), CEPEA/ESALQ via AgroDoc (preço diário saca), CONAB (custo), INMET (clima), MapBiomas (uso do solo).

### Animal — 18 → 60+ com PPM 3939/3940
- **Hoje:** 18 validadas (Nelore→bovino 2670, Tilápia 32877...)
- **Super:** todas raças → espécie (Nelore/Angus→bovino, Landrace→suíno, Galinha→aves) + leite/ovos/mel + peso vivo, conversão alimentar, taxa lotação via **IBGE PPM 3939 (efetivo) + 3940 (aquicultura) + 3939/3940 valor**.
- **Fontes:** IBGE PPM, CEPEA boi gordo/bezerro/frango/suíno, SEAB/PR, leilões.

### Aquático/Extrativista — 8 → 40+
- **Hoje:** 8 (Tilápia, Tambaqui...)
- **Super:** todas espécies aquícolas 3940 + PEVS 289/291 (açaí, castanha, buriti, pequi, eucalipto, pinus) com `producao_total` + `valor`.

**Regra de ouro:** sem `ibge_codigo` + `agrodoc` + prova de `200` na SIDRA/CEPEA, **não entra**. Zero mock. Cada card mostra `fonte + UF + ano + link SIDRA`.

---

## 3. ARQUITETURA — DADOS REAIS EM TEMPO REAL, SEM TRAVAR

```
[IBGE SIDRA 5457/3939/3940] \
[CEPEA/ESALQ AgroDoc] ------> [Proxy /api/ibge-proxy + /api/agrodoc] -> [Redis 12h + DjCache 60s] -> [CultureData.getMetricsBySource(realOnly:true)]
[INMET + OpenMeteo] /                |
[MapBiomas/CAR]  /                   +--> [Fallback só se 3 fontes falharem, com tag "estimado"]
[NF-e / Sensor LoRa]                 |
                                     +--> [Widget 10x5 + Chart.js com AmpliChartStyles (linha/barras/cartao/planilha)]
```

- **Proxy com normalização NFD** já feito (`cult-graos-café → cultura-cafe`, `Nelore → bovino`), cache 12h, timeout 3s, retry 1.
- **Próximo:** fila `jobs` 06h UTC que pré-aquece `ibge_ufs` + `metrics` para as 180 culturas (evita ERR_TIMED_OUT do usuário), `webhook` para CEPEA diário.

---

## 4. CONTROLE — O QUE ELES NÃO DÃO

1. **Rastreabilidade total:** cada saca/lote com QR + hash (safra→talhão→insumo→custo→venda) — exporta `.agro` + blockchain leve (hash SHA256 do lote).
2. **Custo real por talhão:** `custo_producao_data` já com `sacas`/`kg`, agora com `custo_medio_mercado` vs `meu_custo` em tempo real.
3. **Alertas que importam:** Soja cai 5% vs CEPEA → push + WhatsApp; chuva >80% em 72h → adia plantio; rebanho taxa lotação > limite → alerta.

---

## 5. AUTOMAÇÃO — ZERO DIGITAÇÃO

- **Caderno de campo auto:** lê NF-e (XML) do insumo → cria `AplicacaoInsumo` + baixa `Estoque` + lança `Financeiro` (já temos `quick-spreadsheet`).
- **Sensor LoRa 80 reais:** `BME280 + MAX9814` já no `smat-hive-telemetria` → envia `temperatura/umidade/ruído` a cada 15min → `LeituraSensor` → widget `clima` sem digitar.
- **Satélite auto-NDVI:** `MapBiomas + Sentinel-2` via `open-meteo` já com `past_days` → NDVI por talhão sem drone.

---

## 6. ROADMAP — 4 SPRINTS DE 10 DIAS

**S10 — Vegetal Super (em curso):** 29→180 culturas SIDRA, todos `ibge_codigo` validados, mercado com 5 cards reais (valor_saca + 4 IBGE) para qualquer cultura, teste em navegador logado.

**S11 — Animal/Aquático Super + Controle:** PPM 3939/3940 para todas raças/espécies, custo por cabeça, preset `Animal Real`/`Aquático Real` com 2+ widgets cada, alerta de preço.

**S12 — Automação + Rastreabilidade:** jobs 06h, NF-e parser, QR lote, export `.agro` com hash.

**S13 — Paridade + 10x:** benchmark Feature vs FieldView/Orbia (tabela pública), landing “Migrei do FieldView em 1 clique (import .agro)”.

---

## 7. MÉTRICAS DE VITÓRIA

- **Dados:** 180+ culturas com `ibge 200` (hoje 29)
- **Latência:** `widget_data` < 400ms hit, < 3s miss (hoje já com cache 30s)
- **Conversão:** 70% dos novos usuários importam 1 preset real nas primeiras 24h
- **Prova:** cada card exibe `Fonte: IBGE SIDRA 5457/40139 Café (em grão) Total - BR 2024` com link.

---

## 8. PRÓXIMO PASSO IMEDIATO (você escolhe)

- **A:** Eu já expando `vegetal 29→180` (gero `cultures-config.json` completo + `seed_vegetal_super --apply` + teste Soja→Uva no navegador)
- **B:** Começo `jobs 06h + alertas` para as 29 já validadas
- **C:** Fecho `caderno auto NF-e + QR` para zerar digitação

Diz `A, B ou C` que eu já commito e te mostro no navegador logado.
