import io

CAM = "tests/unit/ia_rail_dom.test.js"
t = io.open(CAM, encoding="utf-8").read()

INI = t.find("  describe('os menus'")
FIM = t.find("  describe('o print da tela'")
assert INI > 0 and FIM > INI, (INI, FIM)

NOVO = """  /* OS DOIS \"CRIAR\" SÃO CHAVE SELETORA, E ESTE BLOCO É O GUARDA DISSO.
   *
   * O que aqui estava, e porque saiu
   * --------------------------------
   * Havia dois describes — \"os menus\" e \"os botoes que produzem pecas\" —
   * construídos sobre um design que o produtor rejeitou. Eles mediam:
   *
   *   - `window.IaRail.passar('criar-no-chat')` abrir `.ia-rail-menu` com
   *     `['Planilha', 'Grafico']`;
   *   - o menu ser IRMÃO do botão (o `overflow:hidden` do item cortaria um
   *     filho);
   *   - abrir um menu fechar o anterior;
   *   - quatro acções — `iaCriarPlanilha`, `iaCriarGrafico`, `iaCriarNoPainel`,
   *     `iaResponderNoPainel` — cada uma com um pedido \"COMPLETO\" de mais de
   *     120 caracteres.
   *
   * Nenhuma dessas quatro acções existe em `ia-rail-acoes.js`, e nenhum item
   * da barra tem `menu`. O pedido do produtor está citado em `ia-rail.js`:
   * \"não são menus de escolha, mas sim quando escolhadas forçam a IA a
   * responder nesses locais de forma personalizada e menos textual\". A
   * resposta foi a CHAVE: ligada, injecta uma DIRECTIVA em cada pergunta
   * (`ia-modos.js`) e a resposta vem como PEÇA.
   *
   * Os sintomas medidos eram esses, e nenhum era do sistema:
   *   `expected null to be truthy` (o menu não existe),
   *   `Cannot read properties of null (reading 'querySelectorAll')`,
   *   `Cannot read properties of null (reading 'parentElement')`,
   *   `Cannot read properties of undefined (reading 'getAttribute')`,
   *   `expected [] to have a length of 2 but got +0`.
   *
   * O que se mede agora é o contrato QUE EXISTE. */
  describe('as chaves \"criar\"', () => {
    beforeEach(() => {
      /* A loja de modos: é ela que diz se uma chave está ligada. */
      window.IaModos = {
        _ligados: {},
        alternar: vi.fn(function (qual) {
          this._ligados[qual] = !this._ligados[qual];
          return this._ligados[qual];
        }),
        activo: vi.fn(function (qual) {
          return Boolean(this._ligados[qual]);
        }),
      };
      window.iaAlternarModo = vi.fn(function (qual) {
        if (!window.IaModos) return;
        window.IaModos.alternar(qual);
      });
      /* O rail desenha o interruptor a partir da loja — sem isto os itens com
         `chave` sairiam desactivados. */
      window.__getEditFlags = () => ({ edicao: false });
    });

    it('\"criar no chat\" liga o modo chat, e nao abre menu nenhum', () => {
      window.IaRail.passar('criar-no-chat');
      expect(window.iaAlternarModo, 'o clique nao chamou o interruptor').toHaveBeenCalledWith(
        'chat'
      );
      expect(document.querySelector('.ia-rail-menu'), 'voltou o menu antigo').toBeNull();
    });

    it('\"criar no painel\" liga o modo painel', () => {
      window.IaRail.passar('criar-no-painel');
      expect(window.iaAlternarModo).toHaveBeenCalledWith('painel');
      expect(document.querySelector('.ia-rail-menu')).toBeNull();
    });

    it('a chave desenhada e um interruptor, e diz se esta ligada', () => {
      /* Um interruptor que não anuncia o estado é um botão comum: quem usa
         leitor de ecrã não sabe se a directiva está ligada. */
      window.IaModos._ligados.chat = true;
      window.IaRail.monta(rail);
      const b = rail.querySelector('.ia-rail-item[data-id="criar-no-chat"]');
      expect(b).toBeTruthy();
      expect(b.getAttribute('role')).toBe('switch');
      expect(b.getAttribute('aria-pressed')).toBe('true');
      expect(b).not.toContain('disabled');

      window.IaModos._ligados.chat = false;
      window.IaRail.monta(rail);
      const b2 = rail.querySelector('.ia-rail-item[data-id="criar-no-chat"]');
      expect(b2.getAttribute('aria-pressed')).toBe('false');
    });

    it('sincronizar as chaves redesenha o interruptor sem trocar de preset', () => {
      /* Ligar o modo pela loiça (não pela barra) tem de reflectir-se no
         desenho. Antes o interruptor ficava verde e o desenho dizia o
         contrário — e o produtor carregava duas vezes. */
      window.IaModos._ligados.painel = true;
      expect(() => window.IaRail.sincronizaChaves()).not.toThrow();
      const b = rail.querySelector('.ia-rail-item[data-id="criar-no-painel"]');
      expect(b.getAttribute('aria-pressed')).toBe('true');
    });
  });

"""

io.open(CAM, "w", encoding="utf-8", newline="\n").write(t[:INI] + NOVO + t[FIM:])
print("substituido de", INI, "ate", FIM)
print("removidos", FIM - INI, "chars; escritos", len(NOVO))
