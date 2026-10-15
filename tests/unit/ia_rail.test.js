// A barra lateral do AmplIA: o que ela promete tem de existir.
//
// MEDIDO 2026-10-09: `ia-rail.js:100` tinha
//   attrs.push('onclick="window.IaRail.acao(\'' + it.id + '\'')');
// com as aspas desbalanceadas. `node --check` falhava, o módulo inteiro não
// carregava, e a barra não desenhava NADA — sem erro na consola, sem aviso, e
// com um teste a dizer que estava verde. Foi o que produziu "os ícones estão lá
// mas os nomes nunca aparecem": a barra não estava mal desenhada, a barra não
// existia.
//
// Daí o primeiro teste deste ficheiro, que é o mais importante de todos: um
// erro de sintaxe é a falha mais barata de apanhar e a mais cara de deixar
// passar, porque ela leva o ficheiro INTEIRO e não uma linha.

import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { execFileSync } from 'node:child_process';

const RAIL = resolve(process.cwd(), 'app/static/js/ia-local/ia-rail.js');
const ACOES = resolve(process.cwd(), 'app/static/js/ia-local/ia-rail-acoes.js');
const SRC = readFileSync(RAIL, 'utf8');
const SRC_ACOES = readFileSync(ACOES, 'utf8');

/* O ficheiro é um IIFE. Extrair as funções puras é o que permite testá-las sem
   DOM; o resto (montar, menus) precisa de `document` e é testado à parte. */
function extrai(nome) {
  const i = SRC.indexOf(`function ${nome}(`);
  if (i < 0) throw new Error(`${nome}() nao existe`);
  let d = 0;
  const j = SRC.indexOf('{', i);
  for (let k = j; k < SRC.length; k++) {
    if (SRC[k] === '{') d++;
    else if (SRC[k] === '}') {
      d--;
      if (d === 0) return SRC.slice(i, k + 1);
    }
  }
  throw new Error(`${nome}() nao fecha`);
}

/* As listas sao `var ITENS = [...]`, nao funcoes. O fecho e' o `]` que volta
   a profundidade zero — e a profundidade conta `[`/`]` FORA de strings e de
   comentarios, para um `]` ou `'` dentro de texto (o `path` do icone sidebar,
   ou um apostofo num comentario) nao fechar ou envenenar a lista a meio. */
function extraiLista(nome) {
  const i = SRC.indexOf(`var ${nome} = [`);
  if (i < 0) throw new Error(`${nome} nao existe`);
  const ini = SRC.indexOf('[', i);
  let d = 0;
  let aspas = null;
  let crase = false;
  for (let k = ini; k < SRC.length; k++) {
    const ch = SRC[k];
    const prox = SRC[k + 1];
    if (crase) {
      if (ch === '\\') k++;
      else if (ch === '`') crase = false;
      continue;
    }
    if (aspas) {
      if (ch === '\\') k++;
      else if (ch === aspas) aspas = null;
      continue;
    }
    if (ch === '/' && prox === '*') {
      const fim = SRC.indexOf('*/', k + 2);
      k = fim < 0 ? SRC.length : fim + 1;
      continue;
    }
    if (ch === '/' && prox === '/') {
      const fim = SRC.indexOf('\n', k + 2);
      k = fim < 0 ? SRC.length : fim;
      continue;
    }
    if (ch === '`') crase = true;
    else if (ch === '"' || ch === "'") aspas = ch;
    else if (ch === '[') d++;
    else if (ch === ']') {
      d--;
      if (d === 0) return SRC.slice(ini, k + 1);
    }
  }
  throw new Error(`${nome} nao fecha`);
}

/* `ic()` embrulha o corpo do SVG, e `ITENS` e' uma lista que o chama. Tem de
   existir ANTES do primeiro `eval`, senao a lista rebenta em runtime com um
   ReferenceError numa linha que nao tem nada de errada. */
const SVG =
  '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">';
const ic = (corpo) => SVG + corpo + '</svg>';

const esc = eval(`(${extrai('esc')})`);
const existe = eval(`(${extrai('existe')})`);
const itemHTML = eval(`(${extrai('itemHTML')})`);

/* A lista real, extraida do proprio ficheiro. Uma lista escrita a mao aqui
   seria uma segunda lista — e a segunda lista e' o que diverge. */
const ITENS = eval(`(${extraiLista('ITENS')})`);

describe('o ficheiro carrega', () => {
  /* O teste que teria apanhado a barra inteira a desaparecer. */
  it('ia-rail.js: JS que o browser consegue ler', () => {
    expect(() =>
      execFileSync(process.execPath, ['--check', RAIL], { stdio: 'pipe' })
    ).not.toThrow();
  });

  it('ia-rail-acoes.js: JS que o browser consegue ler', () => {
    expect(() =>
      execFileSync(process.execPath, ['--check', ACOES], { stdio: 'pipe' })
    ).not.toThrow();
  });

  it('as accoes sao carregadas ANTES da barra, e nao ao contrario', () => {
    /* `ia-rail.js` decide se um botao esta activo olhando para `window[nome]`, e
     * os dois sao dois ficheiros separados. Se a barra desenhar primeiro, sai
     * uma barra toda cinzenta e ninguem redesenha — era o que acontecia. */
    const loader = readFileSync(
      resolve(process.cwd(), 'app/static/js/ia-local/ia-rail-loader.js'),
      'utf8'
    );
    /* Procura-se o `import(` e não o nome do ficheiro: o nome aparece primeiro
     * no comentário do topo do loader ("Carrega o `ia-rail.js` e monta a
     * barra"), e uma asserção feita sobre o nome mede o comentário. */
    const iAcoes = loader.indexOf("import('/static/js/ia-local/ia-rail-acoes.js");
    const iRail = loader.indexOf("import('/static/js/ia-local/ia-rail.js");
    expect(iAcoes).toBeGreaterThan(-1);
    expect(iRail).toBeGreaterThan(-1);
    expect(iAcoes, 'ia-rail.js nao pode ser carregado antes das accoes').toBeLessThan(iRail);
  });
});

describe('a barra lateral', () => {
  beforeEach(() => {
    global.window = {};
  });
  afterEach(() => {
    delete global.window;
  });

  it('cada separador sai como separador, nunca como botao', () => {
    // O defeito medido. Um `{sep:1}` sem accao produzia um <button> vazio.
    const separadores = ITENS.filter((i) => i.sep);
    expect(separadores.length).toBeGreaterThan(0);
    for (const sep of separadores) {
      const html = itemHTML(sep);
      expect(html).toContain('ia-rail-sep');
      expect(html).not.toContain('ia-rail-item');
    }
  });

  it('todo item tem rotulo, dica e icone', () => {
    /* A dica é o que diz o que o botão FAZ. Sem ela, quem passa o rato lê só
     * o nome, e "Criar no painel" não diz se cria um dashboard ou se pinta
     * alguma coisa na conversa. */
    for (const it of ITENS.filter((i) => !i.sep)) {
      expect(it.rotulo, `item ${it.id} sem rotulo`).toBeTruthy();
      expect(it.dica, `item ${it.id} sem dica`).toBeTruthy();
      expect(it.icone, `item ${it.id} sem icone`).toBeTruthy();
      expect(it.icone).toContain('<svg');
    }
  });

  it('todo item tem accao — nunca nenhum', () => {
    /* Um item sem `accao` e' um botão que não faz nada. O produtor clica, o
     * ecrã não muda, e conclui que a IA está avariada — a mesma razão pela
     * qual uma recusa tem sempre motivo. */
    for (const it of ITENS.filter((i) => !i.sep)) {
      expect(Boolean(it.accao), `${it.id} nao tem accao`).toBe(true);
      expect(it.menu, `${it.id} ainda tem o campo menu do design antigo`).toBeUndefined();
    }
  });

  it('uma chave fica ACTIVA e diz que e interruptor', () => {
    /* O par `criar-no-chat` / `criar-no-painel` / `usar-nuvem` trocou o menu
     * antigo por uma CHAVE. A chave tem de continuar utilizavel — se sair
     * desactivada, ligar o modo fica um botao cinzento que nao faz nada, que
     * e' exactamente o defeito que o teste do menu apanhava. */
    const comChave = ITENS.filter((i) => !i.sep && i.chave);
    expect(comChave.length, 'nenhuma chave seletora na barra').toBeGreaterThan(0);
    window.iaAlternarModo = () => {};
    for (const it of comChave) {
      const html = itemHTML(it);
      expect(html, `${it.id} tem chave mas saiu desactivado`).not.toContain('disabled');
      expect(html).not.toContain('ainda não existe');
      /* O leitor de ecra tem de anunciar interruptor, nao botao comum: sem
       * `role="switch"` + `aria-pressed`, quem nao ve o ecra nao sabe se a
       * chave esta ligada. */
      expect(html, `${it.id} tem chave sem role="switch"`).toContain('role="switch"');
      expect(html).toContain('aria-pressed="');
    }
  });

  it('nenhum item ficou com o campo menu do design antigo', () => {
    /* Havia menus (`menu:'chat'` + `ia-rail-seta` + `aria-haspopup`) antes de
     * o produtor pedir chaves seletoras. O campo morreu com o design, e este
     * teste e' o que avisa se alguem o ressuscitar sem o implementar: um item
     * com `menu` e sem `accao` volta a ser um botao cinzento que nao faz nada
     * — o defeito medido no browser que o comentario abaixo registava. */
    const comMenu = ITENS.filter((i) => !i.sep && i.menu);
    expect(comMenu.length, 'voltou o menu antigo, sem accao propria').toBe(0);
  });

  it('o HTML nunca chama uma funcao que nao existe', () => {
    /* MEDIDO no browser: `onclick="window.IaRail.passa(...)"` e a API
     * exportava `passar`. O botão ficava activo, o clique não fazia nada, e a
     * consola dizia `TypeError: window.IaRail.passa is not a function` — que é
     * a única pista, e só quem abre a consola a vê. */
    window.iaChatReset = () => {};
    const chamadas = new Set();

    for (const it of ITENS.filter((i) => !i.sep)) {
      const html = itemHTML(it);
      for (const m of html.matchAll(/window\.IaRail\.(\w+)\(/g)) chamadas.add(m[1]);
    }

    // O que a API exporta — lido do próprio ficheiro, para a lista não divergir.
    const exportadas = new Set([...SRC.matchAll(/^\s{4}(\w+):\s*function/gm)].map((m) => m[1]));

    expect(chamadas.size).toBeGreaterThan(0);
    for (const nome of chamadas) {
      expect(exportadas.has(nome), `o HTML chama IaRail.${nome}() e a API nao o exporta`).toBe(
        true
      );
    }
  });

  it('so fica activo o que tem funcao', () => {
    window.iaChatReset = () => {};
    for (const it of ITENS.filter((i) => !i.sep)) {
      const html = itemHTML(it);
      const temFuncao = Boolean(it.accao) && typeof window[it.accao] === 'function';
      if (temFuncao) {
        expect(html, `${it.id} e utilizavel mas saiu desactivado`).not.toContain('disabled');
      } else {
        expect(html, `${it.id} nao tem funcao mas esta activo`).toContain('disabled');
      }
    }
  });

  it('os ids sao unicos — o menu procura por data-id', () => {
    const ids = ITENS.filter((i) => !i.sep).map((i) => i.id);
    expect(new Set(ids).size).toBe(ids.length);
  });

  it('nenhum botao diz "undefined" na dica', () => {
    // Um `title` com "undefined" e' o rasto de um campo em falta. Passa
    // despercebido numa lista de icones.
    for (const it of ITENS.filter((i) => !i.sep)) {
      const html = itemHTML(it);
      expect(html, `${it.id} diz undefined`).not.toContain('undefined');
      expect(html, `${it.id} diz null`).not.toContain('null');
    }
  });

  it('o texto de um item nao parte o atributo title', () => {
    for (const it of ITENS.filter((i) => !i.sep)) {
      const html = itemHTML(it);
      const titulo = (html.match(/title="([^"]*)"/) || [])[1];
      expect(titulo === undefined || titulo.length > 0, `${it.id} sem title`).toBe(true);
    }
  });
});

/* As seis funções que o produtor pediu, pelo nome. Nomes literais de propósito:
   um teste que verifica "alguma acção existe" passa com uma barra que não tem
   meio do que foi pedido. */
describe('as seis funcoes que a barra tem de ter', () => {
  const porItem = (id) => ITENS.find((i) => i.id === id);

  it('1. selecionar um espaco na tela para a IA ler', () => {
    const it = porItem('selecionar-area');
    expect(it).toBeTruthy();
    expect(it.accao).toBe('iaSelecionarArea');
  });

  it('2. importar documento', () => {
    const it = porItem('importar-documento');
    expect(it).toBeTruthy();
    expect(it.accao).toBe('iaImportarDocumento');
  });

  it('3. nova conversa', () => {
    const it = porItem('nova-conversa');
    expect(it).toBeTruthy();
    expect(it.accao).toBe('iaChatReset');
  });

  it('4. historico', () => {
    const it = porItem('historico');
    expect(it).toBeTruthy();
    expect(it.accao).toBe('iaHistorico');
  });

  /* Os dois "criar" são CHAVE SELETORA, não menu.
   *
   * PEDIDO DO PRODUTOR, citado em `ia-rail.js`: "não são menus de escolha,
   * mas sim quando escolhadas forçam a IA a responder nesses locais de forma
   * personalizada e menos textual". Ligada, a chave injecta uma DIRECTIVA em
   * cada pergunta (`ia-modos.js`) e a resposta vem como PEÇA — planilha e
   * gráfico no chat, widgets no preset do dashboard.
   *
   * Este ficheiro já testou o design anterior: `menu: 'chat'` e uma lista
   * `FERRAMENTAS` com `iaCriarPlanilha`, `iaCriarGrafico`, `iaCriarNoPainel`
   * e `iaResponderNoPainel` — quatro acções que NUNCA existiram em
   * `ia-rail-acoes.js`. O teste morria em
   * `eval((${extrai('ferramentasDe')}))` com "ferramentasDe() nao existe",
   * e a suite inteira ia a vermelho sem medir nada.
   *
   * O que se mede agora é o contrato QUE EXISTE: `chave` liga a um modo real
   * da loja, e `accao` é o interruptor que está implementado. */
  it('5. criar no chat: e uma chave que liga o modo chat', () => {
    const it = porItem('criar-no-chat');
    expect(it, 'sem o item criar-no-chat').toBeTruthy();
    expect(it.chave, 'criar-no-chat deixou de ser chave seletora').toBe('chat');
    expect(it.accao).toBe('iaAlternarModo');
    expect(it.menu, 'criar-no-chat voltou a ser menu').toBeUndefined();
  });

  it('6. criar no painel: e uma chave que liga o modo painel', () => {
    const it = porItem('criar-no-painel');
    expect(it, 'sem o item criar-no-painel').toBeTruthy();
    expect(it.chave, 'criar-no-painel deixou de ser chave seletora').toBe('painel');
    expect(it.accao).toBe('iaAlternarModo');
    expect(it.menu, 'criar-no-painel voltou a ser menu').toBeUndefined();
  });

  it('cada item diz o que faz', () => {
    for (const it of ITENS.filter((i) => !i.sep)) {
      expect(it.rotulo, `item ${it.id} sem rotulo`).toBeTruthy();
      expect(it.dica, `${it.rotulo} sem dica`).toBeTruthy();
    }
  });

  it('toda accao chamada existe no ia-rail-acoes.js', () => {
    const definidas = new Set(
      [...SRC_ACOES.matchAll(/window\.(\w+)\s*=\s*(?:async\s+)?function/g)].map((m) => m[1])
    );
    // `iaChatReset` vive no TEMPLATE, e é o reset verdadeiro.
    definidas.add('iaChatReset');

    const chamadas = [...ITENS.filter((i) => !i.sep).map((i) => i.accao)].filter(Boolean);

    expect(chamadas.length).toBeGreaterThan(0);
    for (const nome of chamadas) {
      expect(
        definidas.has(nome),
        `${nome} e' chamada pela barra mas nao esta definida em ia-rail-acoes.js`
      ).toBe(true);
    }
  });

  /* MEDIDO: havia um `window.iaChatReset` no módulo de acções que SÓ fechava a
     janela e limpava o input. Como o módulo carrega depois do template, ele
     sobrescrevia o reset verdadeiro — e "Nova conversa" da barra fechava o
     painel sem apagar nada. Duas funções com o mesmo nome em dois ficheiros, e
     a que ganha é a que chega depois. */
  it('"nova conversa" nao fica definida em dois sitios', () => {
    expect(SRC_ACOES).not.toMatch(/window\.iaChatReset\s*=/);
    expect(SRC).toContain("accao: 'iaChatReset'");
  });
});

describe('o chat guarda por completo e abre por botao, nunca por hover', () => {
  /* MEDIDO 2026-10-10: guardado, um pedaco de 42px (a `.ia-rail` absoluta,
   * orfa do `#ia-dock` sem area propria) ficava na tela. E a barra abria no
   * `:hover` — a janela saltava so' de passar o rato por cima. Agora:
   * guardado = `display:none`; expandir/guardar = classe `.aberta` por botao. */
  it('guardado some por completo e expandir/guardar e botao, nunca hover', () => {
    const CSS = readFileSync(resolve(process.cwd(), 'app/static/css/ia-rail.css'), 'utf8');
    /* Nenhum `:hover` MUDA A LARGURA da barra — o hover que sobrou e' so'
     * tinta de botao (fundo de item, de fechar, de toggle), nunca abrir. */
    const regras = CSS.replace(/\/\*[\s\S]*?\*\//g, '');
    const linhas = regras.split('\n');
    for (const linha of linhas) {
      if (!/\.ia-rail(?![-\w])\s*:\s*hover/.test(linha)) continue;
      expect(linha, `a barra ainda abre no hover: ${linha.trim()}`).not.toMatch(/width\s*:/);
    }
    expect(regras).toMatch(/\.ia-rail\.aberta\s*\{[^}]*width\s*:/);
    /* Guardada some por completo (display:none), nao `width:0` que deixava
     * borda e padding visiveis. */
    expect(CSS).toMatch(/\.ia-rail\.ia-rail-guardada\s*\{[^}]*display\s*:\s*none/);
    /* Expandida por classe `.aberta` (botao), com a largura de antes. */
    expect(CSS).toMatch(/\.ia-rail\.aberta\s*\{[^}]*width\s*:\s*212px/);
    expect(CSS).toMatch(/\.ia-rail\.aberta\s+\.ia-rail-txt\s*\{[^}]*max-width\s*:\s*150px/);
    /* O botao expandir/guardar mora na RAIL (primeiro item, `alternar-barra`,
     * icone `bi-layout-sidebar` no topo dela) — e nao solto no cabecalho: assim
     * ele vai junto quando a rail guarda. A funcao mora em `ia-rail-acoes.js`,
     * onde moram as outras accoes da barra (o `itemHTML` desenha activo so'
     * o que existe no momento do desenho). */
    expect(SRC).toContain("id: 'alternar-barra'");
    expect(SRC).toContain("accao: 'iaRailToggle'");
    expect(SRC).toContain('M0 3a2 2 0 0 1 2-2h12');
    expect(SRC_ACOES).toContain('window.iaRailToggle');
    const TPL = readFileSync(resolve(process.cwd(), 'app/templates/partials/ia_dock.html'), 'utf8');
    expect(TPL, 'o botao antigo ainda esta no cabecalho').not.toContain('id="ia-rail-toggle"');
    /* A barra arranca guardada: sem isso o primeiro paint mostra a lasca. */
    const iNav = TPL.indexOf('<nav');
    expect(iNav).toBeGreaterThan(-1);
    const navTag = TPL.slice(iNav, TPL.indexOf('>', iNav));
    expect(navTag).toContain('id="ia-rail"');
    expect(navTag).toContain('ia-rail-guardada');
    /* Fechar o chat guarda a barra junto — e nao so' tira o `open`. */
    expect(TPL).toContain('window.iaDockFechar');
    expect(TPL).toContain("rail.classList.toggle('ia-rail-guardada'");
    /* Reabrir mostra a barra junto — `iaDockAbrir` em todo ponto que poe
     * `open` no chat. */
    expect(TPL).toContain('window.iaDockAbrir');
    for (const src of [
      readFileSync(resolve(process.cwd(), 'app/static/js/ia-local/ia-print.js'), 'utf8'),
      readFileSync(resolve(process.cwd(), 'app/static/js/ia-local/ia-rail-acoes.js'), 'utf8'),
    ]) {
      expect(src).toContain('iaDockAbrir');
    }
  });
});

describe('os botoes que produzem pecas fazem o trabalho', () => {
  beforeEach(() => {
    global.window = {};
  });
  afterEach(() => {
    delete global.window;
  });

  /* O que este bloco já testou, e porque foi embora:
   *
   * Havia dois testes aqui à procura de `iaCriarPlanilha`, `iaCriarGrafico`,
   * `iaCriarNoPainel` e `iaResponderNoPainel` em `ia-rail-acoes.js` — quatro
   * acções que NUNCA existiram. O primeiro morria em
   * `expect(i).toBeGreaterThan(-1)` com "iaCriarPlanilha nao existe"; o
   * segundo, em `carregaCatalogo|idsDoCatalogo`, porque ia `-1` e o `slice`
   * devolvia uma string vazia.
   *
   * Não eram testes a apanhar um defeito: eram testes a descrever um design
   * que o produtor rejeitou. O pedido está citado em `ia-rail.js` — "não são
   * menus de escolha, mas sim quando escolhadas forçam a IA a responder nesses
   * locais" — e a resposta foi a CHAVE SELETORA, não o menu de ferramentas.
   * Um teste que insiste num contrato abandonado não protege nada: passa a
   * vida a falhar por um motivo que ninguém vai corrigir, e o vermelho deixa
   * de querer dizer o que quer dizer.
   *
   * O que FICA é o que estes botões prometem HOJE, e nenhum deles precisa de
   * gravar nada. */

  it('nenhum botao escreve fora da porta do sandbox', () => {
    /* Nenhuma acção pode fazer `fetch` para gravar. `iaCriarNoPainel` e
     * `iaResponderNoPainel` PEDEM o preset; quem grava é o `h_preset_palco`,
     * depois de o produtor responder que sim. */
    const iGrava = SRC_ACOES.indexOf("method: 'POST'");
    const iMethod = SRC_ACOES.indexOf('method:');
    /* Este ficheiro nao deve conter NENHUM `method:` de fetch. */
    expect(iMethod, 'ia-rail-acoes.js tem um fetch de escrita').toBe(-1);
    expect(iGrava).toBe(-1);
  });

  /* O print deixou de ser um rectângulo sobre a página. A marcação e o overlay
   * foram para `ia-print.js`, e este teste passou a ler esse ficheiro: assertar
   * sobre `ia-rail-acoes.js` já não mediria nada — e um teste que mede o
   * ficheiro errado é um teste verde sobre código que ninguém executa. */
  it('a marcação da tela vive no modulo do print, e nao na barra', () => {
    const PRINT = readFileSync(
      resolve(process.cwd(), 'app/static/js/ia-local/ia-print.js'),
      'utf8'
    );
    /* A barra DELEGACAO: chama o modulo, e nao faz o trabalho ela.
     *
     * Os marcadores do codigo antigo sao `XMLSerializer` e `serializeToString`,
     * que eram o que rasterizava o DOM. A palavra `foreignObject` aparece nos
     * COMENTARIOS, a explicar porque foi embora — e um `not.toMatch` sobre
     * texto inteiro reprovaria a documentacao que explica o problema. */
    expect(SRC_ACOES).not.toContain('XMLSerializer');
    expect(SRC_ACOES).not.toContain('serializeToString');
    expect(PRINT).toMatch(/removeEventListener\('keydown'/);
  });

  it('o overlay da tela e um <video> do fluxo, nao um esboco do DOM', () => {
    const PRINT = readFileSync(
      resolve(process.cwd(), 'app/static/js/ia-local/ia-print.js'),
      'utf8'
    );
    /* `foreignObject` nao rasteriza em Firefox nem em Safari, nao traz o CSS de
     * fora, nao traz <img> com crossorigin, nem canvas — e nao apanha nada que
     * esteja fora do DOM. Um "print da tela" que so fotografa a pagina nao e'
     * um print da tela. */
    expect(PRINT).toContain('getDisplayMedia');
    expect(PRINT).toContain('preferCurrentTab');

    /* E o desenho sai do VIDEO, nao de uma string de HTML.
     *
     * MEDIDO: este teste banhia `XMLSerializer` no ficheiro INTEIRO. Depois o
     * recorte passou a serializar o DOM para SVG (funcao propria, com o clone
     * a levar `xmlns` e as imagens da mesma origem a virar data URL), e o teste
     * foi a vermelho por uma razao que nao era a dele: a proibicao certa e' a
     * do CAMINHO DA CAPTURA, e a do recorte e' outra feature.
     *
     * Por isso a medicao e' sobre as duas funcoes que interessam, e nao sobre
     * o texto do ficheiro: quem captura e quem pinta. */
    const pega = (nome) => {
      const i = PRINT.indexOf(`function ${nome}(`);
      expect(i, `funcao ${nome}() nao existe`).toBeGreaterThan(-1);
      const j = PRINT.indexOf('{', i);
      let d = 0;
      for (let k = j; k < PRINT.length; k++) {
        if (PRINT[k] === '{') d++;
        else if (PRINT[k] === '}' && --d === 0) return PRINT.slice(i, k + 1);
      }
      throw new Error(`${nome}() nao fecha`);
    };

    const captura = pega('pedeEcra');
    expect(captura, 'a captura deixou de pedir o ecra').toContain('getDisplayMedia');

    const pintor = pega('frameParaCanvas');
    /* O frame vem do VIDEO e vai para um CANVAS. Uma serializacao do DOM aqui
     * seria o esboco que este teste existe para impedir. */
    expect(pintor).toContain('drawImage(video');
    expect(pintor).not.toContain('XMLSerializer');
    expect(pintor).not.toContain('serializeToString');
  });

  it('o print so e permitido na pagina do Ampliagro', () => {
    const PRINT = readFileSync(
      resolve(process.cwd(), 'app/static/js/ia-local/ia-print.js'),
      'utf8'
    );
    /* O pedido e' explicito. A guarda e' a mesma que o `base.html` usa para
     * esconder a barra de widgets, mais a visibilidade da appbar — que o
     * `spa.js` alterna ao trocar de aba sem recarregar. */
    expect(PRINT).toContain('ePaginaDoAmpliagro');
    expect(PRINT).toContain("'/dashboard/'");
    expect(PRINT).toMatch(/dashboard-appbar/);
    /* E a guarda e' a PRIMEIRA coisa que `capturar` faz, ANTES de pedir a
     * tela: pedir a tela e' o pedido caro — mostra um pedido ao sistema
     * operativo e acende um ponto no ecra — e nao se pede para depois se
     * recusar. */
    const i = PRINT.indexOf('function capturar');
    const corpo = PRINT.slice(i, PRINT.indexOf('\n  }', i));
    const guarda = corpo.indexOf('motivoDaRecusa');
    expect(guarda).toBeGreaterThan(-1);
    /* `pedeEcra()` e' quem chama `getDisplayMedia`, e vem DEPOIS da guarda. */
    expect(corpo.indexOf('pedeEcra()')).toBeGreaterThan(guarda);
    expect(PRINT.indexOf('function pedeEcra')).toBeGreaterThan(-1);
  });

  /* O print é do ecrã que ESTAVA no ecrã. Sobreviver a um "nova conversa" é
     pior do que não aparecer: o produtor manda na mensagem seguinte uma imagem
     do que via ANTES de recomeçar, e a IA não tem como saber que já não é o
     mesmo ecrã.
     *
     * O `iaChatReset` de verdade está no TEMPLATE — que é onde o histórico
     * também é apagado — e por isso é aqui que se mede. */
  it('"nova conversa" limpa o print que ficou em cima do campo', () => {
    const TPL = readFileSync(resolve(process.cwd(), 'app/templates/partials/ia_dock.html'), 'utf8');
    const i = TPL.indexOf('window.iaChatReset=function');
    expect(i, 'o iaChatReset do template desapareceu').toBeGreaterThan(-1);
    const corpo = TPL.slice(i, TPL.indexOf('window.iaDockVoz', i));
    expect(corpo, '"nova conversa" nao limpa o print').toContain('IaPrint.limpar');
  });

  /* E o print entra no DOM ACIMA do campo de texto — a ordem do flex é o que
     o coloca em cima, sem CSS. */
  it('a caixa do print fica ANTES do campo, e a caixa existe', () => {
    const TPL = readFileSync(resolve(process.cwd(), 'app/templates/partials/ia_dock.html'), 'utf8');
    const iCaixa = TPL.indexOf('id="ia-print-caixa"');
    const iCampo = TPL.indexOf('id="ia-chat-input"');
    expect(iCaixa, 'a caixa do print nao esta no template').toBeGreaterThan(-1);
    expect(iCampo).toBeGreaterThan(-1);
    expect(iCaixa, 'a caixa do print vem DEPOIS do campo').toBeLessThan(iCampo);
  });

  /* Ler o print passa pelo caminho de leitura que ja existe. Um `POST` novo
     para o print seria um caminho novo para o mesmo registo — que e'
     exactamente o que `app/amplia_mcp/` existe para fechar. */
  it('ler o print usa o leitor de documentos, nao um fetch novo', () => {
    const TPL = readFileSync(resolve(process.cwd(), 'app/templates/partials/ia_dock.html'), 'utf8');
    expect(TPL).toContain('window.iaEnviarDocumentoBase64');
    /* Um unico leitor, e as tres entradas apontam para ele. */
    expect(TPL).toContain('async function iaLerDocumento');
    for (const entrada of ['iaDockImage', 'iaDockImageComFicheiro', 'iaEnviarTextoParaLeitura']) {
      const i = TPL.indexOf(`window.${entrada}=`);
      expect(i, `${entrada} nao existe`).toBeGreaterThan(-1);
      /* Estas funções são de várias linhas: cortar no primeiro `\n` pegava só
       * na assinatura, e a assinatura não diz para onde vai o pedido. */
      const corpo = TPL.slice(i, TPL.indexOf('\n};', i));
      expect(corpo, `${entrada} nao passa por iaLerDocumento`).toContain('iaLerDocumento');
    }
    /* E o leitor so' escreve pelo caminho governado. */
    expect((TPL.match(/\/api\/ia\/imagem-estoque\//g) || []).length).toBe(1);
  });

  it('importar documento diz o que nao sabe ler', () => {
    /* Um `accept` que promete `.pdf` e devolve "não consegui" é um botão que
     * mente sobre o que sabe fazer. O `ocr.py` recusa o PDF com uma mensagem
     * que explica porquê — e por isso o PDF não entra no `accept`. */
    expect(SRC_ACOES).toContain('ACEITA');
    const i = SRC_ACOES.indexOf('var ACEITA');
    const lista = SRC_ACOES.slice(i, SRC_ACOES.indexOf('\n', i));
    expect(lista).not.toContain('pdf');
    expect(lista).not.toContain('xlsx');
    expect(lista).toContain('.xml');
  });
});

describe('o texto que o produtor le', () => {
  beforeEach(() => {
    global.window = {};
  });
  afterEach(() => {
    delete global.window;
  });

  it('nenhum botao activo promete algo que nao faz', () => {
    /* Antes, seis botões estavam activos-com-texto "ainda não existe" ao mesmo
     * tempo, que é a forma mais clara de mentir. Hoje nenhum botao está
     * pendente, e este teste é o que impede que volte a estar. */
    window.iaChatReset = () => {};
    for (const it of ITENS.filter((i) => !i.sep)) {
      const html = itemHTML(it);
      if (!html.includes('disabled')) {
        expect(html, `${it.id} esta activo mas a dica diz que ainda nao existe`).not.toContain(
          'ainda'
        );
      }
    }
  });

  it('o rotulo nao e injetavel', () => {
    expect(esc('<img src=x onerror=alert(1)>')).toContain('&lt;img');
  });
});
