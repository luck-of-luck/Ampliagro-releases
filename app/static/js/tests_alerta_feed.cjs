// =============================================================================
// tests_alerta_feed.cjs — a central de avisos do produtor.
//
// A REGRA DE OURO DESTE ARQUIVO:
//
//   O PRODUTOR SEMPRE VÊ O AVISO, E NUNCA VÊ O MESMO AVISO DUAS VEZES.
//
// E HÁ UMA SEGUNDA, MAIS SOBRIA:
//
//   NADA DE TEXTO QUE VEM DO MODELO VIRA HTML.
//
// A `mensagem` de um alerta pode ter sido escrita pelo SmolLM2 rodando no
// navegador do produtor. Isso a torna texto não-confiável na mesma medida que
// um comentário de stranger. Se um dia alguém trocar `textContent` por
// `innerHTML` aqui, o resultado não é um feed bonito: é XSS armazenado,
// disparado no login do produtor, no contexto da sessão dele, com o CSRF token
// à mão. Por isso o teste de `montarCard` passa uma mensagem com `<script>` e
// exige que ela CHEGUE como texto — não que o DOM a interprete.
//
// Sem DOM, sem relógio, sem rede: tudo entra por parâmetro, como em
// `tests_proativo.cjs`. Cartaz de aviso é código que só quebra em produção, na
// tela de quem está perdendo dinheiro.
// =============================================================================

const fs = require('fs');
const path = require('path');

const src = path.join(__dirname, 'ia-local', 'alerta-feed.js');
let ok = 0,
  falhas = 0;

function eq(a, b, msg) {
  if (a === b) {
    ok++;
  } else {
    falhas++;
    console.log(`  FALHOU  ${msg}\n          esperado: ${JSON.stringify(b)}\n          obtido:   ${JSON.stringify(a)}`);
  }
}
function truthy(v, msg) {
  eq(!!v, true, msg);
}

// --- o que o Node sabe ler de um modulo ES, sem executar o bootstrap ---------
// O arquivo importa `csrf-utils` e chama `document` no fim. Em vez de reescrever
// o modulo inteiro (o que testaria uma copia, e nao o arquivo), removemos a
// importacao e a linha do bootstrap, e avaliamos o resto como um modulo.
function carregarFeed() {
  let codigo = fs.readFileSync(src, 'utf8');
  codigo = codigo.replace(/^import .*csrf-utils.*$/m, 'const getCsrfToken = () => "";');
  codigo = codigo.replace(/if \(typeof document !== 'undefined'\)[\s\S]*$/, '');
  codigo = codigo.replace(/^export /gm, '');
  const nomes = [
    'classificarAlerta',
    'deveMostrar',
    'linhasDoCard',
    'montarCard',
    'criarFeed',
    'DURACAO_MS',
  ];
  const f = new Function(`${codigo}\nreturn {${nomes.join(',')}};`);
  return f();
}

const M = carregarFeed();

const CHUVA = {
  id: 7,
  titulo: 'Chuva pode lavar a aplicacao',
  mensagem: '40 mm previstos contra a tarefa de fertilizante.',
  nivel: 0,
  origem: 'llm',
  propriedade: 'Fazenda Sorriso',
  estado: 'novo',
  evidencia: {
    chuva: { mm: 40, prob: 85 },
    tarefa: { descricao: 'Aplicar fertilizante no talhao 4', dia: '2026-09-28' },
    limiar_mm: 10,
  },
};

// =============================================================================
console.log('\n== classificarAlerta: a ponte entre o int do banco e a tela ==');
// =============================================================================
{
  const c = M.classificarAlerta({ nivel: 0 });
  eq(c.nivel, 0, 'nivel 0 e critico');
  eq(c.tom, 'critico', 'tom critico');
  eq(c.urgente, true, 'critico e urgente');
  eq(c.duracaoMs, null, 'CRITICO NAO SOME SOZINHO: um aviso de chuva que expira sozinho e um aviso perdido');
}
{
  const c = M.classificarAlerta({ nivel: 1 });
  eq(c.tom, 'atencao', 'nivel 1 e atencao');
  eq(c.urgente, false, 'atencao nao e urgente');
  truthy(c.duracaoMs > 0, 'atencao some sozinha');
}
{
  const c = M.classificarAlerta({ nivel: 2 });
  eq(c.tom, 'informativo', 'nivel 2 e informativo');
  truthy(c.duracaoMs > 0, 'informativo some');
}
{
  // O banco guarda int; quase todo o resto do Ampliagro usa string. A ponte fica
  // num lugar so. Um "0" perdido num template so falha em producao.
  const c = M.classificarAlerta({ nivel: "0" });
  eq(c.tom, 'critico', 'nivel em string ainda vira critico');
  eq(c.urgente, true, 'string "0" ainda e urgente');
}
{
  const c = M.classificarAlerta({});
  eq(c.nivel, 1, 'sem nivel e atencao, nao critico (falhar para o lado seguro)');
  eq(c.tom, 'atencao', 'sem nivel assume atencao');
}
{
  eq(M.classificarAlerta({ origem: 'llm' }).doModelo, true, 'llm e marcado como do modelo');
  eq(M.classificarAlerta({ origem: 'regra' }).doModelo, false, 'regra NAO e do modelo');
  eq(M.classificarAlerta({ origem: 'LLM' }).doModelo, true, 'origem em caixa alta ainda conta');
}
{
  // O aviso precisa DIZER que veio do modelo. O flag `doModelo` e' o que o
  // `linhasDoCard` usa para escrever isso na tela.
  const { linhas } = M.linhasDoCard({ id: 1, titulo: 'x', nivel: 2, origem: 'llm' });
  const tom = linhas.find((l) => l.tipo === 'tom');
  truthy(tom && tom.texto.includes('modelo'), 'o produtor ve que quem falou foi o modelo');
}
{
  const { linhas } = M.linhasDoCard({ id: 1, titulo: 'x', nivel: 2, origem: 'regra' });
  const tom = linhas.find((l) => l.tipo === 'tom');
  truthy(tom && !tom.texto.includes('modelo'), 'regra fixa NAO se disfarca de modelo');
}

// =============================================================================
console.log('\n== o aviso traz o RACIOCINIO, nao so a ordem ==');
// =============================================================================
{
  const { linhas } = M.linhasDoCard(CHUVA);
  const texto = linhas.map((l) => l.texto).join(' | ');
  truthy(texto.includes('40 mm'), 'o numero da chuva aparece');
  truthy(texto.includes('85%'), 'a probabilidade aparece');
  truthy(texto.includes('Aplicar fertilizante'), 'a tarefa aparece');
  truthy(texto.includes('2026-09-28'), 'o dia aparece');
  truthy(texto.includes('limiar 10 mm'), 'o limiar aparece — o produtor precisa ver onde foi a conta');
}
{
  const { linhas } = M.linhasDoCard({ id: 1, titulo: 'Sem evidencia', nivel: 1 });
  truthy(linhas.some((l) => l.tipo === 'evidencia') === false, 'sem evidencia, nao inventa linha de evidencia');
  truthy(linhas.some((l) => l.tipo === 'titulo'), 'o titulo sempre aparece');
}
{
  // A evidencia vem do Decimal do SQLite. Se o numero chegar como texto, isto
  // quebra — e o produtor ve "chuva prevista null mm".
  const { linhas } = M.linhasDoCard({
    id: 1, titulo: 'x', nivel: 1,
    evidencia: { chuva: { mm: 0, prob: 0 } },
  });
  const ev = linhas.find((l) => l.tipo === 'evidencia');
  truthy(ev, 'mm=0 ainda produz linha de evidencia (zero e um numero valido)');
  truthy(ev.texto.includes('0 mm'), 'zero aparece como 0, nao como ausente');
}

// =============================================================================
console.log('\n== nunca o mesmo aviso duas vezes ==');
// =============================================================================
{
  eq(M.deveMostrar({ id: 1, estado: 'novo' }, []), true, 'primeira vez mostra');
  eq(M.deveMostrar({ id: 1, estado: 'novo' }, [1]), false, 'ja mostrado nao repete');
  eq(M.deveMostrar({ id: 2, estado: 'novo' }, [1]), true, 'outro id mostra');
  eq(M.deveMostrar({ id: 1, estado: 'visto' }, []), false, 'ja visto nao volta');
  eq(M.deveMostrar({ id: 1, estado: 'ignorado' }, []), false, 'ignorado nao volta');
  eq(M.deveMostrar(null, []), false, 'nada nao mostra');
  eq(M.deveMostrar({}, []), false, 'sem id nao mostra');
}

// =============================================================================
console.log('\n== montarCard: texto do modelo NUNCA vira HTML ==');
// =============================================================================
function docFalso() {
  const no = {
    className: '', dataset: {}, attrs: {}, filhos: [], listeners: {},
    setAttribute(k, v) { this.attrs[k] = v; },
    appendChild(f) { this.filhos.push(f); return f; },
    addEventListener(ev, fn) { this.listeners[ev] = fn; },
  };
  return {
    createElement() { return Object.create(no, { filhos: { value: [] } }); },
  };
}
{
  const ATAQUE = '<img src=x onerror="alert(1)">';
  const d = docFalso();
  const el = M.montarCard({ ...CHUVA, titulo: ATAQUE, mensagem: `<b>${ATAQUE}</b>` }, { doc: d });

  eq(el.className.includes('<'), false, 'o titulo malicioso nao entrou no className');
  eq(el.filhos.length > 0, true, 'os filhos foram criados');

  // A prova de que a mensagem chegou como TEXTO: existe `textContent` com a
  // string crua, e nao existe `innerHTML` em lugar nenhum. Se alguem trocar por
  // innerHTML, este teste falha — que e' o ponto dele existir.
  let usouTextContent = false;
  let algumValorCru = false;
  let usouInnerHtml = false;
  for (const f of el.filhos) {
    if (Object.prototype.hasOwnProperty.call(f, 'textContent')) {
      usouTextContent = true;
      if (typeof f.textContent === 'string' && f.textContent.includes('<img')) algumValorCru = true;
    }
    if (Object.prototype.hasOwnProperty.call(f, 'innerHTML')) usouInnerHtml = true;
  }
  eq(usouTextContent, true, 'o texto entrou por textContent');
  eq(usouInnerHtml, false, 'NENHUM elemento recebeu innerHTML');
  eq(algumValorCru, true, 'a string maliciosa chegou intacta como texto, para ser exibida e nao executada');
}
{
  const d = docFalso();
  const el = M.montarCard({ ...CHUVA, nivel: 0 }, { doc: d });
  eq(el.attrs.role, 'alert', 'critico e role=alert');
  eq(el.attrs['aria-live'], 'assertive', 'critico interrompe o leitor de tela');
}
{
  const d = docFalso();
  const el = M.montarCard({ ...CHUVA, nivel: 2 }, { doc: d });
  eq(el.attrs.role, 'status', 'informativo e role=status');
  eq(el.attrs['aria-live'], undefined, 'informativo nao interrompe: seria ruido');
}
{
  const d = docFalso();
  const el = M.montarCard({ ...CHUVA, nivel: 0 }, { doc: d });
  eq(el.dataset.duracaoMs, 'persistente', 'o critico e marcado como persistente');
}
{
  const d = docFalso();
  const el = M.montarCard({ ...CHUVA, nivel: 1 }, { doc: d });
  eq(el.dataset.duracaoMs, String(M.DURACAO_MS[1]), 'o prazo de sumir vem do dominio, nao de um 3000 no listener');
}
{
  let clicado = null;
  const d = docFalso();
  const el = M.montarCard(CHUVA, { doc: d, aoConfirmar: (a) => { clicado = a.id; } });
  const botao = el.filhos[el.filhos.length - 1];
  eq(typeof botao.listeners.click, 'function', 'o botao tem acao');
  botao.listeners.click();
  eq(clicado, 7, 'clicar confirma o alerta certo');
}

// =============================================================================
console.log('\n== o ciclo: sem rede lenta, sem tempestade de avisos ==');
// =============================================================================
(async () => {
  {
    let agendado = 0;
    const inseridos = [];
    const feed = M.criarFeed({
      buscar: async () => ({ alertas: [CHUVA, { ...CHUVA, id: 8, nivel: 1 }] }),
      aoConfirmar: () => {},
      montar: (a) => ({ id: a.id }),
      inserir: (c) => inseridos.push(c),
      ler: () => [],
      gravar: () => {},
      agendar: () => { agendado++; },
    });
    await feed.passada();
    eq(inseridos.length, 2, 'os dois alertas entraram');
    eq(agendado, 1, 'reagendou uma vez');

    await feed.passada();
    eq(inseridos.length, 2, 'a segunda passagem NAO repete o que ja mostrou');
    eq(agendado, 2, 'continua sondando');
  }

  {
    // O teto: 40 alertas de uma vez nao viram 40 cartazes. Uma tela com 40
    // cartazes nao e uma central de avisos, e' um muro que o produtor aprende a
    // ignorar — e ai nenhum aviso chega.
    const muitos = Array.from({ length: 40 }, (_, i) => ({ id: 100 + i, nivel: 0 }));
    const dentro = [];
    await M.criarFeed({
      buscar: async () => ({ alertas: muitos }),
      aoConfirmar: () => {},
      montar: (a) => a.id,
      inserir: (c) => dentro.push(c),
      ler: () => [],
      gravar: () => {},
      agendar: () => {},
    }).passada();
    eq(dentro.length, 3, 'no maximo 3 cartazes por passada');
  }

  {
    // Falha de rede: ouve, segue, nao grita com o produtor. Um cartaz de
    // "nao consegui carregar seus avisos" seria a terceira pior coisa que
    // poderia aparecer na tela do produtor.
    const depois = [];
    let reagendou = false;
    await M.criarFeed({
      buscar: async () => { throw new Error('rede caiu'); },
      aoConfirmar: () => {},
      montar: (a) => a.id,
      inserir: (c) => depois.push(c),
      ler: () => [],
      gravar: () => {},
      agendar: () => { reagendou = true; },
    }).passada();
    eq(depois.length, 0, 'rede caiu: nenhum cartaz, nenhum erro na tela');
    eq(reagendou, true, 'rede caiu e ainda assim continua sondando');
  }

  {
    // Parar precisa parar de verdade: senao o `setTimeout` ja agendado acorda e
    // o feed volta a fazer fetch numa pagina que o produtor fechou.
    let parou = false;
    const f = M.criarFeed({
      buscar: async () => ({ alertas: [CHUVA] }),
      aoConfirmar: () => {},
      montar: (a) => a,
      inserir: () => {},
      ler: () => [],
      gravar: () => {},
      agendar: () => { parou = true; },
    });
    f.parar();
    await f.passada();
    eq(parou, false, 'depois de parar(), nao reagenda mais nada');
  }

  console.log(`\n${falhas === 0 ? 'OK' : 'FALHOU'}: ${ok} ok, ${falhas} falha(s)`);
  // Sem isto, um `falhas > 0` aqui nao quebraria o build: o Node sai com 0 e o
  // pre-commit lê "verde" num arquivo que provou o contrario. Uma suite de teste
  // que nao pode falhar e um comentario com `assert` no meio.
  process.exit(falhas === 0 ? 0 : 1);
})();
