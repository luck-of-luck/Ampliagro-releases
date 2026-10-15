# Comparação Ampliagro × Referências de Mercado — Gaps Replicáveis

> **Objetivo:** mapear o que falta no Ampliagro para entregar o mesmo que os softwares de referência entregam, **excluindo** o que é propriedade da marca (APIs próprias, hardware proprietário, programas internos). Foco apenas no que é **replicável**: códigos, modelos de dados, campos de inserção, fluxos, telas, cálculos e relatórios.
> **Data:** 07/10/2026
> **Base auditada:** `app/models/*.py`, `app/api/serializers.py`, `app/api/views/*`, `app/templates/*` (Ampliagro2, branch `main`).
> **Escopo:** 50 nichos × 10 empresas listadas pelo solicitante. Este documento compara **categorias funcionais replicáveis** por nicho, não cada empresa (as 500 convergem para ~30 padrões funcionais — ver §1).

## Índice

- [1. Método e regra de escopo](#1-método-e-regra-de-escopo)
- [2. Inventário do Ampliagro](#2-inventário-do-ampliagro-o-que-já-existe)
- [3. Matriz resumo por nicho](#3-matriz-resumo-por-nicho)
- [4. Nichos 1–10 — Genética e sementes](02-nichos-01-10-sementes.md)
- [5. Nichos 11–20 — Insumos e proteção](03-nichos-11-20-insumos.md)
- [6. Nichos 21–30 — Manejo e colheita especial](04-nichos-21-30-manejo.md)
- [7. Nichos 31–40 — Gestão e mercado](05-nichos-31-40-gestao.md)
- [8. Nichos 41–50 — Dados, IoT e pecuária digital](06-nichos-41-50-dados.md)
- [9. Gaps transversais e backlog](07-gaps-transversais-backlog.md)

## 1. Método e regra de escopo

### 1.1 O que conta como replicável

| Replicável (entra) | Propriedade da marca (fora) |
|---|---|
| Modelo de dados: tabelas, campos, tipos, obrigatoriedade | API proprietária (ex.: app interno John Deere, Bayer) |
| Telas e fluxos: cadastros, wizards, kanban, checklists | Hardware proprietário (sensores, controladores, máquinas) |
| Códigos: cálculos, fórmulas, regras de negócio públicas | Algoritmos patenteados de genética/CRISPR (o gene em si) |
| Relatórios e exportações: layouts, colunas, formatos abertos | Programas de pontos, marketplaces internos |
| Protocolos abertos: MQTT, GeoJSON, OFX, LCDPR, NDVI via Sentinel (dado aberto) | Contratos e dados comerciais privados |

### 1.2 Por que agrupar por nicho

As 500 empresas convergem para padrões funcionais comuns dentro de cada nicho. Exemplo: os 10 de "Tratamento Industrial de Sementes" entregam, como **software replicável**, o mesmo padrão — ficha de lote + dose + produto + data. O que os diferencia (química própria, máquinas TSI) é marca e está fora do escopo.

### 1.3 Legenda

| Símbolo | Significado |
|---|---|
| ✅ Tem | Ampliagro já possui equivalente |
| ⚠️ Parcial | Existe base, faltam campos ou fluxo |
| ❌ Gap | Não existe; backlog proposto |
