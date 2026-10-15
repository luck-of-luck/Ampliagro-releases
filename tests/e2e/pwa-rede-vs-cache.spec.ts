/**
 * separa o que VEIO DA REDE do que veio do service worker.
 *
 * O spec anterior mediu 1603 KB e 448 ms de FCP. Esses dois numeros nao
 * batem: a 1,6 Mbps, 1603 KB levariam ~8 segundos. A explicacao e que o
 * `transferSize` conta o que o renderer recebeu — incluindo o que o service
 * worker entregou do cache, que nao passou pela rede.
 *
 * Este spec separa as duas coisas, porque a distincao muda a conclusao:
 * 1603 KB do cache e um numero de RAM. 1603 KB da rede e uma factura.
 */
import { test } from '@playwright/test';

test('rede vs cache no primeiro carregamento a 3G', async ({ page }) => {
  await page.goto('/login/');
  await page.fill('input[name="usuario"]', 'demo');
  await page.fill('input[name="senha"]', 'demo123');
  await page.click('button[type="submit"]');
  await page.waitForLoadState('networkidle');
  await page.evaluate(() => navigator.serviceWorker.ready);
  await page.waitForTimeout(400);

  const cdp = await page.context().newCDPSession(page);
  await cdp.send('Network.enable');
  await cdp.send('Network.emulateNetworkConditions', {
    offline: false,
    downloadThroughput: (1600 * 1000) / 8,
    uploadThroughput: (1600 * 1000) / 8,
    latency: 300,
  });

  let rede = 0;
  let cache = 0;
  let daRede = 0;
  let doCache = 0;
  const pesoRede = new Map();

  page.on('response', async (r) => {
    try {
      const len = Number(r.headers()['content-length'] || 0);
      const doSW = r.fromServiceWorker();
      if (doSW) {
        doCache++;
        cache += len;
      } else {
        daRede++;
        rede += len;
        const u = new URL(r.url());
        pesoRede.set(u.pathname + u.search, (pesoRede.get(u.pathname + u.search) || 0) + len);
      }
    } catch {
      /* resposta sem headers (redirect, data:) — nao conta */
    }
  });

  const t0 = Date.now();
  await page.goto('/', { waitUntil: 'load' });
  const ms = Date.now() - t0;
  await page.waitForTimeout(600);
  await cdp.detach();

  const kb = (n: number) => (n / 1024).toFixed(0) + ' KB';
  console.log('\n══════ CARREGAMENTO A 3G, cache ja aquecido ══════');
  console.log(`  load                    : ${ms} ms`);
  console.log(`  respostas DA REDE       : ${daRede}  (${kb(rede)})`);
  console.log(`  respostas DO SW CACHE   : ${doCache}  (${kb(cache)})`);
  console.log('  o que foi mesmo de rede:');
  [...pesoRede.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, 10)
    .forEach(([u, b]) => console.log(`    ${kb(b).padStart(8)}  ${u.slice(0, 60)}`));
  console.log('═════════════════════════════════════════════════\n');
});
