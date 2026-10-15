"""
Security configuration for production deployment.
All settings are environment-driven with secure defaults.
"""

import os
from django.conf import settings

# ============================================================================
# PASSWORD HASHING - SHA-512 based (PBKDF2 with SHA-512)
# ============================================================================

# Use PBKDF2 with SHA-512 for production - 600,000 iterations (OWASP 2024 recommendation)
# The default Django is PBKDF2 with SHA-256 at 600,000 iterations
PASSWORD_HASHERS = [
    "app.security.hashers.PBKDF2SHA512PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.BCryptSHA256PasswordHasher",
    "django.contrib.auth.hashers.ScryptPasswordHasher",
]

# Minimum password requirements (enforced by validators + hashers)
PASSWORD_MIN_LENGTH = 12
PASSWORD_REQUIRE_SPECIAL = True
PASSWORD_REQUIRE_UPPER = True
PASSWORD_REQUIRE_LOWER = True
PASSWORD_REQUIRE_NUMBER = True
PASSWORD_MAX_LENGTH = 128

# ============================================================================
# SESSION SECURITY
# ============================================================================

# Session cookie settings - all secure by default
SESSION_COOKIE_AGE = int(os.environ.get("SESSION_COOKIE_AGE", "7200"))  # 2 hours
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Strict"
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_SAVE_EVERY_REQUEST = True  # Rotate session on each request

# CSRF protection
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = "Strict"
CSRF_USE_SESSIONS = True  # Store CSRF in session instead of cookie
CSRF_FAILURE_VIEW = "app.views.auth.csrf_failure"

# ============================================================================
# SECURITY HEADERS (additional to Django's built-in)
# ============================================================================

# HSTS - 1 year with preload (configure via env for production)
SECURE_HSTS_SECONDS = int(os.environ.get("SECURE_HSTS_SECONDS", "31536000"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# SSL redirect (configure via env)
SECURE_SSL_REDIRECT = os.environ.get("SECURE_SSL_REDIRECT", "True").lower() in (
    "true",
    "1",
    "t",
)

# Content security
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

# Additional headers via middleware
SECURE_CUSTOM_HEADERS = {
    "Permissions-Policy": (
        "accelerometer=(), camera=(), geolocation=(), gyroscope=(), "
        "magnetometer=(), microphone=(), payment=(), usb=()"
    ),
    "Cross-Origin-Embedder-Policy": "require-corp",
    "Cross-Origin-Resource-Policy": "same-origin",
}

# ============================================================================
# AUTHENTICATION HARDENING
# ============================================================================

# Login attempt limiting (complements django-axes)
LOGIN_ATTEMPTS_LIMIT = int(os.environ.get("LOGIN_ATTEMPTS_LIMIT", "5"))
LOGIN_LOCKOUT_DURATION = int(os.environ.get("LOGIN_LOCKOUT_DURATION", "900"))  # 15 min
LOGIN_LOCKOUT_TEMPLATE = "globais/lockout.html"

# Password reset security
PASSWORD_RESET_TIMEOUT = int(os.environ.get("PASSWORD_RESET_TIMEOUT", "1800"))  # 30 min
PASSWORD_RESET_TOKEN_LENGTH = 64

# Two-factor authentication (via django-allauth or custom)
TWO_FACTOR_ENABLED = os.environ.get("TWO_FACTOR_ENABLED", "False").lower() in (
    "true",
    "1",
    "t",
)
TWO_FACTOR_ISSUER = "Ampliagro2"

# ============================================================================
# API SECURITY
# ============================================================================

# API rate limiting (complements DRF throttling)
API_RATE_LIMIT_ANON = "100/hour"
API_RATE_LIMIT_USER = "1000/hour"
API_RATE_LIMIT_AUTH = "10/minute"  # Auth endpoints stricter

# API key settings
API_KEY_HEADER = "X-API-Key"
API_KEY_LENGTH = 64
API_KEY_PREFIX = "ak_"  # Identifiable prefix for logging

# ============================================================================
# ENCRYPTION SETTINGS
# ============================================================================

# Field encryption key (32 bytes for AES-256)
# Generate with: python -c "import secrets; print(secrets.token_hex(32))"
FIELD_ENCRYPTION_KEY = os.environ.get("FIELD_ENCRYPTION_KEY", "")
DEBUG_ENV = os.environ.get("DEBUG", "False").lower() in ("true", "1", "t")
if not FIELD_ENCRYPTION_KEY and not DEBUG_ENV:
    raise ValueError("FIELD_ENCRYPTION_KEY must be set in production")

# Encryption algorithm
FIELD_ENCRYPTION_ALGORITHM = "AES-256-GCM"  # Authenticated encryption

# ============================================================================
# AUDIT LOGGING
# ============================================================================

AUDITLOG_INCLUDE_ALL_MODELS = True
AUDITLOG_EXCLUDE_TRACKING_FIELDS = ["password", "secret", "token", "key"]
AUDITLOG_MASKED_FIELDS = [
    "password",
    "secret",
    "token",
    "key",
    "api_key",
    "private_key",
]

# ============================================================================
# CONTENT SECURITY POLICY - Production strict mode
# ============================================================================

CSP_STRICT_MODE = not DEBUG_ENV

# ============================================================================
# FILE UPLOAD SECURITY
# ============================================================================

FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024  # 5 MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024  # 5 MB
FILE_UPLOAD_PERMISSIONS = 0o600
FILE_UPLOAD_DIRECTORY_PERMISSIONS = 0o700

# Allowed upload types (restrict by content-type AND extension)
ALLOWED_UPLOAD_TYPES = {
    "image/jpeg": [".jpg", ".jpeg"],
    "image/png": [".png"],
    "image/webp": [".webp"],
    "application/pdf": [".pdf"],
    "text/csv": [".csv"],
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [".xlsx"],
}

# ============================================================================
# DATABASE SECURITY
# ============================================================================

# Connection pooling with encryption
DATABASE_OPTIONS = {
    "sslmode": "require",  # Require SSL for PostgreSQL
    "connect_timeout": 10,
    "options": "-c statement_timeout=30000",  # 30s query timeout
}

# ============================================================================
# EMAIL SECURITY
# ============================================================================

EMAIL_USE_TLS = True
EMAIL_USE_SSL = False
EMAIL_TIMEOUT = 30

# ============================================================================
# CACHING SECURITY
# ============================================================================

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": os.environ.get("REDIS_URL", "redis://localhost:6379/1"),
        "OPTIONS": {
            "ssl_cert_reqs": "required",
            "socket_timeout": 5,
            "socket_connect_timeout": 5,
        },
        "KEY_PREFIX": "ampliagro2",
        "TIMEOUT": 300,
    }
}

# ============================================================================
# CORS SECURITY
# ============================================================================

CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get("CORS_ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
]
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_ALL_ORIGINS = False
CORS_EXPOSE_HEADERS = ["X-Request-ID", "X-Response-Time"]
CORS_PREFLIGHT_MAX_AGE = 86400  # 24 hours

# ============================================================================
# PROXY/SSL TERMINATION
# ============================================================================

# Trust X-Forwarded-* headers only from known proxies
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True
USE_X_FORWARDED_PORT = True

# Trusted proxy IPs (comma-separated)
TRUSTED_PROXY_IPS = [
    ip.strip()
    for ip in os.environ.get("TRUSTED_PROXY_IPS", "127.0.0.1").split(",")
    if ip.strip()
]

# ============================================================================
# SECURITY MONITORING
# ============================================================================

# Log all authentication events
AUTH_LOGGING_ENABLED = True
AUTH_LOG_FAILED_ATTEMPTS = True
AUTH_LOG_SUCCESSFUL_LOGINS = True
AUTH_LOG_PASSWORD_CHANGES = True
AUTH_LOG_PERMISSION_CHANGES = True

# Security event alerting
SECURITY_ALERT_EMAIL = os.environ.get("SECURITY_ALERT_EMAIL", "")
SECURITY_ALERT_THRESHOLD = int(
    os.environ.get("SECURITY_ALERT_THRESHOLD", "10")
)  # Failed attempts before alert
