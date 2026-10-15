"""Opções de cultura para o multiselect do cadastro da propriedade.

POR QUE ESTE FICHEIRO EXISTE
-----------------------------
O produtor tem de escolher, no cadastro, **quais culturas produz**. Essa
escolha é o que passa a decidir o que o sistema lhe mostra: guias, widgets e
perguntas de IA das culturas que ele não produz não têm porque aparecer.

O problema: `Cultura` tem 709 linhas (MEDIDO no repositório, ver
`app/api/views/cultures.py:60` — `PaginaCultura`), e são o catálogo PARTILHADO
de todos os produtores. Duas consequências, e ambasmeasured:

1. **709 caixas de selecção são ilegíveis.** Ninguém varre 21 grupos para
   achar "Soja". Por isso a lista vem agrupada por `grupo` (os 21 que o
   próprio modelo declara em `Cultura.GRUPOS`), com cada grupo dobrado, e o
   filtro acontece no browser.

2. **709 linhas em HTML é peso desnecessário.** A lista é entregue UMA vez
   em `json_script` e filtrada no cliente. Não há endpoint novo, não há
   pedido por tecla, e funciona offline — que é o que o CSP do desktop
   exige (`config/settings/desktop.py`). Um `fetch` por tecla seria mais
   simples de escrever e seria uma dependência de rede que o produto não
   deve ter.

O QUE ESTE MÓDULO NÃO FAZ
-------------------------
Não inventa uma lista curada. Uma shortlist escrita à mão ("as 15 mais
comuns") envelhece no dia em que alguém mexe no catálogo, e o produtor de
uma cultura que ficou de fora não tem onde a escolher. A lista vem da
tabela: o que `Cultura` tem, o produtor vê.
"""

from app.models import Cultura

#: Rótulos legíveis de `grupo`. Vem do próprio modelo — uma segunda lista de
#: nomes aqui divergiria da que o admin vê no `Cultura` do Django admin.
_ROTULOS = dict(Cultura.GRUPOS)

#: Colunas que o seletor precisa. `Cultura` tem uma janela de plantio, uma
#: chave de mercado, um código IBGE e um `agrodoc`; nada disso é usado para
#: desenhar uma caixa de selecção. Trazer colunas que não se usam é como o
#: queryset passa a ser lento sem que ninguém perceba porquê.
_COLUNAS = ("id", "nome", "grupo")

#: Tecto de ids aceites num pedido. Não é uma regra de negócio: é o porto
#: antes do `id__in`. Sem isto, um `culturas` com 100 000 entradas vira uma
#: query enorme a partir de um campo que o produtor não devia conseguir
#: escrever à mão.
MAXIMO_CULTURAS = 200


def opcoes_para_seletor():
    """Lista agrupada para o multiselect, pronta para `json_script`.

    Devolve `[{grupo, rotulo, total, culturas: [{id, nome}]}, ...]`, ordenada
    por rótulo para o produtor encontrar pelo nome do grupo e não pelo
    valor interno.

    Só entram culturas `ativo=True`: uma cultura desativada sumiu do produto
    e continua a aparecer no selector seria o produtor a escolher um
    caminho que já não abre. Este filtro é o que `app/tests_onboarding.py`
    passa a verificar.
    """
    linhas = Cultura.objects.filter(ativo=True).only(*_COLUNAS).order_by("nome")

    grupos = {}
    for cultura in linhas:
        grupos.setdefault(cultura.grupo, []).append(
            {"id": cultura.id, "nome": cultura.nome}
        )

    opcoes = [
        {
            "grupo": grupo,
            "rotulo": _ROTULOS.get(grupo, grupo),
            "total": len(culturas),
            "culturas": culturas,
        }
        for grupo, culturas in grupos.items()
    ]
    opcoes.sort(key=lambda g: (g["rotulo"].casefold(), g["grupo"]))
    return opcoes


def ids_validos(ids_recebidos):
    """Ids de cultura que existem, estão activos, e cabem no tecto.

    `ids_recebidos` chega de um POST — é entrada de rede e vale tudo o que a
    validação deixar passar. Três filtragens, nesta ordem:

      1. lista de tamanho razoável (o teto de `MAXIMO_CULTURAS`);
      2. cada item coerente para `int` — o payload é JSON arbitrário;
      3. `id__in` + `ativo=True` — o que sai daqui é sempre uma cultura que
         existe na tabela.

    Devolve uma `list` de `int` sem repetidos, pela ordem de chegada.
    """
    if not isinstance(ids_recebidos, list):
        return []

    vistos, validos = set(), []
    for bruto in ids_recebidos[:MAXIMO_CULTURAS]:
        try:
            id_cultura = int(bruto)
        except (TypeError, ValueError):
            continue
        if id_cultura in vistos:
            continue
        vistos.add(id_cultura)
        validos.append(id_cultura)

    if not validos:
        return []

    existentes = set(
        Cultura.objects.filter(id__in=validos, ativo=True).values_list("id", flat=True)
    )
    return [i for i in validos if i in existentes]
