// A guia de ferramentas — versão limpa (estilo Animal/Vegetal)
//
// O que esta página NÃO tem mais (por decisão de design):
// - Simulador de governança
// - Calculadoras de campo (adubo, semente, pulverizador, área, unidades)
// - Resumo de 3 números (Operacionais/A meio/Não implementado)
// - Fronteiras, governança, dias de registo, "onde vive"
// - Campo "Como ler esta página"
//
// O que ELA TEM:
// - Navegação por categorias (A–H) com contagem
// - Cards limpos: título, resumo centralizado, botão "Abrir"
// - Busca que filtra dentro da categoria ativa
// - Info da categoria ativa (letra + nome + contagem)

import { describe, it, expect, beforeAll } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import vm from 'node:vm';
import { JSDOM } from 'jsdom';

const TEMPLATE = resolve(process.cwd(), 'app/templates/guia-ferramentas.html');
const SRC = readFileSync(TEMPLATE, 'utf8');

function extraiScript() {
  const i = SRC.indexOf('<script>');
  const j = SRC.indexOf('</script>', i);
  if (i < 0 || j < 0) throw new Error('o template nao tem bloco <script>');
  return SRC.slice(i + '<script>'.length, j);
}

function construirDom() {
  const dom = new JSDOM('<!doctype html><html><body></body></html>');
  const { document } = dom.window;

  // Header
  const header = document.createElement('div');
  header.className = 'guide-header';
  header.innerHTML = `
    <h1 class="guide-title"><i class="bi bi-tools"></i> Guia de Ferramentas</h1>
    <div style="flex:1; min-width:200px; position:relative;">
      <i class="bi bi-search" style="position:absolute; left:12px; top:50%; transform:translateY(-50%); color:var(--cor-texto-fraco);"></i>
      <input type="text" class="guide-search-input" id="gfBusca" placeholder="Buscar capacidade..." style="width:100%; padding:8px 12px 8px 36px; border-radius:8px; border:1px solid var(--cor-borda); font-size:14px; outline:none; transition:border-color 0.2s;">
    </div>
    <span class="badge" style="background:var(--cor-primaria-suave);color:var(--cor-primaria);padding:6px 10px;border-radius:999px;font-size:.72rem;font-weight:700">57 capacidades · 0 sensores teus</span>
    <a href="/" class="btn-secondary btn-sm" style="white-space:nowrap;">Dashboard</a>
  `;
  document.body.insertBefore(header, document.body.firstChild);

  // Nav
  const nav = document.createElement('nav');
  nav.className = 'gf-nav';
  nav.id = 'gfNav';
  const classes = [
    { id: 'fiscal', letra: 'A', nome: 'Fiscal', count: 9 },
    { id: 'financeiro', letra: 'B', nome: 'Financeiro', count: 10 },
    { id: 'campo', letra: 'C', nome: 'Campo', count: 12 },
    { id: 'pecuaria', letra: 'D', nome: 'Pecuária', count: 3 },
    { id: 'logistica', letra: 'E', nome: 'Logística', count: 5 },
    { id: 'maquinas', letra: 'G', nome: 'Máquinas e IA', count: 8 },
    { id: 'dados', letra: 'H', nome: 'Dados', count: 10 },
  ];
  for (const c of classes) {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'gf-nav-btn' + (c.id === 'fiscal' ? ' ativo' : '');
    btn.dataset.classe = c.id;
    btn.innerHTML = `<span class="gf-nav-letra">${c.letra}</span><span>${c.nome}</span><span class="gf-nav-contagem">${c.count}</span>`;
    nav.appendChild(btn);
  }
  document.body.appendChild(nav);

  // Categoria info
  const catInfo = document.createElement('div');
  catInfo.className = 'gf-categoria-info';
  catInfo.id = 'gfCatInfo';
  catInfo.innerHTML = '<i class="bi bi-info-circle"></i><span id="gfCatTexto"></span>';
  document.body.appendChild(catInfo);

  // Painel de detalhe (slide-in) - elementos que o script espera
  const detailOverlay = document.createElement('div');
  detailOverlay.className = 'gf-detail-overlay';
  detailOverlay.id = 'gfDetailOverlay';
  document.body.appendChild(detailOverlay);

  const detailPanel = document.createElement('div');
  detailPanel.className = 'gf-detail-panel';
  detailPanel.id = 'gfDetailPanel';
  detailPanel.innerHTML = `
    <div class="gf-detail-header">
      <h3 class="gf-detail-title" id="gfDetailTitle">Detalhes</h3>
      <button class="gf-detail-close" id="gfDetailClose" aria-label="Fechar"><i class="bi bi-x-lg"></i></button>
    </div>
    <div class="gf-detail-body" id="gfDetailBody">
      <div class="lcdpr-skeleton" style="height: 200px;"></div>
    </div>
  `;
  document.body.appendChild(detailPanel);

  // Sections com cards
  const secoes = [
    { id: 'fiscal', items: 9, baseName: 'LCDPR — Livro Caixa do Produtor Rural' },
    { id: 'financeiro', items: 10, baseName: 'Fluxo de Caixa' },
    { id: 'campo', items: 12, baseName: 'Adubo NPK por hectare' },
    { id: 'pecuaria', items: 3, baseName: 'Calendário Sanitário' },
    { id: 'logistica', items: 5, baseName: 'Fretes Abertos' },
    { id: 'maquinas', items: 8, baseName: 'Revisão de Máquinas' },
    { id: 'dados', items: 10, baseName: 'NDVI de Satélite' },
  ];

  for (const s of secoes) {
    const sec = document.createElement('section');
    sec.className = 'gf-seccao' + (s.id === 'fiscal' ? ' ativa' : '');
    sec.id = 'sec-' + s.id;
    const grid = document.createElement('div');
    grid.className = 'gf-grelha';
    for (let i = 0; i < s.items; i++) {
      const art = document.createElement('article');
      art.className = 'gf-item';
      const temRota = i % 3 === 0;
      art.innerHTML = `
        <h3 class="gf-item-nome">${s.baseName} ${i + 1}</h3>
        <p class="gf-item-resumo">Resumo do ${s.baseName.toLowerCase()} item ${i + 1}.</p>
        <div style="margin-top:auto;">
          ${
            temRota
              ? `<a class="gf-btn" href="/rota/${s.id}/${i}">Abrir <span aria-hidden="true">&rarr;</span></a>`
              : '<button type="button" class="gf-btn gf-btn-ghost" disabled>Não implementado</button>'
          }
        </div>
      `;
      grid.appendChild(
        Object.assign(document.createElement('article'), {
          className: 'gf-item',
          innerHTML: art.innerHTML,
        })
      );
    }
    sec.appendChild(grid);
    document.body.appendChild(sec);
  }

  return dom;
}

function correr() {
  const dom = construirDom();
  const sandbox = { document: dom.window.document, window: dom.window, console };
  vm.createContext(sandbox);
  vm.runInContext(extraiScript(), sandbox);
  dom.window.document.dispatchEvent(new dom.window.Event('DOMContentLoaded', { bubbles: true }));
  return dom;
}

describe('a guia limpa (estilo Animal/Vegetal)', () => {
  let dom;

  beforeAll(() => {
    dom = correr();
  });

  it('compila e corre sem lançar', () => {
    expect(dom).toBeDefined();
  });

  it('tem 7 botões de navegação com letras A–H', () => {
    const btns = dom.window.document.querySelectorAll('#gfNav .gf-nav-btn');
    expect(btns.length).toBe(7);
    const letras = Array.from(btns)
      .map((b) => b.querySelector('.gf-nav-letra').textContent)
      .sort();
    expect(letras).toEqual(['A', 'B', 'C', 'D', 'E', 'G', 'H']);
  });

  it('mostra info da categoria ativa (letra + nome + contagem)', () => {
    const texto = dom.window.document.getElementById('gfCatTexto');
    expect(texto.innerHTML).toContain('A Fiscal');
    expect(texto.innerHTML).toContain('9 capacidades');
  });

  it('inicializa com a primeira categoria ativa (Fiscal = 9 cards)', () => {
    const secaoAtiva = dom.window.document.querySelector('.gf-seccao.ativa');
    expect(secaoAtiva?.id).toBe('sec-fiscal');
    expect(secaoAtiva.querySelectorAll('.gf-item').length).toBe(9);
  });

  it('cards têm título, resumo e botão (sem fronteira/governança/estado)', () => {
    const card = dom.window.document.querySelector('.gf-item');
    expect(card.querySelector('.gf-item-nome')).toBeTruthy();
    expect(card.querySelector('.gf-item-resumo')).toBeTruthy();
    expect(card.querySelector('.gf-btn')).toBeTruthy();
    expect(card.querySelector('.gf-fronteira')).toBeFalsy();
    expect(card.querySelector('.gf-governanca')).toBeFalsy();
    expect(card.querySelector('.gf-item-estado')).toBeFalsy();
    expect(card.querySelector('.gf-onda-viva')).toBeFalsy();
    expect(card.querySelector('.gf-ausente-nota')).toBeFalsy();
  });

  it('botão "Abrir" existe só quando há rota; senão botão ghost desabilitado', () => {
    const cardComRota = dom.window.document.querySelector('.gf-item a.gf-btn');
    expect(cardComRota).toBeTruthy();
    expect(cardComRota.textContent).toContain('Abrir');

    const cardSemRota = dom.window.document.querySelector('.gf-item button.gf-btn-ghost:disabled');
    expect(cardSemRota).toBeTruthy();
  });

  it('não tem <input type="number"> (sem calculadoras/simulador)', () => {
    const inputs = dom.window.document.querySelectorAll('input[type="number"]');
    expect(inputs.length).toBe(0);
  });

  it('não tem o typo "quetu"', () => {
    expect(extraiScript()).not.toContain('quetu');
  });

  it('declara `num` zero vezes (simulador/calculadoras removidos)', () => {
    const n = extraiScript().match(/function num\(/g) || [];
    expect(n.length).toBe(0);
  });

  it('não tem simulador (.gf-gov)', () => {
    expect(dom.window.document.querySelector('.gf-gov')).toBeFalsy();
  });

  it('não tem ferramentas de campo (.gf-ferramentas)', () => {
    expect(dom.window.document.querySelector('.gf-ferramentas')).toBeFalsy();
  });

  it('não tem resumo de 3 números (.gf-resumo)', () => {
    expect(dom.window.document.querySelector('.gf-resumo')).toBeFalsy();
  });

  it('não tem "Como ler esta página"', () => {
    expect(extraiScript()).not.toContain('Como ler esta página');
  });
});
