import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

/**
 * Regressão: nenhum widget anunciado no modal pode ser um clique morto.
 *
 * O defeito
 * ----------
 * `WIDGET_CATALOG` (o modal "adicionar widget", em `index.html`) oferecia 60
 * widgets. `WIDGET_TYPES` (`dashboard-desktop.js`) conhecia 48. Os 22 restantes
 * eram clique morto:
 *
 *     window.addWidget = function (widgetId) {
 *         var type = WIDGET_TYPES[widgetId];
 *         if (!type) return 'desconhecido';   // <-- aqui morriam os 22
 *
 * O produtor clicava, aparecia um toast de "Widget desconhecido", e nada era
 * colocado. Pior ainda: se a guarda fosse removida, `generateWidgetContent`
 * devolvia string vazia e o bloco nascia como um buraco na matriz.
 *
 * Porque um teste e não uma nota no changelog
 * -------------------------------------------
 * As duas listas vivem em ficheiros diferentes e crescem por conta própria —
 * um widget novo entra no catálogo e ninguém se lembra do registo. Este teste
 * é a regra que fecha essa porta: se alguém acrescentar ao catálogo sem
 * acrescentar aqui, a suite falha no commit, e não o produtor na sexta-feira.
 */

const RAIZ = resolve(__dirname, '../..');
// `window.WIDGET_CATALOG` era inline no index.html e passou para pagina-index.js
// (extraído; carregado via <script src>). O contrato é o mesmo; a fonte mudou.
const INDEX = readFileSync(resolve(RAIZ, 'app/static/js/pagina-index.js'), 'utf8');
const DESKTOP = readFileSync(resolve(RAIZ, 'app/static/js/tabs/dashboard-desktop.js'), 'utf8');

/** Os ids que o modal oferece ao utilizador. */
function idsDoCatalogo() {
  const i = INDEX.indexOf('window.WIDGET_CATALOG = {');
  expect(i, 'WIDGET_CATALOG tem de existir no index.html').toBeGreaterThan(-1);
  const bloco = INDEX.slice(i, i + 40000);
  return [...bloco.matchAll(/\{\s*id:\s*'([^']+)'/g)].map((m) => m[1]);
}

/** Os ids que `addWidget` sabe colocar. */
function idsDosTipos() {
  const i = DESKTOP.indexOf('const WIDGET_TYPES = {');
  expect(i, 'WIDGET_TYPES tem de existir em dashboard-desktop.js').toBeGreaterThan(-1);
  // Termina em `let widgets = {}` — e NÃO no primeiro `\n};`, que agora cai a
  // meio de uma ficha multilinha e cortava o objecto a meio.
  const fim = DESKTOP.indexOf('let widgets = {}', i);
  expect(fim, 'o objecto WIDGET_TYPES tem de estar seguido de `let widgets`').toBeGreaterThan(i);
  const bloco = DESKTOP.slice(i, fim);
  return [...bloco.matchAll(/'([a-z0-9-]+)'\s*:\s*\{/g)].map((x) => x[1]);
}

describe('catálogo de widgets — nenhum clique pode ser morto', () => {
  const catalogo = idsDoCatalogo();
  const tipos = idsDosTipos();

  it('o modal oferece widgets (guarda contra parse silenciosamente vazio)', () => {
    expect(catalogo.length).toBeGreaterThan(50);
  });

  it('todo widget do catálogo tem ficha em WIDGET_TYPES', () => {
    const orfaos = catalogo.filter((id) => !tipos.includes(id));
    expect(
      orfaos,
      `widgets anunciados no modal que o addWidget nao conhece (clique morto): ${orfaos.join(', ')}`
    ).toEqual([]);
  });

  it('cada ficha declara tamanho default (sem isto, findFreePosition não tem o que medir)', () => {
    const i = DESKTOP.indexOf('const WIDGET_TYPES = {');
    const bloco = DESKTOP.slice(i, DESKTOP.indexOf('let widgets = {}', i));
    const semTamanho = [...bloco.matchAll(/'([a-z0-9-]+)'\s*:\s*\{([^}]*)\}/g)]
      .filter(([, , corpo]) => !/defaultSize/.test(corpo))
      .map(([, id]) => id);
    expect(semTamanho, `fichas sem defaultSize: ${semTamanho.join(', ')}`).toEqual([]);
  });

  it('addWidget tem auto-registo: um id novo nunca volta a ser clique morto', () => {
    // A rede de segurança. Registar os 22 corrige o sintoma; isto corrige a
    // CAUSA — um widget anunciado passa a ser instalável mesmo que a ficha se
    // perca, em vez de devolver 'desconhecido' e não fazer nada.
    const i = INDEX.indexOf('window.addWidget = function');
    expect(i, 'addWidget tem de existir no index.html').toBeGreaterThan(-1);
    const corpo = INDEX.slice(i, i + 2600);

    expect(corpo).toMatch(/WIDGET_CATALOG/);
    expect(corpo).toMatch(/WIDGET_TYPES\[widgetId\]\s*=\s*type/);
  });

  it('generateWidgetContent nunca devolve string vazia (seria um buraco na matriz)', () => {
    const i = INDEX.indexOf('window.generateWidgetContent = function');
    expect(i).toBeGreaterThan(-1);
    const corpo = INDEX.slice(i, i + 1200);
    expect(
      corpo,
      'devolver "" cria um contentor sem conteúdo — o widget fica invisível'
    ).not.toMatch(/return\s*['"]['"]\s*;/);
  });
});

describe('KPIs sem dado — zero não é a mesma coisa que "não medido"', () => {
  const corpoKpis = INDEX.slice(INDEX.indexOf("'kpi-roi':"), INDEX.indexOf("'kpi-insumos':"));

  it('o backend distingue "sem área medida" de "área zero"', () => {
    // Este é o contrato que o front-end tinha a obrigação de respeitar e
    // não respeitava: `area_medida` existe no payload e nunca era lido.
    expect(corpoKpis).toMatch(/SEM_DADO/);
  });

  it('kpi-custo não divide por uma área inventada', () => {
    // `prop.area_total || talhoes.area_total || 1` punha 1 ha no lugar de uma
    // área não medida, e dividia a despesa real por esse 1 — de R$ 0,00/ha a
    // R$ 15.000,00/ha, ambos igualmente falsos.
    expect(corpoKpis).not.toMatch(/area_total\s*\|\|\s*talhoes\.area_total\s*\|\|\s*1/);
  });

  it('kpi-roi não transforma "sem despesa registada" em 0%', () => {
    // `if (roiVal == null) roiVal = 0;` com um `+` à frente mostrava "+0,0%",
    // que se lê como um empate medido.
    expect(corpoKpis).not.toMatch(/roiVal\s*==\s*null\)\s*roiVal\s*=\s*0/);
  });

  it('kpi-manutencoes não diz "OK" quando não sabe', () => {
    // Ausência de dado vestida de "tudo bem" é o pior dos dois mundos:
    // tranquiliza o produtor sobre uma máquina que ninguém monitoriza.
    const bloco = corpoKpis.slice(corpoKpis.indexOf("'kpi-manutencoes':"));
    expect(bloco.slice(0, 700)).toMatch(/==\s*null/);
  });

  it('existe um marcador de "sem dado" partilhado', () => {
    expect(INDEX).toMatch(/window\.SEM_DADO\s*=/);
  });

  it('kpi-sensores dá a mesma resposta para a falta de leitura', () => {
    // A temperatura já caía em "--°C" e a umidade em "0%": mesmo widget, duas
    // respostas para a mesma pergunta, e a de umidade a dizer que o sensor
    // mediu zero.
    // A janela é o PRÓPRIO BLOCO, não um número de caracteres. Um limite
    // fixo (900) acopla o teste ao tamanho do comentário que precede o
    // código: acrescentar duas linhas de explicação ao widget faz o teste
    // falhar sem que o widget tenha mudado um único carácter de
    // comportamento — e a resposta a isso é encurtar o comentário, que é
    // o caminho errado. O bloco termina em `})()`, como nos outros testes
    // deste ficheiro.
    const i = corpoKpis.indexOf("'kpi-sensores':");
    const bloco = corpoKpis.slice(i, corpoKpis.indexOf('})()', i));
    expect(bloco).toMatch(/um\s*!=\s*null\s*\?\s*um\s*\+\s*'%'\s*:\s*'--'/);
    expect(bloco).not.toMatch(/:\s*'0%'/);
  });

  it('kpi-margem-bruta não divide por receitas que não existem', () => {
    // `rec > 0 ? ... : 0` mostrava "0,0%" — uma margem medida, que é
    // precisamente o que não existe quando não há receita.
    expect(corpoKpis).not.toMatch(/rec\s*>\s*0\s*\?\s*\(\(rec\s*-\s*desp\)/);
  });

  it('os contadores (equipa, rebanho, safras) não dizem 0 quando não sabem', () => {
    for (const [id, rotulo] of [
      ['kpi-funcionarios', 'Equipe'],
      ['kpi-animais', 'Rebanho'],
      ['kpi-safras', 'Safras Ativas'],
      ['kpi-produtividade', 'Produtividade Média'],
      ['kpi-caixa', 'Fluxo de Caixa'],
    ]) {
      const i = corpoKpis.indexOf(`'${id}':`);
      expect(i, `faltou o widget ${id}`).toBeGreaterThan(-1);
      const bloco = corpoKpis.slice(i, corpoKpis.indexOf('})()', i));
      // tem de ter uma saida de "sem dado" antes de mostrar o numero
      expect(bloco, `${rotulo} (${id}) mostra um numero sem nunca dizer "sem dado"`).toMatch(
        /SEM_DADO/
      );
    }
  });
});
