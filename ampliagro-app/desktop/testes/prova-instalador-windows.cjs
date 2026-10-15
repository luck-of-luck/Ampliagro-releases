const { _electron: electron } = require('playwright');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const { spawnSync } = require('node:child_process');
(async () => {
  const root = path.resolve(__dirname, '../../..');
  const data = fs.mkdtempSync(path.join(os.tmpdir(), 'ampliagro-packaged-'));
  const application = await electron.launch({
    executablePath: path.join(root, 'ampliagro-app/desktop/dist/win-unpacked/Ampliagro.exe'),
    env: { ...process.env, AMPLIAGRO_DESKTOP_DATA_DIR: data },
    timeout: 60000,
  });
  const proc = application.process();
  const pid = proc.pid;
  console.log('PID', pid, 'DATA', data);
  const output = fs.createWriteStream(path.join(data, 'electron.log'));
  application.process().stdout.pipe(output);
  application.process().stderr.pipe(output);
  try {
    const page = await application.firstWindow();
    await page.locator('#terms').waitFor({ state: 'visible', timeout: 240000 });
    console.log('PACKAGED TERMS OK');
    await page.locator('#accepted').check();
    await page.locator('#next').click();
    await page.locator('#next').click();
    await page
      .locator('#cultures details')
      .first()
      .evaluate((e) => (e.open = true));
    await page.locator('#cultures input').first().check();
    await page.locator('#next').click();
    await page.locator('#step-3').waitFor({ state: 'visible', timeout: 30000 });
    console.log('SELECTION SAVED', fs.existsSync(path.join(data, 'installation.json')));
    const next = application.waitForEvent('window', { timeout: 60000 });
    await page.locator('#next').click();
    const main = await next;
    await main.waitForLoadState('domcontentloaded', { timeout: 60000 });
    console.log('MAIN URL', main.url());
    console.log('MAIN TEXT', (await main.locator('body').innerText()).slice(0, 400));
    await main.screenshot({ path: path.join(data, 'main.png') });
  } finally {
    await Promise.race([application.close(), new Promise((r) => setTimeout(r, 5000))]);
    if (proc.exitCode === null)
      spawnSync('taskkill', ['/PID', String(pid), '/T', '/F'], { windowsHide: true });
    output.end();
  }
})().catch((e) => {
  console.error(e);
  process.exitCode = 1;
});
