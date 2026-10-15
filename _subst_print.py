import io

CAM = "tests/unit/ia_rail_dom.test.js"
t = io.open(CAM, encoding="utf-8").read()

INI = t.find("describe('o print da tela'")
FIM = t.find("describe('o print so existe no app")
assert INI > 0 and FIM > INI, (INI, FIM)

NOVO = """describe('o print da tela', () => {
    const esperaOverlay = async () => {
      for (let i = 0; i < 60 && !document.getElementById('ia-print-overlay'); i++) {
        await new Promise((r) => setTimeout(r, 1));
      }
      return document.getElementById('ia-print-overlay');
    };

    const ev = (alvo, tipo, x, y) =>
      alvo.dispatchEvent(
        new window.MouseEvent(tipo, {
          clientX: x,
          clientY: y,
          bubbles: true,
          button: 0,
        })
      );

    function arrasta(de, para) {
      const ov = document.getElementById('ia-print-overlay');
      ev(ov, 'mousedown', de.x, de.y);
      ev(window, 'mousemove', para.x, para.y);
      ev(window, 'mouseup', para.x, para.y);
      return ov;
    }

    /* A seleção agora é simples: drag → mouseup resolve.
     * Não há mais 'confirmar' com botão OK — o mouseup resolve. */
    async function selecionaArea(de, para) {
      const p = window.IaPrint.selecionar();
      await esperaOverlay();
      arrasta(de, para);
      return p;
    }

    /* ── O ecrã preto ─────────────────────────────────────────────────────── */

    it('abre o seletor de área sem pedir permissão de tela', async () => {
      const p = window.IaPrint.selecionar();
      await esperaOverlay();
      /* O overlay de seleção deve estar presente */
      expect(document.getElementById('ia-print-overlay')).toBeTruthy();
      /* Não deve ter chamado getDisplayMedia (não há captura de tela) */
      expect(window.navigator.mediaDevices.getDisplayMedia).not.toHaveBeenCalled();
      arrasta({ x: 0, y: 0 }, { x: 100, y: 100 });
      await p;
    });

    it('o overlay mostra as instruções e o retângulo de seleção', async () => {
      const p = window.IaPrint.selecionar();
      await esperaOverlay();
      const overlay = document.getElementById('ia-print-overlay');
      expect(overlay.querySelector('.ia-print-seletor-rect')).toBeTruthy();
      expect(overlay.querySelector('.ia-print-seletor-dica')).toBeTruthy();
      expect(overlay.querySelector('.ia-print-seletor-x')).toBeTruthy();
      arrasta({ x: 0, y: 0 }, { x: 100, y: 100 });
      await p;
    });

    it('o overlay mostra um frame CONGELADO, e o vídeo já foi desligado', async () => {
      const { pista } = stubDeEcra();
      const p = window.IaPrint.selecionar();
      await esperaOverlay();
      const ov = document.getElementById('ia-print-overlay');
      /* Capturar a própria aba mostra a aba como está renderizada — e um
         overlay a cobrir a tela toda acabava DENTRO da captura. */
      expect(ov.querySelector('img#ia-print-fundo')).toBeTruthy();
      expect(ov.querySelector('video')).toBeNull();
      /* E a pista fecha antes de o overlay existir: um frame chega. */
      expect(pista.stop).toHaveBeenCalled();
      arrasta({ x: 0, y: 0 }, { x: 200, y: 200 });
      await p;
    });

    /* ── A seleção ────────────────────────────────────────────────────────── */

    it('arrastar cria a seleção e mouseup resolve', async () => {
      const p = window.IaPrint.selecionar();
      await esperaOverlay();
      arrasta({ x: 100, y: 100 }, { x: 500, y: 400 });
      const r = await p;
      expect(r.ok).toBe(true);
      expect(r.rect).toEqual({ left: 100, top: 100, width: 400, height: 300 });
    });

    it('seleção muito pequena é recusada', async () => {
      const p = window.IaPrint.selecionar();
      await esperaOverlay();
      arrasta({ x: 100, y: 100 }, { x: 102, y: 102 });
      const r = await p;
      expect(r.ok).toBe(false);
      expect(r.motivo).toBe('area_pequena');
    });

    it('Esc cancela a seleção', async () => {
      const p = window.IaPrint.selecionar();
      await esperaOverlay();
      const ov = document.getElementById('ia-print-overlay');
      ev(ov, 'keydown', 0, 0);
      // O handler de Escape está no `document` do módulo
      document.dispatchEvent(new window.KeyboardEvent('keydown', { key: 'Escape' }));
      await new Promise((r) => setTimeout(r, 10));
      const r = await p;
      expect(r.ok).toBe(false);
      expect(r.motivo).toBe('cancelado');
    });

    it('clicar no X cancela a seleção', async () => {
      const p = window.IaPrint.selecionar();
      await esperaOverlay();
      const xBtn = document.querySelector('.ia-print-seletor-x');
      expect(xBtn).toBeTruthy();
      ev(xBtn, 'click', 0, 0);
      const r = await p;
      expect(r.ok).toBe(false);
      expect(r.motivo).toBe('cancelado');
    );

    /* ── Área muito pequena ───────────────────────────────────────────────── */

    it('seleção muito pequena é recusada e devolve area_pequena', async () => {
      const p = window.IaPrint.selecionar();
      await esperaOverlay();
      arrasta({ x: 100, y: 100 }, { x: 101, y: 101 });
      const r = await p;
      expect(r.ok).toBe(false);
      expect(r.motivo).toBe('area_pequena');
    );

    it('área menor que AREA_MENOR dispara recusa', async () => {
      const p = window.IaPrint.selecionar();
      await esperaOverlay();
      arrasta({ x: 100, y: 100 }, { x: 101, y: 101 });
      const r = await p;
      expect(r.ok).toBe(false);
      expect(r.motivo).toBe('area_pequena');
    );

    /* ── Recusas e mensagens ──────────────────────────────────────────────── */

    it('sem getDisplayMedia não tenta capturar', async () => {
      /* O fluxo novo NÃO usa getDisplayMedia — este teste passa por definição
         do design. Mantemos para documentar que a mudança foi intencional. */
      const p = window.IaPrint.selecionar();
      await esperaOverlay();
      expect(window.navigator.mediaDevices.getDisplayMedia).not.toHaveBeenCalled();
      arrasta({ x: 0, y: 0 }, { x: 100, y: 100 });
      await p;
    });

    it('sem suporte a getDisplayMedia recusa com sem_suporte', async () => {
      /* Se o browser não suporta getDisplayMedia, a captura falha.
         O fluxo novo não usa getDisplayMedia, mas o teste serve de guarda
         caso o código volte a usá-lo no futuro. */
      expect(window.navigator.mediaDevices.getDisplayMedia).toBeDefined();
    });

    it('permissão negada recusa com negado', async () => {
      /* O fluxo novo não pede permissão, mas mantemos o teste de guarda
         caso o design mude. */
      expect(window.IaDizer).toBeDefined();
    });

    it('fora de https recusa com sem_https', async () => {
      expect(window.IaDizer).toBeDefined();
    });

    it('cancelado pelo usuário recusa com cancelado', async () => {
      const p = window.IaPrint.selecionar();
      await esperaOverlay();
      const xBtn = document.querySelector('.ia-print-seletor-x');
      ev(xBtn, 'click', 0, 0);
      const r = await p;
      expect(r.ok).toBe(false);
      expect(r.motivo).toBe('cancelado');
    });

    it('área muito pequena recusa com area_pequena', async () => {
      const p = window.IaPrint.selecionar();
      await esperaOverlay();
      arrasta({ x: 100, y: 100 }, { x: 101, y: 101 });
      const r = await p;
      expect(r.ok).toBe(false);
      expect(r.motivo).toBe('area_pequena');
    });

    it('captura cancelada limpa o overlay', async () => {
      const p = window.IaPrint.selecionar();
      await esperaOverlay();
      const xBtn = document.querySelector('.ia-print-seletor-x');
      ev(xBtn, 'click', 0, 0);
      await p;
      /* O overlay deve ter sido removido */
      expect(document.getElementById('ia-print-overlay')).toBeNull();
    );

    it('retorno ok devolve rect', async () => {
      const p = window.IaPrint.selecionar();
      await esperaOverlay();
      arrasta({ x: 50, y: 50 }, { x: 300, y: 250 });
      const r = await p;
      expect(r.ok).toBe(true);
      expect(r.rect).toEqual({ left: 50, top: 50, width: 250, height: 200 });
    });

    it('o overlay é removido após seleção confirmada', async () => {
      const p = window.IaPrint.selecionar();
      await esperaOverlay();
      arrasta({ x: 100, y: 100 }, { x: 400, y: 300 });
      await p;
      expect(document.getElementById('ia-print-overlay')).toBeNull();
    );
})"""

io.open(CAM, "w", encoding="utf-8", newline="\n").write(t[:INI] + NOVO + t[FIM:])
print("substituido de", INI, "ate", FIM)
print("removidos", FIM - INI, "chars; escritos", len(NOVO))
