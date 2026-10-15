"""Gravar a mesa da IA num preset DO PRODUTOR. Fase 2.

O QUE ISTO FAZ, E POR QUE NAO E' UM `PalcoIA`
==============================================
Um desenho anterior desta fase gravava a composicao em `PalcoIA.objects.first()`.
**Isso poria a mesa do produtor A no preset do produtor B.** `PalcoIA`
(`app/models/palco.py:62-73`) nao tem `user`: e' um singleton por instalacao, com
`slug` UNIQUE e `CheckConstraint(kind="palco")`. A propria docstring diz por que
motivo a `structure` fica vazia:

    *"Um palco com widgets guardados seria a mesma mesa para toda a gente, e o
    produtor A veria a analise do produtor B assim que abrisse o dashboard."*

Por isso isto grava em `PresetPalco`, que ja' tem `user`, `UniqueConstraint(user, slug)` e
`do_produtore()`. **Nao precisa de migration nova** — e nao ha segunda verdade.

A EXCEPCAO, E ONDE ELA ESTA
===========================
`PresetPalco` estava fechado a escrita da IA por desenho — e com razao
(`models/palco.py:279`): *"a garantia passaria a depender de uma comparacao de
string feita no caminho certo"*. A excepcao que o produtor pediu nao anula isso:
move a decisao para `chamado.pode_escrever`, que ja' existia para a pergunta
*"a IA pode mexer nisto?"*, e fecha a excepcao em `confirm` — a resposta do
produtor, nao um parametro que o modelo preencha. Ver `chamado.py` e
`intents_palco_preset.h_preset_palco`, que e' quem chama a guarda.

O PRODUTOR TEM DIREITO A RECUSAR
=================================
Um preset e' trabalho do produtor: ele renomeou, organizou, apagou o que nao
serve. Uma IA que escreve neles sem perguntar reescreve o trabalho de quem os
organiza. `chamado.py` diz a mesma coisa para o Chamado e a mesma regra
aplica-se aqui.

Por isso `planear` e' separado de `gravar`. E `confirmado=False` nao e' um erro:
e' a RESPOSTA. O que o produtor tem de ver e' o que vai acontecer, antes de
acontecer. E um "nao" tem de ser tão respeitado quanto um "sim" — por isso o
servico nao escreve nada e devolve o que teria escrito.

O QUE NAO ENTRA
================
- Nao cria widgets. O catalogo e' `palco.CATALOGO_IA` e a fronteira continua a
  ser `palco.validar_estrutura`, que descarta o que nao conhece.
- Nao inventa numero. A `widget_composicao` so NOMEIA widgets; os valores vem do
  `dados` do intent, que ja' passou por handlers com tenancy.
- Nao toca em preset de outro. Toda a leitura e escrita e' `do_produtore(user)`.
"""

from __future__ import annotations

from typing import Any

from app.ia import palco
from app.models.palco import PresetPalco

#: O que a IA pode pedir. Deliberadamente curto, e SO' o que o codigo faz.
#:
#: `adicionar`, `remover` e `reordenar` NAO estao aqui porque nao sao codigo
#: distincto: a IA manda a lista nova inteira e o preset fica com ela. E
#: prometer um parametro que nao muda nada e' a forma mais barata de mentir —
#: o produtor pede "addiciona o KPI de caixa", a tela muda, e nao ha forma de
#: perceber que o nome da operacao nunca entrou em conta.
OPERACOES = ("criar", "atualizar")

#: Teto de presets por produtor. Um produtor com 200 dashboards nao tem um
#: dashboard, tem uma pasta. E o menu do dashboard e' uma tira de opcoes
#: (`widget-presets.js`): a partir de um numero, o proprio menu deixa de servir.
MAX_PRESETS_POR_PRODUTOR = 60


def _slug_livre(user, nome: str) -> str:
    """O `custom-` deste preset, livre dentro do produtor.

    Mesma regra de `amplia_palco._slug_livre`: nome repetido actualiza o que ja
    existe, e so para nome NOVO se procura um slug livre. E a unicidade e' por
    produtor, porque dois produtores PODEM chamar "custom-custo" as suas mesas.

    Duplicada e' nao a mesma funcao: a de `amplia_palco.py` e' uma view que
    depende de `request`. Extrair para um modulo partilhado seria o refactor
    certo, e toca numa view que outra sessao pode estar a ler. A regra esta
    escrita duas vezes porque e' curta; se mudar, muda nas duas.
    """
    from django.utils.text import slugify

    ja_existe = PresetPalco.objects.do_produtore(user).filter(nome=nome).first()
    if ja_existe:
        return ja_existe.slug

    base = slugify(nome)[:40].strip("-") or "mesa"
    candidato = f"custom-{base}"
    n = 2
    while (
        PresetPalco.objects.do_produtore(user).filter(slug=candidato).exists()
        and n <= 50
    ):
        candidato = f"custom-{base}-{n}"
        n += 1
    return candidato


def listar(user) -> list[PresetPalco]:
    """Os presets deste produtor, e so deste.

    `do_produtore` nao e' convencao: e' o unico caminho de leitura
    (`PalcoQuerySet`). Um `.filter(user=user)` esquecido aqui e' um vazamento de
    dashboards de um produtor para o vizinho.
    """
    return list(
        PresetPalco.objects.do_produtore(user)
        .select_related("origem")
        .order_by("-fixado", "-criado_em")
    )


def planear(
    user,
    nome: str,
    composicao: Any,
    *,
    operacao: str = "criar",
    layout: str = "",
    fixado: bool = False,
) -> dict[str, Any]:
    """O que a IA PROPOE gravar, sem gravar. E o que a confirmacao mostra.

    Separar o "planear" do "gravar" e' o que permite ao produtor recusar sem
        executar. Um handler que calcula e grava no mesmo folego, com a confirmacao
        depois, tem de desfazer o que ja' fez — e desfazer escrita e' o caminho
        mais curto para apagar a mesa de outra pessoa.
    """
    if user is None or not getattr(user, "is_authenticated", False):
        return {"ok": False, "erro": "utilizador obrigatorio"}

    operacao = str(operacao or "criar").strip().lower()
    if operacao not in OPERACOES:
        return {
            "ok": False,
            "erro": f"operacao desconhecida: {operacao!r}. Use: {', '.join(OPERACOES)}",
        }

    nome = str(nome or "").strip()[:80]
    if not nome:
        return {"ok": False, "erro": "da um nome a mesa (ex: 'Custo por talhao')"}

    widgets, descartados = palco.validar_estrutura(composicao)
    if not widgets:
        return {
            "ok": False,
            "erro": (
                "nenhum widget reconhecido. Os ids do catalogo estao em "
                "`amplia://widgets`; os mais usados: "
                + ", ".join(sorted(palco.CATALOGO_IA)[:6])
            ),
        }

    alvo = PresetPalco.objects.do_produtore(user).filter(nome=nome).first()
    existentes = PresetPalco.objects.do_produtore(user).count()
    # O slug resolve-SE AQUI, uma vez, e `gravar` usa este mesmo valor. Antes
    # cada um calculava o seu, e a guarda nao podia ser chamada com um slug que
    # ainda nao existia — que e' como uma escrita passa a depender de "o slug
    # certo, no caminho certo".
    slug = alvo.slug if alvo is not None else _slug_livre(user, nome)

    return {
        "ok": True,
        # O QUE VAI ACONTECER, e nao o que foi pedido. A IA pode pedir "criar"
        # sobre um nome que ja' existe — e o certo e' actualizar, porque e' o
        # mesmo pedido duas vezes (a regra de `palco_clonar`). Devolver "criar"
        # aqui era mentir sobre o resultado: o plano dizia "criar" e a base de
        # dados dizia "actualizado".
        "operacao": "atualizar" if alvo is not None else "criar",
        "destino": alvo.slug if alvo is not None else None,
        "slug": slug,
        "nome": nome,
        "widgets": widgets,
        "layout": palco.normalizar_layout(layout) if layout else "grid-mixed",
        "fixado": bool(fixado),
        "descartados": descartados,
        "total_presets": existentes,
        "atinge_teto": existentes >= MAX_PRESETS_POR_PRODUTOR and alvo is None,
    }


def gravar(user, plano: dict[str, Any]) -> dict[str, Any]:
    """Grava o que `planear` devolveu. **So depois de `confirmado`.**

    Recebe o plano e nao os argumentos, para que nao haja caminho que grave sem
    ter passado pela validacao. `palco_clonar` (a view) faz a mesma coisa com
    `request.data`, e tambem valida antes.
    """
    if not plano.get("ok"):
        return {"ok": False, "erro": plano.get("erro", "plano invalido")}

    widgets = plano.get("widgets") or []
    if not widgets:
        return {"ok": False, "erro": "plano sem widgets"}

    nome = str(plano["nome"])
    estrutura = {
        "widgets": widgets,
        "layout": plano.get("layout") or "grid-mixed",
        "origem_palco": palco.SLUG_PALCO,
        "escrito_por_ia": True,
    }

    if plano.get("atinge_teto"):
        return {
            "ok": False,
            "erro": (
                f"ja tens {plano['total_presets']} dashboards. Apaga um antes de "
                "criar outro — um produtor com 60 mesas nao tem um dashboard."
            ),
        }

    preset, criado = PresetPalco.objects.get_or_create(
        user=user,
        slug=plano.get("slug") or plano.get("destino") or _slug_livre(user, nome),
        defaults={
            "nome": nome,
            "estrutura": estrutura,
            "fixado": bool(plano.get("fixado")),
        },
    )
    if not criado:
        preset.nome = nome
        preset.estrutura = estrutura
        # `fixado` entra na lista. Ficou de fora numa versao anterior, e o
        # efeito era um pedido de "fixa esta mesa" ser ignorado em silencio
        # sempre que a mesa ja' existia — que e' precisamente o caso em que o
        # produtor repara, porque e' o menu que ele esta a olhar.
        preset.fixado = bool(plano.get("fixado"))
        preset.save(update_fields=["nome", "estrutura", "fixado"])

    return {
        "ok": True,
        "criado": criado,
        "preset": {
            "slug": preset.slug,
            "nome": preset.nome,
            "fixado": preset.fixado,
            "widgets": len(widgets),
        },
    }


def _por_nome_ou_slug(user, nome_ou_slug):
    """O preset deste produtor por nome ou slug, ou None.

    Nome primeiro (é o que o produtor fala), slug depois (o que o sistema
    guarda). Ambos SEMPRE sob `do_produtore`: um nome igual noutra conta
    nunca aparece aqui.
    """
    alvo = str(nome_ou_slug or "").strip()
    if not alvo:
        return None
    achado = PresetPalco.objects.do_produtore(user).filter(nome__iexact=alvo).first()
    if achado is not None:
        return achado
    return PresetPalco.objects.do_produtore(user).filter(slug=alvo).first()


def remover(user, nome_ou_slug: str) -> dict[str, Any]:
    """Apaga UM preset do produtor. Sem confirmação aqui — ela vive no
    intent (`requires_confirmation` + `pode_escrever`), como em `gravar`.
    Um serviço que apaga sem ter sido autorizado é o defeito que a Fase 2
    existe para impedir.
    """
    alvo = _por_nome_ou_slug(user, nome_ou_slug)
    if alvo is None:
        outros = [str(p.nome) for p in listar(user)[:8]]
        return {
            "ok": False,
            "erro": (
                f"não achei dashboard {str(nome_ou_slug or '').strip()!r}. "
                + (
                    f"Os teus: {', '.join(outros)}."
                    if outros
                    else "Não tens nenhum dashboard guardado."
                )
            ),
        }
    nome, slug = alvo.nome, alvo.slug
    n = len((dict(alvo.estrutura or {})).get("widgets") or [])
    alvo.delete()
    return {"ok": True, "nome": nome, "slug": slug, "widgets": n}
