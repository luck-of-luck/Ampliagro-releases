"""
Seed MVP Demo - Fazenda Modelo para JOSIF / FEBRACE
Cria usuário demo/demo123 + 1 fazenda showcase perfeita, limpa lixos (aaaaaaa etc)

Uso:
  python manage.py seed_mvp_demo              # cria/atualiza demo
  python manage.py seed_mvp_demo --reset      # apaga tudo do demo e recria do zero
  python manage.py seed_mvp_demo --reset --with-telemetry  # + 24h telemetria real

Apresentação: login obrigatório, mas com botão Demo (class="actions") -> /demo/ -> logado direto
e demo.bat lança direto logado e pronto.
"""

from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

FAZENDA_MODELO = {
    "nome": "Fazenda Modelo - Primavera do Leste",
    "area_total": Decimal("1240.00"),
    "uf": "MT",
    "cidade": "Primavera do Leste",
    "bioma": "cerrado",
    "lat": Decimal("-15.558"),
    "lon": Decimal("-54.299"),
}

TALHOES_MODELO = [
    {
        "nome": "Talhão A - Soja",
        "area": Decimal("420.00"),
        "tipo_solo": "Latossolo Vermelho",
        "cultura_nome": "Soja",
    },
    {
        "nome": "Talhão B - Milho Safrinha",
        "area": Decimal("380.00"),
        "tipo_solo": "Latossolo Vermelho-Amarelo",
        "cultura_nome": "Milho",
    },
    {
        "nome": "Talhão C - Pastagem",
        "area": Decimal("280.00"),
        "tipo_solo": "Argissolo",
        "cultura_nome": "Brachiaria",
    },
    {
        "nome": "Reserva Legal",
        "area": Decimal("160.00"),
        "tipo_solo": "Cerrado Nativo",
        "cultura_nome": None,
    },
]

LIXOS = ["aaaaaaa", "acaba logo", "fazenda123", "aaaaaaaa"]


class Command(BaseCommand):
    help = "Cria Fazenda Modelo showcase para JOSIF/FEBRACE (demo/demo123)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Apaga propriedades lixas e recria demo do zero",
        )
        parser.add_argument(
            "--with-telemetry",
            action="store_true",
            help="Sincroniza 24h Open-Meteo + simula SOLO/NIVEL/MAQ",
        )

    def handle(self, *args, **opts):
        from app.models import (
            Animal,
            Cultura,
            EstoqueItem,
            Insumo,
            LancamentoFinanceiro,
            Maquinario,
            PerfilUsuario,
            Propriedade,
            Safra,
            Talhao,
        )

        user, created = User.objects.get_or_create(
            username="demo", defaults={"email": "demo@ampliagro.local"}
        )
        if created or not user.check_password("demo123"):
            user.set_password("demo123")
            user.email = "demo@ampliagro.local"
            user.save()
            self.stdout.write(
                self.style.SUCCESS("Usuário demo/demo123 criado/atualizado")
            )
        PerfilUsuario.objects.get_or_create(
            user=user, defaults={"tipo_usuario": "produtor"}
        )

        if opts["reset"]:
            # Deleta TODAS as propriedades do usuário demo, ativando CASCADE
            # Isso garante que a base fica cristalina e resolve a dor #2
            Propriedade.objects.filter(user=user).delete()
            self.stdout.write("Reset: Base limpa para o usuário demo")

        # garante culturas
        def get_cultura(nome, grupo="graos", unidade="sacas"):
            c, _ = Cultura.objects.get_or_create(
                nome=nome,
                defaults={
                    "grupo": grupo,
                    "unidade_comercial": unidade,
                    "ciclo_dias": 120,
                    "ativo": True,
                },
            )
            return c

        soja = get_cultura("Soja", "graos", "sacas")
        milho = get_cultura("Milho", "graos", "sacas")
        brachiaria = get_cultura("Brachiaria", "forrageiras", "kg")

        # Propriedade Modelo
        prop, created = Propriedade.objects.get_or_create(
            user=user,
            nome=FAZENDA_MODELO["nome"],
            defaults={
                "area_total": FAZENDA_MODELO["area_total"],
                "uf": FAZENDA_MODELO["uf"],
                "cidade": FAZENDA_MODELO["cidade"],
                "bioma": FAZENDA_MODELO["bioma"],
                "endereco": "Rod. MT-130, Km 12 - Zona Rural",
            },
        )
        if created:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Propriedade criada: {prop.nome} ({prop.area_total} ha)"
                )
            )
        else:
            self.stdout.write(f"Propriedade ok: {prop.nome}")

        # Talhões
        for t in TALHOES_MODELO:
            talhao, _ = Talhao.objects.get_or_create(
                propriedade=prop,
                nome=t["nome"],
                defaults={
                    "area_hectare": t["area"],
                    "tipo_solo": t["tipo_solo"],
                    "ativo": True,
                },
            )
            # vincula cultura_atual
            if t["cultura_nome"] == "Soja":
                talhao.cultura_atual = soja
            elif t["cultura_nome"] == "Milho":
                talhao.cultura_atual = milho
            elif t["cultura_nome"] == "Brachiaria":
                talhao.cultura_atual = brachiaria
            talhao.save()
            # geometria GeoJSON simples (polígono deslocado)
            from app.models import TalhaoGeometria

            if not hasattr(talhao, "geometria"):
                idx = TALHOES_MODELO.index(t)
                lat0 = float(FAZENDA_MODELO["lat"]) + idx * 0.04
                lon0 = float(FAZENDA_MODELO["lon"]) + idx * 0.03
                d = 0.015
                geojson = {
                    "type": "Feature",
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [
                            [
                                [lon0, lat0],
                                [lon0 + d, lat0],
                                [lon0 + d, lat0 + d],
                                [lon0, lat0 + d],
                                [lon0, lat0],
                            ]
                        ],
                    },
                    "properties": {"nome": t["nome"]},
                }
                TalhaoGeometria.objects.create(
                    talhao=talhao,
                    geojson=geojson,
                    area_calculada_ha=t["area"],
                    centroide_lat=lat0 + d / 2,
                    centroide_lon=lon0 + d / 2,
                )

        # Culturas na propriedade
        prop.culturas.set([soja, milho, brachiaria])

        # Estação Meteo
        from app.models import EstacaoMeteo

        est, _ = EstacaoMeteo.objects.get_or_create(
            propriedade=prop,
            nome=f"Estação {prop.nome}",
            defaults={
                "latitude": FAZENDA_MODELO["lat"],
                "longitude": FAZENDA_MODELO["lon"],
                "ativa": True,
                "codigo_inmet": "A913",
            },
        )

        # Safras que batem
        talhao_a = Talhao.objects.get(propriedade=prop, nome="Talhão A - Soja")
        talhao_b = Talhao.objects.get(
            propriedade=prop, nome="Talhão B - Milho Safrinha"
        )
        Safra.objects.get_or_create(
            propriedade=prop,
            talhao=talhao_a,
            cultura=soja,
            ano=2024,
            defaults={
                "safra_nome": "2024/25",
                "area_plantada": Decimal("420.00"),
                "area_colhida": Decimal("418.00"),
                "producao_total": Decimal("27300"),
                "produtividade": Decimal("65.30"),
                "receita_estimada": Decimal("4200000"),
                "data_plantio": date(2024, 10, 15),
                "data_colheita": date(2025, 2, 20),
            },
        )
        Safra.objects.get_or_create(
            propriedade=prop,
            talhao=talhao_b,
            cultura=milho,
            ano=2025,
            defaults={
                "safra_nome": "Safrinha 2025",
                "area_plantada": Decimal("380.00"),
                "area_colhida": Decimal("375.00"),
                "producao_total": Decimal("28500"),
                "produtividade": Decimal("75.00"),
                "receita_estimada": Decimal("3100000"),
                "data_plantio": date(2025, 2, 28),
                "data_colheita": date(2025, 6, 20),
            },
        )

        # Maquinário com telemetria
        Maquinario.objects.get_or_create(
            propriedade=prop,
            nome="Trator John Deere 8R 340",
            defaults={
                "tipo": "TRATOR",
                "marca": "John Deere",
                "modelo": "8R 340",
                "ano_fabricacao": 2023,
                "horas_uso": Decimal("1240.5"),
                "ativo": True,
            },
        )
        Maquinario.objects.get_or_create(
            propriedade=prop,
            nome="Colheitadeira S790",
            defaults={
                "tipo": "COLHEITADEIRA",
                "marca": "John Deere",
                "modelo": "S790",
                "ano_fabricacao": 2024,
                "horas_uso": Decimal("420.0"),
                "ativo": True,
            },
        )

        # Animal
        Animal.objects.get_or_create(
            propriedade=prop,
            especie="BOVINO",
            raca="Nelore",
            defaults={
                "tipo_producao": "CORTE",
                "quantidade": 120,
                "peso_medio": Decimal("420.00"),
            },
        )

        # Insumos / Estoque / Financeiro demo realista
        Insumo.objects.get_or_create(
            propriedade=prop,
            nome="Semente Soja Intacta 80K",
            defaults={
                "categoria": "SEMENTE",
                "quantidade": Decimal("420"),
                "unidade": "sc",
                "valor_unitario": Decimal("380"),
            },
        )
        Insumo.objects.get_or_create(
            propriedade=prop,
            nome="Fertilizante 04-14-08",
            defaults={
                "categoria": "FERTILIZANTE",
                "quantidade": Decimal("80"),
                "unidade": "t",
                "valor_unitario": Decimal("2850"),
            },
        )
        EstoqueItem.objects.get_or_create(
            propriedade=prop,
            nome="Soja Granel Armazém 1",
            defaults={
                "categoria": "PRODUTO",
                "quantidade": Decimal("540"),
                "unidade": "t",
                "local": "Armazém Central",
            },
        )
        LancamentoFinanceiro.objects.get_or_create(
            propriedade=prop,
            tipo="RECEITA",
            categoria="VENDA_PROD",
            valor=Decimal("1850000"),
            data=date(2025, 3, 10),
            defaults={"descricao": "Venda Soja 2024/25 - 12.500 sc"},
        )
        LancamentoFinanceiro.objects.get_or_create(
            propriedade=prop,
            tipo="DESPESA",
            categoria="INSUMO",
            valor=Decimal("420000"),
            data=date(2024, 10, 5),
            defaults={"descricao": "Compra insumos safra 2024/25"},
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Seed MVP Demo OK - {prop.nome} ({prop.talhoes.count()} talhões, {prop.safras.count()} safras)"
            )
        )

        # Telemetria para esta propriedade (gateways/devices + dados)
        if opts["with_telemetry"]:
            from django.core.management import call_command

            call_command("seed_telemetry", propriedade=prop.id, verbosity=0)
            call_command(
                "sync_inmet",
                propriedade=prop.id,
                horas=24,
                source="open-meteo",
                verbosity=0,
            )
            # garante 24h simulados extras já vem do seed_telemetry
            self.stdout.write(
                self.style.SUCCESS(
                    "Telemetria real (Open-Meteo 24h) sincronizada para Fazenda Modelo"
                )
            )
        else:
            # pelo menos garante devices existem
            from django.core.management import call_command

            call_command("seed_telemetry", propriedade=prop.id, verbosity=0)
            self.stdout.write(
                "Devices/ gateways criados (sem sync - rode --with-telemetry para dados reais)"
            )

        # Servidor demo: mecânico (exemplo do enunciado)
        from app.models import Funcionario

        func_mec, _ = Funcionario.objects.get_or_create(
            propriedade=prop,
            nome="Carlos Mecânico Demo",
            defaults={
                "cargo": "OUTRO",
                "salario": Decimal("3800"),
                "data_admissao": date(2024, 1, 15),
                "ativo": True,
                "nome_fazenda_login": prop.nome,
                "telefone": "(66) 99999-0001",
                "email": "mecanico@ampliagro.local",
            },
        )
        # garante nome_fazenda
        if not func_mec.nome_fazenda_login:
            func_mec.nome_fazenda_login = prop.nome
            func_mec.save()
        user_mec, created_mec = User.objects.get_or_create(
            username="mecanico.demo",
            defaults={"email": "mecanico@ampliagro.local", "first_name": "Carlos"},
        )
        if created_mec or not user_mec.check_password("mec123"):
            user_mec.set_password("mec123")
            user_mec.save()
        PerfilUsuario.objects.update_or_create(
            user=user_mec,
            defaults={
                "tipo_usuario": "servidor",
                "area_servidor": "MECANICA",
                "propriedade_vinculada": prop,
                "funcionario": func_mec,
                "vinculado_por": user,
                "ativo_servidor": True,
                "permissoes": {
                    "paginas": [
                        "estoque_mecanico",
                        "agenda_revisao",
                        "lista_tarefas",
                        "maquinario",
                    ],
                    "pode_criar": True,
                    "pode_editar": True,
                    "pode_ver_financeiro": False,
                },
            },
        )
        func_mec.user = user_mec
        func_mec.save()
        # estoque de mecânica para o dashboard
        EstoqueItem.objects.get_or_create(
            propriedade=prop,
            nome="Filtro Óleo JD 8R",
            defaults={
                "categoria": "PECA",
                "quantidade": Decimal("8"),
                "unidade": "un",
                "local": "Oficina",
            },
        )
        EstoqueItem.objects.get_or_create(
            propriedade=prop,
            nome="Correia S790",
            defaults={
                "categoria": "PECA",
                "quantidade": Decimal("3"),
                "unidade": "un",
                "local": "Oficina",
            },
        )
        EstoqueItem.objects.get_or_create(
            propriedade=prop,
            nome="Óleo 15W40",
            defaults={
                "categoria": "PECA",
                "quantidade": Decimal("60"),
                "unidade": "L",
                "local": "Oficina",
            },
        )
        # garante agenda de revisão visível (ajusta próxima manutenção)
        from datetime import timedelta as _td

        for maq in Maquinario.objects.filter(propriedade=prop):
            if not maq.proxima_manutencao:
                maq.proxima_manutencao = date.today() + _td(
                    days=15 if "Trator" in maq.nome else 30
                )
                maq.save(update_fields=["proxima_manutencao"])

        self.stdout.write(
            self.style.SUCCESS(
                "\nPronto para apresentação:\n"
                "  PRODUTOR: demo / demo123  -> /  (gestão completa)\n"
                '  SERVIDOR MECÂNICO: mecanico.demo / mec123 + Fazenda "Fazenda Modelo - Primavera do Leste"\n'
                '    -> selecione "Servidor" no login, informe fazenda, entre -> /servidor/ (mecânica: estoque, agenda, tarefas)\n'
                '  Login 1-clique: botão Demo na tela de login (class="actions") ou /demo/\n'
                "  demo.bat lança produtor direto logado\n"
            )
        )
