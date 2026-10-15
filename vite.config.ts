import { defineConfig } from 'vite';
import path from 'path';
import tsconfigPaths from 'vite-tsconfig-paths';
import { VitePWA } from 'vite-plugin-pwa';

export default defineConfig({
  root: '.',
  base: '/static/dist/',
  publicDir: 'public',
  build: {
    outDir: 'staticfiles/dist',
    emptyOutDir: true,
    manifest: true,
// sourcemap: 'hidden', e nao `false`. MEDIDO 2026-10-04 (agente 4).
      //
      // O problema que motivou a mudanca era real e continua real: um `.map`
      // contem o FONTE INTEIRO, com nomes de funcao e de variavel, e o
      // WhiteNoise serve `staticfiles/` tal como e. Esconder o bundle nao
      // esconde nada se o `.map` esta ao lado. MEDIDO: 144.683 bytes em
      // `staticfiles/dist/js/legacy.C6Z7LlIz.js.map`.
      //
      // Mas `false` e o remedio errado, por duas razoes:
      //
      // 1. **Nao teve efeito.** Com `false` o bundle ainda traz
      //    `//# sourceMappingURL=legacy.C6Z7LlIz.js.map` (linha 4 do
      //    ficheiro JA construido) enquanto o `.map` nao e recriado. So um
      //    `npx vite build` + `collectstatic` limpa. Ate' la, a fuga
      //    continua exactamente igual.
      // 2. **Estragou o Sentry.** `config/settings/base.py:703` liga o
      //    Sentry quando ha `SENTRY_DSN`, e `browser.sentry-cdn.com` esta na
      //    CSP. Sem source maps, um stack trace de producao chega ao painel
      //    como `legacy.C6Z7LlIz.js:1:482913` — inutilizavel. Trocar
      //    "fuga de fonte" por "erros de producao indecifraveis" nao e uma
      //    troca, e um perda de diagnostico custa mais que um mapa extra.
      //
      // `'hidden'` e' o termo correcto: o Vite GERA o `.map` (para o Sentry
      // receber) e NAO acrescenta o `sourceMappingURL` ao bundle, portanto o
      // browser do visitante nao pede o ficheiro e o ficheiro nao e publicado.
      //
      // O que FALTA para fechar isto de verdade:
      //   1. `npx vite build` + `collectstatic` (o `.map` actual e' de um
      //      build antigo e sobe com a proxima imagem).
      //   2. Um passo de upload do `.map` para o Sentry
      //      (`sentry-cli sourcemaps upload`). Sem ele, o `'hidden'` e'
      //      correcto mas o Sentry continua sem receber os mapas — e entao
      //      o ganho do `'hidden'` ainda nao se paga. Deixado escrito em vez
      //      de feito, porque e um passo de CI que precisa de
      //      `SENTRY_AUTH_TOKEN` e ninguem o pediu.
      sourcemap: 'hidden',
      minify: 'esbuild',
    rollupOptions: {
      input: {
        // A entrada React (`src/main.tsx`) foi removida na V0.
        // A que fica e' o bundle vanilla, o mesmo que `base.html:111`
        // carrega dentro do `{% if VITE_ATIVO %}`.
        legacy: path.resolve(__dirname, 'app/static/js/main.js'),
      },
      output: {
        entryFileNames: 'js/[name].[hash].js',
        chunkFileNames: 'js/chunks/[name].[hash].js',
        assetFileNames: 'assets/[name].[hash].[ext]',
        // `manualChunks` foi removido com o React: os chunks `vendor`,
        // `query`, `charts`, `ui`, `dnd`, `table`, `forms` e `i18n`
        // eram divisions do grafo de imports do React. O bundle vanilla
        // e' um unico `legacy`.
      },
    },
  },
  server: {
    port: 5173,
    host: true,
    proxy: {
      '/api': 'http://localhost:8000',
      '/admin': 'http://localhost:8000',
      '/healthz': 'http://localhost:8000',
    },
    hmr: {
      protocol: 'ws',
      host: 'localhost',
    },
  },
  plugins: [
    tsconfigPaths(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['favicon.ico', 'robots.txt', 'apple-touch-icon.png'],
      manifest: {
        name: 'Ampliagro',
        short_name: 'Ampliagro',
        description: 'Sistema Operacional da Fazenda - Gestão agrícola completa',
        theme_color: '#006B6E',
        background_color: '#ffffff',
        display: 'standalone',
        orientation: 'portrait-primary',
        scope: '/',
        start_url: '/',
        icons: [
          {
            src: '/icons/icon-72x72.png',
            sizes: '72x72',
            type: 'image/png',
            purpose: 'maskable any',
          },
          {
            src: '/icons/icon-96x96.png',
            sizes: '96x96',
            type: 'image/png',
            purpose: 'maskable any',
          },
          {
            src: '/icons/icon-128x128.png',
            sizes: '128x128',
            type: 'image/png',
            purpose: 'maskable any',
          },
          {
            src: '/icons/icon-144x144.png',
            sizes: '144x144',
            type: 'image/png',
            purpose: 'maskable any',
          },
          {
            src: '/icons/icon-152x152.png',
            sizes: '152x152',
            type: 'image/png',
            purpose: 'maskable any',
          },
          {
            src: '/icons/icon-192x192.png',
            sizes: '192x192',
            type: 'image/png',
            purpose: 'maskable any',
          },
          {
            src: '/icons/icon-384x384.png',
            sizes: '384x384',
            type: 'image/png',
            purpose: 'maskable any',
          },
          {
            src: '/icons/icon-512x512.png',
            sizes: '512x512',
            type: 'image/png',
            purpose: 'maskable any',
          },
        ],
        categories: ['productivity', 'business', 'agriculture'],
        screenshots: [],
        shortcuts: [
          {
            name: 'Rastreabilidade',
            short_name: 'Rastros',
            description: 'Ver lotes e rastreabilidade',
            url: '/rastreabilidade/',
            icons: [{ src: '/icons/qr-icon.png', sizes: '192x192' }],
          },
          {
            name: 'Custos',
            short_name: 'Custos',
            description: 'Ver custos de produção',
            url: '/custos/producao/',
            icons: [{ src: '/icons/cost-icon.png', sizes: '192x192' }],
          },
        ],
      },
      workbox: {
        globPatterns: ['**/*.{js,css,html,ico,png,svg,woff2}'],
        runtimeCaching: [
          {
            urlPattern: ({ url }) => url.pathname.startsWith('/api/widget-data') || url.pathname.startsWith('/api/dashboard'),
            handler: 'StaleWhileRevalidate',
            options: {
              cacheName: 'dashboard-cache',
              expiration: { maxEntries: 20, maxAgeSeconds: 60 * 5 },
              cacheableResponse: { statuses: [0, 200] },
            },
          },
          {
            urlPattern: ({ url }) => url.pathname.startsWith('/api/'),
            handler: 'NetworkFirst',
            options: {
              cacheName: 'api-cache',
              expiration: { maxEntries: 100, maxAgeSeconds: 60 * 60 * 24 },
              networkTimeoutSeconds: 3,
              cacheableResponse: { statuses: [0, 200] },
            },
          },
          {
            urlPattern: ({ url }) => url.pathname.startsWith('/static/'),
            handler: 'CacheFirst',
            options: {
              cacheName: 'static-assets',
              expiration: { maxEntries: 50, maxAgeSeconds: 60 * 60 * 24 * 30 },
              cacheableResponse: { statuses: [0, 200] },
            },
          },
        ],
        navigateFallback: '/offline.html',
      },
      devOptions: {
        enabled: true,
        type: 'module',
      },
    }),
  ],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
  },
  // O bloco `test` NÃO vive aqui.
  //
  // A configuração de testes é a de `vitest.config.ts`, e este ficheiro é o
  // da build. Com um `test:` aqui dentro, o Vitest carrega `vite.config.ts` e
  // ignora o `vitest.config.ts` — que é a razão de `npm test` ter estado a
  // devolver "No test files found" e a sair com código 1: o include era só
  // `*.test.tsx` e não existe nenhum ficheiro .tsx em tests/unit, portanto
  // a suite JavaScript corria ZERO testes sem que ninguém desse por isso.
  //
  // Manter a config num sítio só é o que impede as duas de divergirem.
});
