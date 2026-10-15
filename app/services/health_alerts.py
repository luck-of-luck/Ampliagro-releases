import logging
import os

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

SLACK_WEBHOOK = getattr(
    settings,
    "HEALTH_ALERT_SLACK_WEBHOOK",
    os.environ.get("HEALTH_ALERT_SLACK_WEBHOOK", ""),
)
TELEGRAM_BOT_TOKEN = getattr(
    settings,
    "HEALTH_ALERT_TELEGRAM_BOT_TOKEN",
    os.environ.get("HEALTH_ALERT_TELEGRAM_BOT_TOKEN", ""),
)
TELEGRAM_CHAT_ID = getattr(
    settings,
    "HEALTH_ALERT_TELEGRAM_CHAT_ID",
    os.environ.get("HEALTH_ALERT_TELEGRAM_CHAT_ID", ""),
)


def send_health_alert(checks: dict, status: str):
    """
    Envia alerta quando healthz != ok. Usa Slack webhook e/ou Telegram bot se configurados,
    senão apenas loga como warning. Retorna dict com resultados por canal.
    """
    if status == "ok":
        return {"sent": False, "reason": "status ok"}

    # monta mensagem compacta
    lines = [f"🚨 Ampliagro healthz: *{status.upper()}*"]
    for name, chk in checks.items():
        s = chk.get("status", "unknown")
        emoji = "✅" if s == "ok" else "⚠️" if s == "warn" else "❌"
        detail = ""
        if chk.get("latency_ms") is not None:
            detail += f" {chk['latency_ms']}ms"
        if chk.get("error"):
            detail += f" err:{str(chk['error'])[:80]}"
        if chk.get("pending"):
            detail += f" pending:{chk['pending']}"
        lines.append(f"{emoji} {name}: {s}{detail}")
    text = "\n".join(lines)
    results = {}

    # Slack
    if SLACK_WEBHOOK:
        try:
            r = requests.post(SLACK_WEBHOOK, json={"text": text}, timeout=3)
            results["slack"] = {"ok": r.ok, "status": r.status_code}
        except Exception as e:
            results["slack"] = {"ok": False, "error": str(e)}
            logger.warning("health_alert slack fail: %s", e)
    else:
        results["slack"] = {
            "skipped": True,
            "reason": "HEALTH_ALERT_SLACK_WEBHOOK não configurado",
        }

    # Telegram
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            r = requests.post(
                url,
                json={
                    "chat_id": TELEGRAM_CHAT_ID,
                    "text": text,
                    "parse_mode": "Markdown",
                },
                timeout=3,
            )
            results["telegram"] = {"ok": r.ok, "status": r.status_code}
        except Exception as e:
            results["telegram"] = {"ok": False, "error": str(e)}
            logger.warning("health_alert telegram fail: %s", e)
    else:
        results["telegram"] = {
            "skipped": True,
            "reason": "TELEGRAM_BOT_TOKEN/CHAT_ID não configurados",
        }

    # sempre loga
    logger.warning(
        "health_alert sent status=%s checks=%s results=%s", status, checks, results
    )
    return {"sent": True, "text": text, "results": results}
