# G-02 — LoteSemente + TSI (camada semente sobre RastroItem)

## Por que existe

`RastroItem` (`rastreabilidade.py:8-86`) já é lote rastreável com QR/saldo/vencimento, mas não distingue semente (germinação/vigor/pureza) nem tratamento TSI (produto/dose). Colocar 12 campos de semente dentro de `RastroItem` polui o ledger de todos os insumos — a doutrina manda estender por 1-1, não por coluna solta.

## Cirurgia

1. Model `LoteSemente` em `app/models/rastreabilidade.py`:
   - `rastro` OneToOne `RastroItem` CASCADE related `lote_semente` (morre com o lote; sem lote não há laudo)
   - `cultivar` FK `Cultivar` (G-01) SET_NULL null/blank — laudo sobrevive sem catálogo? Não: SET_NULL porque o lote físico continua existindo (razão talhão, `tests_cascata_cultura.py:176`)
   - `categoria` choices [S1, S2, C1, C2, basica, fiscalizada, null]
   - `germinacao_pct`, `vigor_pct`, `pureza_pct` Decimal(5,2, null) — null, nunca 0 (0% germinação é afirmação, não ausência)
   - `peneira` CharField(20, blank)
   - `tsi_produto` CharField(150, blank), `tsi_dose_ml_100kg` Decimal(8,2, null), `tsi_funcao` choices [fungicida, inseticida, nematicida, inoculante, micronutriente, null], `tsi_prestador` CharField(150, blank), `tsi_data` Date(null)
   - `revestimento` choices [nu, grafite, polimero, pellet, null]
   - `fonte_dado` default `declarado` (laudo digitado é afirmação; `medido` só com integração laboratorial futura)
   - Index `[cultivar]`
2. `RastroItemSerializer`: aninhar `lote_semente` read_only (não writable nested — criação em 2 POSTs, evita escrita fantasma).
3. `LoteSementeViewSet` com `get_queryset` por `rastro__propriedade__user` (padrão `rastreabilidade.py:62-65`) + `with_saldo` não se aplica (saldo mora no Rastro).
4. Teste: laudo nulo passa; germinação 0.00 passa (é afirmação válida); sem `rastro` recusa.

## O que NÃO entra

- Sem validação "germinação mínima por espécie" (tabela oficial sem fonte semeada = meta inventada).
- Sem upload de laudo PDF (é superfície; Fase 1 proíbe).

## Critério de saída

- POST Rastro + POST LoteSemente vincula; DELETE Rastro leva LoteSemente; saldo/QR inalterados.
