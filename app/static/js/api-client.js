import { getCsrfToken } from './csrf-utils.js';

const BASE_URL = '';

class ApiClient {
  async request(url, options = {}) {
    const config = {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCsrfToken(),
        ...options.headers,
      },
    };

    try {
      const response = await fetch(`${BASE_URL}${url}`, config);

      if (response.status === 401) {
        window.location.href = '/login/';
        return;
      }

      if (response.status === 403) {
        if (window.showErrorToast) {
          window.showErrorToast('Sem permissão para esta ação');
        }
        throw new Error('Forbidden');
      }

      if (response.status === 429) {
        if (window.showErrorToast) {
          window.showErrorToast('Muitas requisições. Aguarde um momento.');
        }
        throw new Error('Rate limited');
      }

      if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Erro desconhecido' }));
        throw new Error(error.detail || `HTTP ${response.status}`);
      }

      return response.json();
    } catch (error) {
      if (error.name === 'TypeError' && error.message === 'Failed to fetch') {
        if (window.showErrorToast) {
          window.showErrorToast('Sem conexão com o servidor');
        }
      }
      throw error;
    }
  }

  get(url) { return this.request(url); }
  post(url, data) { return this.request(url, { method: 'POST', body: JSON.stringify(data) }); }
  put(url, data) { return this.request(url, { method: 'PUT', body: JSON.stringify(data) }); }
  patch(url, data) { return this.request(url, { method: 'PATCH', body: JSON.stringify(data) }); }
  delete(url) { return this.request(url, { method: 'DELETE' }); }
}

export const api = new ApiClient();
