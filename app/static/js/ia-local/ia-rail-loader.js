/* Carrega o `ia-rail.js` e monta a barra.
 *
 * POR QUE UM FICHEIRO SÓ PARA ISTO
 * =================================
 * O `ia_dock.html` é um template e os ícones são dados — a lista dos itens, os
 * textos e quais ainda não existem. Mantê-los no template é a razão de a barra
 * não poder ser testada sem carregar a página inteira, e de cada item novo
 * obrigar a editar HTML.
 *
 * Aqui ficam em JS, e o `ensureRail` é idempotente: o dock pode ser montado
 * duas vezes (o botão flutuante abre e fecha, e o `ia_panel.js` também o
 * encontra) e a segunda não pode desenhar a barra por cima da primeira.
 *
 * O `import()` dinâmico, e não um `<script>` no template: um script clássico
 * corre antes de o `<nav id="ia-rail">` existir, e a barra desapareceria sem
 * erro nenhum — que é a forma mais cara de um bug de interface.
 */

export function ensureRail() {
  /* O `?v=` e' o que garante que uma correcao chega ao browser sem pedido de
   * cache a ninguem. MEDIDO: com `?v=1` fixo, corrigir `ia-rail.js` nao mudou
   * nada no ecra — o browser serviu a versao antiga e o bug dos separadores
   * continuou a la, com o teste a dizer que estava verde. Um teste que passa
   * sobre codigo que o browser nunca viu e' um teste que nao mede nada.
   *
   * A versão e' o mtime do ficheiro: muda sozinha quando o conteúdo muda, e nao
   * precisa de ninguém se lembrar de a incrementar. */
  const v = Date.now();
  /* AS SESSÕES PRIMEIRO. É a única das quais depende a ACÇÃO ("Histórico"),
   * e uma acção que corre antes da loja existir é uma acção que devolve
   * "não há conversa" quando há. MEDIDO 2026-10-10: o `iaHist` vivia no
   * escopo do módulo do template e o `ia-rail-acoes.js`, sendo outro módulo,
   * via `typeof iaHist === 'undefined'` para sempre. */
  return import('/static/js/ia-local/ia-sessoes.js?v=' + v)
    .catch(function () {
      /* Sem a loja, a conversa continua. O botão "Histórico" passa a dizer que
       * não carregou em vez de mentir que não há conversa nenhuma. */
      if (window.console) console.warn('[amplia] sessoes da IA nao carregaram:', arguments[0]);
      return null;
    })
    .then(function () {
      return import('/static/js/ia-local/ia-print.js?v=' + v);
    })
    .catch(function () {
      /* Sem o modulo de print, a barra TEM de continuar a montar: os outros
       * botoes nao dependem dele. E o "Selecionar area" diz que nao carregou,
       * em vez de ficar cinzento sem explicacao. */
      if (window.console) console.warn('[amplia] tirador de print nao carregou:', arguments[0]);
      return null;
    })
    .then(function () {
      return import('/static/js/ia-local/ia-serie.js?v=' + v);
    })
    .catch(function () {
      /* Sem o desenho de serie, as respostas continuam em prosa: o grafico
       * e' enfeite do modo CRIAR, nunca a resposta. */
      if (window.console) console.warn('[amplia] desenho de serie nao carregou:', arguments[0]);
      return null;
    })
    .then(function () {
      return import('/static/js/ia-local/ia-modos.js?v=' + v);
    })
    .catch(function () {
      /* Sem os modos, as chaves seletoras ("Criar no chat/painel/nuvem")
       * dizem que nao carregaram em vez de fingir que ligaram — e o resto
       * da barra monta igual. Antes este import NEM EXISTIA: nenhum caminho
       * carregava `ia-modos.js`, e `window.IaModos` era undefined para
       * sempre em todas as paginas. */
      if (window.console) console.warn('[amplia] modos da IA nao carregaram:', arguments[0]);
      return null;
    })
    .then(function () {
      return import('/static/js/ia-local/ia-chave.js?v=' + v);
    })
    .catch(function () {
      /* Idem para a engrenagem: sem este import, `window.IaChave` nunca
       * existia e o painel da chave dizia que nao carregou — em toda
       * pagina, sempre. */
      if (window.console) console.warn('[amplia] painel da chave nao carregou:', arguments[0]);
      return null;
    })
    .then(function () {
      return import('/static/js/ia-local/ia-rail-acoes.js?v=' + v);
    })
    .then(function () {
      return import('/static/js/ia-local/ia-rail.js?v=' + v);
    })
    .then(function () {
      const rail = document.getElementById('ia-rail');
      if (!rail) return false;
      if (rail.dataset.montada === '1') return true;
      window.IaRail.monta(rail);
      rail.dataset.montada = '1';
      return true;
    });
}
