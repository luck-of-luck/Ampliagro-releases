import './error-boundary.js';
import { api } from './api-client.js';
import { initI18n, t } from './i18n/index.js';
import * as formatters from './formatters.js';
import * as utils from './utils.js';

import './csrf-utils.js';
import './theme-system.js';
import './data-store.js';
import './data-provider.js';
import './spa.js';

// Expose globals for backward compatibility during migration
window.api = api;
window.initI18n = initI18n;
window.t = t;
window.formatters = formatters;
window.utils = utils;

console.log('[Ampliagro] Main bundle loaded via Vite');
