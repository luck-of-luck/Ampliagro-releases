/* =============================================================================
 * whisper-worker.js — transcrição de áudio fora da main thread.
 * =============================================================================
 *
 * POR QUE UM WORKER E NÃO SÓ UMA Promise
 * --------------------------------------
 * A transcrição de 30 s de Whisper leva, no WebGPU de um celular, centenas de
 * milissegundos a poucos segundos. Feito na main thread, isso congela a
 * interface: o produtor vê a tela parar no meio de gravar, e a conclusão
 * honesta ("a UI travou") é sempre a mesma — e ela é sempre creditada à IA,
 * não ao motivo.
 *
 * Um worker resolve isso de forma estrutural, não por `await`: a main thread
 * continua aceitando input, animando e processando o resto do chat enquanto a
 * inferência acontece em outro contexto. Não existe caminho de código em que
 * "congelar" seja uma opção.
 *
 * POR QUE transformers.js E NÃO WebLLM
 * ------------------------------------
 * WebLLM (o que roda o SmolLM2) só serve modelos de LLM que ele próprio
 * converteu para o formato MLC. Whisper é um encoder-decoder de áudio: não
 * existe build MLC dele, e não vai existir sem que alguém faça a conversão.
 * São dois runtimes diferentes, dois caches de pesos diferentes e — o ponto
 * crítico — DOIS DONOS DO MESMO DISPOSITIVO WebGPU. Ver `whisper-audio.js`.
 *
 * O PIN DE VERSÃO
 * ---------------
 *   @huggingface/transformers@3.8.1
 *
 * Fixado, e não `@latest`, por três motivos práticos:
 *   1. `dtype: 'q4f16'` só existe no repo `Xenova/whisper-*`. `onnx-community/`
 *      não publica q4f16, então trocar o repo "para um mais novo" faz o WebGPU
 *      cair silenciosamente para WASM — mais lento, sem erro visível.
 *   2. A linha 3.x é a que a combinação q4f16 + WebGPU + `Xenova/*` está
 *      documentada. A 4.x é mais nova e precisa de device real para validar
 *      antes de entrar num código que roda no talhão.
 *   3. Modelo + lib têm de ser reprodutíveis: se o `latest` mudar de API, a
 *      transcrição quebra no meio de uma temporada de chuva, no campo.
 * Para subir de versão: mude a constante abaixo e meça em aparelho real.
 * ========================================================================== */

const VERSAO_TRANSFORMERS = '3.8.1';
const CDN = `https://esm.run/@huggingface/transformers@${VERSAO_TRANSFORMERS}`;

const MODELO = 'Xenova/whisper-tiny'; // medido: par q4f16 = 49,9 MB
const DTYPE = 'q4f16'; // fp16: o que o WebGPU consome
const DEVICE_WEBGPU = 'webgpu';

/* O pipeline é criado UMA vez e mantido. Recriá-lo a cada áudio é o caminho
 * classic de memory leak em browser: cada `pipeline()` abre uma sessão ONNX
 * nova, com seus tensores, e a sessão anterior só é liberada por GC — se ela
 * estiver referenciada por qualquer closure, não é liberada. Por isso o
 * `dispose()` é explícito e existe mesmo sem disco. */
let transcriber = null;
let carregando = null; // a promise em curso, para não abrir duas
let deviceAtiva = 'desconhecida';

/** Estado público do worker, para o health check da UI. */
function status() {
  return {
    pronto: !!transcriber,
    carregando: !!carregando,
    modelo: MODELO,
    dtype: DTYPE,
    device: deviceAtiva,
    versao: VERSAO_TRANSFORMERS,
  };
}

async function garantirPipeline(onProgress) {
  if (transcriber) return transcriber;
  if (carregando) return carregando; // já está baixando: não duplica o download

  carregando = (async () => {
    onProgress({ fase: 'baixando_lib', texto: 'Baixando o transcritor...' });
    const mod = await import(/* @vite-ignore */ CDN);
    const { pipeline } = mod;

    onProgress({ fase: 'carregando_modelo', texto: 'Baixando o modelo de áudio (39 MB)...' });

    // WebGPU quando houver; senão WASM. A degradação aqui é intencional e
    // VISÍVEL: quem chama recebe `device` no retorno e mostra na tela. Um
    // fallback silencioso para WASM em vez de GPU é o tipo de coisa que faz
    // alguém medir performance e culpar o modelo errado.
    let device = DEVICE_WEBGPU;
    try {
      if (typeof navigator !== 'undefined' && !navigator.gpu) throw new Error('sem WebGPU');
      transcriber = await pipeline('automatic-speech-recognition', MODELO, {
        dtype: DTYPE,
        device,
        progress_callback: (p) => {
          if (p && p.status === 'progress' && p.total) {
            onProgress({
              fase: 'download',
              pct: Math.round((p.loaded / p.total) * 100),
              texto: `Baixando áudio: ${Math.round((p.loaded / p.total) * 100)}%`,
            });
          }
        },
      });
      deviceAtiva = DEVICE_WEBGPU;
    } catch (e) {
      console.warn('[Whisper] WebGPU indisponível, caindo para WASM:', e && e.message);
      onProgress({ fase: 'sem_webgpu', texto: 'Sem WebGPU: transcrição mais lenta (CPU).' });
      deviceAtiva = 'wasm';
      transcriber = await pipeline('automatic-speech-recognition', MODELO, {
        dtype: 'q4',
        device: 'wasm',
      });
    }
    carregando = null;
    onProgress({ fase: 'pronto', texto: 'Transcritor pronto.', device: deviceAtiva });
    return transcriber;
  })();

  return carregando;
}

/**
 * Transcreve áudio já decodificado (Float32Array mono a 16 kHz).
 *
 * Recebe Float32Array e não Blob de propósito: o WebM/Opus que o MediaRecorder
 * produz precisa ser decodificado por um decodificador de áudio de verdade, e
 * o `OfflineAudioContext` do navegador faz isso E reamostra para 16 kHz, que é
 * a taxa que o Whisper espera. Fazer isso na main thread (onde existe
 * `AudioContext`) e mandar só os samples reduz o payload do worker em uma
 * ordem de grandeza e elimina uma dependência de decodificação lá dentro.
 */
async function transcrever(audio, opts = {}) {
  const onProgress = opts.onProgress || (() => {});
  const t0 = (typeof performance !== 'undefined' ? performance : Date).now();
  const tr = await garantirPipeline(onProgress);

  // `language` explícito: sem ele o Whisper pode inferir inglês a partir de
  // few-shot e transcrever português com sotaque de cinema. Fixar o idioma
  // é a diferença entre "terminei o talhao 4" e lixo.
  const out = await tr(audio, {
    language: 'portuguese',
    task: 'transcribe',
    // Whisper processa em janelas de 30 s. Com chunk_length_s explícito, áudio
    // longo vira N janelas em vez de uma só — e o custo de memória de uma
    // janela é o que define se o celular sobrevive. Sem isto, um áudio de 5
    // minutos tenta atencao sobre tudo de uma vez.
    chunk_length_s: 30,
    return_timestamps: false,
  });

  const texto = (out && out.text ? out.text : '').trim();
  const t1 = (typeof performance !== 'undefined' ? performance : Date).now();
  return {
    texto,
    ms: Math.round(t1 - t0),
    device: deviceAtiva,
    duracaoS: +(audio.length / 16000).toFixed(1),
  };
}

/**
 * Libera o pipeline.
 *
 * É a razão de este arquivo existir em vez de uma chamada `pipeline()` solta
 * no meio do handler. Sem `dispose()`, a sessão ONNX fica viva até o GC decide
 * que pode, e num celular sob pressão de memória isso aparece como o navegador
 * matando a aba — sem mensagem, sem erro, e o produtor perde o áudio.
 *
 * Chamado: (a) explicitamente, quando o produtor sai do modo áudio;
 * (b) em `pagehide`; (c) antes de trocar de modelo.
 */
async function liberar() {
  const t = transcriber;
  transcriber = null;
  deviceAtiva = 'desconhecida';
  if (!t) return { liberado: false, motivo: 'nada carregado' };
  try {
    if (typeof t.dispose === 'function') await t.dispose();
  } catch (e) {
    console.warn('[Whisper] dispose falhou:', e && e.message);
  }
  // Nulo explícito: se alguma closure capturou a referência, ela agora vê null
  // e a sessão pode ser coletada. Sem isto, `t` sobrevive neste escopo.
  return { liberado: true };
}

/* ------------------------------------------------------------------ Wiring */

self.onmessage = async (ev) => {
  const { tipo, id, audio, lang } = ev.data || {};
  const responde = (payload) => self.postMessage({ id, ...payload });

  try {
    if (tipo === 'status') {
      responde({ ok: true, ...status() });
    } else if (tipo === 'preparar') {
      await garantirPipeline((p) => responde({ ok: true, progresso: p }));
      responde({ ok: true, ...status() });
    } else if (tipo === 'transcrever') {
      // transfer, não structuredClone: os samples não são copiados, e o
      // buffer da main thread é desligado no envio. Copiar 30 s a 16 kHz são
      // ~2 MB por áudio; num lote de 5, o GC vira o gargalo.
      const resultado = await transcrever(audio, {
        onProgress: (p) => responde({ ok: true, progresso: p }),
      });
      // libera a referência do payload assim que terminou
      ev.data.audio = null;
      responde({ ok: true, resultado });
    } else if (tipo === 'liberar') {
      responde({ ok: true, ...(await liberar()) });
    } else {
      responde({ ok: false, erro: `tipo desconhecido: ${tipo}` });
    }
  } catch (e) {
    console.error('[Whisper] erro no worker:', e);
    responde({ ok: false, erro: (e && e.message) || String(e) });
  }
};

self.postMessage({ id: 'boot', ok: true, ...status() });
