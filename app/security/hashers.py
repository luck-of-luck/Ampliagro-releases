"""
SHA-512 based password hashers for Django.
Provides PBKDF2 with SHA-512 (600,000 iterations) and direct SHA-512 with salt.
"""

import hashlib
import secrets
import binascii
from django.contrib.auth.hashers import PBKDF2PasswordHasher
from django.utils.crypto import constant_time_compare


class SHA512PasswordHasher:
    """
    Direct SHA-512 password hasher with salt.

    Format: sha512$salt$hash

    NOTE: This is faster than PBKDF2 but less resistant to GPU attacks.
    Use PBKDF2SHA512PasswordHasher for production.
    """

    algorithm = "sha512"
    salt_length = 32
    iterations = 1

    def salt(self):
        return secrets.token_bytes(self.salt_length)

    def encode(self, password, salt, iterations=None):
        if isinstance(password, str):
            password = password.encode("utf-8")
        if isinstance(salt, str):
            salt = salt.encode("utf-8")

        hash_obj = hashlib.sha512()
        hash_obj.update(salt)
        hash_obj.update(password)
        return hash_obj.hexdigest()

    def verify(self, password, encoded):
        algorithm, salt, hash_value = encoded.split("$", 2)
        if algorithm != self.algorithm:
            return False
        return constant_time_compare(self.encode(password, salt), hash_value)

    def safe_summary(self, encoded):
        algorithm, salt, hash_value = encoded.split("$", 2)
        return {
            "algorithm": algorithm,
            "salt": salt[:8] + "...",
            "hash": hash_value[:8] + "...",
        }

    def must_update(self, encoded):
        return False


class PBKDF2SHA512PasswordHasher(PBKDF2PasswordHasher):
    """
    PBKDF2 with SHA-512 - Production grade password hashing.

    Uses 600,000 iterations (OWASP 2024 recommendation for PBKDF2-SHA512).
    More resistant to GPU/ASIC attacks than SHA-512 alone.

    Format: pbkdf2_sha512$iterations$salt$hash
    """

    algorithm = "pbkdf2_sha512"
    iterations = 600000  # OWASP 2024 recommendation
    digest = hashlib.sha512

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Ensure we use SHA-512
        self.digest = hashlib.sha512

    def encode(self, password, salt, iterations=None):
        if iterations is None:
            iterations = self.iterations

        hash_value = self._pbkdf2(password, salt, iterations)
        return f"{self.algorithm}${iterations}${salt}${hash_value}"

    def verify(self, password, encoded):
        try:
            algorithm, iterations, salt, hash_value = encoded.split("$", 3)
        except ValueError:
            return False

        if algorithm != self.algorithm:
            return False

        try:
            iterations = int(iterations)
        except ValueError:
            return False

        return constant_time_compare(
            self._pbkdf2(password, salt, iterations), hash_value
        )

    def _pbkdf2(self, password, salt, iterations):
        if isinstance(password, str):
            password = password.encode("utf-8")
        if isinstance(salt, str):
            salt = salt.encode("utf-8")

        dk = hashlib.pbkdf2_hmac(
            "sha512",
            password,
            salt,
            iterations,
            dklen=64,  # 512 bits = 64 bytes
        )
        return binascii.hexlify(dk).decode("ascii")

    def safe_summary(self, encoded):
        try:
            algorithm, iterations, salt, hash_value = encoded.split("$", 3)
            return {
                "algorithm": algorithm,
                "iterations": iterations,
                "salt": salt[:8] + "...",
                "hash": hash_value[:8] + "...",
            }
        except ValueError:
            return {"algorithm": "invalid", "iterations": "0", "salt": "", "hash": ""}

    def must_update(self, encoded):
        """Check if hash needs updating (iterations too low)."""
        try:
            _, iterations, _, _ = encoded.split("$", 3)
            return int(iterations) < self.iterations
        except (ValueError, IndexError):
            return True


class Argon2idPasswordHasher:
    """
    Argon2id hasher - Most secure option (memory-hard).

    Requires: pip install argon2-cffi
    """

    algorithm = "argon2id"

    def __init__(self):
        try:
            import argon2

            self._hasher = argon2.PasswordHasher(
                time_cost=3,
                memory_cost=65536,  # 64 MB
                parallelism=4,
                hash_len=32,
                salt_len=16,
            )
            self._available = True
        except ImportError:
            self._available = False

    def encode(self, password, salt=None):
        if not self._available:
            raise RuntimeError("argon2-cffi not installed")
        return self._hasher.hash(password)

    def verify(self, password, encoded):
        if not self._available:
            return False
        try:
            return self._hasher.verify(encoded, password)
        except Exception:
            return False

    def safe_summary(self, encoded):
        return {"algorithm": self.algorithm, "hash": encoded[:16] + "..."}

    def must_update(self, encoded):
        return False


# Export all hashers
__all__ = [
    "SHA512PasswordHasher",
    "PBKDF2SHA512PasswordHasher",
    "Argon2idPasswordHasher",
]
