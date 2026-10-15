import { test, expect } from '@playwright/test';

/* O CHAMADO AMPLIA, NO BROWSER A VERDADEIRO.
 *
 * Porque este ficheiro existe, e o que ele prova que os outros não provam
 * ========================================================================
 * Os testes `.cjs` e os `vitest` correm num DOM de mentira ou sem CSS. Provam a
 * aritmética, a autorização e a proveniência. NÃO provam duas coisas:
 *
 *   1. que o browser PINTA o que o módulo desenhou;
 *   2. que um elemento desenhado é CLICÁVEL.
 *
 * A segunda é o que estes testes nasceram para apanhar. O botão "Pedir
 * alteração" estava no DOM, o Playwright clicava por seletor sem problema, os
 * testes passavam — e um utilizador a carregar nele acertava no `grid` de outro
 * widget, porque o painel montava a peça em `#content`, por baixo da matriz
 * bento (`position:absolute !important`).
 *
 * Um botão que aceita o clique e não faz nada é pior do que um botão que não
 * existe: o primeiro promete ao produtor que ele pode mudar a peça.
 *
 * O QUE ESTE FICHEIRO AFIRMA
 * ==========================
 * Que a peça aparece DENTRO do widget da matriz, que o seu botão chega ao
 * `iaDockSend` com um clique de rato, e que sobrevive a um redesenho do painel.
 * A última é a que o browser ganhou por-alone: o `renderWidgetsOnMatrix` apaga
 * e recria todos os `.bento-block`, e sem o ponto de retorno a peça
 * desaparecia a cada render.
 */

const ZONA = 'chamado-amplia';
const WIDGET = '#widget-chamado-amplia';

/* ESTE FICHEIRO É SÉRIO, E POR UMA RAZÃO ESTRUTURAL
 *
 * Há UMA peça por produtor — é uma `UniqueConstraint` no banco, não uma
 * preferência. E cada teste deste ficheiro escreve a peça do MESMO produtor
 * (`demo`), para poder afirmar que o que está no ecrã é o que ele mandou.
 *
 * O `playwright.config.ts` corre com `fullyParallel: true`, que distribui os
 * testes por vários workers. Com uma peça só, dois testes a escrever ao mesmo
 * tempo estão um a reescrever o que o outro acabou de pôr: o `criarPeca` de um
 * deixa de ver o seu texto na leitura, e a falha aparece no `toContainText` mais
 * abaixo — a yards do sítio onde o problema está, que é a concorrência.
 *
 * `serial` declara essa dependência em vez de a esconder. A alternativa era
 * `workers: 1` no config partilhado, que tornaria a suite de toda mais lenta por
 * causa de um ficheiro. Um ficheiro declara o que ele precisa; o config declara
 * o que o repositório precisa.
 */
test.describe.configure({ mode: 'serial' });

/** Cria a peça pela sessão do browser, e devolve o JSON do servidor.
 *
 *  O `ok` do envelope é o `ok` da intent, mas não chega: o `ok` é uma PROMESSA
 *  do servidor, e o que interessa é o banco. Por isso esta função volta a ler e
 *  compara, em duas listas — e a separação entre elas é a regra inteira:
 *
 *  - `temDeVoltar`: o que é ESTRUTURA (tipo, título, colunas, texto). A peça
 *    guarda a receita, e a receita tem de sobreviver.
 *  - `naoTemDeVoltar`: o que está dentro de `linhas`. São os números que a IA
 *    escreveu, e a regra é NÃO os guardar — nem no banco, nem na resposta.
 *
 *  A primeira versão metia os dois na mesma lista e exigia que tudo voltasse.
 *  Ou seja: o teste reprovava o sistema por estar a funcionar. Um teste que
 *  exige o que a especificação proíbe não está a testar a especificação.
 */
async function criarPeca(page: any, blocos: unknown[]) {
  const r = await page.evaluate(
    async (blocos: unknown[]) => {
      const res = await fetch('/api/amplia/exec/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] || '',
        },
        body: JSON.stringify({
          tool: 'amplia_chamado_criar',
          args: { blocos, confirm: true },
        }),
      });
      const escrito = await res.json();
      const lido = await fetch('/api/amplia/palco/chamado/', { cache: 'no-store' }).then(
        (x) => x.json(),
      );
      return { escrito, lido };
    },
    blocos,
  );

  expect(
    r.escrito && r.escrito.ok,
    `a peça tem de ser escrita: ${JSON.stringify(r.escrito).slice(0, 400)}`,
  ).toBe(true);

  /* As `\"` do JSON são DESESCAPADAS antes de comparar: um título com
   * `onerror="..."` volta como `onerror=\"...\"`, e uma comparação de substring
   * não encontra — o teste falhava com um título perfeitamente guardado. */
  const lidoBruto = JSON.stringify(r.lido).replace(/\\"/g, '"');

  const temDeVoltar = new Set<string>();
  const naoTemDeVoltar = new Set<string>();

  const recolhe = (v: unknown, dentroDeLinhas = false) => {
    if (typeof v === 'string') {
      const s = v.trim();
      if (s.length <= 4) return;
      (dentroDeLinhas ? naoTemDeVoltar : temDeVoltar).add(s);
    } else if (Array.isArray(v)) {
      v.forEach((x) => recolhe(x, dentroDeLinhas));
    } else if (v && typeof v === 'object') {
      for (const [k, x] of Object.entries(v)) {
        recolhe(x, dentroDeLinhas || k === 'linhas');
      }
    }
  };
  recolhe(blocos);

  const emFalta = [...temDeVoltar].filter((s) => !lidoBruto.includes(s));
  expect(
    emFalta,
    [
      `a estrutura da peça não sobreviveu: ${JSON.stringify(emFalta).slice(0, 300)}`,
      `envelope: ${JSON.stringify(r.escrito).slice(0, 400)}`,
    ].join('\n  '),
  ).toEqual([]);

  const vazados = [...naoTemDeVoltar].filter((s) => lidoBruto.includes(s));
  expect(
    vazados,
    `números que a IA escreveu e que NÃO podem chegar ao cliente: ${JSON.stringify(vazados).slice(0, 300)}`,
  ).toEqual([]);

  return r;
}

/** Entra como `demo` e CONFIRMA que entrou.
 *
 * Com uma tentativa a mais, e o motivo escrito.
 *
 * O `playwright.config.ts` corre `fullyParallel: true`, e a suite toda escreve
 * na mesma base SQLite ao mesmo tempo. Nessas condições um login pode não
 * completar — e a falha aparece como "o bloco não tem a marca", mil linhas
 * abaixo e do lado errado do problema.
 *
 * Uma repetição não esconde um login que está partido: se o segundo também
 * falhar, o teste continua a falhar, e agora com a mensagem certa. O que deixa
 * de acontecer é um verde-que-não-é, e um vermelho que aponta para o sítio
 * errado.
 */
async function entrar(page: any) {
  for (const tentativa of [1, 2]) {
    await page.goto('/login/');
    await page.fill('input[name="usuario"]', 'demo');
    await page.fill('input[name="senha"]', 'demo123');
    await page.click('#btnEntrar');

    /* O painel responde 200 e traz o dock. A página de login também traz
     * "Entrar", por isso o que se procura é a ausência de login. */
    const entrou = await page
      .waitForURL(/\/(\/|$)/, { timeout: 8000 })
      .then(() => page.locator('#ia-dock').count())
      .then((n: number) => n > 0)
      .catch(() => false);

    if (entrou) return;
    if (tentativa === 2) {
      throw new Error(
        'o login do demo não completou duas vezes — o painel não tem #ia-dock ' +
          `e a URL ficou em ${page.url()}`,
      );
    }
  }
}

/** Vai ao painel e espera que o widget do Chamado esteja pintado. */
async function abrirPainel(page: any) {
  await page.goto('/');
  await page.waitForSelector(WIDGET, { timeout: 20000 });
  /* A peça é desenhada depois da matriz, dentro do `.then` do fetch. */
  await page.waitForFunction(
    () => {
      const c = document.querySelector('#widget-chamado-amplia .widget-content');
      return !!(c && c.getAttribute('data-chamado-pronto') === '1');
    },
    { timeout: 20000 },
  );
}

test.describe('Chamado Amplia — no widget da matriz', () => {
  test.beforeEach(async ({ page }) => {
    await entrar(page);
    await page.waitForLoadState('networkidle');
  });

  test('a peça aparece dentro do widget, e não por baixo da matriz', async ({
    page,
  }) => {
    await criarPeca(page, [{ tipo: 'texto', texto: 'A safra fechou acima do previsto.' }]);
    await abrirPainel(page);

    /* O widget existe na matriz... */
    const widget = page.locator(WIDGET);
    await expect(widget).toBeVisible();
    await expect(widget).toHaveClass(/bento-block/);

    /* ...e a peça está DENTRO dele. Este é o teste que teria falhado antes:
     * a peça desenhava-se em `#content`, que é um IRMÃO da matriz, e por isso
     * ficava por baixo dela. */
    await expect(widget.locator('.amplia-chamado-cab')).toHaveCount(1);
    await expect(widget).toContainText('A safra fechou acima do previsto.');

    /* E o que diz estar por baixo não existe. Se alguém voltar a montar em
     * `#content`, isto acende. */
    const foraDaMatriz = await page.evaluate(() => {
const h = document.getElementById('amplia-chamado-host');
          const widget = document.getElementById('widget-chamado-amplia');
          // `getElementById` devolve `Element | null`, e o `strict` recusa
          // `.contains()` sem guarda. Um `as Element` seria mais curto e
          // mentiroso: se o widget nao existe, a pergunta e' "o host esta
          // dentro do widget?" — e a resposta correta e que nao esta.
          return !!(h && widget && !widget.contains(h));
    });
    expect(foraDaMatriz, 'a peça não pode ser criada fora do widget').toBe(false);
  });

  test('o botão de alterar existe, é clicável e chega ao iaDockSend', async ({
    page,
  }) => {
    await criarPeca(page, [{ tipo: 'texto', texto: 'Clique.' }]);
    await abrirPainel(page);

    /* `data-accao`, com "c" — é assim que o `chamado-amplia.js` escreve. A
     * primeira versão deste teste procurava `data-acao` e falhou com uma
     * contagem ZERO, que é exactamente o que uma barra vazia daria. */
    const botao = page.locator(`${WIDGET} [data-accao="alterar"]`);
    await expect(botao).toHaveCount(1);

    /* Espia-se o método E o input do dock.
     *
     * `iaDockSend` não recebe argumentos: por desenho, o `pedirChat` escreve a
     * pergunta em `#ia-dock-input` e chama o dock, que lê o seu próprio input.
     * Um teste que esperava o texto como argumento estava a testar um método que
     * não existe com a assinatura que eu imaginei — e o "Received: undefined"
     * dizia mais sobre o teste do que sobre o produto. */
    await page.evaluate(() => {
      (window as any).__chamadas = [];
      const original = (window as any).iaDockSend;
      (window as any).iaDockSend = function (...args: unknown[]) {
        (window as any).__chamadas.push({
          args: args,
          input: (document.getElementById('ia-dock-input') as HTMLInputElement)?.value,
        });
        return original.apply(this, args as []);
      };
      (window as any).prompt = () => 'acrescenta uma tabela de despesas';
    });

    /* `click()` normal, sem `force`. `force` saltaria a verificação de que o
     * ponto do rato chega ao elemento — que é exactamente o que se está a
     * testar. O `.click()` simples FAZ essa verificação: se algo estiver por
     * cima, falha. */
    await botao.click();
    await page.waitForTimeout(400);

    const chamadas = await page.evaluate(() => (window as any).__chamadas);
    expect(chamadas.length, 'o clique tem de chegar ao iaDockSend').toBe(1);
    expect(chamadas[0].input, 'a pergunta tem de estar no input do dock').toContain(
      'despesas',
    );
  });

  test('a peça sobrevive a um redesenho do painel', async ({ page }) => {
    await criarPeca(page, [{ tipo: 'texto', texto: 'Antes do redesenho.' }]);
    await abrirPainel(page);
    await expect(page.locator(WIDGET)).toContainText('Antes do redesenho.');

    /* Chamar o render é o que um clique no "atualizar painel" ou a chegada de
     * dados novos faz. E apaga TODOS os `.bento-block`, incluindo o nosso. */
    const redesenhou = await page.evaluate(() => {
      const w = (window as any).widgets || {};
      if (!w['chamado-amplia']) return 'sem-config';
      if (typeof (window as any).renderWidgetsOnMatrix !== 'function') return 'sem-funcao';
      (window as any).renderWidgetsOnMatrix();
      return 'ok';
    });
    expect(redesenhou, `o redesenho tem de acontecer: ${redesenhou}`).toBe('ok');

    /* O contentor novo não tem o que lá estava dentro — e é para isso que o
     * `aposRenderWidgets` existe. */
    await page.waitForTimeout(700);

    /* O estado, para quando a falha for aqui dentro. A mensagem de um
     * `toHaveCount(1)` que dá 0 não diz NADA de útil: não diz se o contentor
     * desapareceu, se ficou sem marcar, ou se ficou marcado e vazio — e essas
     * são três defeitos diferentes em três sítios diferentes. */
    const estado = await page.evaluate(() => {
      const widget = document.getElementById('widget-chamado-amplia');
      const slot = widget ? widget.querySelector('.widget-content') : null;
      return {
        widgetExiste: !!widget,
        marcado: slot ? slot.getAttribute('data-chamado-pronto') : null,
        temPeca: !!document.querySelector('#widget-chamado-amplia .amplia-chamado-cab'),
        ganchoInstalado: !!(window as any).renderWidgetsOnMatrix?.__chamado,
        noWindowWidgets: !!(window as any).widgets?.['chamado-amplia'],
        texto: widget ? widget.textContent?.slice(0, 90) : null,
      };
    });

    await expect(
      page.locator(`${WIDGET} .amplia-chamado-cab`),
      `estado depois do redesenho: ${JSON.stringify(estado)}`,
    ).toHaveCount(1);
    await expect(page.locator(WIDGET)).toContainText('Antes do redesenho.');
  });

  test('o bloco sem_dado aparece MARCADO e nunca como 0', async ({ page }) => {
    await criarPeca(page, [
      {
        tipo: 'tabela',
        titulo: 'Despesas escritas pela IA',
        colunas: ['categoria', 'valor'],
        linhas: [['Adubo', '1.234,56']],
      },
    ]);
    await abrirPainel(page);

    const bloco = page.locator(`${WIDGET} [data-bloco]`).first();
    await expect(bloco).toBeVisible();

    // A MARCA. É o carimbo que diz ao produtor que isto não é uma medição.
    await expect(bloco.locator('.amc-marca')).toContainText('sem dado');

    // E o NÚMERO QUE A IA ESCREVEU NÃO ESTÁ LÁ.
    await expect(bloco).not.toContainText('1.234,56');

    // E há um motivo. Um bloco vazio sem explicação obriga o produtor a
    // concluir que o sistema não funciona.
    await expect(bloco).toContainText(/fonte|descartados/i);
  });

  test('o aviso da peça diz o que não tem apoio', async ({ page }) => {
    await criarPeca(page, [
      { tipo: 'tabela', titulo: 'Despesas', fonte: 'despesas-por-categoria' },
      { tipo: 'texto', texto: 'A margem caiu para 18% este ano.' },
    ]);
    await abrirPainel(page);

    const aviso = page.locator(`${WIDGET} .amplia-chamado-aviso`);
    await expect(aviso).toBeVisible();
    await expect(aviso).toContainText('18');
  });

  test('um título com HTML é TEXTO, não é executado', async ({ page }) => {
    const erros: string[] = [];
    page.on('pageerror', (e) => erros.push(String(e)));

    await criarPeca(page, [
      {
        tipo: 'texto',
        titulo: '<img src=x onerror="window.__XSS=1">',
        texto: 'Comando de teste.',
      },
    ]);
    await abrirPainel(page);

    // Aparece COMO TEXTO. Um título que se lê é a prova de que é texto.
    await expect(page.locator(WIDGET)).toContainText('<img src=x');
    // E NADA foi executado: nem o atributo, nem a variável.
    expect(await page.evaluate(() => (window as any).__XSS)).toBeUndefined();
    expect(await page.locator(`${WIDGET} img`).count()).toBe(0);
    expect(erros).toEqual([]);
  });

  test('a peça sobrevive ao redimensionar e não é tapada', async ({ page }) => {
    await criarPeca(page, [{ tipo: 'texto', texto: 'Legível.' }]);
    await abrirPainel(page);

    /* `elementFromPoint` é o que o RATO alcança. Se o canto da peça não der
     * a própria peça, há algo por cima — e era exactamente esse o bug. */
    const tapado = await page.evaluate((sel) => {
      const bloco = document.querySelector(sel + ' .amplia-chamado-cab');
      if (!bloco) return { erro: 'sem peca' };
      const r = bloco.getBoundingClientRect();
      const alvo = document.elementFromPoint(r.left + 4, r.top + 4);
      return {
        quem: alvo ? alvo.tagName + '.' + String(alvo.className || '') : null,
        eADela: bloco.contains(alvo) || bloco === alvo,
      };
    }, WIDGET);

    expect(tapado.erro).toBeUndefined();
    expect(tapado.eADela, `a peça esta tapada por ${tapado.quem}`).toBe(true);

    /* E o botão continua lá depois de um resize. */
    await page.setViewportSize({ width: 1100, height: 700 });
    await page.waitForTimeout(400);
    await expect(page.locator(`${WIDGET} [data-accao="alterar"]`)).toHaveCount(1);
  });

  test('o preset do Chamado existe na widget-bar', async ({ page }) => {
    await abrirPainel(page);

    /* `ZONA` passa como ARGUMENTO. Uma `const` do Node não existe dentro de
     * `page.evaluate` — a função corre no browser. */
    const existe = await page.evaluate((zona) => {
      const w = window as any;
      if (!w.WidgetIntelligence) return false;
      if (typeof w.WidgetIntelligence.getPresets !== 'function') return false;
      const presets = w.WidgetIntelligence.getPresets();
      if (!Array.isArray(presets)) return false;
      return presets.some((p: { id: string }) => p && p.id === zona);
    }, ZONA);

    expect(existe).toBe(true);
  });
});

test.describe('Chamado Amplia — a API', () => {
  test.beforeEach(async ({ page }) => {
    await entrar(page);
    await page.waitForLoadState('networkidle');
  });

  test('a API responde e a peça é do produtor', async ({ page }) => {
    await criarPeca(page, [{ tipo: 'texto', texto: 'Tenancy.' }]);
    const d = await page.evaluate(async () => {
      const r = await fetch('/api/amplia/palco/chamado/');
      return r.json();
    });
    expect(d.ok).toBe(true);
    expect(d.chamado.existe).toBe(true);
    expect(d.chamado.preset).toBe(ZONA);
    // E a zona de escrita é anunciada, para o JS não montar um botão no sítio
    // errado.
    expect(d.zona_escrita.preset).toBe(ZONA);
  });

  test('o número que a IA escreveu não chega ao cliente', async ({ page }) => {
    await criarPeca(page, [
      {
        tipo: 'tabela',
        titulo: 'Despesas escritas pela IA',
        colunas: ['categoria', 'valor'],
        linhas: [['Adubo', '1.234,56']],
      },
    ]);
    const d = await page.evaluate(async () => {
      const r = await fetch('/api/amplia/palco/chamado/');
      return r.json();
    });

    /* PRIMEIRO: a peça existe mesmo, com a tabela que este teste mandou. Sem
     * esta verificação, o teste seguinte passa por VAZIO — uma peça que nunca
     * foi criada também não contém "1.234,56", e isso não prova que a regra
     * funciona, prova que o pedido não chegou lá. */
    const bloco = (d.chamado.blocos || []).find(
      (b: { config: { titulo?: string } }) =>
        b.config && b.config.titulo === 'Despesas escritas pela IA',
    );
    expect(bloco, 'a peça tem a tabela que o teste mandou').toBeTruthy();

    /* A REGRA: "a IA escolhe a fonte, o servidor escreve os números". */
    const bruto = JSON.stringify(d);
    expect(bruto).not.toContain('1.234,56');

    /* E o contador diz quantos foram. `numeros_sem_apoio` é outra coisa: é
     * para os números que FICAM sem fonte (um texto que afirma "caiu 18%").
     * Confundir as duas daria um teste que passa pelo campo errado. */
    expect(d.chamado.numeros_descartados).toBeGreaterThan(0);

    /* E o bloco fica marcado como sem dado, em vez de vir vazio. */
    expect(d.chamado.sem_dado.length).toBeGreaterThan(0);
  });
});
