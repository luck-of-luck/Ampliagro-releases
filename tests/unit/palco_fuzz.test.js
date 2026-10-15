import { describe, it, expect, beforeAll } from 'vitest';
import fs from 'fs';
import path from 'path';

describe('AmpliaPalco parseIntencao Fuzzing (1000+ tests)', () => {
  beforeAll(() => {
    // Mock the window object since palco-amplia.js relies on it
    if (typeof window === 'undefined') {
      global.window = {
        fetch: () => Promise.resolve(),
      };
      global.document = {
        cookie: '',
      };
    } else {
      window.fetch = () => Promise.resolve();
    }

    // Load palco-amplia.js (it is an IIFE that attaches to window)
    const codePath = path.resolve(__dirname, '../../app/static/js/ia-local/palco-amplia.js');
    const code = fs.readFileSync(codePath, 'utf-8');

    // Evaluate the code in the current context so window.AmpliaPalco is defined
    eval(code);
  });

  it('deve processar 1000 entradas aleatórias sem quebrar (fuzzing)', () => {
    const parseIntencao = window.AmpliaPalco.parseIntencao;
    expect(parseIntencao).toBeDefined();

    const generateRandomString = (length) => {
      let result = '';
      const characters =
        'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 {}[]|"\'\n\r\t!@#$%^&*()_+-=`~';
      const charactersLength = characters.length;
      for (let i = 0; i < length; i++) {
        result += characters.charAt(Math.floor(Math.random() * charactersLength));
      }
      return result;
    };

    let passed = 0;
    const TOTAL_TESTS = 1000;

    for (let i = 0; i < TOTAL_TESTS; i++) {
      // Create different categories of inputs
      const randType = Math.floor(Math.random() * 5);
      let input = '';

      if (randType === 0) {
        // Pure random garbage
        input = generateRandomString(Math.floor(Math.random() * 2000));
      } else if (randType === 1) {
        // Markdown block with garbage
        input = '```amplia\n' + generateRandomString(500) + '\n```';
      } else if (randType === 2) {
        // Valid-looking text but malformed config JSON
        input = 'kpi-custo | Custo | { malformed: json ] \n chart-clima | Clima | { "a": 1 }';
      } else if (randType === 3) {
        // Markdown JSON
        input = '```amplia\n{ "widgets": [' + generateRandomString(100) + '] }\n```';
      } else {
        // Empty or whitespace
        input = '   \n  \t  ';
      }

      // We assert that NO error is thrown for ANY input
      let result;
      try {
        result = parseIntencao(input);

        // Assert that the result is always an array, as per the contract
        expect(Array.isArray(result)).toBe(true);
        passed++;
      } catch (err) {
        throw new Error(
          `Fuzzing falhou na iteração ${i} com erro: ${err.message}. Input: ${input}`
        );
      }
    }

    expect(passed).toBe(TOTAL_TESTS);
  });
});
