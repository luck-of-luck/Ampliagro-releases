/* A SÉRIE em gráfico — o card que o modo CRIAR pendura na conversa.
 *
 * QUEM USA, E QUANDO
 * ==================
 * Qualquer resposta (local ou sandbox) que traga `dados.serie` ganha peça
 * visual quando o modo CRIAR está ligado — sem mexer no handler que a
 * produziu. O contrato é o mesmo que o servidor valida (`chamado.py:
 * serie_valida`): {titulo, rotulo, colunas:[x, y], linhas:[[rot, num]]}.
 * Sem modo, nada se desenha: prosa pura, como sempre foi.
 *
 * Compacto (chat): título + colunas. Expandido (sem palco à vista, com modo
 * painel ligado): + tabela + total. O CSS viaja junto (como o Chamado faz
 * com `garanteEstilo`): um módulo que desenha e não leva o estilo é um
 * módulo que depende da página onde caiu.
 */

(function () {
  'use strict';

  var MAX_LINHAS = 31;

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  function numValido(v) {
    return typeof v === 'number' && isFinite(v);
  }

  function valida(serie) {
    if (!serie || typeof serie !== 'object') return false;
    if (typeof serie.titulo !== 'string' || !serie.titulo.trim()) return false;
    if (typeof serie.rotulo !== 'string' || !serie.rotulo.trim()) return false;
    if (
      !Array.isArray(serie.colunas) ||
      serie.colunas.length !== 2 ||
      typeof serie.colunas[0] !== 'string' ||
      typeof serie.colunas[1] !== 'string'
    ) {
      return false;
    }
    if (!Array.isArray(serie.linhas) || !serie.linhas.length) return false;
    if (serie.linhas.length > MAX_LINHAS) return false;
    for (var i = 0; i < serie.linhas.length; i++) {
      var l = serie.linhas[i];
      if (!Array.isArray(l) || l.length !== 2) return false;
      if (typeof l[0] !== 'string' || !l[0].trim()) return false;
      if (!numValido(l[1])) return false;
    }
    return true;
  }

  function garanteEstilo() {
    if (document.getElementById('ia-serie-estilo')) return;
    var s = document.createElement('style');
    s.id = 'ia-serie-estilo';
    s.textContent = [
      '.ia-serie-card{margin:8px 12px;border:1px solid var(--cor-borda,#e5e7eb);border-radius:12px;overflow:hidden;background:var(--cor-fundo-card,#fff);}',
      '.ia-serie-topo{padding:7px 10px;font-size:11px;font-weight:700;letter-spacing:.02em;text-transform:uppercase;color:var(--cor-primaria,#0f9d6e);background:var(--cor-suave,#f3f7f5);border-bottom:1px solid var(--cor-borda,#e5e7eb);}',
      '.ia-serie-barras{display:flex;align-items:flex-end;gap:6px;height:120px;padding:10px 10px 2px;}',
      '.ia-serie-col{flex:1 1 0;display:flex;flex-direction:column;justify-content:flex-end;align-items:center;gap:4px;min-width:0;height:100%;}',
      '.ia-serie-barra{width:100%;background:rgba(15,157,110,.55);border-radius:4px 4px 0 0;min-height:2px;}',
      '.ia-serie-col b{font-size:9px;font-weight:500;opacity:.65;text-align:center;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:100%;}',
      '.ia-serie-col i{font-size:9px;font-style:normal;font-weight:700;}',
      '.ia-serie-tabela{width:100%;border-collapse:collapse;font-size:11.5px;}',
      '.ia-serie-tabela th{text-align:left;font-weight:600;opacity:.7;padding:5px 10px;border-top:1px solid var(--cor-borda,#e5e7eb);}',
      '.ia-serie-tabela td{padding:3px 10px;border-top:1px solid var(--cor-borda,#e5e7eb);}',
      '.ia-serie-total{display:flex;align-items:baseline;gap:8px;padding:8px 10px;}',
      '.ia-serie-total .v{font-size:1.3rem;font-weight:800;}',
      '.ia-serie-total .d{font-size:11px;opacity:.65;}',
      'html.dark .ia-serie-card{background:rgba(30,41,59,.35);border-color:rgba(59,130,246,.25);}',
      'html.dark .ia-serie-topo{background:rgba(30,41,59,.5);}',
    ].join('');
    document.head.appendChild(s);
  }

  function fmtNum(v) {
    try {
      return Number(v).toLocaleString('pt-BR', { maximumFractionDigits: 1 });
    } catch (e) {
      return String(v);
    }
  }

  function limpar() {
    var caixas = document.querySelectorAll('.ia-serie-card');
    for (var i = 0; i < caixas.length; i++) {
      if (caixas[i].parentNode) caixas[i].parentNode.removeChild(caixas[i]);
    }
  }

  /* Desenha o card no corpo da conversa. Devolve true desenhado.
   *
   * Sem `mostrar` parcial: ou a série inteira passa na validação ou nada
   * sai — meia série (só as colunas que prestam) é um gráfico que mente
   * por omissão. */
  function mostrar(serie, opts) {
    if (!valida(serie)) {
      if (window.console) console.warn('[IaSerie] série inválida, nada desenhado.');
      return false;
    }
    var corpo = document.getElementById('ia-chat-body');
    if (!corpo) return false;
    garanteEstilo();
    limpar();

    var linhas = serie.linhas;
    var maximo = 0;
    for (var i = 0; i < linhas.length; i++) {
      if (linhas[i][1] > maximo) maximo = linhas[i][1];
    }
    if (!maximo) maximo = 1;

    var box = document.createElement('div');
    box.className = 'ia-serie-card';

    var topo = document.createElement('div');
    topo.className = 'ia-serie-topo';
    topo.textContent = String(serie.titulo).slice(0, 120);
    box.appendChild(topo);

    var fita = document.createElement('div');
    fita.className = 'ia-serie-barras';
    fita.setAttribute('role', 'img');
    fita.setAttribute(
      'aria-label',
      String(serie.titulo) +
        ': ' +
        linhas
          .map(function (l) {
            return l[0] + ' ' + fmtNum(l[1]);
          })
          .join(', ')
    );
    linhas.forEach(function (l) {
      var col = document.createElement('div');
      col.className = 'ia-serie-col';
      col.title = l[0] + ': ' + fmtNum(l[1]) + ' ' + serie.rotulo;
      var barra = document.createElement('div');
      barra.className = 'ia-serie-barra';
      barra.style.height = Math.max(2, Math.round((l[1] / maximo) * 100)) + '%';
      var val = document.createElement('i');
      val.textContent = fmtNum(l[1]);
      var leg = document.createElement('b');
      leg.textContent = l[0];
      leg.title = l[0];
      col.appendChild(val);
      col.appendChild(barra);
      col.appendChild(leg);
      fita.appendChild(col);
    });
    box.appendChild(fita);

    if (opts && opts.expandido) {
      var total = 0;
      linhas.forEach(function (l) {
        total += l[1];
      });
      var tot = document.createElement('div');
      tot.className = 'ia-serie-total';
      var vv = document.createElement('span');
      vv.className = 'v';
      vv.textContent = fmtNum(Math.round(total * 10) / 10) + ' ' + serie.rotulo;
      var dd = document.createElement('span');
      dd.className = 'd';
      dd.textContent = 'total em ' + linhas.length + ' dias';
      tot.appendChild(vv);
      tot.appendChild(dd);
      box.appendChild(tot);

      var tab = document.createElement('table');
      tab.className = 'ia-serie-tabela';
      var thead = document.createElement('thead');
      var trh = document.createElement('tr');
      serie.colunas.forEach(function (c) {
        var th = document.createElement('th');
        th.textContent = c;
        trh.appendChild(th);
      });
      thead.appendChild(trh);
      tab.appendChild(thead);
      var tbody = document.createElement('tbody');
      linhas.forEach(function (l) {
        var tr = document.createElement('tr');
        var td0 = document.createElement('td');
        td0.textContent = l[0];
        var td1 = document.createElement('td');
        td1.textContent = fmtNum(l[1]) + ' ' + serie.rotulo;
        tr.appendChild(td0);
        tr.appendChild(td1);
        tbody.appendChild(tr);
      });
      tab.appendChild(tbody);
      box.appendChild(tab);
    }

    corpo.appendChild(box);
    corpo.scrollTop = corpo.scrollHeight;
    return true;
  }

  window.IaSerie = {
    mostrar: mostrar,
    limpar: limpar,
    valida: valida,
  };
})();
