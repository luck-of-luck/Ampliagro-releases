/**
 * Ampliagro AmplIA - Voice Assistant for Field Operations
 * Web Speech API integration for hands-free field operations
 */
class AmplIA {
  constructor() {
    this.recognition = null;
    this.synthesis = window.speechSynthesis;
    this.isListening = false;
    this.isSpeaking = false;
    this.commands = new Map();
    this.context = null; // current context: 'tarefa', 'aplicacao', 'observacao', etc.
    this.pendingAction = null;
    this.wakeWord = 'ampliagro';
    this.isActive = false;
    this.confidenceThreshold = 0.7;

    this.init();
  }

  init() {
    // Check browser support
    if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
      console.warn('[AmplIA] Speech Recognition not supported in this browser');
      return;
    }

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    this.recognition = new SpeechRecognition();

    this.recognition.continuous = true;
    this.recognition.interimResults = true;
    this.recognition.lang = 'pt-BR';
    this.recognition.maxAlternatives = 3;

    this.recognition.onstart = () => {
      this.isListening = true;
      this.emit('listeningStart');
      console.log('[AmplIA] Listening started');
    };

    this.recognition.onend = () => {
      this.isListening = false;
      this.emit('listeningEnd');
      // Auto-restart if active
      if (this.isActive) {
        setTimeout(() => {
          if (this.isActive && !this.isListening) {
            try {
              this.recognition.start();
            } catch (e) {}
          }
        }, 500);
      }
    };

    this.recognition.onresult = (event) => {
      this.handleResult(event);
    };

    this.recognition.onerror = (event) => {
      console.error('[AmplIA] Recognition error:', event.error);
      if (event.error === 'no-speech' || event.error === 'audio-capture') {
        // Silently restart
        setTimeout(() => {
          if (this.isActive && !this.isListening) {
            try {
              this.recognition.start();
            } catch (e) {}
          }
        }, 1000);
      }
    };

    // Register default commands
    this.registerDefaultCommands();

    // Listen for wake word
    this.on('transcript', (text, isFinal) => {
      if (!this.isActive) return;

      const lower = text.toLowerCase();

      // Wake word detection
      if (!this.wakeWordDetected && lower.includes(this.wakeWord)) {
        this.wakeWordDetected = true;
        this.speak('Sim, estou ouvindo');
        return;
      }

      if (!this.wakeWordDetected) return;

      if (isFinal) {
        this.processCommand(text);
        this.wakeWordDetected = false; // Reset for next command
      }
    });

    // Auto-start if configured
    if (localStorage.getItem('amplia_auto_start') === 'true') {
      this.activate();
    }
  }

  registerDefaultCommands() {
    // Tarefa commands
    this.addCommand(
      'criar tarefa',
      async (params) => {
        const desc = params.descricao || params._raw.replace('criar tarefa', '').trim();
        if (!desc) return this.ask('O que precisa ser feito?');

        const task = await this.createTask({
          descricao: desc,
          prioridade: params.prioridade || 'media',
          cargo_alvo: this.getCurrentArea(),
          setor: params.setor || this.getCurrentSector(),
        });

        this.speak(`Tarefa criada: ${task.descricao}`);
        return task;
      },
      { descricao: 'string', prioridade: 'baixa|media|alta|urgente', setor: 'string' }
    );

    this.addCommand(
      'concluir tarefa',
      async (params) => {
        const id = params.id || (await this.ask('Qual tarefa concluir?'));
        await this.completeTask(id);
        this.speak('Tarefa concluída');
      },
      { id: 'string' }
    );

    this.addCommand(
      'nova observação',
      async (params) => {
        const texto = params.texto || params._raw.replace('nova observação', '').trim();
        if (!texto) return this.ask('O que deseja registrar?');

        const note = await this.createFieldNote({
          conteudo: texto,
          tipo: 'observacao',
          talhao_id: params.talhao || this.getCurrentTalhao(),
        });

        this.speak('Observação registrada');
        return note;
      },
      { texto: 'string', talhao: 'string' }
    );

    this.addCommand('ver tarefas', async () => {
      const tasks = await this.getTasks({ status: 'pendente' });
      if (!tasks.length) {
        this.speak('Nenhuma tarefa pendente');
        return;
      }

      const count = tasks.length;
      const urgent = tasks.filter((t) => t.prioridade === 'urgente').length;
      this.speak(`Você tem ${count} tarefas pendentes, ${urgent} urgentes`);

      // Show on screen
      this.emit('showTasks', tasks);
    });

    this.addCommand('ver alertas', async () => {
      const alerts = await this.getAlerts();
      if (!alerts.length) {
        this.speak('Nenhum alerta ativo');
        return;
      }

      const critical = alerts.filter((a) => a.severidade === 'critical').length;
      this.speak(`${alerts.length} alertas ativos, ${critical} críticos`);
      this.emit('showAlerts', alerts);
    });

    this.addCommand('clima', async () => {
      const weather = await this.getWeather();
      if (!weather || weather.temp == null) {
        this.speak('Não consegui obter o clima agora. Tente novamente.');
        return;
      }
      this.speak(`Temperatura máxima ${weather.temp} graus`);
    });

    this.addCommand('ajuda', () => {
      const commands = [
        'Criar tarefa [descrição]',
        'Concluir tarefa [id]',
        'Nova observação [texto]',
        'Ver tarefas',
        'Ver alertas',
        'Como está o clima',
        'Ler notificações',
        'Sincronizar agora',
      ];
      this.speak('Comandos disponíveis: ' + commands.join(', '));
    });

    this.addCommand('sincronizar', async () => {
      this.speak('Iniciando sincronização');
      await window.SyncManager?.syncAll();
      this.speak('Sincronização concluída');
    });

    // Navigation
    this.addCommand('abrir quadro', () => {
      window.location.href = '/operario/kanban/';
    });
    this.addCommand('abrir telemetria', () => {
      window.location.href = '/telemetria/';
    });
    this.addCommand('abrir estoque', () => {
      window.location.href = '/servidor/estoque/';
    });
    this.addCommand('abrir alertas', () => {
      window.location.href = '/servidor/alertas/';
    });
    this.addCommand('ir para painel', () => {
      window.location.href = '/servidor/';
    });
  }

  addCommand(phrase, handler, params = {}) {
    const key = phrase.toLowerCase().trim();
    this.commands.set(key, { handler, params, phrase });
  }

  async processCommand(text) {
    const lower = text.toLowerCase().trim();

    // Find matching command
    for (const [phrase, cmd] of this.commands) {
      if (lower.includes(phrase)) {
        try {
          // Extract parameters from text
          const params = this.extractParams(lower, cmd.phrase, cmd.params);
          await cmd.handler(params);
          return true;
        } catch (error) {
          console.error('[AmplIA] Command error:', error);
          this.speak('Erro ao executar comando');
        }
        return true;
      }
    }

    // No match - try fuzzy match
    const similar = this.findSimilarCommand(lower);
    if (similar) {
      this.speak(`Não entendi. Quis dizer "${similar.phrase}"?`);
    } else {
      this.speak('Não entendi. Diga "ajuda" para ver comandos.');
    }
    return false;
  }

  extractParams(text, phrase, paramDefs) {
    const params = {};
    const remaining = text.replace(phrase, '').trim();

    // Simple extraction - in production would use NLP
    for (const [key, def] of Object.entries(paramDefs)) {
      if (typeof def === 'string') {
        // Try to extract value after keyword
        const regex = new RegExp(`${key}\\s+(\\w+)`, 'i');
        const match = remaining.match(regex);
        if (match) params[key] = match[1];
      }
    }

    params._raw = remaining;
    return params;
  }

  findSimilarCommand(text) {
    let best = null,
      bestScore = 0;
    for (const [phrase] of this.commands) {
      const score = this.similarity(text, phrase);
      if (score > bestScore && score > 0.6) {
        bestScore = score;
        best = { phrase, score };
      }
    }
    return best;
  }

  similarity(a, b) {
    // Simple Levenshtein-based similarity
    const longer = a.length > b.length ? a : b;
    const shorter = a.length > b.length ? b : a;
    if (longer.length === 0) return 1.0;
    const editDistance = this.levenshtein(longer, shorter);
    return (longer.length - editDistance) / longer.length;
  }

  levenshtein(a, b) {
    const matrix = [];
    for (let i = 0; i <= b.length; i++) matrix[i] = [i];
    for (let j = 0; j <= a.length; j++) matrix[0][j] = j;

    for (let i = 1; i <= b.length; i++) {
      for (let j = 1; j <= a.length; j++) {
        if (b[i - 1] === a[j - 1]) matrix[i][j] = matrix[i - 1][j - 1];
        else
          matrix[i][j] = Math.min(
            matrix[i - 1][j - 1] + 1,
            matrix[i][j - 1] + 1,
            matrix[i - 1][j] + 1
          );
      }
    }
    return matrix[b.length][a.length];
  }

  // Speech synthesis
  speak(text, options = {}) {
    if (!this.synthesis) return Promise.resolve();

    return new Promise((resolve) => {
      // Cancel any ongoing speech
      this.synthesis.cancel();

      // Implementação de Fallback Offline (Dor #3)
      if (!navigator.onLine && !this.offlineNotified) {
        this.offlineNotified = true;
        // Se houver um toast disponível na interface, dispara
        if (window.Toastify) {
          Toastify({
            text: 'Modo Offline ativo. Vozes genéricas em uso.',
            duration: 3000,
            gravity: 'top',
            position: 'right',
            style: { background: '#f59e0b' }, // orange
          }).showToast();
        } else {
          console.warn('[AmplIA] Offline mode: TTS cache loaded.');
        }
      } else if (navigator.onLine) {
        this.offlineNotified = false; // reseta
      }

      const utterance = new SpeechSynthesisUtterance(text);
      utterance.lang = 'pt-BR';
      utterance.rate = options.rate || 1.0;
      utterance.pitch = options.pitch || 1.0;
      utterance.volume = options.volume || 1.0;

      // Select Portuguese voice if available (Preferred cloud voice if online, local if offline)
      const voices = this.synthesis.getVoices();
      let ptVoice = null;
      if (navigator.onLine) {
        // Tenta achar voz premium (Google/Microsoft) se online
        ptVoice = voices.find(
          (v) =>
            v.lang.startsWith('pt') && (v.name.includes('Google') || v.name.includes('Microsoft'))
        );
      }
      // Fallback para qualquer voz PT (local cache)
      if (!ptVoice) ptVoice = voices.find((v) => v.lang.startsWith('pt'));

      if (ptVoice) utterance.voice = ptVoice;

      utterance.onend = () => {
        this.isSpeaking = false;
        resolve();
      };
      utterance.onerror = (e) => {
        console.error('[AmplIA] TTS Error:', e);
        this.isSpeaking = false;
        resolve();
      };

      this.isSpeaking = true;
      this.synthesis.speak(utterance);
    });
  }

  stopSpeaking() {
    this.synthesis.cancel();
    this.isSpeaking = false;
  }

  // Activation
  activate() {
    this.isActive = true;
    this.wakeWordDetected = false;
    if (!this.isListening) {
      try {
        this.recognition.start();
      } catch (e) {}
    }
    this.emit('activated');
  }

  deactivate() {
    this.isActive = false;
    this.wakeWordDetected = false;
    if (this.isListening) {
      this.recognition.stop();
    }
    this.emit('deactivated');
  }

  toggle() {
    if (this.isActive) this.deactivate();
    else this.activate();
  }

  // Helpers
  async ask(question) {
    return new Promise((resolve) => {
      this.pendingQuestion = { resolve, question };
      this.speak(question);
      // In real implementation, would listen for answer
      // For now, return empty
      setTimeout(() => resolve(''), 5000);
    });
  }

  async createTask(data) {
    const response = await fetch('/api/tarefas-estagio/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': this.getCSRFToken() },
      body: JSON.stringify(data),
    });
    return response.json();
  }

  async completeTask(id) {
    await fetch(`/api/tarefas-estagio/${id}/mover/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': this.getCSRFToken() },
      body: JSON.stringify({ status: 'concluido' }),
    });
  }

  async getTasks(filters = {}) {
    const params = new URLSearchParams(filters);
    const r = await fetch(`/api/tarefas-estagio/?${params}`);
    return r.json();
  }

  async getAlerts() {
    const r = await fetch('/api/alertas/?resolvido=false');
    return r.json();
  }

  async getWeather() {
    try {
      const r = await fetch('/api/previsao-clima/');
      const j = await r.json();
      if (j.error || j.erro) return null;
      const daily = j.daily || {};
      return {
        temp: daily.temperature_2m_max?.[0] ?? null,
        humidity: null,
        wind: null,
      };
    } catch {
      return null;
    }
  }

  getCurrentArea() {
    try {
      return window.userPerfil?.area_servidor || 'GERAL';
    } catch {
      return 'GERAL';
    }
  }

  getCurrentSector() {
    try {
      return window.userPerfil?.area_servidor || 'GERAL';
    } catch {
      return 'GERAL';
    }
  }

  getCurrentTalhao() {
    try {
      return window.currentTalhaoId;
    } catch {
      return null;
    }
  }

  getCSRFToken() {
    return (
      document.querySelector('[name=csrfmiddlewaretoken]')?.value ||
      document.cookie.match(/csrftoken=([^;]+)/)?.[1] ||
      ''
    );
  }

  // Event emitter
  on(event, callback) {
    this.events = this.events || {};
    this.events[event] = this.events[event] || [];
    this.events[event].push(callback);
  }

  emit(event, ...args) {
    (this.events[event] || []).forEach((cb) => cb(...args));
  }
}

// Global instance
window.AmplIA = new AmplIA();

// UI Toggle
window.toggleAmplIA = () => {
  if (window.AmplIA.isActive) {
    window.AmplIA.deactivate();
    document.getElementById('ampliaBtn')?.classList.remove('active');
  } else {
    window.AmplIA.activate();
    document.getElementById('ampliaBtn')?.classList.add('active');
  }
};

// Auto-start if configured
document.addEventListener('DOMContentLoaded', () => {
  if (localStorage.getItem('amplia_auto_start') === 'true') {
    window.AmplIA.activate();
  }
});

// Export
if (typeof module !== 'undefined') module.exports = AmplIA;
