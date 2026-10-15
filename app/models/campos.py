"""
campos.py — tipos de campo que faltam no Django, prontos para este projeto.

Por que existe: `models.JSONField` usa `json.dumps` puro, que não sabe
serializar `Decimal`, `date`, `datetime` nem `UUID`. Numa ferramenta dinâmica
esses tipos são o pão com manteiga — um campo "Quantidade (kg)" é DECIMAL e um
campo "Quando" é DATA. Sem isto, `registrar()` quebrava na hora de gravar:

    TypeError: Object of type Decimal is not JSON serializable

e a quebra acontecia DEPOIS da validação, ou seja, o produtor via "criado com
sucesso" e o registro sumia.

`JSONFieldPortatil` usa o encoder do próprio Django, que serializa os quatro.
O preço é honesto e está documentado no método: **DECIMAL volta como string**.
Isso é preferível a guardar float, que perde precisão em dinheiro — "12.50" e
"12.5" são o mesmo número, e a diferença entre eles é o que a conciliação
bancária audita.

Motivo de ser uma subclasse e não um `encoder=` solto no model: o mesmo campo
precisa aparecer em vários models (dados, snapshot, escopo_iot) e o
`deconstruct()` precisa ser estável, senão toda migration futura detecta
mudança espúria.
"""

from datetime import date, datetime
from decimal import Decimal

from django.core.serializers.json import DjangoJSONEncoder
from django.db import models


class JSONFieldPortatil(models.JSONField):
    """`JSONField` que aceita Decimal, date, datetime, UUID e lazy strings.

    Portable entre SQLite e Postgres: é o mesmo `JSONField` do Django, só com
    encoder. Não usa operador de backend nenhum (ver `app/ia/json_portatil.py`
    para o que é e o que não é portátil).
    """

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("encoder", DjangoJSONEncoder)
        super().__init__(*args, **kwargs)

    def deconstruct(self):
        nome, caminho, args, kwargs = super().deconstruct()
        # DjangoJSONEncoder nao e serializavel para migration; o caminho de
        # import e a unica forma estavel de descrever isso.
        if "encoder" in kwargs and kwargs["encoder"] is DjangoJSONEncoder:
            kwargs.pop("encoder")
        return nome, caminho, args, kwargs

    def from_db_value(self, value, expression, connection):
        """Converte o que volta do banco para os tipos nativos.

        Só o JSONField precisa disso: o SQLite devolve a string que o encoder
        gravou, e quem lê `dados["quantidade_kg"]` tem de receber `Decimal`, não
        `str`, senão somar dois registros quebra. O Postgres (jsonb) devolve
        objeto já parseado, e o Django não chama este caminho lá.
        """
        if value is None or connection.vendor != "sqlite":
            return value
        import json

        try:
            return json.loads(value, parse_float=Decimal)
        except (TypeError, ValueError):
            return value


def para_tipos_nativos(valor):
    """Converte o que o `DjangoJSONEncoder` gravou de volta ao tipo do campo.

    Útil fora do caminho do banco — por exemplo, quando a IA devolve um schema
    e o código quer comparar antes de gravar.
    """
    if isinstance(valor, str):
        t = valor.strip()
        if re_data(t):
            try:
                return date.fromisoformat(t)
            except ValueError:
                pass
        if "T" in t:
            try:
                return datetime.fromisoformat(t)
            except ValueError:
                pass
    return valor


def re_data(t: str) -> bool:
    return len(t) == 10 and t[4] == "-" and t[7] == "-"
