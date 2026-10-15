# Ampliagro 2.0

Sistema de gestão agrícola — Desktop (Electron + Django) + Web (Django + Docker).

## 🚀 Início Rápido

### Desktop (Windows)
```bash
cd ampliagro-app/desktop
npm install
npm run build:all      # assets + packs + runtime congelado
npm run dist:win       # gera Ampliagro.exe (portable, 246 MB)
```

### Web (Docker)
```bash
docker compose up -d
# http://localhost:8000
```

### Desenvolvimento (Django runserver)
```bash
python manage.py runserver --settings=config.settings.base
```

---

## 📚 Documentação

- [Arquitetura](./docs/arquitetura/) — Modelos, APIs, CSP, OTA, IA, etc.
- [Guias](./docs/guias/) — Ferramentas, planos, handover, IA.
- [Handover](./docs/handover/) — [CHANGELOG](./docs/handover/CHANGELOG.md), [RUNBOOK](./docs/handover/RUNBOOK.md).
- [Legacy](./docs/legacy/) — Documentos antigos.
- [Segurança](./docs/seguranca/instalar-seguramente.md) — Como verificar o instalador e entender os avisos do Windows.

---

## 🧪 Testes

```bash
# Desktop
cd ampliagro-app/desktop
npm run check:python       # Django check
npm run gate:offline       # Teste offline (CSP)
npm run prova:janela       # Janela Electron real
npm run prova:congelado    # Runtime congelado

# Python
python manage.py test app.tests_equipe app.api.tests_placeholder_zero app.ia.tests_pulverizar_zero app.services.tests_clima_cache
```

---

## 📦 Releases

| Versão | Data | Artefacto |
|---|---|---|
| 0.1.0 | 2026-10-12 | Windows portable (`Ampliagro.exe`, 246 MB) |

Ver [CHANGELOG](./docs/handover/CHANGELOG.md) para detalhes.

### 🔒 Verificando o instalador

Como o Ampliagro é um projeto de código aberto e gratuito, **o instalador Windows não possui certificado de code signing pago**. Isso é normal para projetos open source — o Windows pode mostrar um aviso de "publicador desconhecido" na primeira execução.

Para garantir que o instalador é autêntico:

1. **Baixe apenas do GitHub Releases**: https://github.com/luck-of-luck/Ampliagro-releases/releases
2. **Verifique o hash SHA256** do arquivo baixado comparando com o hash publicado na página de release:

```powershell
# PowerShell (Windows)
Get-FileHash Ampliagro.exe -Algorithm SHA256

# Ou no Linux/macOS
sha256sum Ampliagro.exe
```

Se o hash bater com o publicado na release, o instalador é legítimo. O aviso do Windows pode ser ignorado com segurança.

> Por que não há certificado pago? Certificados de code signing (Authenticode) custam ~$100-300/ano e não são viáveis para um projeto de código aberto mantido por estudantes sem financiamento. A confiança vem da transparência: código aberto no GitHub + hash SHA256 para verificação.

---


## 🛠️ Stack

- **Frontend**: Electron 44 + Django Templates + HTMX + Chart.js 4.4.7 + Bootstrap 5.3
- **Backend**: Django 5 + Daphne (ASGI) + SQLite (desktop) / PostgreSQL (web)
- **IA Local**: WebLLM (opcional, pack separado) + Whisper.cpp
- **Packs**: 25 subgrupos, 488 culturas, download sob demanda
- **CI/CD**: GitHub Actions (Win/mac/Linux runners)

---

## 📄 Licença

UNLICENSED — uso interno Ampliagro.