"""Resolução de propriedade com escopo de tenant — UM caminho só.

O QUE ESTE MÓDULO É
-------------------
`resolver(user, params)` é a resposta única à pergunta "de qual fazenda o
produtor está a falar?". Todo handler de intent passa por aqui.

POR QUE ELE EXISTE
------------------
Havia três cópias byte-a-byte desta função, uma por ficheiro:

    app/ia/intents.py   -> `_prop(user, params)`
    app/ia/intents2.py  -> `_prop2(user, params)`
    app/ia/intents3.py  -> `_prop3(user, params)`

Os nomes diferentes (`_prop`, `_prop2`, `_prop3`) diziam "três coisas
diferentes", e é exactamente esse o defeito: são a MESMA regra, e a regra é de
segurança. O filtro `user=user` é o que impede um produtor de ler a fazenda
de outro. Um handler corrigido e dois por corrigir é isolamento de tenant por
sorte — e o teste que passa no handler corrigido dá confiança falsa sobre os
outros dois.

Pior: as cópias já divergiam. `_prop` fazia `params.get(...)` direto e rebentava
com `AttributeError` quando `params` era `None`; `_prop2`/`_prop3` usavam
`(params or {})`. Um `None` é um `params` legitimo — o sandbox chama handlers
sem argumentos opcionais — e o comportamento dependia do ficheiro onde o
handler por acaso vivia.

A REGRA (inalterada, só que agora num sítio só)
-----------------------------------------------
1. `propriedade_id` wins, mas só dentro das propriedades do utilizador. Um id
   de outra conta devolve `None`, nunca a linha alheia.
2. `propriedade` (nome) é procurado por `icontains` dentro do mesmo filtro.
3. Sem nenhum dos dois: a primeira propriedade do utilizador.
4. `None` em vez de excepção quando `params` é `None`.
"""

from __future__ import annotations

from typing import Any


def resolver(user: Any, params: dict | None = None) -> Any:
    """Propriedade de `user` segundo `params`, ou a primeira dele.

    Devolve `None` quando o utilizador não tem propriedade, ou quando pediu
    uma que não é dele. `None` é uma resposta válida: o handler decide se
    pergunta ("cadastre uma propriedade") ou se recusa.

    REVOGAÇÃO — por que esta função é um ponto de verificação
    -------------------------------------------------------
    Este é O resolver de tenancy da IA: tudo o que a IA toca para saber de que
    fazenda fala passa por aqui. E, ao contrário do middleware, isto **não
    depende de haver um `request`**: um task do Celery e uma management command
    chamam esta função exactamente como uma view, e ambos ficavam de fora
    quando a revogação só existia em `app/middleware.py`.

    Ver `app/services/revogacao.py` para a regra e para o que esta chamada
    NÃO substitui.
    """
    from app.models import Propriedade
    from app.services.revogacao import exigir_servidor_ativo

    exigir_servidor_ativo(user)

    params = params or {}
    qs = Propriedade.objects.filter(user=user)

    pid = params.get("propriedade_id")
    if pid:
        # O `user=user` continua no filtro: um id válido de outra conta
        # simplesmente não casa, e o `.first()` devolve None.
        return qs.filter(id=pid).first()

    nome = (params.get("propriedade") or "").strip()
    if nome:
        return qs.filter(nome__icontains=nome).first()

    return qs.first()
