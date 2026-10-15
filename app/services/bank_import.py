import csv
import io
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Tuple

from django.db.models import Q

from app.models.financeiro import LancamentoFinanceiro

try:
    from ofxparse import OfxParser
except ImportError:
    OfxParser = None


def parse_ofx(file_obj) -> List[Dict]:
    """Parse arquivo OFX e retorna lista de transações normalizadas."""
    if not OfxParser:
        raise Exception("Biblioteca ofxparse não está instalada.")

    ofx = OfxParser.parse(file_obj)
    transacoes = []

    for account in ofx.accounts:
        for transaction in account.statement.transactions:
            transacoes.append(
                {
                    "id_banco": transaction.id,
                    "data": transaction.date.date(),
                    "valor": Decimal(str(transaction.amount)),
                    "descricao": transaction.memo or transaction.payee,
                    "tipo": "RECEITA" if transaction.amount > 0 else "DESPESA",
                }
            )

    return transacoes


def parse_csv(file_obj) -> List[Dict]:
    """
    Parse de CSV genérico. Assumimos layout: Data, Descrição, Valor.
    O file_obj deve ser aberto em modo texto ou decodificado.
    """
    content = file_obj.read().decode("utf-8", errors="replace")
    reader = csv.reader(io.StringIO(content), delimiter=";")

    transacoes = []
    for row in reader:
        # Pular cabeçalhos ou linhas vazias
        if len(row) < 3 or "data" in row[0].lower():
            continue

        try:
            # Tenta parsing DD/MM/YYYY
            data_str = row[0].strip()
            data = datetime.strptime(data_str, "%d/%m/%Y").date()

            descricao = row[1].strip()

            # Valor (tratar vírgula)
            valor_str = (
                row[2].replace("R$", "").replace(".", "").replace(",", ".").strip()
            )
            valor = Decimal(valor_str)

            transacoes.append(
                {
                    "id_banco": f"{data_str}-{descricao}-{valor_str}",
                    "data": data,
                    "valor": valor,
                    "descricao": descricao,
                    "tipo": "RECEITA" if valor > 0 else "DESPESA",
                }
            )
        except Exception:
            continue

    return transacoes


def conciliar_transacoes(
    propriedade_id: int, transacoes_banco: List[Dict]
) -> Tuple[List[Dict], List[Dict]]:
    """
    Tenta casar as transações do banco com os Lançamentos Financeiros existentes.
    Retorna (matched, unmatched).
    Matching por: Mesmo tipo, Valor Exato e Data (margem +- 3 dias).
    """
    matched = []
    unmatched = []

    for tb in transacoes_banco:
        # Margem de 3 dias
        data_min = tb["data"] - timedelta(days=3)
        data_max = tb["data"] + timedelta(days=3)
        valor_abs = abs(tb["valor"])

        # Procurar candidato
        candidatos = LancamentoFinanceiro.objects.filter(
            propriedade_id=propriedade_id,
            tipo=tb["tipo"],
            valor=valor_abs,
            pago=False,
            data__gte=data_min,
            data__lte=data_max,
        )

        if candidatos.exists():
            # Casa com o primeiro encontrado (pode-se melhorar heurística)
            candidato = candidatos.first()
            matched.append(
                {
                    "banco": tb,
                    "sistema": {
                        "id": candidato.id,
                        "descricao": candidato.descricao
                        or candidato.get_categoria_display(),
                        "valor": candidato.valor,
                        "data": candidato.data,
                    },
                }
            )
        else:
            unmatched.append(tb)

    return matched, unmatched
