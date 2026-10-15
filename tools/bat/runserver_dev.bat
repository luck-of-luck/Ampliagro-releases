@echo off
REM =====================================================================
REM  Ampliagro - Servidor de desenvolvimento (Django)
REM  Uso: runserver_dev.bat [--porta 8001] [--reload]
REM  Projeto: C:\Trabalho\Projetos\Ativos\Ampliagro — bat em tools\bat\
REM  (a raiz tem stub que redireciona para ca)
REM =====================================================================
setlocal EnableDelayedExpansion

cd /d "%~dp0\..\.."
if not exist "manage.py" cd /d "%~dp0"
if not exist "manage.py" (
  echo [ERRO] manage.py nao encontrado em %CD%
  pause
  exit /b 1
)

set PORTA=8001
set RELOAD_FLAG=--noreload
:parse_args
if "%~1"=="" goto :args_ok
if /i "%~1"=="--porta" ( set PORTA=%~2 & shift & shift & goto :parse_args )
if /i "%~1"=="--reload" ( set RELOAD_FLAG= & shift & goto :parse_args )
shift
goto :parse_args
:args_ok

REM --- Python: prefere a .venv do projeto, senao o python do PATH ---
set PYEXE=%CD%\.venv\Scripts\python.exe
if not exist "%PYEXE%" (
  echo [AVISO] .venv nao encontrada, usando python do PATH
  set PYEXE=python
)

REM --- Ambiente dev ---
set DEBUG=True
set PYTHONIOENCODING=utf-8
set DJANGO_SETTINGS_MODULE=config.settings.dev

REM --- Checagem rapida do Django antes de subir ---
"%PYEXE%" manage.py check >nul 2>&1
if errorlevel 1 (
  echo [ERRO] manage.py check falhou. Veja o erro abaixo:
  "%PYEXE%" manage.py check
  pause
  exit /b 1
)

REM --- Porta ocupada? mostra PID e pergunta se mata ---
for /f "tokens=5" %%P in ('netstat -ano ^| findstr "0.0.0.0:%PORTA%" ^| findstr LISTENING') do set PID_OCUPADO=%%P
if defined PID_OCUPADO (
  echo [AVISO] Porta %PORTA% ocupada pelo PID !PID_OCUPADO!.
  choice /C SN /N /M "Matar processo e continuar? [S/N] "
  if errorlevel 2 (
    echo [INFO] Mantendo servidor atual. Saindo.
    exit /b 0
  )
  taskkill /F /PID !PID_OCUPADO! >nul 2>&1
  timeout /t 2 /nobreak >nul
)

echo =====================================================================
echo  Ampliagro DEV em http://127.0.0.1:%PORTA%/  %RELOAD_FLAG:--noreload=--sem-reload%
echo  Projeto: %CD%
echo  Python: %PYEXE%
echo  Logs: logs\runserver-dev.log
echo  Parar: Ctrl+C
echo =====================================================================
if not exist "logs" mkdir "logs"
"%PYEXE%" manage.py runserver 0.0.0.0:%PORTA% %RELOAD_FLAG%
