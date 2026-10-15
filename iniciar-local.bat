@echo off
REM =====================================================================
REM  Ampliagro - servidor local para teste no celular pela rede Wi-Fi
REM
REM  Por que este script existe, e nao o iniciar.bat:
REM   - iniciar.bat delega para tools\bat\runserver_dev.bat, que procura
REM     .venv\Scripts\python.exe. Nao ha .venv utilizavel nesta maquina
REM     (o Python 3.12 do uv nao consegue criar arquivo dentro do worktree).
REM   - O servidor precisa escutar em 0.0.0.0 para o celular alcancar.
REM   - PLAYWRIGHT_TEST=1 e o caminho que o proprio projeto ja usa em
REM     config/settings/dev.py:24 para forcar DJANGO_VITE dev_mode=False.
REM     Isso faz o Django servir o bundle JA BUILDADO em staticfiles/dist
REM     em vez de apontar para o dev server do Vite. Sem isso, o HTML
REM     referencia localhost:5173 e no celular vira tela branca.
REM
REM  Uso:  .\iniciar-local.bat            (porta 8020)
REM        .\iniciar-local.bat 9000
REM
REM  Celular: conecte na MESMA rede Wi-Fi do PC e abra
REM            http://192.168.10.6:<porta>/
REM =====================================================================
REM EnableDelayedExpansion e obrigatorio: o IP e lido num FOR e usado no %%A
REM mais abaixo, que so expande em tempo de execucao.
setlocal EnableDelayedExpansion

set PORTA=%~1
if "%PORTA%"=="" set PORTA=8020

REM Python do sistema: e o unico desta maquina que consegue gravar no worktree.
set PYEXE=C:\Users\lucas\AppData\Local\Microsoft\WindowsApps\python3.11.exe
if not exist "%PYEXE%" (
  echo [ERRO] Interpretador nao encontrado: %PYEXE%
  pause
  exit /b 1
)

set DJANGO_SETTINGS_MODULE=config.settings.dev
set PLAYWRIGHT_TEST=1

REM O banco e SQLite (db.sqlite3). Sem Redis necessario para o servidor web.
if not exist "db.sqlite3" (
  echo [INFO] Banco novo: aplicando migrations...
  "%PYEXE%" manage.py migrate
)

REM O frontend precisa estar buildado uma vez. Se faltar, o build.
if not exist "staticfiles\dist\.vite\manifest.json" (
  echo [INFO] Manifest ausente: rodando npm install e npm run build...
  call npm install --no-audit --no-fund
  call npm run build
  if errorlevel 1 (
    echo [ERRO] npm run build falhou.
    pause
    exit /b 1
  )
)

REM Descobre o IP da LAN para mostrar no console. O do hotspot do Windows
REM (192.168.137.x) NAO funciona nesta maquina: o adaptador existe mas nao ha
REM rota para 192.168.137.0/24, entao a conexao da no timeout.
for /f "tokens=2 delims=:" %%A in ('ipconfig ^| findstr /c:"IPv4"') do (
  set IPATUAL=%%A
  set IPATUAL=!IPATUAL: =!
)

echo =====================================================================
echo  Ampliagro local
echo Nesta maquem:  http://127.0.0.1:%PORTA%/
echo  No celular:    http://!IPATUAL!:%PORTA%/     ^(mesma rede Wi-Fi do PC^)
echo  Login demo:    demo / demo123
echo  Parar:         Ctrl+C
echo =====================================================================

"%PYEXE%" manage.py runserver 0.0.0.0:%PORTA% --noreload

endlocal
