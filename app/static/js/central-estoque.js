/* Rascunhos de estoque: leitura, revisão humana e confirmação explícita. */
(() => {
  document.querySelectorAll('[data-central-ocr]').forEach((root) => {
    const leitura = root.querySelector('[data-ocr-leitura]');
    const revisao = root.querySelector('[data-ocr-revisao]');
    const entrada = root.querySelector('[data-ocr-entrada]');
    const campos = root.querySelector('[data-ocr-itens]');
    const lista = root.querySelector('[data-ocr-lista]');
    const status = root.querySelector('[data-ocr-status]');
    const confirmar = root.querySelector('[data-ocr-confirmar]');
    const novo = root.querySelector('[data-ocr-novo]');
    const adicionar = root.querySelector('[data-ocr-adicionar]');
    let artefato = null;
    let ocupado = false;
    let concluido = false;
    let pendente = null;

    function informar(texto, erro = false) {
      status.textContent = texto;
      status.dataset.error = String(erro);
    }

    function incluir(item = {}) {
      if (lista.children.length >= 1000) return;
      const fragment = root.querySelector('[data-ocr-item]').content.cloneNode(true);
      const linha = fragment.querySelector('fieldset');
      linha.querySelectorAll('[data-campo]').forEach((input) => {
        input.value = item[input.dataset.campo] ?? input.value;
      });
      linha.querySelector('[data-ocr-remover]').addEventListener('click', () => {
        linha.remove();
        adicionar.disabled = false;
        confirmar.disabled = lista.children.length === 0;
      });
      lista.append(fragment);
      adicionar.disabled = lista.children.length >= 1000;
      confirmar.disabled = false;
      return linha;
    }

    async function requisitar(url, body, json = false) {
      const response = await fetch(url, {
        method: 'POST', credentials: 'same-origin', body: json ? JSON.stringify(body) : body,
        headers: {
          'X-CSRFToken': leitura.querySelector('[name="csrfmiddlewaretoken"]').value,
          ...(json ? { 'Content-Type': 'application/json' } : {}),
        },
      });
      const result = await response.json();
      if (!response.ok || result.ok !== true) {
        const error = new Error(result.erro || 'Não foi possível concluir. Confira sua sessão e os dados.');
        // Apenas rejeições explícitas permitem corrigir o lote; falhas de servidor podem ter ocorrido após a gravação.
        error.rejeitado = response.status >= 400 && response.status < 500;
        if (result.campos?.itens) {
          const detalhes = Object.entries(result.campos.itens).map(([indice, erros]) => (
            `Item ${Number(indice) + 1}: ${Object.values(erros).flat().join(' ')}`
          )).filter((texto) => !texto.endsWith(': '));
          error.message += ` ${detalhes.join(' ')}`;
        }
        throw error;
      }
      return result;
    }

    adicionar.addEventListener('click', () => incluir()?.querySelector('input').focus());
    leitura.addEventListener('submit', async (event) => {
      event.preventDefault();
      if (ocupado || artefato) return;
      const data = new FormData(leitura);
      if (!data.get('imagem')?.size && !String(data.get('texto') || '').trim()) {
        informar('Selecione uma imagem ou digite pelo menos um item.', true);
        return;
      }
      ocupado = true;
      entrada.disabled = true;
      informar('Preparando o rascunho para revisão…');
      try {
        const result = await requisitar(root.dataset.leituraUrl, data);
        if (!Number.isInteger(result.artefato_id) || !Array.isArray(result.itens)) throw new Error('Resposta inválida.');
        artefato = result.artefato_id;
        lista.replaceChildren();
        result.itens.forEach(incluir);
        if (!result.itens.length) incluir();
        revisao.hidden = false;
        novo.hidden = false;
        informar(`${result.aviso || ''} Confira os itens antes de confirmar. O estoque ainda não foi alterado.`.trim());
        lista.querySelector('input')?.focus();
      } catch (error) {
        informar(error.rejeitado ? error.message : 'Não foi possível preparar a revisão. Confira a conexão e tente novamente.', true);
      } finally {
        ocupado = false;
        entrada.disabled = Boolean(artefato);
      }
    });

    revisao.addEventListener('submit', async (event) => {
      event.preventDefault();
      if (ocupado || concluido || !artefato) return;
      if (!pendente) {
        if (!revisao.reportValidity() || !lista.children.length) return;
        pendente = {
          artefato_id: artefato, propriedade_id: Number(root.dataset.propriedade),
          itens: Array.from(lista.children, (linha) => Object.fromEntries(
            Array.from(linha.querySelectorAll('[data-campo]'), (input) => [input.dataset.campo, input.value.trim()]),
          )),
        };
      }
      ocupado = true;
      campos.disabled = true;
      confirmar.disabled = true;
      novo.disabled = true;
      informar('Confirmando os itens no estoque…');
      try {
        const result = await requisitar(root.dataset.confirmacaoUrl, pendente, true);
        concluido = true;
        pendente = null;
        informar(result.reutilizado ? 'Este rascunho já foi gravado. Nenhum item foi duplicado.' : result.resposta);
        confirmar.textContent = 'Estoque confirmado';
      } catch (error) {
        if (error.rejeitado) {
          pendente = null;
          informar(error.message, true);
        } else {
          informar('Não foi possível receber a confirmação. Tente confirmar novamente: o mesmo rascunho será reutilizado para evitar duplicações. Mantenha esta página aberta.', true);
          confirmar.textContent = 'Tentar confirmar o mesmo rascunho';
        }
      } finally {
        ocupado = false;
        campos.disabled = concluido || Boolean(pendente);
        confirmar.disabled = concluido;
        novo.disabled = Boolean(pendente);
      }
    });

    novo.addEventListener('click', () => {
      if (ocupado || pendente) return;
      artefato = null;
      concluido = false;
      leitura.reset();
      lista.replaceChildren();
      revisao.hidden = true;
      novo.hidden = true;
      entrada.disabled = false;
      campos.disabled = false;
      adicionar.disabled = false;
      confirmar.disabled = false;
      confirmar.textContent = 'Confirmar itens no estoque';
      informar('Envie outro documento ou digite uma nova lista.');
      leitura.querySelector('input[type="file"]').focus();
    });
  });
})();
