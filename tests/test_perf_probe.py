"""Sonda de performance: MEDE queries por endpoint. Nao altera o produto.

Corre com:
    python -m pytest tests/test_perf_probe.py -s --no-cov -p no:cacheprovider

Cria uma propriedade com N lancamentos e mede quantas queries cada endpoint
dispara, e quantas dessas sao N+1 (ou seja, queries que crescem com N).
"""

from datetime import date, timedelta

import pytest
from django.contrib.auth.models import User
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

pytestmark = pytest.mark.django_db


N_LANC = 200  # volume que um produtor de um ano inteiro gera


def _cenario():
    from app.models import LancamentoFinanceiro, Propriedade

    user = User.objects.create_user(username="perfprobe", password="x12345678")
    prop = Propriedade.objects.create(
        user=user, nome="Fazenda Perf", area_total=500, cidade="Londrina", uf="PR"
    )
    base = date.today() - timedelta(days=400)
    LancamentoFinanceiro.objects.bulk_create(
        [
            LancamentoFinanceiro(
                propriedade=prop,
                tipo="RECEITA" if i % 3 else "DESPESA",
                valor=100 + i,
                categoria="TESTE",
                data=base + timedelta(days=i % 380),
                descricao=f"lanc {i}",
            )
            for i in range(N_LANC)
        ],
        batch_size=100,
    )
    return user, prop


def _medir(cli, url):
    with CaptureQueriesContext(connection) as ctx:
        r = cli.get(url)
    return r.status_code, len(ctx.captured_queries), ctx.captured_queries


def _tabelas(qs):
    """Conta queries por tabela alvo — evidencia o N+1."""
    from collections import Counter

    c = Counter()
    for q in qs:
        sql = q["sql"]
        for t in (
            "lancamentos",
            "propriedades",
            "talhoes",
            "safras",
            "cultura",
            "estoque",
            "maquinarios",
            "funcionarios",
            "perfilusuario",
            "notificacoes",
            "auth_user",
            "animals",
        ):
            if f'"{t}"' in sql or f" {t} " in sql:
                c[t] += 1
                break
        else:
            c["<outra>"] += 1
    return c


def test_probe_queries_por_endpoint(capsys):
    user, prop = _cenario()
    cli = Client()
    cli.force_login(user)

    endpoints = [
        "/api/dashboard/",
        "/api/widget-data/",
        "/api/funcionarios-resumo/",
        "/api/notificacoes/",
    ]

    print("\n" + "=" * 74)
    print(f"PERF PROBE — {N_LANC} lancamentos, 1 propriedade")
    print("=" * 74)

    for url in endpoints:
        # 1a chamada e' a que paga a cache (se houver).
        with CaptureQueriesContext(connection) as ctx:
            r = cli.get(url)
        qs = ctx.captured_queries
        tempo = sum(float(q["time"]) for q in qs) * 1000
        tabs = _tabelas(qs)
        print(f"\n{url}")
        print(f"  status={r.status_code}  queries={len(qs)}  sql_time={tempo:.1f}ms")
        for t, n in tabs.most_common(6):
            print(f"    {n:>4}x  {t}")

        # 2a chamada: o que a cache de 30s absorve.
        with CaptureQueriesContext(connection) as ctx2:
            cli.get(url)
        print(f"  2a chamada (cache): {len(ctx2.captured_queries)} queries")
        if len(ctx2.captured_queries) < len(qs):
            print("  >> CACHE FUNCIONA")
        else:
            print("  >> SEM CACHE: cada chamada refaz tudo")

    print("=" * 74)
    print("\nSQL DETALHADO — /api/dashboard/ (1a chamada, cache vazia)")
    from django.core.cache import cache as dj_cache

    dj_cache.clear()
    with CaptureQueriesContext(connection) as ctx:
        cli.get("/api/dashboard/")
    for i, q in enumerate(ctx.captured_queries, 1):
        sql = " ".join(q["sql"].split())
        print(f"  {i:>3}. {sql[:135]}")
    print("=" * 74)


def test_probe_template_dashboard():
    """Mede queries do HTML do dashboard (nao da API)."""
    user, prop = _cenario()
    cli = Client()
    cli.force_login(user)
    import gzip

    with CaptureQueriesContext(connection) as ctx:
        r = cli.get("/")
    qs = ctx.captured_queries
    tempo = sum(float(q["time"]) for q in qs) * 1000
    corpo = r.content
    gz = gzip.compress(corpo, 6)
    html = corpo.decode("utf-8", "replace")

    # Quantos <script src> o browser tem de descarregar em paralelo extra.
    externos = len(__import__("re").findall(r"<script[^>]*\ssrc=", html))
    inline = len(__import__("re").findall(r"(?s)<script(?![^>]*\ssrc=)[^>]*>", html))
    links = len(__import__("re").findall(r"<link[^>]*\shref=", html))

    print("\n" + "=" * 74)
    print("TEMPLATE / (HTML do dashboard) — PAYLOAD")
    print(f"  status={r.status_code}")
    print(f"  queries={len(qs)}  sql_time={tempo:.1f}ms")
    print(f"  HTML bruto={len(corpo) / 1024:.1f} KB   gzip={len(gz) / 1024:.1f} KB")
    print(f"  <script src>={externos}  <link href>={links}  blocos inline={inline}")

    print(f"  encoding resposta={r.headers.get('Content-Encoding')!r}")
    print("=" * 74)


def test_probe_indices_e_gzip():
    """Confere indice nas tabelas mais consultadas + se o gzip e' aplicado."""
    from app.models import (
        EstoqueItem,
        Funcionario,
        LancamentoFinanceiro,
        Maquinario,
        Propriedade,
        Safra,
    )

    print("\n" + "=" * 74)
    print("INDICES NAS TABELAS DO CAMINHO QUENTE")
    print("=" * 74)
    for m in (
        Propriedade,
        LancamentoFinanceiro,
        Maquinario,
        Safra,
        EstoqueItem,
        Funcionario,
    ):
        # MEDIDO 2026-10-05: era `i["name"]`, que levanta
        # `TypeError: 'Index' object is not subscriptable`. Um `django.db.models.Index`
        # e' um objecto com atributos — o nome vive em `i.name`. Subscriptar
        # um objecto que nao implementa `__getitem__` nunca funcionou; o teste
        # morria na recolha de nomes, antes de olhar para indice nenhum.
        idx = [i.name for i in m._meta.indexes]
        fks = [f.name for f in m._meta.fields if f.is_relation and not f.primary_key]
        fk_com_idx = [f.name for f in m._meta.fields if f.is_relation and f.db_index]
        print(f"\n  {m.__name__}")
        print(f"    FKs: {fks or '(nenhuma)'}")
        print(f"    Meta.indexes: {idx or '(nenhum)'}")
        print(f"    FK com db_index: {fk_com_idx or '(nenhum)'}")

    user, prop = _cenario()
    cli = Client()
    cli.force_login(user)
    sem = cli.get("/")
    com = cli.get("/", headers={"accept-encoding": "gzip, deflate"})
    print("\n" + "-" * 74)
    print(
        f"GET /  sem accept-encoding : {len(sem.content) / 1024:8.1f} KB  "
        f"enc={sem.headers.get('Content-Encoding')}"
    )
    print(
        f"GET /  com accept-encoding : {len(com.content) / 1024:8.1f} KB  "
        f"enc={com.headers.get('Content-Encoding')}"
    )
    print("=" * 74)


def test_probe_n_plus_1_cresce_com_dados():
    """A prova decisive: duplica os lancamentos e compara.

    Se o numero de queries NAO muda, nao ha N+1 neste endpoint — o custo
    cresce so o tempo de agregacao, o que e' aceitavel.
    """
    from app.models import LancamentoFinanceiro, Propriedade

    def _montar(n):
        user = User.objects.create_user(username=f"probe{n}", password="x12345678")
        prop = Propriedade.objects.create(
            user=user, nome=f"F{n}", area_total=100, cidade="Londrina", uf="PR"
        )
        base = date.today() - timedelta(days=380)
        LancamentoFinanceiro.objects.bulk_create(
            [
                LancamentoFinanceiro(
                    propriedade=prop,
                    tipo="RECEITA" if i % 2 else "DESPESA",
                    valor=10,
                    categoria="T",
                    data=base + timedelta(days=i % 380),
                )
                for i in range(n)
            ],
            batch_size=200,
        )
        return user

    print("\n" + "=" * 74)
    print("N+1: 2x os dados faz o numero de queries crescer?")
    print("=" * 74)
    for n in (50, 400):
        u = _montar(n)
        c = Client()
        c.force_login(u)
        for url in ("/api/dashboard/", "/api/widget-data/"):
            with CaptureQueriesContext(connection) as ctx:
                c.get(url)
            print(
                f"  n={n:>4} lancamentos -> {len(ctx.captured_queries):>4} queries  {url}"
            )
    print("=" * 74)
