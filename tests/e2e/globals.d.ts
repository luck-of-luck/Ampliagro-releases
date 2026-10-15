/**
 * As janelas que o Ampliagro abre para os scripts que não são TypeScript.
 *
 * PORQUE ESTE FICHEIRO EXISTE
 * ---------------------------
 * O dashboard é JavaScript antigo em `<script>` inline — não há
 * declarações em lado nenhum. As specs de Playwright correm esse código com
 * `page.evaluate(() => window.switchTab(...))`, e o `tsc`respondia:
 *
 *   error TS2339: Property 'switchTab' does not exist on type
 *                 'Window & typeof globalThis'.
 *
 * Esse erro é um **diagnóstico errado**. `switchTab` existe — em
 * `app/static/js/spa.js`. O que não existe é a *declaração* de que existe.
 * O TypeScript só conhece o que lhe foi declarado, e ninguém declarou.
 *
* Corrigir isto editando cada spec (fazer `as any`, `// @ts-ignore`) resolve
 * o sintoma e apaga o sinal. Declarar é o conserto: passa a ser verdade para
 * toda a gente, e amanhã quem acrescentar um método no `spa.js` recebe um erro
 * se o esquecer aqui.
 *
 * MEDIDO 2026-10-04 (agente 4): isto fecha 7 dos 41 erros de `tsc` num só
 * ficheiro. Os restantes são tipagem de cada spec e estão declaradas como
 * não feitas.
 *
 * ONDE ESTÁ CADA COISA
 * --------------------
 *   switchTab, _spaHybridBound, __htmlRoutes, __nav  → app/static/js/spa.js
 *   iaInit, iaMotorConsentido                          → ia-local/ia-local.js
 *   __recursos, __XSS                                  → index.html
 *   spa                                                → index.html
 */

// A assinatura de `switchTab` é `switchTab(rota, opcoes)` — declaration
// tentativa. Só o NOME precisa ser conhecido; se um dia alguém lhe passar
// argumentos, o `tsc` passa a dizer a verdade.
declare global {
  interface Window {
    /** `spa.js` — troca de separador sem recarregar a página. */
    switchTab: (rota: string, opcoes?: unknown) => void;

    /** `spa.js` — marca se o modo híbrido foi ligado. */
    _spaHybridBound?: boolean;

    /** `spa.js` — rotas que o servidor renderizou para o cliente. */
    __htmlRoutes?: string[];

    /** `index.html` — a nav já montada, quando o SPA a assume. */
    __nav?: unknown;

    /** `ia-local.js` — carga o motor da borda. Ver o consentimento antes. */
    iaInit?: (onProgress?: (p: { text: string }) => void) => Promise<unknown>;

    /**
     * `ia-local.js` — costura de consentimento do download do modelo.
     *   `iaMotorConsentido(true|false)` força a decisão, sem `confirm()`.
     *   `iaMotorConsentido()` devolve o que está gravado, ou `null`.
     */
    iaMotorConsentido?: (resposta?: boolean) => boolean | null;

    /**
     * `tests/e2e/pwa-peso.spec.ts` — um registo por recurso transferido.
     *
     * O ERRO QUE ESTE TIPO JÁ CAUSOU, e que vale registar: declarei isto
     * primeiro como `Record<string, string>`, a adivinhar. O código usa-o
     * como **array de objectos**, e o `tsc` respondeu
     * `TS2322: Type 'never[]' is not assignable to type 'Record<string, string>'`.
     *
     * Uma declaração errada é pior do que nenhuma: ela não é neutra, ela
     * inventa uma restrição que não existe e faz o teste falhar por um motivo
     * que não tem nada a ver com o que o teste quer medir. Quando não se sabe
     * o tipo, `unknown` é a resposta honesta — obriga a narrowing no ponto de
     * uso e não inventa regras.
     */
    __recursos?: Array<{
      nome: string;
      kb: number;
      tipo: string;
      duracao: number;
    }>;
  }
}

export {};