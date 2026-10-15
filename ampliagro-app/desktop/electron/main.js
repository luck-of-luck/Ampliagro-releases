/**
 * Processo principal do Electron — a casca do Ampliagro Desktop.
 *
 * O Electron inicia e acompanha o runtime Django. Ele:
 *   1. arranca `backend/bootstrap.py` como processo filho;
 *   2. lê UMA linha do stdout — `AMPLIAGRO_DESKTOP_READY port=… pid=…`;
 *   3. configura a instalação pela ponte privada de setup e abre a janela;
 *   4. no fecho, mata o bootstrap.
 *
 * Porquê um processo separado e não correr o Django dentro do Electron:
 * o runtime Python é uma dependência grande e nativa (ver ADR-001) que
 * tem de sobreviver à mesma matriz de empacotamento em todos os SOs, e
 * que precisa de um `python.exe`/`python3` próprio. Casá-lo com o
 * binário do Electron seria uma segunda matriz de empacotamento para
 * manter por causa de conveniência.
 *
 * ---------------------------------------------------------------------------
 * O CONTRACTO DE stdout — se isto mudar, o bootstrap.py muda com ele
 * ---------------------------------------------------------------------------
 * `AMPLIAGRO_DESKTOP_READY port=<int> pid=<int> status=<str>`
 *
 * Tudo o que o bootstrap escreve em stderr é log e vai para o consola.
 * Tudo o que escreve em stdout é canal de comando. Um `console.log`
 * esquecido no bootstrap parte este protocolo em silêncio — a janela
 * ficaria à espera de um READY que nunca chega. É a razão de o bootstrap
 * ter uma função `log()` que escreve só em stderr.
 */

'use strict';

const { spawn } = require('node:child_process');
const path = require('node:path');
const fs = require('node:fs');
const os = require('node:os');
const { randomBytes, createHash } = require('node:crypto');
const { app, BrowserWindow, shell, dialog, Menu } = require('electron');
const { autoUpdater } = require('electron-updater');
const { setup } = require('./setup');

const setupToken = randomBytes(32).toString('hex');
const terms = fs.readFileSync(path.join(__dirname, '../build/license.txt'), 'utf8');
const termsHash = createHash('sha256').update(terms).digest('hex');

/** Onde vive o runtime Python. Em desenvolvimento, o interpretador do sistema. */
function resolverPython() {
  if (process.env.AMPLIAGRO_DESKTOP_PYTHON) {
    return process.env.AMPLIAGRO_DESKTOP_PYTHON;
  }
  // `process.env.ComSpec` só existe no Windows. Nos outros SOs o nome é
  // `python3`. Fallar para `python` e não para `python3` seria o inverso:
  // em Windows o `python` da Microsoft Store é um alias que abre a loja.
  const nome = process.platform === 'win32' ? 'python' : 'python3';
  return nome;
}

/** Directório de dados por-utilizador, como manda cada SO. */
function directorioDados() {
  if (process.env.AMPLIAGRO_DESKTOP_DATA_DIR) {
    return process.env.AMPLIAGRO_DESKTOP_DATA_DIR;
  }
  return path.join(app.getPath('userData'), 'dados');
}

/** Janela principal. Guardada em módulo para o evento `activate`. */
let janelaPrincipal = null;

/** O bootstrap. Guardado para o podermos matar no fecho. */
let processoBootstrap = null;

/** Preenchido a partir da linha READY. */
const servidor = { porta: null, pid: null, url: null };

/**
 * Lê o stdout do bootstrap à procura da linha READY.
 *
 * Devolve uma Promise. É o ÚNICO ponto onde o Electron espera pelo Django,
 * e espera pelo `/healthz` lá dentro do bootstrap — não aqui. Duplicar o
 * health-check aqui seria duas fontes de verdade sobre "o servidor está de
 * pé", e elas iam divergir no dia em que uma health-check mais.
 */
function esperarPronto(processo, timeoutMs = 180000) {
  return new Promise((resolve, reject) => {
    let acumulado = '';
    let resolvido = false;

    const temporizador = setTimeout(() => {
      if (resolvido) return;
      resolvido = true;
      reject(
        new Error(
          `O runtime não ficou pronto em ${timeoutMs / 1000}s.\n` +
            `Ver a saída do processo abaixo para a causa.`
        )
      );
    }, timeoutMs);

    processo.stdout.setEncoding('utf8');
    processo.stdout.on('data', (pedaco) => {
      acumulado += pedaco;

      // Uma linha de cada vez. `indexOf` + corte, porque o READY pode vir
      // colado a linhas de log anteriores no mesmo pacote.
      let corte;
      while ((corte = acumulado.indexOf('\n')) !== -1) {
        const linha = acumulado.slice(0, corte).trim();
        acumulado = acumulado.slice(corte + 1);

        if (!linha.startsWith('AMPLIAGRO_DESKTOP_READY')) {
          process.stdout.write(`  ${linha}\n`);
          continue;
        }

        const m = /^AMPLIAGRO_DESKTOP_READY port=(\d+) pid=(\d+) status=(\S+)$/.exec(linha);
        if (!m) {
          // Linha com a forma errada. Registar e continuar a procurar é
          // melhor que aceitar: aceitar uma porta mal lida faz a janela
          // abrir no sítio errado, e o sintoma (página em branco) não
          // aponta para a linha de protocolo.
          process.stderr.write(`[electron] linha READY com formato inesperado: ${linha}\n`);
          continue;
        }

        if (resolvido) continue;
        resolvido = true;
        clearTimeout(temporizador);
        resolve({ porta: Number(m[1]), pid: Number(m[2]), status: m[3] });
      }
    });

    processo.on('exit', (codigo, sinal) => {
      if (resolvido) return;
      resolvido = true;
      clearTimeout(temporizador);
      reject(
        new Error(
          `O runtime terminou antes de ficar pronto (código ${codigo}${
            sinal ? `, sinal ${sinal}` : ''
          }).`
        )
      );
    });

    processo.on('error', (erro) => {
      if (resolvido) return;
      resolvido = true;
      clearTimeout(temporizador);
      reject(erro);
    });
  });
}

/** Arranca o runtime e devolve `{porta, pid}`. */
async function arrancarRuntime() {
  const dados = directorioDados();
  fs.mkdirSync(dados, { recursive: true });

  // ---------------------------------------------------------------------------
  // DETECÇÃO DE AMBIENTE EMPACOTADO (inclui portable)
  // ---------------------------------------------------------------------------
  // `app.isPackaged` deve ser true em qualquer build do electron-builder.
  // Porém, em alguns casos (portable em certas versões do electron-builder)
  // pode retornar false. Fallback: verifica se o runtime congelado existe
  // no caminho esperado — se existir, trata-se como empacotado.
  const runtimeExe = path.join(
    process.resourcesPath,
    'runtime',
    'ampliagro-runtime',
    process.platform === 'win32' ? 'ampliagro-runtime.exe' : 'ampliagro-runtime'
  );
  const runtimeExiste = fs.existsSync(runtimeExe);
  const empacotado = app.isPackaged || runtimeExiste;

  process.stdout.write(`[electron] isPackaged: ${app.isPackaged}\n`);
  process.stdout.write(`[electron] resourcesPath: ${process.resourcesPath}\n`);
  process.stdout.write(`[electron] runtimeExe: ${runtimeExe}\n`);
  process.stdout.write(`[electron] runtimeExiste: ${runtimeExiste}\n`);
  process.stdout.write(`[electron] empacotado: ${empacotado}\n`);

  let executavel;
  let args = [];
  let cwd;
  const raizCodigo = process.env.AMPLIAGRO_CODE_ROOT || '';

  if (empacotado) {
    executavel = runtimeExe;
    if (!runtimeExiste) {
      throw new Error(`runtime congelado não encontrado em ${runtimeExe}`);
    }
    cwd = path.dirname(executavel);
  } else {
    const raiz = process.env.AMPLIAGRO_CODE_ROOT || path.resolve(__dirname, '..', '..', '..');
    const bootstrap = path.join(raiz, 'ampliagro-app', 'desktop', 'backend', 'bootstrap.py');
    if (!fs.existsSync(bootstrap)) {
      throw new Error(`bootstrap.py não encontrado em ${bootstrap}`);
    }
    executavel = resolverPython();
    args = [bootstrap];
  }

  const ambiente = {
    ...process.env,
    AMPLIAGRO_DESKTOP_DATA_DIR: dados,
    AMPLIAGRO_SETUP_TOKEN: setupToken,
    AMPLIAGRO_TERMS_HASH: termsHash,
    // O `.env` do projecto tem REDIS_URL e DATABASE_URL a apontar para a
    // cloud. `config/settings/desktop.py` já os ignora, mas limpamos
    // também aqui para que o child não os herde por fora do Django.
    REDIS_URL: undefined,
    DATABASE_URL: undefined,
  };
  if (raizCodigo) {
    ambiente.AMPLIAGRO_CODE_ROOT = raizCodigo;
  }

  process.stdout.write(`[electron] runtime: ${executavel}\n`);
  process.stdout.write(`[electron] dados:   ${dados}\n`);

  const processo = spawn(executavel, args, {
    cwd,
    env: ambiente,
    // `windowsHide` evita uma janela de consola do Python a saltar por
    // cima da janela da app. O log continua a chegar ao consola do
    // Electron porque o `stdio` está em `pipe`.
    windowsHide: true,
    stdio: ['ignore', 'pipe', 'pipe'],
  });

  processoBootstrap = processo;
  processo.stderr.setEncoding('utf8');
  processo.stderr.on('data', (pedaco) => process.stderr.write(pedaco));

  return esperarPronto(processo);
}

/** Mata o bootstrap. O SO garante que o Daphne vai com ele (Job Object). */
function pararRuntime() {
  if (!processoBootstrap || processoBootstrap.exitCode !== null) {
    processoBootstrap = null;
    return;
  }
  const proc = processoBootstrap;
  processoBootstrap = null;

  if (process.platform === 'win32') {
    // `/T` mata a árvore inteira. Redundante com o Job Object, e é
    // precisamente essa arazão de ficar: se um dia alguém mexer no job,
    // esta linha ainda apanha o caso comum.
    spawn('taskkill', ['/F', '/T', '/PID', String(proc.pid)], {
      windowsHide: true,
      stdio: 'ignore',
    });
  } else {
    proc.kill('SIGTERM');
  }
}

function criarJanela(url) {
  janelaPrincipal = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 1024,
    minHeight: 700,
    // O produtor tem de ver a barra de janela: é uma aplicação de
    // trabalho, não um kiosk.
    autoHideMenuBar: false,
    backgroundColor: '#ffffff',
    show: false, // mostra depois de `ready-to-show`, para não piscar branco
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      // `contextIsolation` e `sandbox` ficam LIGADOS. Desligar
      // `contextIsolation` daria ao pré-carregado — e ao que for
      // injectado — acesso directo ao `window`, o que com 606 handlers
      // `on*=` nos templates é exactamente a superfície que não se quer
      // aberta. Ver o ficheiro `preload.js` para o que é exposto.
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      spellcheck: false,
    },
  });

  janelaPrincipal.once('ready-to-show', () => janelaPrincipal.show());

  /**
   * Navegação para fora da origem = link externo, não página interna.
   *
   * Sem isto, um `target="_blank"` nos templates abre a página dentro da
   * janela da app e o produtor fica com uma tela de login do Google
   * "dentro" do Ampliagro, sem barra de endereço onde voltar.
   */
  janelaPrincipal.webContents.setWindowOpenHandler(({ url: destino }) => {
    if (new URL(destino).origin === new URL(url).origin) return { action: 'allow' };
    if (/^https?:/.test(destino)) shell.openExternal(destino);
    return { action: 'deny' };
  });

  /**
   * Bloqueia a navegação para fora da origem.
   *
   * O `will-navigate` dispararia se alguém fizesse `location.href=` para
   * um site externo — e a partir daí a janela deixa de estar coberta pela
   * CSP do Django (que é por origem) sem que nada avise.
   */
  janelaPrincipal.webContents.on('will-navigate', (evento, destino) => {
    if (new URL(destino).origin !== new URL(url).origin) {
      evento.preventDefault();
      if (/^https?:/.test(destino)) shell.openExternal(destino);
    }
  });

  janelaPrincipal.on('closed', () => {
    janelaPrincipal = null;
  });

  return janelaPrincipal.loadURL(url);
}

// ---------------------------------------------------------------------------
// Ciclo de vida
// ---------------------------------------------------------------------------

// macOS fecha as janelas e deixa o processo vivo. Sem isto, fechar a janela
// no macOS deixaria o servidor a correr sem janela nenhuma.
app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0 && servidor.url) {
    criarJanela(servidor.url);
  }
});

/**
 * `before-quit` e não `will-quit`: é o último ponto em que o Node ainda
 * corre código de forma síncrona e em que o Electron ainda não matou o
 * processo. Sem este gancho, fechar a janela deixava o Daphne vivo — foi
 * o bug que a medição apanhou, agora coberto pelo Job Object *e* por isto.
 */
app.on('before-quit', pararRuntime);

process.on('exit', pararRuntime);

/** Configuração do auto-updater. */
function configurarAutoUpdater() {
  // A versão da Store é atualizada pela própria loja.
  if (process.windowsStore) return;
  // Canal de release: 'stable' ou 'beta'
  const canal = process.env.AMPLIAGRO_UPDATE_CHANNEL || 'stable';
  autoUpdater.channel = canal;
  autoUpdater.autoDownload = false; // Pergunta antes de baixar
  autoUpdater.autoInstallOnAppQuit = true;

  autoUpdater.on('checking-for-update', () => {
    process.stdout.write(`[updater] A verificar actualizações (canal: ${canal})...\n`);
  });

  autoUpdater.on('update-available', (info) => {
    process.stdout.write(`[updater] Nova versão disponível: ${info.version}\n`);
    // Pergunta ao utilizador se quer actualizar
    dialog
      .showMessageBox(janelaPrincipal, {
        type: 'info',
        title: 'Actualização disponível',
        message: `Ampliagro ${info.version} está disponível.`,
        detail: `Versão actual: ${app.getVersion()}\nNova versão: ${info.version}\n\nDeseja baixar e instalar agora?`,
        buttons: ['Actualizar agora', 'Mais tarde'],
        defaultId: 0,
        cancelId: 1,
      })
      .then(({ response }) => {
        if (response === 0) {
          autoUpdater.downloadUpdate();
        }
      });
  });

  autoUpdater.on('update-not-available', (info) => {
    process.stdout.write(`[updater] Já na versão mais recente (${info.version})\n`);
  });

  autoUpdater.on('error', (err) => {
    process.stderr.write(`[updater] Erro: ${err.message}\n`);
  });

  autoUpdater.on('download-progress', (progress) => {
    const pct = Math.round(progress.percent);
    if (janelaPrincipal) {
      janelaPrincipal.setProgressBar(pct / 100);
      janelaPrincipal.setTitle(`Ampliagro — a baixar ${pct}%`);
    }
  });

  autoUpdater.on('update-downloaded', (info) => {
    if (janelaPrincipal) janelaPrincipal.setProgressBar(-1);
    dialog
      .showMessageBox(janelaPrincipal, {
        type: 'info',
        title: 'Actualização pronta',
        message: `Ampliagro ${info.version} descarregado.`,
        detail: 'A actualização será instalada ao reiniciar a aplicação.',
        buttons: ['Reiniciar agora', 'Depois'],
        defaultId: 0,
        cancelId: 1,
      })
      .then(({ response }) => {
        if (response === 0) {
          autoUpdater.quitAndInstall(false, true);
        }
      });
  });

  // Verifica ao arrancar (depois da janela estar pronta) e a cada 4 horas.
  //
  // `verificarActualizacoes` existe porque `checkForUpdates()` DEVOLVE UMA
  // PROMISE que rejeita, e o `on('error')` de cima não a apanha: uma coisa é
  // o evento, outra é a promessa. Sem o `catch`, uma falha de rede — ou um
  // `latest.yml` que ainda não foi publicado no release — produz
  // `UnhandledPromiseRejectionWarning` no arranque, e isso é um aviso do
  // Electron, não uma nota: o Node pode matar o processo com
  // `--unhandled-rejections=strict`, e o Electron activa-o por omissão em
  // versões futuras. O Desktop fechava sozinho por causa de um 404 numa
  // página que ninguém está a ver.
  const verificarActualizacoes = () => {
    Promise.resolve()
      .then(() => autoUpdater.checkForUpdates())
      .catch(() => {
        // Já registado em `autoUpdater.on('error')`. Aqui só se engole: um
        // segundo relatório da mesma falha é ruído, e a aplicação tem de
        // continuar a funcionar sem actualizador — é o que acontece quando o
        // produtor está offline, que é o caso normal deste produto.
      });
  };

  // Ao arrancar (depois de a janela estar pronta), e depois a cada 4 horas.
  setTimeout(verificarActualizacoes, 5000);
  setInterval(verificarActualizacoes, 4 * 60 * 60 * 1000);
}

async function principal() {
  Menu.setApplicationMenu(null);

  try {
    const ready = arrancarRuntime().then((info) => {
      servidor.porta = info.porta;
      servidor.pid = info.pid;
      servidor.url = `http://127.0.0.1:${info.porta}`;
      process.stdout.write(
        `[electron] runtime pronto em ${servidor.url} (daphne pid=${info.pid}, status=${info.status})\n`
      );
      return servidor.url;
    });
    // O assistente aparece enquanto o banco local é preparado.
    ready.catch((erro) => process.stderr.write(`[setup] ${erro.message}\n`));
    const configured = await setup({ ready, token: setupToken, terms, termsHash });
    servidor.url = configured.destination;
    await criarJanela(configured.destination);
    configured.close();
    configurarAutoUpdater();
  } catch (erro) {
    if (erro.message === 'Configuração cancelada') return;
    // Um ecrã de erro com a CAUSA, não com "algo correu mal". O produtor
    // vai ver isto e tem de saber se foi Python em falta, porta ocupada,
    // ou settings errados.
    dialog.showErrorBox(
      'Ampliagro Desktop — o runtime não arrancou',
      `${erro.message}\n\n` +
        `Python usado: ${resolverPython()}\n` +
        `Dados: ${directorioDados()}\n` +
        `Plataforma: ${os.platform()} ${os.release()}\n\n` +
        `A saída do processo está no consola.`
    );
    pararRuntime();
    app.exit(1);
  }
}

// `ready` antes de arrancar o runtime: `dialog` e `BrowserWindow` só
// existem depois disto.
app.whenReady().then(principal);
