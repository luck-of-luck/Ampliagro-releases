"""Testes do guarda de transporte de `config/settings/prod.py`.

MEDIDO 2026-10-05 (agente 3). Nascem de um achado medido, nao de uma
hipotese: `manage.py check --deploy --settings=config.settings.prod` acusou
security.W004/W008/W012/W016, e `prod.py` declarava os quatro como `True`
nas linhas 31-54. Os valores EFECTIVOS eram `False`.

Causa: `base.py:9` faz `load_dotenv(BASE_DIR / ".env")` sem condicao, e o
`.env` de DESENVOLVIMENTO define os cinco como `False`. `prod.py` le-os de
`os.environ`, portanto um default seguro so protege enquanto a variavel nao
existir — e ela existe.

`DEBUG` sobreviveu porque `prod.py:4` o fixa por literal, DEPOIS do
`from .base import *`. Esse e' o detalhe que torna o defeito facil de
perder: ha um sinal de vida (o W018 nao dispara) ao lado de cinco que
morrem calados.

Estes testes existem para fixar as DUAS metades:
  * com env inseguro -> o arranque RECUSA (falha fechada);
  * com env seguro -> o arranca (a guarda nao e' um obstaculo).

Um teste so do primeiro lado passaria mesmo que a guarda fosse
`raise` incondicional. E' o segundo que a impede de ser umPasteur de
parvoices.
"""

import os
import subprocess
import sys
import textwrap
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

# Carrega `prod.py` num subinterpretador, com um ambiente controlado.
# Nao se importa `config.settings.prod` neste processo: `base.py` faz
# `load_dotenv` no import e o singleton de settings ja' esta' montado pela
# suite. Um subinterpretador e' o unico jeito de observar o arranque real.
_CARGA = textwrap.dedent(
    """
    import os, sys
    sys.path.insert(0, {raiz!r})
    os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings.prod"
    import django
    try:
        django.setup()
    except Exception as exc:
        # Imprime a MENSAGEM, nao so o tipo: metade dos testes afirma o que a
        # recusa diz. Um refusal sem caminho nao se corrige, so se aceita —
        # e para verificar isso e' preciso o texto, que o traceback nao traz
        # de forma legivel.
        print("RECUSOU", type(exc).__name__)
        print(str(exc))
        raise SystemExit(3)
    from django.conf import settings
    print("ARRANCOU", settings.SESSION_COOKIE_SECURE,
          settings.CSRF_COOKIE_SECURE, settings.SECURE_SSL_REDIRECT,
          settings.SECURE_HSTS_SECONDS)
    """
)


class GuardaDeTransporteTest(unittest.TestCase):
    """`prod.py` recusa arrancar com transport inseguro."""

    def _arrancar(self, **ambiente):
        env = {
            k: v
            for k, v in os.environ.items()
            if not k.startswith(
                (
                    "DEBUG",
                    "SESSION_COOKIE_SECURE",
                    "CSRF_COOKIE_SECURE",
                    "SECURE_SSL_REDIRECT",
                    "SECURE_HSTS",
                    "AMPLIAGRO_",
                )
            )
        }
        # DEBUG=False e' o que activa a guarda; `SECRET_KEY` tem de existir
        # senao `base.py` levanta antes de chegarmos a ela.
        env.setdefault("SECRET_KEY", "x" * 50)
        env.update(ambiente)
        env = {k: str(v) for k, v in env.items()}
        return subprocess.run(
            [sys.executable, "-c", _CARGA.format(raiz=str(RAIZ))],
            capture_output=True,
            text=True,
            env=env,
            timeout=120,
        )

    # ── a metade que fecha ───────────────────────────────────────────────────
    def test_recusa_quando_o_env_de_desenvolvimento_vaza(self):
        """O caso real: `.env` de dev define os cinco como False."""
        r = self._arrancar(
            DEBUG="False",
            SESSION_COOKIE_SECURE="False",
            CSRF_COOKIE_SECURE="False",
            SECURE_SSL_REDIRECT="False",
            SECURE_HSTS_SECONDS="0",
            SECURE_HSTS_PRELOAD="False",
            SECURE_HSTS_INCLUDE_SUBDOMAINS="False",
        )
        self.assertNotEqual(r.returncode, 0, "arrancou com transport inseguro")
        self.assertIn("RECUSOU", r.stdout + r.stderr)

    def test_a_mensagem_diz_qual_ficheiro_esta_a_envenenar(self):
        """Um refusal sem caminho nao se corrige: so se aceita."""
        r = self._arrancar(
            DEBUG="False", SESSION_COOKIE_SECURE="False", SECURE_SSL_REDIRECT="False"
        )
        saida = r.stdout + r.stderr
        self.assertIn("base.py", saida)
        self.assertIn("SESSION_COOKIE_SECURE", saida)

    def test_cookies_sem_secure_sozinho_basta_para_recusar(self):
        r = self._arrancar(
            DEBUG="False",
            SESSION_COOKIE_SECURE="False",
            CSRF_COOKIE_SECURE="True",
            SECURE_SSL_REDIRECT="True",
            SECURE_HSTS_SECONDS="31536000",
            SECURE_HSTS_PRELOAD="True",
        )
        self.assertNotEqual(r.returncode, 0)

    def test_hsts_a_zero_sozinho_basta_para_recusar(self):
        r = self._arrancar(
            DEBUG="False",
            SESSION_COOKIE_SECURE="True",
            CSRF_COOKIE_SECURE="True",
            SECURE_SSL_REDIRECT="True",
            SECURE_HSTS_SECONDS="0",
            SECURE_HSTS_PRELOAD="True",
        )
        self.assertNotEqual(r.returncode, 0)

    def test_debug_no_ambiente_nao_pode_destravar_a_guarda(self):
        """MEDIDO. `prod.py:4` fixa `DEBUG = False` por LITERAL, depois do
        `from .base import *`. Logo nenhum `.env` transforma prod em dev, e a
        guarda e' INCONDICIONAL neste modulo — por desenho.

        Escrevi este teste a pedir `DEBUG=True` e esperava que a guarda se
        calasse. Ela nao se cala, e tem razao: se um `.env` conseguisse por
        `DEBUG=True` desligar a protecao de transporte, bastava uma linha
        para a reverter. O teste que esperava um arranque era o teste
        ERRADO, nao a guarda. Corrigi a expectativa, nao o codigo.
        """
        r = self._arrancar(
            DEBUG="True",
            SESSION_COOKIE_SECURE="False",
            CSRF_COOKIE_SECURE="False",
            SECURE_SSL_REDIRECT="False",
            SECURE_HSTS_SECONDS="0",
        )
        self.assertNotEqual(
            r.returncode, 0, "DEBUG=True no ambiente desligou a guarda de transporte"
        )

    def test_o_ambiente_de_desenvolvimento_continua_a_arrancar(self):
        """A outra metade disto: nao pode partir quem desenvolve."""
        env = {
            k: v
            for k, v in os.environ.items()
            if not k.startswith(("DEBUG", "AMPLIAGRO_ALLOW_INSECURE_PROD"))
        }
        env.setdefault("SECRET_KEY", "x" * 50)
        env["DJANGO_SETTINGS_MODULE"] = "config.settings.dev"
        env["DEBUG"] = "True"
        script = (
            f"import sys; sys.path.insert(0, {str(RAIZ)!r})\n"
            "import django; django.setup()\n"
            "print('DEV ARRANCOU')"
        )
        r = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            env={k: str(v) for k, v in env.items()},
            timeout=120,
        )
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("DEV ARRANCOU", r.stdout)

    # ── a metade que impede a guarda de ser um obstaculo ─────────────────────
    def test_arranca_com_o_env_de_producao_correcto(self):
        """Sem isto, `raise` incondicional passaria o teste tudo."""
        r = self._arrancar(
            DEBUG="False",
            SESSION_COOKIE_SECURE="True",
            CSRF_COOKIE_SECURE="True",
            SECURE_SSL_REDIRECT="True",
            SECURE_HSTS_SECONDS="31536000",
            SECURE_HSTS_PRELOAD="True",
            SECURE_HSTS_INCLUDE_SUBDOMAINS="True",
        )
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("ARRANCOU True True True", r.stdout)

    def test_a_escotilha_e_explicita_e_nao_e_o_default(self):
        """A escotilha existe, e o default continua a ser recusar."""
        r = self._arrancar(
            DEBUG="False",
            SESSION_COOKIE_SECURE="False",
            CSRF_COOKIE_SECURE="False",
            SECURE_SSL_REDIRECT="False",
            SECURE_HSTS_SECONDS="0",
            SECURE_HSTS_PRELOAD="False",
            AMPLIAGRO_ALLOW_INSECURE_PROD="1",
        )
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        # ...e sem a escotilha, o MESMO ambiente recusa.
        self.assertNotEqual(
            self._arrancar(
                DEBUG="False",
                SESSION_COOKIE_SECURE="False",
                CSRF_COOKIE_SECURE="False",
                SECURE_SSL_REDIRECT="False",
                SECURE_HSTS_SECONDS="0",
                SECURE_HSTS_PRELOAD="False",
            ).returncode,
            0,
        )


class OEnvDeDesenvolvimentoNaoEnvenenaProducaoTest(unittest.TestCase):
    """O `.env` versionado e' de dev: nao pode desligar seguranca sozinho.

    Nao escrevo no `.env` — e' da maquina do utilizador. Leio-o e afirmo o
    que tem de ser verdade, para que quem o copie para producao saiba o
    que esta' a levar.
    """

    def test_o_env_local_declara_transporte_inseguro(self):
        env = RAIZ / ".env"
        if not env.is_file():
            self.skipTest("sem .env nesta maquina")
        texto = env.read_text(encoding="utf-8-sig")
        for chave in (
            "SESSION_COOKIE_SECURE",
            "CSRF_COOKIE_SECURE",
            "SECURE_SSL_REDIRECT",
        ):
            self.assertIn(
                f"{chave}=False",
                texto,
                f"{chave} ja' nao esta' a False no .env — reveja se a guarda "
                f"ainda e' necessaria",
            )

    def test_o_exemplo_de_producao_tem_transporte_seguro(self):
        """O `.env.prod.example` e' o que se copia para producao."""
        exemplo = RAIZ / ".env.prod.example"
        self.assertTrue(exemplo.is_file(), "falta .env.prod.example")
        texto = exemplo.read_text(encoding="utf-8-sig")
        for chave in (
            "SESSION_COOKIE_SECURE",
            "CSRF_COOKIE_SECURE",
            "SECURE_SSL_REDIRECT",
        ):
            self.assertIn(f"{chave}=True", texto)
        self.assertIn("SECURE_HSTS_SECONDS=31536000", texto)
