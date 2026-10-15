/* ===========================================================================
 * proativo-local.js — a fila do Motor Proativo vista pelo navegador.
 *
 * O QUE ESTE ARQUIVO FAZ, E POR QUE ELE EXISTE SEPARADO
 * ======================================================
 * O SmolLM2 roda AQUI, no aparelho do produtor. O motor proativo roda no
 * servidor. Eles não se encontram em memória compartilhada — se encontram em
 * HTTP, e este arquivo é a ponta desse fio.
 *
 * O caminho é:
 *
 *     servidor enfileira  ->  GET /api/amplia/proativo/pendente/
 *     aba busca (1 por vez) ->  SmolLM2 raciocina
 *     aba chama a tool     ->  POST /api/amplia/exec/  (sandbox.governa)
 *
 * E ESTE ARQUIVO NÃO É "O LLM DO PRODUTOR". Ele não decide nada: ele entrega
 * o texto que o servidor escreveu, aguarda, e entrega o que o modelo devolveu
 * para a MESMA porta governada que o resto do sistema usa. Se este arquivo
 * tivesse um `if` decidindo o que é risco, existiriam duas engenharias de
 * alerta — e elas iam divergir no primeiro caso raro.
 *
 * POR QUE UM MÓDULO NOVO, E NÃO MAIS BLOCO EM ia-local.js
 * ==========================================================
 * Duas razões, e a segunda é a que importa:
 *
 *  1. `ia-local.js` tem 5.800 linhas e é carregado antes deste. Crescer dentro
 *     dele é o que produz um arquivo que ninguem consegue revisar.
 *
 *  2. Ele depende só de GLOBAIS que `ia-local.js` e `whisper-audio.js` já
 *     publicam (`window.__ampliaIa`, `window.__ampliaToolGovernada`,
 *     `window.__ampliaAudio`). Nenhuma alteração nos dois. Isso importa porque
 *     os dois estão sob.active de outra pessoa agora, e um merge que finge que
 *     não mexeu é pior que um conflito visível.
 *
 * A REGRA DE OURO DESTE ARQUIVO
 * ==============================
 *   NUNCA RACIOCINA COM A GPU OCUPADA, NUNCA COM A ABA ESCONDIDA, NUNCA DUAS
 *   VEZES.
 *
 * A serialização com o Whisper não é estilo: dois pedidos de WebGPU juntos
 * dão um travamento sem explicação para o produtor, e o produtor que sofre
 * um travamento sem explicação fecha a aba — e aí não é só o áudio que
 * parou, é o motor proativo inteiro. `decidirTentativa()` é a função que
 * centraliza essa decisão, e ela é testada como invariante.
 *
 * O CSRF vem de `csrf-utils.js`, o módulo compartilhado do projeto. Copiar a
 * leitura do token aqui pareceria inofensivo e criaria dois lugares onde a
 * requisição pode ser montada errada sem nenhum teste reclamar.
 * ======================================================================== */

import { getCsrfToken } from '../csrf-utils.js';

/** Intervalo entre sondas quando a fila está vazia. Generoso de propósito:
 *  um produtor que abriu o app tem bateria e dados móveis a pagar; sondar a
 *  cada 10 s seria uma forma de queimar os dois sem nunca encontrar nada. */
export const INTERVALO_SONDAGEM_MS = 4 * 60 * 1000;

/** Backoff após erro. O primeiro erro é ruído de rede; o quinto significa que
 *  o servidor não está aí, e insistir é desperdício. */
export const INTERVALO_ERRO_MS = [30e3, 60e3, 180e3, 600e3];

/** Quantos cenários uma passada pode drenar. Sem teto, uma fila grande (e o
 *  produtor tem cinco) vira um loop de inferência que segura a GPU por
 *  minutos e ferve o aparelho. */
export const MAX_CENARIOS_POR_PASSADA = 3;

/** Erros seguidos até o poller desistir da sessão. */
export const MAX_FALHAS_SEGUIDAS = 5;

/* ------------------------------------------------------------------------ */
/* As guardas — a parte que a leitura acha e os testes provam                */
/* ------------------------------------------------------------------------ */

/**
 * Decide se vale tentar raciocinar agora. Devolve o motivo quando não vale.
 *
 * O motivo importa tanto quanto a decisão: um poller que simplesmente não
 * faz nada parece quebrado, e a pessoa que precisa depurar ("por que meu
 * produtor nunca foi avisado?") precisa ler a resposta em um log.
 *
 * @param {object} e
 * @param {boolean} e.visivel       a aba está à vista?
 * @param {boolean} e.motorPronto   o WebLLM está carregado?
 * @param {boolean} e.gpuOcupada     o Whisper (ou outra coisa) segura a GPU?
 * @param {boolean} e.emVoo          já há uma passada rodando?
 * @param {number}  e.falhas         erros seguidos até agora
 */
export function decidirTentativa({ visivel, motorPronto, gpuOcupada, emVoo, falhas = 0 } = {}) {
  if (emVoo) return { ok: false, motivo: 'ja ha uma passada em voo' };
  if (!visivel) return { ok: false, motivo: 'aba oculta: produtor nao ve a tela' };
  if (!motorPronto) return { ok: false, motivo: 'modelo local ainda nao carregou' };
  if (gpuOcupada) return { ok: false, motivo: 'GPU ocupada (audio tem prioridade)' };
  if (falhas >= MAX_FALHAS_SEGUIDAS) {
    return { ok: false, motivo: `desistindo apos ${falhas} falhas seguidas` };
  }
  return { ok: true, motivo: '' };
}

/**
 * Monta o prompt do cenario.
 *
 * O `contexto` chega pronto do servidor e NÃO é remontado aqui. Montar de novo
 * na aba faria cada aba decidir o que é relevante, e a mesma previsão viraria
 * dois prompts diferentes dependendo de quem perguntou — e o produtor veria
 * duas respostas para o mesmo tempo.
 *
 * O que esta função acrescenta é o FORMATO de saída, repetido de propósito. Um
 * modelo de 1,7B que já ouviu "responda JSON" no contexto esquece na terceira
 * troca; o lembrete aqui é a diferença entre um alerta e um `console.log` de
 * texto solto.
 */
export function montarPrompt(cenario) {
  const id = cenario && cenario.id;
  const base = String((cenario && cenario.contexto) || '').slice(0, 8000);
  return (
    base +
    '\n\n' +
    'Analise o cenario acima e responda APENAS com JSON, sem texto em volta:\n' +
    '{"achados":[{"titulo":"curto","mensagem":"o que fazer, nao so o que esta errado",' +
    '"nivel_severidade":"critico|atencao|info","criterio":"por que e risco"}]}\n\n' +
    'Se NAO houver risco real, responda exatamente {"achados":[]}. ' +
    'Nao invente tarefa, produto, data ou numero que nao esteja no cenario. ' +
    'Preferir NAO avisar a avisar coisa errada: o produtor confia no que chega.\n' +
    (id ? `Ao emitir, chame a tool amplia_emitir_alerta_proativo com cenario_id=${id}.\n` : '')
  );
}

/**
 * Lê os achados do modelo.
 *
 * Um modelo pequeno devolve JSON sujo: ```json no começo, uma frase depois,
 * aspas trocadas. A leitura tolerante aos dois lados (a mesma de
 * `lerObjetoJson` em ia-local.js) é o que separa "o modelo respondeu" de "o
 * modelo respondeu e a gente entendeu".
 *
 * Devolve [] quando não há achado — e [] é uma RESPOSTA VÁLIDA, não um erro.
 * Confundir as duas coisas faria o poller devolver o cenário e a fila reentregar
 * para sempre.
 */
export function interpretarAchados(texto) {
  const s = String(texto || '');
  if (!s.trim()) return [];
  // Remove cerca de código: é a forma mais comum de sujeira, e um bloco
  // ```json no meio faz o parser desistir antes de chegar no objeto.
  const limpo = s.replace(/```[a-zA-Z]*\n?/g, ' ');
  for (let i = 0; i < limpo.length; i++) {
    if (limpo[i] !== '{') continue;
    const lido = lerObjetoJson(limpo, i);
    if (!lido) continue;
    // `lerObjetoJson` devolve { valor, fim } — o objeto parseado está em
    // `valor`, e não no retorno direto. Ler `lido.achados` dá sempre undefined
    // e o parser devolve [] com a fila cheia: o sintoma parece "o modelo não
    // achou nada" quando na verdade nunca olhamos para a resposta dele.
    const achados = lido.valor && lido.valor.achados;
    if (Array.isArray(achados)) {
      return achados.filter((a) => a && typeof a === 'object' && a.mensagem);
    }
  }
  return [];
}

/** Le um objeto JSON a partir de `ini`, devolvendo o valor e o fim. */
export function lerObjetoJson(s, ini) {
  let profundidade = 0;
  let emString = false;
  let escape = false;
  for (let i = ini; i < s.length; i++) {
    const c = s[i];
    if (escape) {
      escape = false;
      continue;
    }
    if (c === '\\') {
      if (emString) escape = true;
      continue;
    }
    if (c === '"') {
      emString = !emString;
      continue;
    }
    if (emString) continue;
    if (c === '{') profundidade++;
    else if (c === '}') {
      profundidade--;
      if (profundidade === 0) {
        try {
          return { valor: JSON.parse(s.slice(ini, i + 1)), fim: i + 1 };
        } catch (e) {
          return null; // não é JSON válido; tenta a próxima '{'
        }
      }
    }
  }
  return null;
}

/* ------------------------------------------------------------------------ */
/* O poller                                                                  */
/* ------------------------------------------------------------------------ */

/**
 * Cria o poller. TODAS as dependências entram por parâmetro.
 *
 * `apiFetch`, `setTimeout`, `document.visibilityState` e o relógio são injetados
 * porque são eles que quebram: o poller precisa ser testado com "o servidor
 * demorou 30 s" e "a aba ficou 5 minutos oculta", e nenhum dos dois acontece
 * depressa o bastante para esperar num teste.
 */
export function criarPoller({
  sondar,
  raciocinar,
  emitir,
  devolver,
  estado,
  agendar = setTimeout,
  agora = Date.now,
  log = () => {},
  intervaloMs = INTERVALO_SONDAGEM_MS,
  maxPorPassada = MAX_CENARIOS_POR_PASSADA,
} = {}) {
  let emVoo = false;
  let falhas = 0;
  let parado = false;
  /* NOVO — geração de sondagem.
   *
   * `parar()` é só a flag (ver a nota mais abaixo) e o `agendar` é injetado e
   * NÃO devolve id, portanto não há `clearTimeout` para usar. A geração faz o
   * mesmo trabalho sem depender do id: cada timer guarda a geração com que foi
   * criado, e sai sozinho se essa geração já não for a atual.
   *
   * O defeito que ela corrige: o `visibilitychange` chamava `passar()`
   * diretamente, e essa chamada terminava em `agendar(...)` — sem cancelar o
   * timer que JÁ estava pendente. Num telefone, cada bloqueio e desbloqueio do
   * ecrã acrescentava uma sonda: ao fim de N mexidas na tela havia N timers
   * pendentes, e o poller passava a sondar N vezes mais depressa do que o
   * intervalo pedido.
   *
   * A guarda `emVoo` que já existia evita execuções SOBREPOSTAS. Esta evita
   * execuções DEMASIADO FREQUENTES — que é o que consome a bateria de quem
   * deixa a aba aberta o dia inteiro, e o que o backoff existe para proteger.
   */
  let geracao = 0;

  /** Agenda a próxima passada, invalidando as anteriores. */
  function agendarProxima(ms) {
    const minha = geracao;
    agendar(() => {
      if (minha !== geracao) return; // uma passada manual já a substituiu
      passar();
    }, ms);
  }

  function proximoIntervalo() {
    if (falhas === 0) return intervaloMs;
    return INTERVALO_ERRO_MS[Math.min(falhas - 1, INTERVALO_ERRO_MS.length - 1)];
  }

  /** Uma passada. Drena até `maxPorPassada` cenários e devolve. */
  async function passar() {
    if (parado) return;
    if (emVoo) return; // duas passadas sobrepostas é a corrida que a
    // guarda existe para impedir; e o segundo `if` custa nada.
    const g = estado();
    if (!g) return;
    const d = decidirTentativa({ ...g, emVoo, falhas });
    if (!d.ok) {
      log('[proativo] nao tento: ' + d.motivo);
      agendarProxima(intervaloMs);
      return;
    }

    emVoo = true;
    try {
      let processados = 0;
      let deuErrado = false;
      while (processados < maxPorPassada && !parado) {
        const cenario = await sondar();
        if (!cenario || !cenario.id) break; // fila vazia: acabou

        let achados = [];
        try {
          const bruto = await raciocinar(montarPrompt(cenario), cenario);
          achados = interpretarAchados(bruto);
        } catch (e) {
          const msg = (e && e.message) || 'erro ao raciocinar';
          log('[proativo] raciocinio falhou no cenario ' + cenario.id + ': ' + msg);
          await devolver(cenario.id, msg);
          falhas++;
          deuErrado = true;
          if (falhas >= MAX_FALHAS_SEGUIDAS) {
            parado = true;
            log('[proativo] desistindo da sessao apos ' + falhas + ' falhas');
            break;
          }
          continue;
        }

        if (!achados.length) {
          // "Nao achei risco" e' uma RESPOSTA. Devolver o cenario para a fila
          // aqui seria reler o mesmo texto a cada sonda ate o TTL vencer.
          await devolver(cenario.id, 'modelo nao encontrou risco');
          processados++;
          continue;
        }

        for (const a of achados) {
          const r = await emitir(a, cenario.id);
          if (!r || r.ok === false) {
            log('[proativo] alerta recusado: ' + ((r && r.erro) || 'sem retorno'));
          }
        }
        // O cenário é fechado pela própria tool, que só fecha DEPOIS de gravar
        // o alerta. Não é este arquivo que encerra: quem emite é quem conclui.
        processados++;
      }
      // O contador SÓ zera quando a passada terminou sem um único erro. Zerar
      // incondicionalmente no fim da passada é o bug mais tentador de escrever
      // aqui: a fila acaba, o poller acha que está saudável, e o backoff que
      // era para proteger o servidor morre junto com a evidência de que o
      // modelo está falhando.
      if (!deuErrado) falhas = 0;
    } catch (e) {
      falhas++;
      log('[proativo] falhou: ' + ((e && e.message) || e));
      if (falhas >= MAX_FALHAS_SEGUIDAS) {
        parado = true;
        log('[proativo] desistindo da sessao apos ' + falhas + ' falhas');
        return;
      }
    } finally {
      emVoo = false;
    }

    if (!parado) agendarProxima(proximoIntervalo());
  }

  return {
    iniciar() {
      parado = false;
      falhas = 0;
      geracao++; // uma sessão nova invalida os timers da anterior
      agendarProxima(8e3); // primeira sonda: deixa a página assentar
    },
    /**
     * `parar()` é só a flag. O callback já agendado ainda vai acordar — e é
     * ele que encontra `parado` e sai na primeira linha de `passar()`. Um
     * `clearTimeout` exigiria guardar o id do timer, e o id seria a única
     * parte do poller que depende de `agendar` devolver algo. A geração
     * (acima) cobre o caso que a flag NÃO cobre: o timer que fica pendente a
     * mais quando alguém chama `passar()` à mão.
     */
    parar() {
      parado = true;
      geracao++; // nenhum timer pendente volta a sondar depois de parar
    },
    /** Estado observável — é o que o `log` do bootstrap imprime quando algo
     *  estranho acontece, e é o que os testes usam para não esperar relógio. */
    diagnostico: () => ({ emVoo, falhas, parado, geracao }),
    /**
     * Passada pedida de fora: o botão "verificar agora" e o `visibilitychange`
     * quando a aba volta a ficar visível.
     *
     * Invalida os timers pendentes ANTES de correr, para que uma sonda manual
     * não deixe a anterior fila para trás. É seguro nos dois casos de saída
     * rápida: se `parado`, não queremos mesmo sondar; se `emVoo`, quem está a
     * correr é que vai reagendar, e como lê `geracao` ao agendar, apanha o
     * valor novo e não se perde.
     */
    passar: () => {
      geracao++;
      return passar();
    },
  };
}

/* ------------------------------------------------------------------------ */
/* O bootstrap — a única parte que fala com o browser                       */
/* ------------------------------------------------------------------------ */

function gpuEstaOcupada() {
  try {
    const a = window.__ampliaAudio;
    // `.ocupado()` só existe depois que o áudio foi aberto uma vez. Antes
    // disso a GPU está livre, e tratar "desconhecido" como "ocupado" faria o
    // motor proativo nunca rodar em quem nunca gravou áudio.
    return !!(a && a.estado && a.estado.gpu && a.estado.gpu.ocupado());
  } catch (e) {
    return false;
  }
}

function motorPronto() {
  try {
    const i = window.__ampliaIa;
    return !!(i && i.engine && i.engine());
  } catch (e) {
    return false;
  }
}

export function iniciarPollingProativo(opts = {}) {
  /**
   * Fetch próprio, e não `apiFetch` de ia-local.js. Duas razões:
   *
   *  1. `apiFetch` NÃO está no `window` — é um escopo de módulo. Alcançá-lo
   *     exigiria editar o arquivo que outra pessoa está alterando agora.
   *  2. `credentials: 'same-origin'` é obrigatório: a fila é por produtor, e
   *     sem a sessão a resposta seria 403 e o produtor nunca saberia por quê.
   *
   * O que a resposta devolve é o `cenario` pronto — ou `null`, que é a
   * resposta de fila vazia, e não um erro. Tratar "não tem nada" como falha
   * faria o poller entrar em backoff numa fila normalmente vazia.
   */
  const chamar =
    opts.chamar ||
    (async (url, init = {}) => {
      const r = await fetch(url, {
        credentials: 'same-origin',
        cache: 'no-store',
        ...init,
        headers: { 'X-CSRFToken': getCsrfToken(), ...(init.headers || {}) },
      });
      const t = await r.text();
      let d;
      try {
        d = JSON.parse(t);
      } catch {
        throw new Error(t.slice(0, 200) || `HTTP ${r.status}`);
      }
      if (!r.ok) throw new Error(d.erro || d.detail || `HTTP ${r.status}`);
      return d;
    });

  const raciocinarIA = opts.racionar || ((p) => window.__ampliaIa.racionar(p));

  const poller = criarPoller({
    log: (m) => console.log(m),
    estado: () => ({
      visivel: document.visibilityState !== 'hidden',
      motorPronto: motorPronto(),
      gpuOcupada: gpuEstaOcupada(),
    }),
    sondar: async () => {
      const r = await chamar('/api/amplia/proativo/pendente/');
      return (r && r.cenario) || null;
    },
    raciocinar: (prompt) => raciocinarIA(prompt),
    emitir: async (achado, cenarioId) => {
      const r = await window.__ampliaToolGovernada(
        JSON.stringify({
          tool: 'amplia_emitir_alerta_proativo',
          args: {
            mensagem: String(achado.mensagem || '').slice(0, 900),
            titulo: String(achado.titulo || '').slice(0, 120),
            nivel_severidade: String(achado.nivel_severidade || 'atencao'),
            criterio: String(achado.criterio || '').slice(0, 200),
            cenario_id: cenarioId,
          },
        }),
        'motor proativo local'
      );
      return { ok: r !== null && r !== undefined };
    },
    devolver: async (cenarioId, erro) => {
      try {
        await chamar('/api/amplia/proativo/devolver/', {
          method: 'POST',
          body: JSON.stringify({ cenario_id: cenarioId, erro: String(erro || '') }),
        });
      } catch (e) {
        console.warn('[proativo] devolucao falhou:', e && e.message);
      }
    },
  });

  poller.iniciar();
  if (typeof window !== 'undefined') {
    window.__ampliaProativo = poller;
  }
  return poller;
}

/* ------------------------------------------------------------------------ */
/* O autostart                                                               */
/* ------------------------------------------------------------------------ */
/* Este módulo é carregado por `base.html` e ninguém chama a função acima. A
 * alternativa — obrigar cada tela a lembrar de iniciar o motor proativo — é a
 * forma de o motor proativo funcionar em quatro telas e nenhuma delas ter
 * ligado. Então ele se inicia sozinho.
 *
 * Iniciar cedo NÃO é iniciar inferindo: a guarda em `decidirTentativa` recusa
 * enquanto o modelo não carregou, e o poll volta 4 minutos depois. O que se
 * paga aqui é um log, não bateria.
 *
 * E o `visibilitychange` existe pelo caso mais comum de todos: o produtor
 * abriu o app às 8h, a varredura do servidor rodou às 7h12, e ele está vendo um
 * cenário que ele mesmo não pediu. Sem o gatilho ele esperaria o intervalo
 * inteiro, e a espera seria a impressão de que o motor está quebrado.
 */
if (typeof window !== 'undefined' && typeof document !== 'undefined') {
  let _pollerProativo = null;
  const _ligar = () => {
    if (_pollerProativo) return;
    try {
      _pollerProativo = iniciarPollingProativo();
    } catch (e) {
      console.warn('[proativo] nao iniciou:', e && e.message);
    }
  };

  // O WebLLM pode demorar dezenas de segundos num celular. Esperar o evento
  // seria mais elegante, mas o evento nem sempre chega (o motor já carregado
  // por outra aba não emite), e aí o motor proativo nunca ligaria. Ligar e
  // deixar a guarda recusar é o comportamento que falha de forma visível.
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', _ligar, { once: true });
  } else {
    _ligar();
  }

  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible' && _pollerProativo) {
      const d = _pollerProativo.diagnostico();
      // Só sonda se estiver saudável. Um poller que desistiu fica quieto: o
      // produtor recarregar a aba não deve ressuscitar uma fila que ele já
      // decidiu não processar agora.
      if (!d.parado) _pollerProativo.passar();
    }
  });

  window.addEventListener('pagehide', () => {
    if (_pollerProativo) _pollerProativo.parar();
  });
}
