/**
 * Prova da janela: o Electron mostra o login REAL do Django?
 *
 * É o último item da Fase 0, e o único que ainda não estava medido. Até aqui
 * provaram-se coisas de Python (o runtime arranca, o `/healthz` responde, o
 * Daphne morre com o pai). Falta provar que a CASCA carrega a página e que a
 * página é a do Django — e não um ecrã em branco com o ícone na barra.
 *
 * ---------------------------------------------------------------------------
 * PORQUÊ PLAYWRIGHT E NÃO UM GANCHO EM `main.js`
 * ---------------------------------------------------------------------------
 * A primeira tentativa desta prova pedia ao `main.js` que escrevesse um
 * `janela-estado.json`. Descartada: isso é instrumentação de teste dentro
 * de código de produção, e `main.js` é o ficheiro que vai para o pacote.
 * O que fica no repositório é só o produto.
 *
 * O Playwright sabe conduzir Electron (`_electron.launch`), e já é
 * dependência deste projecto (`@playwright/test` no `package.json` da raiz).
 * Não acrescenta nada.
 *
 * ---------------------------------------------------------------------------
 * O QUE SEPARA "ABRIU UMA JANELA" DE "ABRIU O AMPLIAGRO"
 * ---------------------------------------------------------------------------
 * Uma janela branca tem título e tem URL. Por isso o teste não se contenta
 * com `waitForEvent('window')`: ele lê o TEXTO da página e procura o
 * formulário de login. É a diferença entre um título certo e o Ampliagro
 * certo.
 */

'use strict';

const { _electron: electron } = require('playwright');
const path = require('node:path');
const fs = require('node:fs');
const os = require('node:os');

/**
 * Onde está o binário do Electron.
 *
 * Não se deixa o Playwright adivinhar: ele procura `electron` a partir da
 * SUA própria árvore de módulos, e o `playwright` vive no `node_modules`
 * da raiz do repositório enquanto o Electron vive em
 * `ampliagro-app/desktop/node_modules`. Erro medido na primeira tentativa:
 * "Electron executablePath not found!".
 *
 * `require("electron")` fora do Electron devolve o caminho do binário, em
 * Windows, Linux e macOS. Um caminho escrito à mão seria uma fonte de erro
 * por SO.
 */
const BINARIO_ELECTRON = require('electron');

const RAIZ = 'C:\\Trabalho\\Projetos\\Ativos\\Ampliagro2';
const PASTA = path.join(RAIZ, 'ampliagro-app', 'desktop');
const DADOS = path.join(os.tmpdir(), 'ampliagro-desktop-janela');
const CAPTURA = path.join(os.tmpdir(), 'ampliagro-login.png');

const falhas = [];
const ok = (m) => console.log(`  [OK]    ${m}`);
const falha = (m) => {
  console.log(`  [FALHA] ${m}`);
  falhas.push(m);
};

/** Palavras que só aparecem no login do Ampliagro, não numa página em branco. */
const MARCAS_LOGIN = ['login', 'entrar', 'utilizador', 'email', 'senha', 'palavra-passe'];

async function principal() {
  console.log('='.repeat(72));
  console.log('PROVA DA JANELA — o Electron mostra o login do Django?');
  console.log('='.repeat(72));
  console.log(`\n  dados: ${DADOS}`);

  fs.mkdirSync(DADOS, { recursive: true });

  let app;
  try {
    console.log('  a arrancar o Electron…');
    app = await electron.launch({
      args: [PASTA],
      cwd: PASTA,
      executablePath: BINARIO_ELECTRON,
      env: {
        ...process.env,
        AMPLIAGRO_CODE_ROOT: RAIZ,
        AMPLIAGRO_DESKTOP_DATA_DIR: DADOS,
      },
      timeout: 240000, // migrate + daphne + janela numa base nova
    });

    // ---- 1. a janela principal aparece ----
    console.log('  a esperar pela janela…');
    let janela = await app.firstWindow({ timeout: 240000 });
    await janela.waitForLoadState('domcontentloaded');
    if (janela.url().endsWith('/installer.html')) {
      const existente = fs.existsSync(path.join(DADOS, 'installation.json'));
      if (existente) {
        janela = await app.waitForEvent('window', { timeout: 240000 });
      } else {
        await janela.locator('#terms').waitFor({ state: 'visible', timeout: 240000 });
        await janela.locator('#accepted').check();
        await janela.locator('#next').click();
        await janela.locator('#next').click();
        await janela
          .locator('#cultures details')
          .first()
          .evaluate((el) => {
            el.open = true;
          });
        await janela.locator('#cultures input').first().check();
        await janela.locator('#next').click();
        await janela.locator('#step-3').waitFor({ state: 'visible' });
        const proxima = app.waitForEvent('window');
        await janela.locator('#next').click();
        janela = await proxima;
      }
      await janela.waitForURL(/127\.0\.0\.1:\d+/, { timeout: 180000 });
    }
    ok('janela criada');

    // ---- 2. a página carregou (não ficou em 'about:blank') ----
    await janela.waitForLoadState('domcontentloaded', { timeout: 180000 });
    const url = janela.url();
    if (/127\.0\.0\.1:\d+/.test(url)) {
      ok(`carregou o loopback (${url})`);
    } else {
      falha(`URL inesperada: ${url}`);
    }

    // ---- 3. O QUE ESTÁ NO ECRÃ ----
    console.log('  a ler o texto da página…');
    await janela.waitForTimeout(3000);
    const texto = (
      await janela
        .locator('body')
        .innerText()
        .catch(() => '')
    ).toLowerCase();
    const html = (await janela.content().catch(() => '')).toLowerCase();

    const encontrou = MARCAS_LOGIN.filter((m) => texto.includes(m) || html.includes(m));
    if (encontrou.length > 0) {
      ok(`marcas de login encontradas: ${encontrou.join(', ')}`);
    } else {
      falha(
        'a página não parece o login — nenhuma marca de login. ' +
          'Provável ecrã em branco com título certo.'
      );
    }

    // ---- 4. o preload expõe a ponte (e nada mais) ----
    const ponte = await janela
      .evaluate(() => {
        if (typeof window.ampliagro === 'undefined') return null;
        return {
          versao: window.ampliagro.versao,
          chaves: Object.keys(window.ampliagro),
          temNode: typeof window.require !== 'undefined',
          temProcess: typeof window.process !== 'undefined',
        };
      })
      .catch(() => null);

    if (ponte) {
      ok(`ponte do preload exposta: ${JSON.stringify(ponte.chaves)}`);
      if (ponte.temNode || ponte.temProcess) {
        falha(
          'o contexto da página tem require/process — contextIsolation ou ' +
            'sandbox NÃO estão a fazer efeito'
        );
      } else {
        ok('contexto da página isolado (sem require, sem process)');
      }
    } else {
      falha('window.ampliagro indefinido — o preload não carregou');
    }

    // ---- 5. captura de ecrã ----
    console.log('  a capturar o ecrã…');
    const png = await janela.screenshot({ path: CAPTURA }).catch((e) => {
      falha(`captura falhou: ${e.message}`);
      return null;
    });
    if (png) {
      const bytes = fs.statSync(CAPTURA).size;
      if (bytes > 5000) {
        ok(`captura ${(bytes / 1024).toFixed(0)} KB -> ${CAPTURA}`);
      } else {
        falha(`captura com ${bytes} bytes — ecrã praticamente vazio`);
      }
    }

    // ---- 6. título ----
    const titulo = await janela.title();
    console.log(`     título: ${JSON.stringify(titulo)}`);
  } catch (erro) {
    falha(`excepção: ${erro.message}`);
    console.log(erro.stack);
  } finally {
    if (app) {
      console.log('\n  a fechar o Electron…');
      await app.close().catch(() => {});
    }
  }
}

principal()
  .then(() => {
    console.log('\n' + '='.repeat(72));
    console.log('RESULTADO:', falhas.length ? 'FALHOU' : 'PASSOU');
    falhas.forEach((f) => console.log('  -', f));
    console.log('='.repeat(72));
    process.exit(falhas.length ? 1 : 0);
  })
  .catch((e) => {
    console.error('ERRO NÃO TRATADO:', e);
    process.exit(1);
  });
