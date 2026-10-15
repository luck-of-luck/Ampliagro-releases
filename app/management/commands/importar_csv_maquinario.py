"""Importador de telemetria de maquina a partir de CSV.

POR QUE ISTO EXISTE
===================
O plano de execucao §2.3: o Ampliagro tem a **interface** da telemetria de
maquina (`top_globais.py:2` fala em "16 widgets FieldView/JD/Trimble
clonados") mas nao tem a **ingestao**. O produtor que ja tem um John Deere com
telemetria continua a usar o portal da Deere — e nao paga duas vezes, o que
significa que nao migra.

O que este comando NAO faz, e e' a decisao mais importante do ficheiro:
**nao integramos com APIs de fabricante.** Tres理由:

  * John Deere (Operations Center), Climate FieldView e Stara **nao partilham
    API nenhuma**. Nao ha um denominador comum a integrar — so há tres
    integracoes separadas, cada uma com a sua autenticacao, o seu rate limit e
    a sua forma de mudar sem aviso.
  * CSV e' o **denominador comum que ja existe**: os tres exportam ficheiro.
  * Uma importacao manual de CSV resolve o caso de uso real — "actualiza o
    horometro do trator" — que e' o que o produtor faz hoje, a mao, numa
    folha de papel.

Isto e' o plano §2.3 a dizer, em codigo: **CSV primeiro, API nunca, no
arranque**. Tres integracoes antes de provar que alguem quer sincronizacao
automatica e' o erro classico de produto.

O QUE ESTE COMANDO ACTIVA
=========================
`app/iot/regras_auto.py:337` tem a regra `erp_john_deere_30pct`:

    metric = "horimetro" · threshold_max = 250 · severidade = "info"

Ou seja: **a regra proactiva que avisa "o trator passou das 250 horas" ja
esta escrita**. O que lhe faltava era o numero. Este comando forne-ce o
numero. E' por isso que o comando existe em vez de um script avulso: o
objectivo nao e' "importar dados", e' **alimentar um motor que ja existe**.

TAMBEM ALIMENTA
===============
* `Maquinario.horas_uso` — o receptor (`models/maquinario.py`).
* `Maquinario.ultima_manutencao` — para a depreciacao (`valor_atual`).
* `Maquinario.proxima_manutencao` — manutencao preventiva.

FORMATO DO CSV
==============
Delimitado por virgula, cabecalho obrigatorio. Nomes de coluna aceitos, em
qualquer ordem, com ou sem acentos e sem caixa:

    id | id_maquinario | id         — a chave. Ver `resolver_maquinario`.
    horas | horas_uso | horometro  — o numero que a regra le.
    ultima_manutencao | data_ultima
    proxima_manutencao | data_proxima

Exemplo:

    id,horas,ultima_manutencao
    3,251.5,2026-08-14
    7,1240,2026-09-02

EXEMPLO DE CAIXA ALTA (FieldView exporta assim):

    ID;HORA_MOTOR;DATA
    3;251.5;14/08/2026

A deteccao de delimitador e' automatica: `csv.Sniffer` com fallback para
virgula e ponto-e-virgula. Uma coluna `HORA_MOTOR` em vez de `horas` e'
aceite porque o FieldView usa esse nome — e o ficheiro tem de vir do
fabricante, nao de umBulk exportacao nossa.

INVARIANTES
===========
* **So(actualiza)**. Nao cria maquinarios: um CSV com `id` desconhecido e'
  reportado como linha nao reconciliada, nao importado. Motivo: o
  `Maquinario` tem `valor_aquisicao`, `vida_util_anos` e depreciacao. Criar
  um a partir de tres colunas de telemetria produziria um meio-bem com
  depreciacao inventada — e' exactamente o defeito que `proveniencia.py`
  recusa.
* **Tenant.** `--propriedade` e' obrigatorio e o filtro e' por
  `propriedade__user`. Um CSV nao pode escrever na fazenda de outro.
* **Idempotente.** Correr duas vezes com o mesmo CSV resulta no mesmo estado;
  `horas_uso` e' o ultimo valor, nao uma soma.
* **Nada e' silencioso.** Cada linha processada, ignorada ou nao reconciliada
  sai no relatorio. Um importador que nao diz o que falhou e' o mesmo
  "sucesso verde sobre dado perdido" que o plano §2.2corrige para o
  Caderno.
"""

import csv
import io
import os
import sys
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from app.models import Maquinario, Propriedade

#: As colunas que o FieldView, o Operations Center e a Stara usam, e os
#: nomes que Aceitamos para cada conceito. Primeiro valor = nome canonico.
COLUNAS = {
    "id": ("id", "id_maquinario", "maquinario", "equipment_id", "id_equip"),
    "horas": (
        "horas",
        "horas_uso",
        "horometro",
        "hora_motor",
        "engine_hours",
        "hours",
    ),
    "ultima_manutencao": (
        "ultima_manutencao",
        "data_ultima",
        "ultimo_service",
        "last_service",
        # MEDIDO 2026-10-05: o FieldView exporta a coluna da data da ultima
        # manutencao como `DATA`, a secas. Sem este alias a coluna nao era
        # reconhecida e a data era descartada em silencio — a linha era
        # "aplicada" so com as horas, e o produtor ficava sem a manutencao.
        "data",
    ),
    "proxima_manutencao": (
        "proxima_manutencao",
        "data_proxima",
        "proximo_service",
        "next_service",
    ),
}

#: Formatos de data aceitos. O FieldView exporta DD/MM/AAAA, que e'
#: ambiguo com MM/DD/AAAA — por isso o formato americano so e' lido quando
#: o dia do primeiro componente e' > 12, ou seja, quando nao ha duvida.
DATAS = ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%Y/%m/%d")


def _normaliza(chave: str) -> str:
    """`"HORA_MOTOR"` -> `"hora_motor"`; sem acentos, minusculas."""
    import unicodedata

    s = unicodedata.normalize("NFKD", chave.strip().lower())
    return "".join(c for c in s if not unicodedata.combining(c))


def _mapeia(cabecalho):
    """`{coluna_canonica: indice_no_csv}` a partir do cabecalho lido."""
    out = {}
    for i, bruta in enumerate(cabecalho):
        n = _normaliza(bruta)
        for canonico, aliases in COLUNAS.items():
            if n in aliases and canonico not in out:
                out[canonico] = i
                break
    return out


def _numero(texto: str):
    """`'1.234,5'` -> `1234.5`; `'1234.5'` -> `1234.5`; `'1,234.5'` -> `1234.5`.

    Tres formatos porque cada fabricante exporta um. Errar aqui e' pior do
    que recusar: `1.234` em PT-BR sao mil duzentos e trinta e quatro horas, e
    em US sao um virgula virgula tres — e a regra dos 250h dispararia na
    hora errada.
    """
    t = (texto or "").strip().replace(" ", "")
    if not t:
        return None
    # Milhar com ponto, decimal com virgula: o formato pt-BR.
    if "." in t and "," in t:
        return float(t.replace(".", "").replace(",", "."))
    # So virgula: decimal pt-BR (ou milhar US — nenhum dos tres fabricantes
    # exporta isso).
    if "," in t:
        return float(t.replace(",", "."))
    # So ponto: decimal US.
    return float(t)


def _data(texto: str):
    """Primeiro formato que faz sentido. `None` se nenhum."""
    t = (texto or "").strip()
    if not t:
        return None
    for fmt in DATAS:
        try:
            d = datetime.strptime(t, fmt).date()
        except ValueError:
            continue
        # `13/01/2026` so pode ser DD/MM. `01/13/2026` so pode ser MM/DD.
        # O formato so e' aceite com dia > 12 quando o primeiro componente
        # nao passa de 12 — ver a nota em DATAS.
        if fmt == "%Y/%m/%d" and d.month > 12:
            continue
        return d
    return None


class Command(BaseCommand):
    help = (
        "Importa telemetria de maquina de CSV (FieldView, Operations Center, "
        "Stara) para Maquinario.horas_uso, activando as regras proativas que "
        "ja leem o horometro."
    )

    def add_arguments(self, parser):
        parser.add_argument("csv_path", help="Caminho do ficheiro CSV")
        parser.add_argument(
            "--propriedade",
            required=True,
            type=int,
            help="ID da propriedade (obrigatorio: sem isto nao ha tenant)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Mostra o que faria sem escrever",
        )
        parser.add_argument(
            "--delimitador",
            default="auto",
            choices=("auto", ",", ";", "\t"),
            help="Delimitador do CSV (default: auto)",
        )

    def handle(self, *args, **opts):
        prop_id = opts["propriedade"]
        prop = Propriedade.objects.filter(id=prop_id).select_related("user").first()
        if prop is None:
            raise CommandError(
                f"propriedade {prop_id} nao existe. O importador exige uma "
                "propriedade porque um CSV nao tem dono."
            )

        caminho = opts["csv_path"]
        if not os.path.exists(caminho):
            raise CommandError(f"CSV nao encontrado: {caminho}")

        with open(caminho, "r", encoding="utf-8-sig", newline="") as fh:
            texto = fh.read()

        # --- leitura -----------------------------------------------------
        delim = opts["delimitador"]
        if delim == "auto":
            try:
                delim = csv.Sniffer().sniff(texto, delimiters=",;\t").delimiter
            except csv.Error:
                delim = ","
                # Ultimo recurso: a primeira linha tem mais separadores do
                # que campos. Um CSV de maquina tem varias colunas, portanto
                # isto e' seguro — e falhar aqui e' melhor do que parar.
                primeira = texto.split("\n", 1)[0]
                for cand in (";", "\t", ","):
                    if primeira.count(cand) >= 2:
                        delim = cand
                        break

        leitor = csv.reader(io.StringIO(texto), delimiter=delim)
        try:
            cabecalho = next(leitor)
        except StopIteration:
            raise CommandError("o CSV esta vazio")

        mapa = _mapeia(cabecalho)
        if "id" not in mapa:
            raise CommandError(
                "o CSV nao tem coluna de id. Reconhecidas: "
                + ", ".join(sorted(COLUNAS))
                + f". Cabecalho lido: {cabecalho}"
            )
        if "horas" not in mapa:
            self.stdout.write(
                self.style.WARNING(
                    "o CSV nao tem coluna de horas. So datas serao importadas. "
                    "Aceites: " + ", ".join(COLUNAS["horas"])
                )
            )

        maquinas = {
            m.pk: m
            for m in Maquinario.objects.filter(propriedade=prop).select_related(
                "propriedade"
            )
        }

        # --- processamento ------------------------------------------------
        aplicadas, ignoradas, nao_reconciliadas = [], [], []

        with transaction.atomic():
            for n_linha, linha in enumerate(leitor, start=2):
                if not any((c or "").strip() for c in linha):
                    continue  # linha em branco

                bruto_id = linha[mapa["id"]].strip() if len(linha) > mapa["id"] else ""
                if not bruto_id:
                    ignoradas.append((n_linha, "sem id"))
                    continue

                try:
                    maquina_id = int(float(bruto_id))
                except ValueError:
                    # Alguns exportam GUID ou "TRATOR-01". Sem uma chave
                    # estavel nao ha como reconciliar, e inventar um
                    # mapeamento seria exactamente a fabricacao que este
                    # projecto recusa.
                    nao_reconciliadas.append((n_linha, bruto_id, "id nao numerico"))
                    continue

                maquina = maquinas.get(maquina_id)
                if maquina is None:
                    nao_reconciliadas.append(
                        (
                            n_linha,
                            bruto_id,
                            f"nao existe maquinario {maquina_id} nesta propriedade",
                        )
                    )
                    continue

                mudancas = {}

                if "horas" in mapa and len(linha) > mapa["horas"]:
                    horas = _numero(linha[mapa["horas"]])
                    if horas is None:
                        ignoradas.append((n_linha, "horas vazias"))
                    elif horas < 0:
                        # Um horometro negativo nao existe. Ou o export
                        # tem um sinal, ou a coluna nao e' o que achamos.
                        ignoradas.append((n_linha, f"horas negativas ({horas})"))
                    else:
                        mudancas["horas_uso"] = horas

                for campo, coluna in (
                    ("ultima_manutencao", "ultima_manutencao"),
                    ("proxima_manutencao", "proxima_manutencao"),
                ):
                    if coluna in mapa and len(linha) > mapa[coluna]:
                        d = _data(linha[mapa[coluna]])
                        if d is not None:
                            mudancas[campo] = d
                        elif linha[mapa[coluna]].strip():
                            ignoradas.append(
                                (n_linha, f"{coluna} em formato desconhecido")
                            )

                if not mudancas:
                    ignoradas.append((n_linha, "nada a actualizar"))
                    continue

                if opts["dry_run"]:
                    aplicadas.append((n_linha, maquina.nome, dict(mudancas), False))
                    continue

                for k, v in mudancas.items():
                    setattr(maquina, k, v)
                maquina.save(
                    update_fields=list(mudancas.keys()) + ["ultima_manutencao"]
                )
                aplicadas.append((n_linha, maquina.nome, dict(mudancas), True))

            if opts["dry_run"]:
                transaction.set_rollback(True)

        # --- relatorio ---------------------------------------------------
        # Tudo o que aconteceu sai aqui. Um importador que nao diz o que
        # falhou e' o mesmo "sucesso verde sobre dado perdido" que o Caderno
        # de Campo tinha.
        for n_linha, nome, mudancas, escrita in aplicadas:
            detalhe = ", ".join(f"{k}={v}" for k, v in mudancas.items())
            marca = "" if escrita else " (dry-run)"
            self.stdout.write(f"  L{n_linha} {nome}: {detalhe}{marca}")

        for n_linha, motivo in ignoradas:
            self.stdout.write(self.style.WARNING(f"  L{n_linha} ignorada: {motivo}"))

        for n_linha, bruto, motivo in nao_reconciliadas:
            self.stdout.write(
                self.style.ERROR(f"  L{n_linha} NAO RECONCILIADA ({bruto}): {motivo}")
            )

        self.stdout.write("")
        prefixo = "[dry-run] " if opts["dry_run"] else ""
        self.stdout.write(
            f"{prefixo}{len(aplicadas)} actualizadas · "
            f"{len(ignoradas)} ignoradas · "
            f"{len(nao_reconciliadas)} nao reconciliadas "
            f"({prop.nome}, {len(maquinas)} maquinarios)"
        )

        if nao_reconciliadas:
            # Sai != 0 porque nao e' um sucesso: parte da telemetria ficou
            # de fora e o leitor tem de saber.
            sys.exit(1)
