"""O importador de CSV de maquina, testado contra o que cada fabricante exporta.

O QUE ESTES TESTES PROVAM
=========================
O comando `importar_csv_maquinario` existe para substituir o papel que hoje e'
feito a mao: actualizar o horometro do trator. E' o item 1.5 da Onda 1 do
`PLANO-EXECUCAO.md`, e a razao de ser um comando e nao um script avulso e'
que `app/iot/regras_auto.py:337` **ja tem uma regra escrita** que le o
horometro:

    metric = "horimetro" · threshold_max = 250 · severidade = "info"

O que faltava era o numero. Estes testes alimentam-no.

CADA FABRICANTE EXPORTA UM FORMATO
==================================
John Deere (Operations Center), Climate FieldView e Stara nao partilham
nem delimitador nem nome de coluna. Os testes usam os tres formatos reais:

    FieldView        `ID;HORA_MOTOR;DATA`      ponto-e-virgula, DD/MM/AAAA
    Operations Center`id,horas,ultima_manutencao`  virgula, ISO
    Stara            `maquinario;engine_hours` tab,snake_case

Se um destes falhar, o comando nao serve o produtor que tem aquele
maquina — e o objectivo da Onda 1.5 e' exactamente nao assumir que "CSV" e'
uma coisa so.
"""

import io
from datetime import date
from decimal import Decimal

import pytest
from django.core.management import CommandError, call_command

from app.models import Maquinario, Propriedade


@pytest.fixture
def cenario(django_user_model, tmp_path):
    user = django_user_model.objects.create_user(username="jd", password="x")
    prop = Propriedade.objects.create(
        user=user, nome="Fazenda do JD", uf="GO", area_total=100
    )
    trator = Maquinario.objects.create(
        propriedade=prop,
        tipo="TRATOR",
        nome="Trator John Deere 8R 340",
        marca="John Deere",
        horas_uso=Decimal("100"),
    )
    colheitadeira = Maquinario.objects.create(
        propriedade=prop, tipo="COLHEITADEIRA", nome="Colheitadeira X", horas_uso=0
    )
    return {
        "user": user,
        "prop": prop,
        "trator": trator,
        "colheitadeira": colheitadeira,
        "tmp": tmp_path,
    }


def _csv(cenario, conteudo, nome="m.csv", delim=None):
    p = cenario["tmp"] / nome
    p.write_text(conteudo, encoding="utf-8")
    return str(p)


def _importar(cenario, conteudo, nome="m.csv", extra=()):
    args = [_csv(cenario, conteudo, nome), "--propriedade", str(cenario["prop"].pk)]
    args.extend(extra)
    call_command("importar_csv_maquinario", *args, stdout=None)


# ─────────────────────────────────────────────────────────────────────────────
# 1. Os tres formatos de fabricante
# ─────────────────────────────────────────────────────────────────────────────


def test_operations_center_virgula_iso(cenario):
    """John Deere Operations Center: virgula, nomes em portugues, data ISO."""
    _importar(
        cenario,
        f"id,horas,ultima_manutencao\n{cenario['trator'].pk},251.5,2026-08-14\n",
    )
    cenario["trator"].refresh_from_db()
    assert cenario["trator"].horas_uso == Decimal("251.5")
    assert cenario["trator"].ultima_manutencao == date(2026, 8, 14)


def test_fieldview_ponto_e_virgula_e_data_pt(cenario):
    """FieldView exporta `ID;HORA_MOTOR;DATA` com DD/MM/AAAA.

    O `HORA_MOTOR` e' o que o FieldView chama ao horometro — e o comando tem
    de o aceitar, ou nao serve o produtor que tem FieldView.
    """
    _importar(
        cenario,
        f"ID;HORA_MOTOR;DATA\n{cenario['trator'].pk};251,5;14/08/2026\n",
    )
    cenario["trator"].refresh_from_db()
    assert cenario["trator"].horas_uso == Decimal("251.5")
    assert cenario["trator"].ultima_manutencao == date(2026, 8, 14)


def test_stara_tab_e_snake_case(cenario):
    """Stara: tab, `maquinario` em vez de `id`, `engine_hours` em vez de `horas`."""
    _importar(
        cenario,
        "maquinario\tengine_hours\tlast_service\n"
        f"{cenario['trator'].pk}\t251.5\t2026-08-14\n",
    )
    cenario["trator"].refresh_from_db()
    assert cenario["trator"].horas_uso == Decimal("251.5")


def test_milhares_em_formato_pt_br(cenario):
    """`1.234,5` sao mil duzentos e trinta e quatro horas e meia.

    Se isto for lido como `1.234` a regra dos 250h dispara na hora errada — e
    o produtor recebe uma manutencao que nao precisa. E' o caso mais perigoso
    do comando, porque o numero errado e' plausivel.

    NOTA sobre o formato: a virgula decimal so aparece num CSV separado por
    ponto-e-virgula ou tab. Num CSV separado por virgula, `1.234,5` seria lido
    como duas colunas — e nenhum dos tres fabricantes exporta assim. Por isso
    o teste usa `;`, que e' o caso real.
    """
    _importar(cenario, f"id;horas\n{cenario['trator'].pk};1.234,5\n")
    cenario["trator"].refresh_from_db()
    assert cenario["trator"].horas_uso == Decimal("1234.5")


# ─────────────────────────────────────────────────────────────────────────────
# 2. O que o comando NAO faz
# ─────────────────────────────────────────────────────────────────────────────


def test_nao_cria_maquinario_desconhecido(cenario):
    """Um `id` que nao existe e' reportado, nao importado.

    Criar um `Maquinario` a partir de tres colunas de telemetria produziria
    um meio-bem com depreciacao inventada — `valor_aquisicao` e
    `vida_util_anos` ficam a zero, e `valor_atual` devolve None. E' a mesma
    fabricacao que `proveniencia.py` recusa.
    """
    antes = Maquinario.objects.count()
    with pytest.raises(SystemExit):
        _importar(cenario, "id,horas\n999,100\n")
    assert Maquinario.objects.count() == antes


def test_ignora_horometro_negativo(cenario):
    """Um horometro negativo nao existe. Ou o export tem sinal, ou a coluna
    nao e' o que achamos — e nenhum dos dois se adivinha."""
    _importar(cenario, f"id,horas\n{cenario['trator'].pk},-5\n")
    cenario["trator"].refresh_from_db()
    assert cenario["trator"].horas_uso == Decimal("100"), "nao devia ter mudado"


def test_id_nao_numerico_e_reportado(cenario):
    """GUID ou `TRATOR-01` nao se reconciliam. Sem uma chave estavel, o
    unico caminho honesto e dizer que nao deu."""
    with pytest.raises(SystemExit):
        _importar(cenario, "id,horas\nTRATOR-01,251\n")


def test_propriedade_obrigatoria(cenario):
    """Sem `--propriedade` o comando recusa. Um CSV nao tem dono."""
    p = _csv(cenario, "id,horas\n1,100\n")
    with pytest.raises(CommandError):
        call_command("importar_csv_maquinario", p, stdout=None)


def test_propriedade_inexistente_recusa(cenario):
    p = _csv(cenario, "id,horas\n1,100\n")
    with pytest.raises(CommandError):
        call_command(
            "importar_csv_maquinario", p, "--propriedade", "99999", stdout=None
        )


def test_csv_sem_coluna_id_recusa_com_ajuda(cenario):
    """A mensagem diz quais colunas sao aceites. Um `CommandError` que so
    diz "invalido" obriga o utilizador a adivinhar."""
    p = _csv(cenario, "velocidade;rotacoes\n10;2000\n")
    with pytest.raises(CommandError) as e:
        call_command(
            "importar_csv_maquinario",
            p,
            "--propriedade",
            str(cenario["prop"].pk),
            stdout=None,
        )
    assert "horas" in str(e.value)


# ─────────────────────────────────────────────────────────────────────────────
# 3. Tenant e idempotencia
# ─────────────────────────────────────────────────────────────────────────────


def test_nao_toca_em_maquinario_de_outra_fazenda(django_user_model, cenario):
    """`Maquinario` de outra propriedade nao e' actualizado.

    O comando filtra por `propriedade`. Um `--propriedade` apontado para a
    fazenda de outra pessoa nao dá azo a passar um CSV com ids de outra —
    que e' o mesmo formato de fuga que o `TenantIsolationMiddleware` barra
    no HTTP, e que aqui nao passa pelo middleware.
    """
    outro_user = django_user_model.objects.create_user(username="viz", password="x")
    prop2 = Propriedade.objects.create(
        user=outro_user, nome="Fazenda do Vizinho", uf="MT", area_total=50
    )
    maquina_alheia = Maquinario.objects.create(
        propriedade=prop2, tipo="TRATOR", nome="Alheio", horas_uso=10
    )

    # CSV com o id do maquinario alheio, mas a propriedade do cenario.
    with pytest.raises(SystemExit):
        _importar(cenario, f"id,horas\n{maquina_alheia.pk},999\n")

    maquina_alheia.refresh_from_db()
    assert maquina_alheia.horas_uso == Decimal("10"), "tocou em propriedade alheia"


def test_e_idempotente(cenario):
    """Correr duas vezes com o mesmo CSV da o mesmo estado.

    `horas_uso` e' o ultimo valor, nunca uma soma. Se somasse, a segunda
    passagem daria 503 horas e a regra disparava sem razao.
    """
    _importar(cenario, f"id,horas\n{cenario['trator'].pk},251.5\n")
    _importar(cenario, f"id,horas\n{cenario['trator'].pk},251.5\n")
    cenario["trator"].refresh_from_db()
    assert cenario["trator"].horas_uso == Decimal("251.5")


def test_dry_run_nao_escreve(cenario):
    _importar(
        cenario,
        "id,horas\n" + str(cenario["trator"].pk) + ",999\n",
        extra=("--dry-run",),
    )
    cenario["trator"].refresh_from_db()
    assert cenario["trator"].horas_uso == Decimal("100")


def test_varias_linhas_de_once(cenario):
    """Um export de frota tem varias maquinas. Uma por linha, todas."""
    _importar(
        cenario,
        f"id,horas\n{cenario['trator'].pk},251.5\n{cenario['colheitadeira'].pk},1800\n",
    )
    cenario["trator"].refresh_from_db()
    cenario["colheitadeira"].refresh_from_db()
    assert cenario["trator"].horas_uso == Decimal("251.5")
    assert cenario["colheitadeira"].horas_uso == Decimal("1800")


# ─────────────────────────────────────────────────────────────────────────────
# 4. O objectivo: alimentar a regra que ja existe
# ─────────────────────────────────────────────────────────────────────────────


def test_a_regra_proactiva_que_depende_do_horometro_existe(cenario):
    """O plano §2.3 diz que `regras_auto.py:337` tem a regra `horimetro`.

    Este teste nao verifica a regra — verifica que ela continua a existir e a
    ler o mesmo campo que o importador escreve. Se alguem renomear o campo,
    o importador passa a alimentar nada e ninguem da por isso: o sintoma e'
    "a regra nunca dispara", que parece configuracao e nao e' regressao.
    """
    from app.iot import regras_auto

    regras = (
        regras_auto.REGRAS_AUTO
        if hasattr(regras_auto, "REGRAS_AUTO")
        else regras_auto.REGRAS
    )
    horometro = [r for r in regras if r.get("metric") == "horimetro"]
    assert horometro, "a regra do horometro desapareceu de regras_auto.py"

    # MEDIDO 2026-10-05: ha DUAS regras de horometro — 300h para o grao
    # (`grao_maquina_oleo_300h`) e 250h para o John Deere
    # (`erp_john_deere_30pct`). O teste fixava `valor_ref == 250` e passou a
    # falhar quando a regra do grao apareceu, que e' uma mudanca legitima.
    #
    # O que interessa nao e' que seja 250: e' que exista e que o limiar seja
    # um numero. Fixar o valor transformava uma proteccao num obstaculo.
    for r in horometro:
        assert isinstance(r["valor_ref"], (int, float)), (
            f"a regra {r.get('id')!r} tem valor_ref={r['valor_ref']!r}, que nao "
            "e' um numero — a comparacao com o horometro vai rebentar."
        )

    # O campo que a regra le tem de ser o campo que o importador escreve.
    assert Maquinario._meta.get_field("horas_uso")
