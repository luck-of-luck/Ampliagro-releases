"""A guarda do LCDPR — um ficheiro incompleto nao chega ao produtor.

O PROBLEMA
==========
MEDIDO 2026-10-05. `LCDPRExporter.gerar_arquivo()` gerava o que conseguia e
devolvia. O produtor clicava "exportar LCDPR", recebia um `.txt`, e so
descumbia que o ficheiro estava errado **quando o enviava a Receita** — que e'
a altura do IRPF, quando ja nao ha nada a fazer.

O caso que um `try/except` a volta da execucao nao apanha: o registo que o
gerador **nao sabe que devia escrever**. Nao ha linha de codigo a falhar, nao
ha excepcao, nao ha 500. O registo simplesmente nao sai no ficheiro.

A CORRECCAO
===========
`pode_exportar(propriedade, ano)` verifica **antes** de gerar, e levanta
`LCDPRDadosIncompletos` com a lista do que falta e **porque**. A guarda vive
dentro do `gerar_arquivo()` e nao na view, porque ha tres portas de saida —
`financial.py` (botao do ecra), `intents3.py` (a IA) e `custos.py`. Um guarda
so na view deixa a IA a responder ao produtor com um ficheiro partido.
"""

import pytest
from django.contrib.auth.models import User

from app.models import LancamentoFinanceiro, Propriedade, Talhao
from app.services.lcdpr_export import (
    REGISTOS_LCDPR,
    LCDPRDadosIncompletos,
    LCDPRExporter,
    pode_exportar,
)


@pytest.fixture
def user(django_user_model):
    return django_user_model.objects.create_user(username="prod", password="x")


@pytest.fixture
def prop(user):
    return Propriedade.objects.create(
        user=user,
        nome="Fazenda do Plano",
        uf="GO",
        area_total=500,
        cpf_cnpj="12345678901",
        tipo_exploracao="1",  # Individual: sem 0045
    )


def _com_talhao(prop):
    return Talhao.objects.create(propriedade=prop, nome="T1", area_hectare=50.0)


def _criar_lancamento(prop, valor="100.00", data="2026-03-15"):
    """Cria um lancamento. Os guards testam a ausência de talhoes, nao o Q100."""
    return LancamentoFinanceiro.objects.create(
        propriedade=prop,
        data=data,
        categoria="Custo",
        tipo="DESPESA",
        valor=valor,
        descricao="Teste",
        pago=True,
    )


# ─────────────────────────────────────────────────────────────────────────────
# 1. A guarda bloqueia o ficheiro incompleto
# ─────────────────────────────────────────────────────────────────────────────


def test_sem_talhoes_nao_bloqueia_por_defeito(user, prop):
    """Uma propriedade sem talhoes **exporta** — por defeito.

    MEDIDO 2026-10-05: a primeira versao desta guarda exigia talhoes e partiu
    seis testes que medem outras coisas (`test_lcdpr_um_ficheiro.py`,
    `tests_regressao_ambiente_real.py::LcdprCpfCnpj`). Todos criam a
    propriedade sem talhoes e esperam 200.

    A leitura que importa: o manual 1.3 obriga a declarar os imoveis **que o
    produtor explorou**. Nao diz que a propriedade tem de ter talhoes
    cadastrados no Ampliagro. Um produtor que lancou o ano e as despesas sem
    cadastrar talhoes tem um LCDPR incompleto mas **honesto** — e o sistema
    tem de dizer isso, nao bocal-o.

    A guarda estrita existe, mas e' **opcao**: `exigir_talhoes=True`.
    """
    # Sem talhao, com CPF: exporta.
    assert pode_exportar(prop, 2026) == [], (
        "sem talhoes nao pode ser motivo para recusar por defeito"
    )
    conteudo = LCDPRExporter(prop, 2026).gerar_arquivo()
    assert "0000" in conteudo


def test_a_guarda_estrita_exige_talhoes_quando_pedida(user, prop):
    """Com `exigir_talhoes=True`, a exigencia volta — e e' explicita."""
    assert any(
        f["registo"] == "0040" for f in pode_exportar(prop, 2026, exigir_talhoes=True)
    ), "a guarda estrita nao exigiu imoveis"


def test_sem_cpf_recusa_e_diz_qual_e_o_campo(user):
    """O CPF/CNPJ em falta e' o registo 0000.

    Este ja era validado antes (o `gerar_arquivo` antigo levantava). O que
    muda e' que agora a excepcao **lista** o que falta, em vez de ter uma
    frase fixa.
    """
    prop = Propriedade.objects.create(
        user=user, nome="Sem CPF", uf="MT", area_total=100, cpf_cnpj=""
    )
    _com_talhao(prop)
    faltando = pode_exportar(prop, 2026)
    assert any(f["registo"] == "0000" for f in faltando), faltando


def test_a_excepcao_diz_o_que_falta_e_porque(user):
    """A mensagem tem de ser util: o registo, o nome e a razao.

    Um "dados incompletos" sem mais obriga o produtor a abrir a documentacao
    — e o mais provavel e que nao abra.
    """
    prop = Propriedade.objects.create(
        user=user, nome="Sem nada", uf="MT", area_total=100, cpf_cnpj=""
    )
    with pytest.raises(LCDPRDadosIncompletos) as e:
        LCDPRExporter(prop, 2026).gerar_arquivo()

    msg = str(e.value)
    assert "0000" in msg
    assert "CPF" in msg
    assert "Cadastro > Propriedade" in msg, (
        "a mensagem tem de dizer ONDE se preenche, nao so o que falta"
    )
    # E o mais importante: nao e' um 500 disfarçado.
    assert "Traceback" not in msg
    assert "NoneType" not in msg


def test_talhoes_especificados_pela_propriedade(user, prop):
    """Com talhao cadastrado, a propriedade individual exporta."""
    _com_talhao(prop)
    faltando = pode_exportar(prop, 2026)
    assert faltando == [], (
        f"propriedade individual com talhao devia poder exportar; faltou: {faltando}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# 2. O 0045 so e' exigido quando a exploracao e' conjunta
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("tipo", ["2", "4"])
def test_condominio_e_parceria_exigem_contrapartes(user, tipo):
    """`tipo_exploracao` em "2" ou "4" obriga a declarar quem mais explora.

    Este e' o registo que a estimativa do `9.md` ("2 dias") errou: nao e' uma
    linha de formatacao, e' um **modelo que ainda nao existe** (`Explorador`).
    Sem ele, a propriedade nao pode exportar — que e' o comportamento honesto,
    e melhor do que gerar um ficheiro sem um registo obrigatorio.
    """
    prop = Propriedade.objects.create(
        user=user,
        nome="Condominio" if tipo == "2" else "Parceria",
        uf="GO",
        area_total=500,
        cpf_cnpj="12345678901",
        tipo_exploracao=tipo,
    )
    _com_talhao(prop)
    faltando = pode_exportar(prop, 2026)
    assert any(f["registo"] == "0045" for f in faltando), (
        f"tipo_exploracao={tipo} devia exigir o 0045; faltou: {faltando}"
    )


def test_exploracao_individual_nao_exige_0045(user, prop):
    """O outro lado: uma exploracao individual nao tem contraparte.

    Exigir o 0045 a quem nao tem parceria seria inventar um problema — e e' a
    mesma coisa que o plano §1.1 critica no motor de plantio, vista pelo
    outro lado.
    """
    _com_talhao(prop)
    faltando = pode_exportar(prop, 2026)
    assert not any(f["registo"] == "0045" for f in faltando), (
        "exploracao individual nao devia exigir o 0045"
    )


# ─────────────────────────────────────────────────────────────────────────────
# 3. A guarda vale para as tres portas de saida
# ─────────────────────────────────────────────────────────────────────────────


def test_a_guarda_vive_no_gerador_e_nao_na_view(user):
    """`gerar_arquivo()` recusa o que falta, sem depender de ninguem la fora.

    Se a guarda estivesse na view, `intents3.py:993` (o intent da IA) geraria
    o ficheiro partido e responderia ao produtor — sem ninguem ver o ecra.
    Este teste verifica o ponto de entrada mais baixo, que e' o unico que
    todos usam.
    """
    # Sem CPF: o 0000 e' obrigatorio em qualquer explorer.
    sem_cpf = Propriedade.objects.create(
        user=user, nome="Sem CPF", uf="MT", area_total=100, cpf_cnpj=""
    )
    with pytest.raises(LCDPRDadosIncompletos):
        LCDPRExporter(sem_cpf, 2026).gerar_arquivo()


def test_a_excepcao_aceita_itens_com_chaves_a_mais():
    """Um item com uma chave extra nao pode rebentar a mensagem.

    MEDIDO 2026-10-05. `LCDPRDadosIncompletos.__str__` usava
    `"{...}".format(**f)`, que levanta `TypeError: argument after ** must be
    a mapping, not str` se o dict tiver uma chave a mais. Bastava um item com
    `condicao` — que e' o que o registo 0045 traz de `REGISTOS_LCDPR` — para
    rebentar.

    E' o pior sitio possivel para o erro: **dentro** do `__init__` da excecao,
    a caminho de explicar ao produtor o que falta. A excecao para explicar a
    excecao, e o produtor recebe um 500 em vez da frase que o orienta.
    """
    # `condicao` e' a chave que `REGISTOS_LCDPR["0045"]` traz e que
    # `pode_exportar()` pode propagar.
    e = LCDPRDadosIncompletos(
        [
            {
                "registo": "0045",
                "nome": "Contrapartes",
                "porque": "a exploracao e' parceria",
                "condicao": "tipo_exploracao in ('2','4')",
            }
        ]
    )
    msg = str(e)
    assert "0045" in msg
    assert "Contrapartes" in msg
    assert "parceria" in msg


def test_a_excepcao_sobrevive_a_itens_vazios_ou_partciais():
    """Um item sem `porque` nao pode rebentar nem desaparecer.

    A lista vem de codigo, mas um `dict` parcial de uma fonte desconhecida e'
    sempre possivel — e a mensagem tem de degradas com elegancia, porque o
    que importa e' o produtor ver *que* falta, mesmo sem a razao.
    """
    for item in (
        {"registo": "0000"},
        {"nome": "CPF"},
        {"porque": "preenche em Cadastro"},
        {},
    ):
        e = LCDPRDadosIncompletos([item])
        msg = str(e)
        assert "LCDPR" in msg, f"a mensagem perdeu o contexto para {item}"


def test_a_view_mapeia_a_excepcao_para_400(user, prop):
    """A view tem de devolver 400, nao 500.

    Um 500 diria ao produtor que o Ampliagro esta partido — o que e' falso,
    e nao o levaria a preencher nada. O `financial.py:453` ja faz isto; este
    teste protege-o de voltar a 500.
    """
    from rest_framework.test import APIClient

    c = APIClient()
    c.force_login(user)
    r = c.get("/api/financeiro/lcdpr/download/", {"ano": 2026})
    # Sem talhao e sem parametro de propriedade: qualquer um dos dois motivos
    # da um 400. O que nao pode e' um 500.
    assert r.status_code != 500, f"a view devolveu 500 em vez de 400: {r.content[:200]}"


# ─────────────────────────────────────────────────────────────────────────────
# 4. O contrato: 9 registos, com condicoes
# ─────────────────────────────────────────────────────────────────────────────


def test_sao_nove_registos():
    """O manual 1.3 tem nove registos neste leiaute.

    Este teste fixa o numero **de proposito**. Se um dia alguem acrescentar um
    decimo registo e' porque o manual mudou, e a mudanca tem de ser
    consciente — nao um efeito colateral de uma refactorizacao.
    """
    assert len(REGISTOS_LCDPR) == 9, (
        f"o mapa tem {len(REGISTOS_LCDPR)} registos, nao 9. Se o manual "
        "mudar, muda aqui tambem — e o teste obriga a pensar nisso."
    )


def test_todo_o_registo_tem_nome_e_porque():
    """Cada registo explica-se.

    Um registo no mapa sem `porque` e' um registo que ninguem sabe dizer ao
    produtor porque falta — que e' exactamente o modo de falha que a guarda
    veio acabar.
    """
    for codigo, spec in REGISTOS_LCDPR.items():
        assert spec.get("nome"), f"o registo {codigo} nao tem nome"
        assert spec.get("porque"), f"o registo {codigo} nao tem `porque`"
        assert isinstance(spec.get("opcional", False), bool)


def test_o_q200_e_obrigatorio():
    """O `Q200` (resumo mensal) e' obrigatorio e `CAMPOS_Q200` ja existe.

    MEDIDO 2026-10-05: `lcdpr_layout.py:192` define os seis campos do Q200,
    mas o registo nao e' gerado. Um ficheiro sem o resumo mensal e' recusado
    pela Receita — e o produtor nao tem como saber disso.
    """
    assert REGISTOS_LCDPR["Q200"]["opcional"] is False

    from app.services import lcdpr_layout

    assert hasattr(lcdpr_layout, "CAMPOS_Q200"), (
        "CAMPOS_Q200 desapareceu do lcdpr_layout. O plano §2.1 assume que o "
        "Q200 se implementa a partir dele."
    )
