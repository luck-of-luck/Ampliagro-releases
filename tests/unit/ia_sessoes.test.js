// A loja das conversas: sessões com nome, uma por secção, e a troca de secção.
//
// Este ficheiro testa a lógica que estava no template — e que por isso não era
// testada. MEDIDO 2026-10-10: o botão "Histórico" dizia "Ainda não há conversa
// para ver" com conversa no ecrã. A causa era o ESCOPO, e a segunda causa era
// que a lógica vivia inline num `<script type="module">` de um template
// Django: nenhum teste a alcançava.
//
// Aqui corre o ficheiro de `app/static/js/ia-local/` contra o `window` do
// jsdom, que é o que o browser faz.

import { describe, it, expect, beforeEach, beforeAll, afterEach, vi } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const FONTE = readFileSync(resolve(process.cwd(), 'app/static/js/ia-local/ia-sessoes.js'), 'utf8');

/* O ficheiro é uma IIFE que se registou em `window.IaSessoes`. Corre o texto
   num contexto onde `window` é o do jsdom. */
function carrega() {
  // eslint-disable-next-line no-new-func
  new Function('window', 'document', 'navigator', FONTE)(window, document, navigator);
  return window.IaSessoes;
}

/* Navegar para um caminho. O jsdom tem a History API, e é ela que o gancho
   `observar()` embrulha — por isso navegar tem de ser pela história a sério. */
function vaiPara(caminho) {
  window.history.pushState({}, '', caminho);
}

describe('as sessões da conversa', () => {
  let S;
  let historiaLimpa;

  beforeAll(() => {
    /* O módulo EMBRULHA o `history.pushState` e guarda o original. Sem esta
       limpeza, o embrulho de um teste fica instalado no seguinte, e o teste
       seguinte mede o fecho do teste anterior — um verde que não mede nada. */
    historiaLimpa = {
      pushState: window.history.pushState,
      replaceState: window.history.replaceState,
    };
  });

  beforeEach(() => {
    window.history.pushState = historiaLimpa.pushState;
    window.history.replaceState = historiaLimpa.replaceState;
    delete window.history.__iaOriginal;
    /* A loja é SINGLETON: sem este `delete`, o `carrega()` devolve a instância
       do teste anterior, e o espião deste teste registava-se nos ouvintes
       daquele — a medir o fecho de outro teste. */
    delete window.IaSessoes;
    window.localStorage.clear();
    vaiPara('/estoque');
    S = carrega();
  });

  afterEach(() => {
    window.history.pushState = historiaLimpa.pushState;
    window.history.replaceState = historiaLimpa.replaceState;
    delete window.history.__iaOriginal;
    delete window.IaSessoes;
    window.localStorage.clear();
  });

  /* ── A SECÇÃO ─────────────────────────────────────────────────────────── */

  it('a lista está separada por secção', () => {
    S.guardar([{ role: 'user', content: 'quanta ureia tenho' }]);
    vaiPara('/financeiro');
    expect(S.listar(), 'o financeiro viu a conversa do estoque').toHaveLength(0);

    S.guardar([{ role: 'user', content: 'quanto vendi este mês' }]);
    expect(S.listar()).toHaveLength(1);
    expect(S.listar()[0].titulo).toContain('quanto vendi');

    vaiPara('/estoque');
    expect(S.listar()).toHaveLength(1);
    expect(S.listar()[0].titulo).toContain('ureia');
  });

  it('/financeiro e /financeiro/ são a MESMA secção', () => {
    /* Sem a normalização da barra final, o produtor entrava pela navegação e
       pelo botão de voltar e via duas conversas diferentes da mesma secção. */
    vaiPara('/financeiro');
    S.guardar([{ role: 'user', content: 'quanto vendi' }]);
    vaiPara('/financeiro/');
    expect(S.listar()).toHaveLength(1);
  });

  /* ── O NOME ───────────────────────────────────────────────────────────── */

  it('o nome vem da primeira pergunta do produtor', () => {
    S.guardar([
      { role: 'user', content: 'Qual minha produção total de milho' },
      { role: 'assistant', content: 'Foram 1.200 sacas.' },
    ]);
    expect(S.listar()[0].titulo).toBe('Qual minha produção total de milho');
  });

  it('um título longo corta por PALAVRAS, não a meio de uma', () => {
    /* Cortar aos 40 caracteres dá "Qual minha produção total de milho nes" —
       um nome que ninguém reconhece como sendo a pergunta que fez. */
    S.guardar([
      { role: 'user', content: 'Qual minha produção total de milho neste talhão do norte' },
    ]);
    const t = S.listar()[0].titulo;
    expect(t.length).toBeLessThanOrEqual(41);
    expect(t.endsWith('…')).toBe(true);
    expect(t).not.toMatch(/nes…$/);
  });

  it('uma conversa sem pergunta do produtor fica sem nome', () => {
    S.guardar([{ role: 'assistant', content: 'Olá!' }]);
    expect(S.listar()[0].titulo).toBe('');
  });

  it('renomear muda o nome', () => {
    S.guardar([{ role: 'user', content: 'ureia' }]);
    const id = S.listar()[0].id;
    expect(S.renomear(id, '  Compra de   ureia 2026  ')).toBe(true);
    expect(S.listar()[0].titulo).toBe('Compra de ureia 2026');
  });

  /* ── NOVA CONVERSA ────────────────────────────────────────────────────── */

  it('"nova conversa" guarda a anterior COM NOME', () => {
    /* É a ordem que importa: sem o `guardar` antes do `nova`, a conversa
       anterior fica na lista com título vazio — uma linha sem texto, que é uma
       conversa que ninguém reconhece. */
    S.guardar([{ role: 'user', content: 'quanta ureia tenho' }]);
    S.nova();
    const lista = S.listar();
    expect(lista).toHaveLength(2);
    const comNome = lista.filter((s) => s.titulo);
    expect(comNome).toHaveLength(1);
    expect(comNome[0].titulo).toContain('ureia');
  });

  it('"nova conversa" passa a ser a conversa do ecrã', () => {
    S.guardar([{ role: 'user', content: 'ureia' }]);
    const nova = S.nova();
    expect(S.atual().id).toBe(nova.id);
    expect(S.mensagens()).toHaveLength(0);
    expect(S.listar()[0].id).toBe(nova.id, 'a nova tem de subir ao topo');
  });

  /* ── RESTAURAR ────────────────────────────────────────────────────────── */

  it('restaurar devolve as mensagens da conversa antiga', () => {
    const msgs = [
      { role: 'user', content: 'quanta ureia' },
      { role: 'assistant', content: '12 sacas' },
    ];
    S.guardar(msgs);
    const antiga = S.listar()[0].id;
    S.nova();
    S.guardar([{ role: 'user', content: 'outra coisa' }]);

    expect(S.restaurar(antiga)).toEqual(msgs);
    expect(S.atual().id).toBe(antiga, 'restaurar passa a ser a conversa actual');
    expect(S.mensagens()).toEqual(msgs);
  });

  it('restaurar um id que não existe devolve null, não uma lista vazia', () => {
    /* `[]` seria uma conversa vazia, e o ecrã mostraria a saudação como se o
       produtor tivesse recomeçado. `null` é "não existe", e quem chama pode
       dizer isso. */
    expect(S.restaurar('sess_nao_existe')).toBeNull();
  });

  it('apagar tira a conversa da lista', () => {
    S.guardar([{ role: 'user', content: 'ureia' }]);
    const id = S.listar()[0].id;
    expect(S.apagar(id)).toBe(true);
    expect(S.listar()).toHaveLength(0);
  });

  it('apagar a conversa aberta deixa de a apontar', () => {
    S.guardar([{ role: 'user', content: 'ureia' }]);
    const id = S.listar()[0].id;
    S.apagar(id);
    expect(S.atual()).toBeNull();
  });

  /* ── LIMITES ──────────────────────────────────────────────────────────── */

  it('guarda no máximo 20 mensagens por conversa', () => {
    const muitas = [];
    for (let i = 0; i < 50; i++) {
      muitas.push({ role: 'user', content: 'mensagem ' + i });
    }
    S.guardar(muitas);
    expect(S.mensagens()).toHaveLength(20);
  });

  it('guarda no máximo 20 conversas por secção', () => {
    for (let i = 0; i < 25; i++) {
      S.nova();
      S.guardar([{ role: 'user', content: 'conversa ' + i }]);
    }
    expect(S.listar()).toHaveLength(20);
  });

  it('mensagens que não são objectos não rebentam o guardar', () => {
    expect(() => S.guardar([null, undefined, 42, { role: 'user', content: 'ok' }])).not.toThrow();
    expect(S.mensagens()).toHaveLength(1);
  });

  it('guardar nada numa secção sem conversa não cria conversa vazia', () => {
    /* Uma lista com uma linha "Nova conversa · vazia" antes de o produtor ter
       dito seja o que for é ruído. */
    S.guardar([]);
    expect(S.listar()).toHaveLength(0);
  });

  /* ── A TROCA DE SECÇÃO ────────────────────────────────────────────────── */

  it('observar avisa quando a secção muda', () => {
    /* O SPA muda de página com `pushState`, que NÃO dispara evento. Sem o
       gancho, o dock só descobre a troca quando o produtor escreve — e a
       primeira mensagem da secção nova entrava na conversa da anterior. */
    const cb = vi.fn();
    const parar = S.observar(cb);

    vaiPara('/financeiro');
    expect(cb).toHaveBeenCalledTimes(1);
    expect(cb).toHaveBeenCalledWith('/financeiro');

    /* Marcar a mesma secção outra vez não é troca. */
    vaiPara('/financeiro');
    expect(cb).toHaveBeenCalledTimes(1);

    parar();
    vaiPara('/vendas');
    expect(cb).toHaveBeenCalledTimes(1);
  });

  it('observar também apanha o voltar do browser (popstate)', () => {
    const cb = vi.fn();
    const parar = S.observar(cb);
    window.dispatchEvent(new window.Event('popstate'));
    expect(cb).not.toHaveBeenCalled();

    window.history.pushState({}, '', '/pecuaria');
    expect(cb).toHaveBeenCalledTimes(1);
    parar();
  });

  it('observar embrulha o pushState UMA vez só', () => {
    /* Um segundo embrulho por cima do primeiro chamaria o callback duas vezes
       por navegação — e o dock desenharia a conversa duas vezes. */
    S.observar(function () {});
    const primeiro = window.history.pushState;
    S.observar(function () {});
    expect(window.history.pushState).toBe(primeiro);
  });

  it('carregar duas vezes NAO cria duas lojas', () => {
    /* MEDIDO 2026-10-10: este ficheiro é carregado por dois caminhos com duas
       URLs — o `ia_dock.html` importa-o estaticamente e o loader
       dinamicamente com `?v=`. Duas URLs são dois módulos, e dois módulos são
       duas execuções desta IIFE. A segunda fazia `window.IaSessoes = api` por
       cima da primeira, e o observador registado pela primeira ficava órfão:
       a troca de secção funcionava até alguém abrir a barra. */
    const primeira = window.IaSessoes;
    carrega();
    expect(window.IaSessoes).toBe(primeira);
  });

  it('dois ouvintes sao avisados os dois', () => {
    /* Um histórico que só funciona para quem se registou primeiro é um
       histórico que funciona na demonstração. */
    const a = vi.fn();
    const b = vi.fn();
    const pararA = S.observar(a);
    const pararB = S.observar(b);
    vaiPara('/financeiro');
    expect(a).toHaveBeenCalledWith('/financeiro');
    expect(b).toHaveBeenCalledWith('/financeiro');
    pararA();
    pararB();
  });

  it('um ouvinte que rebenta nao impede os outros', () => {
    const bom = vi.fn();
    S.observar(function () {
      throw new Error('rebentei');
    });
    S.observar(bom);
    expect(() => vaiPara('/vendas')).not.toThrow();
    expect(bom).toHaveBeenCalledWith('/vendas');
  });

  /* ── A QUOTA ──────────────────────────────────────────────────────────── */

  it('localStorage cheio não rebenta a conversa', () => {
    /* Modo privado ou quota: `setItem` atira. Perder o histórico é melhor do
       que deixar quem está a falar com a IA sem resposta. */
    const original = window.localStorage.setItem;
    window.localStorage.setItem = () => {
      throw new Error('QuotaExceededError');
    };
    expect(() => S.guardar([{ role: 'user', content: 'ureia' }])).not.toThrow();
    window.localStorage.setItem = original;
  });

  it('localStorage com lixo devolve lista vazia, não uma excepção', () => {
    window.localStorage.setItem(S.chave(), '{isto nao e json');
    expect(S.listar()).toEqual([]);
  });
});
