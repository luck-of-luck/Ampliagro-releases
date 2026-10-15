import structlog
from celery import shared_task

from app.models import RelatorioGerado

logger = structlog.get_logger()

@shared_task
def gerar_relatorio_async(user_id, template_id):
    logger.info("gerando_relatorio_async", user_id=user_id, template_id=template_id)
    # Placeholder for actual report generation logic
    return True
