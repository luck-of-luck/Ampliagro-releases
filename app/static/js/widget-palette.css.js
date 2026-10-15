/**
 * Paleta de Widgets — folha de estilos que não existia.
 * ============================================================================
 * O widget-palette.js escreve markup com ~20 classes (palette-card,
 * palette-card-title, palette-tabs, palette-search…) e NENHUM ficheiro de CSS
 * as definia. O resultado era um painel lateral que funcionava mas se lia como
 * texto solto: sem caixas, sem separações, sem botões.
 *
 * Aqui não se muda comportamento — só o que se vê. As regras seguem os mesmos
 * tokens que o resto do painel (--text-primary, --text-secondary, --card-bg)
 * com valores de recurso, para não dependerem de o tema estar definido no
 * momento em que a paleta abre.
 *
 * Duas decisões que valem a pena explicar:
 *
 * 1. palette-card.sem-dado não fica escondido nem opaco. Reduz-se a saturação
 *    do ícone e dá-se a frase do que falta. Um widget que ainda não tem dados é
 *    informação útil: o produtor vê o que o sistema sabe fazer e o que lhe falta
 *    para o fazer.
 *
 * 2. A grelha usa auto-fill com minmax, não colunas fixas. A paleta vai de ~70
 *    a ~578 widgets (as culturas entram todas); com largura fixa uma metade
 *    ficaria fora do ecrã num portátil.
 *
 * NOTA SOBRE ACENTOS: nada dentro do CSS pode ter o acento grave que abre e
 * fecha templates literais em JavaScript. O CSS vive dentro de um desses, e um
 * acento a mais fecha a string ali — o ficheiro continua a passar a sintaxe e o
 * CSS deixa simplesmente de ser aplicado. Foi o que aconteceu na primeira
 * versão deste ficheiro, e a verificação de sintaxe não o apanha.
 */

(function () {
  'use strict';

  if (document.getElementById('widget-palette-base-css')) return;
  const st = document.createElement('style');
  st.id = 'widget-palette-base-css';
  st.textContent = `
/* ── Tokens locais ─────────────────────────────────────────────────────── */
#widget-palette-panel {
  --wp-bg: #ffffff;
  --wp-bg-soft: #f8fafc;
  --wp-fg: #0f172a;
  --wp-fg-2: #64748b;
  --wp-fg-3: #94a3b8;
  --wp-line: #e2e8f0;
  --wp-accent: #0f9d6e;
  --wp-accent-soft: rgba(15, 157, 110, .12);
  --wp-warn: #f59e0b;
  --wp-r: 12px;
  --wp-gap: 8px;
  /* NÃO se escreve display, position nem width aqui. O painel já é criado
     pelo JS com utilitários do Tailwind:
       "flex flex-col h-full max-w-sm w-full bg-white
        dark:bg-slate-900 border-l translate-x-full"
     Escrever um "position: fixed" aqui ganharia à especificidade do Tailwind e
     a paleta deixaria de poder fechar (o hidden do modal não a esconderia).
     Este ficheiro pinta o que o Tailwind não pinta: as ~20 classes
     palette-* que só existem aqui. */
  background: var(--wp-bg);
  color: var(--wp-fg);
  font-size: 13px;
  /* A paleta é uma coluna cheia de altura; o scroll fica no conteúdo. */
  overflow: hidden;
}
#widget-palette-modal { z-index: 2147483000; }

@media (prefers-color-scheme: dark) {
  #widget-palette-panel {
    --wp-bg: #0f172a; --wp-bg-soft: #1e293b;
    --wp-fg: #e2e8f0; --wp-fg-2: #94a3b8; --wp-fg-3: #64748b;
    --wp-line: #334155;
    --wp-accent-soft: rgba(16, 185, 129, .18);
    border-left-color: #334155;
  }
  #widget-palette-modal:not(.hidden) { background: rgba(2, 6, 23, .62); }
}
/* O painel segue o tema do app quando este define data-theme no <html>. */
[data-theme='dark'] #widget-palette-panel,
.dark #widget-palette-panel {
  --wp-bg: #0f172a; --wp-bg-soft: #1e293b;
  --wp-fg: #e2e8f0; --wp-fg-2: #94a3b8; --wp-fg-3: #64748b;
  --wp-line: #334155;
  --wp-accent-soft: rgba(16, 185, 129, .18);
  border-left-color: #334155;
}
[data-theme='dark'] #widget-palette-modal:not(.hidden),
.dark #widget-palette-modal:not(.hidden) { background: rgba(2, 6, 23, .62); }

/* ── Cabeçalho ─────────────────────────────────────────────────────────── */
.palette-header {
  display: flex; align-items: center; gap: 8px;
  padding: 14px 16px 10px;
  border-bottom: 1px solid var(--wp-line);
  flex-shrink: 0;
}
.palette-title { font-size: 14px; font-weight: 600; margin: 0; }
.palette-count {
  font-size: 11px; color: var(--wp-fg-2);
  background: var(--wp-bg-soft); border: 1px solid var(--wp-line);
  padding: 1px 7px; border-radius: 999px;
}
.palette-shortcut {
  margin-left: auto; font-size: 10px; color: var(--wp-fg-3);
  border: 1px solid var(--wp-line); border-radius: 5px; padding: 2px 6px;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
}
.palette-close {
  flex-shrink: 0; width: 30px; height: 30px; border-radius: 8px;
  border: 1px solid var(--wp-line); background: var(--wp-bg-soft);
  color: var(--wp-fg-2); cursor: pointer; font-size: 15px; line-height: 1;
}
.palette-close:hover { background: var(--wp-accent-soft); color: var(--wp-accent); }

/* ── Pesquisa ──────────────────────────────────────────────────────────── */
.palette-search {
  display: flex; align-items: center; gap: 8px;
  margin: 10px 16px 8px; padding: 7px 10px;
  border: 1px solid var(--wp-line); border-radius: 9px;
  background: var(--wp-bg-soft); color: var(--wp-fg-2);
}
.palette-search input {
  flex: 1; border: 0; background: transparent; outline: none;
  font-size: 13px; color: var(--wp-fg);
}

/* ── Separadores ───────────────────────────────────────────────────────── */
.palette-tabs {
  display: flex; gap: 4px; padding: 0 16px 10px;
  border-bottom: 1px solid var(--wp-line);
  overflow-x: auto; scrollbar-width: none; flex-shrink: 0;
}
.palette-tabs::-webkit-scrollbar { display: none; }
.palette-tab {
  display: inline-flex; align-items: center; gap: 5px;
  padding: 5px 10px; border-radius: 999px;
  border: 1px solid var(--wp-line); background: transparent;
  color: var(--wp-fg-2); font-size: 11.5px; cursor: pointer;
  white-space: nowrap; transition: background .12s, color .12s;
}
.palette-tab:hover { background: var(--wp-bg-soft); }
.palette-tab.active {
  background: var(--wp-accent); border-color: var(--wp-accent);
  color: #fff; font-weight: 600;
}

/* ── Grelha ────────────────────────────────────────────────────────────── */
.palette-content { flex: 1; overflow-y: auto; padding: 10px 16px 16px; }
.palette-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: var(--wp-gap);
}

/* ── Card ──────────────────────────────────────────────────────────────── */
.palette-card {
  position: relative; display: flex; gap: 9px; align-items: flex-start;
  padding: 9px 10px; border-radius: var(--wp-r);
  border: 1px solid var(--wp-line); background: var(--wp-bg);
  cursor: pointer; transition: border-color .12s, box-shadow .12s, transform .12s;
}
.palette-card:hover {
  border-color: var(--wp-accent);
  box-shadow: 0 4px 14px rgba(15, 157, 110, .14);
  transform: translateY(-1px);
}
.palette-card.selected {
  border-color: var(--wp-accent);
  box-shadow: 0 0 0 2px var(--wp-accent-soft);
}
.palette-card.dragging { opacity: .5; }

.palette-card-icon {
  flex-shrink: 0; width: 30px; height: 30px; border-radius: 8px;
  display: flex; align-items: center; justify-content: center;
  color: #fff; font-size: 14px;
}
.palette-card-info { flex: 1; min-width: 0; }
.palette-card-title {
  font-size: 12.5px; font-weight: 600; color: var(--wp-fg);
  line-height: 1.25;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.palette-card-meta {
  display: flex; align-items: center; gap: 6px; margin-top: 4px;
  font-size: 10.5px; color: var(--wp-fg-3);
}
.palette-card-size { font-variant-numeric: tabular-nums; }

/* ── O que falta ───────────────────────────────────────────────────────── */
.palette-card.sem-dado .palette-card-icon { filter: saturate(.35); }
.palette-card.sem-dado .palette-card-title { color: var(--wp-fg-2); font-weight: 500; }
.palette-badge.falta {
  display: inline-flex; align-items: center; justify-content: center;
  width: 14px; height: 14px; border-radius: 50%;
  background: rgba(148, 163, 184, .2); color: var(--wp-fg-3); font-size: 9px;
  cursor: help;
}
.palette-card-requer {
  margin-top: 4px; font-size: 10.5px; line-height: 1.35;
  color: var(--wp-fg-3); font-style: italic;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
  overflow: hidden;
}
.palette-card:hover .palette-card-requer { -webkit-line-clamp: 4; }

.palette-badge.favorite { color: var(--wp-warn); font-size: 11px; }
.palette-badge.recent { color: var(--wp-fg-3); font-size: 11px; }
.palette-badge.culture { color: #10b981; font-size: 11px; }

.palette-fav-btn {
  position: absolute; top: 7px; right: 7px;
  width: 22px; height: 22px; border-radius: 6px;
  border: 0; background: transparent; color: var(--wp-fg-3);
  cursor: pointer; font-size: 12px; opacity: 0; transition: opacity .12s;
}
.palette-card:hover .palette-fav-btn,
.palette-fav-btn.active { opacity: 1; }
.palette-fav-btn.active { color: var(--wp-warn); }

/* ── Vazio e rodapé ────────────────────────────────────────────────────── */
.palette-empty {
  grid-column: 1 / -1; text-align: center;
  padding: 40px 16px; color: var(--wp-fg-2);
}
.palette-empty i { font-size: 26px; opacity: .45; display: block; margin-bottom: 10px; }
.palette-empty h4 { font-size: 13px; margin: 0 0 4px; color: var(--wp-fg); }
.palette-empty p { font-size: 11.5px; margin: 0; }

.palette-footer {
  flex-shrink: 0; padding: 9px 16px; border-top: 1px solid var(--wp-line);
  background: var(--wp-bg-soft);
}
.palette-hints { display: flex; gap: 12px; font-size: 10px; color: var(--wp-fg-3); }
.palette-hints kbd {
  background: var(--wp-bg); border: 1px solid var(--wp-line);
  border-radius: 4px; padding: 0 4px; font-family: inherit;
}

.palette-btn-full {
  display: flex; align-items: center; justify-content: center; gap: 6px;
  width: 100%; padding: 9px; margin-top: 8px; border-radius: 9px;
  border: 1px solid var(--wp-accent); background: var(--wp-accent);
  color: #fff; font-size: 12px; font-weight: 600; cursor: pointer;
}
.palette-btn-full:hover { filter: brightness(1.06); }
.palette-btn-full.ghost {
  background: transparent; color: var(--wp-fg-2); border-color: var(--wp-line);
}
`;
  document.head.appendChild(st);
})();
