"""A revogação de um servidor, num sítio só.

O problema que este ficheiro resolve
====================================

`perfil.ativo_servidor = False` significa "o produtor desligou este
servidor". A partir desse momento, nenhuma operação em nome desse servidor
devia chegar aos dados da fazenda.

A primeira correcção foi o `ServidorRevogadoMiddleware` (`app/middleware.py`),
que é um ponto único e bom — mas é um ponto **HTTP**. E existem operações que
**não passam por HTTP**:

  - um **task do Celery** não recebe um `request`; não entra no middleware;
  - uma **management command** corre de linha de comandos; não entra;
  - uma **view de API** que declara as suas próprias `permission_classes`
    continua a ser servida, porque o default do DRF foi sobreposto.

Isto é o mesmo motivo pelo qual `MERGED.md` regista que um `permission class`
em `DEFAULT_PERMISSION_CLASSES` não resolveria o problema: cada view declara as
suas, e o default fica de fora.

A regra
========

> **Uma regra que tem de valer em N sítios não pode ser lembrada em N sítios.
> Tem de ser um sítio, e o resto descobre.**

Este módulo é esse sítio. `exigir_servidor_ativo()` é fail-closed e é chamada:

  - em `app/api/views/faltantes.py`, dentro de `make_scoped_viewset()`
    (todas as viewsets geradas de uma vez);
  - em `app/ia/propriedade.py::resolver()`, que é por onde TODO o tenancy da
    IA passa — incluindo quando o caller é um task assíncrono;
  - pelos testes que medem a superfície da API.

Quem sabe tem de a chamar. Se amanha nascer uma terceira porta, omitir esta
chamada é um erro de revisão — e o teste de superfície não a apanha, porque o
middleware continua a cobrir o HTTP.

Por que isto NÃO substitui o middleware
========================================

O middleware é o **primeiro** filtro: recusa antes de gastar uma query. Isto é o
**segundo**: vem depois, e cobre quem não passou pelo primeiro. Um dia em que o
`request` não existe, este ainda funciona.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

#: A mensagem que o produtor vê. Não é um 403 genérico: diz o que aconteceu,
#: porque um "403 Forbidden" sem explicação é indistinguível de "a sua sessão
#: acabou" — e o produtor responde à sessão, não ao servidor.
MENSAGEM = "Servidor desativado pelo produtor."


def servidor_ativo(user) -> bool:
    """Diz se `user` pode operar. Fail-closed: na duvida, diz que não.

    Devolver `True` quando não se consegue ler o flag é a falha mais grave que
    este ficheiro pode ter: transforma uma revogação num acesso. Por isso o
    `except` devolve `False`.

    Um `user` sem perfil **não** é revogação — é um registo órfão, e esses
    já respondem "sem dado" nas views. Devolve `True` para não mudar o
    comportamento de quem nunca teve perfil.
    """
    if user is None:
        return False
    if not getattr(user, "is_authenticated", False):
        return True  # anonimo: nao ha servidor a revogar
    try:
        perfil = getattr(user, "perfil", None)
        if perfil is None:
            return True  # registo orfao, nao revogacao
        return bool(perfil.ativo_servidor)
    except Exception as exc:  # noqa: BLE001 — e' exactamente o caso que quero apanhar
        logger.error(
            "nao foi possivel ler PerfilUsuario.ativo_servidor (%s: %s). "
            "Assume-se REVOGADO: um guarda que devolve `True` quando nao sabe "
            "transforma uma revogacao num acesso.",
            type(exc).__name__,
            exc,
        )
        return False


def exigir_servidor_ativo(user) -> None:
    """Levanta `PermissionDenied` se `user` estiver revogado. Não faz nada se não."""
    if not servidor_ativo(user):
        from django.core.exceptions import PermissionDenied

        raise PermissionDenied(MENSAGEM)
