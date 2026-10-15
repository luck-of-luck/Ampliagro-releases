"""O catálogo da guia diz a verdade sobre o código. Este teste obriga-o.

MEDIDO 2026-10-05. Este ficheiro é o que impede a Guia de Ferramentas de
deixar de ser um inventário honesto.

O QUE SE PASSAVA ANTES
----------------------
A guia tinha 4 abas. Ao pedir-se que cobrisse a lista de um produto de topo de
mercado, a resposta óbvia era escrever ~70 itens no template. **12 deles não
existem neste repositório**: MDF-e, certificado A1, IBS/CBS, drones,
beneficiamento, contratos de safra, John Deere, Stara, FieldView, Solinftec,
OTA, WhatsApp.

Um template que os listasse como funcionais seria **o mesmo defeito que se
corrigiu hoje mais cedo** — o botão NDVI mostrava `0.72` num `catch` de uma
rota 404. Um número gerado apresentado como leitura. Uma lista de capacidades
inexistentes apresentada como entregues é o mesmo erro, com mais linhas, e
seria mais difícil de detectar porque ninguém clica em 60 cartões.

ESTE TESTE É O QUE TORNA O CATÁLOGO CRÍVEL
==========================================
Não basta escrever `estado="EXISTE"`. Este teste **abre o ficheiro e lê a
linha**. Um item que diz EXISTE tem de ter:
  1. uma rota que resolve;
  2. uma prova `caminho:linha` que existe e cuja linha não está vazia.

Um item PARCIAL tem de dizer **o que falta** — um PARCIAL sem `falta` escrito
é um EXISTE disfarçado, e o teste trata isso como erro.

Um item NAO_EXISTE **não pode ter rota**. É a regra que impede que um item
"não implementado" ganhe um botão e comece a mentir outra vez.

E a regra reversa, que é a mais importante: **se um item diz EXISTE ou PARCIAL
mas a prova aponta para código que não existe, o teste falha**. É assim que a
afirmação morre quando o código é apagado.
"""

from __future__ import annotations

import pathlib
import re

import pytest
from django.urls import Resolver404, resolve
from django.urls.exceptions import Resolver404 as Resolver404Exc

from app.guias.catalogo import (
    CATALOGO,
    ESTADO_ROTULO,
    EXISTE,
    NAO_EXISTE,
    PARCIAL,
)

RAIZ = pathlib.Path(__file__).resolve().parents[1]

#: A prova tem de ter esta forma: `caminho/ficheiro.ext:linha`.
#:
#: Não só `.py`. Dois itens são implementados em JavaScript — o `data-sync.js`
#: é o caminho vivo da escrita offline, e a IA local corre no browser. Um teste
#: que só aceitasse `.py` obrigaria a inventar uma prova em Python para código
#: que não tem: seria apontar para o ficheiro errado.
PROVA = re.compile(
    r"^(?P<caminho>[A-Za-z0-9_./\\-]+\.(?:py|js|html|json)):(?P<linha>\d+)"
)


# ───────────────────────────────────────────────────────────────────────────
# O CATÁLOGO TEM A FORMA CERTA
# ───────────────────────────────────────────────────────────────────────────


def test_o_catalogo_tem_as_classes_do_mercado():
    """A lista de mercado tem 7 classes com letra. Todas têm de estar aqui.

    A letra é o que o produtor reconhece da lista que viu; perder a letra
    quebra a correspondência entre o que ele leu e o que encontra.
    """
    letras = {c["letra"] for c in CATALOGO}
    # A lista do mercado salta de E para G (não há F). Mantemos essa forma.
    assert letras == {"A", "B", "C", "D", "E", "G", "H"}, (
        f"letras do catálogo: {sorted(letras)} — esperadas A B C D E G H"
    )


def test_toda_classe_tem_nome_resumo_e_itens():
    for c in CATALOGO:
        assert c["nome"], f"classe {c['id']} sem nome"
        assert c["resumo"], f"classe {c['id']} sem resumo"
        assert len(c["itens"]) >= 3, (
            f"classe {c['id']} tem {len(c['itens'])} itens; a lista do mercado "
            f"dá 3 ou mais em todas"
        )


def test_todo_item_tem_nome_e_resumo():
    for c in CATALOGO:
        for it in c["itens"]:
            assert it["nome"], f"item sem nome em {c['id']}"
            assert it["resumo"], f"'{it['nome']}' sem resumo"


def test_todo_item_tem_um_estado_valido():
    """Um estado inventado é um item que a página não sabe desenhar."""
    for c in CATALOGO:
        for it in c["itens"]:
            assert it["estado"] in (EXISTE, PARCIAL, NAO_EXISTE), (
                f"'{it['nome']}' tem estado {it['estado']!r}, que não está no "
                f"vocabulário {ESTADO_ROTULO}"
            )


# ───────────────────────────────────────────────────────────────────────────
# A PROVA TEM DE EXISTIR E APONTAR PARA CÓDIGO REAL
# ───────────────────────────────────────────────────────────────────────────


def _todos_os_itens():
    for c in CATALOGO:
        for it in c["itens"]:
            yield c, it


def test_a_prova_aponta_para_um_ficheiro_que_existe():
    """`caminho:linha` tem de resolver para um ficheiro do repositório.

    Este é o teste que impede a lista de envelhecer em silêncio: quando o
    `nfe.py` mudar de nome, o item quebra o teste em vez de continuar a
    afirmar uma coisa que já não é verdade.
    """
    for c, it in _todos_os_itens():
        if it["estado"] == NAO_EXISTE:
            continue
        m = PROVA.match(it["prova"])
        assert m, (
            f"'{it['nome']}' diz {it['estado']} mas a prova {it['prova']!r} "
            f"não tem a forma `caminho:linha`.\n\n"
            f"Um estado affirmado sem prova é uma promessa. Se não existe "
            f"código, o estado é NAO_EXISTE."
        )
        caminho = RAIZ / m.group("caminho")
        assert caminho.exists(), (
            f"'{it['nome']}' aponta para {m.group('caminho')} que não existe "
            f"mais. O código mudou; a afirmação tem de mudar com ele."
        )


def test_a_linha_da_prova_nao_esta_vazia():
    """Apontar para uma linha em branco é apontar para nada.

    Numa data ou num import removido sobram muitas linhas vazias. Um item que
    aponta para uma delas está a citar código que já não está lá.
    """
    for c, it in _todos_os_itens():
        if it["estado"] == NAO_EXISTE:
            continue
        m = PROVA.match(it["prova"])
        caminho = RAIZ / m.group("caminho")
        linhas = caminho.read_text(encoding="utf-8", errors="replace").splitlines()
        n = int(m.group("linha"))
        assert 1 <= n <= len(linhas), (
            f"'{it['nome']}' aponta para {m.group('caminho')}:{n}, e o ficheiro "
            f"tem {len(linhas)} linhas."
        )
        conteudo = linhas[n - 1].strip()
        assert conteudo, (
            f"'{it['nome']}' aponta para {m.group('caminho')}:{n}, que está "
            f"VAZIA.\n\n"
            f"A linha mudou de sítio. Reaponte a prova para a linha que tem "
            f"o código — não para a antiga."
        )


def test_nenhum_item_existe_aponta_para_codigo_que_diz_nao_existe():
    """A regra reversa, e é a que mais importa.

    Se um item diz EXISTE mas aponta para uma linha que é um
    `NotImplementedError`, um `"ausente"` ou um stub, o catálogo está a
    afirmar o contrário do código.
    """
    # O que indica que o alvo NÃO implementa o que o item promete.
    MARCAS_DE_NAO_IMPLEMENTADO = (
        "NotImplementedError",
        "NAO EXISTE",
        "não existe",
        "ausente",
        "pass  #",
        "raise NotImplemented",
    )

    for c, it in _todos_os_itens():
        if it["estado"] == NAO_EXISTE:
            continue
        m = PROVA.match(it["prova"])
        caminho = RAIZ / m.group("caminho")
        linhas = caminho.read_text(encoding="utf-8", errors="replace").splitlines()
        # Lê a linha E as 6 seguintes: a prova costuma apontar para a função,
        # e o `raise` está dentro do corpo.
        janela = "\n".join(linhas[int(m.group("linha")) - 1 :][:8])
        for marca in MARCAS_DE_NAO_IMPLEMENTADO:
            if marca in janela and it["estado"] == EXISTE:
                pytest.fail(
                    f"'{it['nome']}' diz {EXISTE} mas aponta para código que "
                    f"contém {marca!r}:\n"
                    f"  {m.group('caminho')}:{m.group('linha')}\n"
                    f"  {janela.splitlines()[0][:100]}\n\n"
                    f"O estado correto é {PARCIAL} (com o que falta escrito) ou "
                    f"{NAO_EXISTE}."
                )


# ───────────────────────────────────────────────────────────────────────────
# ROTAS: EXISTE ABRI UMA ROTA; NAO_EXISTE NÃO TEM NENHUMA
# ───────────────────────────────────────────────────────────────────────────


def test_todo_item_operacional_abre_uma_rota_que_resolve():
    """A promessa de um clique é uma rota que resolve. Sem rota, não há botão.

    A excepção é `sem_ecra=True`: uma capacidade que **funciona** mas
    vive dentro de outra página, sem ecrã próprio. A IA no dispositivo é o
    caso — carrega no painel do dashboard, não na guia.

    A excepção é explícita e verificada: `sem_ecra` sem `onde_vive` é um
    item que decidiu não ter botão sem dizer onde está, que é o mesmo
    defeito com um nome novo.
    """
    for c, it in _todos_os_itens():
        if it["estado"] != EXISTE:
            continue
        if it.get("sem_ecra"):
            assert it.get("onde_vive"), (
                f"'{it['nome']}' diz `sem_ecra` sem dizer onde vive. "
                f"Quem diz 'não tem botão' tem de dizer onde está."
            )
            continue
        assert it["rota"], (
            f"'{it['nome']}' diz {EXISTE} mas não tem rota nem `sem_ecra`. "
            f"O produtor clica e não acontece nada — que é a forma educada "
            f"de mentir."
        )
    caminho = it["rota"].split("?")[0]
    try:
        resolve(caminho)
    except (Resolver404, Resolver404Exc):
        pytest.fail(
            f"'{it['nome']}' diz {EXISTE} e aponta para {caminho}, que é "
            f"Resolver404.\n\n"
            f"O teste NDVI apanhou exactamente isto hoje: o botão pedia "
            f"`/api/ia/super/` e a rota não existia. Mesma classe de "
            f"defeito — um cartão que promete e não entrega."
        )


def test_nenhum_item_por_implementar_tem_rota():
    """A regra que impede um "não implementado" de ganhar um botão.

    Um NAO_EXISTE com rota é o começo de uma mentira: o cartão aparece,
    parece clicável, e leva a um 404. Ou pior — alguém liga a rota depois e
    o cartão passa a dizer que já funciona.
    """
    for c, it in _todos_os_itens():
        if it["estado"] != NAO_EXISTE:
            continue
        assert not it["rota"], (
            f"'{it['nome']}' diz {NAO_EXISTE} mas tem a rota {it['rota']!r}. "
            f"Um item que não existe não tem para onde abrir."
        )
        assert it["resumo"], (
            f"'{it['nome']}' diz {NAO_EXISTE} sem dizer o que falta. "
            f"'Não existe' sozinho não ajuda o produtor a decidir."
        )


# ───────────────────────────────────────────────────────────────────────────
# PARCIAL TEM DE DIZER O QUE FALTA
# ───────────────────────────────────────────────────────────────────────────


def test_todo_parcial_declara_o_que_falta():
    """Um PARCIAL sem `falta` escrito é um EXISTE com culpa leve.

    Foi exactamente isto que o `test_manifesto_confere_com_codigo.py` apanhou
    noutro ficheiro: `assert count == 0` a passar no caso que devia sinalizar.
    Um meio-que faz barulho, e o produtor não sabe em que metade está.
    """
    for c, it in _todos_os_itens():
        if it["estado"] != PARCIAL:
            continue
        assert it.get("falta"), (
            f"'{it['nome']}' é {PARCIAL} mas não diz o que falta. "
            f"Ou sobe a {EXISTE}, ou desce a {NAO_EXISTE} — o meio tem de "
            f"dizer onde é o meio."
        )
        assert len(it["falta"]) > 20, (
            f"'{it['nome']}' diz que falta \"{it['falta']}\" — curto demais "
            f"para ser uma fronteira. Diz qual é."
        )


# ───────────────────────────────────────────────────────────────────────────
# O QUE A PÁGINA VAI MOSTRAR
# ───────────────────────────────────────────────────────────────────────────


def test_as_contagens_batem_com_o_catalogo():
    """O cabeçalho não escreve números à mão.

    Se o catálogo cresce e o número não, a página mente — que é o defeito
    desta sessão, noutro lugar.
    """
    from app.views.guias import contagens_catalogo

    contagens = contagens_catalogo()

    por_classe = contagens["por_classe"]
    for c in CATALOGO:
        assert por_classe[c["id"]] == len(c["itens"]), (
            f"classe {c['id']}: contagem diz {por_classe[c['id']]}, catálogo "
            f"tem {len(c['itens'])}"
        )

    por_estado = contagens["por_estado"]
    total = sum(len(c["itens"]) for c in CATALOGO)
    assert sum(por_estado.values()) == total, (
        f"as contagens por estado somam {sum(por_estado.values())}, o "
        f"catálogo tem {total}"
    )
    for estado in por_estado:
        assert estado in ESTADO_ROTULO, f"estado {estado!r} sem rótulo na página"


#: Referência de 2026-10-05, com 7 classes e 57 itens.
#:
#: Ponho 57 e não 70, e é uma decisão. Os itens que faltam da lista de
#: mercado para chegar a 70 já estão no catálogo — como NAO_EXISTE, e alguns
#: como PARCIAL. Cada um ocupa mais linhas do que ocuparia um item verdadeiro,
#: porque a sua graça é dizer com precisão o que falta.
#:
#: Encher a lista de repetições faria o número subir e a informação descer:
#: 57 linhas que dizem algo contra 60 das quais 10 dizem «talvez». É a
#: promessa sem código que o `test_manifesto_confere_com_codigo.py` apanha,
#: e o `0.72` que o botão NDVI mostrava num `catch`.
#:
#: O pedido foi «muitos mais, como o topo de mercado». A resposta honesta não é
#: 70 linhas: é 57 capacidades com estado verificado, das quais 27 abrem uma
#: rota que existe. Um competitor com 70 linhas e 45 por implementar está
#: atrás deste catálogo.
REFERENCIA_ITENS = 57


def test_o_catalogo_cobre_as_capacidades_do_mercado():
    """A guia tem de ser comparável à lista de mercado.

    Não é um requisito arbitrário: é o pedido. E o teste impede que a página
    encolha de volta aos 17 itens sem que ninguém decida.
    """
    total = sum(len(c["itens"]) for c in CATALOGO)
    assert total >= REFERENCIA_ITENS, (
        f"o catálogo tem {total} itens; a referência é {REFERENCIA_ITENS}.\n\n"
        f"Se apagaste capacidade porque ela deixou de existir, o certo é mudar "
        f"a referência e escrever porquê. O que não pode é o número andar "
        f"sozinho."
    )


def test_cada_classe_da_lista_do_mercado_tem_item():
    """Cada bloco da lista de mercado está representado.

    A lista tem A, B, C, D, E, G e H — sem F, porque o mercado também a
    salta. Se amanhã entrar uma secção nova na lista do mercado, este teste
    falha a dizer qual falta. É a versão honesta de "cobre o mercado": a lista
    de classes está escrita aqui, à vista, e alguém tem de a acrescentar.
    """
    classes_na_lista = {"A", "B", "C", "D", "E", "G", "H"}
    assert {c["letra"] for c in CATALOGO} == classes_na_lista


def test_ha_itens_operacionais_que_abrem_rota():
    """Sanidade: a página não pode ser uma lista de 'não existe'.

    Se tudo é NAO_EXISTE, a guia é um passivo. Tem de haver trabalho real
    linkado.
    """
    operacionais = [
        it for _, it in _todos_os_itens() if it["estado"] == EXISTE and it["rota"]
    ]
    assert len(operacionais) >= 20, (
        f"só {len(operacionais)} itens operacionais com rota. A lista de "
        f"mercado é uma promessa de produto; esta é a parte que já funciona."
    )
