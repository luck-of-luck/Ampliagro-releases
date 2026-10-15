# Segurança / CSP / django-csp — Estado 2026-10-11

> Fontes: `app/middleware.py`, `config/settings/base.py:307-347`, `MERGED.md` §2.5, `11-integracao-tecnologias.md` §2.1, `PLANO-EXECUCAO.md` Onda 0 item 0.4

---

## 1. O Bug Crítico (resolvido)

### O que acontecia
- `django-csp` **4.0** instalado
- Middleware ligado em `base.py:120` → `"csp.middleware.CSPMiddleware"`
- **Configuração usava sintaxe 3.x** (`CSP_DEFAULT_SRC`, `CSP_SCRIPT_SRC`, `CSP_FRAME_ANCESTORS`)
- `django-csp` 4.x lê: `getattr(settings, "CONTENT_SECURITY_POLICY", {})`
- **Chave 3.x não existe** → `{}` → `default_config(...)` recebe `{}` → `None`
- **Header nunca saía** — defesa XSS desligada a parecer ligada

### Correção aplicada (`base.py:307-347`)
```python
CONTENT_SECURITY_POLICY = {
    "DEFAULT_SRC": ["'self'"],
    "SCRIPT_SRC": ["'self'", "'wasm-unsafe-eval'", "huggingface.co", "*.ingest.sentry.io"],
    "STYLE_SRC": ["'self'", "'unsafe-inline'"],
    "CONNECT_SRC": ["'self'", "api.open-meteo.com", "servicodados.ibge.gov.br", "nominatim.openstreetmap.org", "*.ingest.sentry.io", "huggingface.co"],
    "FONT_SRC": ["'self'", "data:"],
    "IMG_SRC": ["'self'", "data:", "blob:"],
    "FRAME_ANCESTORS": ["'none'"],
    "BASE_URI": ["'self'"],
    "FORM_ACTION": ["'self'"],
}
```

---

## 2. Dependência Não Declarada

**`django-csp>=4.0,<5.0` NÃO está em `requirements.txt`**

| Fato | Evidência |
|------|-----------|
| Middleware no `MIDDLEWARE` | `base.py:120` |
| Pacote instalado na máquina | `csp` versão **4.0** |
| `django-csp` em `requirements.txt` | 163 linhas, **0 hits** |
| Nem em `requirements-mcp.txt`, `setup.py` | 0 hits nos três |

**Consequência:** `pip install -r requirements.txt` + `manage.py runserver` em máquina limpa **não arranca** (`ImportError` no `MIDDLEWARE`).

**Correção de uma linha:**
```
django-csp>=4.0,<5.0
```

---

## 3. 560 Handlers Inline Bloqueiam Nonce

**Medido:** 560 handlers `on*=` em 54 templates
- `index.html`: **131**
- `dashboard_appbar.html`: 46
- `guia-ferramentas.html`: 22
- `navbar.html`: 17
- 94 `<script>` sem `src`
- 1117 `style=` inline

### Roteiro de migração (ordem obrigatória)

| Etapa | Ação | Porquê |
|-------|------|--------|
| 1 | `django-csp` no `requirements.txt` — **hoje** | Sem isto, nada abaixo importa (boot falha) |
| 2 | `htmx` nos templates de maior densidade (`index.html`, 131 handlers) | Resolve por eliminação, não migração |
| 3 | `jscodeshift` no resto, com `--dry-run` e revisão por template | Transforma **AST**, não regex. `sed` sobre 560 handlers = 560 bugs novos |
| 4 | Só então `script-src 'nonce-...'` estrito, removendo `'unsafe-inline'` | `'unsafe-inline'` em `script-src` = **ausência** de CSP |

### Tecnologias recomendadas

| Camada | Ferramenta | Porque |
|--------|------------|--------|
| Política | `django-csp` 4.0 | Já no MIDDLEWARE. Não é adoptar — é declarar. |
| Nonce no template | `csp.constants.NONCE` + tag `{{ CSP_NONCE }}` | `base.py:359` já aponta para aqui |
| Migração dos 560 | **`jscodeshift`** | Transforma **AST**, não regex |
| Eventos declarativos | **`htmx`** | `hx-on:click` resolve handlers **sem JS inline** |

---

## 4. Guardas de Regressão

| Teste | O que impede |
|-------|--------------|
| `tests/test_csp.py` (13 testes) | `test_o_cabecalho_csp_esta_publicado` — header real sai |
| `test_hmr_continua_condicional_e_o_bundle_nao` | Vite HMR só em DEBUG |
| `test_o_sinal_segue_o_debug_nos_dois_sentidos` | 4 transições DEBUG on/off verificadas |
| `test_a_politica_esta_no_formato_que_a_middleware_le` | `CONTENT_SECURITY_POLICY` no formato 4.x |

---

## 5. Source Maps / Sentry

**`sourcemap: false` no `vite.config.ts` NÃO corrigiu a fuga e degrada o Sentry**

| Problema | Evidência |
|----------|-----------|
| Não teve efeito | `staticfiles/dist/js/legacy.C6Z7LlIz.js:4` **ainda tem** `//# sourceMappingURL=...` enquanto `.map` não é recriado |
| Estragou o Sentry | `base.py:703` liga Sentry com `SENTRY_DSN`. Sem mapas, stack trace chega como `legacy.C6Z7LlIz.js:1:482913` |

**Correção:** `sourcemap: 'hidden'` — gera `.map` e **não** acrescenta `sourceMappingURL` ao bundle.

**Pendente:** `rebuild` + `collectstatic` + `sentry-cli sourcemaps upload` (precisa `SENTRY_AUTH_TOKEN`).

---

## 6. Segredos / Chaves

| Item | Status | Padrão correto |
|------|--------|----------------|
| `AMPLIAGRO_DATA_KEY` | **Não existe em produção** (`base.py`, `dev.py`, `prod.py` não têm) | `age` ou `SOPS`: chave encriptada em ficheiro versionado, valor em variável de ambiente |
| `BACKUP_ENCRYPTION_KEY` | Só protege backups, não ingestão | — |
| `IA_LOCAL_KEY` | Em `base.py:184-187` com `env.str()` | **Padrão correto** — comentário: *"a chave só pode agir pelos user IDs listados aqui"* |

**Precedente do projeto:** `config/settings/base.py:184-187` tem o padrão. Falta aplicar a `AMPLIAGRO_DATA_KEY`.