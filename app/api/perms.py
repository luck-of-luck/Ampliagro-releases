"""Permissões que não pertencem a um modelo.

Porquê um ficheiro próprio: `IsOwnerPropriedade` (em `app/iot/viewsets.py`)
resolve o caso normal — o objecto tem `propriedade`, e a propriedade tem
`user`. O `Cultura` não tem dono nenhum, e por isso essa regra não se lhe
aplica: não há `obj.propriedade` para comparar.

O QUE ESTE CATÁLOGO É
=====================
`Cultura` é a tabela de referência partilhada: janela de plantio, ciclo em
dias, código IBGE SIDRA, unidade comercial. São ~700 linhas, semeadas, e
**todos os produtores partilham as mesmas linhas**. As janelas e o ciclo
alimentam o calendário de plantio, o VRA e o ZARC — ou seja, umarecommendação
agronómica que aparece no ecrã de cada um.

O PROBLEMA
==========
`CulturaViewSet` é um `ModelViewSet` — CRUD completo — com
`permission_classes = [IsAuthenticated]`. Isto é, qualquer produtor
autenticado pode, contra um catálogo que é de toda a gente:

* `PATCH /api/culturas/57/` e mudar `janela_plantio_inicio`,
    `janela_plantio_fim` ou `ciclo_dias` — e a partir desse momento todos
    os outros produtores recebem uma recomendação de plantio errada, sem
    qualquer aviso e sem vestígio de quem mudou;
  * `PATCH` e pôr `ativo=False` — e a cultura desaparece dos ecrãs de toda
    a gente;
  * `DELETE` — aqui o `on_delete=models.PROTECT` nas FKs (`safra.py:51`,
    `producao.py:182`, `producao.py:386`) recusa, e há
    `tests_cascata_cultura.py` a guardar isso. Apagar uma cultura que
    ninguém usa, passa.

Não é exfiltração de dados: é integridade de dados partilhados. E é
silencioso, que é a pior propriedade que um bug pode ter.

O QUE ESTA PERMISSÃO FAZ, E O QUE NÃO FAZ
=========================================
Não proíbe ADD (`POST`). A página de cadastro de cultura
(`cadastro-cultura.html:243`) faz `POST /api/culturas/` e é
`@login_required` sem gate de staff — adicionar cultura é função de produto,
e tira-lha seria partir o produto sem necessidade.

O que fica staff-only é **alterar e apagar** o que já existe e é partilhado.
Criar uma linha nova estraga o sprawl de um produtor; mudar a janela de
plantio de "Soja" estraga a de todos.

Isto não substitui um `Cultura` com dono. Um dia o catálogo deve ser
por-instalação ou por-produtor, e este ficheiro deixa de ser necessário.
Até lá, é o buraco mais pequeno que não parte o produto.
"""

from rest_framework import permissions


class LeituraGlobalEscritaStaff(permissions.BasePermission):
    """Leitura e criação abertas a autenticados; alteração e apagamento só a staff.

            Pensado para tabelas de referência sem dono — hoje só `Cultura`.

    A linha a defender é `has_permission` e não `has_object_permission`:
        numa tabela sem dono não há objecto cujo dono se verifique, e o filtro
        de queryset não ajuda porque o queryset É a tabela toda.
    """

    message = (
        "O catálogo de culturas é partilhado por todos os produtores. "
        "Criar é permitido; alterar ou apagar dados que outros usam é "
        "reservado a administração."
    )

    #: Métodos que não mudam nada que já existia.
    _METODOS_SEGUROS = frozenset({"GET", "HEAD", "OPTIONS"})

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        if not (user and user.is_authenticated):
            return False
        if request.method in self._METODOS_SEGUROS:
            return True
        if request.method == "POST":
            # Acrescentar uma cultura é trabalho do produtor, não dano
            # colateral para os outros.
            return True
        # PUT / PATCH / DELETE mexem em linhas que os outros usam.
        return bool(user.is_staff)

    def has_object_permission(self, request, view, obj):
        # `has_permission` já decidiu. Este método existe porque o DRF chama
        # os dois, e um `return True` aqui seria uma porta aberta caso
        # alguém acrescente um `get_object` a um caminho não coberto.
        return self.has_permission(request, view)
