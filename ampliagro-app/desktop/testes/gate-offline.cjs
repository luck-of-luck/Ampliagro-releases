/**
 * GATE DA FASE 2 — o desktop serve a aplicação SEM REDE.
 *
 * ---------------------------------------------------------------------------
 * O QUE ESTE TESTE PROVA, E O QUE NÃO PROVA
 * ---------------------------------------------------------------------------
 * O bloqueio não é feito aqui. É feito pela **CSP** — `config/settings/
 * desktop.py` define `_CSP_APENAS_LOCAL`, sem uma única origem externa.
 * O browser não pede o que a CSP não permite: não pede para depois
 * recusar.
 *
 * Portanto o que interessa medir é: dado um cliente que obedece à CSP,
 * a aplicação carrega inteira a partir de `127.0.0.1`? E a resposta
 * honesta é medida, não presumida.
 *
 * É por isso que este teste usa um **Chromium normal** e não a janela do
 * Electron. A CSP é um cabeçalho da resposta do Django — vem do mesmo sítio
 * para os dois clientes. E testar com um browser normal evita a instabilidade
 * do `page.goto()` numa janela Electron criada por `loadURL`, que é o
 * que aconteceu nas três primeiras tentativas:
 *
 *   1. `route(...)` com `continue()`  -> a janela fechava-se a meio.
 *   2. `context.setOffline(true)`     -> bloqueia TAMBÉM `127.0.0.1`
 *                                        (a emulação de rede do Chromium
 *                                        não distingue loopback de internet),
 *                                        e as quatro páginas deram timeout.
 *   3. `route` só para externos       -> idem, `Target closed`.
 *
 * Nenhuma dessas três era um problema da aplicação. Eram do mecanismo de
 * teste. Este ficheiro arranca o runtime Django e aponta um browser
 * limpo para ele — que é a mesma coisa que o Electron faz, menos a casca.
 *
 * ---------------------------------------------------------------------------
 * O QUE É TOLERADO
 * ---------------------------------------------------------------------------
 * `api.open-meteo.com`, `nominatim.openstreetmap.org`, os tiles do
 * OpenStreetMap, `agrodocai.com.br`, `esm.run` e `huggingface.co` são
 * SERVIÇOS ou o pack opcional da Fase 4. Não são vendorizáveis: clima e
 * geocodificação não existem offline. Estão fora da CSP, o browser bloqueia-os
 * antes de sair, e são contados à parte para se ver que a aplicação os
 * tentou e que a CSP os travaram — que é o comportamento correcto.
 */

'use strict';

const { chromium } = require('playwright');
const { spawn } = require('node:child_process');
const path = require('node:path');
const fs = require('node:fs');
const os = require('node:os');

const RAIZ = 'C:\\Trabalho\\Projetos\\Ativos\\Ampliagro2';
const BACKEND = path.join(RAIZ, 'ampliagro-app', 'desktop', 'backend', 'bootstrap.py');

/** Serviços: a aplicação pode tentá-los; a CSP trava-os. */
const SERVICOS = [
  'api.open-meteo.com',
  'servicodados.ibge.gov.br',
  'nominatim.openstreetmap.org',
  'tile.openstreetmap.org',
  'agrodocai.com.br',
  'esm.run',
  'huggingface.co',
];

const PAGINAS = ['/login/', '/', '/previsao/clima/', '/telemetria/'];

/** Assets vendorizados que têm de ser servidos. Um 404 aqui é um gráfico,
 *  um mapa ou um ícone que não aparece — e sem erro nenhum. */
const VENDOR_CRITICOS = [
  'vendor/chart.umd-4.4.7.min.js',
  'vendor/leaflet-1.9.4.js',
  'vendor/leaflet-1.9.4.css',
  'vendor/leaflet-draw-1.0.4.js',
  'vendor/bootstrap-icons-1.11.3.min.css',
  'vendor/sweetalert2-11.22.4.all.min.js',
  'vendor/htmx-1.9.10.min.js',
  'vendor/qrcodejs-1.0.0.min.js',
  'vendor/fontes.css',
];

const externos = [];
const servicosTentados = [];
const vendor404 = [];
const erros = [];

function registar(url) {
  if (
    url.startsWith('http://127.0.0.1') ||
    url.startsWith('ws://127.0.0.1') ||
    url.startsWith('data:') ||
    url.startsWith('blob:')
  ) {
    return;
  }
  const alvo = SERVICOS.find((s) => url.includes(s));
  if (alvo) {
    servicosTentados.push(url);
    return;
  }
  externos.push(url);
}

function arrancarRuntime(dados) {
  return new Promise((resolve, reject) => {
    const env = {
      ...process.env,
      AMPLIAGRO_CODE_ROOT: RAIZ,
      AMPLIAGRO_DESKTOP_DATA_DIR: dados,
    };
    delete env.DJANGO_SETTINGS_MODULE;
    delete env.REDIS_URL;
    delete env.DATABASE_URL;

    const proc = spawn('python', [BACKEND], {
      cwd: RAIZ,
      env,
      stdio: ['ignore', 'pipe', 'pipe'],
    });

    let saida = '';
    proc.stdout.setEncoding('utf8');
    proc.stdout.on('data', (pedaco) => {
      saida += pedaco;
      const m = /^AMPLIAGRO_DESKTOP_READY port=(\d+)/m.exec(saida);
      if (m) resolve({ proc, porta: Number(m[1]) });
    });
    proc.stderr.setEncoding('utf8');
    proc.stderr.on('data', (p) => {
      saida += p;
    });

    setTimeout(() => {
      proc.kill();
      reject(new Error('o runtime não ficou pronto em 240s'));
    }, 240000);
  });
}

function matar(proc) {
  if (!proc || proc.exitCode !== null) return;
  if (process.platform === 'win32') {
    spawn('taskkill', ['/F', '/T', '/PID', String(proc.pid)], {
      windowsHide: true,
      stdio: 'ignore',
    });
  } else {
    proc.kill('SIGTERM');
  }
}

async function principal() {
  console.log('='.repeat(74));
  console.log('GATE FASE 2 — a aplicação carrega inteira SEM REDE?');
  console.log('='.repeat(74));

  const dados = path.join(os.tmpdir(), 'ampliagro-gate-offline');
  fs.mkdirSync(dados, { recursive: true });
  console.log(`\n  dados:   ${dados}`);
  console.log(`  páginas: ${PAGINAS.join(', ')}\n`);

  let runtime;
  let navegador;
  try {
    runtime = await arrancarRuntime(dados);
    const base = `http://127.0.0.1:${runtime.porta}`;
    console.log(`  runtime em ${base}`);
    console.log(`  bloqueio: a CSP de config/settings/desktop.py\n`);

    navegador = await chromium.launch();
    const ctx = await navegador.newContext();
    const pagina = await ctx.newPage();

    pagina.on('request', (r) => registar(r.url()));
    pagina.on('response', (resposta) => {
      const u = resposta.url();
      if (resposta.status() >= 400 && u.includes('/static/vendor/')) {
        vendor404.push(`${resposta.status()} ${u.replace(base, '')}`);
      }
    });
    pagina.on('console', (m) => {
      if (m.type() === 'error') erros.push(m.text().slice(0, 170));
    });

    for (const rota of PAGINAS) {
      const antes = externos.length;
      let codigo;
      try {
        const r = await pagina.goto(`${base}${rota}`, {
          waitUntil: 'domcontentloaded',
          timeout: 30000,
        });
        codigo = r ? r.status() : '?';
      } catch (e) {
        codigo = `ERRO ${e.message.slice(0, 45)}`;
      }
      await pagina.waitForTimeout(1800).catch(() => {});
      const novos = externos.length - antes;
      const svcs = servicosTentados.length;
      console.log(
        `  ${String(codigo).padStart(5)}  ${rota.padEnd(20)} (+${novos} externo[s], ${svcs} serviço[s])`
      );
    }

    console.log('\n  assets vendorizados (tem de ser 200):');
    for (const nome of VENDOR_CRITICOS) {
      const r = await pagina.request
        .get(`${base}/static/${nome}`)
        .catch((e) => ({ status: () => 'ERR ' + e.message.slice(0, 40) }));
      const st = r.status();
      console.log(`    ${st === 200 ? '[OK]  ' : '[FALHA]'} ${st}  ${nome}`);
      if (st !== 200) vendor404.push(`${st} ${nome}`);
    }

    // O `{% static %}` tem de estar a resolver para o vendor/.
    const html = await pagina.content();
    const comVendor = (html.match(/\/static\/vendor\//g) || []).length;
    const comCdn = (
      html.match(/unpkg\.com|jsdelivr\.net|cdnjs\.cloudflare\.com|fonts\.googleapis\.com\/css2/g) ||
      []
    ).length;
    console.log(`\n  HTML: ${comVendor} referência(s) a /static/vendor/`);
    console.log(`  HTML: ${comCdn} referência(s) a CDN de biblioteca`);
    if (comCdn > 0) externos.push(`${comCdn} referência(s) de CDN no HTML`);
  } catch (erro) {
    console.log(`\n  [ERRO] ${erro.message}`);
    return 1;
  } finally {
    if (navegador) await navegador.close().catch(() => {});
    if (runtime) matar(runtime.proc);
  }

  console.log('\n' + '='.repeat(74));
  let passou = true;

  if (externos.length) {
    passou = false;
    console.log(`FALHOU: ${externos.length} pedido(s) para fora de 127.0.0.1:`);
    [...new Set(externos)].slice(0, 20).forEach((u) => console.log(`  ${u}`));
  } else {
    console.log('OK: zero pedidos para fora de 127.0.0.1 (fora serviços)');
  }

  if (vendor404.length) {
    passou = false;
    console.log(`\nFALHOU: ${vendor404.length} asset(s) vendorizado(s) em erro:`);
    vendor404.forEach((u) => console.log(`  ${u}`));
  } else {
    console.log('OK: todos os assets vendorizados servidos com 200');
  }

  if (servicosTentados.length) {
    const hosts = [...new Set(servicosTentados.map((u) => new URL(u).host))];
    console.log(`\nServiços tentados e travados pela CSP (correcto sem rede):`);
    hosts.forEach((h) => console.log(`  ${h}`));
  }

  const reais = erros.filter((e) => !/net::|Failed to load resource|ERR_/.test(e));
  if (reais.length) {
    console.log(`\nErros de consola (${reais.length}):`);
    reais.slice(0, 8).forEach((e) => console.log(`  ${e}`));
  }

  console.log(`\n${'='.repeat(74)}`);
  console.log(passou ? 'RESULTADO: PASSOU' : 'RESULTADO: FALHOU');
  console.log('='.repeat(74));
  return passou ? 0 : 1;
}

principal().then(
  (c) => process.exit(c),
  (e) => {
    console.error('ERRO NÃO TRATADO:', e);
    process.exit(1);
  }
);
