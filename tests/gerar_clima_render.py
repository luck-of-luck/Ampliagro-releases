"""Deixa a página de clima e a sua resposta em ficheiros, para o teste de
render as ler.

O teste de render (`tests/unit/clima_render.test.js`) precisa de duas
coisas que o browser lhe daria: o HTML da página tal como o Django a
renderiza, e o JSON do endpoint tal como a view o devolve.

Porquê um dump em vez de o teste pedir ao Django
================================================

O dump é o que MANTÉM o teste honesto. Um teste que monte o payload à
mão passa a descrever um dia que não é o dia que o utilizador vai ver,
e continua verde na mesma. O dump é do sistema a correr.

A CONTA
-------

A conta é a de demonstração, e a palavra-passe vem do ambiente:

    python manage.py criar_conta_demo
    AMPLIAGRO_DEMO_SENHA=<a senha que ele imprimiu> python tests/gerar_clima_render.py

Não há palavra-passe neste ficheiro, e houve — em texto claro, numa linha
`c.login(...)`. Uma senha no repositório deixa de ser uma senha no momento
em que o primeiro clone acontece — e não há forma de a trocar a posteriori
para quem já a leu.

Este texto não volta a citá-la, e é essa a razão de a nota existir:
reproduzir a senha dentro da explicação de que a senha foi removida
voltaria a metê-la no repositório, agora em prosa, onde um `grep` a encontra
com ainda menos esforço. O mesmo vale para qualquer relatório que tenha
citado a linha — citar o achado é correcto; citar o segredo, não.

`criar_conta_demo` GERA uma senha aleatória e mostra-a uma vez
(`:52 senha_forte`), o que significa que este ficheiro nunca pode ter a
senha: ela não é derivável de lado nenhum.

ONDE VAI O DUMP
---------------

`CLIMA_RENDER_FIXTURE_DIR`, ou a pasta temporária do sistema. O caminho
estava fixo para `C:/Users/lucas/...`, que não existe em `ubuntu-latest` —
e o teste que o consome fazia `throw` em vez de saltar, para não passar em
branco. O resultado era um job vermelho em que o `&&` impedia o
`npm run test:cjs` de correr: ~380 checks mortos sem ninguém saber.

O teste e este script leem a MESMA variável. Uma fonte de verdade, dois
lados — que é o que o teste já dizia e o script não cumpria.

Uso:  AMPLIAGRO_DEMO_SENHA=... python tests/gerar_clima_render.py
"""

import json
import os
import pathlib
import sys
import tempfile

RAIZ = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

import django  # noqa: E402

django.setup()

from django.contrib.auth.models import User  # noqa: E402
from django.test import Client  # noqa: E402

#: Mesma variável que `tests/unit/clima_render.test.js` lê. Se uma mudar,
#: o teste falha ALTO (de propósito) e o culpado está no nome do erro.
SAIDA = pathlib.Path(
    os.environ.get("CLIMA_RENDER_FIXTURE_DIR")
    or pathlib.Path(tempfile.gettempdir()) / "ampliagro"
)
SAIDA.mkdir(parents=True, exist_ok=True)

USUARIO = "demo.muzambinho"
SENHA = os.environ.get("AMPLIAGRO_DEMO_SENHA")
if not SENHA:
    print("  [ERRO] falta AMPLIAGRO_DEMO_SENHA.")
    print("")
    print("  A conta de demonstração tem a senha gerada, não uma senha escrita")
    print("  no repositório. Para recriar a conta e gerar o dump:")
    print("")
    print("    python manage.py criar_conta_demo")
    print("    AMPLIAGRO_DEMO_SENHA=<a senha que ele imprimiu> \\")
    print("        python tests/gerar_clima_render.py")
    raise SystemExit(2)

c = Client()

# MEDIDO 2026-10-06: isto era `ok = c.login(username=USUARIO, password=SENHA)`, e
# `Client.login()` chama `authenticate()` SEM um `request`. O `django-axes`
# 6.0.5 — a versao que `requirements.txt` fixa — levanta:
#
#   axes.exceptions.AxesBackendRequestParameterRequired:
#   AxesBackend requires a request as an argument to authenticate
#
# O `Client.login()` e' um atalho de teste que salta o pedido HTTP, e o axes
# recusa precisamente isso: um login sem request nao tem IP, e o IP e' metade
# do que o axes mede. O login REAL, por formulario, leva o request e funciona.
#
# Por isso a sessao e' forcada com `force_login` (o mesmo que 125 usos no
# repositorio), e a SENHA e' verificada a parte com `check_password()`. Sao
# duas perguntas distintas e as duas continuam a ser feitas:
#
#   1. a senha que o `criar_conta_demo` imprimiu e' a senha desta conta?
#   2. ha sessao para o dump? -> `force_login`
#
# Juntas, e' o mesmo contrato de antes. So muda o mecanismo, porque o mecanismo
# antigo deixou de funcionar com o backend de autenticacao que o manifesto
# instala.
u = User.objects.filter(username=USUARIO).first()
if u is None:
    print(f"  [ERRO] o utilizador {USUARIO} nao existe. Corre primeiro:")
    print("    python manage.py criar_conta_demo --settings=config.settings.ci")
    raise SystemExit(2)

if not u.check_password(SENHA):
    print(
        f"  [ERRO] a senha de {USUARIO} nao e' a que o criar_conta_demo "
        f"imprimiu. Volta a correr o comando e usa a senha nova."
    )
    raise SystemExit(2)

c.force_login(u)
ok = True
if not ok:
    print(f"  [ERRO] login falhou para {USUARIO}")
    raise SystemExit(1)

html = c.get("/previsao/clima/")
resposta = c.get("/api/agronomia/clima/previsao/")

if html.status_code != 200:
    print(f"  [ERRO] /previsao/clima/ -> HTTP {html.status_code}")
    raise SystemExit(1)
if resposta.status_code != 200:
    print(f"  [ERRO] endpoint -> HTTP {resposta.status_code}: {resposta.content[:160]}")
    raise SystemExit(1)

payload = resposta.json()

(SAIDA / "clima.html").write_text(
    html.content.decode("utf-8", "replace"), encoding="utf-8"
)
(SAIDA / "clima.json").write_text(
    json.dumps(payload, ensure_ascii=False), encoding="utf-8"
)

print(f"  html: {len(html.content)} bytes -> {SAIDA / 'clima.html'}")
print(
    f"  json: {len(payload.get('daily', {}).get('time', []))} dias -> {SAIDA / 'clima.json'}"
)
print(f"  fonte: {payload.get('fonte_coordenadas')}")
print(f"  aviso: {payload.get('aviso_coordenadas') or '(nenhum)'}")
print("")
print(
    f"  Para o teste:  CLIMA_RENDER_FIXTURE_DIR={SAIDA} npx vitest run tests/unit/clima_render.test.js"
)
