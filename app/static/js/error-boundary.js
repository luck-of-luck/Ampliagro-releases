import { getCsrfToken } from './csrf-utils.js';

window.addEventListener('error', (event) => {
  console.error('[Ampliagro Error]', event.error);
  if (window.showErrorToast) {
    window.showErrorToast('Ocorreu um erro inesperado. Tente recarregar a página.');
  }

  // Enviar para backend (se houver endpoint configurado /api/erro-js/)
  fetch('/api/erro-js/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
    body: JSON.stringify({
      message: event.error?.message || event.message,
      stack: event.error?.stack || '',
      url: window.location.href,
      timestamp: new Date().toISOString(),
    }),
  }).catch(() => {}); // silencioso
});

window.addEventListener('unhandledrejection', (event) => {
  console.error('[Ampliagro Promise Error]', event.reason);
});
