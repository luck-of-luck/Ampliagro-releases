"""Leitura de extractos bancarios: OFX e CSV.

PORQUE ESTE FICHEIRO EXISTE
===========================
Havia dois parsers de OFX no Ampliagro, e o pior deles nao era o fraco:

- `app/api/views/custos.py:397 conciliacao_upload` — parser OFX SGML real,
  funcional, com sugestoes de match. Mas devolve as transacoes e **nunca
  persiste**: nada entra no banco.
- `app/api/views/financeiro_banco.py:64 importar_ofx` — validava a extensao,
  lia o ficheiro, e devolvia
  `{"ok": True, "importadas": 0, "mensagem": "Parser OFX a implementar"}`.

O segundo e' o pior padrao possivel num ERP: **HTTP 200 com `ok: true` e zero
linhas escritas**. O cliente le "ok", fecha o ecra, e assume que o extrato do
banco foi carregado. Nao foi. Esteve assim com um `ET` importado e nunca
usado a duas linhas de distancia — o codigo que mostra a intencao de parser
existe ao lado da prova de que nao existe.

ESTE MODULO E' A UNICA LEITURA
==============================
Extrai a parsing para aqui, e as duas views passam a chamar esta funcao. Duas
consequencias, e a segunda e' a que importa:

1. `importar_ofx` passa a **gravar** `MovimentacaoBancaria`, que e' o que o
   nome da rota promete.
2. O parser deixa de ser codigo dentro de uma `ViewSet`, onde ninguem o
   encontra para testar. Passa a ser uma funcao pura com um teste.

Deduplicacao por `FITID`
========================
O `MovimentacaoBancaria.hash_unico` tem `unique=True`. Um extrato reenviado
pelo banco — e acontece sempre, porque o produtor carrega o mesmo ficheiro
duas vezes — daria `IntegrityError` a meio da gravacao, deixando metade do
extrato gravada e a devolver 500. Aqui o `FITID` (identificador que o proprio banco
da a transacao) vira o hash, e o que ja existe e' actualizado em vez de
duplicado. Sem `FITID` — alguns CSV nao tem — cai para um hash do conteudo
(data+valor+descricao), que também é estavel: a mesma linha reenviada dá o
mesmo hash. Sem FITID, a versão atual usa descrição integral, valor em
centavos e número da ocorrência no arquivo. Extratos parciais com linhas
indistinguíveis continuam exigindo conferência: conteúdo não prova identidade
entre arquivos diferentes.
"""

import csv
import json
import re
from collections import Counter
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from hashlib import sha256

from django.db import transaction

#: Limite defensivo. Um extracto de 5 MB tem ~40 000 lancamentos; acima disso
#: nao e' um extracto, e' um arquivo que se enganou no campo.
TAMANHO_MAXIMO = 5 * 1024 * 1024

FORMATOS_DATA = ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%m/%d/%Y")


class ExtratoNaoReconhecido(ValueError):
    """O ficheiro nao e' um OFX nem um CSV que este sistema saiba ler.

    Existe para a view responder 400 com o que fazer, em vez de 200 com um
    dicionario vazio. Um `ValueError` generico nao diz ao produtor se o
    problema foi o formato ou o nosso parser.
    """


def _campo(bloco: str, tag: str) -> str:
    m = re.search(rf"<{tag}>([^<\r\n]+)", bloco, re.IGNORECASE)
    return m.group(1).strip() if m else ""


def _data_ofx(dt_raw: str):
    try:
        if len(dt_raw) == 8:
            return date(int(dt_raw[:4]), int(dt_raw[4:6]), int(dt_raw[6:8]))
    except (ValueError, TypeError):
        return None
    return None


def _data_csv(bruto: str):
    bruto = (bruto or "").strip()
    if not bruto:
        return None
    for fmt in FORMATOS_DATA:
        try:
            return datetime.strptime(bruto, fmt).date()
        except ValueError:
            continue
    return None


def _decimal(bruto: str):
    """'1.234,56' e '1234.56' dao o mesmo 1234.56.

    O CSV brasileiro usa ponto como separador de milhar e virgula como
    decimal; o OFX usa ponto decimal. Tratar os dois com uma so regra e'
    escrever 1234.56 num extrato que valia 1.234,56 — o pior erro num
    sistema que trata dinheiro, e um erro que nao dá sintaxe inválida.
    """
    texto = str(bruto or "").strip()
    if not texto:
        raise InvalidOperation("vazio")
    if "," in texto:
        # 1.234,56 -> remove separadores de milhar, troca decimal
        texto = texto.replace(".", "").replace(",", ".")
    valor = Decimal(texto)
    if not valor.is_finite() or abs(valor) >= Decimal("1000000000000"):
        raise InvalidOperation("valor fora do limite de 12 inteiros e 2 decimais")
    if valor != valor.quantize(Decimal("0.01")):
        raise InvalidOperation("valor com fração de centavo")
    return valor


def _hash_unico(conta_id, dt, valor, descricao, fitid, ocorrencia=1) -> str:
    """Identidade estavel da transacao, para nao duplicar num reenvio."""
    if fitid:
        return sha256(f"{conta_id}|{fitid}".encode()).hexdigest()
    base = json.dumps(
        [conta_id, str(dt), format(valor, ".2f"), descricao or "", ocorrencia],
        ensure_ascii=False,
    )
    return "v2:" + sha256(base.encode()).hexdigest()[:61]


def ler_extrato(conteudo: bytes, nome_arquivo: str = "") -> list[dict]:
    """Le um OFX ou CSV e devolve a lista normalizada de transacoes.

    Cada dict tem: `data` (date), `descricao`, `valor` (Decimal),
    `tipo` ("RECEITA"/"DESPESA"), `fitid`.

    Levanta `ExtratoNaoReconhecido` se o formato, data ou valor for inválido,
    indicando a linha para correção antes de gravar qualquer movimentação.
    """
    if conteudo is None:
        raise ExtratoNaoReconhecido("Ficheiro vazio.")

    texto = conteudo.decode("utf-8", errors="replace")
    nome = (nome_arquivo or "").lower()
    parece_ofx = (
        nome.endswith((".ofx", ".ofc", ".qfx"))
        or "<ofx" in texto.lower()
        or "<stmtrs" in texto.lower()
    )

    if parece_ofx:
        blocos = re.findall(
            r"<STMTTRN>(.*?)</STMTTRN>", texto, re.DOTALL | re.IGNORECASE
        )
        transacoes = []
        for numero, bloco in enumerate(blocos, start=1):
            try:
                valor = _decimal(_campo(bloco, "TRNAMT"))
            except (InvalidOperation, ValueError) as exc:
                raise ExtratoNaoReconhecido(
                    f"Transação OFX {numero}: valor inválido. Informe até 12 "
                    "dígitos inteiros e 2 decimais. Nenhuma transação foi importada."
                ) from exc
            data = _data_ofx(_campo(bloco, "DTPOSTED")[:8])
            if data is None:
                raise ExtratoNaoReconhecido(
                    f"Transação OFX {numero}: data ausente ou inválida em DTPOSTED. "
                    "Corrija a data no arquivo. Nenhuma transação foi importada."
                )
            transacoes.append(
                {
                    "data": data,
                    "descricao": _campo(bloco, "MEMO") or _campo(bloco, "NAME"),
                    "valor": valor,
                    "tipo": "RECEITA" if valor > 0 else "DESPESA",
                    "fitid": _campo(bloco, "FITID"),
                }
            )
        return transacoes

    linhas = texto.splitlines()
    if nome.endswith(".csv") or not parece_ofx and len(linhas) > 1:
        if not linhas:
            raise ExtratoNaoReconhecido("CSV sem linhas.")
        try:
            return _ler_csv(linhas)
        except (ValueError, KeyError) as exc:
            raise ExtratoNaoReconhecido(f"CSV ilegível: {exc}") from exc

    raise ExtratoNaoReconhecido(
        "Formato não reconhecido. Envie .ofx/.ofc/.qfx ou .csv "
        "delimitado por ';' ou ','."
    )


def _ler_csv(linhas: list[str]) -> list[dict]:
    leitor = csv.DictReader(linhas, delimiter=";")
    campos = leitor.fieldnames or []
    # Fallback para virgula: muitos extratos saem com separadorwrong.
    if len(campos) == 1 and "," in campos[0]:
        leitor = csv.DictReader(linhas, delimiter=",")
    transacoes = []
    for linha in leitor:
        descricao = (
            linha.get("descricao")
            or linha.get("Descricao")
            or linha.get("description")
            or linha.get("historico")
            or linha.get("Histórico")
            or ""
        )
        valor_bruto = (
            linha.get("valor")
            or linha.get("Valor")
            or linha.get("amount")
            or linha.get("montante")
            or ""
        )
        try:
            valor = _decimal(valor_bruto)
        except (InvalidOperation, ValueError) as exc:
            raise ExtratoNaoReconhecido(
                f"Linha CSV {leitor.line_num}: valor ausente ou inválido. "
                "Informe até 12 dígitos inteiros e 2 decimais. "
                "Nenhuma transação foi importada."
            ) from exc
        data_bruta = (
            linha.get("data")
            or linha.get("Data")
            or linha.get("date")
            or linha.get("Data Lancamento")
            or ""
        )
        data = _data_csv(data_bruta)
        if data is None:
            raise ExtratoNaoReconhecido(
                f"Linha CSV {leitor.line_num}: data ausente ou inválida. "
                "Informe uma data válida, como 31/03/2026 ou 2026-03-31. "
                "Nenhuma transação foi importada."
            )
        transacoes.append(
            {
                "data": data,
                "descricao": descricao,
                "valor": valor,
                "tipo": "RECEITA" if valor > 0 else "DESPESA",
                "fitid": linha.get("fitid") or linha.get("id") or "",
            }
        )
    return transacoes


@transaction.atomic
def gravar_movimentacoes(conta, transacoes: list[dict]) -> dict:
    """Grava as transacoes em `MovimentacaoBancaria`, sem duplicar.

    Reenvio do mesmo extracto e' a norma, nao a excecao: o produtor carrega
    o ficheiro duas vezes porque a primeira resposta demorou. Com
    `hash_unico` a `unique=True`, gravar sem verificar rebenta em
    `IntegrityError` a meio, deixando metade do extrato escrita e um 500 ao
    utilizador. Movimentos pendentes existentes são atualizados. Conciliados
    idênticos são preservados; divergências rejeitam e revertem todo o lote.
    """
    from app.models import MovimentacaoBancaria

    criadas = actualizadas = preservadas = 0
    ocorrencias = Counter()
    for numero, t in enumerate(transacoes, start=1):
        if t["data"] is None:
            raise ExtratoNaoReconhecido(
                f"Transação {numero}: data ausente. Nenhuma transação foi importada."
            )
        tipo_mov = "CREDITO" if t["tipo"] == "RECEITA" else "DEBITO"
        identidade = _hash_unico(
            conta.id, t["data"], t["valor"], t["descricao"], t["fitid"]
        )
        ocorrencias[identidade] += 1
        h = _hash_unico(
            conta.id,
            t["data"],
            t["valor"],
            t["descricao"],
            t["fitid"],
            ocorrencias[identidade],
        )
        existente = (
            MovimentacaoBancaria.objects.select_for_update()
            .filter(hash_unico=h)
            .first()
        )
        if existente is None and not t["fitid"]:
            # Só reconhecemos importações antigas com conteúdo integral igual.
            # Casos ambíguos exigem revisão, sem fundir movimentos manualmente.
            legados = list(
                MovimentacaoBancaria.objects.select_for_update()
                .filter(
                    conta=conta,
                    data=t["data"],
                    valor=abs(t["valor"]),
                    tipo=tipo_mov,
                    descricao=t["descricao"] or "(sem descricao)",
                    documento="",
                )
                .exclude(hash_unico__startswith="v2:")[:2]
            )
            representacoes = {
                str(t["valor"]),
                str(t["valor"].normalize()),
                format(t["valor"], ".2f"),
                format(t["valor"].normalize(), "f"),
            }
            if t["valor"] == t["valor"].quantize(Decimal("0.1")):
                representacoes.add(format(t["valor"], ".1f"))
            hashes_legados = {
                sha256(
                    f"{conta.id}|{t['data']}|{valor}|{(t['descricao'] or '')[:60]}".encode()
                ).hexdigest()
                for valor in representacoes
            }
            if legados:
                if len(legados) != 1 or legados[0].hash_unico not in hashes_legados:
                    raise ExtratoNaoReconhecido(
                        f"Transação {numero} sem identificador bancário coincide com "
                        "movimentos anteriores de origem ambígua. Revise esses movimentos "
                        "ou envie um extrato com identificadores. Nenhuma transação foi importada."
                    )
                existente = legados[0]
                existente.hash_unico = h
                existente.save(update_fields=["hash_unico"])
        if existente is not None and existente.conciliado:
            if (
                existente.data != t["data"]
                or existente.valor != abs(t["valor"])
                or existente.tipo != tipo_mov
                or existente.descricao != (t["descricao"] or "(sem descricao)")
                or existente.documento != t["fitid"][:100]
            ):
                raise ExtratoNaoReconhecido(
                    f"Movimentação {existente.pk} já conciliada diverge do extrato. "
                    "Revise a conciliação antes de importar a alteração. "
                    "Nenhuma transação deste envio foi importada."
                )
            preservadas += 1
            continue
        obj, foi_criado = MovimentacaoBancaria.objects.update_or_create(
            hash_unico=h,
            defaults={
                "conta": conta,
                "data": t["data"],
                "descricao": t["descricao"] or "(sem descricao)",
                "valor": abs(t["valor"]),
                "tipo": tipo_mov,
                "documento": t["fitid"][:100],
            },
        )
        if foi_criado:
            criadas += 1
        else:
            actualizadas += 1

    sem_data = sum(1 for t in transacoes if t["data"] is None)
    return {
        "criadas": criadas,
        "actualizadas": actualizadas,
        "preservadas": preservadas,
        "sem_identificador": sum(1 for t in transacoes if not t["fitid"]),
        "sem_data": sem_data,
        "total": len(transacoes),
    }
