import shutil
import time
from datetime import datetime

from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone


def _check_db():
    start = time.monotonic()
    try:
        with connection.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
        return {
            "status": "ok",
            "latency_ms": round((time.monotonic() - start) * 1000, 2),
        }
    except Exception as e:
        return {"status": "fail", "error": str(e)}


def _check_cache():
    start = time.monotonic()
    try:
        key = "healthz_probe"
        cache.set(key, "ok", 10)
        val = cache.get(key)
        ok = val == "ok"
        return {
            "status": "ok" if ok else "fail",
            "latency_ms": round((time.monotonic() - start) * 1000, 2),
            "backend": getattr(settings, "CACHES", {})
            .get("default", {})
            .get("BACKEND", "unknown"),
        }
    except Exception as e:
        return {"status": "fail", "error": str(e)}


def _check_disk():
    try:
        total, used, free = shutil.disk_usage(str(settings.BASE_DIR))
        pct = round(used / total * 100, 1)
        return {
            "status": "ok" if pct < 90 else "warn",
            "used_pct": pct,
            "free_gb": round(free / (1024**3), 2),
        }
    except Exception as e:
        return {"status": "fail", "error": str(e)}


def _check_migrations():
    try:
        executor = MigrationExecutor(connection)
        plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
        pending = len(plan)
        return {"status": "ok" if pending == 0 else "warn", "pending": pending}
    except Exception as e:
        return {"status": "fail", "error": str(e)}


def healthz_detailed(request):
    """GET /healthz -> JSON detalhado para Caddy/k8s + dashboard. Não requer auth."""
    data = {
        "status": "ok",
        "timestamp": timezone.now().isoformat(),
        "version": getattr(settings, "VERSION", "1.0.0"),
        "checks": {
            "db": _check_db(),
            "cache": _check_cache(),
            "disk": _check_disk(),
            "migrations": _check_migrations(),
        },
    }
    # status agregado: fail se qualquer check fail, warn se algum warn
    statuses = [v.get("status") for v in data["checks"].values()]
    if "fail" in statuses:
        data["status"] = "fail"
        status_code = 503
    elif "warn" in statuses:
        data["status"] = "warn"
        status_code = 200
    else:
        status_code = 200

    # header para Caddy não cachear
    resp = JsonResponse(data, status=status_code)
    resp["Cache-Control"] = "no-store"
    return resp


def health_dashboard(request):
    """GET /health/dashboard/ -> HTML observability (requer login)."""
    if not request.user.is_authenticated:
        from django.contrib.auth.views import redirect_to_login

        return redirect_to_login(request.get_full_path())
    data = {
        "db": _check_db(),
        "cache": _check_cache(),
        "disk": _check_disk(),
        "migrations": _check_migrations(),
    }
    # métricas leves da request atual
    ctx = {
        "checks": data,
        "now": datetime.now(),
        "debug": settings.DEBUG,
        "allowed_hosts": settings.ALLOWED_HOSTS,
        "caches_backend": getattr(settings, "CACHES", {})
        .get("default", {})
        .get("BACKEND", ""),
        "time": timezone.now(),
    }
    return render(request, "health-dashboard.html", ctx)
