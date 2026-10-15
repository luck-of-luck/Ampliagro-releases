/* O AGENTE DA NUVEM — a chave da API do Gemini, pela engrenagem.
 * ==============================================================
 *
 * O PEDIDO, NA PALAVRA DO PRODUTOR
 * ================================
 * \"Implemente para que possamos por conta cadastrar uma API do Gemini para
 * inserir um agente da nuvem. Para inserir a API deve ser num ícone de
 * engrenagem no canto inferior do painel ia-rail.\"
 *
 * A engrenagem é o item `config-ia` no fundo da barra (`ia-rail.js`); este
 * ficheiro é o painel que ela abre.
 *
 * ONDE A CHAVE VIVE
 * =================
 * No SERVIDOR, cifrada em repouso. Não no `localStorage`: uma chave de API é
 * um segredo, e o `localStorage` é legível por qualquer script da página e
 * sobrevive a fechar o browser. O padrão da casa é o do `Gateway` de IoT
 * (`app/models/iot.py`): `EncryptedCharField` (Fernet, `app/seguranca.py`) e
 * um `hash_cego` para autenticar sem descriptografar. O modelo
 * `ChaveIA` repete esse padrão, por utilizador.
 *
 * O que este módulo faz é só a INTERFACE: mostrar o estado, pedir a chave,
 * gravar, apagar. A cifra, a validação e a recusa são do servidor.
 *
 * A CHAVE NUNCA VOLTA PARA O ECRÃ
 * ===============================
 * O `GET` devolve `tem_chave` e o provedor — nunca a chave. Escrever num
 * `<input type=password>` o que o servidor não devolve é impossível, e é por
 * isso que o campo começa vazio: \"registe uma nova chave\" não é um formulário
 * de edição, é uma substituição.
 */

(function () {
  'use strict';

  /* SINGLETON — a razão do `ia-sessoes.js` e do `ia-modos.js`: dois caminhos
   * de importação são dois módulos e duas execuções desta IIFE, e a segunda
   * faria `window.IaChave = api` por cima da primeira. Com a guarda, a
   * primeira é a que fica. */
  if (window.IaChave) return;

  var URL_CHAVE = '/api/ia/chave/';
  var ID_PAINEL = 'ia-chave';

  function csrf() {
    /* O token vem da função do template (`ia_dock.html`). Se o template não
     * estiver nesta página, o painel diz que não carregou — não tenta um
     * POST sem token, que é um 403 com uma mensagem que não explica nada. */
    if (typeof window.iaCsrfToken === 'function') return window.iaCsrfToken();
    try {
      var m = document.cookie.split('; ').find(function (c) {
        return c.indexOf('csrftoken=') === 0;
      });
      return m ? m.split('=')[1] : '';
    } catch (e) {
      return '';
    }
  }

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  function fala(texto) {
    var gancho = window.iaLocalMsg;
    if (typeof gancho === 'function' && gancho !== fala) {
      gancho(texto, 'bot');
      return;
    }
    var body = document.getElementById('ia-chat-body');
    if (!body) return;
    var d = document.createElement('div');
    d.className = 'ia-msg bot';
    d.textContent = texto;
    body.appendChild(d);
    body.scrollTop = body.scrollHeight;
  }

  function fecha() {
    var p = document.getElementById(ID_PAINEL);
    if (p) p.remove();
  }

  function estadoHTML(e) {
    var partes = [];
    if (e && e.tem_chave) {
      partes.push(
        '<div class="ia-chave-estado ia-chave-ligada">Agente da nuvem LIGADO</div>' +
          '<div class="ia-chave-nota">Provedor: ' +
          esc(e.provedor || 'gemini') +
          '. As respostas da IA podem vir da nuvem quando o motor local não estiver disponível.</div>'
      );
    } else {
      partes.push(
        '<div class="ia-chave-estado ia-chave-desligada">Agente da nuvem desligado</div>' +
          '<div class="ia-chave-nota">Sem chave, a IA responde só com o motor local — e o texto do produtor não sai do servidor.</div>'
      );
    }
    return partes.join('');
  }

  /* O estado da validação nesta abertura: só libera o Confirmar para o
   * valor EXATO que passou no teste. Trocar uma letra invalida de novo —
   * testar "ABC" e gravar "ABC " (com espaço) seria gravar o que não foi
   * testado. */
  var ultimoTeste = { valor: '', valido: false };

  var teclaRegistrada = null;

  function desligaTecla() {
    if (teclaRegistrada) {
      try {
        document.removeEventListener('keydown', teclaRegistrada);
      } catch (e) {}
      teclaRegistrada = null;
    }
  }

  function fechaTudo() {
    desligaTecla();
    fecha();
  }

  /* O card NO CENTRO DA TELA (overlay próprio), e não dentro do chat: colar
   * chave lendo conversa ao lado é pedir erro de cópia, e o fluxo agora tem
   * três passos (colar -> testar -> confirmar) que merecem palco próprio.
   * As classes internas (topo, corpo, estado, aviso) são as mesmas de
   * antes: `gravar`, `apagar`, `aviso` e `lerEstado` continuam funcionando
   * sem saber que mudaram de endereço. */
  function desenha(estado) {
    fechaTudo();
    if (!document.body) return null;

    ultimoTeste = { valor: '', valido: false };

    var overlay = document.createElement('div');
    overlay.id = 'ia-chave-overlay';
    overlay.className = 'ia-chave-overlay';

    var p = document.createElement('div');
    p.id = ID_PAINEL;
    p.className = 'ia-chave ia-chave-modal';
    p.innerHTML =
      '<div class="ia-chave-topo">' +
      '<span>Agente da nuvem</span>' +
      '<button type="button" class="ia-chave-fechar" title="Fechar" aria-label="Fechar">×</button>' +
      '</div>' +
      '<div class="ia-chave-corpo">' +
      estadoHTML(estado) +
      '<label class="ia-chave-rotulo" for="ia-chave-input">Chave da API do Gemini</label>' +
      '<input id="ia-chave-input" class="ia-chave-input" type="password" ' +
      'placeholder="Cole aqui a chave" autocomplete="off" spellcheck="false">' +
      '<div class="ia-chave-nota">Primeiro testamos aqui mesmo, sem salvar nada. Só entra o Confirmar depois do teste passar.</div>' +
      '<div class="ia-chave-teste" hidden></div>' +
      '<div class="ia-chave-accoes">' +
      '<button type="button" class="ia-chave-btn ia-chave-testar">Testar chave</button>' +
      '<button type="button" class="ia-chave-btn ia-chave-gravar" disabled>Confirmar e gravar</button>' +
      '<button type="button" class="ia-chave-btn ia-chave-apagar">Apagar chave</button>' +
      '</div>' +
      '<div class="ia-chave-aviso" hidden></div>' +
      '<div class="ia-chave-nota">A chave fica cifrada no servidor (Fernet). Nunca é mostrada outra vez.</div>' +
      '</div>';
    overlay.appendChild(p);
    document.body.appendChild(overlay);

    var inp = p.querySelector('#ia-chave-input');
    var btnTestar = p.querySelector('.ia-chave-testar');
    var btnGravar = p.querySelector('.ia-chave-gravar');
    var btnApagar = p.querySelector('.ia-chave-apagar');
    var caixaTeste = p.querySelector('.ia-chave-teste');

    function mostraTeste(ok, texto) {
      caixaTeste.hidden = false;
      caixaTeste.className = 'ia-chave-teste ' + (ok ? 'ia-chave-teste-ok' : 'ia-chave-teste-erro');
      caixaTeste.textContent = texto;
    }

    function escondeTeste() {
      caixaTeste.hidden = true;
      caixaTeste.textContent = '';
    }

    btnApagar.hidden = !(estado && estado.tem_chave);

    p.querySelector('.ia-chave-fechar').addEventListener('click', fechaTudo);

    overlay.addEventListener('click', function (e) {
      if (e.target === overlay) fechaTudo();
    });

    desligaTecla();
    teclaRegistrada = function (e) {
      if (e && e.key === 'Escape') fechaTudo();
    };
    document.addEventListener('keydown', teclaRegistrada);

    inp.addEventListener('input', function () {
      /* Trocou uma letra depois do teste: volta a exigir o teste. */
      if ((inp.value || '').trim() !== ultimoTeste.valor) {
        ultimoTeste = { valor: '', valido: false };
        btnGravar.disabled = true;
        escondeTeste();
      }
    });

    btnTestar.addEventListener('click', function () {
      var v = (inp.value || '').trim();
      if (!v) {
        aviso(p, 'Cole a chave antes de testar.');
        return;
      }
      btnTestar.disabled = true;
      btnTestar.textContent = 'Testando…';
      escondeTeste();
      fetch('/api/ia/chave/testar/', {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf() },
        body: JSON.stringify({ chave: v }),
      })
        .then(function (r) {
          return r
            .json()
            .catch(function () {
              return {};
            })
            .then(function (j) {
              return { http: r.ok, corpo: j || {} };
            });
        })
        .then(function (res) {
          btnTestar.disabled = false;
          btnTestar.textContent = 'Testar chave';
          var j = res.corpo;
          if (j && j.valido) {
            ultimoTeste = { valor: v, valido: true };
            btnGravar.disabled = false;
            mostraTeste(
              true,
              'Chave válida' +
                (j.modelos
                  ? ' (' + j.modelos + (j.modelos === 1 ? ' modelo' : ' modelos') + ' ao alcance).'
                  : '.') +
                ' Pode confirmar.'
            );
          } else {
            ultimoTeste = { valor: '', valido: false };
            btnGravar.disabled = true;
            mostraTeste(false, (j && j.erro) || 'Não consegui testar agora. Tente de novo.');
          }
        })
        .catch(function (e) {
          btnTestar.disabled = false;
          btnTestar.textContent = 'Testar chave';
          ultimoTeste = { valor: '', valido: false };
          btnGravar.disabled = true;
          mostraTeste(
            false,
            'Falha de rede ao testar (' + String((e && e.message) || e) + '). Tente de novo.'
          );
        });
    });

    p.querySelector('.ia-chave-gravar').addEventListener('click', function () {
      var v = (inp.value || '').trim();
      if (!v) {
        aviso(p, 'Cole a chave antes de confirmar.');
        return;
      }
      /* O portão: só grava o valor exato que passou no teste. */
      if (!ultimoTeste.valido || v !== ultimoTeste.valor) {
        aviso(p, 'Teste a chave antes de confirmar — trocou algo depois do último teste.');
        return;
      }
      gravar(p, v);
    });

    p.querySelector('.ia-chave-apagar').addEventListener('click', function () {
      apagar(p);
    });

    setTimeout(function () {
      try {
        inp.focus();
      } catch (e) {}
    }, 50);

    return p;
  }

  function aviso(p, texto) {
    var a = p.querySelector('.ia-chave-aviso');
    if (!a) return;
    a.hidden = false;
    a.textContent = texto;
  }

  function lerEstado(p) {
    return fetch(URL_CHAVE, {
      method: 'GET',
      credentials: 'same-origin',
      headers: { Accept: 'application/json' },
    })
      .then(function (r) {
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.json();
      })
      .then(function (j) {
        return { tem_chave: Boolean(j && j.tem_chave), provedor: (j && j.provedor) || 'gemini' };
      })
      .catch(function (e) {
        /* O estado é diagnóstico: se não se lê, o painel abre em \"sem chave\"
         * e diz porquê. Um painel que não abre por não conseguir ler o estado
         * é um painel que o produtor não consegue usar para registar. */
        aviso(p, 'Não consegui ler o estado da chave: ' + e.message);
        return { tem_chave: false, provedor: 'gemini' };
      });
  }

  function gravar(p, chave) {
    fetch(URL_CHAVE, {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrf(),
      },
      body: JSON.stringify({ chave: chave }),
    })
      .then(function (r) {
        return r
          .json()
          .catch(function () {
            return {};
          })
          .then(function (j) {
            if (!r.ok || !j || j.ok !== true) {
              throw new Error((j && j.erro) || 'HTTP ' + r.status);
            }
            return j;
          });
      })
      .then(function (j) {
        p.querySelector('#ia-chave-input').value = '';
        /* Gravou: o valor testado saiu do campo, então a validação expira
         * junto — sem isto, o Confirmar ficava liberado para um campo vazio.
         * E o Apagar passa a existir, porque agora há chave. */
        ultimoTeste = { valor: '', valido: false };
        var btnGravar = p.querySelector('.ia-chave-gravar');
        if (btnGravar) btnGravar.disabled = true;
        var caixaTeste = p.querySelector('.ia-chave-teste');
        if (caixaTeste) caixaTeste.hidden = true;
        var btnApagar = p.querySelector('.ia-chave-apagar');
        if (btnApagar) btnApagar.hidden = false;
        var corpo = p.querySelector('.ia-chave-corpo');
        var estado = p.querySelector('.ia-chave-estado');
        var nota = estado ? estado.nextElementSibling : null;
        if (estado) {
          estado.className = 'ia-chave-estado ia-chave-ligada';
          estado.textContent = 'Agente da nuvem LIGADO';
        }
        if (nota && nota.classList.contains('ia-chave-nota')) {
          nota.textContent =
            'Provedor: ' +
            ((j && j.provedor) || 'gemini') +
            '. As respostas da IA podem vir da nuvem quando o motor local não estiver disponível.';
        }
        aviso(p, 'Chave gravada. O agente da nuvem está ligado.');
        fala('Chave do Gemini gravada. O agente da nuvem está ligado.');
      })
      .catch(function (e) {
        aviso(p, 'Não consegui gravar a chave: ' + e.message);
      });
  }

  function apagar(p) {
    fetch(URL_CHAVE, {
      method: 'DELETE',
      credentials: 'same-origin',
      headers: { 'X-CSRFToken': csrf() },
    })
      .then(function (r) {
        return r
          .json()
          .catch(function () {
            return {};
          })
          .then(function (j) {
            if (!r.ok || !j || j.ok !== true) {
              throw new Error((j && j.erro) || 'HTTP ' + r.status);
            }
            return j;
          });
      })
      .then(function () {
        p.querySelector('#ia-chave-input').value = '';
        ultimoTeste = { valor: '', valido: false };
        var btnGravar2 = p.querySelector('.ia-chave-gravar');
        if (btnGravar2) btnGravar2.disabled = true;
        var btnApagar2 = p.querySelector('.ia-chave-apagar');
        if (btnApagar2) btnApagar2.hidden = true;
        var estado = p.querySelector('.ia-chave-estado');
        var nota = estado ? estado.nextElementSibling : null;
        if (estado) {
          estado.className = 'ia-chave-estado ia-chave-desligada';
          estado.textContent = 'Agente da nuvem desligado';
        }
        if (nota && nota.classList.contains('ia-chave-nota')) {
          nota.textContent =
            'Sem chave, a IA responde só com o motor local — e o texto do produtor não sai do servidor.';
        }
        aviso(p, 'Chave apagada. O agente da nuvem está desligado.');
        fala('Chave apagada. O agente da nuvem está desligado.');
      })
      .catch(function (e) {
        aviso(p, 'Não consegui apagar a chave: ' + e.message);
      });
  }

  window.IaChave = {
    abrir: function () {
      var p = desenha({ tem_chave: false, provedor: 'gemini' });
      if (!p) return;
      lerEstado(p).then(function (estado) {
        /* O painel já está desenhado; o estado chega e só o bloco de cima
         * muda. Redesenhar tudo perderia o que o produtor já escreveu. */
        var corpo = p.querySelector('.ia-chave-corpo');
        if (!corpo) return;
        var velho = corpo.querySelector('.ia-chave-estado');
        var nota = velho ? velho.nextElementSibling : null;
        var btnApagar3 = p.querySelector('.ia-chave-apagar');
        if (btnApagar3) btnApagar3.hidden = !(estado && estado.tem_chave);
        if (velho && nota && nota.classList.contains('ia-chave-nota')) {
          velho.outerHTML = estadoHTML(estado).match(
            /<div class="ia-chave-estado[^>]*>[^<]*<\/div>/
          )[0];
          nota.outerHTML =
            '<div class="ia-chave-nota">' +
            (estado.tem_chave
              ? 'Provedor: ' +
                esc(estado.provedor || 'gemini') +
                '. As respostas da IA podem vir da nuvem quando o motor local não estiver disponível.'
              : 'Sem chave, a IA responde só com o motor local — e o texto do produtor não sai do servidor.') +
            '</div>';
        }
      });
    },
    fechar: fechaTudo,
  };
})();
