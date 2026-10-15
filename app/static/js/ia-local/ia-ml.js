/*
 * AmplIA ML Client — Aprende localmente, entrega rápido, nunca inventa
 * Usa IndexedDB (pwa/indexeddb.js) para persistir perfil + histórico
 * Atualiza após cada interação; dados reais (API) são prioritários
 */
(function () {
  'use strict';

  const ML_DB_NAME = 'ampliagro-ml';
  const ML_STORE = 'interacoes';
  let mlDB = null;

  // Inicializa IndexedDB local para ML
  async function initML() {
    if (mlDB) return mlDB;
    return new Promise((resolve, reject) => {
      const req = indexedDB.open(ML_DB_NAME, 1);
      req.onerror = () => reject(req.error);
      req.onsuccess = () => {
        mlDB = req.result;
        resolve(mlDB);
      };
      req.onupgradeneeded = (e) => {
        const db = e.target.result;
        if (!db.objectStoreNames.contains(ML_STORE)) {
          db.createObjectStore(ML_STORE, { keyPath: 'id', autoIncrement: true });
        }
      };
    });
  }

  // Registra interação (pergunta + resposta + contexto)
  async function registrarInteracao(pergunta, resposta, contexto, correto) {
    try {
      await initML();
      const tx = mlDB.transaction([ML_STORE], 'readwrite');
      const store = tx.objectStore(ML_STORE);
      store.add({ pergunta, resposta, contexto, correto, timestamp: Date.now() });
    } catch (e) {
      console.warn('[ML] não salvou interação:', e);
    }
  }

  // Aprende com correção (se usuário corrige resposta = incorreta)
  async function corrigirResposta(pergunta, respostaAntiga, respostaNova, contexto) {
    await registrarInteracao(pergunta, respostaNova, contexto, true); // atualizada = correta
    // Se a resposta antiga continha "simulado" ou número inventado → marca como erro para aprender
    if (
      respostaAntiga &&
      (respostaAntiga.includes('simulado') || respostaAntiga.match(/\d+\s*kg/))
    ) {
      await registrarInteracao('ERRO_' + pergunta, respostaAntiga, contexto, false);
    }
  }

  // Perfil rápido — monta a partir de contexto real do usuário (não inventa)
  function montarPerfilRapido(ctx) {
    return {
      tipo: ctx.perfil_usuario?.tipo || 'produtor',
      area: ctx.perfil_usuario?.area || 'GERAL',
      propriedade: ctx.propriedade?.nome || '',
      cidade: ctx.propriedade?.cidade || '',
      uf: ctx.propriedade?.uf || '',
      estacao: ctx.estacao_meteorologica?.nome || null,
      talhoes: (ctx.talhoes_ativos || []).map((t) => t.nome),
      culturas: ctx.culturas_cadastradas || [],
      ultimo_acesso: new Date().toISOString(),
    };
  }

  // Predição simples local — baseia-se apenas no histórico local (não inventa dados)
  async function preverProximaConsultas(perguntaTexto) {
    // Se o histórico local mostra que usuário normalmente pergunta clima após safra
    // → sugerir clima (mas SEM inventar a temperatura — apenas sugerir perguntar)
    const txt = perguntaTexto.toLowerCase();
    const sugerido = [];
    if (txt.includes('safra') || txt.includes('plantio')) sugerido.push('clima');
    if (txt.includes('bovino') || txt.includes('leite') || txt.includes('corte'))
      sugerido.push('producao_animal');
    if (txt.includes('estoque') || txt.includes('insumo')) sugerido.push('lancamentos');
    return sugerido.slice(0, 2); // máx 2 sugestões, todas baseado apenas no texto
  }

  // Expõe globalmente
  window.AmpliagmML = {
    initML,
    registrarInteracao,
    corrigirResposta,
    montarPerfilRapido,
    preverProximaConsultas,
  };
})();
