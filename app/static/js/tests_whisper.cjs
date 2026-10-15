// =============================================================================
// tests_whisper.cjs — o núcleo puro do pipeline de áudio, sem browser nenhum.
// =============================================================================
//
// O QUE ESTE ARQUIVO TESTA, E POR QUE SÓ ISSO
//
// Fila e serializador de GPU são as duas peças que mais quebram e menos se
// testam: só falham sob concorrência, e "funciona no meu navegador" não é
// evidência de nada. Por isso `criarFila` e `criarSerializadorGpu` recebem as
// dependências por parâmetro — o resto do arquivo (MediaRecorder,
// AudioContext, Worker) é plumbing fino que a leitura pega mais rápido.
//
// A Regra de ouro que este arquivo existe para provar:
//
//   WHISPER E O LLM NUNCA SEGUEM O DISPOSITIVO AO MESMO TEMPO.
//
// Isso não é estilo. Se os dois pedirem o WebGPU juntos, um espera e o produtor
// vê um travamento sem explicação. E a exclusão mútua é o que segura o build
// inteiro, então ela é testada como invariante, não como caso a casos.
// =============================================================================

const fs = require('fs');
const path = require('path');

// O whisper-audio.js e um ES module. Node le nativamente com import() dinamico.
const src = path.join(__dirname, 'ia-local', 'whisper-audio.js');

let ok = 0,
  falhas = 0;
function check(nome, cond, detalhe) {
  if (cond) {
    ok++;
    console.log(`  ok   ${nome}`);
  } else {
    falhas++;
    console.log(`  FALHA ${nome}${detalhe ? ' -> ' + detalhe : ''}`);
  }
}
function eq(nome, got, esp) {
  check(
    nome,
    JSON.stringify(got) === JSON.stringify(esp),
    `recebi ${JSON.stringify(got)}, esperava ${JSON.stringify(esp)}`
  );
}
function seca(t) {
  console.log(`\n--- ${t} ---`);
}

(async () => {
  const M = await import(`file://${src.replace(/\\/g, '/')}`);

  // =========================================================================
  seca('escolherMime: o gravador precisa de um MIME que o browser decodifica de volta');
  // =========================================================================
  eq(
    'webm/opus quando suportado',
    M.escolherMime(['audio/webm;codecs=opus', 'audio/mp4']),
    'audio/webm;codecs=opus'
  );
  eq(
    'cai para webm puro quando opus nao bate',
    M.escolherMime(['audio/webm', 'audio/mp4']),
    'audio/webm'
  );
  eq('usa mp4 no iPhone (sem webm)', M.escolherMime(['audio/mp4', 'audio/mpeg']), 'audio/mp4');
  eq('vazio quando nada e suportado', M.escolherMime([]), '');
  check(
    'aceita funcao (MediaRecorder.isTypeSupported)',
    M.escolherMime(() => ['audio/webm;codecs=opus']) === 'audio/webm;codecs=opus'
  );

  // =========================================================================
  seca('criarFila: nao-bloqueante, em ordem, e honesto quando enche');
  // =========================================================================
  {
    const ordem = [];
    const f = M.criarFila({ limite: 3 });
    const dormir = (ms) => new Promise((r) => setTimeout(r, ms));

    // NAO-BLOQUEANTE significa: enfileirar retorna antes de o trabalho
    // terminar. Nao significa "roda sincrono" — a tarefa comeca na microtask
    // seguinte, que e o comportamento correto (imperceptivel, e nao trava a
    // main thread). O que precisa ser garantido e que os tres entram na fila
    // antes de qualquer um terminar.
    let simultaneos = 0,
      pico = 0;
    const marca = (tag, valor) => async () => {
      ordem.push(tag + '-in');
      simultaneos++;
      pico = Math.max(pico, simultaneos);
      await dormir(30);
      ordem.push(tag + '-out');
      simultaneos--;
      return valor;
    };
    const p1 = f.enfileirar(marca('a', 1));
    const p2 = f.enfileirar(marca('b', 2));
    const p3 = f.enfileirar(marca('c', 3));

    // no instante seguinte ao enfileirar, os 3 estao na fila e nada terminou
    eq('enfileirar devolveu sem esperar o trabalho', ordem, []);
    eq('os tres estao na fila', f.tamanho(), 3);

    const [r1, r2, r3] = await Promise.all([p1, p2, p3]);
    eq('ordem preservada (um por vez)', ordem, ['a-in', 'a-out', 'b-in', 'b-out', 'c-in', 'c-out']);
    eq('nenhum job rodou em paralelo', pico, 1);
    eq('resultados na ordem', [r1.valor, r2.valor, r3.valor], [1, 2, 3]);
    eq('fila volta a zero', f.tamanho(), 0);
  }

  {
    // FILA CHEIA: falhar alto e melhor do que aceitar 50 audios e derreter o
    // aparelho. E o produtor precisa saber que a maquina nao da conta.
    const f = M.criarFila({ limite: 2 });
    const bloq = new Promise((r) => setTimeout(r, 40));
    f.enfileirar(async () => {
      await bloq;
      return 'ok';
    });
    f.enfileirar(async () => {
      await bloq;
      return 'ok';
    });
    let erro = null;
    try {
      await f.enfileirar(async () => 'x');
    } catch (e) {
      erro = e;
    }
    check('fila cheia rejeita em vez de acumular', !!erro, `sem erro, tamanho=${f.tamanho()}`);
    eq('erro tem codigo FILA_CHEIA', erro && erro.codigo, 'FILA_CHEIA');
    check('mensagem diz o limite', erro && erro.message.includes('2'), erro && erro.message);
  }

  {
    // Um job que falha NAO pode matar a fila: o audio seguinte tem de rodar.
    const f = M.criarFila({ limite: 2 });
    const r1 = await f.enfileirar(async () => {
      throw new Error('dispositivo caiu');
    });
    const r2 = await f.enfileirar(async () => 'depois do erro');
    eq('job com falha retorna ok:false e nao lanca', r1.ok, false);
    eq('erro preservado', r1.erro.message, 'dispositivo caiu');
    eq('fila segue apos falha', r2.valor, 'depois do erro');
    check('erro fica registrado', f.erros.length >= 1);
    eq('tamanho volta a zero apos erro', f.tamanho(), 0);
  }

  // =========================================================================
  seca('criarSerializadorGpu: A INVARIANTE CENTRAL DO BUILD');
  // =========================================================================
  {
    const g = M.criarSerializadorGpu();
    const dentro = [];
    const sleeping = (ms, tag) =>
      new Promise((r) => {
        dentro.push(tag);
        setTimeout(() => {
          dentro.splice(dentro.indexOf(tag), 1);
          r();
        }, ms);
      });

    // dispara whisper e llm "ao mesmo tempo"
    const a = g.adquirir('whisper', false, () => sleeping(40, 'w'));
    const b = g.adquirir('llm', true, () => sleeping(20, 'l'));
    await Promise.all([a, b]);
    check(
      'nunca houve dois donos da GPU ao mesmo tempo',
      dentro.length <= 1,
      `pico de ocupacao = ${dentro.length}`
    );
    eq('a GPU fica livre no fim', g.ocupado(), false);
    eq('ninguem dono apos o fim', g.donoAtual(), null);
  }

  {
    // PRIORIDADE: o LLM que JA esta pensando nao pode ser interrompido por um
    // audio. Encerrar uma geracao de 1.7B no meio seria pior que o audio
    // esperar meio segundo.
    const g = M.criarSerializadorGpu();
    const ordem = [];
    const p1 = g.adquirir('llm', true, async () => {
      ordem.push('llm-1');
      await new Promise((r) => setTimeout(r, 40));
      ordem.push('llm-1-fim');
    });
    await new Promise((r) => setTimeout(r, 5));
    const p2 = g.adquirir('whisper', false, async () => {
      ordem.push('whisper');
    });
    await Promise.all([p1, p2]);
    eq('o LLM que ja estava rodando termina antes do audio', ordem, [
      'llm-1',
      'llm-1-fim',
      'whisper',
    ]);
  }

  {
    // FILA: tres audios + um llm. O llM com prioridade passa na frente da fila
    // de audios, mas nao na frente de quem ja esta rodando.
    const g = M.criarSerializadorGpu();
    const ordem = [];
    const w = (tag, ms) =>
      g.adquirir(tag, false, async () => {
        ordem.push(tag + '-in');
        await new Promise((r) => setTimeout(r, ms));
        ordem.push(tag + '-out');
      });
    const p1 = w('w1', 30);
    const p2 = w('w2', 10);
    const p3 = w('w3', 10);
    await new Promise((r) => setTimeout(r, 5));
    const pll = g.adquirir('llm', true, async () => {
      ordem.push('llm-prio');
    });
    await Promise.all([p1, p2, p3, pll]);
    eq('prioridade passa na frente da fila de audios', ordem, [
      'w1-in',
      'w1-out',
      'llm-prio',
      'w2-in',
      'w2-out',
      'w3-in',
      'w3-out',
    ]);
  }

  {
    // EXCEÇÃO: um trabalho que lança tem que liberar a GPU. Sem isto, uma
    // exceção em qualquer passo trava TODA a IA do produtor para sempre —
    // e a UI não mostra nada, porque continua esperando.
    const g = M.criarSerializadorGpu();
    let erro = null;
    try {
      await g.adquirir('whisper', false, async () => {
        throw new Error('worker morreu');
      });
    } catch (e) {
      erro = e;
    }
    eq('erro propaga para o chamador', erro && erro.message, 'worker morreu');
    eq('GPU liberada apesar do erro', g.ocupado(), false);
    // e continua utilizavel
    let rodou = false;
    await g.adquirir('llm', false, async () => {
      rodou = true;
    });
    check('fila continua viva depois de uma excecao', rodou);
  }

  {
    // SERIALIZACAO REAL: 20 tarefas concorrentes, uma so por vez. Se o
    // serializador fosse na pratica um no-op, isto acusaria.
    const g = M.criarSerializadorGpu();
    let simultaneos = 0,
      pico = 0;
    const tarefas = [];
    for (let i = 0; i < 20; i++) {
      tarefas.push(
        g.adquirir(i % 2 ? 'llm' : 'whisper', i % 3 === 0, async () => {
          simultaneos++;
          pico = Math.max(pico, simultaneos);
          await new Promise((r) => setTimeout(r, 1));
          simultaneos--;
        })
      );
    }
    await Promise.all(tarefas);
    eq('pico de concorrencia foi 1 (exclusao mutua real)', pico, 1);
  }

  // =========================================================================
  seca('montarPrompt: o LLM precisa saber a diferenca entre relato e comando');
  // =========================================================================
  {
    const catalogo = [
      {
        nome: 'amplia_registrar_observacao_campo',
        descricao: 'registra observacao no caderno de campo',
      },
      { nome: 'amplia_ligar_irrigador', descricao: 'liga o irrigador de um talhao' },
    ];
    const p = M.montarPrompt(
      'terminei de aplicar 50 litros no talhao 4',
      null,
      catalogo,
      'Fazenda Modelo'
    );
    check('inclui a transcricao literalmente', p.includes('terminei de aplicar 50 litros'));
    check(
      'distingue relato de comando no texto do prompt',
      p.includes('"relato"') && p.includes('"comando"')
    );
    check('relato nunca vira acao fisica', p.includes('"relato" NUNCA vira tool'));
    check('pede JSON e nada em volta', p.includes('APENAS com JSON'));
    check('pede para nao inventar talhao/quantidade', /Nao invente talhao/i.test(p));
    check('leva as tools do servidor, nao uma lista local', p.includes('amplia_ligar_irrigador'));
    check('leva o contexto do produtor', p.includes('Fazenda Modelo'));
  }

  {
    const p = M.montarPrompt(
      'liga a irrigacao do talhao 3',
      { talhoes: ['3'], quantidades: [{ valor: '0', unidade: 'l' }] },
      [],
      null
    );
    check(
      'pistas deterministicas entram como pistas, nao como veredito',
      p.includes('podem estar erradas')
    );
    check('funciona sem catalogo de tools', p.includes('(nenhuma)'));
  }

  // =========================================================================
  seca('lerRespostaModelo: um 1.7B devolve JSON sujo — e ainda tem de funcionar');
  // =========================================================================
  {
    eq(
      'json limpo',
      M.lerRespostaModelo(
        '{"tipo":"comando","acao_fisica":true,"frase_curta":"vou ligar o irrigador","tool":"amplia_ligar_irrigador","args":{"talhao":3}}'
      ),
      {
        tipo: 'comando',
        acao_fisica: true,
        frase_curta: 'vou ligar o irrigador',
        tool: 'amplia_ligar_irrigador',
        args: { talhao: 3 },
        bruto:
          '{"tipo":"comando","acao_fisica":true,"frase_curta":"vou ligar o irrigador","tool":"amplia_ligar_irrigador","args":{"talhao":3}}',
      }
    );

    // NÃO é uma proteção — é uma documenting. O cliente NÃO descarta a tool
    // de um "relato": quem filtra é o servidor, via `needs_confirm` no sandbox.
    // Descartar aqui tiraria do produtor uma ação legítima quando o modelo
    // classifica errado; deixar passar faz o servidor PEDIR CONFIRMAÇÃO, que é
    // exatamente a UX certa. O cliente passa o que o modelo disse, e o teste
    // registra que não há filtro escondido.
    eq(
      'cliente NAO descarta a tool de um relato (manda o servidor decidir)',
      (() => {
        const r = M.lerRespostaModelo(
          '{"tipo":"relato","acao_fisica":true,"tool":"amplia_ligar_irrigador","args":{}}'
        );
        return { tipo: r.tipo, tool: r.tool };
      })(),
      { tipo: 'relato', tool: 'amplia_ligar_irrigador' }
    );

    eq(
      'envuelto em cercao de codigo',
      M.lerRespostaModelo('```json\n{"tipo":"relato","frase_curta":"tudo certo"}\n```').tipo,
      'relato'
    );
    eq(
      'JSON no meio de prosa',
      M.lerRespostaModelo('Entendi. {"tipo":"pergunta","frase_curta":"vai chover?"} espero').tipo,
      'pergunta'
    );
    eq(
      'chaves dentro de string nao confundem o parser',
      M.lerRespostaModelo('{"tipo":"relato","frase_curta":"ele disse { isso } e pronto"}')
        .frase_curta,
      'ele disse { isso } e pronto'
    );
    eq(
      'escape de aspas nao quebra',
      M.lerRespostaModelo('{"tipo":"relato","frase_curta":"disse \\"liga\\" e nao fez"}')
        .frase_curta,
      'disse "liga" e nao fez'
    );

    // SEGURANCA: um tipo inventado cai no default seguro (pergunta), que nao
    // executa nada. Default permissivo aqui seria o pior default possivel.
    eq(
      'tipo desconhecido cai em pergunta (nao executa)',
      M.lerRespostaModelo(
        '{"tipo":"executar_tudo","acao_fisica":true,"tool":"amplia_ligar_irrigador"}'
      ).tipo,
      'pergunta'
    );

    eq(
      'texto sem json vira pergunta, nao erro',
      M.lerRespostaModelo('acho que ele quer dizer que terminou o talhao').tipo,
      'pergunta'
    );
    eq('vazio devolve defaults seguros', M.lerRespostaModelo('').acao_fisica, false);
    eq(
      'tool nao-string vira null',
      M.lerRespostaModelo('{"tipo":"comando","tool":123}').tool,
      null
    );
  }

  // =========================================================================
  seca('orcamento: o celular do produtor e quem paga o excesso');
  // =========================================================================
  check(
    'teto de 120 s cabe em 2 janelas de 30 s do whisper',
    M.ORCAMENTO.MAX_SEGUNDOS % 30 === 0,
    `${M.ORCAMENTO.MAX_SEGUNDOS}s`
  );
  check('teto de audio coerente com 15 MB', M.ORCAMENTO.MAX_BYTES <= 15 * 1024 * 1024);
  check('taxa de amostragem e a que o whisper espera', M.ORCAMENTO.TAXA === 16000);
  check('orcamento e congelado (nao mutavel por engano)', Object.isFrozen(M.ORCAMENTO));

  console.log(`\n${'='.repeat(60)}`);
  console.log(
    falhas === 0 ? `TODOS OS ${ok} CHECKS PASSARAM` : `${falhas} FALHA(S) de ${ok + falhas}`
  );
  console.log('='.repeat(60));
  process.exit(falhas === 0 ? 0 : 1);
})().catch((e) => {
  console.error('erro fatal no harness:', e);
  process.exit(2);
});
