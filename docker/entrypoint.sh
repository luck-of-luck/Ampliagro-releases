#!/bin/sh
# ============================================================
# Entrypoint do container web (Ampliagro).
#
# migrate e collectstatic ficam AQUI, e nao no build da imagem: os dois
# precisam de SECRET_KEY e de banco de verdade, que so existem em runtime.
# No build, o collectstatic era engolido por `|| true` e a imagem subia sem
# static nenhum (404 em tudo).
#
# So o papel web (gunicorn/daphne) roda migrate/collectstatic. Os servicos
# celery entram direto no comando e nao disputam o schema lock.
# ============================================================
set -e

case "${1:-}" in
    gunicorn | daphne)
        echo "→ migrate"
        python manage.py migrate --noinput
        echo "→ collectstatic"
        # `--ignore '*.map'`: os SOURCE MAPS nao vao para o `STATIC_ROOT`.
        #
        # MEDIDO 2026-10-04 (agente 4). `vite.config.ts` usa
        # `sourcemap: 'hidden'`, que impede o bundle de *apontar* para o `.map`
        # — verificado: o `legacy.*.js` gerado nao tem `sourceMappingURL`.
        #
        # Mas `'hidden'` nao impede o ficheiro de ser SERVIDO. O `.map` continua
        # em `staticfiles/dist/js/` (146 KB medidos) e o WhiteNoise serve
        # `STATIC_ROOT` tal como esta. O URL e' adivinhavel a partir do nome do
        # bundle. E o `.map` contem o FONTE INTEIRO, com nomes de funcoes.
        #
        # Por isso o ficheiro nao entra no `STATIC_ROOT`: e' melhor nao o ter do
        # que confiar em que ninguem adivinha o nome.
        #
        # O PRECO, escrito para quem decidir de volta: sem o `.map` servido, o
        # Sentry recebe stack traces MINIFICADOS (`legacy.D1-d0q-E.js:1:482913`).
        # Para ter os dois, o passo que falta e um `sentry-cli sourcemaps upload`
        # no CI, com `SENTRY_AUTH_TOKEN`. Nao foi feito porque precisa de um
        # segredo que ninguem pediu — e ate la, e' melhor um mapa legivel no
        # painel do que um Mapa completo publicado.
        python manage.py collectstatic --noinput --clear --ignore '*.map'
        ;;
esac

exec "$@"
