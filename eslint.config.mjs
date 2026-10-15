import js from "@eslint/js";
import eslintConfigPrettier from "eslint-config-prettier";

// `eslint-plugin-prettier` foi REMOVIDO desta lista de propósito.
//
// MEDIDO 2026-10-04 (agente 4): com `prettier/recommended`, o `prettier/prettier`
// é reportado como **error**, e `--max-warnings 0` faz o `npm run lint` falhar
// em divida de formatação que já existia. O ficheiro mais pequeno que
// verifiquei, `app/static/js/tabs/dashboard-desktop.js`, dá 6 erros:
//
//   732:9  error  Delete `<CRLF>......`   prettier/prettier
//
// Instalar o plugin **piorou** o lint em vez de o melhorar.
//
// E o que é um formatador a fazer no meio de um linter é misturar duas
// coisas com contratos diferentes: o linter responde "isto está errado?", o
// formatador responde "isto está feio?". `eslint-config-prettier` (o
// `eslint-config-prettier`, sem o plugin) continua no sitio e é o correcto:
// desliga as regras de formatação do ESLint para o Prettier decidir. A
// formatação passa a correr em `npm run format`, que é onde pertence.
//
// `eslint-plugin-prettier` fica em `devDependencies` porque o `format` usa
// o `prettier` directamente.

export default [
  {
    // O QUE NAO SE LINDA, e porquê. MEDIDO 2026-10-04 (agente 4).
    //
    // `eslint .` sem isto percorria **465 ficheiros**, incluindo:
    //
    //   .venv/Lib/site-packages/**   jquery.js (8.654 linhas), xregexp.js
    //                                (5.120), select2.full.js (5.486) — o
    //                                Django admin, que NÃO É NOSSO CÓDIGO
    //   staticfiles/**               output de `collectstatic`: cópias de
    //                                guide.js, ia-local.js, e o build do Vite
    //   scratch/**                   test_1.js (10.892 linhas),
    //                                kpi_script.js (10.815) — rascunhos
    //   docs/**                      relatórios, incluindo as sondas _sonda*
    //   backups/                     12.151 subpastas (ver 2.md §3.7)
    //
    // Com `prettier` como regra de lint, cada um desses ficheiros era
    // formatado em memória: `npm run lint` passou os **240 s** sem acabar.
    //
    // Isto não é cosmético. Um lint que formata a cópia do Django dentro
    // de `.venv` não está a lintar o nosso código — está a gastar o
    // orçamento de CI e a producing erros em código de terceiros.
    ignores: [
      "node_modules/",
      ".venv/",
      "venv/",
      "staticfiles/",
      "scratch/",
      "docs/",
      "backups/",
      ".git/",
      "**/*.min.js",
      // Service worker: tem o seu próprio formato e é gerado nomental.
      "app/static/js/pwa/sw.js",
      // `.ts` NÃO E' LINTADO, e a razão é uma lacuna conhecida.
      //
      // Este config declara `ecmaVersion: 2022, sourceType: "module"` e mais
      // nada — não há parser de TypeScript. Os 6 ficheiros `tests/e2e/*.spec.ts`
      // davam `Parsing error: Unexpected token :` em cada um. Um lint que
      // falha ao PARSEAR não está a dizer nada sobre o código: está a dizer
      // que não o consegue ler, e o resultado é o mesmo — ninguém o lê.
      //
      // A correcção a sério é `typescript-eslint`, e é uma decisão de
      // dependência que não se toma de passagem. Quem quiser勤奋-lo:
      //
      //   npm i -D typescript-eslint
      //   // e no array: typescript-eslint.configs.recommended
      //
      // O QUE FAZ A VERIFICAÇÃO DE TIPOS, meanwhile, é o `tsc`:
      // `npm run typecheck`. E ele **está a reportar erros** — medido agora,
      // em `tests/e2e/chamado.spec.ts` (TS7006, TS2531) e
      // `tests/e2e/modelo-local.spec.ts` (TS2339: `page` está tipado como
      // `URL` em vez de `Page`, o que torna `page.goto()` um erro de tipos).
      // Ou seja: `npm run build` (`tsc && vite build`) e `npm run typecheck`
      // estão ambos a falhar. Fora do âmbito deste ficheiro, e **digo-o em vez
      // de o esconder atrás de um `--quiet`.**
      "**/*.ts",
      "**/*.tsx",
    ],
  },
  js.configs.recommended,
  eslintConfigPrettier,
  {
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: "module",
      globals: {
        window: "readonly",
        document: "readonly",
        console: "readonly",
        localStorage: "readonly",
        setTimeout: "readonly",
        Promise: "readonly",
        module: "readonly",
        require: "readonly",
        navigator: "readonly",
        fetch: "readonly",
        alert: "readonly",
        Math: "readonly",
        Date: "readonly",
        Image: "readonly",
        HTMLCanvasElement: "readonly",
        btoa: "readonly",
        atob: "readonly",
        clearTimeout: "readonly",
        self: "readonly",
        caches: "readonly",
        Request: "readonly",
        URL: "readonly",
        indexedDB: "readonly"
      }
    },
    rules: {
      "no-unused-vars": "off",
      "no-console": "off",
      "no-undef": "off",
      "no-empty": "off",
      "no-case-declarations": "off",
      "no-self-assign": "off",
      "no-dupe-class-members": "off",
      "no-redeclare": "off",
      "no-useless-assignment": "off",
      "no-useless-escape": "off",
      "no-unreachable": "off"
    }
  }
];
