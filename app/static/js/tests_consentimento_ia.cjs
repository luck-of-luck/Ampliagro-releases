// Verifica consentimento pela ordem observável de runtime e reload, sem rede.
const assert = require('node:assert/strict');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const fonte = pathToFileURL(path.join(__dirname, 'ia-local', 'ia-local.js'));
const principal = 'SmolLM2-1.7B-Instruct-q4f16_1-MLC';
const menor = 'Qwen2-0.5B-Instruct-q4f16_1-MLC';
let checks = 0;
let serial = 0;
function igual(atual, esperado, motivo) {
  assert.deepEqual(atual, esperado, motivo);
  checks++;
}
async function cenario({
  gpu = true,
  memoria = 8,
  respostas = [false],
  storage = new Map(),
  uid = 'teste',
  falhaPrincipal = false,
} = {}) {
  const eventos = [];
  const perguntas = [];
  global.window = {
    AMPLIAGRO_UID: uid,
    confirm(msg) {
      perguntas.push(msg);
      const resposta = respostas.shift();
      assert.equal(typeof resposta, 'boolean', 'pergunta inesperada');
      eventos.push(resposta ? 'aceitou' : 'recusou');
      return resposta;
    },
  };
  const adapter = {
    features: new Set(['shader-f16']),
    limits: { maxStorageBufferBindingSize: 2 ** 30, maxBufferSize: 2 ** 30 },
  };
  Object.defineProperty(global, 'navigator', {
    configurable: true,
    value: {
      deviceMemory: memoria,
      ...(gpu ? { gpu: { requestAdapter: async () => adapter } } : {}),
    },
  });
  global.localStorage = {
    getItem: (key) => storage.get(key) ?? null,
    setItem: (key, value) => storage.set(key, String(value)),
    removeItem: (key) => storage.delete(key),
  };
  global.document = { addEventListener() {}, removeEventListener() {} };
  global.MutationObserver = class {
    observe() {}
    disconnect() {}
  };
  global.IntersectionObserver = class {
    observe() {}
    disconnect() {}
  };
  global.matchMedia = () => ({ matches: false, addEventListener() {} });
  global.fetch = async () => {
    throw new Error('Rede proibida neste teste');
  };
  const mod = await import(`${fonte.href}?consent=${++serial}`);
  const carregar = async () => {
    eventos.push('runtime');
    return {
      prebuiltAppConfig: {
        model_list: [principal, menor].map((model_id) => ({
          model_id,
          required_features: ['shader-f16'],
        })),
      },
      MLCEngine: class {
        setInitProgressCallback() {}
        async reload(modelo) {
          eventos.push(`reload:${modelo}`);
          if (falhaPrincipal && modelo === principal) throw new Error('Falha simulada');
        }
        async unload() {
          eventos.push('unload');
        }
      },
    };
  };
  return { mod, iniciar: () => mod.iaInit(() => {}, carregar), eventos, perguntas, storage };
}
(async () => {
  const recusado = await cenario();
  igual(await recusado.iniciar(), null, 'recusa usa servidor');
  igual(recusado.eventos, ['recusou'], 'recusa impede runtime e modelo');
  igual(
    recusado.mod.obterDiagnosticoIaLocal().motivo,
    'download-recusado',
    'diagnóstico da recusa'
  );
  igual(await recusado.iniciar(), null, 'recusa persistida no mesmo módulo');
  igual(recusado.perguntas.length, 1, 'não repete pergunta');

  const reinicio = await cenario({ storage: recusado.storage });
  igual(await reinicio.iniciar(), null, 'recusa sobrevive a novo módulo');
  igual(reinicio.eventos, [], 'recusa gravada impede pergunta e runtime');
  igual(
    reinicio.storage.get(`ampliagro_ia_consent_teste_${principal}`),
    'nao',
    'recusa por usuário e modelo'
  );

  const outro = await cenario({ storage: recusado.storage, uid: 'outro', respostas: [true] });
  assert.ok(await outro.iniciar());
  checks++;
  igual(
    outro.eventos,
    ['aceitou', 'runtime', `reload:${principal}`],
    'consentimento antes de qualquer runtime ou download'
  );
  igual(outro.perguntas.length, 1, 'decisão de outro usuário não é herdada');
  for (const termo of [/1,1 GB/, /aparelho/, /servidor/]) {
    igual(termo.test(outro.perguntas[0]), true, `mensagem informa ${termo}`);
  }

  const semGPU = await cenario({ gpu: false, respostas: [] });
  igual(await semGPU.iniciar(), null, 'sem GPU usa servidor');
  igual(semGPU.eventos, [], 'não pede download que não pode executar');
  igual(semGPU.mod.obterDiagnosticoIaLocal().motivo, 'webgpu-indisponivel', 'diagnóstico sem GPU');

  const poucaMemoria = await cenario({ memoria: 1 });
  await poucaMemoria.iniciar();
  igual(/ATENÇÃO/.test(poucaMemoria.perguntas[0]), true, 'avisa pouca memória');
  igual(/fechar o navegador/.test(poucaMemoria.perguntas[0]), true, 'explica consequência');

  const fallback = await cenario({ respostas: [true, false], falhaPrincipal: true });
  igual(await fallback.iniciar(), null, 'recusa do modelo menor usa servidor');
  igual(
    fallback.eventos,
    ['aceitou', 'runtime', `reload:${principal}`, 'unload', 'recusou'],
    'libera principal e pergunta antes de baixar modelo menor'
  );
  igual(/0,3 GB|0,4 GB/.test(fallback.perguntas[1]), true, 'informa tamanho do modelo menor');
  igual(
    fallback.storage.get(`ampliagro_ia_consent_teste_${menor}`),
    'nao',
    'recusa do modelo menor é gravada'
  );

  const aceito = await cenario({ respostas: [true] });
  const [motor1, motor2] = await Promise.all([aceito.iniciar(), aceito.iniciar()]);
  igual(motor1 === motor2, true, 'inicializações concorrentes compartilham motor');
  igual(
    aceito.eventos,
    ['aceitou', 'runtime', `reload:${principal}`],
    'uma pergunta e um download'
  );
  console.log(`OK: ${checks} checks`);
})().catch((erro) => {
  console.error(erro);
  process.exitCode = 1;
});
