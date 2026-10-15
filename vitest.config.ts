import { defineConfig } from 'vitest/config';
import tsconfigPaths from 'vite-tsconfig-paths';
import path from 'path';

export default defineConfig({
  // O plugin React foi removido na V0 (saida do React). Os testes que
  // ficam sao `.js` sobre `window`/`document` — os widgets vanilla — e nao
  // precisam de transpilar JSX nem do automatic runtime.
  plugins: [tsconfigPaths()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['tests/setup.ts'],
    // `.test.{js,ts,tsx}` e não só `.tsx`.
    //
    // O include era `tests/unit/**/*.test.tsx` e não existe um único ficheiro
    // .tsx em tests/unit — os testes são todos .js. Resultado: `npm test`
    // respondia "No test files found" e saía com código 1, ou seja, a suite
    // JavaScript do projeto não corria há já muito tempo, sem sinal nenhum.
    //
    // Um include que não casa com nenhum ficheiro é um teste que não existe
    // com a forma de teste. Este include é o contrato: se aparecer um ficheiro
    // novo em tests/unit, ele passa a correr.
    include: ['tests/unit/**/*.test.{js,ts,tsx}'],
    exclude: ['tests/e2e/**', 'node_modules/**'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
      exclude: [
        'node_modules/',
        'tests/',
        '**/*.d.ts',
        '**/*.config.*',
        // `src/main.tsx` e `src/vite-env.d.ts` sairam da cobertura com a
        // arvore React. `src/styles/globals.css` continua em `src/` (e' a
        // entrada do `npm run build:css`) mas nao e' JavaScript e nao entra
        // no report.
      ],
    },
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
  },
});
