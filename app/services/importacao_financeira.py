"""Importação atômica de lançamentos declarados, com identidade externa."""

import csv
import io
import json
from hashlib import sha256

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from app.models import LancamentoFinanceiro, LinhaFinanceiraImportada, Propriedade
from app.services.conectores import ConedorLancamentos, _norm


@transaction.atomic
def importar_lancamentos_csv(*, usuario, propriedade_id, origem, arquivo, conteudo):
    """Grava CSV com id, data, valor e descricao; reenvios não sobrescrevem."""
    if not usuario.is_authenticated:
        raise PermissionDenied("Autenticação necessária.")
    propriedade = (
        Propriedade.objects.select_for_update()
        .filter(pk=propriedade_id, user=usuario)
        .first()
    )
    if propriedade is None:
        raise PermissionDenied("A importação exige acesso de proprietário.")
    origem = str(origem or "").strip()
    if not origem or len(origem) > 100:
        raise ValidationError("Informe a origem do arquivo com até 100 caracteres.")
    if not conteudo or len(conteudo) > 5 * 1024 * 1024:
        raise ValidationError("Envie um CSV não vazio de até 5 MB.")
    try:
        texto = conteudo.decode("utf-8-sig")
        delimitador = ";" if ";" in texto.splitlines()[0] else ","
        leitor = csv.DictReader(io.StringIO(texto), delimiter=delimitador, strict=True)
        campos = [_norm(c) for c in (leitor.fieldnames or [])]
        permitidos = {"id", "data", "valor", "descricao", "tipo", "documento"}
        if len(set(campos)) != len(campos) or not {
            "id",
            "data",
            "valor",
            "descricao",
        } <= set(campos):
            raise ValidationError(
                "Cabeçalho deve conter id, data, valor e descricao, sem colunas repetidas."
            )
        if set(campos) - permitidos:
            raise ValidationError(
                "Colunas não reconhecidas: "
                + ", ".join(sorted(set(campos) - permitidos))
            )
        linhas = []
        for numero, bruta in enumerate(leitor, start=2):
            if None in bruta or any(v is None for v in bruta.values()):
                raise ValidationError(
                    f"Linha {numero}: quantidade de colunas inválida."
                )
            linhas.append({_norm(k): v.strip() for k, v in bruta.items()})
    except (UnicodeDecodeError, csv.Error, IndexError) as exc:
        raise ValidationError(
            "CSV inválido. Use UTF-8, com vírgula ou ponto e vírgula."
        ) from exc
    if not linhas:
        raise ValidationError("O arquivo não contém lançamentos.")
    ids = set()
    for numero, linha in enumerate(linhas, start=2):
        identificador = linha["id"]
        if not identificador or len(identificador) > 100 or identificador in ids:
            raise ValidationError(
                f"Linha {numero}: id externo ausente, repetido ou maior que 100 caracteres."
            )
        ids.add(identificador)
        if linha.get("tipo", "").upper() not in ("", "RECEITA", "DESPESA"):
            raise ValidationError(f"Linha {numero}: tipo deve ser RECEITA ou DESPESA.")
    previa = ConedorLancamentos.importa(
        {c: "" for c in campos if c != "id"}, linhas, propriedade
    )
    if not previa.ok:
        raise ValidationError(
            [f"Linha {item['linha']}: {item['motivo']}" for item in previa.incompletos]
            or ["Não foi possível preparar o arquivo."]
        )
    criados = existentes = 0
    for numero, (linha, registro) in enumerate(
        zip(linhas, previa.registros, strict=True), start=2
    ):
        lancamento = LancamentoFinanceiro(
            propriedade=propriedade,
            categoria="OUTRO",
            pago=False,
            tipo_lancamento_lcdpr="",
            numero_documento=registro["documento"],
            **{k: v for k, v in registro.items() if k != "documento"},
        )
        try:
            lancamento.full_clean()
        except ValidationError as exc:
            raise ValidationError(
                f"Linha {numero}: " + "; ".join(exc.messages)
            ) from exc
        normalizado = {**registro, "valor": format(registro["valor"], ".2f")}
        digest = sha256(
            json.dumps(normalizado, sort_keys=True, default=str).encode()
        ).hexdigest()
        anterior = LinhaFinanceiraImportada.objects.filter(
            propriedade=propriedade, origem=origem, id_externo=linha["id"]
        ).first()
        if anterior:
            if anterior.hash_conteudo != digest:
                raise ValidationError(
                    f"Linha {numero}: id {linha['id']} já importado com conteúdo diferente. Revise o lançamento existente."
                )
            existentes += 1
            continue
        lancamento.save()
        trilha = LinhaFinanceiraImportada(
            propriedade=propriedade,
            lancamento=lancamento,
            origem=origem,
            id_externo=linha["id"],
            hash_conteudo=digest,
            arquivo=arquivo,
            importado_por=usuario,
        )
        trilha.full_clean()
        trilha.save()
        criados += 1
    return {"criados": criados, "existentes": existentes, "total": len(linhas)}
