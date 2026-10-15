@echo off
REM =====================================================================
REM  Ampliagro - Alertas diarios (gerenciador de alertas)
REM  Gera notificacoes (manutencao, estoque, financeiro, MIP, vacinas...)
REM  e limpa as lidas com +7 dias. Chamado pelo Agendador de Tarefas.
REM  Projeto: C:\Trabalho\Projetos\Ativos\Ampliagro - bat em tools\bat\
REM =====================================================================
cd /d "%~dp0\..\.."
if not exist "manage.py" cd /d "%~dp0"
if not exist "manage.py" exit /b 1

set PYEXE=%CD%\.venv\Scripts\python.exe
if not exist "%PYEXE%" set PYEXE=python
set PYTHONIOENCODING=utf-8
set DJANGO_SETTINGS_MODULE=config.settings.dev
if not exist "logs" mkdir "logs"

set LOG=logs\alertas-diario.log
echo [%DATE% %TIME%] inicio >> "%LOG%"
"%PYEXE%" manage.py gerar_alertas >> "%LOG%" 2>&1
"%PYEXE%" manage.py gerar_alertas --clear >> "%LOG%" 2>&1
"%PYEXE%" manage.py verificar_offline >> "%LOG%" 2>&1
"%PYEXE%" manage.py ia_comandos >> "%LOG%" 2>&1
echo [%DATE% %TIME%] fim >> "%LOG%"
