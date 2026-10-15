# Runbook Ampliagro Desktop

Este runbook documenta procedimentos operacionais para o Ampliagro Desktop.

---

## 1. Crash Report

### Onde encontrar logs
| Componente | Localização |
|---|---|
| Electron (main) | Console onde `npm start` foi corrido |
| Django (bootstrap) | Mesma consola (stdout/stderr do child process) |
| Django (runtime) | `APMData/logs/` (ficheiros `.log` rotativos) |
| PyInstaller | `dist-runtime/ampliagro-runtime/warn-ampliagro-runtime.txt` |

### Como gerar crash report
1. Reproduza o erro.
2. Copie a saída da consola (Electron + Django).
3. Se houver traceback Python, inclua o ficheiro `warn-ampliagro-runtime.txt`.
4. Anexe `APMData/logs/django-YYYY-MM-DD.log`.
5. Descreva passos para reproduzir + versão (`Ampliagro 0.1.0`).

### Erros conhecidos
| Sintoma | Causa | Resolução |
|---|---|---|
| Janela branca, navbar OK | `collectstatic` não corrido | `npm run build:assets` |
| "runtime não ficou pronto" | Porta ocupada / Python em falta | Verificar `AMPLIAGRO_DESKTOP_PYTHON`, porta livre |
| WebSocket 400 | `autobahn`/`nvx` em falta no runtime | `pip install autobahn nvx` + rebuild |
| CSP bloqueia recurso | Recurso externo referenciado | Vendorizar ou remover referência |

---

## 2. Voltar ao Modo Web

O Ampliagro Desktop partilha o mesmo código Django da versão web. Para testar/usar no browser:

### Opção A — Docker (produção-like)
```bash
docker compose up -d
# Acede em http://localhost:8000
```

### Opção B — Django runserver (desenvolvimento)
```bash
cd C:\Trabalho\Projetos\Ativos\Ampliagro2
python manage.py runserver 0.0.0.0:8000 --settings=config.settings.base
# Acede em http://localhost:8000
```

### Diferenças Desktop vs Web
| Aspecto | Desktop | Web |
|---|---|---|
| Settings | `config.settings.desktop` | `config.settings.base` / `prod` |
| Base de dados | SQLite (`APMData/db.sqlite3`) | PostgreSQL |
| Cache | DatabaseCache | Redis (`django_redis`) |
| CSP | `local-only` (loopback only) | Permite CDNs, Open-Meteo, OSM |
| Staticfiles | `staticfiles/` (colectado no build) | `staticfiles/` (colectado no Docker) |
| Media | `APMData/media/` | S3 / volume persistente |
| WebSockets | `ws://127.0.0.1:<porta>` | `wss://` via proxy |

### Variáveis de ambiente para forçar modo web no desktop
```bash
set DJANGO_SETTINGS_MODULE=config.settings.base
set AMPLIAGRO_DESKTOP_DATA_DIR=C:\temp\ampliagro-web
python manage.py runserver
```

---

## 3. Backup do SQLite

### Localização
```
APMData/
├── db.sqlite3          # Base de dados principal
├── db.sqlite3-wal      # WAL (Write-Ahead Logging)
├── db.sqlite3-shm      # Shared memory
└── backups/            # Backups automáticos (bootstrap)
```

### Backup manual
```bash
# Parar a aplicação primeiro!
copy APMData\db.sqlite3 APMData\backups\db_20261012_143000.sqlite3
```

### Backup automático (bootstrap)
O `bootstrap.py --preparar` cria backup em `APMData/backups/db_YYYYMMDD_HHMMSS.sqlite3` antes de `migrate`.

### Restore
```bash
# Parar a aplicação!
copy APMData\backups\db_20261012_143000.sqlite3 APMData\db.sqlite3
# Apagar -wal/-shm se existirem
del APMData\db.sqlite3-wal
del APMData\db.sqlite3-shm
```

### Verificar integridade
```bash
sqlite3 APMData\db.sqlite3 "PRAGMA integrity_check;"
# Deve retornar "ok"
```

---

## 4. Atualização de Versão

### Via auto-updater (utilizador)
1. App notifica "Nova versão disponível".
2. Utilizador clica "Actualizar agora".
3. Download em background → prompt "Reiniciar agora".

### Via CLI (admin)
```bash
cd C:\Trabalho\Projetos\Ativos\Ampliagro2\ampliagro-app\desktop
npm run build:all
npm run dist:win
# Entregar dist\Ampliagro 0.1.0.exe ao utilizador
```

### Rollback
1. Utilizador desinstala versão actual (Painel de Controlo).
2. Instala versão anterior (`.exe` guardado).
3. Base de dados SQLite **não é apagada** na desinstalação (fica em `APMData/`).

---

## 5. Reset Completo (Limpar Tudo)

```bash
# 1. Parar app
# 2. Apagar dados
rmdir /s /q %LOCALAPPDATA%\Ampliagro
# 3. Reinstalar
Ampliagro 0.1.0.exe
```

> ⚠️ **Isto apaga a base de dados, cache de packs, logs e configurações.**
> Fazer backup do `db.sqlite3` antes se quiser preservar dados.

---

## 5. Contactos

| Área | Contacto |
|---|---|
| Bugs / Crashes | suporte@ampliagro.com |
| Segurança | security@ampliagro.com |
| DevOps / CI | devops@ampliagro.com |

---

> **Nota:** Este runbook vive em `docs/handover/RUNBOOK.md`. Atualize-o a cada release.