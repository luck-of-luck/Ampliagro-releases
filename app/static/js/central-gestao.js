/* Uploads deliberados: o servidor é responsável por validação e isolamento. */
(() => {
  document.querySelectorAll('[data-contrapartes]').forEach((form) => {
    const add = form.querySelector('[data-adicionar-contraparte]');
    const count = form.querySelector('[name="contrapartes-TOTAL_FORMS"]');
    const maximum = 100;
    add.disabled = Number(count.value) >= maximum;
    add.addEventListener('click', () => {
      const index = Number(count.value);
      if (!Number.isInteger(index) || index < 0 || index >= maximum) return;
      const fragment = form.querySelector('[data-contraparte-modelo]').content.cloneNode(true);
      fragment.querySelectorAll('[name], [id], [for]').forEach((element) => {
        ['name', 'id', 'for'].forEach((attribute) => {
          if (element.hasAttribute(attribute)) element.setAttribute(attribute, element.getAttribute(attribute).replaceAll('__prefix__', String(index)));
        });
      });
      const firstInput = fragment.querySelector('select, input');
      form.querySelector('[data-contrapartes-lista]').append(fragment);
      count.value = String(index + 1);
      add.disabled = index + 1 >= maximum;
      firstInput?.focus();
    });
  });
  document.querySelectorAll('[data-central-upload]').forEach((form) => {
    let enviando = false;
    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      if (enviando) return;
      const button = form.querySelector('button[type="submit"]');
      const status = form.querySelector('[data-upload-status]');
      const data = new FormData(form);
      const url = form.hasAttribute('data-extrato')
        ? `/api/contas-bancarias/${encodeURIComponent(data.get('conta'))}/importar_ofx/`
        : form.action;
      enviando = true;
      button.disabled = true;
      status.dataset.error = 'false';
      status.textContent = 'Importando e conferindo o arquivo…';
      try {
        let response;
        let result;
        try {
          response = await fetch(url, {method:'POST', body:data, credentials:'same-origin',
            headers:{'X-CSRFToken':data.get('csrfmiddlewaretoken')}});
          result = await response.json();
        } catch {
          throw new Error('Não foi possível confirmar a importação. Confira os registros antes de reenviar.');
        }
        if (!response.ok || result.ok === false) throw new Error(result.erro || result.detail || 'Não foi possível importar. Confira o arquivo e sua permissão.');
        status.textContent = result.mensagem || (result.duplicado ? 'Documento já importado; nenhum registro duplicado.' : 'Importação concluída. Atualize a central para conferir os registros.');
      } catch (error) {
        status.dataset.error = 'true';
        status.textContent = error.message || 'Falha de conexão. Confira os registros antes de reenviar.';
      } finally {enviando = false; button.disabled = false;}
    });
  });
})();
