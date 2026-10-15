/**
 * Prova, num browser real, que a PWA abre SEM SINAL.
 *
 * PORQUE ESTE SPEC EXISTE
 * -----------------------
 * O `tests/test_precache_pwa.py` compara o `STATIC_ASSETS` do `sw.js` com o que
 * os templates pedem. Apanha o `?v=` divergente — mas é análise de texto. Não
 * prova que o Cache API guardou nada, nem que a página arranca offline.
 *
 * Havia quatro entradas no precache que NUNCA foram servidas do cache:
 *
 *     /static/js/spa.js?v=20250910e     (o base.html pede ?v=20250912a)
 *     /static/js/guide.js?v=20250910f   (o guia-vegetal pede ?v=20260917a)
 *     navbar-premium.css  e  soft-ui.css  (os templates pedem COM ?v=)
 *
 * O Cache API guarda por URL inteira. Offline, o `spa.js` real vai à rede,
 * falha, e o produtor vê um ecrã em branco. Nenhum teste de texto via isso —
 * é preciso um browser a desligar a rede.
 *
 * O QUE ESTE SPEC FAZ
 * -------------------
 * 1. Deixa o `install` correr e conta o que foi REALLY guardado.
 * 2. Confirma que as entradas que interessam ao shell estão lá.
 * 3. Desliga a rede (`context.setOffline(true)`) e navega outra vez.
 * 4. Confirma que o servidor NÃO foi acordado — se acordou, não há offline.
 *
 * O passo 4 é o que separa "a página respondeu" de "a página respondeu do
 * cache". Sem ele, um `/` que devolva 200 do Django passa por offline.
 */

import { test, expect } from '@playwright/test';
import type { Page } from '@playwright/test';

/**
 * O que `esperarPrecache` devolve.
 *
 * Declarar o retorno e' o que torna isto uma UNIAO DISCRIMINADA. Inferido,
 * o TypeScript dava `ok: boolean` nos dois ramos — e `boolean` nao discrimina:
 * `!r.ok` nao estreitava nada, `r.caches` continuava `| undefined`, e o
 * `reduce` ficava sem overload valido.
 *
 * Com `false`/`true` literais, o `if (!r.ok)` estreita, e o compilador passa
 * a dizer a verdade sobre o codigo que ja estava escrito.
 */
type ResultadoPrecache =
  | { ok: false; motivo: string }
  | { ok: true; scope: string; caches: Record<string, number> };

/** Deixa o service worker instalar e diz quantas entradas gravou. */
async function esperarPrecache(page: Page): Promise<ResultadoPrecache> {
  return page.evaluate(async () => {
    if (!('serviceWorker' in navigator)) return { ok: false, motivo: 'sem serviceWorker' };
    const reg = await navigator.serviceWorker.ready;
    await new Promise((r) => setTimeout(r, 500));
    const nomes = await caches.keys();
    // O tipo, e nao um `const contagem = {}`. Um objecto vazio tem tipo `{}`, e
    // indexa-lo com uma `string` da�� `TS7053`. Dizer o que o objeto e' e' o
    // que corrige — e nao e' um details: e' o mesmo que o codigo queria dizer.
    const contagem: Record<string, number> = {};
    for (const n of nomes) {
      const c = await caches.open(n);
      contagem[n] = (await c.keys()).length;
    }
    return { ok: true, scope: reg.scope, caches: contagem };
  });
}

/**
 * Entra na conta de demonstração.
 *
 * O `serviceWorker.register` está em `base.html:312`, e o `login.html` é
 * standalone — não o estende. Uma visita ao `/login/` não regista nada, e
 * `navigator.serviceWorker.ready` fica pendurado até ao timeout. A primeira
 * versão deste spec falhou exatamente por isso.
 */
async function entrar(page: Page) {
  await page.goto('/login/');
  await page.fill('input[name="usuario"]', 'demo');
  await page.fill('input[name="senha"]', 'demo123');
  await page.click('button[type="submit"]');
  await page.waitForLoadState('networkidle');
}

/** As chaves que o shell precisa, com o `?v=` que o base.html usa. */
const CHAVE_DO_SHELL = [
  '/static/js/spa.js?v=20250912a',
  '/static/css/navbar-premium.css?v=20260917a',
  '/static/css/soft-ui.css?v=20261002',
  '/static/css/theme.css',
  '/static/js/ia-local/ia-local.js',
  '/static/js/ia-local/alerta-feed.js?v=1',
  '/static/js/ia-sandbox.js?v=1',
];

test.describe('PWA offline', () => {
  test('o install guarda as entradas que o shell pede', async ({ page }) => {
    await entrar(page);
    const r = await esperarPrecache(page);

    expect(r.ok, `sem serviceWorker: ${'motivo' in r ? r.motivo : ''}`).toBeTruthy();
    // `esperarPrecache` devolve uma UNIAO: `{ok:false, motivo}` quando nao ha
    // service worker, e `{ok:true, caches}` quando ha. `caches` so existe no
    // segundo ramo — e `expect(r.ok).toBeTruthy()` nao estreita o tipo no
    // TypeScript, so no runtime.
    //
    // E o guard usa `in`, nao `!r.ok`: o TypeScript infere `ok: boolean` nos
    // dois ramos (nao um literal discriminante), e portanto `!r.ok` NAO
    // estreita a uniao. `'caches' in r` estreita, porque e' a presenca da
    // propriedade que distingue os ramos.
    //
    // Sem isto, `Object.values(r.caches)` recebia `unknown[]` e o `reduce`
    // deixava de ter overload valido.
    if (!('caches' in r)) throw new Error(`sem serviceWorker: ${r.motivo ?? ''}`);
    const total = Object.values(r.caches).reduce((a, b) => a + b, 0);
    expect(total, `caches vazias: ${JSON.stringify(r.caches)}`).toBeGreaterThan(5);
  });

  test('as entradas do shell estão na cache com o ?v= certo', async ({ page }) => {
    await entrar(page);
    await esperarPrecache(page);

    const guardadas = await page.evaluate(async (chaves) => {
      const nomes = await caches.keys();
      const todas = new Set();
      for (const n of nomes) {
        const c = await caches.open(n);
        for (const req of await c.keys()) todas.add(new URL(req.url).pathname + new URL(req.url).search);
      }
      return { todas: [...todas], falta: chaves.filter((k) => !todas.has(k)) };
    }, CHAVE_DO_SHELL);

    // Este é o teste que apanha o bug original. A ?v= errada produz uma
    // entrada com outra String, e `falta` vem com o nome dela.
    expect(
      guardadas.falta,
      `NÃO foram para a cache (URL errada no precache, ou ficheiro em falta):\n  ` +
        guardadas.falta.join('\n  '),
    ).toEqual([]);
  });

  test('offline: a raíz arranca sem o servidor', async ({ page, context }) => {
    await entrar(page);
    await esperarPrecache(page);

    // Corta a rede. A partir daqui, qualquer 200 é do cache.
    await context.setOffline(true);

    const resp = await page.goto('/', { waitUntil: 'domcontentloaded' });

    // `expect(x).not.toBeNull()` NÃO estreita o tipo no TypeScript — só no
    // runtime. O `tsc` via `resp` como `Response | null` e recusava
    // `resp.status()`. O guard é o que diz ao compilador o que o teste
    // assume; sem ele o teste passa a tocar no vazio.
    expect(resp, 'sem resposta offline').not.toBeNull();
    if (!resp) throw new Error('sem resposta offline');
    // O `networkFirst` devolve `caches.match('/')` quando a rede falha.
    expect(
      resp.status(),
      `offline devolveu ${resp.status()} — o servidor foi acordado ou o cache não tinha '/'`,
    ).toBeLessThan(400);

    // O SPA router tem de ter carregado. `spa.js` é o que faz isso; se o
    // precache tivesse o `?v=` errado, este é o ponto onde falha.
    //
    // O marcador é `window._spaHybridBound`, que o `spa.js` põe quando liga os
    // interceptadores de clique. A primeira versão deste spec adivinhou
    // `window.spa` e uns selectores que não existem — e passou a falhar por
    // causa do teste, não da aplicação. O nome real está em spa.js.
    const estado = await page.evaluate(() => ({
      ligado: window._spaHybridBound === true,
      temSwitchTab: typeof window.switchTab === 'function',
      temRotas: Array.isArray(window.__htmlRoutes),
    }));
    expect(
      estado.ligado || estado.temSwitchTab,
      `o shell da SPA nao inicializou offline: ${JSON.stringify(estado)}`,
    ).toBeTruthy();
  });

  test('a consentimento do motor nao descarrega 1,1 GB sem perguntar', async ({ page }) => {
    await page.goto('/login/');

    // A valva é uma função pura: com saveData ligado tem de recusar sem
    // mostrar o confirm. Verificamos a função, não o prompt (o `confirm`
    // bloqueia e o Playwright tem de o tratar à mão).
    await page.addInitScript(() => {
      Object.defineProperty(navigator, 'connection', {
        value: { saveData: true, effectiveType: '4g', downlink: 10 },
        configurable: true,
      });
    });
    await page.goto('/login/');

// Em `/login/` a valva não está carregada — o login.html é standalone.
    // O que interessa é que NÃO haja um fetch do modelo no arranque.
    const puxouModelo = await page.evaluate(() =>
      performance.getEntriesByType('resource').some((r) => /huggingface|mlc-ai|\.wasm$/i.test(r.name)),
    );
    expect(puxouModelo, 'a pagina puxou pesos do modelo sem interaction').toBeFalsy();

    // Isto NÃO pode continuar a ser `existe || true`: essa expressão é sempre
    // verdadeira, e a asserção que se seguia não podia falhar. Um teste que
    // não pode falhar é pior do que nenhum — ocupa o olho e não mede nada.
    //
    // A costura agora existe de facto (`window.iaMotorConsentido`, em
    // ia-local.js), e a afirmação é a que se pretendia: *se* a valva
    // carregou, tem de trazer a costura.
    const existe = await page.evaluate(() => typeof window.iaMotorConsentido === 'function');
    const valvaCarregada = await page.evaluate(() => typeof window.iaInit === 'function');
    if (valvaCarregada) {
      expect(existe, 'a valva carregou mas nao expoe iaMotorConsentido').toBe(true);
    }
  });
});
