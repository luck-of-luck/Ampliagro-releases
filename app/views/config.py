import json

from django import forms
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from app.cultures.seletor import opcoes_para_seletor
from app.hierarquia import hierarquia_required
from app.models import *

from .utils import *


@login_required
def perfil_config_view(request):
    propriedades = list(Propriedade.objects.filter(user=request.user))
    return render(
        request,
        "perfil-config.html",
        {
            "propriedades": propriedades,
            # A lista agrupada para o multiselect. Mesmo formato e mesma
            # função que o onboarding (`app.cultures.seletor`), de propósito:
            # duas listas de culturas em dois ecrãs divergem no primeiro dia em
            # que alguém acrescenta uma cultura nova, e o produtor vê uma
            # coisa no cadastro e outra nas configurações.
            "culturas": opcoes_para_seletor(),
            # Só `id` e `nome`: o `<select>` das fazendas não precisa de
            # `area_total` nem de `geometria`, e mandar a geometria de cada
            # propriedade para dentro de um `<script>` é um payload que
            # ninguém pediu.
            "propriedades_simples": [
                {"id": p.id, "nome": p.nome} for p in propriedades
            ],
        },
    )


@login_required
def config_dia_view(request):
    return render(
        request,
        "config-dia.html",
        {"propriedades": Propriedade.objects.filter(user=request.user)},
    )


@login_required
def config_noturno_view(request):
    return render(
        request,
        "config-noturno.html",
        {"propriedades": Propriedade.objects.filter(user=request.user)},
    )


@login_required
def config_sistema_view(request):
    return render(
        request,
        "config-sistema.html",
        {"propriedades": Propriedade.objects.filter(user=request.user)},
    )


@login_required
def config_page_view(request):
    propriedades = Propriedade.objects.filter(user=request.user)
    return render(request, "config_page.html", {"propriedades": propriedades})


@login_required
def erro_report_view(request):
    return render(request, "erro-report.html")


# ── culturas da propriedade ────────────────────────────────────────────────
# O ecrã que fecha o círculo do cadastro. A página de onboarding diz "dá para
# mudar depois nas configurações" — e até agora era uma promessa sem ecrã. Um
# produtor que errou o grupo na entrada ficava preso à escolha, que é a única
# coisa que decide o que ele vê em todo o produto.
#
# Porquê UM endpoint e não o `/api/onboarding/save/`:
#  - o onboarding cria a propriedade; aqui a propriedade já existe. Salvar
#    nela de novo abriria um segundo `Propriedade`.
#  - a escolha é POR propriedade. O filtro (`app/cultures/filtro.py`) agrega
#    todas as do produtor, mas o produtor raciocina por fazenda — "na minha
#    fazenda do cerrado é só soja, aqui é soja e gado".


def _propriedade_do_productor(request, pk):
    """A propriedade `pk`, SE for do produtor. `None` se não for.

    `get_object_or_404` sobre `Propriedade.objects.filter(user=request.user)`.
    O filtro de dono é a fronteira: buscar por `pk` a secas devolveria a
    propriedade de outro produtor, e `culturas.set()` nela é uma escrita
    cross-tenant com resposta 200 — o pior resultado possível, porque parece
    que funcionou.
    """
    from django.shortcuts import get_object_or_404

    return get_object_or_404(Propriedade, pk=pk, user=request.user)


@login_required
def culturas_propriedade_api(request, pk):
    """Lê e grava as culturas escolhidas de uma propriedade.

    GET  -> `{propriedade, ids, n_marcadas, perguntada}` — o estado actual.
    POST -> aceita `{culturas: [id, ...]}` e substitui a escolha.

    O POST substitui em vez de acrescentar. Acrescentar tornava impossível
    DESMARCAR, e o produtor que marcou uma cultura por engano ficaria com ela
    para sempre: a interface tem de oferecer a mesma operação que o cadastro.
    """
    propriedade = _propriedade_do_productor(request, pk)

    if request.method == "POST":
        from app.cultures.seletor import ids_validos

        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"ok": False, "erro": "JSON inválido"}, status=400)

        # A fronteira de confiança: mesmo `ids_validos` do cadastro. O que não
        # passar é ignorado, e o que passar é gravado — o que o produtor vê
        # depois é exactamente o que guardou.
        escolhidas = ids_validos(data.get("culturas"))
        propriedade.culturas.set(escolhidas)

        # A marca é reescrita SEMPRE que o POST chega com a chave. Editar a
        # lista depois de responder "nenhuma" tem de continuar a ser uma
        # resposta — senão limpar voltava a ser indistinguível de nunca ter
        # passado pelo seletor, que é o bug que a coluna `culturas_escolhidas_em`
        # existe para impedir.
        propriedade.culturas_escolhidas_em = timezone.now()
        propriedade.save(update_fields=["culturas_escolhidas_em"])

        return JsonResponse(
            {
                "ok": True,
                "ids": escolhidas,
                "n_marcadas": len(escolhidas),
            }
        )

    marcadas = list(propriedade.culturas.values_list("id", flat=True))
    return JsonResponse(
        {
            "propriedade": propriedade.nome,
            "propriedade_id": propriedade.id,
            "ids": marcadas,
            "n_marcadas": len(marcadas),
            "perguntada": propriedade.culturas_escolhidas_em is not None,
        }
    )
