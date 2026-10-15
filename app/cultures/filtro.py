"""Que culturas este produtor vê nas guias, nos widgets e na IA.

A REGRA, E PORQUÊ TEM TRÊS ESTADOS
----------------------------------
O cadastro (`app/api/views/user.py::onboarding_save`) passou a gravar as
culturas que o produtor marca. Esta módulo decide o que essa escolha filtra —
e o detalhe que decide tudo é que "sem culturas" quer dizer duas coisas
diferentes:

  ``None``  — o produtor NUNCA passou pelo seletor. A conta é anterior ao
              cadastro com multi-seleção, ou está a ser criada por API/import.
              Não filtra: mostra o catálogo inteiro, como sempre.

  ``set()`` — o produtor passou pelo seletor e não marcou nada. Escolha
              explícita de "não é uma exploração de plantas". Filtra para
              zero: é o que ele pediu.

  ``{ids}`` — escolheu. Filtra para o que ele marcou.

COLLAPSE-DO-ISSO é o ponto em que a maioria das implementações parte. Sem o
estado `None`, o filtro "mostra só o que foi escolhido" esvazia a guia de
toda a gente que já tinha conta — e isso não é uma feature, é uma regressão
em que 100% dos utilizadores existentes perdem o produto em silêncio. Sem o
estado `set()`, "não marquei nada" é indistinguível de "ainda não me
perguntaram", e quem escolheu não ver guias continua a vê-las.

Esta distinção é lida do DATO (existe algum vínculo em `Propriedade.culturas`?
existe?) e não de uma flag nova. Uma flag nova seria outro estado para
manter, e o dia que alguém a Fill-in sem querer o produto volta a esvaziar
sozinho.

O QUE ESTE MÓDULO NÃO FAZ
-------------------------
Não esconde a cultura do CATÁLOGO. `Cultura` é a tabela global partilhada,
usada por safras, talhões, registos e pela API; filtrá-la por produtor seria
um bug de tenancy, não uma feature. O que se filtra é o que o produtor VÊ:
cartões de guia, widgets do painel, e perguntas da IA.
"""

from app.models import Cultura, Propriedade

#: Animal e aquicultura. `perenes` fica de fora de propósito: no catálogo é a
#: fazenda de café perene, que é vegetal mesmo sendo `perenes` um grupo
#: ambíguo — e um widget vegetal a desaparecer para quem produz café seria
#: pior do que o inverso.
GRUPOS_NAO_VEGETAIS = frozenset(
    {
        # de app/views/guias.py::ANIMAL_GRUPOS
        "bovinos",
        "suinos",
        "ovinos",
        "equinos",
        "bufalos",
        "aves",
        "leite",
        "ovos",
        # de app/views/guias.py::AQUATICA_GRUPOS
        "peixes",
        "crustaceos",
        "infraestrutura",
    }
)

# `perenes` NÃO está aqui, apesar de o nome sugerir "raça". MEDIDO 13/10/2026:
# `Cultura.objects.filter(grupo="perenes")` devolve UMA linha — `Cafe`. Café é
# vegetal. Tê-lo em `NAO_VEGETAIS` esconderia NDVI e rastreabilidade de
# defensivos a quem produz café, e eu tinha-o posto aqui por suposição — o
# teste `GruposConcordamComAsGuias::test_a_divisao_vegetal_animal_e_a_mesma`
# é que apanhou, comparando com a lista de `guias.py`, que nunca o teve.


#: Tudo o resto de `Cultura.GRUPOS` é vegetal. Derivado, não escrito à mão: uma
#: lista de nomes de grupo repetida num segundo sítio diverge no primeiro dia em
#: que alguém acrescenta uma cultura nova.
#:
#: A concordância com `app/views/guias.py::NAO_VEGETAL_GRUPOS` — que é quem
#: realmente decide o que é animal e o que é aquático — é verificada por
#: `tests/test_filtro_culturas_guias.py::GruposConcordamComAsGuias`. Esse teste
#: é o que impede as duas listas de se separarem; sem ele, "vegetal" aqui e
#: "vegetal" lá são duas definições com o mesmo nome.
GRUPOS_VEGETAIS = frozenset(
    g for g, _ in Cultura.GRUPOS if g not in GRUPOS_NAO_VEGETAIS
)

#: Aquicultura. Separate de "animal" porque as perguntas são diferentes:
#: "mormaço da tilápia" não é uma pergunta de gado, e "quanto leite produzi"
#: não é uma pergunta de peixe. Uma categoria "tudo que não é vegetal" era o
#: que o `NAO_VEGETAL_GRUPOS` de `guias.py` usa — e está certa PARA AS GUIAS
#: (a guia de animal tem de mostrar os peixes que o produtor tem), mas errada
#: PARA AS PERGUNTAS: oferecer `producao_leite` a quem tem tanque é ruído
#: com aparência de resposta.
#:
#: Por isso existem as três. `GRUPOS_NAO_VEGETAIS` continua a existir e a
#: concordar com `guias.py`; `GRUPOS_ANIMAL` e `GRUPOS_AQUATICA` repartem-no
#: para o que a IA pergunta.
GRUPOS_AQUATICA = frozenset({"peixes", "crustaceos"})

#: Rebanho terrestre. `aves` incluído — ave é animal, e as perguntas de
#: avicultura (bico, balança) são de rebanho tanto como as de gado.
GRUPOS_ANIMAL = frozenset(
    g for g in GRUPOS_NAO_VEGETAIS if g not in GRUPOS_AQUATICA
) - {"infraestrutura"}

#: Aves. Separate de "animal" porque as perguntas de avicultura não fazem
#: sentido a quem tem vaca: "ajustar o bico a 4%" e "2,8 kg por ave" são de
#: granja, e oferecê-las a um pecuarista de corte é ruído com número em cima.
GRUPOS_AVES = frozenset({"aves"})

#: Marca -> grupos de cultura. A ÚNICA tabela que resolve marcas.
#:
#: Uma função com um `if marca == "vegetal" / elif "animal"` duplicada em
#: `paginas.py` e em `capacidades.py` é duas tabelas com o mesmo nome — e é
#: assim que uma marca passa a ser reconhecida num sítio e ignorada no outro,
#: sem erro nenhum: o widget aparece e a pergunta não, ou ao contrário.
#:
#: Não há `if` para marcas desconhecidas: `grupos_da_marca` devolve `None`, e
#: `None` é "não filtra" (ver `widget_aplicavel`). A falha é ABERTA de propósito.
#: Um `aplica_a` com letra errada esconde a pergunta de toda a gente e ninguém
#: dá por isso — o produto fica mais pobre e o bug é invisível. Com falha
#: aberta, o erro mostra a pergunta a toda a gente, alguém pergunta "porque é
#: que estou a ver isto?" e está arrumado no dia.
_MARCAS = {
    "vegetal": GRUPOS_VEGETAIS,
    "animal": GRUPOS_ANIMAL,
    "aquatica": GRUPOS_AQUATICA,
    "aves": GRUPOS_AVES,
}


def grupos_da_marca(marca):
    """Os grupos a que a marca se aplica. `None` = não filtra.

    `None` para marca ausente (widget/intent de fazenda) E para marca que
    ninguém conhece. Ver a nota acima: falha aberta é deliberada.
    """
    if not marca:
        return None
    return _MARCAS.get(marca)


def widget_aplicavel(grupos_usuario, grupos_widget):
    """Este produtor vê isto?

    `grupos_widget` vem de `grupos_da_marca`; `None` significa "serve a
    qualquer cultura" (ou "marca que ninguém conhece", que também não
    filtra — ver `grupos_da_marca`).
    """
    if grupos_widget is None:
        return True
    if grupos_usuario is None:
        return True  # nunca perguntado: mostra tudo
    return bool(grupos_usuario & grupos_widget)


def grupos_escolhidos(user):
    """`grupo` das culturas que este produtor escolheu, ou `None` se não escolheu.

    Devolve `None` — não o conjunto vazio — pelo mesmo motivo de
    `ids_escolhidos`: quem nunca foi perguntado não filtra, e quem respondeu
    "nenhuma" filtra para zero grupos.

    Um produtor que escolheu Soja e Tilápia devolve `{"graos", "peixes"}` — é
    o que permite a um widget dizer "só me interessa a quem planta OU tem
    peixe", sem ele saber que a pergunta existe.
    """
    ids = ids_escolhidos(user)
    if ids is None:
        return None
    return frozenset(Cultura.objects.filter(id__in=ids).values_list("grupo", flat=True))


def ids_escolhidos(user):
    """Ids de `Cultura` que este produtor escolheu.

    Devolve ``None`` quando nunca escolheu (não filtra) e um `set` — que pode
    ser vazio — quando escolheu.

    A consulta é em duas partes e as DUAS são necessárias. Ler só os vínculos
    não chega, e é o erro que este módulo já Cometia uma vez (MEDIDO
    13/10/2026, apanhado por `test_escolheu_e_esvaziou_nao_e_none`):

    - Os vínculos dizem **o que** foi escolhido. Vazio = nada escolhido.
    - `culturas_escolhidas_em` diz **se foi perguntado**. `null` = nunca
      perguntado.

    Só com os vínculos, quem marca duas culturas e depois as apaga fica com
    zero linhas — exactamente o mesmo dado que a conta que nunca viu o
    seletor. E as duas têm de se comportar ao contrário: a segunda não pode
    filtrar (esvaziar a guia de toda a gente que já tinha conta), a primeira
    tem de esvaziar. Um `set()` devolvido a partir de "não há vínculos"
    tratava as duas como a mesma e apagava o produto de 100% dos utilizadores
    existentes sem um único erro no log.

    E é pela relação invertida, e não por propriedade a propriedade, porque o
    que interessa é "este produtor já passou pelo seletor em ALGUMA
    propriedade". Um produtor com duas fazendas, uma configurada e outra não,
    tem escolha feita: filtra-se para o que/configurou. Filtrar por
    propriedade daria duas respostas diferentes para o mesmo utilizador
    conforme a fazenda aberta, e a lista de guias não distingue as duas.
    """
    if user is None or not getattr(user, "is_authenticated", False):
        return None

    perguntado = Propriedade.objects.filter(
        user=user, culturas_escolhidas_em__isnull=False
    ).exists()
    if not perguntado:
        return None

    return set(
        Cultura.objects.filter(propriedades__user=user).values_list("id", flat=True)
    )


def visiveis(user):
    """QuerySet de `Cultura` que este produtor vê nas guias."""
    ids = ids_escolhidos(user)
    if ids is None:
        return Cultura.objects.all()
    return Cultura.objects.filter(id__in=ids)


def escolheu(user):
    """`True` só quando o produtor passou pelo seletor.

    Para o que precisa de saber se o filtro está activo (uma nota "só mostramos
    o que você cultiva", uma rota de "adicionar cultura"), e não se está a ver
    alguma cultura.
    """
    return ids_escolhidos(user) is not None
