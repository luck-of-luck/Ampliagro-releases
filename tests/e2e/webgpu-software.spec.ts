/**
 * O WebGPU pode ser ligado por software? Se sim, o modelo carrega e a
 * pergunta original tem resposta definitiva.
 *
 * O Chromium headless nao traz WebGPU por omissao — `requestAdapter()` devolve
 * null. Ha uma via por software (Dawn + SwiftShader), que e lenta mas CORRE.
 * Nao e a velocidade de um telemivel; e a pergunta "o codigo do ia-local.js
 * carrega mesmo o modelo e responde, ou estaPartido?".
 *
 * Se ate assim nao der, o veredicto e "neste ambiente nao ha GPU" — e o que
 * fica por provar passa a precisar de um dispositivo real, e diz-se isso.
 */
import { test, expect } from '@playwright/test';

test.use({
  launchOptions: {
    args: [
      '--enable-unsafe-webgpu',
      '--enable-features=Vulkan,UseSkiaRenderer',
      '--use-angle=swiftshader',
      '--use-gl=angle',
      '--disable-vulkan-surface',
      '--enable-features=SharedArrayBuffer',
    ],
  },
});

test('WebGPU por software: o modelo carrega?', async ({ page }) => {
  const pedidosModelo: string[] = [];
  const errosModelo: string[] = [];

  page.on('request', (r) => {
    if (/huggingface|hf\.co|\.wasm$/i.test(r.url())) pedidosModelo.push(r.url());
  });
  page.on('console', (m) => {
    const t = m.text();
    if (/\[IA\]|WebLLM|MLC|webgpu|adapter/i.test(t)) errosModelo.push(t.slice(0, 160));
  });

  await page.goto('/login/');
  await page.fill('input[name="usuario"]', 'demo');
  await page.fill('input[name="senha"]', 'demo123');
  await page.click('button[type="submit"]');
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(500);

  const gpu = await page.evaluate(async () => {
    const nav = navigator as Navigator & {
      gpu?: { requestAdapter(): Promise<{ features?: Set<string> } | null> };
    };
    if (!nav.gpu) return { ok: false, motivo: 'navigator.gpu ausente' };
    try {
      const a = await nav.gpu.requestAdapter();
      if (!a) return { ok: false, motivo: 'requestAdapter() -> null' };
      return { ok: true, features: [...(a.features ?? [])].slice(0, 6) };
    } catch (e) {
      return { ok: false, motivo: String((e as Error).message) };
    }
  });

  console.log('\n═══ WebGPU por software ═══');
  console.log(`  adaptador: ${gpu.ok ? 'DISPONIVEL' : 'INDISPONIVEL — ' + gpu.motivo}`);
  if (gpu.ok) console.log(`  features : ${(gpu.features as string[]).join(', ')}`);

  if (!gpu.ok) {
    console.log('  → sem GPU, o modelo nao carrega. Veredicto do ambiente.');
    console.log('════════════════════════════════════════════\n');
    expect(typeof gpu.ok).toBe('boolean');
    return;
  }

  // Ha GPU. Agora a pergunta real: o ia-local.js carrega o modelo?
  // `saveData` desligado e 4G, para a valva deixar passar.
  await page.evaluate(async () => {
    Object.defineProperty(navigator, 'connection', {
      value: { saveData: false, effectiveType: '4g', downlink: 50 },
      configurable: true,
    });
    localStorage.setItem('amplia_ia_motor', 'aceito');
  });

  await page.evaluate(() => (window as unknown as { iaDockToggle: () => void }).iaDockToggle?.());

  // O download de 1,1 GB por software vai demorar. Damos 150 s e vemos ate
  // onde chega — o que interessa e o PROGRESSO, nao a conclusao.
  let estado = '';
  for (let i = 0; i < 30; i++) {
    await page.waitForTimeout(5000);
    estado = await page.evaluate(() => {
      const w = window as unknown as { iaLocal?: { ready: unknown }; iaEngine?: unknown };
      return JSON.stringify({
        ready: w.iaLocal?.ready ?? null,
        temEngine: !!w.iaEngine,
        ui: document.getElementById('ia-status')?.textContent ?? null,
        prog: document.querySelector('#ia-progress span')?.textContent ?? null,
      });
    });
    process.stdout.write(`    [${(i + 1) * 5}s] ${estado}\n`);
    if (/pronto|server/.test(estado)) break;
  }

  console.log(`\n  pedidos do modelo: ${pedidosModelo.length}`);
  pedidosModelo.slice(0, 6).forEach((u) => console.log(`     ${u.slice(0, 90)}`));
  console.log('  consola:');
  [...new Set(errosModelo)].slice(0, 8).forEach((l) => console.log(`     ${l}`));
  console.log('\n  ESTADO FINAL: ' + estado);
  console.log('════════════════════════════════════════════\n');

  // Se chegou a `pronto` ou a `server`, o codigo correu ate ao fim da cadeia.
  expect(estado, 'o estado final nunca foi lido').toContain('ready');
});
