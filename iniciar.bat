@echo off
REM =====================================================================
REM  Ampliagro - INICIAR servidor de desenvolvimento
REM  Uso (PowerShell):  .\iniciar.bat
REM  Uso (cmd):         iniciar.bat [--porta 8001] [--reload]
REM  Abre em: http://127.0.0.1:8001/
REM  Projeto: C:\Trabalho\Projetos\Ativos\Ampliagro
REM =====================================================================
call "%~dp0tools\bat\runserver_dev.bat" %*
