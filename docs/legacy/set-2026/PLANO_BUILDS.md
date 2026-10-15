# 🏗️ PLANO DE BUILDS — AMPLIAGRO MASTER PLAN

> **Projeto:** `C:\Trabalho\Projetos\Ativos\Ampliagro`
> **Criado em:** 2026-08-31
> **Baseado em:** `dores que iremos sanar` (200 defeitos + 100 critérios de comparação)
> **Formato:** Otimizado para execução autônoma por sistema multi-agente
> **Total de Builds:** 18 fases em ordem de dependência e prioridade

---

## 📋 PROTOCOLO PARA AGENTES AUTÔNOMOS

```
ANTES DE INICIAR CADA BUILD:
1. Leia ESTE ARQUIVO inteiro (PLANO_BUILDS.md)
2. Localize a build com status [PENDENTE] de menor número
3. Verifique que TODAS as builds anteriores estão [CONCLUÍDO]
4. Leia o bloco CONTEXTO INICIAL da build
5. Execute cada tarefa na ordem listada
6. Após cada tarefa, marque-a como [x] no arquivo
7. Ao concluir TODAS as tarefas da build, execute os TESTES DE VALIDAÇÃO
8. Se TODOS os testes passarem, altere o status da build para [CONCLUÍDO]
9. Atualize a ÚLTIMA LINHA do bloco com: "Concluído em: YYYY-MM-DD HH:MM por [nome-agente]"
10. Volte ao passo 2 para a próxima build

SE UMA TAREFA FALHAR:
- Registre o erro no campo NOTAS da build
- Tente corrigir até 3 vezes
- Se não conseguir, marque como [BLOQUEADO] e pule para a próxima tarefa
- NÃO marque a build como concluída se houver tarefas bloqueadas

REGRAS DE OURO:
- NUNCA quebre funcionalidade existente (rodar `python manage.py check` antes e depois)
- SEMPRE faça commits atômicos (1 commit por tarefa, mensagem descritiva)
- SEMPRE atualize este arquivo após cada tarefa concluída
- NUNCA altere código de uma build que já está [CONCLUÍDO]
```

---

## 🗺️ MAPA GERAL — ORDEM DE EXECUÇÃO

```
BUILD 00 ▸ Segurança Urgente (.env, secrets)               [CONCLUÍDO-FASE1] ~2h (Fase1 Fernet 0046 ok, Fase2 pendente 22/09/2026)
BUILD 01 ▸ Fundação Backend (PostgreSQL, settings split)    [CONCLUÍDO] ~8h (31/08/2026)
BUILD 02 ▸ Qualidade de Código (linting, formatting, CI)   [CONCLUÍDO] ~6h
BUILD 03 ▸ Arquitetura Backend (split files, cache, queue)  [PENDENTE] ~12h
BUILD 04 ▸ Fundação Frontend (bundler, TypeScript, i18n)    [PENDENTE] ~10h
BUILD 05 ▸ Testes e Validação (E2E, unit, integration)     [PENDENTE] ~12h
BUILD 06 ▸ Design System e UI/UX                            [PENDENTE] ~16h
BUILD 07 ▸ Módulo Financeiro Completo                       [PENDENTE] ~20h
BUILD 08 ▸ Agronomia e Inteligência de Campo                [PENDENTE] ~16h
BUILD 09 ▸ Pecuária Profunda                                [PENDENTE] ~14h
BUILD 10 ▸ Estoque e Supply Chain                           [PENDENTE] ~12h
BUILD 11 ▸ Frota e Maquinário                               [PENDENTE] ~10h
BUILD 12 ▸ RH e Equipe                                      [PENDENTE] ~12h
BUILD 13 ▸ IoT e Telemetria Robusta                         [PENDENTE] ~16h
BUILD 14 ▸ Performance e Escalabilidade                     [PENDENTE] ~10h
BUILD 15 ▸ Mobile e PWA Avançado                            [PENDENTE] ~10h
BUILD 16 ▸ Integrações Externas e Marketplace               [PENDENTE] ~16h
BUILD 17 ▸ Negócio, Monetização e Compliance                [PENDENTE] ~12h
                                                    TOTAL: ~204h
```

---

## 🔢 GRAFO DE DEPENDÊNCIAS

```
BUILD 00 ──┐
            ├──▶ BUILD 01 ──┐
            │                ├──▶ BUILD 02 ──┐
            │                │               ├──▶ BUILD 03 ──┐
            │                │               │               ├──▶ BUILD 05
            │                │               │               ├──▶ BUILD 07
            │                │               │               ├──▶ BUILD 10
            │                │               │               ├──▶ BUILD 12
            │                │               │               ├──▶ BUILD 13
            │                │               │               └──▶ BUILD 14
            │                │               │
            │                │               └──▶ BUILD 04 ──┐
            │                │                               ├──▶ BUILD 06
            │                │                               ├──▶ BUILD 08
            │                │                               ├──▶ BUILD 09
            │                │                               ├──▶ BUILD 11
            │                │                               ├──▶ BUILD 15
            │                │                               └──▶ BUILD 16
            │                │
            │                └──▶ BUILD 17 (pode rodar após BUILD 03)
```

---
---

# ═══════════════════════════════════════════════════════════════
# BUILD 00 — SEGURANÇA URGENTE
# ═══════════════════════════════════════════════════════════════

**Status:** [CONCLUÍDO] — Fase1 ok (Fase2: por-Propriedade + envelope)
**Prioridade:** 🔴 CRÍTICA (executar PRIMEIRO, antes de qualquer outra build)
**Esforço estimado:** ~2 horas
**Defeitos cobertos:** #146, #147, #148, #149, #155, #156, #157, #158
**Dependências:** Nenhuma (BUILD 00 é a raiz)
**Concluído em:** _não concluído_

## 🎯 OBJETIVO
Eliminar vulnerabilidades de segurança críticas que expõem o sistema a ataques imediatos. Remover credenciais do repositório, adicionar proteções básicas contra brute force e XSS, e configurar CSRF corretamente para APIs.

## 📖 CONTEXTO INICIAL
O arquivo `.env` (181 bytes) está no repositório com credenciais expostas. O sistema não tem rate limiting no login, CSP headers, política de senha, nem timeout de sessão. O CSRF token não está sendo enviado nas chamadas fetch() do JavaScript. Essas são falhas que podem ser exploradas AGORA.

## ✅ TAREFAS

### T00.01 — Remover .env do repositório e configurar .env.example
- [x] Copiar `.env` atual para backup seguro fora do repositório
- [x] Adicionar `.env` ao `.gitignore` (verificar se já está)
- [x] Remover `.env` do tracking: `git rm --cached .env`
- [x] Verificar que `.env.example` existe e contém apenas placeholders (sem valores reais)
- [x] Commit: `security: remove .env from repository tracking`
- **Arquivos:** `.gitignore`, `.env`, `.env.example`
- **Validação:** `git status` não mostra `.env` como tracked

### T00.02 — Configurar política de senha
- [x] Adicionar validators de senha em `config/settings.py`:
  ```python
  AUTH_PASSWORD_VALIDATORS = [
      {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
      {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 8}},
      {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
      {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
  ]
  ```
- **Arquivos:** `config/settings.py`
- **Validação:** `python manage.py check` passa sem erros

### T00.03 — Configurar rate limiting no login
- [ ] Instalar `pip install django-axes`
- [ ] Adicionar `axes` ao `INSTALLED_APPS`
- [x] Instalar `pip install django-axes`
- [x] Adicionar `axes` ao `INSTALLED_APPS` e `AUTHENTICATION_BACKENDS`
- [x] Configurar `AXES_FAILURE_LIMIT = 5` e lockout time (15 min)
- [x] Criar template `app/templates/globais/lockout.html`
- **Arquivos:** `config/settings.py`, `app/templates/globais/lockout.html`
- **Validação:** Falhar login 5 vezes bloqueia a tela

### T00.04 — Configurar CSRF para chamadas fetch() JavaScript
- [ ] Garantir que `CSRF_COOKIE_HTTPONLY = False` em settings.py (para JS ler o cookie)
- [ ] Adicionar `{% csrf_token %}` em `base.html` se não existir
- **Arquivos:** `app/static/js/csrf-utils.js`, `config/settings.py`, `app/templates/base.html`
- **Validação:** POSTs via JS não retornam 403 Forbidden

### T00.05 — Adicionar CSP headers básico
- [ ] Instalar `pip install django-csp`
- [ ] Adicionar `csp.middleware.CSPMiddleware` ao `MIDDLEWARE`
- [ ] Configurar CSP em settings.py:
  ```python
  CSP_DEFAULT_SRC = ("'self'",)
  CSP_SCRIPT_SRC = ("'self'", "'unsafe-inline'", "'unsafe-eval'", "cdn.jsdelivr.net", "cdnjs.cloudflare.com")
  CSP_STYLE_SRC = ("'self'", "'unsafe-inline'", "cdn.jsdelivr.net", "fonts.googleapis.com")
  CSP_FONT_SRC = ("'self'", "fonts.gstatic.com", "cdn.jsdelivr.net")
  CSP_IMG_SRC = ("'self'", "data:", "blob:", "*.tile.openstreetmap.org")
  CSP_CONNECT_SRC = ("'self'", "localhost:*", "api.open-meteo.com", "servicodados.ibge.gov.br")
  ```
- **Arquivos:** `config/settings.py`
- **Validação:** Headers CSP presentes em `curl -I http://localhost:8000/`

### T00.06 — Configurar timeout de sessão
- [ ] Adicionar em `config/settings.py`:
  ```python
  SESSION_COOKIE_AGE = 86400  # 24 horas
  SESSION_EXPIRE_AT_BROWSER_CLOSE = False
  SESSION_SAVE_EVERY_REQUEST = True  # renova a cada request
  ```
- **Arquivos:** `config/settings.py`
- **Validação:** `python manage.py check` passa

### T00.07 — Sanitizar JSONField inputs
- [ ] Criar validador em `app/validators.py`:
  ```python
  import json
  from django.core.exceptions import ValidationError

  def validate_json_safe(value):
      """Rejeita JSON com strings que parecem código malicioso."""
      serialized = json.dumps(value)
      dangerous = ['<script', 'javascript:', 'eval(', 'Function(', '__proto__']
      for pattern in dangerous:
          if pattern.lower() in serialized.lower():
              raise ValidationError(f'JSON contém conteúdo potencialmente perigoso: {pattern}')
  ```
- [ ] Aplicar `validators=[validate_json_safe]` nos JSONFields críticos de `models.py`:
  - `PerfilUsuario.permissoes`
  - `Device.profile`
  - `Device.raw_config`
  - `RegraAlertaTelemetria.config`
  - `TelemetryData.raw_payload`
- **Arquivos:** `app/validators.py`, `app/models.py`
- **Validação:** `python manage.py check` passa, testes com JSON malicioso são rejeitados

## 🧪 TESTES DE VALIDAÇÃO DA BUILD 00
```bash
python manage.py check
python manage.py test  # se existirem testes
# Verificar manualmente:
# 1. .env não aparece em `git status`
# 2. Login com senha "123" é rejeitado
# 3. 6 tentativas de login falho = lockout
# 4. POST via fetch() sem CSRF retorna 403
# 5. Response headers contêm Content-Security-Policy
```

## 📝 NOTAS
_Espaço para o agente registrar observações, erros encontrados ou decisões tomadas._

---
---

# ═══════════════════════════════════════════════════════════════
# BUILD 01 — FUNDAÇÃO BACKEND
# ═══════════════════════════════════════════════════════════════

**Status:** [CONCLUÍDO]
**Prioridade:** 🔴 CRÍTICA (pré-requisito para TODAS as builds seguintes)
**Esforço estimado:** ~8 horas
**Defeitos cobertos:** #31, #46, #34, #35, #47, #48, #49, #159
**Dependências:** BUILD 00 [CONCLUÍDO]
**Concluído em:** 2026-08-31

## 🎯 OBJETIVO
Migrar de SQLite para PostgreSQL, separar settings por ambiente (dev/staging/prod), adicionar logging estruturado, health check, request tracing, CORS, compressão, e backup automático. Esta build cria a base sólida para tudo que vem depois.

## 📖 CONTEXTO INICIAL
O sistema roda em SQLite (db.sqlite3, 2.8MB) que não suporta múltiplos escritores simultâneos — isso é um bloqueador total para produção. O settings.py era monolítico (4.5KB) sem distinção dev/prod na primeira versão. Não há logging estruturado, health check, nem CORS configurado. O backup é manual.

## ✅ TAREFAS

### T01.01 — Instalar dependências de infra
- [x] Criar/atualizar `requirements.txt` com:
  ```
  psycopg2-binary>=2.9
  django-environ>=0.11
  django-cors-headers>=4.3
  whitenoise>=6.6
  structlog>=24.1
  django-health-check>=3.18
  ```
- [x] Instalar: `pip install -r requirements.txt`
- **Arquivos:** `requirements.txt`
- **Validação:** `pip list | findstr psycopg2` mostra versão

### T01.02 — Split settings.py em base/dev/prod
- [x] Criar pasta `config/settings/`
- [x] Criar `config/settings/__init__.py`:
  ```python
  import os
  env = os.environ.get('DJANGO_ENV', 'dev')
  if env == 'prod':
      from .prod import *
  elif env == 'staging':
      from .staging import *
  else:
      from .dev import *
  ```
- [ ] Criar `config/settings/base.py` com TUDO do settings.py atual, EXCETO:
  - DATABASE config
  - DEBUG
  - ALLOWED_HOSTS
  - SECRET_KEY (ler de env)
  - Usar `environ.Env()` para carregar `.env`
- [ ] Criar `config/settings/dev.py`:
  ```python
  from .base import *
  DEBUG = True
  ALLOWED_HOSTS = ['*']
  DATABASES = {
      'default': {
          'ENGINE': 'django.db.backends.sqlite3',
          'NAME': BASE_DIR / 'db.sqlite3',
      }
  }
  ```
- [ ] Criar `config/settings/prod.py`:
  ```python
  from .base import *
  import environ
  env = environ.Env()
  DEBUG = False
  ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=['localhost'])
  DATABASES = {
      'default': env.db('DATABASE_URL', default='postgres://ampliagro:ampliagro@localhost:5432/ampliagro')
  }
  SECURE_SSL_REDIRECT = True
  SESSION_COOKIE_SECURE = True
  CSRF_COOKIE_SECURE = True
  ```
- [ ] Criar `config/settings/staging.py` (cópia de prod mas com `DEBUG=True`)
- [ ] Remover `config/settings.py` original (renomear para `config/settings_OLD.py.bak`)
- [ ] Atualizar `manage.py` para `os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')`
- [ ] Atualizar `.env` para conter `DJANGO_ENV=dev`
- [ ] Atualizar `.env.example` com todos os novos envvars
- **Arquivos:** `config/settings/`, `config/settings.py`, `manage.py`, `.env`, `.env.example`
- **Validação:** `python manage.py check` passa com settings split

### T01.03 — Configurar PostgreSQL para produção/staging
- [x] Adicionar no `.env.example`
- [x] Documentar no README.md como instalar PostgreSQL e criar o banco
- [x] Em dev, SQLite continua funcionando (settings/dev.py usa SQLite)
- [x] Testar migração
- **Arquivos:** `.env.example`, `README.md`
- **Validação:** `python manage.py check` com DJANGO_ENV=dev (SQLite) e DJANGO_ENV=staging (PostgreSQL se disponível)

### T01.04 — Configurar logging estruturado (structlog)
- [x] Adicionar config structlog em `config/settings/base.py`
- [x] Criar diretório `logs/` e adicionar ao `.gitignore`
- **Arquivos:** `config/settings/base.py`, `logs/.gitkeep`, `.gitignore`
- **Validação:** Ao iniciar o servidor, logs estruturados aparecem no console

### T01.05 — Adicionar health check endpoint
- [x] Adicionar `health_check` ao `INSTALLED_APPS`
- [x] Adicionar plugins
- [x] Adicionar url em `config/urls.py`
- **Arquivos:** `config/settings/base.py`, `config/urls.py`
- **Validação:** `curl http://localhost:8000/health/` retorna 200 com JSON de status

### T01.06 — Adicionar middleware de request_id
- [x] Criar `app/middleware.py`
- [x] Adicionar `app.middleware.RequestIDMiddleware` ao topo do MIDDLEWARE
- **Arquivos:** `app/middleware.py`, `config/settings/base.py`
- **Validação:** Response headers contêm `X-Request-ID`

### T01.07 — Configurar CORS headers
- [x] Adicionar `corsheaders` ao `INSTALLED_APPS`
- [x] Adicionar `corsheaders.middleware.CorsMiddleware`
- [x] Configurar em base.py
- **Arquivos:** `config/settings/base.py`

### T01.08 — Configurar whitenoise para assets estáticos
- [x] Adicionar `whitenoise.middleware.WhiteNoiseMiddleware`
- [x] Configurar `STATICFILES_STORAGE`
- [x] Rodar `python manage.py collectstatic --noinput`
- **Arquivos:** `config/settings/base.py`, `config/settings/prod.py`
- **Validação:** Assets servidos com headers de compressão (gzip)

### T01.09 — Configurar backup automático do banco
- [x] Criar script customizado python para gerenciar os backups: `scripts/backup_db.py`
- [x] Validar que detecta env var e faz dump correto (sqlite/postgres)
- **Arquivos:** `scripts/backup_db.py`
- [ ] Criar management command `app/management/commands/backup_db.py`:
  ```python
  from django.core.management.base import BaseCommand
  from django.core.management import call_command

  class Command(BaseCommand):
      help = 'Backup do banco de dados'
      def handle(self, *args, **options):
          call_command('dbbackup', '--clean')
          self.stdout.write(self.style.SUCCESS('Backup concluído'))
  ```
- **Arquivos:** `config/settings/base.py`, `app/management/commands/backup_db.py`
- **Validação:** `python manage.py backup_db` cria arquivo em `_backups/db/`

## 🧪 TESTES DE VALIDAÇÃO DA BUILD 01
```bash
python manage.py check
python manage.py migrate --run-syncdb
python manage.py runserver 0.0.0.0:8000
# Em outro terminal:
curl http://localhost:8000/healthz/  # → 200 OK
curl -I http://localhost:8000/       # → X-Request-ID presente
python manage.py backup_db           # → Arquivo de backup criado
```

## 📝 NOTAS
_Espaço para o agente registrar observações._

---
---

# ═══════════════════════════════════════════════════════════════
# BUILD 02 — QUALIDADE DE CÓDIGO (Linting, Formatting, CI/CD)
# ═══════════════════════════════════════════════════════════════

**Status:** [PENDENTE]
**Prioridade:** 🟠 ALTA
**Esforço estimado:** ~6 horas
**Defeitos cobertos:** #58, #59, #129, #130, #131, #161
**Dependências:** BUILD 01 [CONCLUÍDO]
**Concluído em:** _não concluído_

## 🎯 OBJETIVO
Implementar ferramentas de qualidade de código (linting Python e JS, formatação, type checking) e pipeline CI/CD no GitHub Actions para enforcement automático. Nenhum código novo deve entrar no repositório sem passar por linting e testes.

## 📖 CONTEXTO INICIAL
O projeto tem 0% de enforcement de qualidade. Não há ESLint, Prettier, flake8/ruff, mypy, nem CI/CD pipeline. Código JS e Python seguem estilos inconsistentes. Erros de tipo só aparecem em runtime.

## ✅ TAREFAS

### T02.01 — Configurar Ruff (linter + formatter Python)
- [x] Instalar: `pip install ruff`
- [x] Criar `ruff.toml` na raiz
- [x] Rodar `ruff check app/ config/ scripts/ --fix` para corrigir auto-fixáveis
- [x] Rodar `ruff format app/ config/ scripts/`
- [x] Commit: `chore: apply ruff linting and formatting`
- **Arquivos:** `ruff.toml`, todos os `.py`
- **Validação:** `ruff check app/ config/` retorna 0 erros

### T02.02 — Configurar ESLint + Prettier para JavaScript
- [x] Instalar: `npm install -D eslint prettier eslint-config-prettier eslint-plugin-prettier`
- [x] Criar `.eslintrc.json` (ou `eslint.config.mjs`)
- [x] Criar `.prettierrc`
- [x] Adicionar scripts ao `package.json`
- [x] Rodar `npm run lint:js` e `npm run format:js`
- [x] Commit: `chore: apply ESLint and Prettier to JS files`
- **Arquivos:** `.eslintrc.json`, `.prettierrc`, `package.json`, todos os `.js`
- **Validação:** `npm run lint:js` retorna 0 erros (apenas warnings permitidos)

### T02.03 — Configurar mypy para type checking Python
- [ ] Instalar: `pip install mypy django-stubs djangorestframework-stubs`
- [ ] Criar `mypy.ini`:
  ```ini
  [mypy]
  python_version = 3.11
  plugins = mypy_django_plugin.main, mypy_drf_plugin.main
  ignore_missing_imports = True
  warn_return_any = True
  warn_unused_ignores = True
  disallow_untyped_defs = False  # relaxar inicialmente

  [mypy.plugins.django-stubs]
  django_settings_module = config.settings

  [mypy-app.migrations.*]
  ignore_errors = True
  ```
- [ ] Rodar `mypy app/ --ignore-missing-imports` para ver estado atual (não precisa 0 erros)
- [ ] Commit: `chore: add mypy configuration`
- **Arquivos:** `mypy.ini`
- **Validação:** `mypy app/models.py` roda sem crash (erros são OK por agora)

### T02.04 — Criar CI/CD Pipeline (GitHub Actions)
- [x] Criar/Atualizar `.github/workflows/ci.yml`:
  ```yaml
  name: CI

  on:
    push:
      branches: [main, develop]
    pull_request:
      branches: [main]

  jobs:
    lint:
      runs-on: ubuntu-latest
      steps:
        - uses: actions/checkout@v4
        - uses: actions/setup-python@v5
          with: { python-version: '3.11' }
        - uses: actions/setup-node@v4
          with: { node-version: '20' }
        - run: pip install ruff mypy
        - run: npm ci
        - run: ruff check app/ config/
        - run: npm run lint:js

    test:
      runs-on: ubuntu-latest
      needs: lint
      steps:
        - uses: actions/checkout@v4
        - uses: actions/setup-python@v5
          with: { python-version: '3.11' }
        - run: pip install -r requirements.txt
        - run: python manage.py check
        - run: python manage.py test --parallel
      env:
        DJANGO_ENV: dev
        SECRET_KEY: ci-test-secret-key-not-for-production

    security:
      runs-on: ubuntu-latest
      steps:
        - uses: actions/checkout@v4
        - uses: actions/setup-python@v5
          with: { python-version: '3.11' }
        - run: pip install bandit safety
        - run: bandit -r app/ -ll --skip B101
        - run: safety check --full-report || true
  ```
- [ ] Commit: `ci: add GitHub Actions CI pipeline`
- **Arquivos:** `.github/workflows/ci.yml`
- **Validação:** Push ao branch e verificar que Actions roda

### T02.05 — Adicionar pre-commit hooks
- [ ] Instalar: `pip install pre-commit`
- [ ] Criar `.pre-commit-config.yaml`:
  ```yaml
  repos:
    - repo: https://github.com/astral-sh/ruff-pre-commit
      rev: v0.5.0
      hooks:
        - id: ruff
          args: [--fix]
        - id: ruff-format

    - repo: https://github.com/pre-commit/mirrors-prettier
      rev: v3.1.0
      hooks:
        - id: prettier
          types_or: [javascript, css]

    - repo: https://github.com/pre-commit/pre-commit-hooks
      rev: v4.6.0
      hooks:
        - id: trailing-whitespace
        - id: end-of-file-fixer
        - id: check-yaml
        - id: check-json
        - id: detect-private-key
  ```
- [ ] Instalar hooks: `pre-commit install`
- [ ] Rodar em tudo: `pre-commit run --all-files`
- [ ] Commit: `chore: add pre-commit hooks`
- **Arquivos:** `.pre-commit-config.yaml`
- **Validação:** Tentativa de commit com código ruim é bloqueada

## 🧪 TESTES DE VALIDAÇÃO DA BUILD 02
```bash
ruff check app/ config/         # 0 erros
npm run lint:js                 # 0 erros
python manage.py check          # OK
pre-commit run --all-files      # todos passam
```

## 📝 NOTAS
_Espaço para o agente registrar observações._

---
---

# ═══════════════════════════════════════════════════════════════
# BUILD 03 — ARQUITETURA BACKEND (Split, Cache, Queue, API)
# ═══════════════════════════════════════════════════════════════

**Status:** [PENDENTE]
**Prioridade:** 🟠 ALTA
**Esforço estimado:** ~12 horas
**Defeitos cobertos:** #26, #27, #28, #29, #30, #32, #33, #36, #37, #38, #39, #40, #41, #42, #43, #44, #45, #50, #152, #168, #169, #177
**Dependências:** BUILD 02 [CONCLUÍDO]
**Concluído em:** _não concluído_

## 🎯 OBJETIVO
Refatorar a arquitetura backend para ser escalável e maintainable: splittar os arquivos monolíticos (models.py, views.py, api/views.py), adicionar Redis cache, Celery task queue, paginação, filtros, documentação OpenAPI, e audit logging.

## 📖 CONTEXTO INICIAL
- `app/models.py` = 1588 linhas, 57KB — contém TODOS os 30+ modelos do sistema
- `app/views.py` = 65KB — contém TODAS as views Django
- `app/api/views.py` = 108KB — contém TODAS as views da API
- Sem cache, sem task queue, sem paginação, sem filtros padronizados, sem documentação de API
- `context_processors.py` carrega dados em TODA request
- `TarefaEstagio.save()` faz lógica pesada direto no model

## ✅ TAREFAS

### T03.01 — Splittar models.py em package models/
- [ ] Criar diretório `app/models/`
- [ ] Criar `app/models/__init__.py` que importa todos os modelos:
  ```python
  from .core import Cultura, Propriedade, Talhao, TalhaoGeometria
  from .safra import Safra, Insumo, AplicacaoInsumo
  from .equipe import Funcionario, CARGOS
  from .maquinario import Maquinario
  from .financeiro import LancamentoFinanceiro
  from .pecuaria import Animal, ProducaoAnimal
  from .estoque import EstoqueItem
  from .apiario import ApiarioColmeia, ProducaoApiario
  from .producao import RegistroProducao, EstagioCultura, TarefaEstagio
  from .iot import Gateway, Device, TelemetryData, RegraAlertaTelemetria, AlertaTelemetria, ComandoDevice, FonteDadosExterna, EstacaoMeteo, LeituraSensor
  from .usuario import PerfilUsuario, DashboardUserState, WidgetUsuario, Notificacao
  from .relatorio import RelatorioTemplate, RelatorioGerado
  from .erro import ErroReport
  ```
- [ ] Mover cada grupo de modelos para seu arquivo:
  - `app/models/core.py` → Cultura, Propriedade, Talhao, TalhaoGeometria, BIOMAS
  - `app/models/safra.py` → Safra, Insumo, AplicacaoInsumo, CATEGORIAS_INSUMO
  - `app/models/equipe.py` → Funcionario, CARGOS
  - `app/models/maquinario.py` → Maquinario, TIPOS_MAQUINARIO
  - `app/models/financeiro.py` → LancamentoFinanceiro, CATEGORIAS_FINANCEIRO
  - `app/models/pecuaria.py` → Animal, ProducaoAnimal, ESPECIES_ANIMAL, TIPOS_PRODUCAO_ANIMAL
  - `app/models/estoque.py` → EstoqueItem, CATEGORIAS_ESTOQUE
  - `app/models/apiario.py` → ApiarioColmeia, ProducaoApiario
  - `app/models/producao.py` → RegistroProducao, EstagioCultura, TarefaEstagio
  - `app/models/iot.py` → Gateway, Device, TelemetryData, RegraAlertaTelemetria, AlertaTelemetria, ComandoDevice, FonteDadosExterna, EstacaoMeteo, LeituraSensor + todas as CHOICES de IoT
  - `app/models/usuario.py` → PerfilUsuario, DashboardUserState, WidgetUsuario, Notificacao
  - `app/models/relatorio.py` → RelatorioTemplate, RelatorioGerado
  - `app/models/erro.py` → ErroReport, TIPOS_ERRO
- [ ] Manter `app/models.py` original como `app/models_BACKUP.py` (temporário)
- [ ] Rodar `python manage.py check` — corrigir imports quebrados
- [ ] Rodar `python manage.py makemigrations` — NÃO deve gerar novas migrations se FKs estiverem certas
- [ ] Commit: `refactor: split models.py into models/ package (13 módulos)`
- **Arquivos:** `app/models/` (13 novos arquivos), `app/models.py` → backup
- **Validação:** `python manage.py check` + `python manage.py migrate --check` (sem novas migrations)

### T03.02 — Splittar views.py em views/ package
- [ ] Criar `app/views/` com `__init__.py` importando todas as views
- [ ] Dividir por domínio:
  - `app/views/auth.py` → login, logout, demo_login, onboarding
  - `app/views/cadastro.py` → todos os cadastro_*_view
  - `app/views/dashboard.py` → index_view, dashboard_os, resumo_gerencial
  - `app/views/campo.py` → setor_campo, setor_estoque, agenda_*, previsao_*
  - `app/views/servidor.py` → servidor_dashboard, servidor_estoque, servidor_agenda, servidor_alertas
  - `app/views/operario.py` → operario_kanban, operario_perfil, operario_registrar, operario_criar_login
  - `app/views/iot.py` → sensores, dispositivos, telemetria
  - `app/views/guias.py` → guia_vegetal, guia_animal, guia_aquatica, guia_sistemas, registro_cafe, registro_cultura
  - `app/views/config.py` → perfil_config, config_dia, config_noturno, config_sistema, config_page, erro_report
  - `app/views/financeiro.py` → simulador_financeiro, simulador_colheita, simulador_lucro
  - `app/views/logistica.py` → logistica_caminhao, logistica_rotas, mapa
  - `app/views/estoque.py` → estoque_geral, estoque_insumos
  - `app/views/equipe.py` → equipe_agenda, equipe_empregados
  - `app/views/api.py` → get_talhoes_api, servidor_config_api
- [ ] Atualizar `app/urls.py` para importar dos novos módulos
- [ ] Commit: `refactor: split views.py into views/ package (14 módulos)`
- **Arquivos:** `app/views/` (14 novos arquivos), `app/urls.py`
- **Validação:** `python manage.py check` + todas as URLs funcionam

### T03.03 — Splittar api/views.py em módulos
- [ ] Criar `app/api/views/` com `__init__.py`
- [ ] Dividir api/views.py por domínio:
  - `app/api/views/cultures.py` → endpoints de culturas, IBGE, fallback
  - `app/api/views/production.py` → endpoints de produção, safras
  - `app/api/views/financial.py` → endpoints financeiros
  - `app/api/views/iot.py` → endpoints de telemetria, devices, gateways
  - `app/api/views/kanban.py` → endpoints de tarefas, estágios
  - `app/api/views/user.py` → endpoints de perfil, dashboard state, widgets
  - `app/api/views/estoque.py` → endpoints de estoque, insumos
- [ ] Atualizar `app/api/urls.py`
- [ ] Commit: `refactor: split api/views.py into api/views/ package (7 módulos)`
- **Arquivos:** `app/api/views/` (7 novos), `app/api/urls.py`
- **Validação:** Todas as APIs retornam 200 OK

### T03.04 — Configurar Redis cache
- [ ] Instalar: `pip install django-redis`
- [ ] Adicionar em `config/settings/base.py`:
  ```python
  CACHES = {
      'default': {
          'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',  # dev fallback
      }
  }
  ```
- [ ] Em `config/settings/prod.py`:
  ```python
  CACHES = {
      'default': {
          'BACKEND': 'django_redis.cache.RedisCache',
          'LOCATION': env('REDIS_URL', default='redis://localhost:6379/0'),
          'OPTIONS': {'CLIENT_CLASS': 'django_redis.client.DefaultClient'},
      }
  }
  SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
  SESSION_CACHE_ALIAS = 'default'
  ```
- [ ] Adicionar `cache_page` nas views mais pesadas (dashboard, relatórios)
- **Arquivos:** `config/settings/base.py`, `config/settings/prod.py`
- **Validação:** `python manage.py check` com e sem Redis

### T03.05 — Configurar Celery para task queue
- [ ] Instalar: `pip install celery[redis] django-celery-results`
- [ ] Criar `config/celery.py`:
  ```python
  import os
  from celery import Celery

  os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
  app = Celery('ampliagro')
  app.config_from_object('django.conf:settings', namespace='CELERY')
  app.autodiscover_tasks()
  ```
- [ ] Adicionar em `config/__init__.py`:
  ```python
  from .celery import app as celery_app
  __all__ = ('celery_app',)
  ```
- [ ] Configurar em base.py:
  ```python
  CELERY_BROKER_URL = env('CELERY_BROKER_URL', default='redis://localhost:6379/1')
  CELERY_RESULT_BACKEND = 'django-db'
  CELERY_ACCEPT_CONTENT = ['json']
  CELERY_TASK_SERIALIZER = 'json'
  INSTALLED_APPS += ['django_celery_results']
  ```
- [ ] Criar `app/tasks.py` com task de exemplo:
  ```python
  from celery import shared_task
  import structlog

  logger = structlog.get_logger()

  @shared_task
  def gerar_relatorio_async(user_id, template_id):
      logger.info("gerando_relatorio", user_id=user_id, template_id=template_id)
      # Implementação futura na BUILD 07
      return {'status': 'ok'}
  ```
- [ ] `python manage.py migrate` para tabelas celery_results
- **Arquivos:** `config/celery.py`, `config/__init__.py`, `config/settings/base.py`, `app/tasks.py`
- **Validação:** `celery -A config inspect ping` retorna pong (com Redis rodando)

### T03.06 — Adicionar paginação e filtros à API
- [ ] Instalar: `pip install django-filter`
- [ ] Configurar DRF em base.py:
  ```python
  REST_FRAMEWORK = {
      'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
      'PAGE_SIZE': 50,
      'DEFAULT_FILTER_BACKENDS': [
          'django_filter.rest_framework.DjangoFilterBackend',
          'rest_framework.filters.SearchFilter',
          'rest_framework.filters.OrderingFilter',
      ],
      'DEFAULT_THROTTLE_CLASSES': [
          'rest_framework.throttling.AnonRateThrottle',
          'rest_framework.throttling.UserRateThrottle',
      ],
      'DEFAULT_THROTTLE_RATES': {
          'anon': '100/hour',
          'user': '1000/hour',
      },
  }
  ```
- [ ] Adicionar `filterset_fields`, `search_fields`, `ordering_fields` nos viewsets existentes
- **Arquivos:** `config/settings/base.py`, `app/api/views/*.py`
- **Validação:** `GET /api/telemetry/?page=1&page_size=10` retorna paginado

### T03.07 — Adicionar documentação OpenAPI (Swagger)
- [ ] Instalar: `pip install drf-spectacular`
- [ ] Adicionar `drf_spectacular` ao `INSTALLED_APPS`
- [ ] Configurar:
  ```python
  REST_FRAMEWORK['DEFAULT_SCHEMA_CLASS'] = 'drf_spectacular.openapi.AutoSchema'
  SPECTACULAR_SETTINGS = {
      'TITLE': 'Ampliagro API',
      'DESCRIPTION': 'API do sistema de gestão agrícola Ampliagro',
      'VERSION': '1.0.0',
      'SERVE_INCLUDE_SCHEMA': False,
  }
  ```
- [ ] Adicionar URLs:
  ```python
  from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
  urlpatterns += [
      path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
      path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
  ]
  ```
- **Arquivos:** `config/settings/base.py`, `config/urls.py`
- **Validação:** `http://localhost:8000/api/docs/` mostra Swagger UI

### T03.08 — Extrair signals do model save()
- [ ] Criar `app/signals.py`:
  ```python
  from django.db.models.signals import pre_save
  from django.dispatch import receiver
  import structlog

  logger = structlog.get_logger()

  @receiver(pre_save, sender='app.TarefaEstagio')
  def sync_tarefa_status(sender, instance, **kwargs):
      """Sincroniza concluida <-> status e denormaliza propriedade."""
      if instance.concluida and instance.status != 'concluido':
          instance.status = 'concluido'
          if not instance.concluida_em:
              from django.utils import timezone
              instance.concluida_em = timezone.now()
      elif instance.status == 'concluido' and not instance.concluida:
          instance.concluida = True
          if not instance.concluida_em:
              from django.utils import timezone
              instance.concluida_em = timezone.now()
      elif instance.status in ['pendente', 'andamento'] and instance.concluida:
          instance.concluida = False
          instance.concluida_em = None

      if not instance.propriedade_id and instance.estagio_id:
          try:
              from app.models import Propriedade
              reg_user = instance.estagio.registro.user
              prop = Propriedade.objects.filter(user=reg_user).first()
              if prop:
                  instance.propriedade = prop
          except Exception:
              pass
  ```
- [ ] Registrar signals em `app/apps.py`:
  ```python
  class AppConfig(AppConfig):
      def ready(self):
          import app.signals  # noqa
  ```
- [ ] Remover lógica do `TarefaEstagio.save()` — deixar apenas `super().save()`
- **Arquivos:** `app/signals.py`, `app/apps.py`, `app/models/producao.py`
- **Validação:** Tarefas no Kanban continuam sincronizando status corretamente

### T03.09 — Adicionar audit log
- [ ] Instalar: `pip install django-auditlog`
- [ ] Adicionar `auditlog` ao INSTALLED_APPS
- [ ] Adicionar `auditlog.middleware.AuditlogMiddleware` ao MIDDLEWARE
- [ ] Registrar modelos críticos em `app/audit.py`:
  ```python
  from auditlog.registry import auditlog_registry
  from app.models import (
      LancamentoFinanceiro, Funcionario, Propriedade,
      Maquinario, EstoqueItem, Animal, TarefaEstagio,
      Device, RegraAlertaTelemetria, PerfilUsuario,
  )

  for model in [LancamentoFinanceiro, Funcionario, Propriedade,
                Maquinario, EstoqueItem, Animal, TarefaEstagio,
                Device, RegraAlertaTelemetria, PerfilUsuario]:
      auditlog_registry.register(model)
  ```
- [ ] Importar em `app/apps.py`
- [ ] `python manage.py migrate`
- **Arquivos:** `app/audit.py`, `app/apps.py`, `config/settings/base.py`
- **Validação:** Editar um registro e verificar em `AuditLog.objects.all()` que o log foi criado

### T03.10 — Otimizar context_processors.py
- [ ] Mover carregamento de dados pesados para cache ou lazy loading:
  ```python
  from django.core.cache import cache

  def global_context(request):
      if not request.user.is_authenticated:
          return {}

      cache_key = f'ctx_{request.user.id}'
      ctx = cache.get(cache_key)
      if ctx:
          return ctx

      # carregar dados leves apenas
      ctx = {
          'user_tipo': getattr(request.user, 'perfil', None) and request.user.perfil.tipo_usuario or 'produtor',
      }
      cache.set(cache_key, ctx, 300)  # 5 min cache
      return ctx
  ```
- **Arquivos:** `app/context_processors.py`
- **Validação:** Requests subsequentes usam cache (visível no log)

### T03.11 — Squash migrations
- [ ] Contar quantas migrations existem: `dir app\migrations\*.py /b | find /c /v ""`
- [ ] Se > 20, squash: `python manage.py squashmigrations app 0001 XXXX` (onde XXXX é a última)
- [ ] Testar: `python manage.py migrate --run-syncdb`
- **Arquivos:** `app/migrations/`
- **Validação:** `python manage.py showmigrations` mostra lista limpa

### T03.12 — Adicionar select_related/prefetch_related nas queries pesadas
- [ ] Auditar views que fazem queries N+1:
  - `index_view` → Propriedade + talhoes + safras + culturas
  - `servidor_dashboard_view` → tarefas + funcionarios
  - `operario_kanban_view` → tarefas + estagios + registros
- [ ] Adicionar `select_related` e `prefetch_related` em cada query
- [ ] Exemplo:
  ```python
  # ANTES:
  talhoes = Talhao.objects.filter(propriedade=prop)
  # DEPOIS:
  talhoes = Talhao.objects.filter(propriedade=prop).select_related('cultura_atual').prefetch_related('safras')
  ```
- **Arquivos:** `app/views/*.py` (vários)
- **Validação:** Instalar `django-debug-toolbar` e verificar redução de queries

## 🧪 TESTES DE VALIDAÇÃO DA BUILD 03
```bash
python manage.py check
python manage.py migrate
python manage.py runserver 0.0.0.0:8000
# Verificar:
# 1. http://localhost:8000/api/docs/ → Swagger UI funciona
# 2. APIs retornam resultados paginados
# 3. Dashboard carrega sem erros
# 4. Kanban funciona (drag & drop + status sync)
# 5. `python manage.py shell -c "from app.models import *; print(Propriedade.objects.count())"` funciona
```

## 📝 NOTAS
_Espaço para o agente._

---
---

# ═══════════════════════════════════════════════════════════════
# BUILD 04 — FUNDAÇÃO FRONTEND (Bundler, TypeScript, i18n)
# ═══════════════════════════════════════════════════════════════

**Status:** [PENDENTE]
**Prioridade:** 🟠 ALTA
**Esforço estimado:** ~10 horas
**Defeitos cobertos:** #51, #52, #53, #54, #55, #56, #57, #60, #61, #62, #63, #64, #65, #66, #67, #68, #69, #70, #71, #72, #73, #74, #170, #172
**Dependências:** BUILD 02 [CONCLUÍDO]
**Concluído em:** _não concluído_

## 🎯 OBJETIVO
Configurar Vite como bundler para todo o JavaScript/CSS, implementar base TypeScript, adicionar i18n framework, lazy loading de módulos pesados, global error boundary, e utilitários de formatação. Isso resolve os problemas de performance frontend (LCP > 5s) e maintainability.

## 📖 CONTEXTO INICIAL
33 módulos JS (~450KB total) servidos como arquivos individuais sem bundling, minificação ou tree-shaking. `guide.js` sozinho tem 177KB. Sem TypeScript, sem i18n, sem lazy loading. index.html tem 687KB. LCP estimado > 5s.

## ✅ TAREFAS

### T04.01 — Configurar Vite como bundler
- [ ] Instalar: `npm install -D vite vite-plugin-static-copy`
- [ ] Criar `vite.config.js`:
  ```javascript
  import { defineConfig } from 'vite';
  import { resolve } from 'path';

  export default defineConfig({
    root: 'app/static',
    build: {
      outDir: '../../staticfiles/dist',
      emptyOutDir: true,
      rollupOptions: {
        input: {
          main: resolve(__dirname, 'app/static/js/main.js'),
        },
        output: {
          entryFileNames: 'js/[name].[hash].js',
          chunkFileNames: 'js/chunks/[name].[hash].js',
          assetFileNames: 'assets/[name].[hash].[ext]',
        },
      },
      sourcemap: true,
      minify: 'esbuild',
    },
    server: {
      port: 5173,
      proxy: {
        '/api': 'http://localhost:8000',
        '/admin': 'http://localhost:8000',
      },
    },
  });
  ```
- [ ] Criar `app/static/js/main.js` como entry point que importa módulos necessários:
  ```javascript
  // Core modules — sempre carregados
  import './csrf-utils.js';
  import './theme-system.js';
  import './spa.js';
  import './data-store.js';
  import './data-provider.js';

  // Lazy modules — carregados sob demanda
  // import('./guide.js') — quando necessário
  // import('./experiment.js') — quando necessário
  ```
- [ ] Atualizar `package.json` scripts:
  ```json
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  }
  ```
- [ ] Testar: `npm run build` gera bundle em `staticfiles/dist/`
- **Arquivos:** `vite.config.js`, `app/static/js/main.js`, `package.json`
- **Validação:** `npm run build` produz JS minificado < 200KB total (gzipped)

### T04.02 — Modularizar guide.js (177KB → chunks)
- [ ] Identificar seções independentes de `guide.js` (cada cultura/grupo)
- [ ] Extrair em módulos separados:
  - `app/static/js/guides/graos.js`
  - `app/static/js/guides/frutas.js`
  - `app/static/js/guides/hortalicas.js`
  - `app/static/js/guides/pecuaria.js`
  - `app/static/js/guides/florestal.js`
  - etc.
- [ ] No main guide.js, usar dynamic imports:
  ```javascript
  export async function loadGuide(grupo) {
    const module = await import(`./guides/${grupo}.js`);
    return module.default;
  }
  ```
- [ ] Vite fará code splitting automaticamente
- **Arquivos:** `app/static/js/guide.js` → `app/static/js/guides/` (múltiplos)
- **Validação:** guide.js principal < 20KB, chunks < 30KB cada

### T04.03 — Criar global error boundary
- [ ] Criar `app/static/js/error-boundary.js`:
  ```javascript
  window.addEventListener('error', (event) => {
    console.error('[Ampliagro Error]', event.error);
    showErrorToast('Ocorreu um erro inesperado. Tente recarregar a página.');
    // Enviar para backend (futuro: Sentry)
    fetch('/api/erro-js/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
      body: JSON.stringify({
        message: event.error?.message || event.message,
        stack: event.error?.stack || '',
        url: window.location.href,
        timestamp: new Date().toISOString(),
      }),
    }).catch(() => {}); // silencioso
  });

  window.addEventListener('unhandledrejection', (event) => {
    console.error('[Ampliagro Promise Error]', event.reason);
  });
  ```
- [ ] Importar em `main.js` como primeiro módulo
- **Arquivos:** `app/static/js/error-boundary.js`, `app/static/js/main.js`
- **Validação:** Erro JS mostra toast ao invés de página quebrada

### T04.04 — Criar utilitários de formatação (Intl API)
- [ ] Criar `app/static/js/formatters.js`:
  ```javascript
  const locale = navigator.language || 'pt-BR';

  export const formatCurrency = (value, currency = 'BRL') =>
    new Intl.NumberFormat(locale, { style: 'currency', currency }).format(value);

  export const formatNumber = (value, decimals = 2) =>
    new Intl.NumberFormat(locale, { minimumFractionDigits: decimals, maximumFractionDigits: decimals }).format(value);

  export const formatDate = (date, style = 'medium') =>
    new Intl.DateTimeFormat(locale, { dateStyle: style }).format(new Date(date));

  export const formatDateTime = (date) =>
    new Intl.DateTimeFormat(locale, { dateStyle: 'short', timeStyle: 'short' }).format(new Date(date));

  export const formatRelativeTime = (date) => {
    const diff = (new Date(date) - new Date()) / 1000;
    const rtf = new Intl.RelativeTimeFormat(locale, { numeric: 'auto' });
    if (Math.abs(diff) < 60) return rtf.format(Math.round(diff), 'second');
    if (Math.abs(diff) < 3600) return rtf.format(Math.round(diff / 60), 'minute');
    if (Math.abs(diff) < 86400) return rtf.format(Math.round(diff / 3600), 'hour');
    return rtf.format(Math.round(diff / 86400), 'day');
  };

  export const formatArea = (ha) => `${formatNumber(ha)} ha`;
  export const formatWeight = (kg) => kg >= 1000 ? `${formatNumber(kg/1000)} t` : `${formatNumber(kg)} kg`;
  ```
- [ ] Substituir formatações manuais nos módulos existentes para usar `formatters.js`
- **Arquivos:** `app/static/js/formatters.js`
- **Validação:** Datas e moedas formatam corretamente em PT-BR

### T04.05 — Configurar base i18n
- [ ] Criar `app/static/js/i18n/`:
  - `app/static/js/i18n/index.js` (loader de traduções)
  - `app/static/js/i18n/pt-BR.json` (todas as strings atuais)
  - `app/static/js/i18n/en-US.json` (placeholders para futuro)
  - `app/static/js/i18n/es-AR.json` (placeholders para futuro)
- [ ] Implementar função `t()`:
  ```javascript
  let currentLocale = 'pt-BR';
  let translations = {};

  export async function initI18n(locale = 'pt-BR') {
    currentLocale = locale;
    const module = await import(`./${locale}.json`);
    translations = module.default;
  }

  export function t(key, params = {}) {
    let text = translations[key] || key;
    for (const [k, v] of Object.entries(params)) {
      text = text.replace(`{${k}}`, v);
    }
    return text;
  }
  ```
- **Arquivos:** `app/static/js/i18n/`
- **Validação:** `t('dashboard.titulo')` retorna "Dashboard" em pt-BR

### T04.06 — Criar fetch interceptor global
- [ ] Criar `app/static/js/api-client.js`:
  ```javascript
  import { getCsrfToken } from './csrf-utils.js';

  const BASE_URL = '';

  class ApiClient {
    async request(url, options = {}) {
      const config = {
        ...options,
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCsrfToken(),
          ...options.headers,
        },
      };

      try {
        const response = await fetch(`${BASE_URL}${url}`, config);

        if (response.status === 401) {
          window.location.href = '/login/';
          return;
        }

        if (response.status === 403) {
          showErrorToast('Sem permissão para esta ação');
          throw new Error('Forbidden');
        }

        if (response.status === 429) {
          showErrorToast('Muitas requisições. Aguarde um momento.');
          throw new Error('Rate limited');
        }

        if (!response.ok) {
          const error = await response.json().catch(() => ({ detail: 'Erro desconhecido' }));
          throw new Error(error.detail || `HTTP ${response.status}`);
        }

        return response.json();
      } catch (error) {
        if (error.name === 'TypeError' && error.message === 'Failed to fetch') {
          showErrorToast('Sem conexão com o servidor');
        }
        throw error;
      }
    }

    get(url) { return this.request(url); }
    post(url, data) { return this.request(url, { method: 'POST', body: JSON.stringify(data) }); }
    put(url, data) { return this.request(url, { method: 'PUT', body: JSON.stringify(data) }); }
    patch(url, data) { return this.request(url, { method: 'PATCH', body: JSON.stringify(data) }); }
    delete(url) { return this.request(url, { method: 'DELETE' }); }
  }

  export const api = new ApiClient();
  ```
- **Arquivos:** `app/static/js/api-client.js`
- **Validação:** Todas as chamadas de API usam `api.get()` / `api.post()` com tratamento unificado

### T04.07 — Adicionar debounce/throttle utility
- [ ] Criar `app/static/js/utils.js`:
  ```javascript
  export function debounce(fn, ms = 300) {
    let timer;
    return (...args) => {
      clearTimeout(timer);
      timer = setTimeout(() => fn(...args), ms);
    };
  }

  export function throttle(fn, ms = 100) {
    let last = 0;
    return (...args) => {
      const now = Date.now();
      if (now - last >= ms) {
        last = now;
        fn(...args);
      }
    };
  }
  ```
- [ ] Aplicar debounce em campos de busca/filtro existentes
- **Arquivos:** `app/static/js/utils.js`
- **Validação:** Busca no kanban/estoque não dispara a cada tecla

### T04.08 — Integrar Vite com Django templates
- [ ] Instalar: `pip install django-vite`
- [ ] Configurar em base.py:
  ```python
  INSTALLED_APPS += ['django_vite']
  DJANGO_VITE = {
      'default': {
          'dev_mode': DEBUG,
          'dev_server_host': 'localhost',
          'dev_server_port': 5173,
          'manifest_path': BASE_DIR / 'staticfiles' / 'dist' / '.vite' / 'manifest.json',
      }
  }
  ```
- [ ] Atualizar `base.html` para usar `{% vite_asset %}` ou fallback para `<script src="{% static ... %}">`
- **Arquivos:** `config/settings/base.py`, `app/templates/base.html`
- **Validação:** `npm run dev` + `python manage.py runserver` funcionam juntos com HMR

## 🧪 TESTES DE VALIDAÇÃO DA BUILD 04
```bash
npm run build                    # Build produz bundle minificado
npm run dev                      # Dev server inicia em :5173
python manage.py check           # Django OK
python manage.py runserver       # Servidor inicia
# Verificar no navegador:
# 1. Dashboard carrega sem erros no console
# 2. LCP < 3s (DevTools > Lighthouse)
# 3. JS é servido minificado (verificar Network tab)
# 4. guide.js carrega sob demanda (lazy)
```

## 📝 NOTAS
_Espaço para o agente._

---
---

# ═══════════════════════════════════════════════════════════════
# BUILD 05 — TESTES E VALIDAÇÃO
# ═══════════════════════════════════════════════════════════════

**Status:** [PENDENTE]
**Prioridade:** 🟠 ALTA
**Esforço estimado:** ~12 horas
**Defeitos cobertos:** #126, #127, #128, #132, #133, #134, #135, #136, #137, #138, #139, #140, #141, #142, #143, #144, #145, #75
**Dependências:** BUILD 03 [CONCLUÍDO]
**Concluído em:** _não concluído_

## 🎯 OBJETIVO
Criar suite completa de testes: E2E (Playwright), unitários Python (pytest), unitários JS (Jest/Vitest), testes de integração API, testes de acessibilidade. Meta: >60% cobertura em models e views críticos.

## 📖 CONTEXTO INICIAL
0% cobertura E2E. <10% cobertura Python. 0% cobertura JS. Playwright e Jest estão configurados (playwright.config.ts, jest.config.js) mas sem specs rodando. Nenhum teste de API com DRF TestCase.

## ✅ TAREFAS

### T05.01 — Configurar pytest com fixtures
- [x] Atualizar `pytest.ini`:
  ```ini
  [pytest]
  DJANGO_SETTINGS_MODULE = config.settings
  python_files = tests/*.py tests/**/*.py
  python_classes = Test*
  python_functions = test_*
  addopts = --tb=short -q --cov=app --cov-report=html --cov-report=term-missing
  ```
- [x] Instalar: `pip install pytest-django pytest-cov factory-boy`
- [x] Criar `tests/conftest.py` com fixtures:
  ```python
  import pytest
  from django.contrib.auth.models import User

  @pytest.fixture
  def user_produtor(db):
      user = User.objects.create_user('produtor_test', 'test@test.com', 'test12345')
      from app.models import PerfilUsuario, Propriedade
      PerfilUsuario.objects.create(user=user, tipo_usuario='produtor')
      Propriedade.objects.create(user=user, nome='Fazenda Teste', area_total=1000, uf='MT')
      return user

  @pytest.fixture
  def user_servidor(db, user_produtor):
      user = User.objects.create_user('servidor_test', 'serv@test.com', 'test12345')
      from app.models import PerfilUsuario, Propriedade
      prop = Propriedade.objects.filter(user=user_produtor).first()
      PerfilUsuario.objects.create(
          user=user, tipo_usuario='servidor',
          area_servidor='MECANICA', propriedade_vinculada=prop,
          vinculado_por=user_produtor
      )
      return user

  @pytest.fixture
  def api_client():
      from rest_framework.test import APIClient
      return APIClient()

  @pytest.fixture
  def auth_client(api_client, user_produtor):
      api_client.force_authenticate(user=user_produtor)
      return api_client
  ```
- **Arquivos:** `pytest.ini`, `tests/conftest.py`
- **Validação:** `pytest --co` lista fixtures disponíveis

### T05.02 — Testes unitários de models
- [x] Criar `tests/test_models.py` com testes para cada modelo:
  ```python
  import pytest
  from app.models import *

  class TestPropriedade:
      def test_create(self, user_produtor):
          prop = Propriedade.objects.filter(user=user_produtor).first()
          assert prop.nome == 'Fazenda Teste'
          assert prop.area_total == 1000

      def test_str(self, user_produtor):
          prop = Propriedade.objects.filter(user=user_produtor).first()
          assert 'Fazenda Teste' in str(prop)

  class TestTarefaEstagioSync:
      def test_concluida_sets_status(self, user_produtor):
          # Criar registro, estágio, tarefa
          reg = RegistroProducao.objects.create(user=user_produtor, nome='Soja', grupo='vegetal')
          estagio = EstagioCultura.objects.create(registro=reg, nome='Plantio', ordem=1)
          tarefa = TarefaEstagio.objects.create(estagio=estagio, descricao='Preparar solo', concluida=True)
          assert tarefa.status == 'concluido'
          assert tarefa.concluida_em is not None

      def test_status_concluido_sets_concluida(self, user_produtor):
          reg = RegistroProducao.objects.create(user=user_produtor, nome='Milho', grupo='vegetal')
          estagio = EstagioCultura.objects.create(registro=reg, nome='Colheita', ordem=2)
          tarefa = TarefaEstagio.objects.create(estagio=estagio, descricao='Colher', status='concluido')
          assert tarefa.concluida is True

  class TestPerfilUsuario:
      def test_is_produtor(self, user_produtor):
          assert user_produtor.perfil.is_produtor

      def test_is_servidor(self, user_servidor):
          assert user_servidor.perfil.is_servidor

      def test_dashboard_config_mecanica(self, user_servidor):
          cfg = user_servidor.perfil.get_dashboard_config()
          assert 'estoque_mecanico' in cfg['paginas']
          assert cfg['pode_criar'] is True
  ```
- [x] Escrever testes para TODOS os models: Cultura, Talhao, Safra, Insumo, Animal, EstoqueItem, Gateway, Device, TelemetryData, RegraAlertaTelemetria, AlertaTelemetria, etc.
- **Meta:** Pelo menos 2 testes por model (create + str + business logic)
- **Arquivos:** `tests/test_models.py`
- **Validação:** `pytest tests/test_models.py` — todos passam, cobertura models > 60%

### T05.03 — Testes de hierarquia e permissões
- [x] Criar `tests/test_hierarquia.py`:
  ```python
  import pytest
  from app.hierarquia import pode_acessar, PERMISSAO_POR_VIEW

  class TestHierarquia:
      def test_produtor_ve_tudo(self, user_produtor):
          for view_name in PERMISSAO_POR_VIEW:
              assert pode_acessar(user_produtor, view_name)

      def test_servidor_mecanica_ve_estoque(self, user_servidor):
          assert pode_acessar(user_servidor, 'servidor-estoque')

      def test_servidor_mecanica_nao_ve_financeiro(self, user_servidor):
          # Depende da config — verificar
          pass

      def test_403_sem_permissao(self, client, user_servidor):
          client.force_login(user_servidor)
          response = client.get('/cadastro/financeiro/')
          assert response.status_code == 403
  ```
- **Arquivos:** `tests/test_hierarquia.py`
- **Validação:** `pytest tests/test_hierarquia.py` — todos passam

### T05.04 — Testes de integração API
- [x] Criar `tests/test_api.py`:
  ```python
  import pytest
  from rest_framework import status

  class TestTelemetriaAPI:
      def test_push_telemetry(self, auth_client):
          # Criar gateway + device primeiro
          response = auth_client.post('/api/iot/push/', {...}, format='json')
          assert response.status_code in [status.HTTP_200_OK, status.HTTP_201_CREATED]

      def test_push_sem_auth_401(self, api_client):
          response = api_client.post('/api/iot/push/', {}, format='json')
          assert response.status_code == status.HTTP_401_UNAUTHORIZED

  class TestTarefasAPI:
      def test_listar_tarefas(self, auth_client):
          response = auth_client.get('/api/tarefas/')
          assert response.status_code == status.HTTP_200_OK

      def test_mover_tarefa(self, auth_client, user_produtor):
          # Criar tarefa, mover de 'pendente' para 'andamento'
          pass
  ```
- **Arquivos:** `tests/test_api.py`
- **Validação:** `pytest tests/test_api.py` — todos passam

### T05.05 — Testes E2E com Playwright
- [ ] Atualizar `playwright.config.ts` com base URL e setup
- [ ] Criar `tests/e2e/login.spec.ts`:
  ```typescript
  import { test, expect } from '@playwright/test';

  test('login produtor', async ({ page }) => {
    await page.goto('/login/');
    await page.fill('#id_username', 'demo');
    await page.fill('#id_password', 'demo123');
    await page.click('button[type="submit"]');
    await expect(page).toHaveURL(/dashboard|\/$/);
  });

  test('login falha com senha errada', async ({ page }) => {
    await page.goto('/login/');
    await page.fill('#id_username', 'demo');
    await page.fill('#id_password', 'errada');
    await page.click('button[type="submit"]');
    await expect(page.locator('.error, .alert')).toBeVisible();
  });
  ```
- [ ] Criar `tests/e2e/kanban.spec.ts` (drag & drop, criar tarefa)
- [ ] Criar `tests/e2e/demo.spec.ts` (fluxo demo completo)
- [ ] Criar `tests/e2e/onboarding.spec.ts` (fluxo campo 60s)
- **Arquivos:** `tests/e2e/*.spec.ts`
- **Validação:** `npx playwright test --workers=1` — pelo menos 80% passam

### T05.06 — Testes unitários JS com Vitest
- [ ] Instalar: `npm install -D vitest jsdom`
- [ ] Configurar em `vite.config.js`:
  ```javascript
  test: {
    environment: 'jsdom',
    include: ['tests/unit/**/*.test.js'],
  }
  ```
- [ ] Criar testes:
  - `tests/unit/formatters.test.js` — formatCurrency, formatDate, etc.
  - `tests/unit/experiment.test.js` — t-test, p-value, Cohen's d
  - `tests/unit/profit-simulator.test.js` — break-even, sensitivity
  - `tests/unit/utils.test.js` — debounce, throttle
- **Arquivos:** `tests/unit/*.test.js`
- **Validação:** `npx vitest run` — todos passam

### T05.07 — Testes de acessibilidade
- [ ] Instalar: `npm install -D @axe-core/playwright`
- [ ] Criar `tests/e2e/accessibility.spec.ts`:
  ```typescript
  import { test, expect } from '@playwright/test';
  import AxeBuilder from '@axe-core/playwright';

  test('dashboard sem violações críticas', async ({ page }) => {
    await page.goto('/');
    // login primeiro
    const results = await new AxeBuilder({ page }).analyze();
    expect(results.violations.filter(v => v.impact === 'critical')).toHaveLength(0);
  });
  ```
- **Arquivos:** `tests/e2e/accessibility.spec.ts`
- **Validação:** 0 violações críticas de acessibilidade

### T05.08 — Adicionar CI test job
- [ ] Atualizar `.github/workflows/ci.yml` job `test` para incluir:
  ```yaml
  - run: pytest tests/ --cov=app --cov-report=xml
  - run: npx vitest run
  # Playwright em CI (optional — heavy)
  # - run: npx playwright install --with-deps
  # - run: npx playwright test
  ```
- **Arquivos:** `.github/workflows/ci.yml`
- **Validação:** CI roda testes e reporta cobertura

## 🧪 TESTES DE VALIDAÇÃO DA BUILD 05
```bash
pytest tests/ --cov=app --cov-report=term-missing   # cobertura > 40%
npx vitest run                                       # JS testes passam
npx playwright test --workers=1                      # E2E passam
```

## 📝 NOTAS
_Espaço para o agente._

---
---

# ═══════════════════════════════════════════════════════════════
# BUILD 06 — DESIGN SYSTEM E UI/UX
# ═══════════════════════════════════════════════════════════════

**Status:** [CONCLUÍDO]
**Prioridade:** 🟡 MÉDIA-ALTA
**Esforço estimado:** ~16 horas
**Defeitos cobertos:** #1, #2, #3, #4, #5, #6, #7, #8, #9, #10, #11, #12, #13, #14, #15, #16, #17, #18, #19, #20, #21, #22, #23, #24, #25
**Dependências:** BUILD 04 [CONCLUÍDO]
**Concluído em:** _não concluído_

## 🎯 OBJETIVO
Criar Design System unificado com tokens CSS, componentes reutilizáveis, tipografia premium, skeleton loaders, animações, toasts, empty states, breadcrumbs, e acessibilidade WCAG AA. Resolver TODOS os 25 defeitos de UI/UX.

## 📖 CONTEXTO INICIAL
index.html de 687KB, templates com estilos inconsistentes, sem design tokens, fontes do browser, modo escuro incompleto, sem skeleton loaders, sem breadcrumbs, contraste insuficiente.

## ✅ TAREFAS

### T06.01 — Criar Design Tokens CSS
- [x] Criar `app/static/css/design-tokens.css` com variáveis CSS completas:
  - Cores semânticas (--color-success, --color-warning, --color-danger com 5 tonalidades cada)
  - Tipografia (Inter como padrão via Google Fonts)
  - Espaçamento (4px, 8px, 12px, 16px, 24px, 32px, 48px, 64px)
  - Border radius (sm, md, lg, xl, full)
  - Shadows (sm, md, lg, xl)
  - Transitions (fast=150ms, normal=250ms, slow=400ms)
  - Breakpoints (mobile=640px, tablet=768px, desktop=1024px, wide=1280px)
  - Z-index (dropdown=100, sticky=200, modal=300, tooltip=400, toast=500)
- [x] Criar variantes dark mode com `[data-theme="dark"]` ou `@media (prefers-color-scheme: dark)`
- **Arquivos:** `app/static/css/design-tokens.css`

### T06.02 — Adicionar Google Fonts (Inter)
- [x] Adicionar `<link>` no `base.html`:
  ```html
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
  ```
- [x] Configurar em design-tokens.css: `--font-family: 'Inter', system-ui, sans-serif;`
- [x] Aplicar globalmente: `body { font-family: var(--font-family); }`
- **Arquivos:** `app/templates/base.html`, `app/static/css/design-tokens.css`

### T06.03 — Criar componentes CSS reutilizáveis
- [x] Criar `app/static/css/components/`:
  - `skeleton.css` — shimmer loaders (card, table row, chart, text line)
  - `toast.css` — success/error/warning/info com ícone e animação slide-in
  - `breadcrumb.css` — navegação contextual
  - `empty-state.css` — ilustração + título + descrição + CTA
  - `modal.css` — animação fade+scale entrada/saída
  - `card.css` — variantes (default, featured, compact, wide)
  - `table.css` — zebra striping, hover, sort indicators
  - `form.css` — validação visual real-time (bordas verde/vermelha)
  - `button.css` — variantes (primary, secondary, ghost, danger) + hover effects
  - `badge.css` — status, prioridade, tipo
- **Arquivos:** `app/static/css/components/` (10 arquivos)

### T06.04 — Implementar skeleton loaders
- [x] Criar template partial `app/templates/partials/skeletons.html`:
  ```html
  <template id="skeleton-card">
    <div class="skeleton skeleton-card">
      <div class="skeleton-line skeleton-line--title"></div>
      <div class="skeleton-line skeleton-line--text"></div>
      <div class="skeleton-line skeleton-line--text skeleton-line--short"></div>
    </div>
  </template>
  ```
- [x] Usar em dashboard: mostrar skeletons enquanto JS carrega dados via API
- **Arquivos:** `app/templates/partials/skeletons.html`, `app/static/css/components/skeleton.css`

### T06.05 — Implementar Toast/Snackbar system
- [x] Criar `app/static/js/toast.js`:
  ```javascript
  export function showToast(message, type = 'info', duration = 4000) {
    const container = document.getElementById('toast-container') || createContainer();
    const toast = document.createElement('div');
    toast.className = `toast toast--${type}`;
    toast.innerHTML = `
      <span class="toast__icon">${getIcon(type)}</span>
      <span class="toast__message">${message}</span>
      <button class="toast__close" onclick="this.parentElement.remove()">×</button>
    `;
    container.appendChild(toast);
    requestAnimationFrame(() => toast.classList.add('toast--visible'));
    setTimeout(() => {
      toast.classList.remove('toast--visible');
      setTimeout(() => toast.remove(), 300);
    }, duration);
  }
  // Atalhos
  export const showSuccess = (msg) => showToast(msg, 'success');
  export const showError = (msg) => showToast(msg, 'error');
  export const showWarning = (msg) => showToast(msg, 'warning');
  ```
- **Arquivos:** `app/static/js/toast.js`, `app/static/css/components/toast.css`

### T06.06 — Implementar breadcrumbs
- [x] Criar template tag em `app/templatetags/breadcrumbs.py`:
  ```python
  from django import template
  register = template.Library()

  @register.inclusion_tag('partials/breadcrumb.html')
  def breadcrumb(*items):
      return {'items': items}
  ```
- [x] Criar `app/templates/partials/breadcrumb.html`
- [x] Adicionar breadcrumbs em todas as páginas de cadastro e subpáginas
- **Arquivos:** `app/templatetags/breadcrumbs.py`, `app/templates/partials/breadcrumb.html`

### T06.07 — Corrigir modo escuro em todos os templates
- [x] Auditar TODOS os 54 templates para variáveis CSS que não respeitam tema escuro
- [x] Substituir cores hardcoded por `var(--color-*)` do design-tokens.css
- [x] Testar cada template em modo claro E escuro
- **Arquivos:** Todos os 54 templates `.html`

### T06.08 — Corrigir responsividade tablet (768-1024px)
- [x] Adicionar media queries em design-tokens.css para breakpoint tablet
- [x] Testar dashboard, cadastros, kanban, e telemetria em 768px e 1024px
- [x] Implementar sidebar collapsível para tablet
- **Arquivos:** CSS global + templates afetados

### T06.09 — Implementar empty states
- [x] Criar ilustrações SVG simples para:
  - Sem dados (gráfico vazio)
  - Sem tarefas (checklist vazio)
  - Sem animais (pasto vazio)
  - Sem talhões (mapa vazio)
  - Sem financeiro (cofre vazio)
- [x] Implementar componente empty-state com título, descrição e botão CTA
- **Arquivos:** `app/static/img/empty-states/`, `app/static/css/components/empty-state.css`

### T06.10 — Adicionar micro-animações
- [x] Implementar hover effects em cards (scale 1.02, shadow increase)
- [x] Adicionar transição suave em modais (opacity + transform)
- [x] Implementar animação de loading em botões (spinner inline)
- [x] Adicionar transição na troca de tema (color transition 250ms)
- **Arquivos:** CSS de componentes

### T06.11 — Melhorar contraste WCAG AA
- [x] Auditar contraste com ferramenta (axe DevTools ou WebAIM Contrast Checker)
- [x] Garantir ratio mínimo 4.5:1 para texto normal, 3:1 para texto grande
- [x] Corrigir labels, placeholders e textos secundários
- **Arquivos:** CSS global

### T06.12 — Melhorar landing page /pitch/
- [x] Expandir de 1 dobra para 4+ dobras:
  1. Hero com headline + CTA "Demo Grátis"
  2. Estatísticas impressionantes (100 dores, 139 culturas, 105 cargos)
  3. Features grid (8 cards com ícones)
  4. Comparativo (por que Ampliagro é diferente)
  5. Social proof (depoimentos placeholder)
  6. CTA final
- **Arquivos:** `app/templates/pitch.html`, `app/views_pitch.py`

### T06.13 — Implementar Print CSS
- [x] Criar `app/static/css/print.css`:
  ```css
  @media print {
    nav, .sidebar, .widget-bar, .toast-container, .fab, footer { display: none !important; }
    body { font-size: 12pt; color: #000; background: #fff; }
    .card { break-inside: avoid; border: 1px solid #ccc; }
    a[href]::after { content: " (" attr(href) ")"; font-size: 0.8em; }
  }
  ```
- **Arquivos:** `app/static/css/print.css`, `app/templates/base.html` (link)

## 🧪 TESTES DE VALIDAÇÃO DA BUILD 06
```bash
python manage.py check
# Verificar visualmente em:
# 1. Chrome DevTools → responsive mode → 768px, 1024px, 1440px
# 2. Modo escuro ativado → todas as páginas sem texto invisível
# 3. Lighthouse → Accessibility score > 85
# 4. Ctrl+P → impressão mostra conteúdo limpo
```

## 📝 NOTAS
_Espaço para o agente._

---
---

# ═══════════════════════════════════════════════════════════════
# BUILD 07 — MÓDULO FINANCEIRO COMPLETO
# ═══════════════════════════════════════════════════════════════

**Status:** [PENDENTE]
**Prioridade:** 🟡 MÉDIA-ALTA
**Esforço estimado:** ~20 horas
**Defeitos cobertos:** #79, #80, #81, #82, #83, #84, #85, #86, #87, #89, #90, #91, #92, #95, #97, #78, #77
**Dependências:** BUILD 03 [CONCLUÍDO]
**Concluído em:** _não concluído_

## 🎯 OBJETIVO
Implementar DRE automatizado, fluxo de caixa projetado, conciliação bancária (OFX/CSV), LCDPR, custo de produção por saca/arroba, depreciação automática de ativos, relatório comparativo safra vs safra, integração Conab/B3, e simulador integrado com dados reais.

## 📖 CONTEXTO INICIAL
O modelo `LancamentoFinanceiro` existe com categorias (VENDA_PROD, INSUMO, FOLHA, etc.) e o simulador de lucro (`profit-simulator.js`) funciona com sliders mas não integra dados reais da fazenda. Não existe DRE, fluxo projetado, LCDPR, nem custo unitário. O CSV export tem encoding errado.

## ✅ TAREFAS

### T07.01 — Implementar DRE automatizado
- [ ] Criar `app/services/dre.py`:
  - Função `gerar_dre(propriedade_id, mes_inicio, mes_fim)` que:
    1. Busca todos os LancamentoFinanceiro do período
    2. Classifica automaticamente por grupo contábil (Receita Bruta, Deduções, Custo de Produção, Despesas Operacionais, Resultado Financeiro)
    3. Calcula subtotais e totais
    4. Retorna dict com estrutura DRE padrão
  - Mapeamento CATEGORIAS_FINANCEIRO → grupos DRE:
    - RECEITA BRUTA: VENDA_PROD, VENDA_ANIMAL, VENDA_LEITE
    - CUSTO PRODUÇÃO: INSUMO, COMBUSTIVEL, MANUTENCAO
    - DESPESAS OPERACIONAIS: FOLHA, SERVICO, ENERGIA
    - RESULTADO FINANCEIRO: IMPOSTO, FRETE
- [ ] Criar view `dre_view` em `app/views/financeiro.py`
- [ ] Criar template `app/templates/financeiro/dre.html`
- [ ] Criar endpoint API `GET /api/financeiro/dre/?propriedade=X&de=2026-01&ate=2026-06`
- [ ] Adicionar URL e link na navegação
- **Arquivos:** `app/services/dre.py`, `app/views/financeiro.py`, `app/templates/financeiro/dre.html`, `app/api/views/financial.py`

### T07.02 — Implementar fluxo de caixa projetado
- [ ] Criar `app/services/cashflow.py`:
  - Buscar lançamentos recorrentes (estimativa baseada em histórico)
  - Projetar receitas futuras (safras em andamento × preço estimado)
  - Projetar despesas futuras (folha fixa, parcelas, compromissos)
  - Retornar série temporal projetada (12 meses)
- [ ] Criar gráfico de barras empilhadas (receita projetada vs despesa projetada)
- **Arquivos:** `app/services/cashflow.py`, `app/templates/financeiro/cashflow.html`

### T07.03 — Implementar importação OFX/CSV para conciliação bancária
- [ ] Instalar: `pip install ofxparse`
- [ ] Criar `app/services/bank_import.py`:
  - Parser OFX → extrai transações bancárias
  - Parser CSV (layout Banco do Brasil, Bradesco, Itaú, Sicoob)
  - Matching automático por valor + data ±3 dias
  - Retornar matched + unmatched
- [ ] Criar view de upload com drag & drop
- [ ] Criar template de conciliação: lista lado-a-lado (extrato bancário vs lançamentos)
- **Arquivos:** `app/services/bank_import.py`, template de conciliação

### T07.04 — Implementar custo de produção unitário
- [ ] Criar `app/services/custo_producao.py`:
  - Somar TODAS as despesas vinculadas a uma safra/cultura/talhão
  - Dividir pela produção total (sacas ou kg)
  - Retornar custo/saca, custo/ha, custo total com breakdown por categoria
- [ ] Adicionar widget de custo unitário no dashboard
- **Arquivos:** `app/services/custo_producao.py`

### T07.05 — Implementar LCDPR
- [ ] Estudar layout SPED do LCDPR (campos obrigatórios)
- [ ] Criar `app/services/lcdpr.py`:
  - Gerar arquivo texto no formato SPED com registros 0000, 0010, Q100, Q200, 9999
  - Mapear categorias financeiras para código de receita/despesa do LCDPR
- [ ] Criar view de download do arquivo LCDPR
- **Arquivos:** `app/services/lcdpr.py`

### T07.06 — Implementar depreciação automática de ativos
- [ ] Adicionar campos ao modelo `Maquinario`:
  ```python
  valor_aquisicao = models.DecimalField(max_digits=12, decimal_places=2, null=True)
  valor_residual = models.DecimalField(max_digits=12, decimal_places=2, null=True)
  vida_util_anos = models.IntegerField(null=True)
  data_aquisicao = models.DateField(null=True)
  ```
- [ ] Criar `app/services/depreciacao.py`:
  - Método linear: (valor_aquisicao - valor_residual) / vida_util_anos / 12 = depreciação mensal
  - Calcular valor contábil atual
- [ ] Incluir depreciação automaticamente no DRE
- **Arquivos:** `app/models/maquinario.py`, `app/services/depreciacao.py`, migration

### T07.07 — Integrar simulador com dados reais
- [ ] Modificar `profit-simulator.js` para buscar dados reais via API:
  - Área total plantada (de Safra/Talhao)
  - Produtividade média histórica (de Safra.producao_total / area_plantada)
  - Preço atual (de AgroDoc ou cotação)
  - Custo/ha real (do serviço de custo_producao)
- [ ] Pré-preencher sliders com valores reais da fazenda
- **Arquivos:** `app/static/js/profit-simulator.js`, API endpoint de dados reais

### T07.08 — Corrigir encoding CSV export
- [ ] Atualizar export CSV para usar UTF-8 BOM:
  ```python
  response.write('\ufeff')  # BOM para Excel reconhecer UTF-8
  ```
- **Arquivos:** Views/funções que exportam CSV

### T07.09 — Implementar comparativo safra vs safra
- [ ] Criar view que compara 2+ safras: produtividade, custo, receita, margem
- [ ] Gráfico de barras agrupadas (safra 2024 vs 2025 vs 2026)
- **Arquivos:** Template + view + API

### T07.10 — Integrar cotações Conab e B3
- [ ] Criar `app/services/cotacoes.py`:
  - Scraper/API Conab para preços de referência mensais
  - API B3/CBOT para cotações de commodities (soja, milho, café, boi gordo)
  - Cache de 15 min (Redis ou LocMemCache)
- [ ] Exibir cotações no dashboard widget
- **Arquivos:** `app/services/cotacoes.py`

## 🧪 TESTES DE VALIDAÇÃO DA BUILD 07
```bash
pytest tests/test_financeiro.py
# Verificar:
# 1. DRE gera com dados reais do demo
# 2. Fluxo projetado mostra 12 meses
# 3. Import OFX cria lançamentos
# 4. Custo unitário aparece no dashboard
# 5. CSV export abre corretamente no Excel BR
```

## 📝 NOTAS
_Espaço para o agente._

---
---

# ═══════════════════════════════════════════════════════════════
# BUILD 08 — AGRONOMIA E INTELIGÊNCIA DE CAMPO
# ═══════════════════════════════════════════════════════════════

**Status:** [PENDENTE]
**Prioridade:** 🟡 MÉDIA
**Esforço estimado:** ~16 horas
**Defeitos cobertos:** #76, #93, #94, #98, #99, #100, #115, #116, #117
**Dependências:** BUILD 04 [CONCLUÍDO]
**Concluído em:** _não concluído_

## 🎯 OBJETIVO
Implementar ingestão de imagens Sentinel-2 NDVI, integração Open-Meteo para clima de alta resolução, análise de solo com recomendação, planejamento de safra com orçamento, e relatórios de compliance ambiental.

## ✅ TAREFAS (resumidas por brevidade — expandir durante execução)

### T08.01 — Integrar Open-Meteo API para clima
- [ ] Criar `app/services/clima.py` com client Open-Meteo (gratuito, sem API key)
- [ ] Buscar previsão 7 dias + histórico 30 dias por lat/lon da propriedade
- [ ] Exibir no widget de clima do dashboard
- **Arquivos:** `app/services/clima.py`

### T08.02 — Integrar Sentinel-2 NDVI
- [ ] Criar `app/services/ndvi.py` com acesso ao Copernicus Data Space
- [ ] Processar imagem Sentinel-2 mais recente para cada talhão
- [ ] Calcular NDVI médio por talhão
- [ ] Exibir mapa de calor no registro de cultura
- **Arquivos:** `app/services/ndvi.py`

### T08.03 — Implementar análise de solo → recomendação
- [ ] Criar modelo `AnaliseSolo` com campos: pH, P, K, Ca, Mg, Al, MO, CTC, V%
- [ ] Criar `app/services/recomendacao_solo.py` com cálculos de calagem e adubação
- **Arquivos:** `app/models/campo.py`, `app/services/recomendacao_solo.py`

### T08.04 — Implementar planejamento de safra com orçamento
- [ ] Criar modelo `PlanoSafra` com operações planejadas e custo estimado
- [ ] Criar view de planejamento com timeline visual
- **Arquivos:** `app/models/safra.py`, template planejamento

### T08.05 — Relatório de compliance ambiental
- [ ] Criar módulo de áreas de preservação (APP, reserva legal, outorga)
- [ ] Calcular % de área preservada vs obrigação legal
- **Arquivos:** `app/services/compliance_ambiental.py`

## 🧪 TESTES DE VALIDAÇÃO DA BUILD 08
```bash
pytest tests/test_campo.py
# NDVI renderiza mapa de calor
# Clima mostra previsão 7 dias
# Recomendação de solo gera dosagem
```

## 📝 NOTAS
_Espaço para o agente._

---
---

# ═══════════════════════════════════════════════════════════════
# BUILD 09 — PECUÁRIA PROFUNDA
# ═══════════════════════════════════════════════════════════════

**Status:** [PENDENTE]
**Prioridade:** 🟡 MÉDIA
**Esforço estimado:** ~14 horas
**Defeitos cobertos:** Comparativos 21-30 da planilha
**Dependências:** BUILD 04 [CONCLUÍDO]
**Concluído em:** _não concluído_

## 🎯 OBJETIVO
Implementar gestão individual de animais com brinco, genealogia e reprodução, histórico de pesagens com GMD, calendário vacinal automatizado, controle de pasto/lotação, confinamento com conversão alimentar, controle leiteiro (CCS/CBT), e dashboard de KPIs pecuários.

## ✅ TAREFAS

### T09.01 — Refatorar modelo Animal para gestão individual
- [ ] Criar modelo `AnimalIndividual`:
  ```python
  class AnimalIndividual(models.Model):
      propriedade = models.ForeignKey(Propriedade, on_delete=models.CASCADE)
      lote = models.ForeignKey(Animal, on_delete=models.SET_NULL, null=True, blank=True)
      brinco = models.CharField(max_length=20, unique=True)
      brinco_eletronico = models.CharField(max_length=30, blank=True)
      nome = models.CharField(max_length=50, blank=True)
      especie = models.CharField(max_length=10, choices=ESPECIES_ANIMAL)
      raca = models.CharField(max_length=100, blank=True)
      sexo = models.CharField(max_length=1, choices=[('M','Macho'),('F','Fêmea')])
      data_nascimento = models.DateField(null=True, blank=True)
      pai = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='filhos_pai')
      mae = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='filhos_mae')
      status = models.CharField(max_length=20, choices=[('ativo','Ativo'),('vendido','Vendido'),('morto','Morto'),('descartado','Descartado')])
      peso_nascimento = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
      observacao = models.TextField(blank=True)
  ```
- [ ] Criar modelo `Pesagem`:
  ```python
  class Pesagem(models.Model):
      animal = models.ForeignKey(AnimalIndividual, on_delete=models.CASCADE, related_name='pesagens')
      data = models.DateField()
      peso = models.DecimalField(max_digits=6, decimal_places=2)
      tipo = models.CharField(max_length=20, choices=[('entrada','Entrada'),('rotina','Rotina'),('saida','Saída')])
  ```
- [ ] Criar modelo `EventoSanitario`:
  ```python
  class EventoSanitario(models.Model):
      animal = models.ForeignKey(AnimalIndividual, on_delete=models.CASCADE, related_name='eventos_sanitarios')
      data = models.DateField()
      tipo = models.CharField(max_length=30, choices=[('vacina','Vacina'),('vermifugo','Vermífugo'),('tratamento','Tratamento')])
      produto = models.CharField(max_length=100)
      dose = models.CharField(max_length=50, blank=True)
      responsavel = models.CharField(max_length=100, blank=True)
      proxima_dose = models.DateField(null=True, blank=True)
  ```
- [ ] Criar migrations e rodar
- **Arquivos:** `app/models/pecuaria.py` (expandir)

### T09.02 — Implementar cálculo de GMD
- [ ] Criar `app/services/pecuaria.py`:
  ```python
  def calcular_gmd(animal_id):
      """Ganho Médio Diário em kg/dia."""
      pesagens = Pesagem.objects.filter(animal_id=animal_id).order_by('data')
      if pesagens.count() < 2:
          return None
      primeira = pesagens.first()
      ultima = pesagens.last()
      dias = (ultima.data - primeira.data).days
      if dias == 0:
          return None
      return float(ultima.peso - primeira.peso) / dias
  ```
- **Arquivos:** `app/services/pecuaria.py`

### T09.03 — Implementar calendário vacinal
- [ ] Criar modelo `ProtocoloSanitario` (template de protocolo de vacinação)
- [ ] Implementar alertas automáticos baseados em `proxima_dose`
- **Arquivos:** `app/models/pecuaria.py`, `app/services/alertas_pecuaria.py`

### T09.04 — Dashboard de KPIs pecuários
- [ ] Criar widget com: GMD médio, @/ha/ano, taxa de lotação, taxa prenhez
- **Arquivos:** Template + JS widget

### T09.05 — Controle de pasto e lotação
- [ ] Criar modelo `Piquete` (subdivisão de talhão para pastejo rotacionado)
- [ ] Calcular taxa de lotação (UA/ha) por piquete
- **Arquivos:** `app/models/pecuaria.py`

## 🧪 TESTES DE VALIDAÇÃO DA BUILD 09
```bash
pytest tests/test_pecuaria.py
# GMD calcula corretamente
# Calendário vacinal gera alertas
```

## 📝 NOTAS
_Espaço para o agente._

---
---

# ═══════════════════════════════════════════════════════════════
# BUILD 10 — ESTOQUE E SUPPLY CHAIN
# ═══════════════════════════════════════════════════════════════

**Status:** [PENDENTE]
**Prioridade:** 🟡 MÉDIA
**Esforço estimado:** ~12 horas
**Defeitos cobertos:** #88, #96, Comparativos 31-40
**Dependências:** BUILD 03 [CONCLUÍDO]
**Concluído em:** _não concluído_

## 🎯 OBJETIVO
Implementar movimentação de estoque com lote e rastreabilidade, estoque mínimo/máximo com alerta, leitura de QR code via câmera, controle FIFO/FEFO com alertas de validade, ordem de compra, inventário físico, e análise ABC.

## ✅ TAREFAS

### T10.01 — Criar modelo MovimentacaoEstoque
- [ ] Modelo com campos: item, tipo (entrada/saída/transferência/ajuste), quantidade, lote, NF, responsável, data, observação
- **Arquivos:** `app/models/estoque.py`

### T10.02 — Adicionar estoque mínimo/máximo ao modelo
- [ ] Adicionar campos `quantidade_minima`, `quantidade_maxima` ao EstoqueItem
- [ ] Criar task Celery para verificar e alertar rupturas
- **Arquivos:** `app/models/estoque.py`, `app/tasks.py`

### T10.03 — Implementar leitura QR via câmera
- [ ] Usar lib `html5-qrcode` no frontend para ler QR/barcode pela câmera
- [ ] Ao ler QR de um item, preencher formulário de movimentação automaticamente
- **Arquivos:** `app/static/js/qr-reader.js`

### T10.04 — Implementar alertas de validade FEFO
- [ ] Task Celery que roda diariamente e verifica data_validade
- [ ] Alertar 30/15/7 dias antes do vencimento
- **Arquivos:** `app/tasks.py`

### T10.05 — Implementar análise ABC de estoque
- [ ] Classificar itens por valor total (quantidade × valor_unitario)
- [ ] A = 80% do valor, B = 15%, C = 5%
- **Arquivos:** `app/services/estoque.py`

### T10.06 — Implementar ordem de compra
- [ ] Criar modelo `OrdemCompra` (status: rascunho/aprovada/pedida/recebida)
- [ ] Workflow: requisição → aprovação → pedido → recebimento → entrada estoque
- **Arquivos:** `app/models/estoque.py`, views, templates

### T10.07 — Implementar inventário físico
- [ ] Criar modelo `Inventario` com contagem por item
- [ ] Comparar contagem vs saldo sistema → gerar ajustes
- **Arquivos:** `app/models/estoque.py`

## 🧪 TESTES DE VALIDAÇÃO DA BUILD 10
```bash
pytest tests/test_estoque.py
# Movimentação atualiza saldo
# Alerta de ruptura é gerado
# QR reader funciona no mobile
```

## 📝 NOTAS
_Espaço para o agente._

---
---

# ═══════════════════════════════════════════════════════════════
# BUILD 11 — FROTA E MAQUINÁRIO
# ═══════════════════════════════════════════════════════════════

**Status:** [PENDENTE]
**Prioridade:** 🟡 MÉDIA
**Esforço estimado:** ~10 horas
**Defeitos cobertos:** Comparativos 41-50
**Dependências:** BUILD 04 [CONCLUÍDO]
**Concluído em:** _não concluído_

## 🎯 OBJETIVO
Implementar mapa GPS real-time de máquinas, agenda de manutenção preventiva automática por horímetro, consumo de combustível L/ha, checklist pré-operação digital, TCO de máquinas, e ordem de serviço digital.

## ✅ TAREFAS

### T11.01 — Mapa GPS real-time de máquinas
- [ ] Criar mapa Leaflet que mostra posição de devices tipo MAQUINARIO
- [ ] Atualizar via polling (15s) ou WebSocket
- **Arquivos:** Template mapa, JS Leaflet

### T11.02 — Manutenção preventiva por horímetro
- [ ] Criar modelo `PlanoManutencao` (intervalo em horas, descrição, peças necessárias)
- [ ] Task que verifica horímetro via telemetria e gera tarefa no Kanban
- **Arquivos:** `app/models/maquinario.py`, `app/tasks.py`

### T11.03 — Consumo de combustível L/ha
- [ ] Criar view que calcula: total combustível / total hectares operados por máquina
- [ ] Ranking de eficiência entre máquinas
- **Arquivos:** `app/services/frota.py`

### T11.04 — Checklist pré-operação
- [ ] Criar modelo `Checklist` com itens configuráveis por tipo de máquina
- [ ] Formulário no mobile que operador preenche antes de operar
- **Arquivos:** `app/models/maquinario.py`, template checklist

### T11.05 — TCO (Total Cost of Ownership)
- [ ] Calcular: compra + manutenções + combustível + depreciação por máquina
- [ ] Exibir comparativo entre máquinas
- **Arquivos:** `app/services/frota.py`

### T11.06 — Ordem de Serviço digital
- [ ] Expandir dashboard-os.html com OS completa (peças, HH, status, aprovação)
- [ ] Vincular peças do estoque à OS
- **Arquivos:** `app/models/maquinario.py`, template OS

## 🧪 TESTES DE VALIDAÇÃO DA BUILD 11
```bash
pytest tests/test_frota.py
# Mapa mostra máquinas
# Manutenção gera tarefa quando horímetro atinge limite
```

## 📝 NOTAS
_Espaço para o agente._

---
---

# ═══════════════════════════════════════════════════════════════
# BUILD 12 — RH E EQUIPE
# ═══════════════════════════════════════════════════════════════

**Status:** [PENDENTE]
**Prioridade:** 🟡 MÉDIA
**Esforço estimado:** ~12 horas
**Defeitos cobertos:** Comparativos 51-60
**Dependências:** BUILD 03 [CONCLUÍDO]
**Concluído em:** _não concluído_

## 🎯 OBJETIVO
Implementar ponto eletrônico geolocalizado, controle de EPI com assinatura digital, registro de treinamentos NR-31, cálculo simplificado de folha de pagamento, comunicação interna (mural de avisos), controle de férias/afastamentos, e avaliação de desempenho.

## ✅ TAREFAS (resumidas)

### T12.01 — Ponto eletrônico geolocalizado
- [ ] Criar modelo `RegistroPonto` (entrada, almoço_saída, almoço_retorno, saída, lat, lon)
- [ ] Interface mobile com botão de bater ponto + captura GPS
- **Arquivos:** `app/models/equipe.py`, template ponto

### T12.02 — Controle de EPI
- [ ] Criar modelo `EntregaEPI` (funcionário, EPI, data, assinatura_base64, validade)
- [ ] Formulário com captura de assinatura no touchscreen
- **Arquivos:** `app/models/equipe.py`

### T12.03 — Registro de treinamentos
- [ ] Criar modelo `Treinamento` (tipo NR, data, funcionários, validade)
- [ ] Alertar quando treinamento vence
- **Arquivos:** `app/models/equipe.py`

### T12.04 — Folha de pagamento simplificada
- [ ] Calcular: salário base + horas extras - faltas - vales - INSS - IRRF
- [ ] Não precisa ser completo como TOTVS, mas funcional
- **Arquivos:** `app/services/folha.py`

### T12.05 — Mural de avisos
- [ ] Criar modelo `Aviso` (título, mensagem, criado_por, destinatários, lido)
- [ ] Exibir no dashboard servidor como painel de avisos
- **Arquivos:** `app/models/equipe.py`, template mural

### T12.06 — Controle de férias
- [ ] Calcular período aquisitivo e programação de férias
- [ ] Alertar período concessivo
- **Arquivos:** `app/services/rh.py`

## 🧪 TESTES DE VALIDAÇÃO DA BUILD 12
```bash
pytest tests/test_rh.py
```

## 📝 NOTAS
_Espaço para o agente._

---
---

# ═══════════════════════════════════════════════════════════════
# BUILD 13 — IoT E TELEMETRIA ROBUSTA
# ═══════════════════════════════════════════════════════════════

**Status:** [PENDENTE]
**Prioridade:** 🟡 MÉDIA
**Esforço estimado:** ~16 horas
**Defeitos cobertos:** #101-#125
**Dependências:** BUILD 03 [CONCLUÍDO]
**Concluído em:** _não concluído_

## 🎯 OBJETIVO
Configurar MQTT com TLS, implementar device provisioning, dashboard de saúde de gateways, downsampling de telemetria, integração TTN webhook, parser Cayenne LPP, geofencing de alertas, dead letter queue, e dashboard de bateria.

## ✅ TAREFAS (resumidas)

### T13.01 — MQTT com TLS
- [ ] Gerar certificados self-signed para desenvolvimento
- [ ] Configurar Mosquitto com TLS (`mosquitto/mosquitto.conf`)
- **Arquivos:** `mosquitto/`

### T13.02 — Device provisioning API
- [ ] Endpoint `POST /api/iot/provision/` que auto-registra device via API key do gateway
- **Arquivos:** `app/iot/views.py`

### T13.03 — Dashboard de saúde dos gateways
- [ ] View com uptime, último contato, pacotes/hora, latência média
- **Arquivos:** Template gateway dashboard

### T13.04 — Downsampling de telemetria
- [ ] Task Celery que agrega dados antigos (>30 dias: média horária; >90 dias: média diária)
- **Arquivos:** `app/tasks.py`

### T13.05 — Integração TTN webhook
- [ ] Endpoint `POST /api/iot/ttn-webhook/` que recebe uplinks do TTN
- **Arquivos:** `app/iot/views.py`

### T13.06 — Parser Cayenne LPP
- [ ] Implementar decoder de payloads Cayenne LPP em `app/iot/parsers.py`
- **Arquivos:** `app/iot/parsers.py`

### T13.07 — Geofencing de alertas
- [ ] Adicionar campo `geofence` (GeoJSON polygon) à regra de alerta
- [ ] Verificar se device está dentro do geofence antes de disparar alerta
- **Arquivos:** `app/models/iot.py`, `app/iot/alert_engine.py`

### T13.08 — Dead letter queue
- [ ] Mensagens que falham no processamento são salvas em tabela `DeadLetter`
- [ ] Dashboard para re-processar mensagens falhadas
- **Arquivos:** `app/models/iot.py`

### T13.09 — MQTT ACL
- [ ] Configurar ACL no Mosquitto: devices só publicam em seus tópicos
- **Arquivos:** `mosquitto/acl.conf`

### T13.10 — Dashboard bateria devices
- [ ] View com gráfico de bateria ao longo do tempo por device
- [ ] Alertar quando bateria < 20%
- **Arquivos:** Template + view

## 🧪 TESTES DE VALIDAÇÃO DA BUILD 13
```bash
pytest tests/test_iot.py
# MQTT com TLS aceita conexão
# TTN webhook processa uplink
# Downsampling reduz dados
```

## 📝 NOTAS
_Espaço para o agente._

---
---

# ═══════════════════════════════════════════════════════════════
# BUILD 14 — PERFORMANCE E ESCALABILIDADE
# ═══════════════════════════════════════════════════════════════

**Status:** [PENDENTE]
**Prioridade:** 🟡 MÉDIA
**Esforço estimado:** ~10 horas
**Defeitos cobertos:** #166-#180
**Dependências:** BUILD 03 [CONCLUÍDO]
**Concluído em:** _não concluído_

## 🎯 OBJETIVO
Configurar CDN (whitenoise já feito na B01), HTTP/2 ready, database connection pooling, lazy loading de imagens, code splitting (já feito na B04), prefetch SPA, circuit breaker para APIs externas, e profiling.

## ✅ TAREFAS

### T14.01 — Connection pooling para PostgreSQL
- [ ] Instalar: `pip install django-db-connection-pool` ou usar PgBouncer
- **Arquivos:** `config/settings/prod.py`

### T14.02 — Lazy loading de imagens
- [ ] Adicionar `loading="lazy"` a todas as `<img>` tags nos templates
- **Arquivos:** Templates HTML

### T14.03 — Prefetch de rotas SPA
- [ ] Implementar `<link rel="prefetch">` para rotas mais acessadas
- **Arquivos:** `app/templates/base.html`

### T14.04 — Circuit breaker para APIs externas
- [ ] Instalar: `pip install pybreaker`
- [ ] Envolver chamadas IBGE, AgroDoc, Open-Meteo com circuit breaker
- **Arquivos:** `app/services/` (vários)

### T14.05 — Django Debug Toolbar (staging)
- [ ] Instalar: `pip install django-debug-toolbar`
- [ ] Ativar apenas em staging/dev
- **Arquivos:** `config/settings/dev.py`

### T14.06 — Lighthouse CI
- [ ] Adicionar job no CI:
  ```yaml
  - run: npm install -g @lhci/cli
  - run: lhci autorun --config=lighthouserc.json
  ```
- **Arquivos:** `.github/workflows/ci.yml`, `lighthouserc.json`

## 🧪 TESTES DE VALIDAÇÃO DA BUILD 14
```bash
# Lighthouse Performance score > 70
# DB connections pooled (verificar em debug toolbar)
```

## 📝 NOTAS
_Espaço para o agente._

---
---

# ═══════════════════════════════════════════════════════════════
# BUILD 15 — MOBILE E PWA AVANÇADO
# ═══════════════════════════════════════════════════════════════

**Status:** [PENDENTE]
**Prioridade:** 🟡 MÉDIA
**Esforço estimado:** ~10 horas
**Defeitos cobertos:** #181-#195
**Dependências:** BUILD 04 [CONCLUÍDO]
**Concluído em:** _não concluído_

## 🎯 OBJETIVO
Implementar push notifications (Web Push API), geolocalização automática, modo câmera com geotag, background fetch para fotos, share target, adaptive icons, splash screen, e modo economia de dados.

## ✅ TAREFAS (resumidas)

### T15.01 — Web Push Notifications
- [ ] Instalar: `pip install django-webpush`
- [ ] Configurar VAPID keys
- [ ] Criar subscription endpoint
- [ ] Enviar push quando alerta crítico é disparado
- **Arquivos:** `config/settings/base.py`, `app/static/js/push.js`

### T15.02 — Geolocalização automática no caderno
- [ ] Usar `navigator.geolocation.getCurrentPosition()` ao criar observação
- [ ] Salvar lat/lon automaticamente
- **Arquivos:** `app/static/js/pwa/` módulos

### T15.03 — Modo câmera com geotag
- [ ] Usar `navigator.mediaDevices.getUserMedia()` para capturar foto
- [ ] Extrair EXIF GPS ou usar geolocation
- **Arquivos:** `app/static/js/camera.js`

### T15.04 — Share target
- [ ] Adicionar `share_target` no manifest.json
- **Arquivos:** `app/static/manifest.json`

### T15.05 — Adaptive icons
- [ ] Criar maskable icon (safe zone respeitada)
- [ ] Atualizar manifest.json com `purpose: "any maskable"`
- **Arquivos:** `app/static/manifest.json`, ícones

### T15.06 — Modo economia de dados
- [ ] Detectar `navigator.connection.saveData` e reduzir qualidade de imagens
- [ ] Desabilitar animações e auto-refresh quando saveData=true
- **Arquivos:** `app/static/js/data-saver.js`

## 🧪 TESTES DE VALIDAÇÃO DA BUILD 15
```bash
# Lighthouse PWA score > 90
# Push notification chega no celular
# Foto com geotag salva corretamente
```

## 📝 NOTAS
_Espaço para o agente._

---
---

# ═══════════════════════════════════════════════════════════════
# BUILD 16 — INTEGRAÇÕES EXTERNAS E MARKETPLACE
# ═══════════════════════════════════════════════════════════════

**Status:** [PENDENTE]
**Prioridade:** 🔵 BAIXA-MÉDIA
**Esforço estimado:** ~16 horas
**Defeitos cobertos:** #111, #112, #113, #114, Comparativos 62-65
**Dependências:** BUILD 04 [CONCLUÍDO]
**Concluído em:** _não concluído_

## 🎯 OBJETIVO
Implementar integrações com Climate FieldView API, John Deere Operations Center API, webhooks para terceiros, API pública documentada, e SSO (Google login).

## ✅ TAREFAS (resumidas)

### T16.01 — Climate FieldView integration (readonly)
- [ ] Registrar app no Climate FieldView Developer Portal
- [ ] Implementar OAuth2 flow para autorização
- [ ] Buscar dados de máquina e mapas de plantio/colheita
- **Arquivos:** `app/services/fieldview.py`

### T16.02 — John Deere Operations Center (readonly)
- [ ] Registrar no JD developer portal
- [ ] Implementar OAuth2 + buscar dados de operação
- **Arquivos:** `app/services/johndeere.py`

### T16.03 — Webhooks para terceiros
- [ ] Criar modelo `WebhookSubscription` (url, evento, secret)
- [ ] Disparar webhook quando eventos importantes ocorrem
- **Arquivos:** `app/models/integracao.py`, `app/services/webhooks.py`

### T16.04 — SSO Google Login
- [ ] Instalar: `pip install django-allauth`
- [ ] Configurar Google OAuth provider
- **Arquivos:** `config/settings/base.py`, templates login

### T16.05 — API pública documentada
- [ ] Expandir Swagger docs (BUILD 03) com exemplos e guias
- [ ] Criar `/developers/` page com documentação de API
- **Arquivos:** Templates docs, Swagger config

## 🧪 TESTES DE VALIDAÇÃO DA BUILD 16
```bash
pytest tests/test_integracoes.py
# OAuth flow FieldView funciona
# Webhook dispara e é recebido
```

## 📝 NOTAS
_Espaço para o agente._

---
---

# ═══════════════════════════════════════════════════════════════
# BUILD 17 — NEGÓCIO, MONETIZAÇÃO E COMPLIANCE
# ═══════════════════════════════════════════════════════════════

**Status:** [PENDENTE]
**Prioridade:** 🔵 BAIXA-MÉDIA
**Esforço estimado:** ~12 horas
**Defeitos cobertos:** #150, #153, #163, #164, #165, #196-#200
**Dependências:** BUILD 03 [CONCLUÍDO]
**Concluído em:** _não concluído_

## 🎯 OBJETIVO
Implementar multi-tenancy (visão de grupo/holding), modelo de precificação/assinatura, 2FA, RBAC granular, LGPD compliance, módulo de contratos de safra, e integração CAR/SICAR.

## ✅ TAREFAS (resumidas)

### T17.01 — Multi-tenancy (visão de grupo)
- [ ] Criar modelo `GrupoAgricola` que agrupa múltiplas propriedades
- [ ] Dashboard consolidado para o grupo
- **Arquivos:** `app/models/core.py`

### T17.02 — Modelo de precificação
- [ ] Criar modelo `Plano` (free, basic, pro, enterprise) com limites
- [ ] Middleware de controle de features por plano
- **Arquivos:** `app/models/billing.py`

### T17.03 — 2FA (autenticação dois fatores)
- [ ] Instalar: `pip install django-otp django-two-factor-auth`
- [ ] Configurar TOTP + QR code
- **Arquivos:** `config/settings/base.py`, templates 2FA

### T17.04 — RBAC granular
- [ ] Expandir `PerfilUsuario.permissoes` para suportar permissões por ação (ver/criar/editar/deletar) por módulo
- **Arquivos:** `app/models/usuario.py`, `app/hierarquia.py`

### T17.05 — LGPD compliance
- [ ] Criar mecanismo de consentimento no cadastro de funcionários
- [ ] Implementar direito de exclusão (anonimização de dados)
- [ ] Política de retenção configurável
- **Arquivos:** `app/services/lgpd.py`

### T17.06 — Módulo de contratos de safra
- [ ] Criar modelo `ContratoSafra` (comprador, quantidade, preço, prazo, status)
- [ ] Dashboard de posição vendida vs disponível
- **Arquivos:** `app/models/comercializacao.py`

### T17.07 — Integração CAR/SICAR
- [ ] Importar shapefile/GeoJSON do CAR
- [ ] Exibir áreas de preservação no mapa
- **Arquivos:** `app/services/car.py`

## 🧪 TESTES DE VALIDAÇÃO DA BUILD 17
```bash
pytest tests/test_negocio.py
# Multi-tenancy consolida dados
# 2FA funciona com TOTP
# LGPD exclusão anonimiza dados
```

## 📝 NOTAS
_Espaço para o agente._

---
---

# ═══════════════════════════════════════════════════════════════
# 📊 TABELA MESTRE: DEFEITO → BUILD
# ═══════════════════════════════════════════════════════════════

Mapeamento rápido de cada defeito (1-200) para a build que o resolve:

| Defeitos | Build | Tema |
|----------|-------|------|
| 1-25 | BUILD 06 | UI/UX e Design |
| 26-28 | BUILD 03 | Split de arquivos |
| 29-30 | BUILD 03 | Cache + Queue |
| 31 | BUILD 01 | PostgreSQL |
| 32-33 | BUILD 03 | Paginação + Rate Limit |
| 34-35 | BUILD 01 | Logging + Health Check |
| 36-45 | BUILD 03 | Arquitetura backend |
| 46 | BUILD 01 | Settings split |
| 47-49 | BUILD 01 | Middleware + CORS + Compressão |
| 50 | BUILD 01 | Django storages |
| 51-75 | BUILD 04 | Frontend fundação |
| 76-100 | BUILD 07 + 08 | Financeiro + Campo |
| 101-125 | BUILD 13 | IoT robusta |
| 126-145 | BUILD 05 | Testes |
| 146-149 | BUILD 00 | Segurança urgente |
| 150 | BUILD 17 | 2FA |
| 151 | BUILD 13 | API key rotation |
| 152 | BUILD 03 | Audit log |
| 153 | BUILD 17 | RBAC |
| 154-157 | BUILD 00 | Segurança básica |
| 158-159 | BUILD 01 | Backup + Encryption |
| 160-162 | BUILD 02 | SAST/DAST no CI |
| 163-165 | BUILD 17 | LGPD |
| 166-180 | BUILD 14 | Performance |
| 181-195 | BUILD 15 | Mobile/PWA |
| 196-200 | BUILD 17 | Negócio |

---

# ═══════════════════════════════════════════════════════════════
# 📅 CRONOGRAMA ESTIMADO
# ═══════════════════════════════════════════════════════════════

| Fase | Builds | Estimativa | Semana |
|------|--------|-----------|--------|
| **FASE 1 — Fundação** | 00 + 01 + 02 | ~16h | Semana 1 |
| **FASE 2 — Arquitetura** | 03 + 04 | ~22h | Semana 2-3 |
| **FASE 3 — Qualidade** | 05 | ~12h | Semana 3 |
| **FASE 4 — UX + Financeiro** | 06 + 07 | ~36h | Semana 4-5 |
| **FASE 5 — Domínio** | 08 + 09 + 10 + 11 + 12 | ~64h | Semana 6-9 |
| **FASE 6 — Infra Avançada** | 13 + 14 + 15 | ~36h | Semana 10-11 |
| **FASE 7 — Integração + Negócio** | 16 + 17 | ~28h | Semana 12-13 |
| **TOTAL** | 18 builds | **~204h** | **~13 semanas** |

---

*Documento gerado em 2026-08-31. Atualizar este arquivo após cada build concluída.*
*Referência: `dores que iremos sanar` (200 defeitos) + planilha comparativa (100 critérios × 20 concorrentes).*
