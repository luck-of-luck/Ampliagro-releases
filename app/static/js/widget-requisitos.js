/**
 * REGISTO DE REQUISITOS DOS WIDGETS
 * ============================================================================
 * Para cada widget: o que ele precisa para mostrar um número, e como confirmar
 * que esse número existe. A paleta usa isto para DIZER ao produtor o que falta,
 * em vez de esconder o widget — um menu que não explica porquê é um menu que
 * o produtor contorna.
 *
 * PORQUÊ UM REGISTO E NÃO UM `if` ESPALHADO
 * ------------------------------------------
 * Widgets sem dados já não mostram números inventados (há um `default: null` no
 * `getWidgetDataFromAPI` e um `SEM_DADO` no `generateWidgetContent`). O que
 * faltava era a OUTRA metade: antes de o produtor escolher, dizer-lhe "isto vai
 * ficar vazio porque ainda não tem lançamentos financeiros". É esta tabela que
 * faz essa ligação, e é a única fonte de verdade sobre o assunto.
 *
 * COMO SE LÊ UM `precisa`
 * -----------------------
 *   precisa: [ 'chave', ... ]   routes no payload de /api/widget-data/
 *   se uma rota estiver VAZIA (array, {} ou contagem 0), o widget diz o que
 *   falta em vez de mostrar moldura vazia.
 *
 *   `fn` é uma alternativa quando o requisito não é uma rota (ex.: o produtor
 *   pode ter sensores mas nenhuma estação com leitura boa).
 *
 * Os ids NÃO listados aqui ficam `pronto: true` por omissão — o registo é
 * exhaustivo para os widgets com dadoscondicoes, e aberto para os restantes. Um
 * widget novo sem entrada não é bloqueado: aparece e o renderizador trata-o.
 */

(function (global) {
  'use strict';

  // ── Utilitários de leitura ──────────────────────────────────────────────
  // Todos devolvem `false` (= não há) ou um valor verdadeiro. Nenhum inventa.

  function naoVazio(v) {
    if (v == null) return false;
    if (Array.isArray(v)) return v.length > 0;
    if (typeof v === 'number') return true;
    if (typeof v === 'object') return Object.keys(v).length > 0;
    if (typeof v === 'string') return v.trim().length > 0;
    return Boolean(v);
  }

  function rota(d, caminho) {
    // "financeiro.lancamentos" -> navega sem lançar
    var atual = d;
    var partes = String(caminho).split('.');
    for (var i = 0; i < partes.length; i++) {
      if (atual == null) return undefined;
      atual = atual[partes[i]];
    }
    return atual;
  }

  /** Há CONTAGENS > 0 num bloco? `{total_safras: 3}` é dado; `{}` não é. */
  function algumContagem(d, prefixo) {
    var bloco = d && d[prefixo];
    if (!bloco || typeof bloco !== 'object') return false;
    for (var k in bloco) {
      if (Object.prototype.hasOwnProperty.call(bloco, k)) {
        var v = bloco[k];
        if (typeof v === 'number' && v > 0) return true;
        if (Array.isArray(v) && v.length > 0) return true;
        if (v && typeof v === 'object' && !Array.isArray(v)) {
          for (var j in v) {
            if (Object.prototype.hasOwnProperty.call(v, j)) {
              var w = v[j];
              if (typeof w === 'number' && w > 0) return true;
              if (Array.isArray(w) && w.length > 0) return true;
            }
          }
        }
      }
    }
    return false;
  }

  // ── O registo ────────────────────────────────────────────────────────────
  //
  // `falta` é a frase que o produtor lê. Escreve-se na 2ª pessoa e diz o que
  // fazer, não só o que falta: "cadastre uma safra" ensina, "sem safras"
  // só informa.
  var REQUISITOS = {
    // ── Financeiro: todos dependem de lançamentos ──────────────────────────
    'kpi-caixa': {
      precisa: ['financeiro.lancamentos'],
      falta: 'Cadastre lançamentos financeiros para ver o saldo.',
    },
    'kpi-roi': {
      precisa: ['financeiro.lancamentos'],
      falta: 'Cadastre receitas e despesas para calcular o ROI.',
    },
    'kpi-custo': {
      precisa: ['financeiro.lancamentos', 'propriedade.area_total'],
      falta: 'Cadastre despesas e a área da propriedade para calcular o custo por hectare.',
    },
    'kpi-margem-bruta': {
      precisa: ['financeiro.lancamentos'],
      falta: 'Cadastre lançamentos para ver a margem por hectare.',
    },
    'table-financeiro': {
      precisa: ['financeiro.lancamentos'],
      falta: 'Cadastre lançamentos para ver a tabela financeira.',
    },
    'chart-financeiro': {
      precisa: ['financeiro.mensal'],
      falta: 'Cadastre lançamentos neste ano para ver o gráfico.',
    },
    'table-vendas-regiao': {
      precisa: ['financeiro.lancamentos'],
      falta: 'Cadastre lançamentos para ver as vendas por região.',
    },
    'kpi-pedidos': {
      precisa: ['financeiro.lancamentos'],
      falta: 'Cadastre lançamentos para ver os pedidos de venda.',
    },
    'kpi-melhor-cliente': {
      precisa: ['safras.items'],
      falta: 'Cadastre safras para ver o melhor talhão.',
    },

    // ── Produção: dependem de safras ───────────────────────────────────────
    'kpi-produtividade': {
      precisa: ['safras.items'],
      falta: 'Cadastre uma safra com produção para ver a produtividade.',
    },
    'kpi-vendas-totais': {
      precisa: ['safras.items'],
      falta: 'Cadastre safras para ver a produção total.',
    },
    'chart-safras': {
      precisa: ['safras.items'],
      falta: 'Cadastre safras para ver o gráfico por ano.',
    },
    'table-safras': {
      precisa: ['safras.items'],
      falta: 'Cadastre safras para ver a tabela.',
    },
    'table-data': {
      precisa: ['safras.items'],
      falta: 'Cadastre safras para ver os dados.',
    },
    'chart-area': {
      precisa: ['safras.items'],
      falta: 'Cadastre safras para ver a área por cultura.',
    },
    'chart-mixed': {
      precisa: ['safras.items'],
      falta: 'Cadastre safras para ver o gráfico combinado.',
    },
    'list-colheita': {
      precisa: ['safras.items'],
      falta: 'Cadastre safras com data de colheita para ver a agenda.',
    },

    // ── Talhões ────────────────────────────────────────────────────────────
    'kpi-area': {
      precisa: ['propriedade'],
      falta: 'Desenhe a propriedade no cadastro para ver a área.',
    },
    'kpi-vra-ndvi': {
      precisa: ['talhoes.items'],
      falta: 'Cadastre talhões com geometria para ver o NDVI por satélite.',
    },
    'kpi-guidance-ab': {
      precisa: ['talhoes.items'],
      falta: 'Cadastre talhões para ver o guidance A-B.',
    },
    'kpi-rota-otimizada': {
      precisa: ['talhoes.items'],
      falta: 'Cadastre talhões para ver a rota otimizada.',
    },
    'kpi-as-applied': {
      precisa: ['aplicacoes'],
      falta: 'Cadastre aplicações para comparar o aplicado com o planeado.',
    },
    'kpi-praga-ai': {
      precisa: ['talhoes.items'],
      falta: 'Cadastre talhões para a IA procurar pragas.',
    },
    'kpi-ai-cultura': {
      precisa: ['talhoes.items'],
      falta: 'Cadastre talhões para a IA identificar a cultura por satélite.',
    },

    // ── Estoque e insumos ──────────────────────────────────────────────────
    'kpi-alertas': {
      precisa: ['insumos'],
      falta: 'Cadastre insumos com stock mínimo para receber alertas.',
    },
    'chart-estoque': {
      precisa: ['estoque.items'],
      falta: 'Cadastre itens de estoque para ver o gráfico.',
    },
    'table-estoque': {
      precisa: ['estoque.items'],
      falta: 'Cadastre itens de estoque para ver a tabela.',
    },
    'table-insumos': {
      precisa: ['insumos'],
      falta: 'Cadastre insumos para ver a tabela.',
    },

    // ── Maquinário ─────────────────────────────────────────────────────────
    'kpi-manutencoes': {
      precisa: ['maquinarios.items'],
      falta: 'Cadastre maquinários para ver as revisões.',
    },
    'list-manutencao': {
      precisa: ['maquinarios.items'],
      falta: 'Cadastre maquinários para ver a manutenção.',
    },

    // ── Rebanho e apiário ──────────────────────────────────────────────────
    'kpi-animais': {
      precisa: ['animais.items'],
      falta: 'Cadastre animais para ver o rebanho.',
    },
    'chart-producao-animal': {
      precisa: ['producao_animal'],
      falta: 'Cadastre produção animal para ver o gráfico.',
    },
    'list-colmeias': {
      precisa: ['apiario.items'],
      falta: 'Cadastre apiário para ver as colmeias.',
    },

    // ── Equipa e agenda ────────────────────────────────────────────────────
    'kpi-funcionarios': {
      precisa: ['funcionarios.items'],
      falta: 'Cadastre funcionários para ver a equipa.',
    },
    'list-agenda': {
      precisa: ['funcionarios.items'],
      falta: 'Cadastre funcionários para ver a agenda.',
    },
    'list-tarefas': {
      precisa: [],
      falta: 'Ainda não há tarefas. Crie uma na aba Operação para a ver aqui.',
      sempreVazio: true,
    },
    'list-tasks': {
      precisa: [],
      falta: 'Ainda não há tarefas. Crie uma na aba Operação para a ver aqui.',
      sempreVazio: true,
    },
    'calendar-widget': {
      precisa: [],
      falta: 'Ainda não há nada agendado.',
      sempreVazio: true,
    },
    'kpi-calendario': {
      precisa: [],
      falta: 'Ainda não há nada agendado.',
      sempreVazio: true,
    },

    // ── Clima e sensores ───────────────────────────────────────────────────
    'kpi-clima': {
      precisa: ['weather'],
      falta: 'Não foi possível obter a previsão para esta propriedade.',
    },
    'weather-widget': {
      precisa: ['weather'],
      falta: 'Não foi possível obter a previsão para esta propriedade.',
    },
    'kpi-chuva-1km': {
      precisa: ['weather'],
      falta: 'Registe as coordenadas da propriedade (mapa ou GPS) para ver a chuva.',
    },
    'kpi-sensores': {
      fn: function (d) {
        return naoVazio(d && d.sensores);
      },
      precisa: [],
      falta: 'Registe uma estação meteorológica para ver leituras de sensor.',
    },

    // ── Propriedade ────────────────────────────────────────────────────────
    'widget-resumo': {
      precisa: ['propriedade'],
      falta: 'Desenhe a propriedade no cadastro.',
    },
  };

  /**
   * Avalia um widget contra o payload de /api/widget-data/.
   *
   * Devolve SEMPRE um dos três estados:
   *   'pronto'    — tem o que precisa
   *   'falta'     — falta-lhe uma fonte, e `msg` diz qual
   *   'sem-fonte' — não há registo e não é renderizável (nunca deve acontecer,
   *                 e o chamador deve tratá-lo como erro, não como "vazio")
   */
  function avaliar(widgetId, dados) {
    var reg = REQUISITOS[widgetId];
    if (!reg) {
      // Sem registo: presume pronto. O registo cobre os que precisam de uma
      // fonte; os restantes são renderizados sem condicoes.
      return { estado: 'pronto', msg: '' };
    }

    var d = dados || {};

    if (reg.fn) {
      try {
        if (reg.fn(d)) return { estado: 'pronto', msg: '' };
      } catch (e) {
        /* um avaliador que rebenta não pode travar o menu */
      }
      return { estado: 'falta', msg: reg.falta || '' };
    }

    if (reg.sempreVazio) {
      return { estado: 'falta', msg: reg.falta || '' };
    }

    var rotas = reg.precisa || [];
    for (var i = 0; i < rotas.length; i++) {
      if (!naoVazio(rota(d, rotas[i]))) {
        return { estado: 'falta', msg: reg.falta || '' };
      }
    }
    // Um requisito que depende de contagem precisa da contagem, não do objecto.
    if (rota(d, 'financeiro') && reg.precisa.indexOf('financeiro.lancamentos') !== -1) {
      if (!algumContagem(d, 'financeiro')) {
        return { estado: 'falta', msg: reg.falta || '' };
      }
    }
    return { estado: 'pronto', msg: '' };
  }

  global.WIDGET_REQUISITOS = REQUISITOS;
  global.avaliarWidgetRequisito = avaliar;
})(window);
