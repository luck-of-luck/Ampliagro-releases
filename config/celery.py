import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

app = Celery("ampliagro")

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object("django.conf:settings", namespace="CELERY")

# Load task modules from all registered Django apps.
app.autodiscover_tasks()

try:
    from app.ia.proativo_tasks import BEAT_SCHEDULE

    app.conf.beat_schedule = BEAT_SCHEDULE
except ImportError as e:
    # Isto NAO pode ser um `pass` mudo. Um ImportError aqui significa que
    # `app.ia.proativo_tasks` nao importou — e esse modulo e' o worker
    # proativo INTEIRO (as regras determinéticas, os tetos, a purga).
    #
    # Calado, o worker celery arrancava, nao tinha tarefa agendada nenhuma, e
    # o Agendador do Windows continuava a registar "sucesso". O sintoma era
    # "a IA avisa as vezes": sem log, nao ha nada que ligue o silencio do
    # worker a esta linha.
    import logging

    logging.getLogger(__name__).warning(
        "celery: BEAT_SCHEDULE nao carregou (%s: %s). O worker celery vai correr "
        "SEM tarefas agendadas. Se o Agendador de Tarefas do Windows estiver "
        "armado (tools/bat/setup_tarefa_proativa.bat), a varredura continua por "
        "la; se nao estiver, nao ha varredura nenhuma — e ninguem vai ver erro.",
        type(e).__name__,
        e,
    )


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f"Request: {self.request!r}")
