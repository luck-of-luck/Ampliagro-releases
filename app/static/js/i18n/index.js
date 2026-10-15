let currentLocale = 'pt-BR';
let translations = {};

export async function initI18n(locale = 'pt-BR') {
  currentLocale = locale;
  try {
    const module = await import(`./${locale}.json`);
    translations = module.default;
  } catch (err) {
    console.error(`Falha ao carregar traduções para ${locale}`, err);
    translations = {};
  }
}

export function t(key, params = {}) {
  let text = translations[key] || key;
  for (const [k, v] of Object.entries(params)) {
    text = text.replace(`{${k}}`, v);
  }
  return text;
}
