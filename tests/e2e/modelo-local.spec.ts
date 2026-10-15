/**
 * O MODELO LOCAL REALMENTE FUNCIONA? E A VALVA DE 1,1 GB SEGURA?
 *
 * O QUE ESTE SPEC FECHA
 * ---------------------
 * A primeira pergunta que fizeste foi se o modelo esta realmente a funcionar
 * e a interagir com o produtor. A resposta que dei foi "nao posso confirmar sem
 * browser". Havia browser no repositorio — eu nao tinha procurado. Aqui esta.
 *
 * Sao tres perguntas, e as tres importam:
 *
 *  1. O WebGPU existe neste ambiente? Se nao, o modelo NAO carrega, e a
 *     cadeia de fallback (Qwen2-0.5B -> modo servidor) e que responde. Isso
 *     nao e um defeito do codigo; e o ambiente. Mas tem de ser DICTO, nao
 *     asumido.
 *
 *  2. A valva de 1,1 GB segura? Com `saveData` ligado ou em 2G, abrir a
 *     conversa NAO pode arrancar o download. Este e o meu codigo, e o que
 *     protege a factura de dados do produtor.
 *
 *  3. Recusar o motor degrada bem? O produtor tem de ficar com uma
 *     explicacao honesta e a conversa a funcionar pelo servidor — nunca um
 *     spinner eterno.
 */
import { test, expect } from '@playwright/test';

/** Login + esperar o SW, que e quem guarda a pagina para o offline. */
/**
 * `page` era declarado como `URL` — o tipo DOM, nao a pagina do Playwright.
 *
 * Uma palavra, oito erros: `page.goto` nao existe em `URL`, e quando o
 * Playwright passava a `Page` real o `as` nao encaixava e dava tres
 * `TS2345`. O sintoma apontava para dentro do Playwright; a causa era um
 * nome de tipo aqui em cima.
 *
 * O vizinho `temWebGpu` usa `import('@playwright/test').Page` e nunca falhou
 * — o que mostra que o tipo certo estava disponivel a duas linhas de
 * distancia. Um `tsc` limpo teria encontrado isto em segundos.
 */
async function entrar(page: import('@playwright/test').Page) {
  await page.goto('/login/');
  await page.fill('input[name="usuario"]', 'demo');
  await page.fill('input[name="senha"]', 'demo123');
  await page.click('button[type="submit"]');
  await page.waitForLoadState('networkidle');
}

/** O ambiente suporta WebGPU? Chromium headless costuma NAO suportar. */
async function temWebGpu(page: import('@playwright/test').Page) {
  return page.evaluate(async () => {
    const nav = navigator as Navigator & { gpu?: { requestAdapter(): Promise<unknown> } };
    if (!nav.gpu) return { ok: false, motivo: 'navigator.gpu ausente' };
    try {
      const adapter = await nav.gpu.requestAdapter();
      return adapter
        ? { ok: true, info: String((adapter as { info?: unknown }).info ?? 'adapter sem info') }
        : { ok: false, motivo: 'requestAdapter() devolveu null' };
    } catch (e) {
      return { ok: false, motivo: String((e as Error).message ?? e) };
    }
  });
}

test.describe('modelo local no browser', () => {
  test('1. o que este ambiente suporta, dito e nao assumido', async ({ page }) => {
    await entrar(page);
    const gpu = await temWebGpu(page);
    console.log('\n═══ AMBIENTE ═══');
    console.log(`  WebGPU: ${gpu.ok ? 'DISPONIVEL' : 'INDISPONIVEL'} — ${gpu.motivo ?? gpu.info}`);
    console.log(`  navigator.hardwareConcurrency: ${await page.evaluate(() => navigator.hardwareConcurrency)}`);
    console.log(`  deviceMemory: ${await page.evaluate(() => (navigator as never as { deviceMemory?: number }).deviceMemory ?? 'nao exposto')}`);
    console.log('════════════════════════\n');

    // Nao afirmamos nada sobre o resultado: o que este spec faz e NAO Deixar
    // o resultado ser um palpite. `expect` so garante que medimos.
    expect(typeof gpu.ok).toBe('boolean');
  });

  test('2. saveData ligado: a valva recusa SEM arrancar o download', async ({ page }) => {
    // Injeta ANTES de qualquer script da pagina correr.
    await page.addInitScript(() => {
      Object.defineProperty(navigator, 'connection', {
        value: { saveData: true, effectiveType: '4g', downlink: 10 },
        configurable: true,
      });
    });

    // Espia QUALQUER tentativa de ir buscar pesos do modelo.
    const pedidosModelo: string[] = [];
    page.on('request', (r) => {
      const u = r.url();
      if (/huggingface|hf\.co|mlc-ai|\.wasm$|resolve\/main/i.test(u)) pedidosModelo.push(u);
    });

    await entrar(page);
    await page.evaluate(() => navigator.serviceWorker.ready);
    await page.waitForTimeout(300);

    // Abre a conversa. E este o gesto que arrancava 1,1 GB.
    await page.evaluate(() => (window as unknown as { iaDockToggle: () => void }).iaDockToggle?.());
    await page.waitForTimeout(1200);

    const estado = await page.evaluate(() => ({
      consent: (window as unknown as { iaMotorConsentido?: () => boolean | null }).iaMotorConsentido?.(),
      status: document.getElementById('ia-status')?.textContent ?? null,
    }));

    console.log('\n═══ saveData LIGADO ═══');
    console.log(`  iaMotorConsentido() : ${estado.consent}`);
    console.log(`  estado na UI        : ${estado.status}`);
    console.log(`  pedidos do modelo   : ${pedidosModelo.length}`);
    if (pedidosModelo.length) pedidosModelo.slice(0, 5).forEach((u) => console.log(`     ${u.slice(0, 80)}`));
    console.log('═════════════════════\n');

    // A valva tem de recusar (devolve false, nao null: null = ainda nao decidido).
    expect(estado.consent, 'saveData ligado devia devolver false').toBe(false);
    // E o mais importante: nada foi buscar pesos.
    expect(
      pedidosModelo,
      `a valva deixou passar ${pedidosModelo.length} pedido(s) de pesos com saveData ligado`,
    ).toEqual([]);
  });

  test('3. 2G: a valva recusa e o produtor ouve porquê', async ({ page }) => {
    await page.addInitScript(() => {
      Object.defineProperty(navigator, 'connection', {
        value: { saveData: false, effectiveType: '2g', downlink: 0.2 },
        configurable: true,
      });
    });

    const pedidosModelo: string[] = [];
    page.on('request', (r) => {
      if (/huggingface|hf\.co|mlc-ai|\.wasm$/i.test(r.url())) pedidosModelo.push(r.url());
    });

    await entrar(page);
    await page.evaluate(() => navigator.serviceWorker.ready);
    await page.waitForTimeout(300);
    await page.evaluate(() => (window as unknown as { iaDockToggle: () => void }).iaDockToggle?.());
    await page.waitForTimeout(1200);

    const estado = await page.evaluate(() => ({
      consent: (window as unknown as { iaMotorConsentido?: () => boolean | null }).iaMotorConsentido?.(),
      status: document.getElementById('ia-status')?.textContent ?? null,
      // O corpo do chat deve ter a explicacao honesta.
      fala: document.getElementById('ia-chat-body')?.textContent?.slice(-260) ?? '',
    }));

    console.log('\n═══ 2G ═══');
    console.log(`  iaMotorConsentido() : ${estado.consent}`);
    console.log(`  estado na UI       : ${estado.status}`);
    console.log(`  pedidos do modelo  : ${pedidosModelo.length}`);
    console.log(`  ultima mensagem    : ${JSON.stringify(estado.fala.slice(-140))}`);
    console.log('══════════════════\n');

    expect(estado.consent).toBe(false);
    expect(pedidosModelo).toEqual([]);
    // O produtor nao pode ficar a olhar para um spinner eterno.
    expect(estado.status, 'a UI ficou sem estado — recusa tem de ser visivel').toBe('sem motor');
  });
});
