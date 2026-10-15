export function getCsrfToken() {
  return (
    document.querySelector('[name=csrfmiddlewaretoken]')?.value ||
    document.cookie
      .split(';')
      .find((c) => c.trim().startsWith('csrftoken='))
      ?.split('=')[1] ||
    ''
  );
}
export function fetchWithCsrf(url, options = {}) {
  const headers = options.headers || {};
  headers['X-CSRFToken'] = getCsrfToken();
  return fetch(url, { ...options, headers });
}
