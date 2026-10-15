from datetime import timedelta

from django.db import models
from django.utils import timezone

from app.models.estoque import EstoqueItem


class EstoqueService:
    @staticmethod
    def alerta_ruptura(propriedade_id: int):
        """Retorna itens cujo estoque está abaixo da quantidade mínima."""
        itens = EstoqueItem.objects.filter(
            propriedade_id=propriedade_id, quantidade__lte=models.F("quantidade_minima")
        ).exclude(quantidade_minima=0)

        alertas = []
        for item in itens:
            alertas.append(
                {
                    "item_id": item.id,
                    "nome": item.nome,
                    "quantidade_atual": float(item.quantidade),
                    "quantidade_minima": float(item.quantidade_minima),
                    "unidade": item.unidade,
                    "status": "critico" if float(item.quantidade) <= 0 else "alerta",
                }
            )
        return alertas

    @staticmethod
    def alerta_fefo(propriedade_id: int):
        """Identifica itens vencendo nos próximos 30, 15 ou 7 dias, e vencidos."""
        hoje = timezone.now().date()
        limite_30_dias = hoje + timedelta(days=30)

        itens = EstoqueItem.objects.filter(
            propriedade_id=propriedade_id,
            data_validade__isnull=False,
            data_validade__lte=limite_30_dias,
            quantidade__gt=0,
        ).order_by("data_validade")

        alertas = []
        for item in itens:
            dias_restantes = (item.data_validade - hoje).days
            status = "vencido"
            if dias_restantes > 15:
                status = "30d"
            elif dias_restantes > 7:
                status = "15d"
            elif dias_restantes >= 0:
                status = "7d"

            alertas.append(
                {
                    "item_id": item.id,
                    "nome": item.nome,
                    "data_validade": item.data_validade,
                    "dias_restantes": dias_restantes,
                    "quantidade_afetada": float(item.quantidade),
                    "unidade": item.unidade,
                    "status": status,
                }
            )
        return alertas

    @staticmethod
    def analise_curva_abc(propriedade_id: int):
        """
        Classifica itens em A, B e C baseado no valor total no estoque.
        A: 80% do valor acumulado
        B: +15% (95% do total)
        C: +5% (100% do total)
        """
        itens = EstoqueItem.objects.filter(
            propriedade_id=propriedade_id, quantidade__gt=0
        )

        # Calcular valor total por item
        dados_itens = []
        valor_estoque_total = 0.0

        for item in itens:
            valor_item = float(item.quantidade) * float(item.valor_unitario)
            valor_estoque_total += valor_item
            dados_itens.append(
                {
                    "item_id": item.id,
                    "nome": item.nome,
                    "quantidade": float(item.quantidade),
                    "valor_unitario": float(item.valor_unitario),
                    "valor_total": valor_item,
                }
            )

        if valor_estoque_total == 0:
            return {"curva_abc": [], "valor_total": 0}

        # Ordenar por valor decrescente
        dados_itens.sort(key=lambda x: x["valor_total"], reverse=True)

        # Atribuir classes
        valor_acumulado = 0.0
        for idx, item in enumerate(dados_itens):
            valor_acumulado += item["valor_total"]
            percentual_acumulado = valor_acumulado / valor_estoque_total

            if percentual_acumulado <= 0.80:
                item["classe_abc"] = "A"
            elif percentual_acumulado <= 0.95:
                item["classe_abc"] = "B"
            else:
                item["classe_abc"] = "C"

        return {"valor_total": round(valor_estoque_total, 2), "itens": dados_itens}
