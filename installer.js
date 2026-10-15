'use strict';

const api = window.ampliagroSetup;
const byId = (id) => document.getElementById(id);
let step = 0;
let data;
let busy = false;
const selected = new Set();
const normalize = (text) =>
  text
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase();
const error = (message) => {
  byId('error').textContent = message;
  byId('error').hidden = !message;
};

function refresh() {
  document.querySelectorAll('section').forEach((el, i) => {
    el.hidden = i !== step;
  });
  document.querySelectorAll('.steps li').forEach((el, i) => {
    if (i === step) el.setAttribute('aria-current', 'step');
    else el.removeAttribute('aria-current');
  });
  byId('back').hidden = step === 0 || step === 3;
  byId('back').disabled = busy;
  byId('next').disabled =
    busy || (step === 0 && !byId('accepted').checked) || (step === 2 && !selected.size);
  byId('next').textContent = busy
    ? 'Preparando…'
    : step === 3
      ? 'Abrir Ampliagro →'
      : step === 2
        ? 'Preparar minhas culturas →'
        : 'Continuar →';
  byId('count').textContent =
    `${selected.size} cultura${selected.size === 1 ? '' : 's'} selecionada${selected.size === 1 ? '' : 's'}`;
}

function renderCultures() {
  const query = normalize(byId('search').value);
  const container = byId('cultures');
  container.replaceChildren();
  let count = 0;
  data.grupos.forEach((group) => {
    const entries = group.culturas.filter((c) =>
      normalize(`${c.nome} ${group.rotulo}`).includes(query)
    );
    if (!entries.length) return;
    count += entries.length;
    const details = document.createElement('details');
    details.open = Boolean(query);
    const summary = document.createElement('summary');
    summary.textContent = `${group.rotulo} · ${entries.length}`;
    const grid = document.createElement('div');
    grid.className = 'culture-grid';
    entries.forEach((culture) => {
      const label = document.createElement('label');
      const input = document.createElement('input');
      input.type = 'checkbox';
      input.checked = selected.has(culture.id);
      input.addEventListener('change', () => {
        if (input.checked && selected.size >= 200) {
          input.checked = false;
          error('Selecione até 200 culturas.');
          return;
        }
        if (input.checked) selected.add(culture.id);
        else selected.delete(culture.id);
        error('');
        refresh();
      });
      label.append(input, document.createTextNode(culture.nome));
      grid.append(label);
    });
    details.append(summary, grid);
    container.append(details);
  });
  byId('empty').hidden = count > 0;
}

byId('theme').addEventListener('click', () => {
  const light = document.documentElement.dataset.theme !== 'light';
  document.documentElement.dataset.theme = light ? 'light' : 'dark';
  byId('theme').textContent = light ? 'Modo escuro' : 'Modo claro';
  localStorage.setItem('ampliagro-landing-theme', light ? 'light' : 'dark');
});
if (localStorage.getItem('ampliagro-landing-theme') === 'light') byId('theme').click();
byId('accepted').addEventListener('change', refresh);
byId('search').addEventListener('input', renderCultures);
byId('clear').addEventListener('click', () => {
  selected.clear();
  renderCultures();
  refresh();
});
byId('back').addEventListener('click', () => {
  step--;
  error('');
  refresh();
});
byId('next').addEventListener('click', async () => {
  if (busy || byId('next').disabled) return;
  error('');
  if (step < 2) {
    step++;
    refresh();
    return;
  }
  busy = true;
  refresh();
  try {
    if (step === 3) {
      await api.open();
      return;
    }
    const mode = document.querySelector('input[name=mode]:checked').value;
    await api.save({
      mode,
      culturas: [...selected],
      accepted: byId('accepted').checked,
      termsHash: data.termsHash,
    });
    byId('summary').textContent =
      `${selected.size} perfil(is) de cultura preparado(s). ${mode === 'local' ? 'Seus dados ficam neste computador.' : 'Você acessará o servidor web configurado.'}`;
    const chips = byId('selected-summary');
    chips.replaceChildren();
    data.grupos
      .flatMap((g) => g.culturas)
      .filter((c) => selected.has(c.id))
      .forEach((c) => {
        const chip = document.createElement('span');
        chip.textContent = c.nome;
        chips.append(chip);
      });
    step = 3;
  } catch (err) {
    error(err.message);
  } finally {
    busy = false;
    refresh();
  }
});

async function initialize() {
  if (!api) {
    byId('status').textContent =
      'Abra o aplicativo Ampliagro Desktop para configurar sua instalação. Este assistente precisa do servidor local do aplicativo.';
    return;
  }
  try {
    data = await api.read();
    if (
      !data.forceSetup &&
      data.installation?.termsHash === data.termsHash &&
      data.installation?.acceptedAt
    ) {
      await api.open();
      return;
    }
    byId('terms').textContent = data.terms;
    if (Array.isArray(data.installation?.culturas)) {
      data.installation.culturas.forEach((id) => selected.add(id));
    }
    if (data.officialURL) {
      document.querySelector('input[value=cloud]').disabled = false;
      byId('cloud-status').textContent = new URL(data.officialURL).host;
    }
    renderCultures();
    byId('status').hidden = true;
    refresh();
  } catch (err) {
    byId('status').textContent =
      'Não foi possível preparar a configuração. Feche e abra o aplicativo para tentar novamente.';
    error(err.message);
  }
}
initialize();
