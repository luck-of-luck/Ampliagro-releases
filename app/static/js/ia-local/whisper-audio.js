/* =============================================================================
 * whisper-audio.js — a Magia do Áudio, do microfone ao sandbox.
 * =============================================================================
 *
 * producer grava (offline)
 *      ↓
 * decodifica + reamostra 16 kHz      (OfflineAudioContext, main thread)
 *      ↓
 * Whisper transcreve                  (worker, fora da main thread)
 *      ↓
 * SmolLM2 interpreta a semântica      (relato ou comando?)
 *      ↓
 * tool governada                      (/api/amplia/exec/ → sandbox.executar)
 *
 * -----------------------------------------------------------------------------
 * O PROBLEMA QUE DOMINA TUDO AQUI: WebGPU É UM DISPOSITIVO, NÃO UM RECURSO
 * -----------------------------------------------------------------------------
 * O WebLLM (SmolLM2) e o Whisper rodam em runtimes diferentes, em contextos
 * diferentes, mas pedem o MESMO dispositivo gráfico. Se os dois pedirem ao
 * mesmo tempo, um dos dois espera — e o usuário vê um travamento sem
 * explicação nenhuma.
 *
 * Isso não é uma hipótese. É a razão de existir um `criarSerializadorGpu()`
 * neste arquivo: a exclusão mútua entre "o LLM está pensando" e "o Whisper está
 * transcrevendo" é explícita, e não uma propriedade emergente de quem chega primeiro.
 *
 * E o porquê de NÃO desligar o LLM antes de transcrever, que seria a solução
 * mais óbvia: `engine.unload()` joga fora 1,1 GB de pesos. Recarregar depois
 * custa dezenas de segundos. O produtor não pode pagar isso a cada áudio — ele
 * fala, espera, e fala de novo. O LLM fica residente e apenas SE CALADO.
 *
 * -----------------------------------------------------------------------------
 * POR QUE A PARTE DIFÍCIL ESTÁ ESCRITA COMO FUNÇÕES PURAS
 * -----------------------------------------------------------------------------
 * Fila e serializador são as duas peças que mais quebram e menos se testam:
 * são código que só falha sob concorrência, e "funciona no meu navegador" não
 * é evidência. Por isso `criarFila` e `criarSerializadorGpu` recebem todas as
 * dependências por parâmetro e não tocam em DOM, Worker nem fetch. O
 * `tests_whisper.cjs` exercita esses dois sem browser nenhum.
 *
 * O resto (MediaRecorder, AudioContext, Worker) é plumbing fino, e é o tipo de
 * código que a inspeção visual pega mais rápido que um teste unitário.
 * ========================================================================== */

/* ---------------------------------------------------------------- orçamento */

/**
 * Limites. O objetivo aqui não é segurança contra arquivo malicioso (o
 * navegador já limita) e sim não matar o aparelho do produtor.
 */
export const ORCAMENTO = Object.freeze({
  /* Whisper processa em janelas de 30 s. Acima disso o custo de memória
   * cresce, e o celular de 4 GB do talhão é quem paga. 2 min é o suficiente
   * para um relatório de serviço e cabe folgado em duas janelas. */
  MAX_SEGUNDOS: 120,
  /* WebM/Opus é ~24 kbps. 15 MB de áudio são ~80 min: generouso demais para
   * qualquer coisa que um produtor grave de uma sentada. */
  MAX_BYTES: 15 * 1024 * 1024,
  /* Taxa que o Whisper espera. Reprodutível em qualquer browser. */
  TAXA: 16000,
});

/**
 * Escolhe o MIME do MediaRecorder.
 *
 * Não é cosmetico: a ordem de preferência é por compatibilidade real de
 * decodificação, não porsuporte do gravador. `audio/webm;codecs=opus` é o
 * único que TODOS os navegadores de celular decodificam de volta. Se cair para
 * `audio/mp4` (Safari) o `OfflineAudioContext` ainda decodifica, mas o
 * Opus em WebM é o caminho testado.
 *
 * Função pura: testável sem browser, e é justamente onde um `if` errado
 * custaria um bug que só aparece em iPhone.
 */
export function escolherMime(tipoSuportado) {
  const lista = typeof tipoSuportado === 'function' ? tipoSuportado() : tipoSuportado || [];
  const candidatos = [
    'audio/webm;codecs=opus',
    'audio/webm',
    'audio/ogg;codecs=opus',
    'audio/mp4',
    'audio/mpeg',
  ];
  for (const m of candidatos) {
    if (lista && (lista.includes ? lista.includes(m) : (lista || []).toString().indexOf(m) >= 0))
      return m;
  }
  return '';
}

/* ------------------------------------------------------------- serialização */

/**
 * Exclusão mútua com prioridade por turno.
 *
 * `prioridade` faz o LLM passar na frente quando ele JÁ está pensando — não
 * o inverso. Encerrar uma geração de 1,7B no meio para ouvir um áudio seria
 * pior que o áudio esperar meio segundo.
 *
 * Sem isto, o sintoma e um enganoso: o produtor vê "pensando..." e, dois
 * segundos depois, "transcrevendo...", e não tem como saber qual etapa está
 * consumindo a GPU. Ambos os donos competem e ambos reportam lentidão.
 */
export function criarSerializadorGpu() {
  /* Array simples com shift(). Uma lista ligada aqui seria mais esperta e
   * igualmente errada: a primeira versao usava `proximo` e mantinha uma variavel
   * `atual` que NUNCA era atribuida — entao `livre()` saia cedo, a promessa
   * nunca resolvia, e a GPU travava para sempre. Foi descoberto pelos testes
   * de concorrencia, nao por leitura. Codigo que so funciona sob concorrencia
   * precisa ser obvvio de relance, nao esperto. */
  let ocupado = false;
  let dono = null;
  const fila = [];

  function iniciar() {
    if (ocupado || !fila.length) return;
    ocupado = true;
    const t = fila.shift();
    dono = t;
    t.rodar();
  }

  /**
   * @param nome        'llm' | 'whisper' — quem esta segurando a GPU
   * @param prioritario quando true, entra na frente da fila existente. NUNCA
   *                     interrompe quem ja esta rodando: encerrar uma geracao
   *                     de 1,7B no meio seria pior que o audio esperar meio
   *                     segundo.
   */
  function adquirir(nome, prioritario, fn) {
    return new Promise((resolve, reject) => {
      const turno = {
        nome,
        async rodar() {
          try {
            await fn();
            resolve();
          } catch (e) {
            // o erro VAI para quem chamou: quem chamou precisa saber que a
            // transcricao falhou, e nao receber um undefined silencioso
            reject(e);
          } finally {
            // `finally` e o unico lugar seguro: liberacao tanto no caminho
            // feliz quanto na excecao. Se isto sair daqui, uma excecao em
            // qualquer passo trava a IA do produtor para sempre, e a UI nao
            // mostra nada porque continua esperando.
            ocupado = false;
            dono = null;
            iniciar();
          }
        },
      };
      if (prioritario) fila.unshift(turno);
      else fila.push(turno);
      iniciar();
    });
  }

  return {
    adquirir,
    ocupado: () => ocupado,
    donoAtual: () => (dono ? dono.nome : null),
    tamanhoFila: () => fila.length,
  };
}

/* ------------------------------------------------------------------- fila */

/**
 * Fila de trabalhos com um único consumidor.
 *
 * Non-blocking significa duas coisas, e é fácil confundir:
 *  (a) a interface não trava — garantido pelo worker; e
 *  (b) o ENCAMINHAMENTO não espera — a função retorna imediatamente e o
 *      trabalho acontece depois.
 *
 * (b) é o que a interface precisa para poder mandar três áudios seguidos sem
 * o segundo ficar bloqueado atrás do primeiro na hora de enviar.
 *
 * Rejeicao quando cheio e deliberada: better falhar alto e dizer "a fila está
 * cheia" do que aceitar 50 áudios e fazer o aparelho derreter tentando
 * decodificar todos. E o produtor vê que a máquina não dá conta, que é
 * informação útil — diferente de um spinner eterno.
 */
export function criarFila({ limite = 4 } = {}) {
  let tamanho = 0;
  let corrida = Promise.resolve();
  const erros = [];

  function enfileirar(tarefa) {
    if (tamanho >= limite) {
      const e = new Error(`fila cheia (${limite} itens) — mande menos audios de uma vez`);
      e.codigo = 'FILA_CHEIA';
      return Promise.reject(e);
    }
    tamanho++;
    // A corrente INTERNA nunca rejeita — de propósito.
    //
    // Se ela rejeitasse, o próximo `enfileirar` encadearia numa promessa já
    // rejeitada e a tarefa nova nunca executaria. O efeito no produto é
    // silencioso e permanente: um áudio que falha (perdeu o microfone, o
    // worker caiu) mataria a fila para sempre, e todo áudio seguinte seria
    // engolido sem aviso nenhum.
    //
    // A corrente existe só para ORDENAR. O erro é entregue no resultado de
    // cada chamada, que é quem tem interesse nele.
    corrida = corrida.then(
      () =>
        Promise.resolve()
          .then(tarefa)
          .then(
            (valor) => {
              tamanho--;
              return { ok: true, valor };
            },
            (erro) => {
              tamanho--;
              erros.push(erro);
              return { ok: false, erro };
            }
          ),
      // rede de seguranca: se a corrente anterior viesse rejeitada por algum
      // motivo fora deste caminho, o próximo job ainda roda.
      () => {
        tamanho--;
        return { ok: true, valor: undefined };
      }
    );
    return corrida;
  }

  return {
    enfileirar,
    tamanho: () => tamanho,
    erros,
  };
}

/* ------------------------------------------------------------------ prompt */

/**
 * O prompt que decide relato ou comando.
 *
 * Este é o ponto onde o SmolLM2 entra, e ele NÃO é enfeite. Um regex
 * distingue "terminei de aplicar" de "aplica agora"; ele não distingue
 * "pode ligar a irrigação do talhão 4?" de "liga a irrigação do talhão 4". A
 * diferença entre relato e comando é de INTENÇÃO, e intenção é o que o modelo
 * de linguagem foi treinado para ler.
 *
 * Por isso a saída é JSON estruturado e não texto: o texto o produtor lê, o
 * JSON o servidor usa. E a lista de tools VEM do servidor (`catalogoTools`),
 * nunca é hardcoded aqui — um catálogo duplicado no cliente é um catálogo que
 * um dia mente sobre o que existe.
 *
 * `sinais` são as pistas da primeira versão do backend. Elas vão como contexto,
 * não como veredito: o modelo pode discordar, e quando discorda o servidor
 * ainda exige confirmação. A segurança não depende do modelo acertar.
 */
export function montarPrompt(transcricao, sinais, catalogoTools, contexto) {
  const linhas = [
    'Voce e o assistente de um produtor rural brasileiro. Ouve um relato falado.',
    '',
    'TRANSCRICAO:',
    `"${transcricao}"`,
    '',
  ];

  if (sinais && Object.keys(sinais).length) {
    const p = [];
    if (sinais.talhoes && sinais.talhoes.length) p.push(`talhoes=${sinais.talhoes.join(',')}`);
    if (sinais.quantidades && sinais.quantidades.length)
      p.push(`quantidades=${sinais.quantidades.map((q) => q.valor + q.unidade).join(',')}`);
    if (sinais.classes_insumo && sinais.classes_insumo.length)
      p.push(`classes=${sinais.classes_insumo.join(',')}`);
    if (p.length) linhas.push(`PISTAS DETERMINISTICAS (podem estar erradas): ${p.join(' | ')}`);
    linhas.push('');
  }

  if (contexto) linhas.push(`CONTEXTO: ${String(contexto).slice(0, 400)}`, '');

  linhas.push(
    'Classifique o que o produtor FALA, nao o que ele QUER:',
    '- "relato": ele JA fez algo, ou esta descrevendo um estado. Ex: "terminei de aplicar 50 litros no talhao 4".',
    '- "comando": ele pede que ALGO SEA FEITO agora. Ex: "liga a irrigacao do talhao 4", "pode pulverizar?".',
    '- "pergunta": ele quer saber de volta. Ex: "vai chover hoje?".',
    '',
    'Responda APENAS com JSON, sem texto em volta:',
    '{"tipo":"relato|comando|pergunta","acao_fisica":true|false,',
    ' "frase_curta":"o que ele disse, para o produtor ler",',
    ' "tool":null,"args":{}}',
    '',
    'REGRAS:',
    '- "tool" so pode ser uma tool da lista abaixo. Se nenhuma servir, tool=null.',
    '- "relato" NUNCA vira tool de acao fisica. Um relato nao se repete.',
    '- Nao invente talhao, quantidade ou produto. O que nao estiver na transcricao, deixa null.',
    '- Nao escreva mais que 200 caracteres em "frase_curta".',
    '',
    'TOOLS DISPONIVEIS:',
    (catalogoTools || [])
      .slice(0, 60)
      // `catalogoToolsAmplia()` normaliza cada tool para `{ nome, desc }`
      // (ver a normalização em ia-local.js). Ler `t.descricao` aqui devolvia
      // `undefined` para TODAS, e o prompt chegava ao modelo assim:
      //
      //     - amplia_ajuda:
      //     - amplia_status_sensores:
      //
      // Uma lista de nomes sem descrição não é catálogo: um modelo de 1.7B
      // escolhe por PALAVRA, e sem palavra não tem em que se apoiar. Aceita
      // as duas chaves porque um chamador futuro pode passar a forma crua.
      .map((t) => `- ${t.nome}: ${String(t.desc ?? t.descricao ?? '').slice(0, 90)}`)
      .join('\n') || '- (nenhuma)'
  );
  return linhas.join('\n');
}

/**
 * Lê a resposta do modelo.
 *
 * Parse tolerante de propósito: um modelo de 1,7B devolve
 * `{"tipo":"comando",...}` às vezes embrulhado em ```json, às vezes com
 * vírgula sobrando, às vezes com aspas simples. Rejeitar tudo por causa
 * disso significaria o usuário falando e o sistema em silêncio — a falha mais
 * cara possível num produto de voz.
 *
 * Devolve SEMPRE um objeto com defaults seguros. Na dúvida, `pergunta`:
 * uma pergunta não executa nada, e o produtor ainda recebe resposta.
 */
export function lerRespostaModelo(texto) {
  const vazio = {
    tipo: 'pergunta',
    acao_fisica: false,
    frase_curta: '',
    tool: null,
    args: {},
    bruto: texto || '',
  };
  if (!texto) return vazio;
  let s = String(texto);
  s = s.replace(/```(?:json)?/gi, '').replace(/```/g, '');

  for (let i = 0; i < s.length; i++) {
    if (s[i] !== '{') continue;
    let prof = 0,
      emStr = false,
      esc = false,
      fim = -1;
    for (let j = i; j < s.length; j++) {
      const c = s[j];
      if (esc) {
        esc = false;
        continue;
      }
      if (c === '\\') {
        if (emStr) esc = true;
        continue;
      }
      if (c === '"') {
        emStr = !emStr;
        continue;
      }
      if (emStr) continue;
      if (c === '{') prof++;
      else if (c === '}') {
        prof--;
        if (prof === 0) {
          fim = j;
          break;
        }
      }
    }
    if (fim < 0) continue;
    try {
      const o = JSON.parse(s.slice(i, fim + 1));
      if (o && (o.tipo || o.tool)) {
        return {
          tipo: ['relato', 'comando', 'pergunta'].includes(o.tipo) ? o.tipo : 'pergunta',
          acao_fisica: o.acao_fisica === true,
          frase_curta: String(o.frase_curta || '').slice(0, 240),
          tool: typeof o.tool === 'string' && o.tool ? o.tool : null,
          args: o.args && typeof o.args === 'object' ? o.args : {},
          bruto: texto,
        };
      }
    } catch (e) {
      /* tenta a próxima '{' */
    }
  }
  return vazio;
}

/* =========================================================================
 * PLUMBING DE BROWSER (a parte que precisa existir para rodar de verdade)
 * ========================================================================= */

const estado = {
  worker: null,
  workerPronto: false,
  gravando: false,
  recorder: null,
  chunks: [],
  fila: null,
  gpu: null,
  audioCtx: null,
  ultimo: '',
  onFase: null,
};

function log(...a) {
  console.log('[Áudio]', ...a);
}

/** Cria o worker sob demanda. Nunca no load da página. */
function garantirWorker() {
  if (estado.worker) return estado.worker;
  estado.worker = new Worker(new URL('./whisper-worker.js', import.meta.url), { type: 'module' });
  estado.worker.onmessage = (ev) => {
    const m = ev.data || {};
    if (m.id === 'boot' || m.id === undefined) {
      estado.workerPronto = true;
    }
  };
  estado.worker.onerror = (e) => {
    console.warn('[Áudio] worker com erro:', e && e.message);
  };
  return estado.worker;
}

/**
 * Envia ao worker e resolve. `transfer` move o buffer em vez de copiá-lo —
 * ~2 MB por áudio de 30 s, o que num lote de 5 seria 10 MB de cópia e lixo
 * para o GC no meio de uma gravação.
 */
function pedirWorker(mensagem, transfer) {
  const w = garantirWorker();
  const id = Math.random().toString(36).slice(2);
  return new Promise((resolve, reject) => {
    const antes = (ev) => {
      if (!ev.data || ev.data.id !== id) return;
      w.removeEventListener('message', antes);
      resolve(ev.data);
    };
    w.addEventListener('message', antes);
    w.postMessage({ ...mensagem, id }, transfer || []);
    setTimeout(
      () => {
        w.removeEventListener('message', antes);
        reject(new Error('worker nao respondeu a tempo'));
      },
      10 * 60 * 1000
    );
  });
}

/**
 * Blob → Float32Array mono a 16 kHz.
 *
 * Feito na main thread porque é lá que existe `AudioContext`. O
 * `OfflineAudioContext` reamostra para 16 kHz com o filtro decente do browser,
 * e downmix para mono é meio do custo. Mandar o Blob cru ao worker obrigaria o worker a
 * ter um decodificador de áudio, que ele não tem.
 */
async function paraSamples16k(blob) {
  const AC = window.AudioContext || window.webkitAudioContext;
  if (!AC) throw new Error('sem AudioContext');
  if (!estado.audioCtx) estado.audioCtx = new AC();
  const bruto = await estado.audioCtx.decodeAudioData(await blob.arrayBuffer());
  const dur = bruto.duration;
  if (dur > ORCAMENTO.MAX_SEGUNDOS) {
    throw new Error(`áudio de ${Math.round(dur)}s passa do limite de ${ORCAMENTO.MAX_SEGUNDOS}s`);
  }
  const frames = Math.ceil(dur * ORCAMENTO.TAXA);
  const off = new OfflineAudioContext(1, frames, ORCAMENTO.TAXA);
  const src = off.createBufferSource();
  src.buffer = bruto;
  // downmix para mono: o Whisper é treinado em canal único
  const ganho = off.createGain();
  ganho.gain.value = 1;
  src.connect(ganho);
  ganho.connect(off.destination);
  src.start();
  const render = await off.startRendering();
  return render.getChannelData(0);
}

/**
 * O LLM interpretando.
 *
 * A serialização aqui não é casual: está em `criarSerializadorGpu`. Enquanto o Whisper
 * segura a GPU, o LLM espera; e o inverso também.
 */
async function interpretar(transcricao, sinais, catalogo, contexto) {
  const gpu = estado.gpu;
  return gpu.adquirir('llm', true, async () => {
    const mod = await import('./ia-local.js');
    const prompt = montarPrompt(transcricao, sinais, catalogo, contexto);
    // o motor pode ser null se o WebGPU falhou: nesse caso quem responde é o
    // texto puro, e o produtor ainda vê o que ele disse.
    if (!mod.obterIaEngine || !mod.obterIaEngine()) {
      return lerRespostaModelo(
        JSON.stringify({
          tipo: sinais && sinais.sugere_acao_fisica ? 'comando' : 'relato',
          acao_fisica: !!(sinais && sinais.sugere_acao_fisica),
          frase_curta: transcricao.slice(0, 200),
          tool: null,
          args: {},
        })
      );
    }
    const saida = await mod.raciocinarComPrompt(prompt, { maxTokens: 200 });
    return lerRespostaModelo(saida);
  });
}

/**
 * Grava e processa. Ponto de entrada para a UI.
 *
 * Devolve imediatamente com um handle; o resultado chega por `aoFinalizar`.
 * É isso que mantém o botão de gravar responsivo: o `await` do produtor é
 * sobre a PROMESSA DE ENVIAR, não sobre a transcrição.
 */
export async function iniciarGravacao({ aoFase, aoFinalizar, contexto } = {}) {
  estado.onFase = aoFase || null;
  if (!estado.fila) estado.fila = criarFila({ limite: 4 });
  if (!estado.gpu) estado.gpu = criarSerializadorGpu();

  const fase = (f, t) => {
    if (estado.onFase) estado.onFase({ fase: f, texto: t });
  };

  const stream = await navigator.mediaDevices.getUserMedia({
    audio: {
      channelCount: 1,
      echoCancellation: true,
      noiseSuppression: true,
      autoGainControl: true,
    },
  });
  const mime = escolherMime(() => (window.MediaRecorder ? MediaRecorder.isTypeSupported : null));
  const mr = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined);
  estado.chunks = [];
  mr.ondataavailable = (e) => {
    if (e.data && e.data.size) estado.chunks.push(e.data);
  };
  estado.recorder = mr;
  estado.gravando = true;
  mr.start(250); // 250 ms: chunks pequenos o bastante para não perder o início
  fase('gravando', 'Gravando… fale normalmente.');
  log('gravando, mime=', mime);

  return {
    async parar() {
      if (!estado.gravando) return null;
      estado.gravando = false;
      const partes = estado.chunks;
      estado.chunks = [];
      estado.recorder = null;

      const blob = new Blob(partes, { type: mime || 'audio/webm' });
      // encerrar as tracks LIBERA o microfone. Sem isto, o indicador do
      // sistema continua aceso e o produtor acredita que está gravando.
      stream.getTracks().forEach((t) => t.stop());

      if (blob.size > ORCAMENTO.MAX_BYTES) {
        fase('erro', 'Áudio longo demais.');
        return null;
      }

      fase('processando', 'Preparando áudio…');
      return estado.fila
        .enfileirar(async () => {
          try {
            fase('transcrevendo', 'Transcrevendo (pode levar alguns segundos)…');
            const samples = await paraSamples16k(blob);
            // Whisper primeiro, com a GPU exclusiva
            const res = await estado.gpu.adquirir('whisper', false, async () => {
              const r = await pedirWorker({ tipo: 'transcrever', audio: samples }, [
                samples.buffer,
              ]);
              return r;
            });
            const transcricao = (res && res.resultado && res.resultado.texto) || '';
            if (!transcricao) {
              fase('erro', 'Não consegui entender esse áudio.');
              return null;
            }
            estado.ultimo = transcricao;
            log('transcrito em', res.resultado.ms, 'ms, device=', res.resultado.device);

            // os sinais vêm do backend: mesma função que o Python usa, para
            // que cliente e servidor não discordem do que é um talhão
            let sinais = null;
            try {
              const mod = await import('./ia-local.js');
              sinais = await mod.extrairSinaisAudio(transcricao);
            } catch (e) {
              log('sinais indisponiveis:', e && e.message);
            }

            fase('interpretando', 'Entendendo o que você disse…');
            const cat = await obterCatalogo();
            const leitura = await interpretar(transcricao, sinais, cat, contexto);

            // DESCARGA IMEDIATA: devolve a GPU para o LLM e não segura os pesos
            // de áudio mais tempo que o necessário.
            try {
              await pedirWorker({ tipo: 'liberar' });
            } catch (e) {}

            if (leitura.tool) {
              fase('agindo', 'Executando…');
              const resposta = await window.__ampliaToolGovernada(
                JSON.stringify({ tool: leitura.tool, args: leitura.args }),
                transcricao
              );
              fase('fim', resposta || leitura.frase_curta);
              if (aoFinalizar) aoFinalizar({ transcricao, leitura, resposta });
              return { transcricao, leitura, resposta };
            }

            fase('fim', leitura.frase_curta || transcricao);
            if (aoFinalizar) aoFinalizar({ transcricao, leitura, resposta: null });
            return { transcricao, leitura, resposta: null };
          } catch (e) {
            console.warn('[Áudio] falhou:', e);
            fase('erro', (e && e.message) || 'Falha ao processar o áudio.');
            if (aoFinalizar) aoFinalizar({ erro: e });
            return null;
          }
        })
        .then((r) => (r && r.ok ? r.valor : null));
    },
    cancelando() {
      if (estado.recorder && estado.recorder.state !== 'inactive') estado.recorder.stop();
      estado.gravando = false;
      stream.getTracks().forEach((t) => t.stop());
    },
  };
}

async function obterCatalogo() {
  try {
    const mod = await import('./ia-local.js');
    return (await mod.catalogoToolsAmplia()) || [];
  } catch (e) {
    return [];
  }
}

/**
 * Solta o worker.
 *
 * `pagehide` e não `beforeunload`: no mobile, `beforeunload` frequentemente não
 * dispara (o SO mata o processo), e `pagehide` dispara. Um worker de Whisper
 * segurando sessão ONNX viva numa aba que o navegador reciclou é RAM que não
 * volta.
 */
export function encerrarAudio() {
  if (estado.recorder && estado.recorder.state !== 'inactive') {
    try {
      estado.recorder.stop();
    } catch (e) {}
  }
  estado.gravando = false;
  if (estado.worker) {
    estado.worker.terminate();
    estado.worker = null;
    estado.workerPronto = false;
  }
  if (estado.audioCtx) {
    try {
      estado.audioCtx.close();
    } catch (e) {}
    estado.audioCtx = null;
  }
  estado.fila = null;
  estado.gpu = null;
}

/* =========================================================================
 * MONTAGEM DO BOTAO
 * =========================================================================
 * Deliberadamente NAOprocura um seletor sozinho ("#chatInput", ".composer").
 *
 * O chat desta aplicacao e montado por JS, e o compositor nao tem um id
 * estavel no HTML — um seletor chutado aqui produziria um botao que funciona
 * na tela de desenvolvimento e some em producao, ou pior: dois botoes, ou
 * nenhum, sem erro nenhum. Esse e o tipo de codigo que se aceita com base em
 * "eu vi que apareceu".
 *
 * A funcao recebe o elemento-alvo de quem sabe onde ele esta. Uma linha no
 * template, e o botao aparece no lugar certo.
 * ========================================================================= */
export function montarBotaoMicrofone(alvo, opts = {}) {
  if (!alvo || typeof alvo.appendChild !== 'function') {
    console.warn('[Áudio] alvo invalido para o botao de microfone');
    return null;
  }
  if (alvo.querySelector && alvo.querySelector('[data-amplia-mic]')) {
    return alvo.querySelector('[data-amplia-mic]'); // ja montado
  }

  const doc = alvo.ownerDocument || document;
  const botao = doc.createElement('button');
  botao.type = 'button';
  botao.setAttribute('data-amplia-mic', '1');
  botao.setAttribute('aria-label', 'Gravar audio para a IA');
  botao.title = 'Gravar audio (funciona offline)';
  botao.textContent = '🎙';

  // Estilo minimo e inline de proposito: este arquivo nao conhece o design
  // system, e um CSS global aqui seria uma decisao de aparencia tomada no
  // lugar errado. Quem chama pode reestilizar depois.
  botao.style.cssText = 'font-size:18px;line-height:1;padding:6px 9px;cursor:pointer;';

  const fase = (f) => {
    const txt = (f && f.texto) || '';
    botao.title = txt || 'Gravar audio (funciona offline)';
    // so durante o processamento o botao mostra que algo esta acontecendo
    botao.dataset.fase = (f && f.fase) || '';
    botao.disabled =
      f && (f.fase === 'transcrevendo' || f.fase === 'interpretando' || f.fase === 'agindo');
  };

  let sessao = null;
  botao.addEventListener('click', async () => {
    // segundo toque = parar. Um botao so, com dois estados: e o que cabe num
    // celular com o dedo grande e a tela suja de poeira.
    if (sessao && !estado.gravando) {
      fase({ fase: 'processando', texto: 'Processando…' });
      await sessao.parar();
      sessao = null;
      return;
    }
    try {
      fase({ fase: 'preparando', texto: 'Abrindo o microfone…' });
      sessao = await iniciarGravacao({
        aoFase: fase,
        aoFinalizar: (r) => {
          sessao = null;
          if (r && r.erro) {
            fase({ fase: 'erro', texto: r.erro.message || 'Falhou' });
            return;
          }
          fase({ fase: 'fim', texto: 'Ouvi. Mande ou ajuste antes de executar.' });
          if (opts.aoOuvir) opts.aoOuvir(r);
          if (opts.aoMostrarTranscricao) opts.aoMostrarTranscricao(r && r.transcricao, r);
        },
        contexto: opts.contexto,
      });
      fase({ fase: 'gravando', texto: 'Gravando… toque de novo para parar.' });
    } catch (e) {
      console.warn('[Áudio] microfone negado:', e && e.message);
      sessao = null;
      fase({ fase: 'erro', texto: 'Sem microfone: verifique a permissao do navegador.' });
    }
  });

  alvo.appendChild(botao);
  return botao;
}

if (typeof window !== 'undefined') {
  window.__ampliaAudio = { iniciarGravacao, encerrarAudio, montarBotaoMicrofone, estado };
  // pagehide, e nao beforeunload: ver o comentário acima
  window.addEventListener('pagehide', () => {
    try {
      encerrarAudio();
    } catch (e) {}
  });
}
