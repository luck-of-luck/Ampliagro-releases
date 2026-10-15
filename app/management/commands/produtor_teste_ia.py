"""Um produtor de teste para a Fase 2, com senha conhecida.

POR QUE ISTO EXISTE
===================
A raiz `/` e' publica, por isso o dashboard abre sem sessao — e e' por isso que
o meu fetch a `/api/amplia/palco/info/` devolveu a PAGINA DE LOGIN com HTTP 200.
Status 200, `content-type: text/html`, titulo "Acesso ao sistema". Um fetch que
devolve 200 e nao e' o que se pediu e' o pior resultado para quem esta a
diagnosticar: parece que correu.

A view `palco_info` devolve SEMPRE `JsonResponse`, e tem `@login_required`. Logo
o HTML nao pode vir de la: vem do middleware, antes da view. E a unica forma de
o resolver e' ter uma sessao de verdade.

Este comando cria um produtor com senha conhecida e diz qual e', para nao ficar
a adivinhar senhas na base de dados de outra pessoa.

USO
===
    python manage.py produtor_teste_ia

NAO apaga o que ja' existe, NAO mexe em noutro produtor, e pode correr as vezes
que quiser. O que faz e' um utilizador novo com um nome proprio.
"""

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

NOME = "produtor_ia"
SENHA = "testar-ia-2026"


class Command(BaseCommand):
    help = "Cria um produtor de teste para experimentar a Fase 2 (guardar tela)."

    def handle(self, *args, **options):
        u, criado = User.objects.get_or_create(
            username=NOME,
            defaults={"email": "produtor-ia@exemplo.local", "is_staff": False},
        )
        u.is_active = True
        u.set_password(SENHA)
        u.save()

        from app.models.palco import PresetPalco

        accao = "CRIADO" if criado else "REUSADO (senha reposta)"
        self.stdout.write(self.style.SUCCESS(f"{accao}: {NOME} / {SENHA}"))
        self.stdout.write(
            f"presets deste produtor: {PresetPalco.objects.do_produtore(u).count()}"
        )
        self.stdout.write("")
        self.stdout.write("Entre em http://127.0.0.1:8000/login/ com esses dados.")
        self.stdout.write("Depois: Intelligence > converse 'guarda essa tela'.")
