/**
 * Preload da janela: a unica ponte entre o Django (uma pagina web normal)
 * e o Electron.
 *
 * ---------------------------------------------------------------------------
 * A REGRA QUE TORNA ESTE FICHEIRO CURTO
 * ---------------------------------------------------------------------------
 * Aqui nao existe API `ampliagro.fechar()`, `ampliagro.abrirFicheiro()` ou
 * `ampliagro.executar()`. E a ausencia e a decisao.
 *
 * Cada uma dessas funcoes seria uma porta de entrada para o sistema
 * operativo, a partir de uma pagina que renderiza dados de uma fazenda.
 * Os templates sao 119 ficheiros com 606 handlers `on*=` e scripts inline:
 * esse e o exacto material de onde um XSS entraria.
 *
 * A superficie certa, agora, e zero. Quando o desktop precisar de algo
 * (abrir a pasta de dados, notificar), o gancho entra aqui com uma
 * funcao nomeada e um canal `ipcRenderer` fixo -- nunca com um
 * `invoke()` generico que aceite o que vier.
 *
 * Com `sandbox: true` e `contextIsolation: true` (ver `main.js`), o
 * `require` e o `fs` nao existem no contexto da pagina. Um XSS injectado
 * encontra esta superficie vazia. A diferenca entre "injection numa app"
 * e "injection na app que tem a base de dados da fazenda".
 */

'use strict';

const { contextBridge } = require('electron');

contextBridge.exposeInMainWorld('ampliagro', {
  versao: '0.0.0-fase0',

  /**
   * A origem da pagina.
   *
   * A pagina ja sabe a propria origem: leu-a da barra de endereco. Este
   * metodo existe para diagnostico -- aparecer na consola como
   * `ampliagro.origem()` -- e para a prova de offline da Fase 2, que
   * precisa de distinguir pedidos a loopback de pedidos para fora.
   *
   * NUNCA usar para decidir se um pedido e de confianca: a origem e
   * escrita pelo dono da pagina. Nao e material de autorizacao.
   */
  origem: () => window.location.origin,
});
