@echo off
REM ===========================================================================
REM  rodar_varrer_proativo.bat - a varredura, executada pelo Agendador
REM ===========================================================================
REM
REM  POR QUE ESTE .bat EXISTE, E POR QUE O AGENDADOR NAO CHAMA O PYTHON DIRETO
REM  ==========================================================================
REM  O Agendador de Tarefas roda com diretorio de trabalho C:\Windows\System32.
REM  E o DATABASE_URL do Ampliagro aponta db.sqlite3 por caminho RELATIVO.
REM  Mandar o Python direto faria o job abrir outro banco (ou nenhum, com "no
REM  such table") - e falhar as 7h12 e 17h12, todo dia, sem ninguem ver.
REM
REM  Este script e' ASCII de proposito. O cmd.exe le .bat na codepage do
REM  sistema, nao em UTF-8: um acento em comentario pode virar lixo que quebra
REM  o PARSE do arquivo inteiro, e o sintoma e' a tarefa falhar sem executar
REM  nenhuma linha - inclusive sem cd, sem log e sem Python. Foi exatamente o
REM  que aconteceu na primeira versao deste arquivo.
REM
REM  A alternativa seria schtasks /tr com cmd /c cd /d ... && python ..., que
REM  quebra em silencio quando o caminho tem espaco. Um .bat nao quebra.
REM
REM  SAIDA: stdout E stderr vao para logs\varredura-proativa.log, com rotacao por
REM  TAMANHO. Um log que cresce para sempre enche o disco da fazenda - e o dia
REM  em que o job falha e' justamente o dia em que o disco encheu.
REM
REM  Este arquivo NAO agenda nada. Agendar e' setup_tarefa_proativa.bat.
REM ===========================================================================

setlocal
set "RAIZ=%~dp0..\.."
set "PYTHON=%RAIZ%\.venv\Scripts\python.exe"
set "LOGDIR=%RAIZ%\logs"
set "LOG=%LOGDIR%\varredura-proativa.log"
set "LIMITE=1048576"

if not exist "%PYTHON%" (
    echo ERRO: Python da venv nao encontrado em "%PYTHON%" 1>&2
    exit /b 1
)

if not exist "%LOGDIR%" mkdir "%LOGDIR%" 2>nul

REM --- rotacao por tamanho: o log nao pode ser a proxima causa de falha ------
if exist "%LOG%" call :rotaciona

REM --- cd para a raiz: e' o que garante o banco certo ------------------------
cd /d "%RAIZ%"

echo ==== %date% %time% ==== >> "%LOG%"
"%PYTHON%" manage.py varrer_proativo >> "%LOG%" 2>&1
set "SAIDA=%ERRORLEVEL%"

if %SAIDA% NEQ 0 echo FALHOU ^(codigo %SAIDA%^). Detalhes acima. >> "%LOG%"

exit /b %SAIDA%

:rotaciona
setlocal
set "TAM=0"
for %%A in ("%LOG%") do set "TAM=%%~zA"
if %TAM% GTR %LIMITE% move /Y "%LOG%" "%LOG%.1" >nul 2>&1
endlocal
exit /b 0
