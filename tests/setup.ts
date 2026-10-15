import '@testing-library/jest-dom';
import { vi } from 'vitest';

// O `cleanup()` do `@testing-library/react` foi removido na V0 (saida do
// React). Desmontar componentes React nao faz sentido sem React: `afterEach`
// de cleanup existia para o React Testing Library; os testes que ficam sao
// `.js` sobre `window`/`document`, e nao ha component tree para desmontar.
//
// O `matchMedia` e o `ResizeObserver` abaixo NAO sao de React: os testes
// exercitam os widgets vanilla (`widgetbar-windows.cjs` e companhia), que
// usam ambos. Ficam.
Object.defineProperty(window, 'matchMedia', { writable:true, value: vi.fn().mockImplementation(q=>({ matches:false, media:q, onchange:null, addListener:vi.fn(), removeListener:vi.fn(), addEventListener:vi.fn(), removeEventListener:vi.fn(), dispatchEvent:vi.fn() })) });
global.ResizeObserver = vi.fn().mockImplementation(()=>({ observe:vi.fn(), unobserve:vi.fn(), disconnect:vi.fn() }));
