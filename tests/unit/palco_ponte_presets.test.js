// A ponte: a composicao da IA (lista) vira o objecto que o dashboard desenha.
//
// MEDIDO 2026-10-09: com `meus_presets` a ser lido, o preset guardado passa a
// existir em `PRESETS` — mas a forma errada produz um preset que o menu mostra
// e a grelha nao desenha. Estes testes medem a traducao, que e' a parte nova.

import { describe, it, expect, beforeEach } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const SRC = readFileSync(resolve(process.cwd(), 'app/static/js/ia-local/palco-amplia.js'), 'utf8');

/* Extrai as funcoes puras do IIFE para as poder testar sem DOM. A alternativa
   — carregar o ficheiro inteiro — puxaria `document` e `window` para dentro de
   um teste que nao precisa deles. */
function extrai(nome) {
  const i = SRC.indexOf(`function ${nome}(`);
  if (i < 0) throw new Error(`${nome}() nao existe em palco-amplia.js`);
  let profundidade = 0;
  let j = SRC.indexOf('{', i);
  for (let k = j; k < SRC.length; k++) {
    if (SRC[k] === '{') profundidade++;
    else if (SRC[k] === '}') {
      profundidade--;
      if (profundidade === 0) return SRC.slice(i, k + 1);
    }
  }
  throw new Error(`${nome}() nao fecha`);
}

const GRELHA_SRC = extrai('geometria');
const TRADUZIR_SRC = extrai('paraGrelha');
const REGISTAR_SRC = extrai('registarPresetsGuardados');
/* `_clona` e' chamada por `registarPresetsGuardados`, e a extraccao e' por
   funcao: sem ela aqui dentro, o `eval` corre sem ela e falha em runtime. */
const CLONA_SRC = extrai('_clona');

const GRELHA = { col: 21, altura: 8, folga: 2 };
const geometria = eval(`(${GRELHA_SRC.replace('function geometria', 'function')})`);
const paraGrelha = eval(`(${TRADUZIR_SRC.replace('function paraGrelha', 'function')})`);
const _clona = eval(`(${CLONA_SRC.replace('function _clona', 'function')})`);
const registarPresetsGuardados = eval(
  `(${REGISTAR_SRC.replace('function registarPresetsGuardados', 'function')})`
);

describe('a ponte entre a mesa da IA e o dashboard', () => {
  it('substitui a composição após edição confirmada e aceita excluir o último widget', () => {
    registarPresetsGuardados([{ slug: 'custom-teste', estrutura: { widgets: [{ tipo: 'kpi-caixa' }] } }]);
    registarPresetsGuardados([{ slug: 'custom-teste', estrutura: { widgets: [{ tipo: 'kpi-custo' }] } }], true);
    expect(Object.keys(window.PRESET_WIDGETS_JSON['custom-teste'])).toEqual(['kpi-custo']);
    registarPresetsGuardados([{ slug: 'custom-teste', estrutura: { widgets: [] } }], true);
    expect(window.PRESET_WIDGETS_JSON['custom-teste']).toEqual({});
  });
  beforeEach(() => {
    global.window = { PRESETS: {}, PRESET_WIDGETS_JSON: {} };
    global.localStorage = {
      setItem() {},
      getItem() {
        return null;
      },
    };
    global.renderWidgetbarPresets = () => {};
    window.renderWidgetbarPresets = () => {};
  });

  it('converte a LISTA da IA no OBJECTO que o dashboard itera', () => {
    const g = paraGrelha([
      { tipo: 'kpi-custo', titulo: 'Custo' },
      { tipo: 'kpi-caixa', titulo: 'Caixa' },
    ]);
    // A forma e' o ponto: o dashboard faz Object.keys() e percorre valores.
    expect(Array.isArray(g)).toBe(false);
    expect(Object.keys(g)).toEqual(['kpi-custo', 'kpi-caixa']);
  });

  it('da a cada widget geometria, senao o dashboard nao o posiciona', () => {
    const g = paraGrelha([{ tipo: 'kpi-custo' }, { tipo: 'kpi-roi' }]);
    expect(g['kpi-custo']).toMatchObject({
      gridX: expect.any(Number),
      gridY: expect.any(Number),
      gridW: expect.any(Number),
      gridH: expect.any(Number),
      visible: true,
    });
    // Duas posicoes diferentes: dois widgets no mesmo sitio e' um sobre o
    // outro, e o produtor vê um widget.
    expect(g['kpi-custo'].gridX).not.toBe(g['kpi-roi'].gridX);
  });

  it('a geometria nao se repete ao passar da 3a linha', () => {
    // 7 widgets = 3 na primeira linha, 3 na segunda, 1 na terceira. O 7º cai na
    // coluna 0 da linha 2 — e o 1º na coluna 0 da linha 0. E' esse par que
    // tem de diferir; comparar com o 4º (coluna 1) nao provaria nada.
    const g = paraGrelha(Array.from({ length: 7 }, (_, i) => ({ tipo: `kpi-x${i}` })));
    expect(g['kpi-x0'].gridX).toBe(0);
    expect(g['kpi-x6'].gridX).toBe(0);
    expect(g['kpi-x0'].gridY).not.toBe(g['kpi-x6'].gridY);

    // E nenhuma celula se repete: o par (x, y) tem de ser unico.
    const celulas = Object.values(g).map((w) => `${w.gridX},${w.gridY}`);
    expect(new Set(celulas).size).toBe(celulas.length);
  });

  it('descarta o que nao tem id, em vez de criar um widget sem nome', () => {
    const g = paraGrelha([{ titulo: 'sem tipo' }, null, { tipo: 'kpi-caixa' }]);
    expect(Object.keys(g)).toEqual(['kpi-caixa']);
  });

  it('aceita a lista vazia e o que nao e uma lista', () => {
    expect(paraGrelha([])).toEqual({});
    expect(paraGrelha(null)).toEqual({});
    expect(paraGrelha('isto nao e uma lista')).toEqual({});
  });

  it('regista o preset guardado com o nome que o produtor lhe deu', () => {
    const n = registarPresetsGuardados([
      {
        slug: 'custom-custo',
        nome: 'Custo por talhao',
        estrutura: { widgets: [{ tipo: 'kpi-custo' }] },
      },
    ]);
    expect(n).toBe(1);
    expect(window.PRESETS['custom-custo'].label).toBe('Custo por talhao');
    expect(Object.keys(window.PRESETS['custom-custo'].widgets)).toEqual(['kpi-custo']);
  });

  /* MEDIDO 2026-10-09 no browser: o preset aparecia no menu com os widgets
     certos e a grelha desenhavam OUTRO preset. `pagina-index.js:2434` constroi
     `PRESETS` a partir de `PRESET_WIDGETS_JSON`, e o `persistPresetWidgets`
     (:2848) escreve nessa fonte — um preset que so' vive em `PRESETS` e'
     apagado pelo proximo render. Este e' o teste que pegou isso. */
  it('escreve na FONTE, e nao so no menu', () => {
    registarPresetsGuardados([
      {
        slug: 'custom-custo',
        estrutura: { widgets: [{ tipo: 'kpi-custo' }, { tipo: 'kpi-roi' }] },
      },
    ]);
    expect(Object.keys(window.PRESET_WIDGETS_JSON['custom-custo'])).toEqual([
      'kpi-custo',
      'kpi-roi',
    ]);
  });

  it('a FONTE e o menu nao sao o mesmo objecto', () => {
    registarPresetsGuardados([
      { slug: 'custom-custo', estrutura: { widgets: [{ tipo: 'kpi-custo' }] } },
    ]);
    expect(window.PRESETS['custom-custo'].widgets).not.toBe(
      window.PRESET_WIDGETS_JSON['custom-custo']
    );
  });

  it('nao sobrescreve o que a FONTE ja tem (o produtor arranjou-o)', () => {
    // Estado real depois do dashboard re-semeiar: a FONTE tem o que o produtor
    // arranjou, e o menu tem a entrada (que o dashboard constroi da FONTE).
    window.PRESET_WIDGETS_JSON['custom-custo'] = { 'kpi-alertas': { gridX: 0 } };
    window.PRESETS['custom-custo'] = { label: 'O meu', widgets: {} };
    const n = registarPresetsGuardados([
      {
        slug: 'custom-custo',
        nome: 'Da IA',
        estrutura: { widgets: [{ tipo: 'kpi-custo' }] },
      },
    ]);
    // O que importa e' a FONTE: e' dela que a grelha e' construida. O menu pode
    // ficar com o label novo (e' cosmetico), mas os widgets tem de ser os do
    // produtor.
    expect(n).toBe(0);
    expect(Object.keys(window.PRESET_WIDGETS_JSON['custom-custo'])).toEqual(['kpi-alertas']);
  });

  it('o menu sozinho nao trava o registo: quem trava e a FONTE', () => {
    // Um preset que so' o menu conhece e' um preset que o proximo re-render
    // reconstroi a partir da FONTE — nao ha la nada a perder. O que protege o
    // que o produtor fez sao os widgets na FONTE, e isso e' o teste anterior.
    window.PRESETS['custom-custo'] = { label: 'O meu', widgets: {} };
    const n = registarPresetsGuardados([
      { slug: 'custom-custo', nome: 'Da IA', estrutura: { widgets: [{ tipo: 'kpi-custo' }] } },
    ]);
    expect(n).toBe(1);
    expect(Object.keys(window.PRESET_WIDGETS_JSON['custom-custo'])).toEqual(['kpi-custo']);
  });

  it('nao regista preset sem widgets: um preset vazio nao se desenha', () => {
    const n = registarPresetsGuardados([
      { slug: 'custom-vazio', nome: 'Vazio', estrutura: { widgets: [] } },
    ]);
    expect(n).toBe(0);
    expect(window.PRESETS['custom-vazio']).toBeUndefined();
  });

  it('nao rebenta sem PRESETS (o dashboard pode nao ter carregado)', () => {
    global.window = {};
    window.PRESETS = undefined;
    expect(
      registarPresetsGuardados([
        { slug: 'custom-x', estrutura: { widgets: [{ tipo: 'kpi-custo' }] } },
      ])
    ).toBe(0);
  });

  it('so desenha uma vez, e so quando houve preset novo', () => {
    let desenhados = 0;
    window.renderWidgetbarPresets = () => {
      desenhados++;
    };
    registarPresetsGuardados([
      { slug: 'custom-a', estrutura: { widgets: [{ tipo: 'kpi-custo' }] } },
    ]);
    expect(desenhados).toBe(1);
    registarPresetsGuardados([]);
    expect(desenhados).toBe(1);
  });
});
