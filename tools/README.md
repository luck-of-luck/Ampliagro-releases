# Tools — Ampliagro

> **Raiz:** `C:\Trabalho\Projetos\Ativos\Ampliagro`

## 📁 Estrutura

```
tools/
├── bat/               # .bat — Windows Batch (duplo clique)
│   ├── demo.bat               # DEMO JOSIF/FEBRACE — seed + runserver + abre /demo/
│   ├── runserver_dev.bat      # DEBUG=True + runserver (padrão 8001)
│   ├── git-auto.bat           # git add -A + commit + push (msg auto)
│   ├── git-push.bat           # commit + push com detecção de branch
│   ├── setup_tarefa_proativa.bat   # agenda a varredura no Agendador do Windows
│   ├── rodar_varrer_proativo.bat  # dispara a varredura agora
│   ├── alertas_diario.bat     # gera o relatório diário de alertas
│   └── (sem README próprio)
└── ps1/               # PowerShell
    └── git-auto.ps1           # equivalente PowerShell do git-auto.bat
```

## 🔧 Uso

```bat
REM a partir da raiz do projeto
tools\bat\demo.bat
tools\bat\git-auto.bat "feat: nova cultura"
tools\bat\runserver_dev.bat
tools\bat\runserver_dev.bat --porta 8000 --reload
tools\bat\setup_tarefa_proativa.bat --status

REM ou via stub na raiz (compatibilidade)
.\demo.bat
.\runserver_dev.bat
.\iniciar.bat
```

`runserver_dev.bat` usa `config.settings.dev`, prefere `.venv\Scripts\python.exe`
e pergunta antes de matar um processo que já ocupa a porta. Log em
`logs\runserver-dev.log`.

```powershell
# PowerShell
tools\ps1\git-auto.ps1 -Message "fix: tema dark"
```

## ⚙️ Adaptação ao novo caminho

Todos `.bat` agora fazem:

```bat
cd /d "%~dp0\..\.."
if not exist "manage.py" cd /d "%~dp0"
```

`%~dp0` é a pasta do `.bat` (`tools\bat\`), então `\..\..` volta para a raiz do projeto `C:\Trabalho\Projetos\Ativos\Ampliagro` onde está `manage.py`.  
`git-auto.ps1` usa:

```ps1
$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $ProjectRoot
```

Stubs na raiz — `demo.bat`, `runserver_dev.bat` e `iniciar.bat` — apenas
redirecionam (`call "%~dp0tools\bat\<mesmo>.bat" %*`). Não há stub de
`git-auto.bat`: chame direto por `tools\bat\git-auto.bat`.

## 📦 Versão

* **Migrado:** 2026-08-30 de `C:\Users\lucas\Documents\Projetos_geral\Ampliagro` → `C:\Trabalho\Projetos\Ativos\Ampliagro`
* **Grafo de código:** Codebase-Memory (MCP) é o principal; `graphify-out/` é o secundário — ver `docs/README.md`
