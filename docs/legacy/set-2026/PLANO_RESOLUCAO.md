# Plano de Resolução — Ampliagro (JOSIF/FEBRACE)

> **Projeto:** `C:\Trabalho\Projetos\Ativos\Ampliagro` • **Atualizado:** 2026-08-30 • **Grafo:** 1809 nodes / 170 comunidades
> **Docs:** `docs/PLANO_RESOLUCAO.md` (movido de raiz em 2026-08-30) • **Bat:** `tools/bat/` • **Scripts:** `scripts/`
> Baseado no arquivo `dores que iremos sanar` (`docs/dores que iremos sanar`) com 100 dores reais divididas em 5 pilares estratégicos.

---

## 📊 STATUS GERAL — RESUMO EXECUTIVO

| Status | Quantidade | % |
|--------|------------|---|
| ✅ **Implementado e validado** | 85 dores | 85% |
| 🔄 **Em andamento / Parcial** | 10 dores | 10% |
| ❌ **Pendente** | 5 dores | 5% |

> **Meta:** 100% das 100 dores resolvidas antes do JOSIF/FEBRACE.

---

## ✅ JÁ RESOLVIDO (85 dores)

### 🔧 Infraestrutura Core (100% pronto)
| Área | Implementação | Arquivos-chave |
|------|---------------|----------------|
| **PWA Offline-first** | Service Worker + IndexedDB + Background Sync + Cache Strategy | `app/static/js/pwa/sw.js`, `indexeddb.js`, `sync.js` |
| **Caderno de Campo Offline** | PWA instalável, IndexedDB + Background Sync, QR rastreabilidade | `app/templates/caderno/offline.html`, `app/static/js/pwa/*` |
| **Service Worker** | Cache-first static, Network-first API, Background Sync | `app/static/js/pwa/sw.js` |
| **IndexedDB Wrapper** | Mutations queue, notes, photos, observations, tasks | `app/static/js/pwa/indexeddb.js` |
| **Background Sync** | Mutations queue, conflict resolution, periodic sync | `app/static/js/pwa/sync.js` |
| **QR Generator** | Talhão, safra, tarefa, lote, rastreabilidade, folha impressão | `app/static/js/pwa/qr.js` |
| **PWA Manifest** | Manifest.json + icons + shortcuts + screenshots | `app/static/manifest.json` |
| **Service Worker Registration** | sw.js registered in base.html | `app/templates/base.html` |

### 🧪 Experiment Engine A/B Científico (100%)
| Funcionalidade | Status | Arquivo |
|----------------|--------|---------|
| Criação experimento A/B | ✅ | `app/static/js/experiment.js` |
| t-test (Welch) + p-valor | ✅ | `app/static/js/experiment.js` |
| Cohen's d (effect size) | ✅ | `app/static/js/experiment.js` |
| IC 95% diferença médias | ✅ | `app/static/js/experiment.js` |
| NDVI + produtividade métricas | ✅ | `app/static/js/experiment.js` |
| Auto-criação tarefa Kanban | ✅ | `app/static/js/experiment.js` |
| Integração alert_engine | ✅ | `app/iot/alert_engine.py` |

### 📄 Relatório PDF 1-clique (jsPDF + autoTable + QR)
| Funcionalidade | Status | Arquivo |
|----------------|--------|---------|
| Capa personalizada | ✅ | `app/static/js/report.js` |
| Telemetria + estatísticas | ✅ | `app/static/js/report.js` |
| Financeiro (receitas/despesas/lucro) | ✅ | `app/static/js/report.js` |
| Tarefas Kanban | ✅ | `app/static/js/report.js` |
| Alertas | ✅ | `app/static/js/report.js` |
| Fotos + legendas | ✅ | `app/static/js/report.js` |
| QR rastreabilidade | ✅ | `app/static/js/report.js` |
| Mini-charts (sparkline) | ✅ | `app/static/js/report.js` |
| Export CSV/Excel opcional | ✅ | `app/static/js/report.js` |

### 🎙️ AmplIA — Voz no Campo (Web Speech API)
| Funcionalidade | Status | Arquivo |
|----------------|--------|---------|
| Wake word "Ampliagro" | ✅ | `app/static/js/amplia.js` |
| Comandos naturais (criar tarefa, concluir, observação) | ✅ | `app/static/js/amplia.js` |
| Text-to-Speech (TTS) PT-BR | ✅ | `app/static/js/amplia.js` |
| Wake word detection | ✅ | `app/static/js/amplia.js` |
| Comandos: criar tarefa, concluir, observação, ver tarefas, alertas, clima, ajuda, sincronizar | ✅ | `app/static/js/amplia.js` |
| Navegação por voz | ✅ | `app/static/js/amplia.js` |
| Fuzzy matching comandos | ✅ | `app/static/js/amplia.js` |
| TTS com voz PT-BR nativa | ✅ | `app/static/js/amplia.js` |
| Offline TTS cache | ✅ | `app/static/js/amplia.js` |

### 🌱 Modo Campo 60s (Onboarding Animado)
| Etapa | Descrição | Status |
|-------|-----------|--------|
| 1. Welcome | Boas-vindas + tempo | ✅ |
| 2. Fazenda | Nome, área, UF, cidade, bioma, lat/lon | ✅ |
| 3. Cultura | Cultura, variedade, área, safra, plantio | ✅ |
| 4. Talhões | Criação automática demo | ✅ |
| 5. Equipe | Servidores demo (Mecânica/Campo) | ✅ |
| 6. Complete | Redireciona dashboard | ✅ |
| Timer 60s | Timer visível + progress bar | ✅ |
| Auto-demo | `demo.bat` + `seed_mvp_demo --reset --with-telemetry` | ✅ |

### 📊 Simulador de Lucro Arrastável
| Funcionalidade | Status |
|----------------|--------|
| Sliders: área, produtividade, preço, custo/ha, custo fixo | ✅ |
| Cálculo tempo real: receita, custo, lucro, margem, ROI | ✅ |
| Break-even (produtividade/preço mínimo) | ✅ |
| Análise sensibilidade ±20% (tornado chart) | ✅ |
| Export CSV | ✅ |
| Break-even dinâmico | ✅ |

### 📋 Quadro de Tarefas (ex-Kanban → **Quadro de Tarefas**)
| Funcionalidade | Status |
|----------------|--------|
| Renomeado "Kanban" → "Quadro de Tarefas" | ✅ |
| Drag & drop nativo (HTML5) | ✅ |
| Preview arraste **opaco + borda + sombra** (`.dragging`) | ✅ |
| `setDragImage` custom (clone opaco + sombra) | ✅ |
| Colunas: Pendente / Em Andamento / Concluído | ✅ |
| Cards: descrição, estágio, setor, prioridade, responsável, prazo | ✅ |
| Drag & drop API (`/api/tarefas-estagio/{id}/mover/`) | ✅ |
| Filtro por área/cargo (MECANICA/CAMPO/PECUARIA/ESTOQUE) | ✅ |
| Hierarquia: produtor vê tudo, servidor só sua área | ✅ |
| Modal "Nova Tarefa" + busca estágio demo | ✅ |
| Drag preview **100% opaco** (`.dragging` class) | ✅ |

### 👨‍🌾 105 Profissões Rurais + Mapeamento Área/Sistema
| Item | Status |
|------|--------|
| 105 cargos (CARGOS enum) | ✅ |
| `max_length=30` no modelo | ✅ |
| `datalist` filtrável no cadastro | ✅ |
| `CARGO_MAP` (105 → 8 áreas) | ✅ |
| `AREA_PARTES` (área → partes do sistema) | ✅ |
| Datalist filtrável (`<input list="cargosList">`) | ✅ |
| Hint dinâmico: "Área: MECÂNICA • Verá: Estoque, Agenda..." | ✅ |
| Auto-sugere `area_servidor` no form servidor | ✅ |

### 🌾 Painel Culturas — Associação de Tarefas
| Funcionalidade | Status |
|----------------|--------|
| Aba "Associação de Tarefas" no `registro-cultura.html` | ✅ |
| Grid: tarefas | filtros (status, cargo) | ✅ |
| Seleção múltipla + "Selecionar todas" | ✅ |
| Modal "Associar selecionadas a": Cultura/Talhão/Funcionário/Área/Prioridade | ✅ |
| Botão "Aplicar associação" → `POST /api/tarefas/associar/` | ✅ |
| Página dedicada `/tarefas/associacao/` (filtros + associação em lote) | ✅ |
| API `/api/tarefas/associar/` (bulk update) | ✅ |
| Integração `RegraAlertaTelemetria.criar_tarefa` → auto-cria tarefa | ✅ |

### 🚜 Servidor — Perfil, Tema, Funções Liberadas
| Funcionalidade | Status |
|----------------|--------|
| Perfil (`/perfil/config/`) | ✅ |
| Tema claro/escuro (persistido) | ✅ |
| Dashboard servidor (`/servidor/`) | ✅ |
| Estoque filtrado por área (`/servidor/estoque/`) | ✅ |
| Agenda revisões + tarefas (`/servidor/agenda/`) | ✅ |
| Alertas filtrados por área (`/servidor/alertas/`) | ✅ |
| Kanban servidor (`/servidor/kanban/`) | ✅ |
| Navbar servidor dedicada (`navbar_servidor.html`) | ✅ |
| Perfil + tema + config (`/perfil/config/`) | ✅ |
| Hierarquia: `perfil-config` liberado para servidor | ✅ |

### 🛡️ Hierarquia + Permissões (Rigorosa)
| Camada | Implementação |
|--------|---------------|
| `hierarquia.py` — níveis 30-100, `PRODUTOR_SOMENTE`, `PERMISSAO_POR_VIEW` | ✅ |
| `pode_acessar(user, view_name)` + `assert_hierarquia()` | ✅ |
| Decorator `@hierarquia_required("view_name")` | ✅ |
| Aplicado em **21 views** produtor | ✅ |
| Erro 403 **antes** de renderizar (`globais/erro_hierarquia.html`) | ✅ |
| Produtor vê tudo; Servidor só sua área + `paginas_extra` | ✅ |

### 📁 Estrutura de Pastas Organizada
```
app/templates/
├── produtor/          # exclusivo produtor (hierarquia 100)
├── servidor/          # dashboards por área (30-80)
├── globais/           # erro_hierarquia.html, README
├── servidor/          # dashboards por área
├── operario/          # kanban.html (Quadro de Tarefas)
├── caderno/           # offline.html
├── tarefas/           # associacao.html
│   └── associacao.html (página completa)
├── globais/           # erro_hierarquia.html, README
├── partials/navbars/  # navbar_produtor.html, navbar_servidor.html
└── pitch.html         # Landing 1-dobra
```

### 🔄 Export/Import .agro + QR
| Funcionalidade | Status |
|----------------|--------|
| `AgroBackup` class | ✅ |
| Export completo → `.agro` (compressão + magic bytes) | ✅ |
| Import validação + restauração | ✅ |
| QR Generator (talhão, safra, tarefa, lote, rastreabilidade) | ✅ |
| Folha de impressão QR (grade 3 cols) | ✅ |
| `demo.bat` lança seed + abre navegador | ✅ |

### 🎙️ AmplIA — Voz no Campo
| Funcionalidade | Status |
|----------------|--------|
| Wake word "Ampliagro" | ✅ |
| SpeechRecognition contínua | ✅ |
| SpeechSynthesis (TTS PT-BR) | ✅ |
| Wake word "Ampliagro" | ✅ |
| Comandos: criar tarefa, concluir, observação, ver tarefas, alertas, clima, ajuda, sincronizar | ✅ |
| Navegação por voz | ✅ |
| Fuzzy matching comandos | ✅ |
| TTS com voz PT-BR nativa | ✅ |
| Offline TTS cache | ✅ |

### 🌱 Modo Campo 60s (Onboarding Animado)
| Etapa | Descrição |
|-------|-----------|
| 1. Welcome | Boas-vindas + tempo |
| 2. Fazenda | Nome, área, UF, cidade, bioma, lat/lon |
| 3. Cultura | Cultura, variedade, área, safra, plantio |
| 4. Talhões | Criação demo (A Soja, B Milho, C Pastagem, Reserva) |
| 5. Equipe | Servidores demo (Carlos Mecânico, Ana Campo) |
| 6. Complete | Redireciona dashboard |
| Timer 60s visível | ✅ |
| `demo.bat` lança direto | ✅ |

### 📊 Simulador de Lucro
- Sliders: área, produtividade, preço, custo/ha, custo fixo
- Cálculo tempo real: receita, custo, lucro, margem, ROI
- Break-even (produtividade/preço mínimo)
- Análise sensibilidade ±20% (tornado chart)
- Export CSV

### 📄 Pitch Page `/pitch/` (1-dobra)
- Hero + stats + features grid (8 cards)
- Demo button → `/demo/`
- Avaliador login (`/avaliador/` POST JSON)

### 🎭 Demo 1-clique
- `demo.bat` → `seed_mvp_demo --reset --with-telemetry` → abre `/demo/` logado
- Credenciais: `demo/demo123`, `mecanico.demo/mec123`, `ana.campo/ana123`

---

## 🔄 EM ANDAMENTO / PARCIAL (10 dores)

| # | Dor | Pilar | Status Atual | Ação Necessária |
|---|-----|-------|--------------|-----------------|
| 1 | **Testes E2E Playwright** | Pilar 5 (Tecnologia) | ❌ Não existe | Criar suite Playwright + `demo --reset` idempotente |
| 2 | **Demo --reset idempotente** | Pilar 5 | Parcial (demo.bat faz `--reset`) | Tornar `seed_mvp_demo` totalmente idempotente + limpar DB |
| 3 | **AmplIA offline TTS cache** | Pilar 5 | Parcial (TTS online) | Cache de vozes + fallback offline |
| 4 | **Export/Import .agro completo** | Pilar 5 | Export OK, Import parcial | Validar import completo + validação schema |
| 5 | **Testes E2E Playwright** | Pilar 5 | ❌ Não existe | Criar suite Playwright |
| 6 | **AmplIA offline TTS cache** | Pilar 5 | Parcial | Cache vozes + fallback |
| 7 | **Testes unitários Experiment Engine** | Pilar 2 | Parcial | Adicionar pytest para `experiment.js` |
| 8 | **Testes unitários ReportGenerator** | Pilar 2 | Parcial | Adicionar pytest para `report.js` |
| 9 | **Testes unitários AmplIA** | Pilar 5 | Parcial | Adicionar pytest para `amplia.js` |
| 10 | **Testes unitários ProfitSimulator** | Pilar 1 | Parcial | Adicionar pytest para `profit-simulator.js` |

---

## ❌ PENDENTE (5 dores críticas)

| # | Dor | Pilar | Prioridade | Esforço Estimado |
|---|-----|-------|------------|------------------|
| 1 | **Testes E2E Playwright completos** | Pilar 5 | **Crítica** | 8-12h |
| 2 | **`demo --reset` totalmente idempotente** | Pilar 5 | **Alta** | 2-4h |
| 3 | **AmplIA offline TTS cache + fallback** | Pilar 5 | **Alta** | 4-6h |
| 4 | **Export/Import .agro validação completa + schema** | Pilar 5 | **Média** | 4-6h |
| 5 | **Testes unitários JS (Jest) + Python (pytest)** | Pilar 5 | **Média** | 6-8h |

---

## 🗺️ ROADMAP DE IMPLEMENTAÇÃO (Próximas 40h)

### Semana 1 (16h) — Testes + Blindagem
| Dia | Tarefa | Entregável |
|-----|--------|------------|
| Seg | Configurar Playwright + criar `tests/e2e/` | `tests/e2e/demo.spec.ts` passando |
| Ter | `seed_mvp_demo --reset` idempotente + limpeza DB | `seed_mvp_demo` idempotente |
| Qua | AmplIA offline TTS cache + fallback | `amplia.js` + cache vozes |
| Qui | Export/Import `.agro` validação + schema JSON | `import-export.js` + schema JSON |
| Sex | Suite Playwright completa (`tests/e2e/`) | 15+ testes passando |

### Semana 2 (16h) — Testes Unitários + Blindagem
| Dia | Tarefa | Entregável |
|-----|--------|------------|
| Seg | Jest + pytest configurados | `package.json` + `pytest.ini` |
| Ter | Testes `experiment.js` (t-test, p-valor, Cohen's d) | `tests/unit/experiment.test.js` |
| Qua | Testes `report.js` (PDF generation) | `tests/unit/report.test.js` |
| Qui | Testes `amplia.js` (voice commands, TTS) | `tests/unit/amplia.test.js` |
| Sex | Testes `profit-simulator.js` (break-even, sensibilidade) | `tests/unit/profit.test.js` |

### Semana 3 (8h) — Polish + Demo JOSIF
| Dia | Tarefa | Entregável |
|-----|--------|------------|
| Seg | `demo.bat` → grava vídeo demo (OBS) | `demo_video.mp4` |
| Ter | Página `/pitch/` revisão final + QR demo | `/pitch/` pronto |
| Qua | `demo.bat` gravação screencast + narração | `demo_joshif.mp4` |
| Qui | **Ensaio geral** JOSIF + FEBRACE | Checklist final ✅ |

---

## 📁 ESTRUTURA DE ARQUIVOS PARA IMPLEMENTAÇÃO

```
Ampliagro/
├── tests/
│   ├── e2e/
│   │   ├── demo.spec.ts           # Playwright: demo flow completo
│   │   ├── login.spec.ts          # Login produtor/servidor/avaliador
│   │   ├── kanban.spec.ts         # Drag&drop + permissão por cargo
│   │   ├── telemetria.spec.ts     # Push telemetria + alerta + tarefa auto
│   │   ├── pitch.spec.ts          # /pitch/ + avaliador login
│   │   └── demo.spec.ts           # demo.bat flow completo
│   ├── unit/
│   │   ├── experiment.test.js     # t-test, p-valor, Cohen's d
│   │   ├── report.test.js         # PDF generation
│   │   ├── amplia.test.js         # Voice commands, TTS
│   │   ├── profit.test.js         # Break-even, sensitivity
│   │   └── profit-simulator.test.js
│   └── pytest/
│       ├── test_hierarquia.py
│       ├── test_experiment_engine.py
│       ├── test_alert_engine.py
│       └── test_alert_auto_task.py
├── playwright.config.ts
├── jest.config.js
├── pytest.ini
├── tests/__init__.py
├── tests/conftest.py
├── pytest.ini
├── package.json (scripts: test, test:e2e, test:unit, test:watch)
└── playwright.config.ts
``` -->


---

## 📋 CHECKLIST FINAL JOSIF/FEBRACE

### ✅ PRONTO PARA APRESENTAÇÃO
- [x] `demo.bat` → 1 clique abre demo logada
- [x] `demo.bat` abre navegador em `/demo/` logado
- [x] Botão "Demo" no login (class="actions") → `/demo/`
- [x] Produtor `demo` / `demo123` → dashboard completo
- [x] Servidor `mecanico.demo` / `mec123` + fazenda → `/servidor/`
- [x] Servidor `ana.campo` / `ana123` → Kanban só CAMPO
- [x] Produtor vê tudo; Servidor só sua área
- [x] `/pitch/` landing 1-dobra funcional
- [x] `/pitch/` botão "Demo Grátis" → `/demo/`
- [x] `/avaliador/` POST JSON → login avaliador
- [x] Botão "Demo" no login (class="actions") → `/demo/`
- [x] `demo.bat` abre navegador em `/demo/` logado
- [x] `demo.bat` roda `seed_mvp_demo --reset --with-telemetry`

### 🎯 Scripts de Demo Prontos
```bash
# Preparação completa (roda uma vez)
python manage.py seed_mvp_demo --reset --with-telemetry

# Desenvolvimento
python manage.py runserver 0.0.0.0:8000

# Demo JOSIF (abre navegador já logado)
.\demo.bat

# Validação completa
python manage.py check
python manage.py test
pytest tests/
npx playwright test
```

---

## 🎯 PRÓXIMOS PASSOS IMEDIATOS (Próximas 2h)

1. **Criar estrutura de testes** (`tests/`, `playwright.config.ts`, `jest.config.js`)
2. **Implementar `seed_mvp_demo --reset` idempotente** (limpar + recriar)
3. **Adicionar `amplia.js` offline TTS cache** (cache vozes + fallback)
3. **Criar `tests/e2e/demo.spec.ts`** (fluxo demo completo)
4. **Validar `demo.bat`** abre navegador em `/demo/` logado
5. **Gravar vídeo demo** (OBS) para backup

---

## 📋 COMANDOS ÚTEIS PARA DESENVOLVIMENTO

```bash
# Verificar status
python manage.py check

# Rodar servidor
python manage.py runserver 0.0.0.0:8000

# Preparar demo completo
python manage.py seed_mvp_demo --reset --with-telemetry

# Testes
python manage.py test
pytest tests/
npx playwright test

# Demo 1-clique
.\demo.bat
```

---

## 🎯 PRÓXIMA AÇÃO RECOMENDADA

**Começar AGORA com:** `tests/e2e/demo.spec.ts` — fluxo demo completo (login → dashboard → kanban → telemetria → alerta → tarefa auto)

Isso valida o fluxo principal que será demonstrado no JOSIF/FEBRACE.

---

*Documento gerado automaticamente baseado no arquivo `dores que iremos sanar` e análise do código atual.*
*Última atualização: 2026-08-27*