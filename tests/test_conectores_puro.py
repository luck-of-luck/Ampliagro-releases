"""Testa a logica pura dos conectores, sem Django nem base de dados.

Existe por um motivo concreto: o resto da suite precisa do Django pronto, e
`app/ia/proativo.py` esteve com `IndentationError` durante parte do dia (outro
processo a escrever). Um ficheiro que so precisa de `decimal` e `unicodedata`
nao tem por que esperar por isso.
"""

import importlib.util
import sys
from decimal import Decimal
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]


def _carrega():
    caminho = RAIZ / "app" / "services" / "conectores.py"
    spec = importlib.util.spec_from_file_location("conectores_sozinho", caminho)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["conectores_sozinho"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_a_deteccao_de_formato_e_estrita():
    """Reconhece o que e' deste conector e recusa o que nao e'.

    Este e' o teste que impede o erro caro: um conector que aceita um formato
    proximo escreve 200 registos no sitio errado, e o produtor so descobre
    quando um total nao bate. `None` e' a resposta obrigatoria.
    """
    m = _carrega()

    assert m.ConectorMaquinas.detecta({"Maquina": "", "Horas_Motor": ""}) == (
        "horimetro-csv-v1"
    )
    assert m.ConectorMaquinas.detecta({"maquina": "", "lat": ""}) == (
        "telemetria-csv-v1"
    )
    assert (
        m.ConedorLancamentos.detecta({"Data": "", "Valor": "", "Historico": ""})
        == "lancamentos-csv-v1"
    )
    assert m.ConectorSafra.detecta({"Cultura": "", "Área": ""}) == "safra-csv-v1"

    # O que NAO e' deste conector tem de dar `None`, nunca um palpite.
    assert m.ConedorLancamentos.detecta({"coluna": "x"}) is None
    assert m.ConectorSafra.detecta({"Data": "", "Valor": ""}) is None
    assert m.ConedorLancamentos.detecta({}) is None


def test_o_formato_nao_reconhecido_diz_o_que_esperava():
    """Recusar sem explicar e' um beco sem saida para o produtor.

    O resultado tem de dizer: (a) que nao reconheceu, (b) que formatos
    esperava, e (c) quais colunas viu. Sem (c), o produtor nao tem como
    corrigir.
    """
    m = _carrega()

    r = m.ConedorLancamentos.importa(
        {"Foo": "", "Bar": "", "Baz": ""},
        [{"Foo": "1", "Bar": "2", "Baz": "3"}],
        propriedade=None,
    )

    assert r.formato_detectado == "nao_reconhecido"
    assert r.total_linhas == 0
    assert r.importados == 0
    texto = r.resumo_para_o_produtor()
    assert "nenhum registro gravado" in texto
    assert "lancamentos-csv-v1" in r.avisos[0]
    assert "Foo" in r.avisos[0]


def test_a_coluna_desconhecida_e_contada_nunca_descartada_em_silencio():
    """Se o ficheiro trouxer uma coluna a mais, o produtor tem de saber.

    E' o contrato que `importar_csv_maquinario` ja cumpre e que o
    `ConectorMaquinas` tambem cumpre. Um conector que importasse as colunas
    que reconhece e falhasse em dizer quais mais trouxe e' um conector que
    perde dados em silencio.
    """
    m = _carrega()

    r = m.ConectorMaquinas.importa(
        {"Maquina": "", "Horas_Motor": "", "Coluna_Que_Nao_Conheco": ""},
        [],
        propriedade=None,
    )

    assert r.formato_detectado == "horimetro-csv-v1"
    assert "Coluna_Que_Nao_Conheco" in r.campos_desconhecidos
    assert any("nao reconheci" in a for a in r.avisos)


def test_o_numero_para_e_nan_ou_none():
    """Zero-trust: `NaN` nunca. `None` quando nao e' numero.

    Um `NaN` num campo `Decimal` levanta `InvalidOperation` na base de dados, e
    o produtor ve "erro de servidor" numa pagina que devia mostrar um numero.
    `test_telemetria_zero_trust.py` exige `None`; este teste exige que a
    CONVERSAO ja devolva `None`, antes de chegar ao campo.
    """
    m = _carrega()

    assert m._numero("NaN") is None
    assert m._numero("nan") is None
    assert m._numero("inf") is None
    assert m._numero("") is None
    assert m._numero(None) is None
    assert m._numero("abc") is None

    assert m._numero("42") == Decimal("42")
    assert m._numero("1.234,56") == Decimal("1234.56")
    assert m._numero("R$ 1.500,00") == Decimal("1500.00")
    assert m._numero("1.5") == Decimal("1.5")


def test_a_normalizacao_de_coluna_casa_grafias_diferentes():
    """`Horas_Motor`, `horas-motor` e `HORAS MOTOR` sao a mesma coluna.

    Nao e' umaiska: e' o ficheiro do painel da maquina que traz `Horas` e o
    relatorio do John Deere traz `HORAS_MOTOR`. O produtor nao escolhe a
    grafia, o equipamento escolhe.
    """
    m = _carrega()

    assert m._norm("Horas_Motor") == "horas_motor"
    assert m._norm("horas-motor") == "horas_motor"
    assert m._norm("HORAS MOTOR") == "horas_motor"
    assert m._norm("Área") == "area"
    assert m._norm("LAT") == "lat"


def test_a_data_aceita_os_formatos_que_o_equipamento_traz():
    m = _carrega()

    assert str(m._data("2026-03-15")) == "2026-03-15"
    assert str(m._data("15/03/2026")) == "2026-03-15"
    assert m._data("") is None
    assert m._data("quarta-feira") is None


def test_o_contrato_do_resultado_e_o_mesmo_com_zero_linhas_e_com_mil():
    """Um consumidor que faca `r["rejeitados"]` nao pode rebentar no vazio.

    Este e' o mesmo principio de `compliance_ambiental.py`: dois ramos com
    conjuntos de chaves diferentes sao um contrato que ninguem pode satisfazer.
    O ramo mais frequente ('nao havia nada para importar') e' o que mais se
    esquece.
    """
    m = _carrega()

    vazio = m.ResultadoImportacao(conector="x", formato_detectado="y")
    cheio = m.ResultadoImportacao(conector="x", formato_detectado="y", total_linhas=5)

    assert vazio.rejeitados == []
    assert vazio.incompletos == []
    assert vazio.campos_desconhecidos == []
    assert cheio.rejeitados == []
    assert "registo(s) importados" in vazio.resumo_para_o_produtor()
    assert "nao tinha linhas de dados" in vazio.resumo_para_o_produtor()


def test_o_resumo_menciona_o_que_ficou_de_fora():
    """O produtor tem de ver o que ficou de fora, nao so o que entrou.

    Um resumo que so diz quantos entraram esconde uma importacao a meio. A
    razao do `Incomplete` e do `rejeitado` tem de aparecer no texto.
    """
    m = _carrega()

    r = m.ResultadoImportacao(
        conector="maquinas",
        formato_detectado="telemetria-csv-v1",
        total_linhas=40,
        importados=35,
        incompletos=[{"linha": 3, "motivo": "maquina desconhecida"}],
        rejeitados=[m.Rejeicao(linha=4, motivo="linha corrompida")],
    )

    texto = r.resumo_para_o_produtor()
    assert "35" in texto
    assert "5" in texto or "5 ficaram" in texto
    assert "1" in texto  # 1 ficou por preencher
    assert "nao entraram" in texto


def test_o_catalogo_declara_a_regra_csv_primeiro():
    """A regra tem de estar no catalogo, nao so no manual.

    A IA le o catalogo antes de tentar. Se a regra 'CSV primeiro, API nunca' so
    estiver num `.md` que ninguem abre, o proximo agente propoe um conector de
    API — que e' exactamente o que a folha diz para nao fazer.
    """
    m = _carrega()

    cat = m.catalogo_conectores()
    assert "CSV primeiro, API nunca" in cat["regra"]
    assert len(cat["conectores"]) == len(m.CONECTORES)
    for c in cat["conectores"]:
        assert c["formatos_aceitos"], f"o conector {c['nome']} nao declara formato"
        assert c["campos_reconhecidos"], f"o conector {c['nome']} nao declara campos"


def test_o_catalogo_nao_promete_integracao_oficial():
    """Nao ha acordo com John Deere, Stara, Climate FieldView ou Solinftec.

    Dizer isto no catalogo e' o que impede um agente de vender ao produtor uma
    'integracao oficial' que nao existe. Um conector que le o ficheiro que a
    marca exporta e' uma coisa; integrar com a marca e' outra.
    """
    m = _carrega()

    cat = m.catalogo_conectores()
    texto = cat["regra"] + " " + cat["o_que_faz"]
    assert "Nao ha integracao oficial" in texto
    for marca in ("John Deere", "Stara", "Climate FieldView", "Solinftec"):
        assert marca in texto, f"o catalogo nao menciona {marca}"


def test_previa_devolve_registros_sem_declarar_gravacao():
    m = _carrega()
    resultado = m.ConedorLancamentos.importa(
        {"data": "", "valor": "", "descricao": ""},
        [{"data": "15/03/2026", "valor": "100,00", "descricao": "Venda"}],
        propriedade=None,
    )
    assert resultado.ok
    assert resultado.importados == 0
    assert resultado.actualizados == 0
    assert len(resultado.registros) == 1
    assert resultado.registros[0]["valor"] == Decimal("100.00")
    assert "nenhum registro gravado" in resultado.resumo_para_o_produtor()


def test_previa_com_linha_incompleta_nao_declara_sucesso_total():
    m = _carrega()
    resultado = m.ConedorLancamentos.importa(
        {"data": "", "valor": "", "descricao": ""},
        [
            {"data": "15/03/2026", "valor": "100", "descricao": "Venda"},
            {"data": "invalida", "valor": "20", "descricao": "Outra"},
        ],
        propriedade=None,
    )
    assert not resultado.ok
    assert len(resultado.registros) == 1
    assert resultado.incompletos[0]["linha"] == 3
    assert resultado.importados == 0
    assert "entraram," not in resultado.resumo_para_o_produtor()
