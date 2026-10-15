@echo off
REM ===========================================================================
REM  setup_tarefa_proativa.bat - agenda a varredura no Agendador do Windows
REM ===========================================================================
REM
REM  USO
REM  ====
REM    setup_tarefa_proativa.bat            instala
REM    setup_tarefa_proativa.bat --status   mostra o que esta agendado
REM    setup_tarefa_proativa.bat --remove   desinstala
REM    setup_tarefa_proativo.bat --run-once roda AGORA, para provar antes
REM
REM  ASCII de proposito: o cmd.exe le .bat na codepage do sistema. Um acento em
REM  comentario quebra o PARSE do arquivo inteiro e a tarefa falha sem executar
REM  uma linha sequer.
REM
REM  POR QUE DUAS TAREFAS, E NAO UMA
REM  ===============================
REM  A intencao e' duas varreduras por dia: 7h12 (antes da ida ao campo) e
REM  17h12 (antes de fechar o dia). O schtasks /sc daily agenda UMA execucao
REM  diaria; para a segunda, a opcao ingenua seria /mo 600, e o resultado dela
REM  depende de o Windows re-ancorar no dia seguinte ou nao - ou seja, um job que
REM  as vezes dispara duas vezes e as vezes uma, sem ninguem saber por que.
REM
REM  Duas tarefas e' mais honesto: duas entradas visiveis no Agendador, dois
REM  resultados, nenhuma dependencia de comportamento do Windows. Se uma falhar o
REM  produtor ve - e a outra, que e' a que importa, roda.
REM
REM  POR QUE O AGENDADOR E NAO O CELERY
REM  ================================
REM  Para um job de alguns segundos duas vezes ao dia, um broker e' infraestrutura
REM  a mais: Redis nao tem build oficial no Windows, WSL e' um sistema operacional
REM  inteiro, e o preco real nao e' instalar - e' SUPORTE. Cada "o alerta nao veio"
REM  vira "o Redis caiu", e quem resolve isso nao e' o produtor, nao e' a IA, e' o
REM  computador da fazenda. O Agendador ja estava na maquina, e' nativo, sobrevive
REM  a reinicio, nao tem daemon para dar crash, e mostra o ultimo resultado.
REM
REM  QUANDO TROCAR
REM  ==============
REM  Quando o volume justificar concorrencia real entre workers. Nao antes. E
REM  quando trocar, o app.ia.proativo_tasks.varrer() nao muda: ele ja era o
REM  nucleo, e tanto o Celery quanto este agendador sao apenas embrulhos.
REM ===========================================================================

setlocal
set "RAIZ=%~dp0..\.."
set "RUNNER=%RAIZ%\tools\bat\rodar_varrer_proativo.bat"
set "T1=AmplIA Varredura Proativa - Manha 0712"
set "T2=AmplIA Varredura Proativa - Tarde 1712"

if not exist "%RUNNER%" (
    echo ERRO: runner nao encontrado em "%RUNNER%" 1>&2
    exit /b 1
)

if /I "%~1"=="--remove"  goto remover
if /I "%~1"=="--status"  goto status
if /I "%~1"=="--run-once" goto rodar
goto instalar

:instalar
echo.
echo   Agendando a varredura proativa do AmplIA
echo   -------------------------------------------
echo   07:12  antes da ida ao campo
echo   17:12  antes de fechar o dia
echo.

REM /f substitui sem perguntar: o script precisa ser idempotente. Rodar duas
REM vezes tem que dar o mesmo resultado, e nao "a tarefa ja existe".
schtasks /create /tn "%T1%" /tr "\"%RUNNER%\"" /sc daily /st 07:12 /f >nul
if errorlevel 1 (
    echo   FALHOU ao agendar a manha. 1>&2
    exit /b 1
)
echo   ok  %T1%

schtasks /create /tn "%T2%" /tr "\"%RUNNER%\"" /sc daily /st 17:12 /f >nul
if errorlevel 1 (
    echo   FALHOU ao agendar a tarde. 1>&2
    exit /b 1
)
echo   ok  %T2%

echo.
echo   Para conferir:      setup_tarefa_proativa.bat --status
echo   Para provar AGORA:  setup_tarefa_proativa.bat --run-once
echo   Para desinstalar:  setup_tarefa_proativa.bat --remove
echo.
exit /b 0

:status
echo.
echo   Tarefas agendadas:
echo.
REM Filtra por "AmplIA" - o nome da NOSSA tarefa - e nao por "TaskName" ou
REM "Next Run Time". O schtasks usa os rotulos do Windows, e eles sao
REM traduzidos: num Windows pt-BR o campo chama-se "Proxima execucao", e o
REM findstr por rotulo ingles nao acha nada. Filtrar pelo proprio nome da
REM tarefa funciona em qualquer idioma, porque o valor nao e' traduzido.
echo   (colunas do Agendador do Windows: nome, proxima execucao, status, ultimo resultado)
echo.
schtasks /query /fo CSV /nh 2>nul | findstr /i "AmplIA"
echo.
if exist "%RAIZ%\logs\varredura-proativa.log" (
    echo   Ultimas linhas do log:
    powershell -NoProfile -Command "Get-Content -Tail 10 '%RAIZ%\logs\varredura-proativa.log'"
) else (
    echo   Log ainda nao existe - a varredura nunca rodou.
)
echo.
exit /b 0

:rodar
echo   Rodando a varredura agora, na sua frente...
echo.
call "%RUNNER%"
set "COD=%ERRORLEVEL%"
echo.
if "%COD%"=="0" (
    echo   Terminou bem. O log esta em logs\varredura-proativa.log
) else (
    echo   Terminou com codigo %COD%. Veja logs\varredura-proativa.log
)
echo.
exit /b %COD%

:remover
echo.
echo   Removendo as tarefas...
schtasks /delete /tn "%T1%" /f >nul 2>&1
if errorlevel 1 (echo   nao estava: manha) else (echo   removida: manha)
schtasks /delete /tn "%T2%" /f >nul 2>&1
if errorlevel 1 (echo   nao estava: tarde) else (echo   removida: tarde)
echo.
echo   O log em logs\varredura-proativa.log foi mantido, de proposito:
echo   quem remove a agenda costuma estar investigando o que ela fez.
echo.
exit /b 0
