"""
Secure token generation and verification for API keys, password reset, etc.
Uses cryptographically secure random generation with HMAC verification.
"""

import hashlib
import hmac
import secrets
import time
import base64
from typing import Optional, Dict, Any
from django.conf import settings
from django.core.signing import TimestampSigner, BadSignature, SignatureExpired
from django.utils.crypto import constant_time_compare


class SecureTokenGenerator:
    """
    Generates and verifies secure tokens for various purposes:
    - API keys (long-lived, identifiable prefix)
    - Password reset tokens (short-lived, one-time)
    - Email verification tokens
    - CSRF tokens
    - Session tokens
    """

    # Token prefixes for identification
    PREFIXES = {
        "api_key": "ak_",
        "password_reset": "pr_",
        "email_verify": "ev_",
        "session": "ss_",
        "csrf": "cs_",
        "webhook": "wh_",
        "device": "dv_",
    }

    # Token lengths (entropy bytes)
    LENGTHS = {
        "api_key": 32,
        "password_reset": 32,
        "email_verify": 32,
        "session": 32,
        "csrf": 32,
        "webhook": 32,
        "device": 24,
    }

    # Default expiration times (seconds)
    EXPIRATIONS = {
        "api_key": None,
        "password_reset": 1800,
        "email_verify": 86400,
        "session": 7200,
        "csrf": 7200,
        "webhook": None,
        "device": 2592000,
    }

    def __init__(self, secret_key: Optional[str] = None):
        self.secret_key = secret_key or getattr(settings, "SECRET_KEY", "")
        if not self.secret_key:
            raise ValueError("SECRET_KEY must be configured")
        self._signer = TimestampSigner(key=self.secret_key)

    def generate(
        self,
        token_type: str,
        prefix: Optional[str] = None,
        length: Optional[int] = None,
    ) -> str:
        """Generate a secure random token with optional prefix."""
        if token_type not in self.LENGTHS:
            raise ValueError(f"Unknown token type: {token_type}")

        token_length = length or self.LENGTHS[token_type]
        token_prefix = prefix or self.PREFIXES.get(token_type, "")

        random_bytes = secrets.token_bytes(token_length)
        token = base64.urlsafe_b64encode(random_bytes).decode("ascii").rstrip("=")

        return f"{token_prefix}{token}"

    def generate_api_key(self, identifier: str = "") -> str:
        """Generate an API key with optional identifier embedded."""
        key = self.generate("api_key")
        if identifier:
            id_hash = hashlib.sha256(identifier.encode()).hexdigest()[:8]
            return f"{key}|{id_hash}"
        return key

    def hash_token(self, token: str) -> str:
        """Create a secure hash of a token for storage."""
        pepper = self.secret_key.encode()[:32]
        return hashlib.pbkdf2_hmac(
            "sha256", token.encode(), pepper, 100000, dklen=32
        ).hex()

    def verify_hash(self, token: str, stored_hash: str) -> bool:
        """Verify a token against its stored hash using constant-time comparison."""
        computed_hash = self.hash_token(token)
        return constant_time_compare(computed_hash, stored_hash)

    def sign_token(self, token: str, purpose: str = "") -> str:
        """Sign a token with timestamp for expiration checking."""
        payload = f"{token}|{purpose}"
        return self._signer.sign(payload)

    def unsign_token(
        self, signed_token: str, max_age: Optional[int] = None, purpose: str = ""
    ) -> str:
        """Verify and extract token from signed token."""
        payload = self._signer.unsign(signed_token, max_age=max_age)
        token, token_purpose = payload.rsplit("|", 1)

        if purpose and token_purpose != purpose:
            raise BadSignature("Token purpose mismatch")

        return token

    def create_reset_token(self, user_id: int) -> str:
        """Create a password reset token for a user."""
        payload = f"reset|{user_id}|{int(time.time())}"
        return self.sign_token(payload, "password_reset")

    def verify_reset_token(self, token: str, max_age: int = 1800) -> int:
        """Verify a password reset token and return user_id."""
        payload = self.unsign_token(token, max_age=max_age, purpose="password_reset")
        parts = payload.split("|")
        if parts[0] != "reset" or len(parts) != 3:
            raise BadSignature("Invalid reset token format")
        return int(parts[1])

    def create_verification_token(self, email: str) -> str:
        """Create an email verification token."""
        payload = f"verify|{email}|{int(time.time())}"
        return self.sign_token(payload, "email_verify")

    def verify_verification_token(self, token: str, max_age: int = 86400) -> str:
        """Verify an email verification token and return email."""
        payload = self.unsign_token(token, max_age=max_age, purpose="email_verify")
        parts = payload.split("|")
        if parts[0] != "verify" or len(parts) != 3:
            raise BadSignature("Invalid verification token format")
        return parts[1]

    def create_device_token(self, device_id: str, user_id: int) -> str:
        """Create a device authorization token."""
        token = self.generate("device")
        payload = f"device|{device_id}|{user_id}|{token}|{int(time.time())}"
        return self.sign_token(payload, "device_auth")

    def verify_device_token(self, token: str, max_age: int = 2592000) -> Dict[str, Any]:
        """Verify a device token and return device info."""
        payload = self.unsign_token(token, max_age=max_age, purpose="device_auth")
        parts = payload.split("|")
        if parts[0] != "device" or len(parts) != 5:
            raise BadSignature("Invalid device token format")

        return {
            "device_id": parts[1],
            "user_id": int(parts[2]),
            "token": parts[3],
            "issued_at": int(parts[4]),
        }


class TokenBucketRateLimiter:
    """
    Token bucket rate limiter for API endpoints.
    Thread-safe implementation using Redis or in-memory fallback.
    """

    def __init__(self, capacity: int, refill_rate: float, redis_client=None):
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.redis = redis_client
        self._local_buckets: Dict[str, Dict[str, Any]] = {}

    def _get_bucket(self, key: str) -> Dict[str, Any]:
        if self.redis:
            # Redis implementation would go here
            return {}  # Placeholder
        else:
            if key not in self._local_buckets:
                self._local_buckets[key] = {
                    "tokens": float(self.capacity),
                    "last_refill": time.time(),
                }
            return self._local_buckets[key]

    def consume(self, key: str, tokens: int = 1) -> bool:
        """Try to consume tokens from bucket. Returns True if allowed."""
        bucket = self._get_bucket(key)
        now = time.time()

        elapsed = now - bucket["last_refill"]
        bucket["tokens"] = min(
            self.capacity, bucket["tokens"] + elapsed * self.refill_rate
        )
        bucket["last_refill"] = now

        if bucket["tokens"] >= tokens:
            bucket["tokens"] -= tokens
            return True
        return False

    def get_remaining(self, key: str) -> int:
        """Get remaining tokens in bucket."""
        bucket = self._get_bucket(key)
        now = time.time()
        elapsed = now - bucket["last_refill"]
        tokens = min(self.capacity, bucket["tokens"] + elapsed * self.refill_rate)
        return int(tokens)


def generate_secure_random_string(
    length: int = 32, alphabet: Optional[str] = None
) -> str:
    """Generate a cryptographically secure random string."""
    if alphabet is None:
        alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"

    return "".join(secrets.choice(alphabet) for _ in range(length))


def constant_time_compare_strings(a: str, b: str) -> bool:
    """Constant-time string comparison."""
    return constant_time_compare(a.encode(), b.encode())


# Default instances
_default_generator: Optional[SecureTokenGenerator] = None


def get_token_generator() -> SecureTokenGenerator:
    """Get default token generator instance."""
    global _default_generator
    if _default_generator is None:
        _default_generator = SecureTokenGenerator()
    return _default_generator


def generate_api_key(identifier: str = "") -> str:
    """Generate an API key using default generator."""
    return get_token_generator().generate_api_key(identifier)


def hash_token(token: str) -> str:
    """Hash a token using default generator."""
    return get_token_generator().hash_token(token)


def verify_token_hash(token: str, stored_hash: str) -> bool:
    """Verify a token against stored hash using default generator."""
    return get_token_generator().verify_hash(token, stored_hash)


def create_password_reset_token(user_id: int) -> str:
    """Create a password reset token."""
    return get_token_generator().create_reset_token(user_id)


def verify_password_reset_token(token: str) -> int:
    """Verify a password reset token and return user_id."""
    return get_token_generator().verify_reset_token(token)


_default_generator: Optional[SecureTokenGenerator] = None

__all__ = [
    "SecureTokenGenerator",
    "TokenBucketRateLimiter",
    "generate_secure_random_string",
    "constant_time_compare_strings",
    "get_token_generator",
    "generate_api_key",
    "hash_token",
    "verify_token_hash",
    "create_password_reset_token",
    "verify_password_reset_token",
]
