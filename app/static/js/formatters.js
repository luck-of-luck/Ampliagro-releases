const locale = navigator.language || 'pt-BR';

const _nf = new Map();
const _numFmt = (options) => {
  const key = JSON.stringify(options);
  let f = _nf.get(key);
  if (!f) {
    f = new Intl.NumberFormat(locale, options);
    _nf.set(key, f);
  }
  return f;
};

const _dt = new Map();
const _dateFmt = (options) => {
  const key = JSON.stringify(options);
  let f = _dt.get(key);
  if (!f) {
    f = new Intl.DateTimeFormat(locale, options);
    _dt.set(key, f);
  }
  return f;
};

export const formatCurrency = (value, currency = 'BRL') =>
  _numFmt({ style: 'currency', currency }).format(value);

export const formatNumber = (value, decimals = 2) =>
  _numFmt({ minimumFractionDigits: decimals, maximumFractionDigits: decimals }).format(value);

export const formatDate = (date, style = 'medium') =>
  _dateFmt({ dateStyle: style }).format(new Date(date));

export const formatDateTime = (date) =>
  _dateFmt({ dateStyle: 'short', timeStyle: 'short' }).format(new Date(date));

const _rtf = new Intl.RelativeTimeFormat(locale, { numeric: 'auto' });
export const formatRelativeTime = (date) => {
  const diff = (new Date(date) - new Date()) / 1000;
  if (Math.abs(diff) < 60) return _rtf.format(Math.round(diff), 'second');
  if (Math.abs(diff) < 3600) return _rtf.format(Math.round(diff / 60), 'minute');
  if (Math.abs(diff) < 86400) return _rtf.format(Math.round(diff / 3600), 'hour');
  return _rtf.format(Math.round(diff / 86400), 'day');
};

export const formatArea = (ha) => `${formatNumber(ha)} ha`;
export const formatWeight = (kg) =>
  kg >= 1000 ? `${formatNumber(kg / 1000)} t` : `${formatNumber(kg)} kg`;
