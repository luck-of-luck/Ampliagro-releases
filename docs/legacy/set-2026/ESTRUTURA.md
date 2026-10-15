# Estrutura — Ampliagro

> **Raiz:** `C:\Trabalho\Projetos\Ativos\Ampliagro`
> **Migrado de:** `C:\Users\lucas\Documents\Projetos_geral\Ampliagro` (2026-08-30)
> **Reorganização raiz:** 2026-09-06 — arquivos soltos movidos para pastas
> **Grafo principal:** Codebase-Memory MCP (projeto `C-Trabalho-Projetos-Ativos-Ampliagro`)
> **Grafo secundário:** `graphify-out/` (`graphify update .`)

## Árvore (nível 1 — resumida)

```
C:\Trabalho\Projetos\Ativos\Ampliagro\
├── docs\                # Documentação curada (tudo que estava solto na raiz)
│   ├── ANALISE_CRITICA.md           # Análise crítica arquitetura (movido raiz 2026-09-06)
│   ├── PLANO_BUILDS.md              # Roadmap 10 builds (movido raiz 2026-09-06)
│   ├── PLANO_RASTREABILIDADE_CUSTOS.md # Plano rastreabilidade (movido raiz 2026-09-06)
│   ├── PLANO_SUPER_DADOS_REAIS.md   # Dados reais IBGE/AgroDoc (movido raiz 2026-09-06)
│   ├── PLANO_RESOLUCAO.md           # Plano JOSIF/FEBRACE — 100 dores (já em docs, duplex removido)
│   ├── CURIOSIDADES.md              # Auditoria 139 culturas (já em docs, duplex removido)
│   ├── DORES.md                     # 100 dores mapeadas
│   ├── ESTRUTURA.md                 # ← este arquivo — mapa da reorganização
│   ├── AGENTS.md                    # ponte para as regras (canônicas na raiz)
│   ├── COMOESTAOHTML                # Snapshot HTML dashboard
│   └── README.md                    # Índice docs/
├── product-data\        # Dados curados (era raiz solto)
│   ├── animal_aquatico_real_map.json # Mapa animal/aquático IBGE (movido raiz 2026-09-06)
│   └── vegetal_real_map.json         # Mapa vegetal IBGE (movido raiz 2026-09-06)
├── media\recordings\    # Gravações / vídeos debug (era raiz solto)
│   ├── 20260901_230211.mp4           # Vídeo dashboard (movido raiz 2026-09-06)
│   └── 20260906_135000.mp4           # Vídeo flicker meta (movido raiz 2026-09-06)
├── logs\                # Logs locais (.gitignore: logs/*)
│   ├── README.md
│   ├── varredura-proativa.log    # saida da varredura (rotacao por tamanho)
│   ├── alertas-diario.log
│   ├── runserver-dev.log, runserver-dev.err.log
│   └── server_log.txt, srv.log, srv.err, test-run.log, ...
├── scratch\             # Rascunhos descartaveis (.gitignore: /scratch/)
│   ├── test.js, test_0.js, test_1.js
│   ├── kpi_script.js
│   └── fetch_icons.py, provar_*.py, medir_*.py, ...
├── tools\               # Automação — movido da raiz (2026-08-30)
│   ├── bat\                     # .bat (Windows Batch)
│   │   ├── demo.bat             # DEMO JOSIF — seed + runserver + abre /demo/
│   │   ├── runserver_dev.bat    # DEBUG=True runserver (--porta/--reload)
│   │   ├── setup_tarefa_proativo.bat  # agenda a varredura no Agendador do Windows
│   │   ├── rodar_varrer_proativo.bat  # roda a varredura sem agendar
│   │   ├── alertas_diario.bat   # agenda os alertas diários
│   │   ├── git-auto.bat         # git add/commit/push auto
│   │   └── git-push.bat         # commit + push com deteccao de branch
│   ├── ps1\                     # PowerShell
│   │   └── git-auto.ps1
│   └── README.md
├── scripts\             # Python utilitários (movidos da raiz + existentes)
│   ├── _check.py, _check2.py, _find_unbalanced.py, _fix_all.py  # ← movidos da raiz em 2026-08-30
│   ├── check_*.py, find_*.py, test_*.py, get_*.py                # já existentes
│   └── README.md
├── app\                 # Django — models, views, api, templates, static
│   ├── models\          # 29 módulos de domínio (pecuaria, maquinario, ...)
│   ├── views\           # views HTML (dashboard, guias, financeiro, ...)
│   ├── api\views\       # 26 DRF viewsets
│   ├── static\js\       # theme-system.js, spa.js, widget-*.js, pwa/sw.js
│   ├── templates\       # index.html, base.html, partials/
│   └── ...
├── graphify-out\        # grafo secundário (`graphify update .`)
├── config\              # settings/{base,dev,prod,test}.py, urls, wsgi, asgi, celery
├── tests\               # e2e (Playwright) + unit + js + fixtures + sondas
├── docs\                # BUILD_0..BUILD_3_4 (não há pasta builds\)
├── backups\             # zips + dumps (já organizado)
├── grafos\              # atalhos para o Codebase-Memory UI e graphify
├── demo.bat (stub)      # call "%~dp0tools\bat\demo.bat" %*
└── ...                  # .git, .venv, node_modules, db.sqlite3, etc.
```

## O que mudou

### 2026-09-06 — Reorganização de arquivos soltos na raiz

| Antes (raiz solto) | Depois | Motivo |
|---|---|---|
| `ANALISE_CRITICA.md` | `docs/ANALISE_CRITICA.md` | Planejamento → docs |
| `PLANO_BUILDS.md` | `docs/PLANO_BUILDS.md` | Planejamento → docs |
| `PLANO_RASTREABILIDADE_CUSTOS.md` | `docs/PLANO_RASTREABILIDADE_CUSTOS.md` | Planejamento → docs |
| `PLANO_SUPER_DADOS_REAIS.md` | `docs/PLANO_SUPER_DADOS_REAIS.md` | Planejamento → docs |
| `PLANO_RESOLUCAO.md` (dup) | `docs/PLANO_RESOLUCAO.md` (mantido) + duplex rm | Deduplicado |
| `CURIOSIDADES.md` (dup) | `docs/CURIOSIDADES.md` (mantido) + duplex rm | Deduplicado |
| `DORES.md` (dup) | `docs/DORES.md` (mantido) + duplex rm | Deduplicado |
| `animal_aquatico_real_map.json` | `product-data/animal_aquatico_real_map.json` | Dados → product-data |
| `vegetal_real_map.json` | `product-data/vegetal_real_map.json` | Dados → product-data |
| `20260901_230211.mp4` | `media/recordings/20260901_230211.mp4` | Mídia → media/recordings |
| `20260906_135000.mp4` | `media/recordings/20260906_135000.mp4` | Mídia → media/recordings |
| `kanban_out.txt` | `logs/kanban_out.txt` | Log → logs (já não existe) |
| `console` | `logs/console` (.gitignore) | Log → logs (já não existe) |
| `server_log.txt` | `logs/server_log.txt` (.gitignore) | Log → logs |
| `scratch_0.js` | `scratch/scratch_0.js` | Rascunho → scratch (já não existe) |
| `scratch_1.js` | `scratch/scratch_1.js` | Rascunho → scratch (já não existe) |
| `test.js` | `scratch/test.js` | Rascunho → scratch |
| `implementation_plan.md` | `docs/implementation_plan.md` (.gitignore) | Planejamento → docs |
| seed `open("*.json","w")` | `Path("product-data/*.json")` + espelho raiz compat | Código atualizado |
| `media/` | `.gitignore: media/` (já) | Mídia ignorada, mas tracking preservado via `git mv` |
| `product-data/` | `.gitignore: product-data/` (já) | Dados locais, tracking preservado via `git mv` |

> **Resultado:** todos os `.md` de planejamento em `docs/`, mapas em `product-data/`, vídeos em `media/recordings/`, logs em `logs/`, rascunhos em `scratch\`. Scripts `seed_*_real.py` atualizados para escrever em `product-data/` com fallback raiz.

### 2026-08-30 — Migração inicial

| Antes (raiz) | Depois | Motivo |
|---|---|---|
| `CURIOSIDADES.md` | `docs/CURIOSIDADES.md` | Documentação curada |
| `PLANO_RESOLUCAO.md` | `docs/PLANO_RESOLUCAO.md` | Documentação curada |
| `COMOESTAOHTML` | `docs/COMOESTAOHTML` | Snapshot |
| `AGENTS.md` | `AGENTS.md` (raiz) + `docs/AGENTS.md` | Regras na raiz; docs/ é ponte |
| `demo.bat` | `tools/bat/demo.bat` + stub raiz | Automação |
| `git-auto.bat` | `tools/bat/git-auto.bat` | Automação |
| `git-push.bat` | `tools/bat/git-push.bat` | Automação |
| `runserver_dev.bat` | `tools/bat/runserver_dev.bat` | Automação |
| `git-auto.ps1` | `tools/ps1/git-auto.ps1` | Automação |
| `_check.py` etc. | `scripts/_check.py` etc. | Python utilitários |
| `C:\Users\lucas\Documents\Projetos_geral\Ampliagro` | `C:\Trabalho\Projetos\Ativos\Ampliagro` | Novo caminho |

## Como usar (novo caminho)

```bat
REM DEMO (recomendado)
tools\bat\demo.bat
REM ou stub compatível
.\demo.bat

REM Git
tools\bat\git-auto.bat "feat: ..."
tools\ps1\git-auto.ps1 -Message "fix: ..."

REM Dev
tools\bat\runserver_dev.bat
python manage.py runserver 0.0.0.0:8001

REM Scripts Python
python scripts/_check.py
python scripts/check_culture_sources.py

REM Grafo
graphify query "como funciona o tema escuro?"
graphify update .
```

## Compatibilidade

* Stubs na raiz `demo.bat`, `runserver_dev.bat` e `iniciar.bat` apenas fazem `call "%~dp0tools\bat\<mesmo>.bat"` — pode remover quando todos se acostumarem.
* `.bat` em `tools\bat\` fazem `cd /d "%~dp0\..\.."` para achar `manage.py` mesmo quando executados de `tools\bat\`.
* `scripts/_*.py` usam `Path(__file__).resolve().parent.parent` para achar a raiz, então funcionam tanto via `python scripts/_check.py` quanto `cd scripts && python _check.py`.

## Próximos passos

* Remover stubs da raiz quando migração estiver consolidada
* Manter `docs/` como fonte única de documentação (evitar duplicar na raiz)
* Rodar `graphify label` com `GEMINI_API_KEY` para renomear as 33 comunidades novas
