let editandoId = null;

// ── Helpers ──
function getCSRFToken() {
  return document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';
}

function showToast(msg, type) {
  var t = document.getElementById('toast');
  if (!t) return;
  t.textContent = msg;
  t.className = 'toast toast-' + type + ' show';
  setTimeout(function () {
    t.classList.remove('show');
  }, 3000);
}

function showLoading(btn) {
  if (!btn) return;
  btn.disabled = true;
  btn.dataset.originalHtml = btn.innerHTML;
  btn.innerHTML = '<span class="loading-spinner"></span> Salvando...';
}

function hideLoading(btn) {
  if (!btn) return;
  btn.disabled = false;
  if (btn.dataset.originalHtml) {
    btn.innerHTML = btn.dataset.originalHtml;
  }
}

// ── Strategy 4: Input Masks ──
var INPUT_MASK_CONFIG = {
  moeda: { prefix: 'R$ ', decimal: 2, sep: ',', group: '.' },
  area: { decimal: 2, suffix: ' ha' },
  percent: { decimal: 1, suffix: '%' },
};

function applyInputMask(input) {
  var mask = input.dataset.mask || input.getAttribute('data-mask');
  if (!mask) return;
  input.addEventListener('input', function () {
    var raw = this.value.replace(/[^\d]/g, '');
    if (mask === 'moeda') {
      if (!raw) {
        this.value = '';
        return;
      }
      var num = parseInt(raw) / 100;
      this.value =
        'R$ ' + num.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    } else if (mask === 'area') {
      if (!raw) {
        this.value = '';
        return;
      }
      var num = parseFloat(raw) / 100;
      this.value = num.toFixed(2).replace('.', ',') + ' ha';
    } else if (mask === 'data') {
      var d = raw.replace(/^(\d{2})(\d)/, '$1/$2').replace(/^(\d{2}\/\d{2})(\d)/, '$1/$2');
      this.value = d.substring(0, 10);
    }
  });
  input.addEventListener('blur', function () {
    if (mask === 'moeda' && !this.value) {
      this.value = '';
      return;
    }
    if (mask === 'moeda' && this.value === 'R$ ') {
      this.value = '';
    }
  });
}

function setupInputMasks(container) {
  if (!container) container = document;
  container.querySelectorAll('[data-mask]').forEach(applyInputMask);
}

// ── Strategy 4: Help Tooltips ──
function renderHelpTooltip(text) {
  return (
    '<span class="help-tooltip" onclick="event.stopPropagation()" data-help="' +
    encodeURIComponent(text) +
    '">?<span class="help-tooltip-text">' +
    text +
    '</span></span>'
  );
}

// ── Strategy 1: Smart Defaults ──
function initSmartDefaults(formId) {
  var form = document.getElementById(formId);
  if (!form) return;

  // Ano agricola
  var anoField = form.querySelector('[name="ano"]');
  if (anoField && !anoField.value) {
    var now = new Date();
    var year = now.getFullYear();
    var nextYear = year + 1;
    // Se estamos no segundo semestre, sugere ano agricola 2025/2026
    if (now.getMonth() >= 6) {
      if (anoField.tagName === 'SELECT') {
        var val = year + '/' + nextYear;
        for (var i = 0; i < anoField.options.length; i++) {
          if (anoField.options[i].value === val) {
            anoField.value = val;
            break;
          }
        }
      } else {
        anoField.value = year + '/' + nextYear;
      }
    } else {
      if (anoField.tagName === 'SELECT') {
        var val2 = String(year);
        for (var j = 0; j < anoField.options.length; j++) {
          if (anoField.options[j].value === val2) {
            anoField.value = val2;
            break;
          }
        }
      } else {
        anoField.value = year;
      }
    }
  }

  // Ultima propriedade usada
  var propField = form.querySelector('[name="propriedade"]');
  if (propField && propField.tagName === 'SELECT') {
    var lastProp = localStorage.getItem('ampliagro_last_propriedade');
    if (lastProp) {
      for (var k = 0; k < propField.options.length; k++) {
        if (String(propField.options[k].value) === lastProp) {
          propField.value = lastProp;
          break;
        }
      }
    }
  }
}

// ── Strategy 1: Salvar e Continuar ──
function renderKeepToggle() {
  return '<label class="keep-toggle"><input type="checkbox" id="keep-fields-toggle" checked><span class="keep-toggle-track"></span><span class="keep-toggle-label">Manter dados fixos apos salvar</span></label>';
}

function shouldKeepFields() {
  var cb = document.getElementById('keep-fields-toggle');
  return cb ? cb.checked : false;
}

var KEEP_FIELDS_DEFAULT = [
  'propriedade',
  'ano',
  'cultura',
  'tipo',
  'categoria',
  'fornecedor',
  'especie',
  'tipo_producao',
];

function afterSaveHandler(formId, btn) {
  if (!shouldKeepFields()) return;
  var form = document.getElementById(formId);
  if (!form) return;
  var keepNames = KEEP_FIELDS_DEFAULT;
  var keep = document.getElementById('keep-fields-list');
  if (keep) {
    var custom = (keep.value || '')
      .split(',')
      .map(function (s) {
        return s.trim();
      })
      .filter(Boolean);
    if (custom.length) keepNames = custom;
  }
  form.querySelectorAll('input, select, textarea').forEach(function (el) {
    if (el.name && keepNames.indexOf(el.name) >= 0) return;
    if (el.type === 'checkbox') el.checked = false;
    else if (el.type === 'hidden') {
    } else el.value = '';
  });
  // Foca no primeiro campo vazio
  var first = form.querySelector(
    'input:not([type=hidden]):not([disabled]), select:not([disabled])'
  );
  if (first)
    setTimeout(function () {
      first.focus();
    }, 100);
}

// ── Strategy 1: Keyboard Navigation ──
function setupKeyboardNav(formId) {
  var form = document.getElementById(formId);
  if (!form) return;
  form.addEventListener('keydown', function (e) {
    if (e.key === 'Enter' && e.target.tagName !== 'TEXTAREA') {
      var inputs = Array.from(
        form.querySelectorAll(
          'input:not([type=hidden]):not([type=checkbox]):not([disabled]), select:not([disabled]), textarea:not([disabled])'
        )
      );
      var idx = inputs.indexOf(e.target);
      if (idx >= 0 && idx < inputs.length - 1) {
        e.preventDefault();
        inputs[idx + 1].focus();
      } else if (idx === inputs.length - 1) {
        e.preventDefault();
        var submitBtn = form.querySelector('button[type="submit"]');
        if (submitBtn) submitBtn.click();
      }
    }
  });
}

// ── Strategy 3: Duplicar Registro ──
function duplicateRecord(endpoint, id, formId, submitFn) {
  if (!id) return;
  fetch(endpoint + id + '/')
    .then(function (r) {
      return r.json();
    })
    .then(function (data) {
      delete data.id;
      delete data.id_local;
      var form = document.getElementById(formId);
      if (!form) return;
      preencherForm(formId, data);
      editandoId = null;
      var btn = form.querySelector('button[type="submit"]');
      if (btn) btn.innerHTML = btn.dataset.originalHtml || '<i class="bi bi-check-lg"></i> Salvar';
      var cancelBtn = form.querySelector('.btn-cancel-edit');
      if (cancelBtn) cancelBtn.remove();
      form.onsubmit = function (e) {
        return submitFn(e);
      };
      showToast('Registro duplicado! Ajuste os campos e salve.', 'info');
    })
    .catch(function () {
      showToast('Erro ao duplicar registro', 'error');
    });
}

// ── Strategy 3: Edicao Inline ──
function setupInlineEdit(tableId, endpoint) {
  var table = document.getElementById(tableId);
  if (!table) return;
  table.querySelectorAll('td[data-inline]').forEach(function (cell) {
    cell.addEventListener('dblclick', function () {
      if (this.querySelector('input')) return;
      var field = this.dataset.inline;
      var recordId = this.dataset.id;
      var current = this.textContent.trim();
      var input = document.createElement('input');
      input.type = 'text';
      input.value = current;
      input.className = 'inline-edit-input';
      input.style.width = this.offsetWidth - 10 + 'px';
      this.textContent = '';
      this.appendChild(input);
      input.focus();
      input.select();
      function save() {
        var newVal = input.value.trim();
        if (newVal !== current && recordId) {
          var body = {};
          body[field] = newVal;
          fetch(endpoint + recordId + '/', {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCSRFToken() },
            body: JSON.stringify(body),
          })
            .then(function (r) {
              if (r.ok) {
                showToast('Atualizado!', 'success');
                cell.textContent = newVal;
              } else {
                cell.textContent = current;
                showToast('Erro ao atualizar', 'error');
              }
            })
            .catch(function () {
              cell.textContent = current;
              showToast('Erro de conexao', 'error');
            });
        } else {
          cell.textContent = newVal || current;
        }
      }
      input.addEventListener('blur', save);
      input.addEventListener('keydown', function (ev) {
        if (ev.key === 'Enter') {
          ev.preventDefault();
          input.blur();
        }
        if (ev.key === 'Escape') {
          cell.textContent = current;
        }
      });
    });
  });
}

// ── Validation ──
function validateField(input) {
  if (!input || !input.name) return true;
  var value = (input.value || '').trim();
  var isValid = true;
  var group = input.closest('.form-group') || input.parentElement;
  var existingError = group ? group.querySelector('.field-error') : null;
  if (existingError) existingError.remove();
  input.classList.remove('error');

  if (input.required && !value && input.type !== 'checkbox') {
    isValid = false;
  }
  if (input.type === 'number' && value) {
    var num = parseFloat(value);
    if (input.min && num < parseFloat(input.min)) isValid = false;
    if (input.max && num > parseFloat(input.max)) isValid = false;
  }

  if (!isValid) {
    input.classList.add('error');
    if (group) {
      var err = document.createElement('small');
      err.className = 'field-error';
      err.textContent = 'Campo obrigatório';
      group.appendChild(err);
    }
  }
  return isValid;
}

function validateForm(formId) {
  var form = document.getElementById(formId);
  if (!form) return true;
  var inputs = form.querySelectorAll('input, select, textarea');
  var valid = true;
  inputs.forEach(function (el) {
    if (el.name && el.name !== 'csrfmiddlewaretoken' && !validateField(el)) valid = false;
  });
  return valid;
}

function preencherForm(formId, data) {
  var form = document.getElementById(formId);
  if (!form) return;
  Object.keys(data).forEach(function (key) {
    var el = document.getElementById('id_' + key) || form.querySelector('[name="' + key + '"]');
    if (!el) return;
    if (el.type === 'checkbox') el.checked = !!data[key];
    else if (el.type === 'date') el.value = data[key] ? String(data[key]).substring(0, 10) : '';
    else el.value = data[key] != null ? data[key] : '';
  });
}

function setupEditMode(formId, apiEndpoint, id) {
  editandoId = id;
  var form = document.getElementById(formId);
  if (!form) return;
  var btn = form.querySelector('button[type="submit"]');
  var origBtnHtml = btn ? btn.innerHTML : '';
  var origSubmit = form.onsubmit;
  if (btn) btn.innerHTML = '<i class="bi bi-check-lg"></i> Atualizar';
  var cancelBtn = form.querySelector('.btn-cancel-edit');
  if (!cancelBtn) {
    cancelBtn = document.createElement('button');
    cancelBtn.type = 'button';
    cancelBtn.className = 'btn-secondary btn-cancel-edit';
    cancelBtn.textContent = 'Cancelar';
    cancelBtn.onclick = function () {
      form.reset();
      editandoId = null;
      if (btn) btn.innerHTML = origBtnHtml;
      form.onsubmit = origSubmit;
      cancelBtn.remove();
    };
    if (btn && btn.parentNode) btn.parentNode.appendChild(cancelBtn);
    else form.appendChild(cancelBtn);
  }
  try {
    form.scrollIntoView({ behavior: 'smooth', block: 'start' });
  } catch (e) {}
}

async function atualizarRegistro(event, endpoint, formId, id) {
  event.preventDefault();
  var form = document.getElementById(formId);
  var btn = form.querySelector('button[type="submit"]');
  showLoading(btn);
  var data = {};
  form.querySelectorAll('[name]').forEach(function (el) {
    var key = el.getAttribute('name');
    if (key === 'csrfmiddlewaretoken') return;
    if (el.type === 'checkbox') data[key] = el.checked;
    else if (el.type === 'number') data[key] = el.value === '' ? null : parseFloat(el.value);
    else if (el.type === 'date') data[key] = el.value || null;
    else if (el.value === '') {
      /* omite: evita null em campo texto nao-nulavel no PATCH */
    } else data[key] = el.value;
  });
  try {
    var resp = await fetch(endpoint + id + '/', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCSRFToken() },
      body: JSON.stringify(data),
    });
    if (resp.ok) {
      showToast('Atualizado com sucesso!', 'success');
      setTimeout(function () {
        location.reload();
      }, 800);
    } else {
      var err = await resp.json();
      showToast('Erro: ' + JSON.stringify(err), 'error');
    }
  } catch (e) {
    showToast('Erro de conexão: ' + e.message, 'error');
  }
  hideLoading(btn);
  return false;
}

function openConfirmModal(message, onConfirm) {
  var modal = document.getElementById('confirm-modal');
  if (!modal) return;
  modal.querySelector('.confirm-message').textContent = message;
  modal.style.display = 'flex';
  function cleanup() {
    modal.style.display = 'none';
    confirmBtn.removeEventListener('click', handleConfirm);
    cancelBtn.removeEventListener('click', handleCancel);
  }
  function handleConfirm() {
    cleanup();
    if (typeof onConfirm === 'function') onConfirm();
  }
  function handleCancel() {
    cleanup();
  }
  var confirmBtn = modal.querySelector('.confirm-yes');
  var cancelBtn = modal.querySelector('.confirm-no');
  confirmBtn.addEventListener('click', handleConfirm);
  cancelBtn.addEventListener('click', handleCancel);
}

function carregarSelect(endpoint, selectId, valueKey, labelKey, emptyMsg) {
  var sel = document.getElementById(selectId);
  if (!sel) return;
  emptyMsg = emptyMsg || 'Carregando...';
  sel.innerHTML = '<option value="">' + emptyMsg + '</option>';
  fetch(endpoint)
    .then(function (r) {
      return r.json();
    })
    .then(function (data) {
      sel.innerHTML = '<option value="">Selecione...</option>';
      (data.results || data).forEach(function (item) {
        var opt = document.createElement('option');
        opt.value = item[valueKey || 'id'];
        opt.textContent = item[labelKey || 'nome'];
        sel.appendChild(opt);
      });
    })
    .catch(function () {
      sel.innerHTML = '<option value="">Erro ao carregar</option>';
    });
}

// Edit functions (backward compat)
function editarSafra(id) {
  fetch('/api/safras/' + id + '/')
    .then(function (r) {
      return r.json();
    })
    .then(function (data) {
      preencherForm('safra-form', {
        propriedade: data.propriedade,
        talhao: data.talhao,
        cultura: data.cultura,
        safra_nome: data.safra_nome,
        ano: data.ano,
        data_plantio: data.data_plantio,
        data_colheita: data.data_colheita,
        area_plantada: data.area_plantada,
        area_colhida: data.area_colhida,
        producao_total: data.producao_total,
        receita_estimada: data.receita_estimada,
      });
      setupEditMode('safra-form', '/api/safras/', id);
      document.getElementById('safra-form').onsubmit = function (e) {
        e.preventDefault();
        return atualizarRegistro(e, '/api/safras/', 'safra-form', id);
      };
    })
    .catch(function () {
      showToast('Erro ao carregar safra', 'error');
    });
}
function editarTalhao(id) {
  fetch('/api/talhoes/' + id + '/')
    .then(function (r) {
      return r.json();
    })
    .then(function (data) {
      preencherForm('talhao-form', {
        propriedade: data.propriedade,
        nome: data.nome,
        area_hectare: data.area_hectare,
        cultura_atual: data.cultura_atual,
        tipo_solo: data.tipo_solo,
        ativo: data.ativo,
      });
      setupEditMode('talhao-form', '/api/talhoes/', id);
      document.getElementById('talhao-form').onsubmit = function (e) {
        e.preventDefault();
        return atualizarRegistro(e, '/api/talhoes/', 'talhao-form', id);
      };
    })
    .catch(function () {
      showToast('Erro ao carregar talhão', 'error');
    });
}
function editarMaquinario(id) {
  fetch('/api/maquinarios/' + id + '/')
    .then(function (r) {
      return r.json();
    })
    .then(function (data) {
      preencherForm('maquinario-form', {
        propriedade: data.propriedade,
        tipo: data.tipo,
        nome: data.nome,
        marca: data.marca,
        modelo: data.modelo,
        ano_fabricacao: data.ano_fabricacao,
        horas_uso: data.horas_uso,
        ultima_manutencao: data.ultima_manutencao,
        proxima_manutencao: data.proxima_manutencao,
        ativo: data.ativo,
      });
      setupEditMode('maquinario-form', '/api/maquinarios/', id);
      document.getElementById('maquinario-form').onsubmit = function (e) {
        e.preventDefault();
        return atualizarRegistro(e, '/api/maquinarios/', 'maquinario-form', id);
      };
    })
    .catch(function () {
      showToast('Erro ao carregar maquinário', 'error');
    });
}
function editarFinanceiro(id) {
  fetch('/api/lancamentos/' + id + '/')
    .then(function (r) {
      return r.json();
    })
    .then(function (data) {
      preencherForm('financeiro-form', {
        propriedade: data.propriedade,
        tipo: data.tipo,
        categoria: data.categoria,
        valor: data.valor,
        data: data.data,
        descricao: data.descricao,
        talhao: data.talhao,
        pago: data.pago,
        data_pagamento: data.data_pagamento,
        conta_bancaria: data.conta_bancaria || '',
        tipo_documento_lcdpr: data.tipo_documento_lcdpr || '6',
        numero_documento: data.numero_documento || '',
        tipo_lancamento_lcdpr: data.tipo_lancamento_lcdpr || '',
      });
      setupEditMode('financeiro-form', '/api/lancamentos/', id);
      document.getElementById('financeiro-form').onsubmit = function (e) {
        e.preventDefault();
        return atualizarRegistro(e, '/api/lancamentos/', 'financeiro-form', id);
      };
    })
    .catch(function () {
      showToast('Erro ao carregar lançamento', 'error');
    });
}
function editarEstoque(id) {
  fetch('/api/estoque/' + id + '/')
    .then(function (r) {
      return r.json();
    })
    .then(function (data) {
      preencherForm('estoque-form', {
        propriedade: data.propriedade,
        categoria: data.categoria,
        nome: data.nome,
        quantidade: data.quantidade,
        unidade: data.unidade,
        local: data.local,
        data_validade: data.data_validade,
        observacao: data.observacao,
      });
      setupEditMode('estoque-form', '/api/estoque/', id);
      document.getElementById('estoque-form').onsubmit = function (e) {
        e.preventDefault();
        return atualizarRegistro(e, '/api/estoque/', 'estoque-form', id);
      };
    })
    .catch(function () {
      showToast('Erro ao carregar item', 'error');
    });
}
function editarColmeia(id) {
  fetch('/api/colmeias/' + id + '/')
    .then(function (r) {
      return r.json();
    })
    .then(function (data) {
      preencherForm('colmeia-form', {
        propriedade: data.propriedade,
        identificacao: data.identificacao,
        tipo_abelha: data.tipo_abelha,
        data_instalacao: data.data_instalacao,
        localizacao: data.localizacao,
        ativa: data.ativa,
        observacao: data.observacao,
      });
      setupEditMode('colmeia-form', '/api/colmeias/', id);
      document.getElementById('colmeia-form').onsubmit = function (e) {
        e.preventDefault();
        return atualizarRegistro(e, '/api/colmeias/', 'colmeia-form', id);
      };
    })
    .catch(function () {
      showToast('Erro ao carregar colmeia', 'error');
    });
}
function editarPropriedade(id) {
  fetch('/api/propriedades/' + id + '/')
    .then(function (r) {
      return r.json();
    })
    .then(function (data) {
      preencherForm('propriedade-form', {
        nome: data.nome,
        area_total: data.area_total,
        uf: data.uf,
        cidade: data.cidade,
        endereco: data.endereco,
        bioma: data.bioma,
        moeda: data.moeda,
        cpf_cnpj: data.cpf_cnpj || '',
        caepf: data.caepf || '',
        inscricao_estadual: data.inscricao_estadual || '',
        tipo_exploracao: data.tipo_exploracao || '1',
        participacao: data.participacao || '100.00',
      });
      setupEditMode('propriedade-form', '/api/propriedades/', id);
      document.getElementById('propriedade-form').onsubmit = function (e) {
        e.preventDefault();
        return atualizarRegistro(e, '/api/propriedades/', 'propriedade-form', id);
      };
    })
    .catch(function () {
      showToast('Erro ao carregar propriedade', 'error');
    });
}
function editarInsumo(id) {
  fetch('/api/insumos/' + id + '/')
    .then(function (r) {
      return r.json();
    })
    .then(function (data) {
      preencherForm('insumo-form', {
        propriedade: data.propriedade,
        nome: data.nome,
        categoria: data.categoria,
        quantidade: data.quantidade,
        unidade: data.unidade,
        valor_unitario: data.valor_unitario,
        fornecedor: data.fornecedor,
      });
      setupEditMode('insumo-form', '/api/insumos/', id);
      document.getElementById('insumo-form').onsubmit = function (e) {
        e.preventDefault();
        return atualizarRegistro(e, '/api/insumos/', 'insumo-form', id);
      };
    })
    .catch(function () {
      showToast('Erro ao carregar insumo', 'error');
    });
}
function editarAnimal(id) {
  fetch('/api/animais/' + id + '/')
    .then(function (r) {
      return r.json();
    })
    .then(function (data) {
      preencherForm('animal-form', {
        propriedade: data.propriedade,
        especie: data.especie,
        tipo_producao: data.tipo_producao,
        raca: data.raca,
        quantidade: data.quantidade,
        peso_medio: data.peso_medio,
        data_entrada: data.data_entrada,
      });
      setupEditMode('animal-form', '/api/animais/', id);
      document.getElementById('animal-form').onsubmit = function (e) {
        e.preventDefault();
        return atualizarRegistro(e, '/api/animais/', 'animal-form', id);
      };
    })
    .catch(function () {
      showToast('Erro ao carregar animal', 'error');
    });
}
function editarLote(id) {
  fetch('/api/lotes-aquaticos/' + id + '/')
    .then(function (r) {
      return r.json();
    })
    .then(function (data) {
      preencherForm('lote-form', {
        propriedade: data.propriedade,
        especie: data.especie,
        sistema: data.sistema,
        ambiente: data.ambiente,
        quantidade: data.quantidade,
        biomassa_media: data.biomassa_media,
        data_povoamento: data.data_povoamento,
        observacao: data.observacao,
      });
      setupEditMode('lote-form', '/api/lotes-aquaticos/', id);
      document.getElementById('lote-form').onsubmit = function (e) {
        e.preventDefault();
        return atualizarRegistro(e, '/api/lotes-aquaticos/', 'lote-form', id);
      };
    })
    .catch(function () {
      showToast('Erro ao carregar lote', 'error');
    });
}
function editarMIP(id) {
  fetch('/api/monitoramentos-praga/' + id + '/')
    .then(function (r) {
      return r.json();
    })
    .then(function (data) {
      preencherForm('mip-form', {
        talhao: data.talhao,
        cultura: data.cultura,
        data: data.data,
        praga: data.praga,
        nivel_infestacao: data.nivel_infestacao,
        nivel_controle: data.nivel_controle,
        acao_recomendada: data.acao_recomendada,
      });
      setupEditMode('mip-form', '/api/monitoramentos-praga/', id);
      document.getElementById('mip-form').onsubmit = function (e) {
        e.preventDefault();
        return atualizarRegistro(e, '/api/monitoramentos-praga/', 'mip-form', id);
      };
    })
    .catch(function () {
      showToast('Erro ao carregar monitoramento', 'error');
    });
}
function editarRacao(id) {
  fetch('/api/racoes/' + id + '/')
    .then(function (r) {
      return r.json();
    })
    .then(function (data) {
      preencherForm('racao-form', {
        propriedade: data.propriedade,
        nome: data.nome,
        especie_alvo: data.especie_alvo,
        fase: data.fase,
        composicao: data.composicao,
        custo_kg: data.custo_kg,
      });
      setupEditMode('racao-form', '/api/racoes/', id);
      document.getElementById('racao-form').onsubmit = function (e) {
        e.preventDefault();
        return atualizarRegistro(e, '/api/racoes/', 'racao-form', id);
      };
    })
    .catch(function () {
      showToast('Erro ao carregar ração', 'error');
    });
}
function editarFuncionario(id) {
  fetch('/api/funcionarios/' + id + '/')
    .then(function (r) {
      return r.json();
    })
    .then(function (data) {
      preencherForm('func-form', {
        propriedade: data.propriedade,
        nome: data.nome,
        cargo: data.cargo,
        salario: data.salario,
        telefone: data.telefone,
        email: data.email,
        data_admissao: data.data_admissao,
        ativo: data.ativo,
      });
      setupEditMode('func-form', '/api/funcionarios/', id);
      document.getElementById('func-form').onsubmit = function (e) {
        e.preventDefault();
        return atualizarRegistro(e, '/api/funcionarios/', 'func-form', id);
      };
    })
    .catch(function () {
      showToast('Erro ao carregar funcionário', 'error');
    });
}
