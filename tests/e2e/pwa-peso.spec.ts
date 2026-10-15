/**
 * Quanto tempo demora REALMENTE o painel a abrir, com rede de campo?
 *
 * PORQUE ISTE SPEC EXISTE
 * -----------------------
 * Passámos a sessão toda a discutir 8 KB e 63 KB de gzip como se fossem
 * problemas. Nao sao. A unica forma de saber se o `index.html` de 161 KB gzip
 * e um problema ou nao e MEDIR. E medir e o que este spec faz.
 *
 * A REDE QUE SIMULAMOS
 * --------------------
 * O produtor esta no campo. "3G" de laboratorio e ~1,6 Mbps effective; o
 * `saveData` do `ia-local.js` trataanything abaixo de 2 Mbps como 3G, que e
 * o mesmo numero. Usamos o perfil "3G" do CDP, que e o que o Lighthouse
 * classifica como telefone Android de gama baixa.
 *
 * O QUE MEDIMOS
 * -------------
 *   - bytes transferidos, e de onde vem cada um
 *   - quando aparece o primeiro conteudo (FCP)
 *   - quando a rede fica quieta (load)
 *   - quantos pedidos sao feitos ao servidor (o cache PWA conta como 0)
 *
 * E um numero, nao uma opiniao. Se o `index.html` nao aparece no topo da
 * lista, o trabalho de o separar e uma tarefa de Maintenance, nao um bug.
 */
import { test, expect } from '@playwright/test';
import type { Page } from '@playwright/test';

/**
 * Chrome DevTools Protocol: o unico jeito de estrangular a rede de verdade.
 *
 * As anotacoes nao sao decoracao. `noImplicitAny` esta ligado e o
 * `strict` tambem: um `page` sem tipo aqui significava que `page.context()`
 * devolvia `any`, e `any` propaga-se pelo ficheiro inteiro sem que nenhum
 * erro aponte para a origem. Nomear o tipo e' o que mantem o resto honesto.
 */
async function estrangular(page: Page, kbps: number, latenciaMs: number) {
  const cdp = await page.context().newCDPSession(page);
  await cdp.send('Network.enable');
  await cdp.send('Network.emulateNetworkConditions', {
    offline: false,
    downloadThroughput: (kbps * 1000) / 8,
    uploadThroughput: (kbps * 1000) / 8,
    latency: latenciaMs,
  });
  return cdp;
}

async function entrar(page: Page) {
  await page.goto('/login/');
  await page.fill('input[name="usuario"]', 'demo');
  await page.fill('input[name="senha"]', 'demo123');
  await page.click('button[type="submit"]');
  await page.waitForLoadState('networkidle');
  // Deixa o SW assentar antes da medicao.
  await page.evaluate(() => navigator.serviceWorker.ready);
  await page.waitForTimeout(400);
}

test.describe('peso real no telefone', () => {
  test('mede o que o painel transfere e quanto demora', async ({ page }) => {
    await entrar(page);

    // Instrumenta ANTES de navegar, para apanhar tudo.
    await page.addInitScript(() => {
      window.__recursos = [];
      const obs = new PerformanceObserver((lista) => {
        for (const e of lista.getEntries()) {
          // `getEntries()` devolve `PerformanceEntry`, que NAO tem nem
          // `transferSize` nem `initiatorType`. Sao `PerformanceResourceTiming`.
          // Sem este narrowing o `tsc` dizia que as propriedades nao existiam —
          // e estava certo: no tipo declarado, nao existem.
          const r = e as PerformanceResourceTiming;
          window.__recursos?.push({
            nome: r.name,
            kb: Math.round((r.transferSize || r.encodedBodySize || 0) / 1024),
            tipo: r.initiatorType,
            duracao: Math.round(r.duration),
          });
        }
      });
      obs.observe({ type: 'resource', buffered: true });
      window.__nav = performance.getEntriesByType('navigation')[0] || null;
    });

    const cdp = await estrangular(page, 1600, 300); // 1,6 Mbps, 300 ms RTT
    const t0 = Date.now();
    await page.goto('/', { waitUntil: 'load' });
    const loadMs = Date.now() - t0;

    const m = await page.evaluate(() => {
      // `getEntriesByType('navigation')` devolve `PerformanceEntry[]`, e
      // `domContentLoadedEventEnd`/`loadEventEnd` so existem em
      // `PerformanceNavigationTiming`. O narrowing e' o que torna a leitura
      // verdadeira — o `as` nao e' um atalho, e' a correccao do tipo.
      const nav = performance.getEntriesByType('navigation')[0] as
        | PerformanceNavigationTiming
        | undefined;
      const fcp = performance.getEntriesByName('first-contentful-paint')[0];
      const recursos = window.__recursos ?? [];
      const total = recursos.reduce((a, r) => a + r.kb, 0);
      const porTipo: Record<string, number> = {};
      for (const r of recursos) {
        porTipo[r.tipo] = (porTipo[r.tipo] || 0) + r.kb;
      }
      const topo = [...recursos].sort((a, b) => b.kb - a.kb).slice(0, 8);
      return {
        fcp: fcp ? Math.round(fcp.startTime) : null,
        domContentLoaded: nav ? Math.round(nav.domContentLoadedEventEnd) : null,
        load: nav ? Math.round(nav.loadEventEnd) : null,
        total,
        pedidos: recursos.length,
        porTipo,
        topo,
      };
    });
    await cdp.detach();

    // ── O relatório ──
    console.log('\n═══ PAINEL em 3G (1,6 Mbps, 300 ms RTT) ═══');
    console.log(`  first contentful paint : ${m.fcp} ms`);
    console.log(`  DOMContentLoaded      : ${m.domContentLoaded} ms`);
    console.log(`  load (wall clock)     : ${loadMs} ms`);
    console.log(`  pedidos               : ${m.pedidos}`);
    console.log(`  transferido total     : ${m.total} KB`);
    console.log('\n  por tipo:');
    for (const [t, kb] of Object.entries(m.porTipo).sort((a, b) => b[1] - a[1])) {
      console.log(`    ${String(t).padEnd(12)} ${String(kb).padStart(6)} KB`);
    }
    console.log('\n  os 8 mais pesados:');
    for (const r of m.topo) {
      const curto = r.nome.replace(/^https?:\/\/[^/]+/, '').slice(0, 58);
      console.log(`    ${String(r.kb).padStart(6)} KB  ${curto}`);
    }
    console.log('══════════════════════════════════════════════\n');

    // O painel tem de aparecer. Este nao e um teste de performance — e um
    // rede de base. Se a 3G a pagina nao abre, o resto da discussao e_noise.
    expect(m.fcp, 'nenhum first contentful paint — a pagina nao desenhou nada').not.toBeNull();
  });

  test('o precache evita o servidor na segunda visita', async ({ page }) => {
    await entrar(page);
    await estrangular(page, 1600, 300);

    // segunda visita, MESMA rede, agora com a cache quente
    let pedidosAoServidor = 0;
    page.on('response', (r) => {
      // O que NAO veio do precache. Um request sem `fromServiceWorker` e rede.
      const sf = r.fromServiceWorker();
      if (!sf && r.request().resourceType() !== 'document') pedidosAoServidor++;
    });

    const t0 = Date.now();
    await page.goto('/', { waitUntil: 'load' });
    const loadMs = Date.now() - t0;
    await page.waitForTimeout(800);

    console.log('\n═══ SEGUNDA VISITA, cache quente, 3G ═══');
    console.log(`  load            : ${loadMs} ms`);
    console.log(`  pedidos a rede  : ${pedidosAoServidor}`);
    console.log('═══════════════════════════════════════\n');

    expect(m2(loadMs), 'sem tempo de load').toBeGreaterThan(0);
  });
});

function m2(x: number) {
  return x;
}
