"""
app/models/financeiro_banco.py — SHIM de compatibilidade.

HISTORICO
---------
Este arquivo era uma COPIA INTEIRA de ``app/models/financeiro.py``: as mesmas
6 classes (ContaBancaria, MovimentacaoBancaria, Parcelamento,
ConciliacaoBancaria, PushSubscription, NotificacaoTemplate), definidas de novo.

Como o Django registra models por (app_label, model_name) e ambas viviam em
``app.models``, qualquer import dos dois modulos juntos estourava:

    RuntimeError: Conflicting 'contabancaria' models in application 'app':
    <class 'app.models.financeiro.ContaBancaria'> and
    <class 'app.models.financeiro_banco.ContaBancaria'>

E isso NAO era theoretical: ``app/views/cadastro.py`` importa
``financeiro_banco.ContaBancaria`` dentro da view, ou seja, a pagina
``/cadastro/financeiro/`` quebrava com HTTP 500 sempre que era acessada.

A copia tambem estava DESATUALIZADA. ``financeiro.py`` e a versao canonica e
ja tinha recebido melhorias que a copia nao tem:
  * ``__str__`` em todas as classes
  * ``MovimentacaoBancaria.hash_unico`` com ``default=uuid4``
  * ``Meta.ordering`` em Parcelamento e ConciliacaoBancaria
  * FK de usuario como string ``"auth.User"`` (evita import eager)
  * ``Parcelamento.status`` com as 4 choices explicitas (VENCIDA inclusa)

O QUE ESTE ARQUIVO FAZ AGORA
----------------------------
Reexporta as classes de ``financeiro.py``. Assim:
  * os 2 importadores existentes (``app/services/lcdpr_export.py`` e
    ``app/views/cadastro.py``) continuam funcionando sem alteracao;
  * existe uma unica definicao de cada model, registrada uma vez;
  * nao ha divergencia possivel entre as duas copias.

Nao ha migration envolvida: a tabela ``app_contabancaria`` sempre pertenceu a
``app.models.financeiro.ContaBancaria`` — a duplicata nunca conseguiu coexistir
com ela, portanto nunca teve tabela propria.
"""

from app.models.financeiro import (  # noqa: F401
    ConciliacaoBancaria,
    ContaBancaria,
    MovimentacaoBancaria,
    NotificacaoTemplate,
    Parcelamento,
    PushSubscription,
)

__all__ = [
    "ContaBancaria",
    "MovimentacaoBancaria",
    "Parcelamento",
    "ConciliacaoBancaria",
    "PushSubscription",
    "NotificacaoTemplate",
]
