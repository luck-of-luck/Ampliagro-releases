"""A guarda de dono, num sitio so — e dentro do serializer.

MEDIDO 2026-10-05 (agente 11). Inventario dos serializers: 25 validam a
pertenca dentro de si (com `validate_propriedade`/`validate_talhao`), e **37
nao**. Os 37 dependem do middleware.

A diferenca nao e' o numero. E' de QUEM depende a garantia:

  * um serializer com guarda protege-se a si proprio;
  * um sem guarda depende de uma linha noutro ficheiro — e essa linha ja
    demonstrou, DUAS vezes, que pode ter lapse em silencio: primeiro o corpo
    JSON, depois o nome do campo. Nenhuma das duas deu erro.

Porquê um modulo, e nao mais um `validate_*` copiado para cada um:

  * o caminho de um registo ate ao dono nao e' o mesmo em todos. Um
    `talhao` tem `talhao.propriedade`; um `insumo` tem
    `insumo.propriedade`; uma `safra` tem `safra.talhao.propriedade`; um
    `funcionario` tem `funcionario.propriedade`. Escrever essa cadeia a mao em
    37 serializers e' como se obtem uma cadeia errada em tres deles.
  * uma funcao partilhada e' um sitio unico para corrigir quando a propriedade
    ganha um nivel. Com 37 copias, sao 37 sítios a esquecer.

COMO SE USA
===========

    class AplicacaoInsumoSerializer(OwnershipMixin, serializers.ModelSerializer):
        dono_pelo_campo = {"talhao": "talhao.propriedade"}

O mixin encontra o `validate_<campo>` de cada campo declarado e chama a
cadeia. O serializer fica com a guarda **dentro de si** — que e' o ponto.
"""

from __future__ import annotations

from rest_framework import serializers

# a cadeia de um registo ate ao `user`. Cada entrada: o campo do serializer, e
# o caminho de atributos ate ao dono, NO MODELO DE DESTINO.
CADEIAS = {
    "propriedade": "user",
    "user": "user",
    "talhao": "propriedade.user",
    "safra": "talhao.propriedade.user",
    "insumo": "propriedade.user",
    "maquinario": "propriedade.user",
    "funcionario": "propriedade.user",
    "animal": "propriedade.user",
    "device": "propriedade.user",
    "gateway": "propriedade.user",
    "estacao": "propriedade.user",
    "safra_a": "talhao.propriedade.user",
    "safra_b": "talhao.propriedade.user",
    "talhao_a": "propriedade.user",
    "talhao_b": "propriedade.user",
    "lote": "propriedade.user",
    "colmeia": "apiario.propriedade.user",
    "fonte": "propriedade.user",
}


def dono_de(obj, caminho: str):
    """Segue `talhao.propriedade.user` e devolve o user, ou None se algo falta."""
    atual = obj
    for parte in caminho.split("."):
        if atual is None:
            return None
        atual = getattr(atual, parte, None)
    return atual


class OwnershipMixin:
    """Guarda de pertenca, dentro do serializer.

    Declarar `dono_pelo_campo = {"talhao": "talhao.propriedade.user"}` e' o
    mesmo que escrever o `validate_talhao` a mao — mas a cadeia esta escrita
    uma vez so.

    Deliberadamente NAO usa `self.request`: um serializer chamado sem request
    (carga directa, task de fundo) nao tem como saber a quem pertence, e
    inventar essa resposta seria devolver `True` a um `validate` que nao
    valida nada. Nesse caso o campo e' deixado como veio — e quem chama tem de
    garantir o escopo. Um `validate` que passa quando nao sabe e' pior do que
    um `validate` que falha, porque parece que a propriedade esta' garantida.
    """

    #: {"<campo do serializer>": "<cadeia de atributos ate ao user>"}
    dono_pelo_campo: dict[str, str] = {}

    def _validar_dono(self, campo: str, valor):
        cadeia = (self.dono_pelo_campo or {}).get(campo)
        if not cadeia:
            return valor

        request = self.context.get("request")
        user = getattr(request, "user", None) if request else None
        if user is None or not getattr(user, "is_authenticated", False):
            return valor

        dono = dono_de(valor, cadeia)
        if dono is None:
            # o registo existe mas a cadeia nao chega ao dono (ex: talhao sem
            # propriedade). Nao se pode afirmar a pertenca.
            raise serializers.ValidationError(
                {
                    "campo": f"Não foi possível confirmar a quem pertence este "
                    f"registo ({campo})."
                }
            )
        if dono_id(dono) != user.pk:
            raise serializers.ValidationError(
                {campo: "Este registo não pertence à sua propriedade."}
            )
        return valor


def _make_validador(campo: str):
    """Cria a funcao `validate_<campo>` de uma vez."""

    def validador(self, valor):
        return self._validar_dono(campo, valor)

    validador.__name__ = f"validate_{campo}"
    validador.__qualname__ = f"validate_{campo}"
    return validador


class OwnershipMixin:
    """Guarda de pertenca, dentro do serializer.

    Declarar `dono_pelo_campo = {"talhao": "talhao.propriedade.user"}` produz o
    mesmo efeito que escrever o `validate_talhao` a mao — mas a cadeia esta
    escrita uma vez so.
    """

    #: {"<campo do serializer>": "<cadeia de atributos ate ao user>"}
    dono_pelo_campo: dict[str, str] = {}

    def _validar_dono(self, campo: str, valor):
        cadeia = (self.dono_pelo_campo or {}).get(campo)
        if not cadeia:
            return valor

        request = self.context.get("request")
        user = getattr(request, "user", None) if request else None
        if user is None or not getattr(user, "is_authenticated", False):
            return valor

        dono = dono_de(valor, cadeia)
        if dono is None:
            raise serializers.ValidationError(
                {campo: "Nao foi possivel confirmar a quem pertence este registo."}
            )
        if dono_id(dono) != user.pk:
            raise serializers.ValidationError(
                {campo: "Este registo nao pertence a sua propriedade."}
            )
        return valor

    def __init_subclass__(cls, **kw):
        """Gera `validate_<campo>` REAIS para cada campo declarado.

        Porquê `__init_subclass__` e nao `__getattr__`: `__getattr__` e' de
        INSTANCIA. Funcionaria em runtime, mas o validador nao seria um
        atributo de verdade — nao apareceria em `dir()`, e um teste (ou o
        proprio `hasattr`) nao o encontraria. Um validador que so' existe
        quando alguem o pede e' um validador de que ninguem tem certeza.

        Aqui o metodo e' criado na classe. E um `validate_talhao` escrito a mao
        pelo autor NAO e' sobrescrito: `setattr` so' acontece quando o nome
        ainda nao existe nesta classe.
        """
        super().__init_subclass__(**kw)
        declarados = cls.__dict__.get("dono_pelo_campo") or {}
        for campo in declarados:
            nome = f"validate_{campo}"
            if nome in cls.__dict__:
                continue
            setattr(cls, nome, _make_validador(campo))


def dono_id(user) -> int | None:
    return getattr(user, "pk", None) or getattr(user, "id", None)


def inventariar_serializer(cls) -> dict[str, str]:
    """Que campos deste serializer apontam para um registo que tem dono?"""

    campos: dict[str, str] = {}
    meta = getattr(cls, "Meta", None)
    if meta is None:
        return campos
    for f in getattr(meta, "fields", []) or []:
        nome = getattr(f, "source", None) or f
        if nome in CADEIAS:
            campos[nome] = CADEIAS[nome]
    return campos
