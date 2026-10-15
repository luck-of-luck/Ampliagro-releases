/**
 * Ampliagro A/B Experiment Engine - Scientific method for agriculture
 *
 * REGRA DESTE MÓDULO — não quebrar ao estender:
 *
 *   Nenhum número sai daqui sem dizer de onde veio.
 *
 * `fonte_dado` tem tres estados, e é obrigatório em toda saída:
 *   'medido'  — veio de um sensor/API. Citamos a origem e o timestamp.
 *   'sem_dado'— não existe medição. Ausência, não zero.
 *   'simulado'— gerado. Só é aceito se quem pede passar `permitirSimulado: true`,
 *                e sai carimbado como 'simulado' em toda a análise.
 *
 * A versão anterior deste ficheiro devolvia `{temp:25, humidity:65, rain:0}` e
 * `{moisture:45, ph:6.2, ec:0.8}` de `getCurrentWeather(talhaoId)` /
 * `getSoilData(talhaoId)` — recebiam `talhaoId` e ignoravam-no. Um p-value
 * calculado sobre isso descreve uma constante, não a lavoura. O README vendia
 * este módulo como "Scientific A/B testing ✅". Agora devolve 'sem_dado' quando
 * não sabe, que é a única resposta honesta.
 */

/** Tipos de LeituraSensor -> campo de contexto. Schema: app/models/iot.py:524 */
const SENSOR_CLIMA = { temperatura: 'temp', umidade: 'humidity', chuva: 'rain' };
const SENSOR_SOLO = { umidade_solo: 'moisture', ph: 'ph', condutividade: 'ec' };

class ExperimentEngine {
  constructor() {
    this.experiments = new Map();
    this.results = new Map();
  }

  // ---------------------------------------------------------------- contexto

  /**
   * Lê o contexto real de um talhão a partir das leituras de sensor.
   *
   * Só `qualidade === 'good'` conta como 'medido'. 'suspect' desce para
   * 'suspect' — existe leitura, mas não é confiável. Ausente é 'sem_dado'.
   *
   * @returns {Promise<{fonte_dado:string, valores:object, origem:string|null, motivo:string|null}>}
   */
  async collectContext(talhaoId) {
    const resposta = { fonte_dado: 'sem_dado', valores: {}, origem: null, motivo: null };

    if (talhaoId === undefined || talhaoId === null || talhaoId === '') {
      resposta.motivo = 'experimento sem talhao definido';
      return resposta;
    }

    let leituras;
    try {
      const r = await fetch(`/api/leituras-sensor/?talhao=${encodeURIComponent(talhaoId)}`, {
        headers: { Accept: 'application/json' },
        credentials: 'same-origin',
      });
      if (!r.ok) {
        resposta.motivo = `leitura de sensor respondeu ${r.status}`;
        return resposta;
      }
      const corpo = await r.json();
      leituras = Array.isArray(corpo) ? corpo : corpo.results || corpo.data || [];
    } catch (e) {
      resposta.motivo = `leitura de sensor indisponível: ${e && e.message}`;
      return resposta;
    }

    if (!Array.isArray(leituras) || leituras.length === 0) {
      resposta.motivo = 'nenhuma leitura de sensor para este talhao';
      return resposta;
    }

    // Mais recente por tipo; o backend já ordena por -timestamp.
    const porTipo = new Map();
    for (const l of leituras) {
      if (!l || l.tipo === undefined || !porTipo.has(l.tipo)) porTipo.set(l.tipo, l);
    }

    let medidos = 0;
    let suspeitos = 0;

    for (const [tipo, campo] of Object.entries(SENSOR_CLIMA)) {
      const l = porTipo.get(tipo);
      if (!l) continue;
      this._colocar(resposta, campo, l, tipo);
      if (resposta.valores[campo].fonte_dado === 'medido') medidos++;
      else suspeitos++;
    }
    for (const [tipo, campo] of Object.entries(SENSOR_SOLO)) {
      const l = porTipo.get(tipo);
      if (!l) continue;
      this._colocar(resposta, campo, l, tipo);
      if (resposta.valores[campo].fonte_dado === 'medido') medidos++;
      else suspeitos++;
    }

    if (medidos === 0 && suspeitos === 0) {
      resposta.motivo = 'as leituras existentes não cobrem os tipos de clima/solo conhecidos';
      return resposta;
    }

    resposta.origem = 'LeituraSensor';
    // Um campo suspect ainda é medição que existe. 'sem_dado' só quando nada.
    resposta.fonte_dado =
      medidos > 0 ? (suspeitos > 0 ? 'medido_com_ressalva' : 'medido') : 'suspect';
    if (suspeitos > 0) {
      resposta.motivo = `${suspeitos} campo(s) com qualidade 'suspect'`;
    }
    return resposta;
  }

  _colocar(resposta, campo, leitura, tipo) {
    const bruto = leitura.valor;
    const n = typeof bruto === 'number' ? bruto : parseFloat(bruto);
    if (!isFinite(n)) return;
    resposta.valores[campo] = {
      valor: n,
      unidade: leitura.unidade || null,
      // 'bad' e 'suspect' não são medido: são medição que não se pode usar.
      fonte_dado: leitura.qualidade === 'good' ? 'medido' : 'suspect',
      tipo_sensor: tipo,
      timestamp: leitura.timestamp || null,
      estacao: leitura.estacao_nome || null,
    };
  }

  /** Cache curto: leituras de sensor não mudam no meio de uma medição. */
  _cacheContexto(talhaoId, ttlMs = 300000) {
    this._cache = this._cache || new Map();
    const chave = String(talhaoId);
    const agora = Date.now();
    const guardado = this._cache.get(chave);
    if (guardado && agora - guardado.t < ttlMs) return guardado.ctx;
    return null;
  }

  _guardaContexto(talhaoId, ctx) {
    this._cache = this._cache || new Map();
    this._cache.set(String(talhaoId), { t: Date.now(), ctx });
  }

  async contextFor(talhaoId) {
    const guardado = this._cacheContexto(talhaoId);
    if (guardado) return guardado;
    const ctx = await this.collectContext(talhaoId);
    this._guardaContexto(talhaoId, ctx);
    return ctx;
  }

  // Create a new A/B experiment
  //
  // CHAVE E' O `uid`, NUNCA O `id`. O `uid` e' gerado aqui, no cliente, e e' a
  // identidade estavel do registo; o `id` do servidor chega mais tarde e nao
  // existe enquanto o produtor esta offline. Misturar os dois dava chaves
  // diferentes para o mesmo experimento conforme o sync — que e' o tipo de bug
  // que so aparece no campo, quando a rede vai e volta.
  createExperiment(config) {
    const exp = {
      uid: this._novoUid(),
      id: null, // preenchido pelo servidor no primeiro sincronizar()
      name: config.name,
      hypothesis: config.hypothesis,
      variable: config.variable, // e.g., 'fertilizante_npk', 'variedade', 'irrigacao'
      treatment_a: config.treatment_a, // {name: 'Controle', params: {...}}
      treatment_b: config.treatment_b, // {name: 'Tratamento', params: {...}}
      talhao_a: config.talhao_a, // Talhao ID
      talhao_b: config.talhao_b,
      cultura_id: config.cultura_id,
      metrics: config.metrics || ['produtividade', 'custo', 'qualidade'],
      start_date: new Date().toISOString(),
      end_date: config.end_date || null,
      status: 'active', // active, completed, archived
      sample_size: config.sample_size || 30,
      significance_level: config.significance_level || 0.05,
      versao_analise: config.versao_analise || '',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      _sincronizado: false,
    };

    this.experiments.set(exp.uid, exp);
    this.results.set(exp.uid, []);
    this.saveToStorage();
    return exp;
  }

  // Record measurement for a treatment
  //
  // `expUid` e' o `uid` do experimento, nunca o `id` — ver `createExperiment`.
  //
  // Passa a ser async porque o contexto (clima/solo) é lido da API e gravado
  // junto da medição — o contexto de uma medição é o que valia na hora dela,
  // não o que vale na hora da análise.
  async recordMeasurement(expUid, treatment, talhaoId, data) {
    const exp = this.experiments.get(expUid);
    if (!exp) throw new Error('Experimento não encontrado');

    const ctx = await this.contextFor(talhaoId);

    const measurement = {
      uid: this._novoUid(),
      exp_uid: expUid,
      treatment: treatment, // 'A' or 'B'
      talhao_id: talhaoId,
      data: data, // {produtividade: 65, custo: 1200, qualidade: 8.5}
      timestamp: new Date().toISOString(),
      _pendente: true, // A2b: ainda nao subiu
      metadata: {
        clima: ctx.valores,
        solo: {},
        // O carimbo vai no topo da medição: quem lê isto depois sabe se pode
        // acreditar, sem precisar ir abrir o contexto.
        fonte_dado: ctx.fonte_dado,
        origem: ctx.origem,
        motivo: ctx.motivo,
      },
    };

    // Separa clima de solo no mesmo dicionário de valores.
    for (const campo of Object.keys(SENSOR_SOLO)) {
      if (ctx.valores[campo] !== undefined) {
        measurement.metadata.solo[campo] = ctx.valores[campo];
        delete measurement.metadata.clima[campo];
      }
    }

    if (!this.results.has(expUid)) this.results.set(expUid, []);
    this.results.get(expUid).push(measurement);
    this.saveToStorage();
    return measurement;
  }

  /**
   * Statistical analysis - Welch's t-test for A/B comparison
   *
   * REGRA: só declara significância estatística se o contexto das medições for
   * medido. Um p-value sobre clima/solo inventado é um número sobre uma
   * constante — e é pior que não ter p-value, porque parece rigor.
   *
   * Quando o contexto é 'sem_dado', a análise corre e devolve as estatísticas
   * descritivas, mas `significativo` fica `null` e o motivo fica escrito.
   */
  async analyzeExperiment(expUid) {
    const exp = this.experiments.get(expUid);
    if (!exp) throw new Error('Experimento não encontrado');
    const results = this.results.get(expUid) || [];

    const groupA = results.filter((r) => r.treatment === 'A');
    const groupB = results.filter((r) => r.treatment === 'B');

    if (groupA.length < 2 || groupB.length < 2) {
      return {
        fonte_dado: 'sem_dado',
        error: 'Dados insuficientes para analise (minimo 2 por grupo)',
        sample_sizes: { a: groupA.length, b: groupB.length },
      };
    }

    // O contexto vem das medições. Se alguma não tem, registramos o motivo.
    const semContexto = results.filter((r) => !r.metadata || r.metadata.fonte_dado === 'sem_dado');
    const contextoMedido = results.length > 0 && semContexto.length === 0;
    const contextoSuspeito = !contextoMedido && semContexto.length < results.length;
    const fonteContexto = contextoMedido
      ? 'medido'
      : contextoSuspeito
        ? 'medido_com_ressalva'
        : 'sem_dado';
    const motivoContexto = contextoMedido
      ? null
      : `${semContexto.length} de ${results.length} medições sem contexto medido (clima/solo)`;

    const podeDeclarar = contextoMedido;
    const results_by_metric = {};

    for (const metric of exp.metrics) {
      const valoresA = groupA
        .map((r) => r.data[metric])
        .filter((v) => typeof v === 'number' && isFinite(v));
      const valoresB = groupB
        .map((r) => r.data[metric])
        .filter((v) => typeof v === 'number' && isFinite(v));

      if (valoresA.length < 2 || valoresB.length < 2) continue;

      const stats = this.ttest(valoresA, valoresB);
      const d = this.cohenD(valoresA, valoresB);

      // Variância zero em ambos os grupos não é um resultado, é uma divisão
      // por zero. Devolvemos o desvio e paramos — sem p-value inventado.
      if (!isFinite(stats.p)) {
        results_by_metric[metric] = {
          n_a: valoresA.length,
          n_b: valoresB.length,
          mean_a: this.mean(valoresA),
          mean_b: this.mean(valoresB),
          std_a: this.std(valoresA),
          std_b: this.std(valoresB),
          effect_size: isFinite(d) ? d : null,
          confidence_interval: null,
          t_statistic: isFinite(stats.t) ? stats.t : null,
          p_value: null,
          significativo: null,
          interpretacao: isFinite(d)
            ? `Diferenca observada de ${(this.mean(valoresA) - this.mean(valoresB)).toFixed(
                2
              )} ${metric}, mas sem variacao nos grupos: nao ha como separar efeito de ruido.`
            : 'Grupos sem variacao: nao ha variacao que testar.',
        };
        continue;
      }

      results_by_metric[metric] = {
        n_a: valoresA.length,
        n_b: valoresB.length,
        mean_a: this.mean(valoresA),
        mean_b: this.mean(valoresB),
        std_a: this.std(valoresA),
        std_b: this.std(valoresB),
        t_statistic: stats.t,
        p_value: stats.p,
        // null, não false: "não medido" e "não significativo" são coisas diferentes.
        significativo: podeDeclarar ? stats.p < (exp.significance_level || 0.05) : null,
        effect_size: isFinite(d) ? d : null,
        confidence_interval: this.confidenceInterval(valoresA, valoresB, 0.95),
        interpretacao: this.interpretResult(
          stats.p,
          valoresA,
          valoresB,
          exp.significance_level,
          podeDeclarar
        ),
      };
    }

    return {
      // Chaves em inglês, como o resto do código. Só o `fonte_dado` é em
      // português — é conceito de produto, não convenção de API.
      experiment: exp,
      // O carimbo do contexto, separado do das métricas: as métricas vêm de
      // que o produtor mediu no talhão (sempre medido), o contexto vem do
      // sensor (pode não existir).
      fonte_dado: fonteContexto,
      fonte_dado_metricas: 'medido',
      contexto_medido: contextoMedido,
      contexto_motivo: motivoContexto,
      sample_sizes: { a: groupA.length, b: groupB.length },
      metrics: results_by_metric,
      overall_conclusion: this.overallConclusion(
        results_by_metric,
        exp.significance_level,
        podeDeclarar
      ),
      analyzed_at: new Date().toISOString(),
    };
  }

  // Welch's t-test (unequal variances)
  ttest(a, b) {
    const n1 = a.length,
      n2 = b.length;
    const var1 = this.variance(a),
      var2 = this.variance(b);

    const se = Math.sqrt(var1 / n1 + var2 / n2);
    const t = (this.mean(a) - this.mean(b)) / se;

    // Welch-Satterthwaite degrees of freedom
    const df =
      Math.pow(var1 / n1 + var2 / n2, 2) /
      (Math.pow(var1 / n1, 2) / (n1 - 1) + Math.pow(var2 / n2, 2) / (n2 - 1));

    // Ver `twoTailedPValue`. Esta chamada já devolve o p-value bilateral.
    const p = this.twoTailedPValue(t, df);

    return { t, df, p };
  }

  // Cohen's d effect size
  cohenD(a, b) {
    const pooledSD = Math.sqrt(
      ((a.length - 1) * this.variance(a) + (b.length - 1) * this.variance(b)) /
        (a.length + b.length - 2)
    );
    if (pooledSD === 0) return NaN;
    return (this.mean(a) - this.mean(b)) / pooledSD;
  }

  // 95% Confidence Interval for difference of means
  confidenceInterval(a, b, confidence = 0.95) {
    const n1 = a.length,
      n2 = b.length;

    const se = Math.sqrt(this.variance(a) / n1 + this.variance(b) / n2);
    if (se === 0) return null;
    const df =
      Math.pow(this.variance(a) / n1 + this.variance(b) / n2, 2) /
      (Math.pow(this.variance(a) / n1, 2) / (n1 - 1) +
        Math.pow(this.variance(b) / n2, 2) / (n2 - 1));

    const t = this.criticalT(1 - confidence, df);
    const margin = t * Math.sqrt(this.variance(a) / n1 + this.variance(b) / n2);
    const diff = this.mean(a) - this.mean(b);

    return [diff - margin, diff + margin];
  }

  /**
   * p-value BILATERAL para a distribuição t, por integração de Simpson.
   *
   *   P(|T| >= |t|) = 1 - 2 * integral_0^|t| f(u) du
   *
   * POR QUE MUDOU DE MÉTODO — e esta é a parte que interessa:
   *
   * A versão anterior usava a beta regularizada
   * `I_{df/(df+t^2)}(df/2, 1/2)` com uma fração contínua. Esse caminho tem
   * um defeito silencioso: quando `b` é inteiro, o coeficiente `m*(b-m)`
   * zera em `m == b`, o quociente `d*c` fica exactamente 1, e a condição de
   * paragem dispara ANTES da convergência. Não falhava — parava cedo e
   * devolvia um número plausível e errado.
   *
   * Medido contra tabelas t publicadas (erro do p-value):
   *      df=18  t=1.73406   esperado 0.10   beta 0.095608   aqui 0.100001
   *      df=18  t=2.10092   esperado 0.05   beta 0.048817   aqui 0.050000
   *      df=10  t=1.81246   esperado 0.10   beta 0.097422   aqui 0.100000
   *      df=5   t=2.01505   esperado 0.10   beta 0.099250   aqui 0.100000
   * A beta erra ~4% em todos os casos. E o chamador ainda multiplicava o
   * resultado por 2, o que a tornava ~2x errada.
   *
   * A integração de Simpson sobre [0, |t|] reproduz as tabelas com 6 casas.
   * Custa ~2000 avaliacoes da densidade — irrelevante para uma analise que
   * corre uma vez, e era o que tornava a máquina antiga proprietaria de um
   * bug que ninguém veria.
   *
   * df = 1 (Cauchy) fica de fora: a densidade tem 1/u em zero e Simpson nao
   * converge. df=1 so acontece com n=2 em ambos os grupos. Usa-se a forma
   * fechada, e `analyzeExperiment` trata esse caso a parte.
   */
  twoTailedPValue(t, df, N) {
    if (!isFinite(t) || !isFinite(df) || df <= 0) return NaN;
    const absT = Math.abs(t);
    if (absT === 0) return 1;

    // Cauchy: P(|T|>|t|) = 1 - (2/pi) * arctan(|t|)
    if (df === 1) return 1 - (2 / Math.PI) * Math.atan(absT);

    const passos = N || 2000;
    const h = absT / passos;
    let soma = this.tDensity(0, df) + this.tDensity(absT, df);
    for (let i = 1; i < passos; i++) {
      soma += (i % 2 ? 4 : 2) * this.tDensity(i * h, df);
    }
    const cdf = (soma * h) / 3;
    const p = 1 - 2 * cdf;
    // Erro de arredondamento pode dar -1e-16 ou 1+1e-16.
    return Math.min(1, Math.max(0, p));
  }

  /** Densidade da distribuição t. */
  tDensity(u, df) {
    const lg = this.logGamma((df + 1) / 2) - this.logGamma(df / 2);
    return (Math.exp(lg) / Math.sqrt(df * Math.PI)) * Math.pow(1 + (u * u) / df, -(df + 1) / 2);
  }

  /**
   * Valor critico t para um p-value alvo, por bisseccao sobre `twoTailedPValue`.
   *
   * Antes usava `tInverse`, que era uma expansao de Cornish-Fisher e uma
   * `normalInverse` de Acklam — duas aproximacoes encadeadas, uma delas
   * inventada no proprio ficheiro. Isto inverte a MESMA funcao que produz o
   * p-value, entao o intervalo de confianca e o p-value nunca se contradizem.
   */
  criticalT(pTarget, df) {
    if (!isFinite(pTarget) || !isFinite(df) || df <= 0) return NaN;
    if (pTarget >= 1) return 0;
    if (pTarget <= 0) return Infinity;
    let lo = 0;
    let hi = 1;
    while (this.twoTailedPValue(hi, df) > pTarget && hi < 1e6) hi *= 2;
    for (let i = 0; i < 200; i++) {
      const mid = (lo + hi) / 2;
      if (this.twoTailedPValue(mid, df) > pTarget) lo = mid;
      else hi = mid;
    }
    return (lo + hi) / 2;
  }

  // Log gamma function (Lanczos approximation)
  logGamma(z) {
    const p = [
      676.5203681218851, -1259.1392167224028, 771.32342877765313, -176.61502916214059,
      12.507343278686905, -0.13857109526572012, 9.9843695780195716e-6, 1.5056327351493116e-7,
    ];

    if (z < 0.5) return Math.log(Math.PI / Math.sin(Math.PI * z)) - this.logGamma(1 - z);

    z -= 1;
    let x = 0.99999999999980993;
    for (let i = 0; i < p.length; i++) x += p[i] / (z + i + 1);
    const t = z + 7.5;
    return 0.5 * Math.log(2 * Math.PI) + (z + 0.5) * Math.log(t) - t + Math.log(x);
  }

  mean(arr) {
    return arr.reduce((a, b) => a + b, 0) / arr.length;
  }
  variance(arr) {
    const m = this.mean(arr);
    return arr.reduce((a, b) => a + (b - m) ** 2, 0) / (arr.length - 1);
  }
  std(arr) {
    return Math.sqrt(this.variance(arr));
  }

  interpretResult(p, a, b, alpha = 0.05, podeDeclarar = true) {
    // Sem contexto medido, o p-value descreve as medias do produtor — e nada
    // sobre a causa. Dizer "significante" aqui seria inventar Attribution.
    if (!podeDeclarar) {
      const diff = this.mean(a) - this.mean(b);
      return (
        `Diferenca observada de ${diff.toFixed(2)} (A-B). ` +
        `Sem clima/solo medido para estas medicoes, portanto NAO e possivel ` +
        `atribuir a diferenca ao tratamento (p = ${p.toFixed(4)} e descritivo).`
      );
    }
    if (p >= alpha) return 'Não há diferença estatisticamente significativa (p ≥ ' + alpha + ')';
    const diff = this.mean(a) - this.mean(b);
    const direction = diff > 0 ? 'A > B' : 'B > A';
    return `Diferença significativa (p = ${p.toFixed(4)}). ${direction}.`;
  }

  overallConclusion(results, alpha, podeDeclarar = true) {
    const avaliados = Object.values(results);
    if (!avaliados.length) return 'Nenhuma métrica com dados suficientes para comparar.';
    if (!podeDeclarar) {
      return (
        `${avaliados.length} métrica(s) comparada(s) descritivamente. ` +
        `Nenhuma conclusão de causalidade: falta clima/solo medido nas medições.`
      );
    }
    const sig = avaliados.filter((r) => r.significado === true);
    if (!sig.length) return 'Nenhuma métrica mostrou diferença significativa.';
    return `${sig.length} de ${avaliados.length} métricas com diferença significativa (p < ${alpha}).`;
  }

  // ======================================================================
  // A2b — PERSISTENCIA. O servidor e' a fonte de verdade; o local e' cache.
  //
  // O QUE MUDOU E POR QUE
  // ----------------------
  // Antes disto tudo vivia em `localStorage` e morria com a cache do
  // navegador. O produtor que limpou os dados perdeu meses de medições, e
  // ninguem mais — comprador, cooperativa, investidor — nunca viu nenhuma.
  //
  // **O localStorage nao foi removido.** O produto promete offline completo
  // (PWA) e o produtor esta no talhao sem rede; tira-lo seria tirar uma
  // promessa. A convencao da casa ja estava feita em `data-sync.js`: local
  // como cache optimista, servidor como fonte de verdade, e `_pending` como a
  // bandeira de "ainda nao subiu". Segue-se a convencao em vez de a substituir.
  //
  // A DIFFERENCA QUE IMPORTA: IDEMPOTENCIA
  // -------------------------------------
  // `data-sync.js` faz `item.id ? PUT : POST`. Se o POST chega ao servidor mas
  // a resposta nao chega ao cliente, o `item.id` continua falso, o produtor
  // volta a sincronizar, e o servidor cria um DUPLICADO — sem forma de saber
  // que e' o mesmo registo.
  //
  // Aqui cada objecto tem `uid` (UUID do cliente) gerado ANTES do envio, e o
  // servidor faz upsert por `uid`. O mesmo push duas vezes da o mesmo
  // registo. Ver `app/api/views/experimento.py`.
  // ======================================================================

  /** O `uid` e' o que torna o reenvio idempotente. Gerado no cliente, uma vez. */
  _novoUid() {
    if (typeof crypto !== 'undefined' && crypto.randomUUID) return crypto.randomUUID();
    // Fallback para onde nao ha `crypto.randomUUID` (contexto nao seguro).
    // Nao e' criptografico e nao precisa de ser: so tem de ser unico no
    // dispositivo. Um contador + timestamp chega, e o servidor trata chaves
    // iguais de outro dispositivo como dois registos diferentes — que e' o
    // comportamento correcto.
    this._seq = (this._seq || 0) + 1;
    return `u-${Date.now()}-${this._seq}-${Math.random().toString(16).slice(2, 10)}`;
  }

  _csrf() {
    if (typeof getCSRFToken === 'function') return getCSRFToken();
    const m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return m ? decodeURIComponent(m[1]) : '';
  }

  /**
   * Marca como pendente tudo o que ainda nao foi confirmado pelo servidor.
   *
   * Existe por causa de um caso concreto: registos gravados por uma versao
   * anterior do ficheiro, que nao tinham o campo `_pendente`. Sem isto, esses
   * registos ficariam presos no dispositivo para sempre — o produtor via-os na
   * lista e they'd nunca subirem.
   *
   * Devolve quantos MARCOU, nao quantos ha pendentes. Para contar, ha
   * `_contarPendentes()`. Confundir as duas coisas dá um zero que parece dizer
   * "nada por enviar" quando há coisas por enviar — que é o tipo de numero
   * enganador que a §10 desta carta já apanhou duas vezes.
   */
  _marcaPendentes() {
    let n = 0;
    for (const exp of this.experiments.values()) {
      for (const m of this.results.get(exp.uid) || []) {
        if (!m._pendente && !m._sincronizado) {
          m._pendente = true;
          n++;
        }
      }
    }
    return n;
  }

  /** Quantas medicoes estao por enviar. Nao altera nada. */
  _contarPendentes() {
    let n = 0;
    for (const exp of this.experiments.values()) {
      for (const m of this.results.get(exp.uid) || []) {
        if (m._pendente && !m._sincronizado) n++;
      }
    }
    return n;
  }

  /**
   * Envia o que está pendente. Idempotente — pode ser chamada vezes seguidas.
   *
   * Devolve `{ ok, criados, ja_existiam, falhas }`. `ja_existiam > 0` num
   * reenvio e' o sinal de que o servidor nao duplicou.
   */
  async sincronizar() {
    if (this._aSincronizar) return { ok: false, motivo: 'sincronizacao em andamento' };
    this._aSincronizar = true;

    const resumo = { ok: true, criados: 0, ja_existiam: 0, falhas: 0, detalhe: [] };
    try {
      // 1) Os experimentos primeiro: uma medicao sem experimento no servidor
      //    e' orfa. A ordem nao e' cosmética.
      const expsPendentes = [...this.experiments.values()].filter((e) => !e._sincronizado);
      for (const exp of expsPendentes) {
        const corpo = this._experimentoParaApi(exp);
        const r = await fetch('/api/experimentos/', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': this._csrf() },
          credentials: 'same-origin',
          body: JSON.stringify(corpo),
        });
        if (!r.ok) {
          resumo.falhas++;
          resumo.detalhe.push({ tipo: 'experimento', uid: exp.uid, http: r.status });
          continue;
        }
        const gravado = await r.json();
        // O `id` do servidor passa a ser a chave local. A partir daqui a
        // medicao ja pode ser emparelhada sem ambiguidade.
        exp.id = gravado.id;
        exp._sincronizado = true;
        delete exp._pendente;
        this.experiments.set(exp.uid, exp);
        resumo.criados++;
      }

      // 2) As medicoes em lote — o caminho normal do offline.
      const lote = [];
      for (const exp of this.experiments.values()) {
        for (const m of this.results.get(exp.uid) || []) {
          if (m._pendente && !m._sincronizado) lote.push(this._medicaoParaApi(m, exp));
        }
      }
      if (lote.length) {
        const r = await fetch('/api/medicoes-experimentais/lote/', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': this._csrf() },
          credentials: 'same-origin',
          body: JSON.stringify({ medicoes: lote }),
        });
        if (r.ok) {
          const resposta = await r.json();
          resumo.criados += resposta.criados || 0;
          resumo.ja_existiam += resposta.ja_existiam || 0;
          resumo.falhas += resposta.rejeitados || 0;
          for (const m of this._todasAsMedicoes()) {
            if (m._pendente) {
              if ((resposta.erros || []).some((e) => e.indice === this._indiceDe(lote, m))) {
                // Rejeitado: fica pendente, e a proxima tentativa volta a tentar.
                // Perder a medicao seria pior do que tentar duas vezes.
                continue;
              }
              m._pendente = false;
              m._sincronizado = true;
            }
          }
        } else {
          resumo.falhas += lote.length;
          resumo.detalhe.push({ tipo: 'lote_medicoes', http: r.status });
        }
      }

      this.saveToStorage();
      resumo.ok = resumo.falhas === 0;
      return resumo;
    } catch (e) {
      resumo.ok = false;
      resumo.erro = e && e.message;
      // Nao se apaga nada: a proxima chamada tenta outra vez. E' a diferenca
      // entre "ficou para a proxima" e "perdeu-se a medicao".
      this.saveToStorage();
      return resumo;
    } finally {
      this._aSincronizar = false;
    }
  }

  _todasAsMedicoes() {
    const todas = [];
    for (const exp of this.experiments.values()) {
      for (const m of this.results.get(exp.uid) || []) todas.push(m);
    }
    return todas;
  }

  _indiceDe(lote, medicao) {
    return lote.findIndex((x) => x.uid === medicao.uid);
  }

  _experimentoParaApi(exp) {
    return {
      uid: exp.uid,
      nome: exp.name,
      hypothesis: exp.hypothesis,
      variavel: exp.variable,
      tratamento_a: exp.treatment_a || {},
      tratamento_b: exp.treatment_b || {},
      talhao_a: exp.talhao_a ?? null,
      talhao_b: exp.talhao_b ?? null,
      metricas: exp.metrics || [],
      significance_level: exp.significance_level ?? 0.05,
      contexto_inicial: exp.contexto_inicial || {},
      versao_analise: exp.versao_analise || '',
    };
  }

  _medicaoParaApi(m, exp) {
    return {
      uid: m.uid,
      experimento_uid: exp.uid,
      tratamento: m.treatment,
      talhao: m.talhao_id ?? null,
      dados: m.data || {},
      contexto: m.metadata || {},
      fonte_dado: m.metadata ? m.metadata.fonte_dado || 'sem_dado' : 'sem_dado',
      // O relogio do CLIENTE, de proposito: e' a condicao em que o produtor
      // mediu. `sincronizado_em` e' do servidor e nao viaja.
      registado_em: m.timestamp,
    };
  }

  /**
   * Puxa do servidor o que o produtor tem em falta.
   *
   * `pull` e' um merge por `uid`, nao uma substituicao: o que esta so no
   * aparelho (ainda pendente) continua la. Substituir tudo seria deitar fora
   * medicoes feitas offline — que e' o pior sitio possivel para perder dados.
   */
  async puxarDoServidor() {
    const r = await fetch('/api/experimentos/?page_size=200', {
      headers: { Accept: 'application/json' },
      credentials: 'same-origin',
    });
    if (!r.ok) return { ok: false, http: r.status };

    const corpo = await r.json();
    const lista = Array.isArray(corpo) ? corpo : corpo.results || [];

    let novos = 0;
    for (const exp of lista) {
      const local = this.experiments.get(exp.uid);
      if (local) {
        // Ja existe aqui. Ganha o que tem mais medicoes — o servidor e' a
        // fonte de verdade, mas o que so existe local ainda nao subiu.
        if (!local._sincronizado && exp.total_medicoes > 0) continue;
      } else {
        this.experiments.set(exp.uid, {
          id: exp.id,
          uid: exp.uid,
          name: exp.nome,
          hypothesis: exp.hypothesis,
          variable: exp.variavel,
          treatment_a: exp.tratamento_a,
          treatment_b: exp.tratamento_b,
          talhao_a: exp.talhao_a,
          talhao_b: exp.talhao_b,
          metrics: exp.metricas,
          significance_level: exp.significance_level,
          contexto_inicial: exp.contexto_inicial,
          versao_analise: exp.versao_analise,
          _sincronizado: true,
        });
        novos++;
      }
      if (!this.results.has(exp.uid)) this.results.set(exp.uid, []);
    }

    this.saveToStorage();
    return { ok: true, experimentos: lista.length, novos };
  }

  // --- Cache local -------------------------------------------------------
  //
  // Continua a existir, e de proposito: e' o que permite working offline no
  // talhao. Nao e' mais a fonte de verdade — e' a fila de saida.

  saveToStorage() {
    try {
      localStorage.setItem(
        'ampliagro_experimentos_v2',
        JSON.stringify([...this.experiments.entries()])
      );
      localStorage.setItem('ampliagro_medicoes_v2', JSON.stringify([...this.results.entries()]));
    } catch (e) {
      // Cota cheia e' possivel: 40 experimentos com contexto JSON nao ocupam
      // muito, mas um `localStorage` partilhado com o resto da app pode encher.
      // Perder a cache e' aceitavel; perder o registo exigiria confirmacao.
      console.warn('[ExperimentEngine] nao foi possivel gravar a cache local:', e && e.message);
    }
  }

  loadFromStorage() {
    try {
      const exps = JSON.parse(localStorage.getItem('ampliagro_experimentos_v2') || '[]');
      const ress = JSON.parse(localStorage.getItem('ampliagro_medicoes_v2') || '[]');
      this.experiments = new Map(exps);
      this.results = new Map(ress);
      return { ok: true, experimentos: this.experiments.size };
    } catch (e) {
      console.warn('[ExperimentEngine] nao foi possivel ler a cache local:', e && e.message);
      return { ok: false, erro: e && e.message };
    }
  }
}

// Global instance
window.ExperimentEngine = new ExperimentEngine();
window.ExperimentEngine.loadFromStorage();

// Sincroniza quando a rede volta. `online` e' o evento certo para o offline:
// dispara quando o `navigator` sabe que ha rede, sem ser preciso sondar.
if (typeof window !== 'undefined' && window.addEventListener) {
  window.addEventListener('online', () => {
    window.ExperimentEngine.sincronizar().then((r) => {
      if (r && r.criados)
        console.info(`[ExperimentEngine] ${r.criados} registo(s) sincronizado(s)`);
    });
  });
}

// Export
if (typeof module !== 'undefined') module.exports = ExperimentEngine;
