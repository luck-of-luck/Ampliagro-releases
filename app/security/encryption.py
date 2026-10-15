"""
Field-level encryption using AES-256-GCM (authenticated encryption).
Protects sensitive data at rest in the database.
"""

import os
import base64
import secrets
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


class FieldEncryption:
    """
    AES-256-GCM field encryption for sensitive database fields.

    Usage:
        encryption = FieldEncryption()
        encrypted = encryption.encrypt("sensitive data")
        decrypted = encryption.decrypt(encrypted)

    The encrypted format includes: version|nonce|ciphertext
    All components are base64 encoded and joined with '|'.
    """

    VERSION = 1
    KEY_LENGTH = 32  # 256 bits
    NONCE_LENGTH = 12  # 96 bits for GCM
    SALT_LENGTH = 16
    TAG_LENGTH = 16

    def __init__(self, key=None):
        if key is None:
            key = getattr(settings, "FIELD_ENCRYPTION_KEY", "")

        if not key:
            if settings.DEBUG:
                # Generate a deterministic key for development
                key = self._derive_key("ampliagro2-dev-key", b"dev-salt-16-bytes")
            else:
                raise ImproperlyConfigured(
                    "FIELD_ENCRYPTION_KEY must be set in production. "
                    'Generate with: python -c "import secrets; print(secrets.token_hex(32))"'
                )

        if isinstance(key, str):
            # If hex encoded
            try:
                key = bytes.fromhex(key)
            except ValueError:
                # If raw string, derive key
                key = self._derive_key(key, b"ampliagro2-salt-16")

        if len(key) != self.KEY_LENGTH:
            raise ValueError(
                f"Encryption key must be {self.KEY_LENGTH} bytes (256 bits)"
            )

        self._key = key
        self._cipher = AESGCM(key)

    @staticmethod
    def _derive_key(password: str, salt: bytes) -> bytes:
        """Derive a 256-bit key from password using PBKDF2."""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        return kdf.derive(password.encode("utf-8"))

    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt a string and return base64 encoded ciphertext.

        Format: v1|nonce|ciphertext
        All parts base64 encoded.
        """
        if not isinstance(plaintext, str):
            plaintext = str(plaintext)

        # Generate random nonce for each encryption
        nonce = secrets.token_bytes(self.NONCE_LENGTH)

        # Encrypt
        plaintext_bytes = plaintext.encode("utf-8")
        ciphertext = self._cipher.encrypt(nonce, plaintext_bytes, None)

        # Format: version|nonce|ciphertext (all base64)
        parts = [
            str(self.VERSION),
            base64.b64encode(nonce).decode("ascii"),
            base64.b64encode(ciphertext).decode("ascii"),
        ]
        return "|".join(parts)

    def decrypt(self, encrypted: str) -> str:
        """
        Decrypt a string encrypted with encrypt().
        """
        if not isinstance(encrypted, str):
            raise ValueError("Encrypted data must be a string")

        parts = encrypted.split("|")
        if len(parts) != 3:
            raise ValueError("Invalid encrypted format")

        version = int(parts[0])
        if version != self.VERSION:
            raise ValueError(f"Unsupported encryption version: {version}")

        try:
            nonce = base64.b64decode(parts[1])
            ciphertext = base64.b64decode(parts[2])
        except Exception as e:
            raise ValueError(f"Invalid base64 encoding: {e}")

        if len(nonce) != self.NONCE_LENGTH:
            raise ValueError(f"Invalid nonce length: {len(nonce)}")

        try:
            plaintext_bytes = self._cipher.decrypt(nonce, ciphertext, None)
            return plaintext_bytes.decode("utf-8")
        except Exception as e:
            raise ValueError(f"Decryption failed: {e}")

    def encrypt_bytes(self, data: bytes) -> bytes:
        """Encrypt raw bytes."""
        nonce = secrets.token_bytes(self.NONCE_LENGTH)
        ciphertext = self._cipher.encrypt(nonce, data, None)
        return nonce + ciphertext

    def decrypt_bytes(self, encrypted: bytes) -> bytes:
        """Decrypt raw bytes."""
        if len(encrypted) < self.NONCE_LENGTH + self.TAG_LENGTH:
            raise ValueError("Encrypted data too short")

        nonce = encrypted[: self.NONCE_LENGTH]
        ciphertext = encrypted[self.NONCE_LENGTH :]
        return self._cipher.decrypt(nonce, ciphertext, None)

    @classmethod
    def generate_key(cls) -> str:
        """Generate a new random encryption key (hex encoded)."""
        return secrets.token_hex(cls.KEY_LENGTH)

    @classmethod
    def rotate_key(cls, old_encrypted: str, old_key: str, new_key: str) -> str:
        """Re-encrypt data with a new key."""
        old_cipher = FieldEncryption(old_key)
        new_cipher = FieldEncryption(new_key)

        plaintext = old_cipher.decrypt(old_encrypted)
        return new_cipher.encrypt(plaintext)


# Convenience functions for simple use cases
_default_encryption = None


def _get_default_encryption():
    global _default_encryption
    if _default_encryption is None:
        _default_encryption = FieldEncryption()
    return _default_encryption


def encrypt_field(value: str) -> str:
    """Encrypt a field value using the default encryption."""
    return _get_default_encryption().encrypt(value)


def decrypt_field(value: str) -> str:
    """Decrypt a field value using the default encryption."""
    return _get_default_encryption().decrypt(value)


class EncryptedFieldMixin:
    """
    Mixin for Django model fields that automatically encrypt/decrypt.

    Usage:
        class MyModel(models.Model):
            ssn = EncryptedCharField(max_length=11)

            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self._encryption = FieldEncryption()
    """

    def __init__(self, *args, encryption=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._encryption = encryption or _get_default_encryption()

    def get_prep_value(self, value):
        if value is None or value == "":
            return value
        return self._encryption.encrypt(value)

    def from_db_value(self, value, expression, connection):
        if value is None or value == "":
            return value
        try:
            return self._encryption.decrypt(value)
        except Exception:
            # Return encrypted value if decryption fails (data corruption)
            return value

    def to_python(self, value):
        if value is None or value == "":
            return value
        if isinstance(value, str) and "|" in value:
            try:
                return self._encryption.decrypt(value)
            except Exception:
                return value
        return value


# Django model field classes (require django.db.models)
try:
    from django.db import models

    class EncryptedCharField(EncryptedFieldMixin, models.CharField):
        """Encrypted CharField."""

        pass

    class EncryptedTextField(EncryptedFieldMixin, models.TextField):
        """Encrypted TextField."""

        pass

    class EncryptedEmailField(EncryptedFieldMixin, models.EmailField):
        """Encrypted EmailField."""

        pass

    __all__ = [
        "FieldEncryption",
        "encrypt_field",
        "decrypt_field",
        "EncryptedFieldMixin",
        "EncryptedCharField",
        "EncryptedTextField",
        "EncryptedEmailField",
    ]

except ImportError:
    __all__ = [
        "FieldEncryption",
        "encrypt_field",
        "decrypt_field",
        "EncryptedFieldMixin",
    ]
