"""Criptografia de dados sensíveis em repouso (Fase 1 da ponta a ponta).

- Chave Fernet em `AMPLIAGRO_DATA_KEY` (gerar com `Fernet.generate_key()`).
- Sem env + DEBUG: chave fixa de DEV (nunca produção). Sem env + prod: explode.
- `EncryptedCharField`: grava `enc1:<token>`, lê descriptografando; texto
  legado sem prefixo passa direto (migração sem backfill de leitura).
- Índice cego: para campos buscados por igualdade (ex: api_key), guarde
  `sha256(plaintext)` num campo separado e busque por ele — Fernet é
  randomizado e nunca casa em `filter(campo=valor)`.
"""

import hashlib

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import models

PREFIXO = "enc1:"
_DEV_KEY = b"P9BO46kX9OJ46V3LRADIHqiGN_lP_ElHOT9u9nZdWdM="

_fernet = None


def get_fernet():
    global _fernet
    if _fernet is not None:
        return _fernet
    chave = getattr(settings, "AMPLIAGRO_DATA_KEY", "") or ""
    if not chave:
        import os
        import sys

        chave = os.environ.get("AMPLIAGRO_DATA_KEY", "")
        # `manage.py test` passa "test" em argv, mas pytest nao. E o proprio
        # pytest-django chama django.test.utils.setup_test_environment(), que
        # poe settings.DEBUG = False — logo o "DEBUG" abaixo nunca era
        # verdadeiro durante a suite, e qualquer teste que gravasse um
        # EncryptedField estourava ImproperlyConfigured. Sem chave em teste,
        # seguimos com a chave de DEV; fora de teste, continua explodindo.
        testando = (
            any(a == "test" or a.endswith("/test") for a in sys.argv)
            or "pytest" in sys.modules
            or bool(os.environ.get("PYTEST_CURRENT_TEST"))
        )
        if not chave and (getattr(settings, "DEBUG", False) or testando):
            chave = _DEV_KEY.decode()
        if not chave:
            raise ImproperlyConfigured(
                "AMPLIAGRO_DATA_KEY não configurada (produção exige chave Fernet)"
            )
    _fernet = Fernet(chave.encode() if isinstance(chave, str) else chave)
    return _fernet


def criptografar(texto):
    if texto is None or texto == "":
        return texto
    s = str(texto)
    if s.startswith(PREFIXO):
        return s
    return PREFIXO + get_fernet().encrypt(s.encode()).decode()


def descriptografar(valor):
    if not valor or not str(valor).startswith(PREFIXO):
        return valor  # legado em claro
    try:
        return get_fernet().decrypt(str(valor)[len(PREFIXO) :].encode()).decode()
    except (InvalidToken, ValueError):
        return valor  # chave trocada: não quebra leitura


def hash_cego(texto):
    """SHA-256 p/ busca por igualdade sem expor o valor (índice cego)."""
    return hashlib.sha256(str(texto or "").encode()).hexdigest()


class EncryptedCharField(models.CharField):
    """CharField com Fernet transparente. Aumente max_length: token ocupa ~120+ chars."""

    def get_prep_value(self, value):
        value = super().get_prep_value(value)
        if value is None:
            return value
        return criptografar(value)

    def from_db_value(self, value, expression, connection):
        return descriptografar(value)

    def to_python(self, value):
        value = super().to_python(value)
        return descriptografar(value)
