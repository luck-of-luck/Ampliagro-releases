# Contributing to Ampliagro

Thank you for your interest in contributing to Ampliagro! This document provides guidelines and instructions for contributing.

## 🎯 Development Workflow

### Prerequisites

- Python 3.11 (CI fixa `3.11`; testado em 3.11.9)
- Node.js 20+
- Git

Postgres e Redis **não** são obrigatórios para desenvolver ou testar: dev e a
suíte rodam em SQLite. Só `docker-compose*.yml` e `config.settings.prod` os exigem.

### Setup

```bash
# 1. Fork the repository
# 2. Clone your fork
git clone https://github.com/<your-username>/Ampliagro.git
cd Ampliagro

# 3. Create a feature branch
git checkout -b feature/your-feature-name

# 4. Install dependencies
pip install -r requirements.txt
npm install

# 5. Set up environment
cp .env.example .env
# Edit .env with your configuration

# 6. Run migrations
python manage.py migrate

# 7. Run development server
python manage.py runserver 0.0.0.0:8001 --noreload
```

`manage.py` usa `config.settings.dev` por padrão. Outros ambientes existem em
`config/settings/`: `prod.py`, `test.py` (SQLite em memória, sem migrações).

### Coding Standards

#### Python
- Follow PEP 8 style guidelines
- Use type hints where applicable
- Write docstrings for all public functions and classes
- Use meaningful variable and function names
- Keep functions focused on a single responsibility

```python
# ✅ Good
def calcular_custo_producao(safra: Safra, talhao: Talhao) -> Decimal:
    """Calculate production cost per unit for a given harvest."""
    ...

# ❌ Bad
def calc(s): ...
```

#### JavaScript / TypeScript
- Use descriptive variable names
- Avoid global variables
- Use ES6+ features (const/let, arrow functions, destructuring)
- Comment complex logic

#### CSS / Tailwind
- Use Tailwind utility classes over custom CSS
- Follow mobile-first responsive design
- Use CSS custom properties for design tokens
- Maintain WCAG AA contrast ratios

## 🐛 Reporting Issues

When reporting a bug, please include:

1. **Description** — Clear, concise description of the bug
2. **Steps to Reproduce** — Minimal steps to reproduce the issue
3. **Expected Behavior** — What you expected to happen
4. **Actual Behavior** — What actually happened
5. **Environment** — Browser, OS, Python/Django version
6. **Screenshots** — If applicable

## ✨ Feature Requests

Before proposing a new feature:

1. Check existing issues to avoid duplicates
2. Describe the problem it solves and who benefits
3. Provide mockups or examples if possible
4. Consider backward compatibility

## 🧪 Testing

`pytest.ini` define `testpaths = tests app` e já liga `--cov=app`. Rodar
`python -m pytest app/` **ignora `tests/`** — use `python -m pytest` para a suíte
completa.

### Unit & integration tests
```bash
python -m pytest                        # suíte completa (tests/ + app/)
python -m pytest tests/unit
python -m pytest --cov-report=html
```

`config.settings.test` usa SQLite em memória com migrações desligadas — não
precisa de Postgres nem Redis.

### E2E tests
```bash
npx playwright test                    # sobe o Django em :8000 via webServer
npx playwright test --project=a11y     # axe-core nos specs *.a11y.spec.ts
```

### JS tests
```bash
npm test                               # vitest + node:test
```

All new features must include:
- Unit tests exercising the behavior you changed
- E2E scenarios for critical user flows
- Regression test first, where the change is a bug fix

## 📝 Documentation

- Update README.md for user-facing changes
- Update `docs/` for architecture/design changes (start at `docs/README.md`)
- Add docstrings to all new public APIs
- Update `docs/PLANO_RASTREABILIDADE_CUSTOS.md` for roadmap changes

## 🔀 Pull Requests

1. **Small, focused PRs** — One feature or bug fix per PR
2. **Descriptive titles** — "Add Rastreabilidade model" not "fix stuff"
3. **Description** — Explain what and why, not just how
4. **Linked issues** — Reference related issues with `Closes #123`
5. **Rebase** — Keep your branch updated with `main`
6. **Pass CI** — All checks must pass before merge

### PR Template

```markdown
## Description
<!-- What does this PR do? -->

## Related Issue
<!-- Closes #ISSUE_NUMBER -->

## Changes
<!-- Bullet list of significant changes -->

## Testing
<!-- How was this tested? -->

## Checklist
- [ ] Code follows style guidelines
- [ ] Self-reviewed code
- [ ] New tests added
- [ ] Documentation updated
- [ ] No breaking changes to existing functionality
```

## 🏷️ Commit Messages

Follow conventional commits format:

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

Examples:
```
feat(finance): add DRE automático module
fix(drag): sync rAF flush for headless browser testing
docs(readme): update architecture diagram
```

## 📚 Codebase Structure

```
Ampliagro/
├── app/                       # Django app (note: models/views/api are packages)
│   ├── models/                # 29 módulos de domínio (pecuaria, maquinario, ...)
│   ├── views/                 # views HTML (dashboard, guias, financeiro, ...)
│   ├── api/
│   │   ├── views/             # 26 DRF viewsets, routers em urls.py
│   │   ├── serializers.py
│   │   └── urls.py
│   ├── templates/             # templates HTML
│   ├── static/                # css/ e js/ (spa.js, dashboard, widgets, pwa/sw.js)
│   ├── ia/                    # AmplIA — intents, sandbox, proativo
│   ├── iot/                   # telemetria (urls/views)
│   ├── amplia_mcp/            # ferramentas MCP para a IA local
│   ├── management/commands/   # seed_*, varrer_proativo, mqtt_listener, ...
│   └── migrations/
├── config/
│   ├── settings/              # base.py + dev.py + prod.py + test.py
│   ├── urls.py, asgi.py, wsgi.py, celery.py
├── tests/                     # e2e/ (Playwright), unit/, js/, fixtures/, sondas/
├── docs/                      # documentação (ver docs/README.md)
├── tools/{bat,ps1}/           # automação Windows (ver tools/README.md)
├── scripts/                   # utilitários Python avulsos (ver scripts/README.md)
├── src/styles/                # fonte Tailwind (build:css)
├── staticfiles/               # saída do collectstatic + sw.js servido
├── grafos/, graphify-out/     # grafos de código
├── Dockerfile, docker-compose.yml, docker-compose.prod.yml
├── requirements.txt, package.json, pytest.ini, ruff.toml, mypy.ini
└── README.md                  # Este arquivo
```

`static/` não existe na raiz: os assets ficam em `app/static/`, e o bundle
servido em `staticfiles/`.

## 🤝 Community

- **Questions:** Open a GitHub Discussion or issue
- **Discipline:** Be respectful and constructive
- **Mentorship:** We welcome newcomers — ask questions!
- **Localization:** Contributions to internationalize the platform are welcome

---

*Contributing to Ampliagro means helping feed the world.* 🌾
