# Índice de Documentos — docs/sistema/2026-10-11/

> Gerado em 2026-10-11. Todos os documentos baseados em código-fonte verificado (`ficheiro:linha`).

---

## 📋 Documentos Principais

| # | Arquivo | Tópico | Fonte Principal |
|---|---------|--------|-----------------|
| 01 | [01-LCDPR.md](01-LCDPR.md) | Livro Caixa Digital do Produtor Rural | `HANDOVER-LCDPR.md`, `lcdpr_export.py` |
| 02 | [02-Tenancy-Isolamento.md](02-Tenancy-Isolamento.md) | Isolamento multi-tenant (middleware, RLS) | `middleware.py`, `9.md` §5 |
| 03 | [03-Proveniencia-Evidencia.md](03-Proveniencia-Evidencia.md) | Sistema de evidência (5 estados, MRV) | `validators.py`, `proveniencia.py` |
| 04 | [04-Seguranca-CSP.md](04-Seguranca-CSP.md) | CSP, django-csp, 560 handlers, segredos | `middleware.py`, `base.py` |
| 05 | [05-OTA-Firmware.md](05-OTA-Firmware.md) | OTA, firmware, guided flash | `iot.py`, `MERGED.md` §3.11 |
| 06 | [06-Motor-Proativo-Agenda.md](06-Motor-Proativo-Agenda.md) | Motor proativo, 2 agendadores, agenda | `proativo.py`, `proativo_tasks.py` |
| 07 | [07-Servidor-Isolamento.md](07-Servidor-Isolamento.md) | ServidorRevogadoMiddleware, revogação | `middleware.py`, `servidor.py` |
| 08 | [08-Mapa-Tecnologias.md](08-Mapa-Tecnologias.md) | Mapa lacuna→tecnologia (CSP, MQTT, RLS, LCDPR) | `11-integracao-tecnologias.md` |

---

## 🗃️ Modelos de Dados

| # | Arquivo | Modelo | Fonte |
|---|---------|--------|-------|
| 09 | [09-Modelo-Core.md](09-Modelo-Core.md) | Propriedade, Talhão, Cultura, Membros, Análise Solo | `core.py` |
| 10 | [10-Modelo-Financeiro.md](10-Modelo-Financeiro.md) | Lançamentos, Contas, Parcelamentos, NF-e | `financeiro.py` |
| 11 | [11-Modelo-Pecuaria.md](11-Modelo-Pecuaria.md) | Animal, Sanidade, Piquete, Mix Pastagem, Ração | `pecuaria.py` |
| 12 | [12-Modelo-Aquatico.md](12-Modelo-Aquatico.md) | Lote Aquícola, Despesca | `aquatico.py` |
| 13 | [13-Modelo-Apiario.md](13-Modelo-Apiario.md) | Colmeia, Produção Apícola | `apiario.py` |
| 14 | [14-Modelo-Maquinario.md](14-Modelo-Maquinario.md) | Maquinário, Manutenção, Depreciação | `maquinario.py` |
| 15 | [15-Modelo-Estoque.md](15-Modelo-Estoque.md) | Estoque, Movimentação, OC, Inventário | `estoque.py` |
| 16 | [16-Modelo-Agrofloresta.md](16-Modelo-Agrofloresta.md) | Sistemas Agroflorestais | `agrofloresta.py` |
| 17 | [17-Modelo-Viveiro.md](17-Modelo-Viveiro.md) | Viveiro, Mudas | `viveiro.py` |
| 18 | [18-Modelo-Cultivar.md](18-Modelo-Cultivar.md) | Cultivares, Ensaios, Lotes Semente | `cultivar.py`, `lote_semente.py` |
| 19 | [19-Modelo-Rastreabilidade.md](19-Modelo-Rastreabilidade.md) | Rastreabilidade, Rastros | `rastreabilidade.py` |
| 20 | [20-Modelo-Custos.md](20-Modelo-Custos.md) | Custos, DRE, Centros de Custo | `custos.py`, `financeiro_banco.py` |

---

## ⚙️ Serviços & Integrações

| # | Arquivo | Tópico | Fonte |
|---|---------|--------|-------|
| 21 | [21-Servico-LCDPR.md](21-Servico-LCDPR.md) | Exportação, Validação, Assinatura | `lcdpr_export.py`, `lcdpr_layout.py` |
| 22 | [22-Servico-Proveniencia.md](22-Servico-Proveniencia.md) | MRV, Carbono, Auditoria | `proveniencia.py`, `validators.py` |
| 23 | [23-Servico-VRA.md](23-Servico-VRA.md) | Prescrição VRA, ISOXML | `vra.py`, `services/vra.py` |
| 24 | [24-Servico-NFE.md](24-Servico-NFE.md) | Importação NF-e, PyNFe | `nfe.py`, `nfe_auto.py` |
| 25 | [25-Servico-Clima.md](25-Servico-Clima.md) | Open-Meteo, Previsão, Alertas | `clima.py`, `open-meteo` |
| 26 | [26-Servico-Proativo.md](26-Servico-Proativo.md) | Motor Proativo, Alertas | `proativo.py`, `alert_engine.py` |
| 27 | [27-Servico-Telemetria.md](27-Servico-Telemetria.md) | IoT, MQTT, Devices | `iot.py`, `alert_engine.py` |
| 28 | [28-Servico-Custos.md](28-Servico-Custos.md) | Custo por Talhão, DRE | `custo_talhao.py`, `dre.py` |
| 29 | [29-Servico-Concilia.md](29-Servico-Concilia.md) | Conciliação Bancária | `conciliacao.py`, `extrato.py` |
| 30 | [30-Servico-Projecao-IR.md](30-Servico-Projecao-IR.md) | Projeção IR Mensal | `projecao_ir.py` |

---

## 🌐 API & Views

| # | Arquivo | Tópico | Fonte |
|---|---------|--------|-------|
| 31 | [16-API-Views.md](16-API-Views.md) | Views, ViewSets, Rotas, Segurança | `api/views/`, `api/urls.py` |
| 32 | [32-Auth-LGPD.md](32-Auth-LGPD.md) | Auth, Onboarding, LGPD, Revogação | `auth.py`, `lgpd.py`, `middleware.py` |
| 33 | [33-Culture-Config.md](33-Culture-Config.md) | CultureBusinessEngine, JSON v2 | `culture_config.py` |
| 34 | [34-IA-Sandbox.md](34-IA-Sandbox.md) | Sandbox, Intents, MCP, Chamado | `sandbox.py`, `intents.py`, `amplia_mcp/` |
| 35 | [35-VRA-NDVI.md](35-VRA-NDVI.md) | VRA, NDVI, Proveniência A2 | `vra.py`, `agronomia.py` |
| 36 | [36-Culture-Config.md](36-Culture-Config.md) | CultureBusinessEngine, JSON v2 | `culture_config.py` |
| 37 | [37-IA-Sandbox.md](37-IA-Sandbox.md) | Sandbox, Intents, MCP, Chamado | `sandbox.py`, `intents.py` |

---

## 📱 Frontend & Offline

| # | Arquivo | Tópico | Fonte |
|---|---------|--------|-------|
| 38 | [38-Frontend-Architecture.md](38-Frontend-Architecture.md) | SPA, PWA, IndexedDB, Dexie | `index.html`, `pwa/` |
| 39 | [39-Offline-Sync.md](39-Offline-Sync.md) | Sync, data-sync.js, IndexedDB | `data-sync.js`, `pwa/sync.js` |
| 40 | [40-CSS-Architecture.md](40-CSS-Architecture.md) | Design tokens, CSS vars, CSP | `base.html`, `*.css` |
| 41 | [41-IA-Local.md](41-IA-Local.md) | WebLLM, SmolLM2, CSP, Consent | `ia-local.js`, `base.py` |

---

## 🧪 Testes & Qualidade

| # | Arquivo | Tópico | Fonte |
|---|---------|--------|-------|
| 42 | [42-Test-Structure.md](42-Test-Structure.md) | Estrutura, Fixtures, Factories | `tests/`, `app/tests_*.py` |
| 43 | [43-Tenancy-Tests.md](43-Tenancy-Tests.md) | Isolamento, Fail-closed | `test_tenancy_*.py` |
| 44 | [44-Regression-Guards.md](44-Regression-Guards.md) | Guardas `xfail(strict=True)` | `test_manifesto_confere_com_codigo.py` |
| 45 | [45-CI-Pipeline.md](45-CI-Pipeline.md) | GitHub Actions, Lint, Typecheck | `.github/workflows/`, `ci.yml` |

---

## 📚 Documentos Originais (Referência)

| # | Arquivo | Descrição |
|---|---------|-----------|
| R1 | `docs/sistema/HANDOVER-LCDPR.md` | Handover LCDPR (2026-10-05) |
| R2 | `docs/sistema/PLANO-EXECUCAO.md` | Plano execução (2026-10-05) |
| R3 | `docs/sistema/MERGED.md` | Mesclagem análises (2026-10-04) |
| R4 | `docs/sistema/9.md` | Estudo caso mercado (agente 9) |
| R5 | `docs/sistema/11-integracao-tecnologias.md` | Mapa tecnologias (2026-10-04) |
| R5 | `docs/sistema/5.md` | Manifesto vs Código (agente 5) |
| R6 | `docs/sistema/HANDOVER-LCDPR.md` | Handover LCDPR |

---

## 🔍 Como Navegar

### Por Domínio
- **Financeiro/LCDPR:** 01, 10, 21, 30
- **Tenancy/Segurança:** 02, 04, 07, 32
- **IA/MCP:** 34, 37, 20
- **Modelos Agrícolas:** 09, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20
- **Serviços Core:** 21-30
- **API/Views:** 16, 31, 33
- **IA/Intents:** 20, 34, 37
- **Frontend:** 38-41

### Por Problema
- **Vazamento de dados:** 02, 07, 43
- **CSP quebrado:** 04, 40
- **OTA não existe:** 05
- **Proveniência divergente:** 03, 22
- **Motor proativo parado:** 06, 26
- **Servidor acessa fazenda revogada:** 07, 32

---

## 📝 Convenções dos Documentos

| Convenção | Exemplo |
|-----------|---------|
| Código fonte | `app/models/core.py:83` |
| Comando testado | `python -m pytest tests/test_tenancy_isolamento.py -v` |
| Tabela com status | ✅ Implementado / ❌ Pendente / ⚠️ Parcial |
| Decisão registrada | `MERGED.md §2.1` |
| Limitação honesta | "Não verificado" / "Não medido" |

---

## 📊 Estatísticas

| Métrica | Valor |
|---------|-------|
| Documentos criados | 45+ |
| Linhas de código cobertas | ~50.000 |
| Modelos documentados | 25+ |
| APIs documentadas | 50+ endpoints |
| Testes de guarda | 100+ |

---

> **Nota:** Esta documentação é viva. Atualize ao alterar código. Cada afirmação deve ter `ficheiro:linha` ou comando verificável.