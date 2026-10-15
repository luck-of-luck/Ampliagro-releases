import { defineConfig, devices } from '@playwright/test';

// Apontar a suite para um servidor que ja esta de pe (por exemplo o celular
// testando na LAN, ou um ambiente de homologacao):
//   BASE_URL=http://192.168.10.6:8020 npx playwright test --project=a11y
// Com BASE_URL setado, o webServer nao sobe nada -- quem manda no processo
// da aplicacao e quem a subiu. Sem isso, o Playwright tentaria ocupar a
// porta 8000, que aqui ja e usada por outro checkout.
const SERVIDOR_EXTERNO = !!process.env.BASE_URL;

export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: 'html',
  use: {
    baseURL: process.env.BASE_URL || 'http://localhost:8000',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'firefox',
      use: { ...devices['Desktop Firefox'] },
    },
    {
      name: 'webkit',
      use: { ...devices['Desktop Safari'] },
    },
    {
      name: 'a11y',
      use: { ...devices['Desktop Chrome'] },
      testMatch: '**/*.a11y.spec.ts',
      // SERIAL, e obrigatorio: quase todo teste deste projeto faz login, e o
      // runserver de dev e single-threaded (--noreload) com CACHES em
      // DatabaseCache sobre SQLite. Rodando em paralelo, os logins disputam a
      // base e estoura "database is locked" / timeout de navegacao — foi o que
      // aconteceu: 9 falhas que SUMIRAM todas com workers=1.
      workers: 1,
    },
  ],
  webServer: SERVIDOR_EXTERNO
    ? undefined
    : [
        {
          command: 'npm run dev',
          url: 'http://localhost:5173',
          reuseExistingServer: !process.env.CI,
          timeout: 120000,
        },
        {
          command: 'python manage.py runserver 8000 --settings=config.settings.dev',
          url: 'http://localhost:8000',
          reuseExistingServer: !process.env.CI,
          timeout: 120000,
          env: {
            PLAYWRIGHT_TEST: '1',
            DJANGO_SETTINGS_MODULE: 'config.settings.dev',
          },
        },
      ],
});
