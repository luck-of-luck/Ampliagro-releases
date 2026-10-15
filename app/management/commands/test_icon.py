from django.core.management.base import BaseCommand
from django.template import Context, Template


class Command(BaseCommand):
    help = 'Testa renderizacao de template'

    def handle(self, *args, **options):
        try:
            t = Template('{% load agro_icons %}{{ "bovinos"|grupo_icon }}')
            c = Context({})
            print(t.render(c))

            t2 = Template('{% load agro_icons %}{{ "graos"|grupo_icon }}')
            print(t2.render(c))
        except Exception:
            import traceback
            traceback.print_exc()
