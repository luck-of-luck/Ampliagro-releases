from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

FAZENDA = {
    "nome": "Fazenda Muzambinho",
    "area_total": Decimal("85.60"),
    "bioma": "mata_atlantica",
    "lat": Decimal("-21.344"),
    "lon": Decimal("-46.525"),
    "endereco": "Estrada do Gloria, Km 4 - Zona Rural",
}

TALHOES = [
    {
        "nome": "Talhao 1 - Catuai Vermelho",
        "area_hectare": Decimal("28.50"),
        "tipo_solo": "Latossolo Vermelho-Amarelo",
        "cultura": "Cafe",
    },
    {
        "nome": "Talhao 2 - Bourbon Amarelo",
        "area_hectare": Decimal("22.00"),
        "tipo_solo": "Latossolo Vermelho-Amarelo",
        "cultura": "Cafe",
    },
    {
        "nome": "Talhao 3 - Topazio MG-1190",
        "area_hectare": Decimal("18.80"),
        "tipo_solo": "Argissolo Vermelho-Amarelo",
        "cultura": "Cafe",
    },
    {
        "nome": "Pastagem - Braquiaria",
        "area_hectare": Decimal("10.30"),
        "tipo_solo": "Latossolo Vermelho",
        "cultura": "Brachiaria",
    },
    {
        "nome": "Reserva Legal",
        "area_hectare": Decimal("6.00"),
        "tipo_solo": "Mata Atlantica nativa",
        "cultura": None,
    },
]

LANCAMENTOS = [
    {
        "tipo": "RECEITA",
        "categoria": "VENDA_PROD",
        "valor": Decimal("392000.00"),
        "data": date(2025, 7, 10),
        "descricao": "Venda cafe Talhao 1 - 280 sc Catuai Vermelho",
    },
    {
        "tipo": "RECEITA",
        "categoria": "VENDA_PROD",
        "valor": Decimal("308000.00"),
        "data": date(2025, 7, 22),
        "descricao": "Venda cafe Talhao 2 - 220 sc Bourbon Amarelo",
    },
    {
        "tipo": "RECEITA",
        "categoria": "VENDA_PROD",
        "valor": Decimal("254800.00"),
        "data": date(2025, 8, 5),
        "descricao": "Venda cafe Talhao 3 - 182 sc Topazio MG-1190",
    },
    {
        "tipo": "RECEITA",
        "categoria": "FINANC",
        "valor": Decimal("84000.00"),
        "data": date(2025, 3, 15),
        "descricao": "Adiantamento cooperativa - contrato entrega jun/2025",
    },
    {
        "tipo": "DESPESA",
        "categoria": "INSUMO",
        "valor": Decimal("68400.00"),
        "data": date(2024, 9, 20),
        "descricao": "Fertilizante NPK 20-05-20 micronutrientes set/2024",
    },
    {
        "tipo": "DESPESA",
        "categoria": "INSUMO",
        "valor": Decimal("22800.00"),
        "data": date(2024, 10, 8),
        "descricao": "Defensivos fungicida inseticida safra 2024",
    },
    {
        "tipo": "DESPESA",
        "categoria": "INSUMO",
        "valor": Decimal("14500.00"),
        "data": date(2024, 11, 5),
        "descricao": "Calcario dolomitico calagem preventiva",
    },
    {
        "tipo": "DESPESA",
        "categoria": "MO",
        "valor": Decimal("48600.00"),
        "data": date(2025, 6, 30),
        "descricao": "Colheita manual 27 trabalhadores 18 dias",
    },
    {
        "tipo": "DESPESA",
        "categoria": "MO",
        "valor": Decimal("12800.00"),
        "data": date(2025, 7, 5),
        "descricao": "Processamento e secagem terreiro mecanico",
    },
    {
        "tipo": "DESPESA",
        "categoria": "MANUT",
        "valor": Decimal("8700.00"),
        "data": date(2025, 2, 14),
        "descricao": "Manutencao derricadeira e atomizador",
    },
    {
        "tipo": "DESPESA",
        "categoria": "OUTROS",
        "valor": Decimal("6200.00"),
        "data": date(2024, 12, 3),
        "descricao": "Energia eletrica irrigacao out-nov 2024",
    },
    {
        "tipo": "DESPESA",
        "categoria": "OUTROS",
        "valor": Decimal("3800.00"),
        "data": date(2025, 1, 20),
        "descricao": "Frete cooperativa 4 carretas 69km",
    },
]

MAQUINARIOS = [
    {
        "nome": "Derricadeira Jacto DM-5",
        "tipo": "OUTRO",
        "marca": "Jacto",
        "modelo": "DM-5",
        "ano_fabricacao": 2021,
        "horas_uso": Decimal("620.0"),
        "ativo": True,
    },
    {
        "nome": "Pulverizador Jacto KO-400",
        "tipo": "OUTRO",
        "marca": "Jacto",
        "modelo": "KO-400",
        "ano_fabricacao": 2022,
        "horas_uso": Decimal("280.0"),
        "ativo": True,
    },
]

INSUMOS = [
    {
        "nome": "NPK 20-05-20 Cafe",
        "categoria": "FERTILIZANTE",
        "quantidade": Decimal("12"),
        "unidade": "t",
        "valor_unitario": Decimal("2850"),
    },
    {
        "nome": "Fungicida Tebuconazol",
        "categoria": "DEFENSIVO",
        "quantidade": Decimal("48"),
        "unidade": "L",
        "valor_unitario": Decimal("85"),
    },
    {
        "nome": "Mudas Catuai Vermelho",
        "categoria": "SEMENTE",
        "quantidade": Decimal("1200"),
        "unidade": "mudas",
        "valor_unitario": Decimal("2.50"),
    },
]

ESTOQUE = [
    {
        "nome": "Cafe beneficiado Catuai",
        "categoria": "PRODUTO",
        "quantidade": Decimal("42"),
        "unidade": "sc",
        "local": "Armazem cooperativa",
    },
    {
        "nome": "Cafe em coco aguardando",
        "categoria": "PRODUTO",
        "quantidade": Decimal("8"),
        "unidade": "sc",
        "local": "Terreiro coberto",
    },
]

SAFRAS = [
    {
        "cultura": "Cafe",
        "ano": 2023,
        "safra_nome": "2023/24",
        "talhao_nome": "Talhao 1 - Catuai Vermelho",
        "area_plantada": Decimal("28.50"),
        "area_colhida": Decimal("27.80"),
        "producao_total": Decimal("972.00"),
        "produtividade": Decimal("35.00"),
        "receita_estimada": Decimal("1069200"),
        "data_plantio": date(2023, 5, 1),
        "data_colheita": date(2023, 6, 30),
    },
    {
        "cultura": "Cafe",
        "ano": 2024,
        "safra_nome": "2024/25",
        "talhao_nome": "Talhao 1 - Catuai Vermelho",
        "area_plantada": Decimal("28.50"),
        "area_colhida": Decimal("28.50"),
        "producao_total": Decimal("855.00"),
        "produtividade": Decimal("30.00"),
        "receita_estimada": Decimal("1197000"),
        "data_plantio": date(2024, 5, 1),
        "data_colheita": date(2025, 7, 10),
    },
    {
        "cultura": "Cafe",
        "ano": 2024,
        "safra_nome": "2024/25",
        "talhao_nome": "Talhao 2 - Bourbon Amarelo",
        "area_plantada": Decimal("22.00"),
        "area_colhida": Decimal("22.00"),
        "producao_total": Decimal("726.00"),
        "produtividade": Decimal("33.00"),
        "receita_estimada": Decimal("1016400"),
        "data_plantio": date(2024, 5, 1),
        "data_colheita": date(2025, 7, 22),
    },
    {
        "cultura": "Cafe",
        "ano": 2024,
        "safra_nome": "2024/25",
        "talhao_nome": "Talhao 3 - Topazio MG-1190",
        "area_plantada": Decimal("18.80"),
        "area_colhida": Decimal("18.80"),
        "producao_total": Decimal("602.00"),
        "produtividade": Decimal("32.00"),
        "receita_estimada": Decimal("842800"),
        "data_plantio": date(2024, 5, 1),
        "data_colheita": date(2025, 8, 5),
    },
]


class Command(BaseCommand):
    help = "Seed dados realistas de cafe para a conta demo.muzambinho (JOSIF)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset", action="store_true", help="Remove dados existentes e recria"
        )

    def handle(self, *args, **opts):
        from app.models import (
            Cultura,
            EstacaoMeteo,
            EstoqueItem,
            Funcionario,
            Insumo,
            LancamentoFinanceiro,
            Maquinario,
            Propriedade,
            Safra,
            Talhao,
            TalhaoGeometria,
        )

        u = User.objects.get(username="demo.muzambinho")
        prop = Propriedade.objects.get(user=u, nome=FAZENDA["nome"])

        if opts["reset"]:
            LancamentoFinanceiro.objects.filter(propriedade=prop).delete()
            Safra.objects.filter(propriedade=prop).delete()
            Maquinario.objects.filter(propriedade=prop).delete()
            Insumo.objects.filter(propriedade=prop).delete()
            EstoqueItem.objects.filter(propriedade=prop).delete()
            for t in Talhao.objects.filter(propriedade=prop):
                TalhaoGeometria.objects.filter(talhao=t).delete()
            Talhao.objects.filter(propriedade=prop).delete()
            self.stdout.write("Reset: dados anteriores removidos.")

        prop.area_total = FAZENDA["area_total"]
        prop.bioma = FAZENDA["bioma"]
        prop.endereco = FAZENDA["endereco"]
        prop.save()
        self.stdout.write(f"Propriedade: {prop.nome} - {prop.area_total} ha")

        def get_cultura(nome, grupo="perenes", unidade="sacas"):
            c, _ = Cultura.objects.get_or_create(
                nome=nome,
                defaults={
                    "grupo": grupo,
                    "unidade_comercial": unidade,
                    "ciclo_dias": 365,
                    "ativo": True,
                },
            )
            return c

        cafe = get_cultura("Cafe", "perenes", "sacas")
        brach = get_cultura("Brachiaria", "forrageiras", "kg")
        prop.culturas.set([cafe, brach])

        lat0, lon0 = float(FAZENDA["lat"]), float(FAZENDA["lon"])
        for idx, td in enumerate(TALHOES):
            cult = (
                cafe if td["cultura"] == "Cafe" else (brach if td["cultura"] else None)
            )
            talhao, _ = Talhao.objects.get_or_create(
                propriedade=prop,
                nome=td["nome"],
                defaults={
                    "area_hectare": td["area_hectare"],
                    "tipo_solo": td["tipo_solo"],
                    "ativo": True,
                    "cultura_atual": cult,
                },
            )
            talhao.area_hectare = td["area_hectare"]
            if cult and not talhao.cultura_atual:
                talhao.cultura_atual = cult
            talhao.save()
            if not TalhaoGeometria.objects.filter(talhao=talhao).exists():
                lt, lg, d = lat0 - idx * 0.018, lon0 + idx * 0.015, 0.012
                TalhaoGeometria.objects.create(
                    talhao=talhao,
                    geojson={
                        "type": "Feature",
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [
                                [
                                    [lg, lt],
                                    [lg + d, lt],
                                    [lg + d, lt + d],
                                    [lg, lt + d],
                                    [lg, lt],
                                ]
                            ],
                        },
                        "properties": {"nome": td["nome"]},
                    },
                    area_calculada_ha=td["area_hectare"],
                    centroide_lat=lt + d / 2,
                    centroide_lon=lg + d / 2,
                )
        self.stdout.write(f"Talhoes: {Talhao.objects.filter(propriedade=prop).count()}")

        EstacaoMeteo.objects.get_or_create(
            propriedade=prop,
            nome=f"Estacao {prop.nome}",
            defaults={
                "latitude": FAZENDA["lat"],
                "longitude": FAZENDA["lon"],
                "ativa": True,
                "codigo_inmet": "A548",
            },
        )

        safra_count = 0
        for sd in SAFRAS:
            try:
                talhao = Talhao.objects.get(propriedade=prop, nome=sd["talhao_nome"])
            except Talhao.DoesNotExist:
                self.stderr.write(f'Talhao nao encontrado: {sd["talhao_nome"]}')
                continue
            _, created = Safra.objects.get_or_create(
                propriedade=prop,
                talhao=talhao,
                cultura=get_cultura(sd["cultura"]),
                ano=sd["ano"],
                safra_nome=sd["safra_nome"],
                defaults={
                    "area_plantada": sd["area_plantada"],
                    "area_colhida": sd["area_colhida"],
                    "producao_total": sd["producao_total"],
                    "produtividade": sd["produtividade"],
                    "receita_estimada": sd["receita_estimada"],
                    "data_plantio": sd["data_plantio"],
                    "data_colheita": sd["data_colheita"],
                },
            )
            if created:
                safra_count += 1
        self.stdout.write(f"Safras: {safra_count} novas")

        lanc_count = 0
        for ld in LANCAMENTOS:
            _, created = LancamentoFinanceiro.objects.get_or_create(
                propriedade=prop,
                tipo=ld["tipo"],
                categoria=ld["categoria"],
                valor=ld["valor"],
                data=ld["data"],
                defaults={"descricao": ld["descricao"]},
            )
            if created:
                lanc_count += 1
        total_rec = sum(
            float(l["valor"]) for l in LANCAMENTOS if l["tipo"] == "RECEITA"
        )
        total_desp = sum(
            float(l["valor"]) for l in LANCAMENTOS if l["tipo"] == "DESPESA"
        )
        saldo = total_rec - total_desp
        self.stdout.write(f"Lancamentos: {lanc_count} | Rec R | Desp R | Saldo R")

        for md in MAQUINARIOS:
            maq, _ = Maquinario.objects.get_or_create(
                propriedade=prop,
                nome=md["nome"],
                defaults={k: v for k, v in md.items() if k != "nome"},
            )
            if not maq.proxima_manutencao:
                from datetime import timedelta as td_

                maq.proxima_manutencao = date.today() + td_(days=30)
                maq.save(update_fields=["proxima_manutencao"])

        for ins in INSUMOS:
            Insumo.objects.get_or_create(
                propriedade=prop,
                nome=ins["nome"],
                defaults={k: v for k, v in ins.items() if k != "nome"},
            )

        for es in ESTOQUE:
            EstoqueItem.objects.get_or_create(
                propriedade=prop,
                nome=es["nome"],
                defaults={k: v for k, v in es.items() if k != "nome"},
            )

        Funcionario.objects.filter(propriedade=prop).update(ativo=True)

        maqs_ativos = Maquinario.objects.filter(propriedade=prop, ativo=True).count()
        self.stdout.write(
            self.style.SUCCESS(
                "Seed Muzambinho concluido:\n"
                f"  Fazenda     : {prop.nome} - {prop.area_total} ha\n"
                f"  Talhoes     : {Talhao.objects.filter(propriedade=prop).count()}\n"
                f"  Safras      : {Safra.objects.filter(propriedade=prop).count()}\n"
                f"  Lancamentos : {LancamentoFinanceiro.objects.filter(propriedade=prop).count()}\n"
                f"  Saldo       : R$ {saldo:,.0f}\n"
                f"  Maquinarios : {maqs_ativos} ativos\n"
            )
        )
