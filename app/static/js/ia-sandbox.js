/* Ampliagro — IA Local Sandbox (cliente).
   O painel/IA chama o sandbox auditado em vez de sair pesquisando por aí:
   - window.IASandbox.intents()      → catálogo com INSTRUÇÕES (o que pode + exemplos)
   - window.IASandbox.executar(intent, params) → roda no servidor (flags auditadas)
   - window.IASandbox.artefatos(tipo) → lê o artifactory (BD do sistema)
   - window.IASandbox.guardar(chave, tipo, dados) → escreve no artifactory
   Auth = sessão (cookie). A chave local (X-IA-Key) é só de serviços — nunca no JS. */
(function () {
  'use strict';

  function csrf() {
    return document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';
  }

  async function req(url, opts) {
    const r = await fetch(url, Object.assign({ credentials: 'same-origin' }, opts || {}));
    const j = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error((j && (j.erro || j.error)) || 'HTTP ' + r.status);
    return j;
  }

  window.IASandbox = {
    _catalogCache: null,
    /* Catálogo de intents + instruções (com cache em memória — 1 fetch por sessão) */
    intents() {
      if (this._catalogCache) return Promise.resolve(this._catalogCache);
      return req('/api/ia/intents/').then((j) => {
        this._catalogCache = j.intents || {};
        // console: registra que a IA LEU as instruções (1x por sessão)
        this._log('instrucao', 'IA leu o catálogo de intents', {
          total: Object.keys(this._catalogCache).length,
        }).catch(() => {});
        return this._catalogCache;
      });
    },
    /* Log genérico pro console de registros (não bloqueia o chat se falhar) */
    _log(tipo, resumo, dados, execucaoId) {
      return req('/api/ia/evento/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf() },
        body: JSON.stringify({ tipo, resumo, dados: dados || {}, execucao_id: execucaoId || null }),
      }).catch(() => ({}));
    },
    /* Executa intent auditada: {intent:'vai_chover', params:{horas:24}}.
     *
     * Os modos de criação (chat/painel) viajam no `meta`: o servidor compõe
     * peça/gráfico a partir deles. Lidos da loja (`IaModos`), nunca de
     * argumento — um chamador que escolhesse os modos no parâmetro decidiria
     * a apresentação por chamada, e dois chamadores divergiriam. */
    executar(intent, params, meta) {
      var modos = [];
      try {
        if (window.IaModos && window.IaModos.MODOS && typeof window.IaModos.activo === 'function') {
          modos = window.IaModos.MODOS.filter(function (m) {
            return window.IaModos.activo(m);
          });
        }
      } catch (e) {}
      var corpo = {
        intent,
        params: params || {},
        meta: Object.assign({ modos }, meta || {}),
      };
      return req('/api/ia/executar/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf() },
        body: JSON.stringify(corpo),
      });
    },
    /* Lê artefatos do BD (ex: ultimo clima, ultima tarefa) */
    artefatos(tipo) {
      const q = tipo ? '?tipo=' + encodeURIComponent(tipo) : '';
      return req('/api/ia/artefatos/' + q).then((j) => j.artefatos || []);
    },
    /* Guarda nota/resultado no artifactory */
    guardar(chave, tipo, dados) {
      return req('/api/ia/artefatos/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf() },
        body: JSON.stringify({ chave, tipo: tipo || 'nota', dados: dados || {} }),
      });
    },
    /* Atalhos em linguagem natural (espelham os exemplos do catálogo) */
    vaiChover(horas) {
      return this.executar('vai_chover', { horas: horas || 24 });
    },
    climaAgora() {
      return this.executar('clima_agora', {});
    },
    ligarIrrigador(deviceEui, confirm) {
      return this.executar('ligar_irrigador', { device_eui: deviceEui || '', confirm: !!confirm });
    },
    desligarIrrigador(deviceEui, confirm) {
      return this.executar('desligar_irrigador', {
        device_eui: deviceEui || '',
        confirm: !!confirm,
      });
    },
    associarTarefa(titulo, extra) {
      return this.executar('associar_tarefa', Object.assign({ titulo }, extra || {}));
    },
    statusSensores() {
      return this.executar('status_sensores', {});
    },
    /* ML: usuário satisfeito? grava aprendizado no artifactory */
    feedback(execucaoId, gostou, pergunta, resposta) {
      return this.executar('feedback', {
        execucao_id: execucaoId || null,
        gostou,
        pergunta,
        resposta,
      });
    },
    ajuda() {
      return this.executar('ajuda', {});
    },
  };
})();
