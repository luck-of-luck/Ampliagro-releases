/** @type {import('tailwindcss').Config} */
export default {
  // O `content` decide que utilitarios Tailwind sao gerados. Apontar para
  // um glob que nao casa com nenhum ficheiro NAO da erro: o Tailwind gero
  // menos regras e em silencio.
  //
  // MEDIDO 2026-10-03, na remocao do React (V0):
  // `'./src/**/*.{tsx,ts,html}'` apontava para os 46 ficheiros `.tsx`/`.ts`
  // de `src/`. Quando sairam, 97 utilitarios desapareceram do
  // `tailwind-compiled.css` — que e' servido em `base.html:16`. As
  // templates nao usam quase nenhum deles, entao a pagina continuava a
  // parecer igual; mas nao ha teste que apanhe uma regra CSS que deixou de
  // existir.
  //
  // `src/` tem agora so `styles/globals.css` (a entrada do `build:css`), que
  // nao contem classes. O que produz utilitarios sao os templates e o
  // JavaScript que escreve HTML — `app/static/js/cultures-loader.js:457`
  // escreve `top-1.5`, `group-hover/card:`, `bg-white/5`, e o JS nunca foi
  // varrido por este config. Por isso `app/static/js` esta aqui: e' o que
  // realmente escreve HTML.
  content: ['./app/templates/**/*.html', './app/static/js/**/*.js', './src/**/*.html'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        primary: {
          50: '#f0fdfa',
          100: '#ccfbf1',
          200: '#99f6e4',
          300: '#5eead4',
          400: '#2dd4bf',
          500: '#14b8a6',
          600: '#0d9488',
          700: '#0f766e',
          800: '#115e59',
          900: '#134e4a',
          950: '#042f2e',
        },
        ncs: {
          green: '#006B6E',
          'green-light': '#009688',
          'green-dark': '#004D4F',
          cream: '#FDFBF7',
          dark: '#1A1A1A',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      animation: {
        'fade-in': 'fadeIn 0.3s ease-out',
        'slide-up': 'slideUp 0.3s ease-out',
        'slide-down': 'slideDown 0.3s ease-out',
        'pulse-soft': 'pulseSoft 2s infinite',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { transform: 'translateY(10px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
        slideDown: {
          '0%': { transform: 'translateY(-10px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
        pulseSoft: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.7' },
        },
      },
    },
  },
  plugins: [],
};
