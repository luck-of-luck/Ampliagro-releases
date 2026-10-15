"""
Security middleware for Django.
Provides security headers, rate limiting, and request validation.
"""

import time
import logging
from typing import Optional, Callable, Any
from django.conf import settings
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils.deprecation import MiddlewareMixin
from django.core.cache import cache
from django.core.exceptions import PermissionDenied

from app.security.tokens import TokenBucketRateLimiter

logger = logging.getLogger(__name__)


# Type annotation for HttpRequest with dynamic attributes
class _HttpRequest(HttpRequest):
    user: Any
    api_key: Optional[str]
    _audit_start_time: float


class SecurityHeadersMiddleware(MiddlewareMixin):
    """
    Adds security headers to all responses.
    Implements defense-in-depth security headers.
    """

    def __init__(self, get_response: Callable):
        self.get_response = get_response
        super().__init__(get_response)

        # Default security headers
        self.security_headers = getattr(
            settings,
            "SECURE_CUSTOM_HEADERS",
            {
                "Permissions-Policy": (
                    "accelerometer=(), camera=(), geolocation=(), gyroscope=(), "
                    "magnetometer=(), microphone=(), payment=(), usb=()"
                ),
                "Cross-Origin-Embedder-Policy": "require-corp",
                "Cross-Origin-Resource-Policy": "same-origin",
                "X-Content-Type-Options": "nosniff",
                "X-Frame-Options": "DENY",
                "X-XSS-Protection": "1; mode=block",
                "Referrer-Policy": "strict-origin-when-cross-origin",
            },
        )

    def process_response(
        self, request: HttpRequest, response: HttpResponse
    ) -> HttpResponse:
        # Add security headers
        for header, value in self.security_headers.items():
            if header not in response:
                response[header] = value

        # Add CSP if not already set
        if "Content-Security-Policy" not in response:
            csp = getattr(settings, "CONTENT_SECURITY_POLICY", None)
            if csp:
                directives = csp.get("DIRECTIVES", {})
                csp_header = "; ".join(
                    f"{k} {' '.join(v)}" for k, v in directives.items()
                )
                response["Content-Security-Policy"] = csp_header

        # HSTS header for HTTPS
        if request.is_secure() and not settings.DEBUG:
            hsts_seconds = getattr(settings, "SECURE_HSTS_SECONDS", 31536000)
            hsts_header = f"max-age={hsts_seconds}"
            if getattr(settings, "SECURE_HSTS_INCLUDE_SUBDOMAINS", True):
                hsts_header += "; includeSubDomains"
            if getattr(settings, "SECURE_HSTS_PRELOAD", True):
                hsts_header += "; preload"
            response["Strict-Transport-Security"] = hsts_header

        # Remove server header for security
        if "Server" in response:
            del response["Server"]

        return response


class RateLimitMiddleware(MiddlewareMixin):
    """
    Rate limiting middleware using token bucket algorithm.
    Supports both authenticated and anonymous users.
    """

    def __init__(self, get_response: Callable):
        self.get_response = get_response
        super().__init__(get_response)

        # Rate limit configurations
        self.limits = {
            "default": {
                "capacity": 1000,
                "refill_rate": 1000 / 3600,  # 1000/hour
            },
            "auth": {
                "capacity": 10,
                "refill_rate": 10 / 60,  # 10/minute
            },
            "api": {
                "capacity": 100,
                "refill_rate": 100 / 60,  # 100/minute
            },
            "login": {
                "capacity": 5,
                "refill_rate": 5 / 300,  # 5/5min
            },
            "password_reset": {
                "capacity": 3,
                "refill_rate": 3 / 3600,  # 3/hour
            },
        }

        self.limiters = {}
        for name, config in self.limits.items():
            self.limiters[name] = TokenBucketRateLimiter(
                capacity=config["capacity"], refill_rate=config["refill_rate"]
            )

    def _get_client_ip(self, request: HttpRequest) -> str:
        """Extract client IP, respecting proxy headers if configured."""
        xff = request.META.get("HTTP_X_FORWARDED_FOR")
        if xff and getattr(settings, "TRUSTED_PROXY_IPS", []):
            # Only trust X-Forwarded-For from known proxies
            client_ip = xff.split(",")[0].strip()
            return client_ip
        return request.META.get("REMOTE_ADDR", "unknown")

    def _get_rate_limit_key(self, request: HttpRequest, limit_type: str) -> str:
        """Generate rate limit key for request."""
        ip = self._get_client_ip(request)
        user_id = request.user.id if request.user.is_authenticated else "anon"
        return f"ratelimit:{limit_type}:{user_id}:{ip}"

    def _check_rate_limit(self, request: HttpRequest, limit_type: str) -> bool:
        """Check if request is within rate limits."""
        key = self._get_rate_limit_key(request, limit_type)
        limiter = self.limiters.get(limit_type, self.limiters["default"])
        return limiter.consume(key)

    def process_request(self, request: HttpRequest) -> Optional[HttpResponse]:
        # Skip rate limiting for health checks and static files
        if request.path.startswith(("/health", "/static/", "/media/", "/favicon.ico")):
            return None

        # Determine rate limit type based on path
        limit_type = "default"
        if request.path.startswith("/api/auth/") or request.path in [
            "/login/",
            "/password-reset/",
        ]:
            limit_type = "auth"
        elif request.path.startswith("/api/"):
            limit_type = "api"
        elif request.path in ["/login/"]:
            limit_type = "login"
        elif request.path in ["/password-reset/"]:
            limit_type = "password_reset"

        if not self._check_rate_limit(request, limit_type):
            logger.warning(
                "Rate limit exceeded",
                extra={
                    "path": request.path,
                    "ip": self._get_client_ip(request),
                    "user": request.user.id
                    if request.user.is_authenticated
                    else "anonymous",
                    "limit_type": limit_type,
                },
            )
            return JsonResponse(
                {
                    "error": "Rate limit exceeded",
                    "message": "Too many requests. Please try again later.",
                    "retry_after": 60,
                },
                status=429,
                headers={"Retry-After": "60"},
            )

        return None


class RequestValidationMiddleware(MiddlewareMixin):
    """
    Validates incoming requests for common attack patterns.
    """

    # Suspicious patterns that might indicate attacks
    SUSPICIOUS_PATTERNS = [
        # SQL injection
        r"(?i)(\bunion\b.*\bselect\b|\bselect\b.*\bunion\b)",
        r"(?i)\bor\b\s+\d+\s*=\s*\d+",
        r"(?i)\bunion\b\s+all\s+\bselect\b",
        # XSS
        r"<script[^>]*>.*?</script>",
        r"javascript:",
        r"on\w+\s*=",
        # Path traversal
        r"\.\./",
        r"\.\.\\",
        # Command injection
        r"(?i)(;|\||&|\$\(|\`)",
        # LDAP injection
        r"\(\|",
        # NoSQL injection
        r"\$\w+",
    ]

    def __init__(self, get_response: Callable):
        self.get_response = get_response
        super().__init__(get_response)
        import re

        self._compiled_patterns = [re.compile(p) for p in self.SUSPICIOUS_PATTERNS]

    def process_request(self, request: HttpRequest) -> Optional[HttpResponse]:
        # Skip validation for safe methods
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return None

        # Check content type
        content_type = request.META.get("CONTENT_TYPE", "")
        if (
            "application/json" not in content_type
            and "multipart/form-data" not in content_type
        ):
            return None

        # Check request body size
        max_size = getattr(settings, "DATA_UPLOAD_MAX_MEMORY_SIZE", 5 * 1024 * 1024)
        content_length = request.META.get("CONTENT_LENGTH")
        if content_length and int(content_length) > max_size:
            logger.warning(
                "Request body too large",
                extra={
                    "path": request.path,
                    "content_length": content_length,
                    "max_size": max_size,
                    "ip": request.META.get("REMOTE_ADDR"),
                },
            )
            return JsonResponse({"error": "Request body too large"}, status=413)

        # Scan for suspicious patterns in request body
        try:
            body = request.body.decode("utf-8", errors="ignore")
            for pattern in self._compiled_patterns:
                if pattern.search(body):
                    logger.warning(
                        "Suspicious request pattern detected",
                        extra={
                            "path": request.path,
                            "pattern": pattern.pattern,
                            "ip": request.META.get("REMOTE_ADDR"),
                            "user": request.user.id
                            if request.user.is_authenticated
                            else "anonymous",
                        },
                    )
                    # Don't block - just log for monitoring
                    break
        except Exception:
            pass  # Ignore decoding errors

        return None


class APIKeyAuthenticationMiddleware(MiddlewareMixin):
    """
    API Key authentication for machine-to-machine communication.
    """

    def __init__(self, get_response: Callable):
        self.get_response = get_response
        super().__init__(get_response)

        # Paths that require API key
        self.api_key_paths = getattr(
            settings,
            "API_KEY_REQUIRED_PATHS",
            [
                "/api/v1/",
                "/api/webhook/",
            ],
        )

        # Header name for API key
        self.api_key_header = getattr(settings, "API_KEY_HEADER", "X-API-Key")

    def process_request(self, request: HttpRequest) -> Optional[HttpResponse]:
        # Check if path requires API key
        requires_api_key = any(
            request.path.startswith(path) for path in self.api_key_paths
        )

        if not requires_api_key:
            return None

        # Check for API key in header
        api_key = request.META.get(
            f"HTTP_{self.api_key_header.replace('-', '_').upper()}"
        )
        if not api_key:
            # Also check Authorization header
            auth_header = request.META.get("HTTP_AUTHORIZATION", "")
            if auth_header.startswith("ApiKey "):
                api_key = auth_header[7:]

        if not api_key:
            return JsonResponse(
                {"error": "API key required", "code": "API_KEY_MISSING"}, status=401
            )

        # Validate API key (implement your validation logic)
        # This is a placeholder - integrate with your API key storage
        if not self._validate_api_key(api_key):
            logger.warning(
                "Invalid API key attempted",
                extra={
                    "path": request.path,
                    "ip": request.META.get("REMOTE_ADDR"),
                    "api_key_prefix": api_key[:8] if api_key else "none",
                },
            )
            return JsonResponse(
                {"error": "Invalid API key", "code": "API_KEY_INVALID"}, status=401
            )

        # Store API key info on request for views to use
        request.api_key = api_key
        return None

    def _validate_api_key(self, api_key: str) -> bool:
        """
        Validate API key against stored keys.
        Implement your own validation logic here.
        """
        # Placeholder - implement actual validation
        # Example: Check against database of hashed API keys
        return True


class AuditLoggingMiddleware(MiddlewareMixin):
    """
    Audit logging middleware for security-relevant events.
    Logs authentication, authorization, and data access events.
    """

    def __init__(self, get_response: Callable):
        self.get_response = get_response
        super().__init__(get_response)
        self.audit_logger = logging.getLogger("security.audit")

    def process_request(self, request: HttpRequest) -> Optional[HttpResponse]:
        # Store request start time for duration calculation
        request._audit_start_time = time.time()
        return None

    def process_response(
        self, request: HttpRequest, response: HttpResponse
    ) -> HttpResponse:
        # Log security-relevant events
        self._audit_request(request, response)
        return response

    def _audit_request(self, request: HttpRequest, response: HttpResponse):
        # Skip non-security-relevant requests
        if request.path.startswith(("/static/", "/media/", "/health", "/favicon.ico")):
            return

        # Determine if this is a security event
        is_security_event = (
            request.path.startswith("/api/auth/")
            or request.path in ["/login/", "/logout/", "/password-reset/"]
            or response.status_code in (401, 403, 429)
            or request.method in ("POST", "PUT", "PATCH", "DELETE")
        )

        if not is_security_event:
            return

        # Calculate request duration
        duration = 0
        if hasattr(request, "_audit_start_time"):
            duration = (time.time() - request._audit_start_time) * 1000  # ms

        # Build audit record
        audit_data = {
            "timestamp": time.time(),
            "method": request.method,
            "path": request.path,
            "status_code": response.status_code,
            "duration_ms": round(duration, 2),
            "ip": request.META.get("REMOTE_ADDR"),
            "user_agent": request.META.get("HTTP_USER_AGENT", "")[:200],
            "user_id": request.user.id if request.user.is_authenticated else None,
            "username": request.user.username
            if request.user.is_authenticated
            else None,
            "referer": request.META.get("HTTP_REFERER", "")[:200],
        }

        # Log at appropriate level
        if response.status_code >= 400:
            self.audit_logger.warning("Security event", extra=audit_data)
        else:
            self.audit_logger.info("Security event", extra=audit_data)


# Convenience function to apply all security middlewares
def get_security_middlewares():
    """Returns list of security middleware classes in correct order."""
    return [
        "app.security.middleware.SecurityHeadersMiddleware",
        "app.security.middleware.RateLimitMiddleware",
        "app.security.middleware.RequestValidationMiddleware",
        "app.security.middleware.AuditLoggingMiddleware",
    ]


__all__ = [
    "SecurityHeadersMiddleware",
    "RateLimitMiddleware",
    "RequestValidationMiddleware",
    "APIKeyAuthenticationMiddleware",
    "AuditLoggingMiddleware",
    "get_security_middlewares",
]
