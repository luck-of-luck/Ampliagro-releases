"""Caça-fantasmas: banco x models + viewsets/serializers x models.

Uso: python manage.py checar_drift
Sai 1 se houver coluna fantasma, tabela sem model, filterset/search/
ordering com campo inexistente ou serializer com campo inexistente.
"""

from django.apps import apps
from django.core.management.base import BaseCommand
from django.db import connection


def _model_field_names(model):
    out = set()
    for f in model._meta.get_fields():
        out.add(f.name)
        if hasattr(f, "attname"):
            out.add(f.attname)
    return out


class Command(BaseCommand):
    help = "Detecta drift banco x models e campos fantasma em viewsets/serializers"

    def handle(self, *args, **options):
        problemas = self.checar_banco()
        problemas += self.checar_viewsets()
        problemas += self.checar_serializers()
        if problemas:
            self.stdout.write(self.style.ERROR(f"{problemas} problema(s)"))
            raise SystemExit(1)
        self.stdout.write(self.style.SUCCESS("sem drift: banco == models == api"))

    def checar_banco(self):
        cur = connection.cursor()
        tables = [
            r[0]
            for r in cur.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name LIKE 'app_%' AND name NOT LIKE 'bkp_%'"
            ).fetchall()
        ]
        model_tables = {}
        for m in apps.get_app_config("app").get_models():
            model_tables[m._meta.db_table] = {f.column for f in m._meta.local_fields}

        problemas = 0
        for t in sorted(tables):
            if t not in model_tables:
                self.stdout.write(f"ORFA (sem model): {t}")
                continue
            db_cols = {
                c.name for c in connection.introspection.get_table_description(cur, t)
            }
            fantasmas = sorted(db_cols - model_tables[t])
            if fantasmas:
                problemas += 1
                self.stdout.write(self.style.WARNING(f"FANTASMA {t}: {fantasmas}"))
            faltando = sorted(model_tables[t] - db_cols)
            if faltando:
                problemas += 1
                self.stdout.write(self.style.ERROR(f"FALTA NO BANCO {t}: {faltando}"))
        return problemas

    def checar_viewsets(self):
        from rest_framework.viewsets import ModelViewSet

        from app.api import views as V

        problemas = 0
        for name in dir(V):
            cls = getattr(V, name)
            if not (
                isinstance(cls, type)
                and issubclass(cls, ModelViewSet)
                and cls is not ModelViewSet
            ):
                continue
            ser = getattr(cls, "serializer_class", None)
            model = getattr(ser, "Meta", None) and getattr(ser.Meta, "model", None)
            if model is None:
                continue
            ok = _model_field_names(model)
            for attr in ("filterset_fields", "search_fields", "ordering_fields"):
                for fld in getattr(cls, attr, None) or []:
                    root = fld.lstrip("-=^@$").split("__")[0]
                    if root not in ok and root != "id":
                        problemas += 1
                        self.stdout.write(
                            self.style.ERROR(
                                f"FANTASMA {name}.{attr}: '{fld}' nao existe em {model.__name__}"
                            )
                        )
        return problemas

    def checar_serializers(self):
        from rest_framework import serializers as S

        from app.api import serializers as SER

        problemas = 0
        for name in dir(SER):
            cls = getattr(SER, name)
            if not (
                isinstance(cls, type)
                and issubclass(cls, S.ModelSerializer)
                and cls is not S.ModelSerializer
            ):
                continue
            try:
                cls().get_fields()
            except Exception as e:
                problemas += 1
                self.stdout.write(self.style.ERROR(f"SERIALIZER QUEBRADO {name}: {e}"))
        return problemas
