# Gaps transversais, backlog e exclusões

## T — transversais (valem p/ todos os nichos)

| ID | Gap | Situação | Replicação |
|---|---|---|---|
| T-01 | Importação CSV/XLSX (estoque, animais, aplicações) | ❌ só NF-e XML e OFX | Importador com mapeamento + fonte_dado=declarado |
| T-02 | Assinatura simples (visita, entrega) | ❌ | Canvas→PNG + nome + data (sem certificadora) |
| T-03 | Compartilhar com agrônomo | ⚠️ `MembroPropriedade` existe | Convite link + papel consultor leitura |
| T-04 | PDF fechamento safra 1-clique | ⚠️ template existe | Layout: área, produção, custo/ha, margem |
| T-05 | WhatsApp/SMS além push | ⚠️ canais no model, sem driver | Gateway genérico (BSP é contrato, fora) |
| T-06 | Multi-idioma PT/EN/ES | ❌ | Django i18n |
| T-07 | Completude por tela | ⚠️ `faltantes.py` existe | Barra usando `faltantes` |
| T-08 | Timeline única da safra | ❌ | Query agregada ordenada (só leitura) |

## Backlog priorizado (valor ÷ esforço)

### P0 — fecha negócio

| ID | Entrega | Base | Esforço |
|---|---|---|---|
| G-25 | Orçado × realizado por operação | PlanoSafra+CustoProducao | M |
| G-35 | Comparativo safra × safra | Safra+Custo | P (front) |
| G-01 | Cultivar | Cultura | P |
| G-31 | Visita técnica | Receituario | P |
| G-24 | Contrato grãos | Romaneio+Financeiro | M |
| G-09 | Carência/EPI/MAPA + bloqueio | Aplicacao+Safra | P |
| G-42 | Reprodução + GMD + giro | Animal+Pesagem+Piquete | M |
| T-01 | Importador CSV | serializers | M |

### P1 — diferencia no campo

G-02 (semente+TSI), G-07 (adubação+NC), G-08 (calda), G-10 (armadilhas), G-11 (irrigação FAO-56), G-13 (colheita+umidade), G-39 (NDVI→VRA), G-38 (graus-dia), G-33 (checklist), G-27 (crédito), G-28 (seguro), G-40 (jornada), G-05 (safrinha, só código).

### P2 — nichos especiais

G-03, G-04, G-06, G-12, G-14, G-15, G-16, G-17, G-18, G-19, G-20, G-21, G-22, G-23, G-26, G-29, G-30, G-32, G-34, G-36, G-37, G-41, G-43. P3: T-02 a T-08.

## O que NÃO replicar (marca)

1. Genes/eventos, química de formulações — só ficha/dose públicas.
2. Hardware (sensores, RTK, drones, secadores) — só dados.
3. APIs/apps proprietários (Drive, JDLink, painéis fabricante, fintechs).
4. Pontos/marketplace/scoring interno.
5. Selos certificadores (selo é serviço; checklist é replicável).
6. Blockchain permissionada proprietária — hash local cobre.
7. IA proprietária de recomendação — FAO/Embrapa/IPCC cobrem.

## Fontes

- Código Ampliagro lido em 07/10/2026 (`app/models/*.py`, serializers, views, templates).
- Fetches 07/10/2026: Aegro (orçamento/estoque/offline/NF-e), AgriWebb (reprodução/nutrição/pastagem), FieldView (mapas, prescrição, PDF/CSV, compartilhar).
- Demais nichos pelo padrão funcional público (MAPA/RFB/MTE, Embrapa/FAO-56/IPCC, Fundecitrus/SCA/HVI/CONSECANA, GeoJSON/MQTT/OFX). Sem copiar implementação proprietária. Não se afirma auditoria do fonte fechado dos 500 produtos.
