// =============================================================================
// alerta-feed.js — a central de avisos do produtor.
//
// A OUTRA METADE DO MOTOR
// =======================
// `proativo-local.js` faz o celular raciocinar. Este arquivo faz o produtor
// LER o que o motor raciocinou. Sem ele, o motor pode estar perfeito e ser
// invisível — e um motor invisível não muda a vida de ninguém.
//
// Uma decisão que define o arquivo inteiro: a mensagem do alerta PODE ter sido
// escrita por um modelo de linguagem. Isso a torna texto não-confiável na mesma
// medida que um comentário de strangers. Por isso NADA aqui usa innerHTML com
// dado que veio do servidor. Todo texto entra por `textContent`. Se alguém
// algum dia trocar isso por innerHTML, o que deixa de ser um feed de avisos
// vira um XSS armazenado, disparado no login do produtor, no contexto da sessão
// dele, com o CSRF token à mão. Não é stylistic choice; é a diferença entre um
// produto e um incidente.
//
// O QUE NÃO ESTÁ AQUI, DE PROPÓSITO
// =================================
// - Nada de WebGPU, WebLLM ou inferência. Este arquivo LÊ. Quem raciocina é o
//   `proativo-local.js`. Se este arquivo precisasse de GPU, o aviso dependeria
//   de o modelo estar carregado — e o pior momento para o produtor ficar sem
//   aviso é justamente quando o navegador está ocupado.
// - Nada de polling agressivo. O produtor que deixa a aba aberta o dia inteiro
//   não pode pagar 6 requisições por minuto para não ver mudança nenhuma.
// - Nada de som. Um aviso que assusta o produtor às 3h da manhã faz ele
//   desligar as notificações de vez, e aí não recebe mais nenhum.
//
// A REGRA DE OURO DESTE ARQUIVO:
//
//   O PRODUTOR SEMPRE VÊ O AVISO, E NUNCA VÊ O MESMO AVISO DUAS VEZES.
// =============================================================================

import { getCsrfToken } from '../csrf-utils.js';

const NS = 'amplia.alertaFeed.v1';

/** Quanto tempo o cartaz fica sozinho, por severidade. `null` = não some. */
export const DURACAO_MS = { 0: null, 1: 45_000, 2: 20_000 };

/** A primeira sondagem é quase imediata: o produtor acabou de abrir o sistema. */
export const INTERVALO_SONDAGEM_MS = 2 * 60 * 1000;

/** Sondagem com a aba escondida. Lenta, mas não zerada. */
export const INTERVALO_OCULTA_MS = 5 * 60 * 1000;

/** Teto de alertas por passagem. Uma tela com 40 cartões não é uma central. */
export const MAX_CARTES = 3;

/**
 * O que este endpoint devolve, translated para o que a tela precisa.
 *
 * `nivel` é int no banco (0/1/2) e string em quase todo o resto do Ampliagro
 * ("critical"/"warning"/"info"). A ponte fica AQUI, num lugar só, em vez de
 * espalhada por listeners e comparações — porque a alternativa é um `=== "0"`
 * perdido num template, que só falha em produção.
 */
export function classificarAlerta(alerta = {}) {
  const nivel = Number(alerta.nivel);
  const urgente = nivel === 0;
  // `in`, e nao `??`. O critico tem prazo `null` DE PROPOSITO — "nao some" e um
  // valor, e nao uma ausencia. Com `DURACAO_MS[nivel] ?? DURACAO_MS[1]` o
  // `null` era tratado como ausente e o aviso mais urgente da tela inteira
  // sumia sozinho em 45 segundos. Este e' o bug de `??` que o teste pegou, e ele
  // e' a razao de o prazo ser decidido no dominio e nao no listener.
  const duracaoMs = nivel in DURACAO_MS ? DURACAO_MS[nivel] : DURACAO_MS[1];
  return {
    nivel: Number.isFinite(nivel) ? nivel : 1,
    urgente,
    tom: nivel === 0 ? 'critico' : nivel === 2 ? 'informativo' : 'atencao',
    rotulo: nivel === 0 ? 'Crítico' : nivel === 2 ? 'Informativo' : 'Atenção',
    duracaoMs,
    // `llm` é o caminho do celular. O produtor DEVE saber quando quem falou foi
    // um modelo raciocinando e não uma regra fixa — o peso que ele dá ao
    // advice é diferente, e esconder isso seria mentir sobre a origem.
    doModelo: String(alerta.origem || '').toLowerCase() === 'llm',
  };
}

/**
 * Já mostrei este alerta nesta sessão?
 *
 * A sessão, e não o navegador inteiro, é a unidade certa: o produtor recarrega
 * a página o dia todo, e um recarregamento não pode ser um temporal de alertas
 * que ele já leu. Mas fechar e reabrir o navegador é um "de novo" — ele pode
 * ter esquecido, e o aviso de chuva de amanhã continua valendo amanhã.
 */
export function chaveSessao(agora = Date.now()) {
  return `${NS}:${Math.floor(agora / 86_400_000)}`;
}

function lerMostrados(agora = Date.now()) {
  try {
    const bruto = sessionStorage.getItem(chaveSessao(agora));
    const lista = bruto ? JSON.parse(bruto) : [];
    return Array.isArray(lista) ? lista : [];
  } catch {
    // sessionStorage lança em modo privado de alguns navegadores, e num iframe
    // sem SAMEORIGIN. Feed quebrado é pior que feed que repete um aviso.
    return [];
  }
}

function gravarMostrados(ids, agora = Date.now()) {
  try {
    sessionStorage.setItem(chaveSessao(agora), JSON.stringify(ids.slice(-200)));
  } catch {
    /* mesma decisão: degrada, não quebra */
  }
}

/**
 * O servidor NÃO confirmou que o produtor leu — desmarca o alerta.
 *
 * Existe por causa do `fetch`: ele só rejeita em falha de rede, e um 403 de
 * CSRF ou um 500 resolve-se como sucesso. Sem isto, o `catch` engolia o erro e
 * o alerta ficava marcado como visto para o resto do dia, com o
 * `IAAlertaProativo.estado` ainda em "novo" no servidor: o sino contava um
 * aviso que o produtor já tinha lido e não conseguia mais fechar.
 */
function esquecerMostrado(id, agora = Date.now()) {
  const chave = chaveSessao(agora);
  try {
    const bruto = sessionStorage.getItem(chave);
    const lista = bruto ? JSON.parse(bruto) : [];
    if (!Array.isArray(lista)) return;
    const restante = lista.filter((x) => x !== id);
    if (restante.length !== lista.length) {
      sessionStorage.setItem(chave, JSON.stringify(restante));
    }
  } catch {
    /* degrada, não quebra */
  }
}

/** Um alerta já visto nesta sessão volta a aparecer? Não. */
export function deveMostrar(alerta, jaMostrados = []) {
  if (!alerta || !alerta.id) return false;
  if (String(alerta.estado || 'novo') !== 'novo') return false;
  return !jaMostrados.includes(alerta.id);
}

/**
 * O texto do produtor: o aviso, a origem, e o RACIOCÍNIO.
 *
 * A evidência é o que separa isto de um SMS. "Vai chover" ele ignora; "chuva de
 * 40 mm, 85% de chance, contra a aplicação de fertilizante marcada para o dia
 * 28, limiar 10 mm" ele consegue decidir.
 */
export function linhasDoCard(alerta = {}) {
  const c = classificarAlerta(alerta);
  const ev = alerta.evidencia || {};
  const chuva = ev.chuva || {};
  const tarefa = ev.tarefa || {};

  const linhas = [];
  if (c.rotulo)
    linhas.push({
      tipo: 'tom',
      texto: `${c.rotulo}${c.doModelo ? ' · raciocínio do modelo' : ''}`,
    });
  if (alerta.titulo) linhas.push({ tipo: 'titulo', texto: alerta.titulo });
  if (alerta.mensagem) linhas.push({ tipo: 'mensagem', texto: alerta.mensagem });

  const fatos = [];
  if (chuva.mm != null) fatos.push(`chuva prevista ${chuva.mm} mm`);
  if (chuva.prob != null) fatos.push(`${chuva.prob}% de chance`);
  if (tarefa.descricao) fatos.push(`tarefa: ${tarefa.descricao}`);
  if (tarefa.dia) fatos.push(`dia ${tarefa.dia}`);
  if (ev.limiar_mm != null) fatos.push(`limiar ${ev.limiar_mm} mm`);
  if (fatos.length) linhas.push({ tipo: 'evidencia', texto: fatos.join(' · ') });

  if (alerta.propriedade) linhas.push({ tipo: 'prop', texto: alerta.propriedade });
  return { tom: c.tom, urgente: c.urgente, linhas };
}

/**
 * Monta o cartaz. `document` e `setTimeout` entram por parâmetro porque este
 * arquivo é testado fora do navegador — é a mesma disciplina de
 * `proativo-local.js`, e ela existe por um motivo concreto: cartaz de aviso é
 * código que só quebra em produção, na tela de quem está indo Losing money.
 */
export function montarCard(alerta, { doc = document, aoConfirmar } = {}) {
  const { tom, urgente, linhas } = linhasDoCard(alerta);
  const dur = classificarAlerta(alerta).duracaoMs;
  const el = doc.createElement('div');
  el.className = `amplia-av af-${tom}`;
  el.setAttribute('role', urgente ? 'alert' : 'status');
  if (urgente) el.setAttribute('aria-live', 'assertive');
  el.dataset.alertaId = String(alerta.id || '');
  // O cartaz sabe o próprio prazo de validade. Quem decide sumir é o DOM, mas
  // o prazo é uma decisão do DOMÍNIO: se a_policy mudar, muda aqui, e não em
  // dois lugares — o bug clássico do `3000` escrito dentro de um listener.
  if (dur == null) {
    el.dataset.duracaoMs = 'persistente';
  } else {
    el.dataset.duracaoMs = String(dur);
  }

  for (const l of linhas) {
    const p = doc.createElement('p');
    p.className = `af-l af-${l.tipo}`;
    // textContent. Sempre. Ver a nota sobre XSS no topo do arquivo.
    p.textContent = l.texto;
    el.appendChild(p);
  }

  const btn = doc.createElement('button');
  btn.type = 'button';
  btn.className = 'af-ok';
  btn.textContent = 'Entendi';
  btn.addEventListener('click', () => {
    if (typeof aoConfirmar === 'function') aoConfirmar(alerta);
  });
  el.appendChild(btn);
  return el;
}

/**
 * O ciclo. Mesma forma de `criarPoller`: tudo injetado, nada de DOM, relógio
 * ou rede dentro da lógica — para que o teste possa acelerar o tempo em vez de
 * esperar dois minutos e torcer.
 */
export function criarFeed({
  buscar,
  aoConfirmar,
  montar = montarCard,
  inserir,
  ler = lerMostrados,
  gravar = gravarMostrados,
  esquecer = esquecerMostrado,
  agendar = setTimeout,
  agora = () => Date.now(),
  visivel = () => typeof document === 'undefined' || document.visibilityState !== 'hidden',
  maxCartes = MAX_CARTES,
} = {}) {
  let interrompido = false;
  let mostrados = ler();

  function pendurar(alertas = []) {
    const novos = [];
    for (const a of alertas) {
      if (!deveMostrar(a, mostrados)) continue;
      mostrados.push(a.id);
      novos.push(a);
      if (novos.length >= maxCartes) break;
    }
    if (novos.length) {
      mostrados = [...new Set(mostrados)];
      gravar(mostrados);
    }
    for (const a of novos) inserir(montar(a, { aoConfirmar }));
    return novos.length;
  }

  async function passada() {
    if (interrompido) return;
    let alertas = [];
    try {
      const r = await buscar();
      alertas = (r && r.alertas) || [];
    } catch {
      // Falha de rede aqui é esperada e passageira. Ouve-se sobre a exceção e
      // tenta-se de novo; a alternativa — mostrar erro ao produtor — transforma
      // um_timeout de 200 ms em pânico por notificação.
      alertas = [];
    }
    pendurar(alertas);
    if (!interrompido) {
      agendar(passada, visivel() ? INTERVALO_SONDAGEM_MS : INTERVALO_OCULTA_MS);
    }
  }

  return {
    passada,
    parar() {
      interrompido = true;
    },
    get mostrados() {
      return mostrados;
    },
  };
}

function _ligar() {
  if (document.getElementById('amplia-alerta-feed')) return;
  if (!document.body) return;

  const cont = document.createElement('div');
  cont.id = 'amplia-alerta-feed';
  cont.setAttribute('aria-live', 'polite');
  cont.className = 'af-cont';
  document.body.appendChild(cont);

  const toast = document.createElement('div');
  toast.className = 'af-sino';
  toast.setAttribute('role', 'status');
  toast.title = 'Avisos do sistema';
  document.body.appendChild(toast);

  async function confirmar(alerta) {
    // some na hora: a espera da rede não pode prender o produtor na frente da
    // tela. A UI é optimista; o que NÃO pode ser optimista é o estado.
    //
    // O bug que este comentário substituía: o `catch {}` de baixo parecia
    // tratar a falha, mas `fetch` NÃO rejeita em erro HTTP — só em falha de
    // rede. Um 403 de CSRF, um 404, um 429 e um 500 resolvem-se como
    // sucesso. Pior: `pendurar()` já tinha gravado o id em `mostrados` (e em
    // sessionStorage) ANTES do POST. O resultado era um `catch` que nunca
    // disparava, sobre um estado que nunca voltava atrás:
    //
    //   - o produtor fecha o aviso que leu;
    //   - o servidor não sabe, e `IAAlertaProativo.estado` fica "novo";
    //   - o sino volta a contá-lo, e não há caminho para o fechar.
    //
    // O contador só cresce. Por isso: `!r.ok` conta como falha, e a falha
    // DESMARCA o alerta para a próxima sondagem o trazer de volta.
    const el = cont.querySelector(`[data-alerta-id="${alerta.id}"]`);
    if (el) el.remove();
    try {
      const r = await fetch('/api/amplia/alertas/visto/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
        body: JSON.stringify({ alerta_id: alerta.id }),
        credentials: 'same-origin',
      });
      if (!r.ok) throw new Error('alertas/visto ' + r.status);
    } catch (e) {
      esquecer(alerta.id);
      console.warn('[alerta] nao consegui confirmar', alerta.id, e && e.message);
    }
  }

  const feed = criarFeed({
    buscar: async () => {
      const r = await fetch('/api/amplia/alertas/pendentes/', { credentials: 'same-origin' });
      if (!r.ok) throw new Error(String(r.status));
      return r.json();
    },
    aoConfirmar: confirmar,
    inserir(el) {
      cont.appendChild(el);
      const dur = Number(el.dataset.duracaoMs);
      if (Number.isFinite(dur) && dur > 0) {
        setTimeout(() => el.remove(), dur);
      }
      if (cont.children.length > 5) cont.firstElementChild?.remove();
      atualizarSino();
    },
  });

  function atualizarSino() {
    const n = cont.children.length;
    toast.textContent = n ? String(n) : '';
    toast.classList.toggle('af-tem', n > 0);
  }

  document.addEventListener('visibilitychange', () => {
    if (!document.hidden) feed.passada();
  });
  window.addEventListener('pagehide', () => feed.parar());
  feed.passada();
}

if (typeof document !== 'undefined') {
  document.addEventListener('DOMContentLoaded', _ligar, { once: true });
}
