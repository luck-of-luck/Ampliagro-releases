'use strict';

const path = require('node:path');
const { pathToFileURL } = require('node:url');
const { BrowserWindow, ipcMain, app } = require('electron');

function webURL(value) {
  if (!value) return null;
  const url = new URL(value);
  if (url.protocol !== 'https:' || url.username || url.password || url.hash) {
    throw new Error('AMPLIAGRO_WEB_URL deve ser uma URL HTTPS sem credenciais ou fragmento.');
  }
  return url.href;
}

/**
 * Para onde a janela principal vai depois do assistente.
 *
 * O PRODUTOR TEM DE ENTRAR PELO LOGIN. Abrir a raiz (`/`) mostra o painel
 * a quem ainda nao tem conta — e a primeira coisa que ele ve e' um painel
 * vazio, nao uma pergunta. Por isso o destino e' sempre `/login/`.
 *
 * `?primeiro=1` diz ao template para perguntar "e o primeiro acesso?" e
 * oferecer o cadastro. Nao e' um booleano de estado: e' uma PERGUNTA. O
 * template mostra-a sempre que o parametro vem, mesmo que ja existam
 * contas na base — quem abre o desktop pela segunda vez e' perguntado
 * outra vez e fecha com "nao". O que decide se a pergunta aparece e' o
 * parametro; o que decide se e' a primeira vez a base esta vazio.
 *
 * `url.origin` da' a origem; o caminho e' reescrito por `new URL()`.
 * A origem e' o que `main.js` usa para travar a navegacao, e nao muda.
 */
function destinoDaApp(base) {
  return new URL('/login/?primeiro=1', base).href;
}

async function setup({ ready, token, terms, termsHash }) {
  const root = app.isPackaged
    ? path.join(process.resourcesPath, 'setup')
    : path.resolve(__dirname, '../../..');
  const page = path.join(root, 'installer.html');
  const officialURL = webURL(process.env.AMPLIAGRO_WEB_URL);
  let installation;
  let busy = false;
  const window = new BrowserWindow({
    width: 1100,
    height: 800,
    minWidth: 760,
    minHeight: 650,
    title: 'Preparar seu Ampliagro',
    backgroundColor: '#101918',
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, 'setup-preload.js'),
      contextIsolation: true,
      sandbox: true,
      nodeIntegration: false,
    },
  });
  window.webContents.setWindowOpenHandler(() => ({ action: 'deny' }));
  window.webContents.on('will-navigate', (event) => event.preventDefault());
  const trusted = (event) => {
    if (
      event.sender !== window.webContents ||
      event.senderFrame !== window.webContents.mainFrame ||
      event.senderFrame.url !== pathToFileURL(page).href
    )
      throw new Error('Origem não autorizada');
  };
  async function request(method, data) {
    const base = await ready;
    const response = await fetch(`${base}/desktop/setup/`, {
      method,
      redirect: 'error',
      signal: AbortSignal.timeout(30000),
      headers: { 'X-Ampliagro-Setup': token, 'Content-Type': 'application/json' },
      body: data ? JSON.stringify(data) : undefined,
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.erro || `Falha na configuração (${response.status})`);
    return result;
  }
  return new Promise((resolve, reject) => {
    let finished = false;
    const clean = () =>
      ['setup:read', 'setup:save', 'setup:open'].forEach((channel) =>
        ipcMain.removeHandler(channel)
      );
    ipcMain.handle('setup:read', async (event) => {
      trusted(event);
      const data = await request('GET');
      installation = data.installation;
      return {
        ...data,
        terms,
        termsHash,
        officialURL,
        forceSetup: process.argv.includes('--ampliagro-setup'),
      };
    });
    ipcMain.handle('setup:save', async (event, data) => {
      trusted(event);
      if (busy) throw new Error('Preparação em andamento');
      if (data?.mode === 'cloud' && !officialURL) throw new Error('Servidor web indisponível');
      busy = true;
      try {
        const result = await request('POST', data);
        installation = result.installation;
        return result;
      } finally {
        busy = false;
      }
    });
    ipcMain.handle('setup:open', async (event) => {
      trusted(event);
      if (!installation || installation.termsHash !== termsHash)
        throw new Error('Conclua a configuração primeiro');
      const destination = installation.mode === 'cloud' ? officialURL : await ready;
      if (!destination) throw new Error('Configure o endereço do servidor web para continuar');
      finished = true;
      clean();
      resolve({ destination: destinoDaApp(destination), close: () => window.close() });
    });
    window.on('closed', () => {
      clean();
      if (!finished) {
        reject(new Error('Configuração cancelada'));
        app.quit();
      }
    });
    window.loadFile(page).catch(reject);
  });
}

module.exports = { setup, webURL, destinoDaApp };
