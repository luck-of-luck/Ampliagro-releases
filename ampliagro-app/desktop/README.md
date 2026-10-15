# Ampliagro Desktop

App de ambiente de trabalho para Windows, macOS e Linux. O plano completo,
com as fases e as medições, está em [`PLAN.md`](PLAN.md). As decisões que
fixam a arquitectura estão em [`docs/adr/`](docs/adr/).

## Onde corre o quê

```
electron/main.js      casca; lê a porta do runtime e abre a janela
electron/preload.js   ponte mínima (superfície zero, por desenho)
backend/bootstrap.py  processo filho: migura, arranca Daphne, espera /healthz
config/settings/desktop.py   (na raiz do repo — ver nota abaixo)
```

`config/settings/desktop.py` vive **fora** desta pasta porque
`DJANGO_SETTINGS_MODULE` resolve por caminho de import e o módulo faz
`from .base import *` — tem de estar no pacote `config`. É a única peça de
desktop que não vive aqui, e é deliberado.

## Comandos

| Comando | O que faz |
|---|---|
| `npm install` | instala o Electron. Se o npm bloquear o `postinstall`, correr `node node_modules/electron/install.js`. |
| `npm run check:python` | `manage.py check` com os settings de desktop. É o CI. |
| `npm run build:assets` | `collectstatic`. **Obrigatório antes de empacotar.** |
| `npm run build:runtime` | PyInstaller: `dist-runtime/`, por SO. |
| `npm start` | arranca o Electron. |
| `npm run inventario:cdn` | lista as referências de CDN, com linha e contexto |
| `npm run vendor:download` | descarrega as libs para `app/static/vendor/` (com SHA256) |
| `npm run vendor:verificar` | confere checksums **e** se cada `url()` de CSS resolve |
| `npm run vendor:reescrever` | mostra o que mudaria nos templates (não escreve) |
| `npm run vendor:aplicar` | aplica (guarda `.cdn-backup` de cada ficheiro) |
| `npm run vendor:restaurar` | desfaz a reescrita |
| `npm run prova:janela` | a janela mostra o Django real (Playwright) |
| `npm run prova:encerramento` | o servidor morre com o pai (Job Object) |
| `npm run prova:congelado` | o `.exe` arranca, migra e serve |
| `npm run gate:offline` | **a prova da Fase 2**: zero pedidos para fora de `127.0.0.1` |

O Python usado é o do sistema, excepto se `AMPLIAGRO_DESKTOP_PYTHON` apontar
para outro. Congelar o runtime é trabalho da Fase 1 — feito: `--preparar`.

## As três armadilhas que já mordem

**1. `config/asgi.py:6` faz `setdefault(... "config.settings.prod")`.**
O `bootstrap.py` tem de pôr `DJANGO_SETTINGS_MODULE` no ambiente **antes**
de qualquer import do Django. Se importar primeiro, o desktop arranca com
os settings de produção: PostgreSQL, `django_redis`, e
`SECURE_SSL_REDIRECT=True` — que em loopback HTTP dá um loop de 301 e uma
janela branca sem mensagem.

**2. `staticfiles/` desatualizado enche o ecrã de vazio.**
`STATICFILES_STORAGE` é `CompressedManifestStaticFilesStorage`
(`config/settings/base.py:253`), que serve a partir do que foi colectado e
não de `app/static/`. A web não sofre disto porque o `Dockerfile:58` corre
`collectstatic` na build. O desktop precisa de `npm run build:assets`.

Este é o mais traiçoeiro dos três: **não dá erro nenhum**. A navbar
aparece, o título está certo, e o meio da página não. Já foi dado por
"funciona" uma vez — apanhou-se porque a prova tira uma captura de ecrã
e lê o que está lá.

**3. O bloqueio contra a rede é a CSP, não o teste.**
`config/settings/desktop.py` define `_CSP_APENAS_LOCAL`, sem uma única
origem externa. Tentar provar o offline bloqueando no Playwright **não
funciona**: `route` fecha a janela Electron, e `setOffline(true)` bloqueia
também o `127.0.0.1` — a emulação de rede do Chromium não distingue loopback
de internet. O `gate-offline.cjs` arranca o runtime e aponta um Chromium
limpo para ele: a CSP é um cabeçalho de resposta, e vem do mesmo sítio
para os dois clientes.

Se mexer na CSP sem correr `npm run gate:offline`, o mapa ou os gráficos
desaparecem **em silêncio**.

## Estado

### Assistente de primeira abertura

O Electron abre `installer.html` antes da janela principal. Usa a licença existente
em `build/license.txt`, registra seu SHA-256 e a data do aceite, oferece o modo local
e usa o mesmo catálogo agrupado do cadastro. A seleção fica em
`dados/installation.json`; somente os perfis escolhidos são materializados em
`dados/culturas/`. O cadastro local reutiliza a seleção e pula a etapa repetida.
O cadastro web mantém o seletor para usuários que não executaram o instalador.

No teste de instalação limpa em 15/10/2026, as migrações forneceram 75 culturas.
A base de desenvolvimento não é empacotada. O assistente mostra o catálogo que
existe no runtime, sem prometer que as 709 entradas da base de desenvolvimento
estão presentes em uma instalação nova.

No Windows, o NSIS copia os arquivos em segundo plano e inicia o app com
`--ampliagro-setup`: a primeira interface interativa é o assistente com a identidade
do Ampliagro e os termos em UTF-8. Reinstalações manuais também exibem o aceite,
preservando a seleção de culturas. Instalações `/S` continuam não interativas.
Fechar o assistente não desfaz a cópia dos arquivos; ele reaparece na próxima
abertura se a configuração ainda não foi concluída. DMG/PKG/AppImage/deb mostram o assistente
na primeira abertura do app, não durante a montagem ou execução do gerenciador
de pacotes. Os termos são os já existentes no projeto, sem revisão jurídica nova.

Sem `AMPLIAGRO_WEB_URL`, a opção web fica indisponível. Com uma URL HTTPS oficial
no ambiente do Electron, a opção abre esse serviço ao concluir. O servidor remoto
mantém seu próprio cadastro: seleção e dados locais não são enviados a ele.
Não há migração automática entre modos. O servidor local continua restrito a
`127.0.0.1`: abrir o aplicativo não habilita acesso por outros dispositivos.

**Limite do empacotamento atual:** os perfis individuais são preparados localmente;
o instalador ainda inclui recursos compartilhados e o catálogo de nomes. Isto não
é download remoto seletivo de todo o conteúdo agrícola. Separar guias, widgets e
packs agrupados em artefatos independentes e publicá-los ainda é necessário para
reduzir o instalador dessa maneira. Nenhum servidor de packs foi inventado.

### Assinatura de distribuição

**Caminho gratuito recomendado para distribuição Windows:** a Microsoft Store
oferece cadastro gratuito e assinatura de pacotes distribuídos pela loja,
conforme o [anúncio oficial](https://blogs.windows.com/windowsdeveloper/2026/05/07/publish-to-microsoft-store-as-a-company-now-with-free-registration-and-faster-onboarding/).
É necessária conta verificada, reserva do aplicativo e aprovação. Isso não fornece
um certificado para assinar o instalador EXE distribuído fora da loja.

`build/store.js` prepara o pacote AppX suportado pelo electron-builder existente.
Copie a identidade exata emitida no Partner Center para `AMPLIAGRO_STORE_IDENTITY`,
`AMPLIAGRO_STORE_PUBLISHER` e `AMPLIAGRO_STORE_PUBLISHER_NAME`, então execute:

```powershell
npm run dist:store
```

O pacote é preparado para submissão, não publicado automaticamente. Sem identidade
oficial, o comando falha com uma instrução em vez de inventar um publicador.
Na versão Store, a atualização fica a cargo da loja.

### Validação do assistente em 15/10/2026

- Gerado `dist/Ampliagro-x64.exe` (183.900.998 bytes), ainda **NotSigned**.
- Prova no executável empacotado: termos visíveis, seleção persistida e painel
  local aberto. Reproduzir com `npm run prova:instalador` após `npm run dist:win`.
- Prova do lançador NSIS com identidade de teste isolada: instalação sem `/S`
  abriu `Ampliagro.exe --ampliagro-setup`, com a janela “Preparar seu Ampliagro”.
- Passaram 3 testes de interface do assistente, incluindo reinstalação, 6 do backend de configuração,
  19 do cadastro, 6 de favicon e 13 suítes CJS; typecheck e lint dos novos
  módulos verificados passaram.
- Na verificação da correção do instalador, `npm test` teve 309 testes aprovados,
  10 ignorados e duas suítes com falha: `clima_render.test.js` sem fixture e
  `ia_rail_dom.test.js` acessando um elemento inexistente. O lint geral registrou
  704 erros fora do assistente; lint dos arquivos JS alterados e typecheck passaram.
- Na abertura do painel empacotado, `/static/js/legacy.C8j9sdRf.js` retornou 404.
  O bundle existe sob `staticfiles/dist/js`; o prefixo Vite do desktop precisa
  de correção própria. Não foi mascarado nem contado como painel integralmente validado.
- macOS/Linux não foram compilados ou executados nesta máquina Windows.
- Download remoto por cultura e assinatura confiável continuam pendentes;
  o assistente atual prepara os perfis que já constam no catálogo local.

O projeto ainda não dispõe de certificado confiável. Os scripts de certificado
autoassinado não estabelecem confiança nos computadores dos produtores.
O [SignPath Foundation](https://signpath.org/terms.html) aceita candidaturas gratuitas
de projetos integralmente abertos sob licença OSI, sujeitos a aprovação. A licença
`UNLICENSED` do desktop e a licença de uso reservada precisam ser resolvidas pelo
titular antes de considerar essa candidatura; não foram alteradas pelo assistente.
No macOS, a [isenção da Apple](https://developer.apple.com/help/account/membership/fee-waivers/)
é limitada a organizações elegíveis, não uma assinatura gratuita geral.

O CI existente aceita `CODE_SIGN_CERTIFICATE` e `CODE_SIGN_PASSWORD`. Após obter
uma identidade confiável, valide o artefato assinado e o nome real do publicador:

```powershell
./build/verify-signature.ps1 -Artifact ./dist/Ampliagro-x64.exe -ExpectedPublisher 'Nome legal do publicador'
```

O comando rejeita assinatura inválida, publicador divergente e ausência de carimbo
de tempo. Não instala certificados raiz, não desativa proteção e não certifica a
ausência de malware. Mesmo arquivos assinados podem receber aviso de reputação:
[documentação Microsoft](https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/smartscreen-reputation).

Fases 0, 1 e 2 concluídas e verificadas. As medições estão em `PLAN.md`.

Limitações conhecidas, ambas por medir e não por suposição:

- **macOS**: não há Job Object nem `PR_SET_PDEATHSIG`, portanto o
  encerramento depende de o Electron matar explicitamente o filho. O
  Windows (Job Object) e o Linux (`PR_SET_PDEATHSIG`) estão medidos.
- **Serviços sem cache**: clima, geocodificação, tiles e cotações são
  travados pela CSP sem rede. O **clima já tem cache em JSON**
  (`clima.json`, no directório de dados) e mostra a última captura com a
  hora, ou `—`/`sem sinal`. Os outros não — vê-se a falha, não uma
  captura.
