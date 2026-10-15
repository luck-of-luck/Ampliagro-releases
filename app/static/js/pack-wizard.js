/**
 * Pack Wizard - primeiro arranque
 * Permite ao produtor escolher quais culturas/packs instalar
 */

(function (global) {
  'use strict';

  var Wizard = (function () {
    var modal = null;
    var state = {
      selected: {}, // packId -> true
      groups: [],
      loading: true,
    };

    function createModal() {
      if (modal) return modal;

      modal = document.createElement('div');
      modal.className = 'pack-wizard-modal';
      modal.innerHTML = modalHTML();
      document.body.appendChild(modal);

      bindEvents();
      return modal;
    }

    function modalHTML() {
      return (
        '' +
        '<div class="modal-backdrop"></div>' +
        '<div class="modal-dialog modal-xl" role="document">' +
        '<div class="modal-content">' +
        '<div class="modal-header">' +
        '<h5 class="modal-title"><i class="bi bi-box-seam"></i> Bem-vindo ao Ampliagro Desktop</h5>' +
        '</div>' +
        '<div class="modal-body" style="max-height:70vh;overflow:auto;">' +
        '<p class="text-muted mb-3">Escolha as culturas que você cultiva. Os packs serão baixados e instalados localmente para funcionar 100% offline.</p>' +
        '<div id="wizard-groups"></div>' +
        '</div>' +
        '<div class="modal-footer">' +
        '<div class="wizard-progress text-muted small mb-2" id="wizard-progress"></div>' +
        '<button type="button" class="btn btn-secondary" id="wizard-select-none">Nenhum</button>' +
        '<button type="button" class="btn btn-outline-primary" id="wizard-select-all">Todos (' +
        totalCultures() +
        ' culturas)</button>' +
        '<button type="button" class="btn btn-primary" id="wizard-install" disabled>' +
        '<span class="spinner-border spinner-border-sm me-1 d-none" id="wizard-spinner"></span>' +
        'Instalar selecionados</button>' +
        '</div>' +
        '</div>' +
        '</div>'
      );
    }

    function totalCultures() {
      var total = 0;
      state.groups.forEach(function (g) {
        g.subgroups.forEach(function (sg) {
          total += sg.culture_count;
        });
      });
      return total;
    }

    function bindEvents() {
      modal.querySelector('#wizard-select-all').addEventListener('click', selectAll);
      modal.querySelector('#wizard-select-none').addEventListener('click', selectNone);
      modal.querySelector('#wizard-install').addEventListener('click', installSelected);
      modal.querySelector('.modal-backdrop').addEventListener('click', function (e) {
        if (e.target === e.currentTarget) cancel();
      });
    }

    function renderGroups() {
      var container = modal.querySelector('#wizard-groups');
      container.innerHTML = state.groups
        .map(function (g) {
          return (
            '' +
            '<div class="card mb-3">' +
            '<div class="card-header d-flex justify-content-between align-items-center">' +
            '<h6 class="mb-0"><i class="' +
            g.icon +
            '"></i> ' +
            g.title +
            '</h6>' +
            '<span class="badge bg-secondary">' +
            g.subgroups.reduce(function (a, b) {
              return a + b.culture_count;
            }, 0) +
            ' culturas</span>' +
            '</div>' +
            '<div class="card-body">' +
            '<div class="row g-2">' +
            g.subgroups
              .map(function (sg) {
                var installed = global.PackLoader && global.PackLoader.isInstalled(sg.id);
                var selected = state.selected[sg.id];
                return (
                  '' +
                  '<div class="col-md-6 col-lg-4 col-xl-3">' +
                  '<div class="form-check pack-option ' +
                  (selected ? 'selected' : '') +
                  (installed ? ' installed' : '') +
                  '" data-pack="' +
                  sg.id +
                  '">' +
                  '<input class="form-check-input" type="checkbox" id="pack-' +
                  sg.id +
                  '" ' +
                  (selected ? 'checked' : '') +
                  (installed ? ' disabled' : '') +
                  '>' +
                  '<label class="form-check-label w-100 d-flex flex-column align-items-start p-2" for="pack-' +
                  sg.id +
                  '">' +
                  '<i class="' +
                  sg.icon +
                  ' fa-2x text-primary mb-1"></i>' +
                  '<strong>' +
                  sg.title +
                  '</strong>' +
                  '<small class="text-muted">' +
                  sg.culture_count +
                  ' culturas</small>' +
                  (installed ? '<span class="badge bg-success mt-1">Instalado</span>' : '') +
                  '</label>' +
                  '</div>' +
                  '</div>'
                );
              })
              .join('') +
            '</div>' +
            '</div>' +
            '</div>'
          );
        })
        .join('');

      // Bind checkboxes
      modal.querySelectorAll('.pack-option input').forEach(function (cb) {
        cb.addEventListener('change', function () {
          var packId = cb.closest('.pack-option').dataset.pack;
          if (cb.checked) state.selected[packId] = true;
          else delete state.selected[packId];
          updateUI();
        });
      });
    }

    function updateUI() {
      var count = Object.keys(state.selected).length;
      var installBtn = modal.querySelector('#wizard-install');
      var progress = modal.querySelector('#wizard-progress');
      installBtn.disabled = count === 0;
      progress.textContent =
        count + ' pack(s) selecionado(s), ' + totalSelectedCultures() + ' culturas';
      modal.querySelectorAll('.pack-option').forEach(function (el) {
        el.classList.toggle('selected', state.selected[el.dataset.pack]);
      });
    }

    function totalSelectedCultures() {
      var total = 0;
      Object.keys(state.selected).forEach(function (packId) {
        var sg = state.groups
          .flatMap(function (g) {
            return g.subgroups;
          })
          .find(function (sg) {
            return sg.id === packId;
          });
        if (sg) total += sg.culture_count;
      });
      return total;
    }

    function selectAll() {
      state.groups.forEach(function (g) {
        g.subgroups.forEach(function (sg) {
          if (!global.PackLoader.isInstalled(sg.id)) state.selected[sg.id] = true;
        });
      });
      renderGroups();
      updateUI();
    }

    function selectNone() {
      state.selected = {};
      renderGroups();
      updateUI();
    }

    async function installSelected() {
      var packs = Object.keys(state.selected);
      if (packs.length === 0) return;

      var btn = modal.querySelector('#wizard-install');
      var spinner = modal.querySelector('#wizard-spinner');
      btn.disabled = true;
      spinner.classList.remove('d-none');
      btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Instalando...';

      var errors = [];
      for (var i = 0; i < packs.length; i++) {
        var packId = packs[i];
        try {
          btn.innerHTML =
            '<span class="spinner-border spinner-border-sm me-1"></span> Instalando ' +
            packId +
            ' (' +
            (i + 1) +
            '/' +
            packs.length +
            ')';
          await global.PackLoader.loadPack(packId);
        } catch (err) {
          errors.push(packId + ': ' + err.message);
        }
      }

      spinner.classList.add('d-none');
      btn.innerHTML = 'Instalar selecionados';
      btn.disabled = false;

      if (errors.length === 0) {
        showToast('Sucesso', packs.length + ' pack(s) instalado(s) com sucesso!', 'success');
        close();
      } else {
        showToast('Aviso', errors.length + ' pack(s) falharam: ' + errors.join('; '), 'warning');
      }
    }

    function cancel() {
      if (Object.keys(state.selected).length > 0) {
        if (!confirm('Sair sem instalar? As culturas não instaladas não funcionarão offline.'))
          return;
      }
      close();
    }

    function close() {
      if (modal && modal.parentNode) modal.parentNode.removeChild(modal);
      modal = null;
    }

    function showToast(title, msg, type) {
      // Reusa toast system se existir, senão alert
      if (global.showToast) global.showToast(title, msg, type);
      else alert(title + ': ' + msg);
    }

    // API pública
    return {
      open: async function () {
        if (state.loading) {
          try {
            state.groups = await global.PackLoader.listPacks();
            state.loading = false;
          } catch (e) {
            console.error('[Wizard] Falha ao carregar packs:', e);
            alert('Erro ao carregar lista de packs: ' + e.message);
            return;
          }
        }
        createModal();
        renderGroups();
        updateUI();
      },
      close: close,
    };
  })();

  global.PackWizard = Wizard;
})(typeof window !== 'undefined' ? window : this);
