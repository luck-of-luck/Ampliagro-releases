"""PROFILING TEMPORARIO (nao commitar) - conta queries por endpoint."""

import time
import traceback
from collections import Counter

import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext


@pytest.mark.django_db
def test_perf_probe(client):
    User = get_user_model()
    u = User.objects.create_user(username="perfprobe", password="x")
    c = Client()
    c.force_login(u)

    ENDPOINTS = [
        "/api/dashboard/",
        "/api/notificacoes/",
        "/api/agenda/",
        "/api/agenda-producao/",
        "/api/custos/producao/",
    ]
    out = []
    for ep in ENDPOINTS:
        with CaptureQueriesContext(connection) as ctx:
            t0 = time.perf_counter()
            r = c.get(ep)
            dt = time.perf_counter() - t0
        q = len(ctx.captured_queries)
        sql = sum(float(x.get("time", 0) or 0) for x in ctx.captured_queries)
        out.append(
            f"{ep:30s} HTTP {r.status_code} q={q:4d} wall={dt * 1000:8.1f}ms sql={sql * 1000:7.1f}ms"
        )
        norm = Counter(" ".join(x["sql"].split())[:115] for x in ctx.captured_queries)
        for n, s in sorted(((n, s) for s, n in norm.items() if n > 2), reverse=True)[
            :6
        ]:
            out.append(f"     {n:4d}x  {s}")
    print("\n".join(out))


@pytest.mark.django_db
def test_perf_traceback(client):
    """De ONDE vem o N+1 e o que trava o dashboard (stack + timings)."""
    import traceback

    from app.models import (
        Animal,
        Cultura,
        Funcionario,
        Maquinario,
        Propriedade,
        Safra,
        Talhao,
    )

    from datetime import date

    User = get_user_model()
    u = User.objects.create_user(username="perftb", password="x")
    p = Propriedade.objects.create(
        user=u,
        nome="Fazenda TB",
        cidade="Campo Verde",
        uf="MT",
        area_total=1000,
    )
    cult = Cultura.objects.first() or Cultura.objects.create(nome="Soja")
    for i in range(60):
        t = Talhao.objects.create(
            propriedade=p, nome=f"T{i}", area_hectare=float(i + 1)
        )
        for a in range(2):
            Safra.objects.create(
                propriedade=p,
                talhao=t,
                ano=2025 + a,
                safra_nome=f"S{i}-{a}",
                cultura=cult,
                area_plantada=10.0,
            )
    Funcionario.objects.create(
        propriedade=p,
        nome="F1",
        ativo=True,
        salario=1000,
        data_admissao=date(2024, 1, 1),
    )
    for i in range(10):
        Maquinario.objects.create(
            propriedade=p, nome=f"M{i}", tipo="tractor", ativo=True
        )
    Animal.objects.create(propriedade=p, especie="bovino", quantidade=10)

    c = Client()
    c.force_login(u)

    # ---- 1. N+1: captura stack da query repetida de app_propriedade
    from django.conf import settings
    from django.db import connection, reset_queries

    settings.DEBUG = True
    from django.test.utils import CaptureQueriesContext

    # MEDIDO 2026-10-05. Esta linha falhava com `KeyError: 'stack'`, e a causa
    # NAO e' uma opcao mal posta — e' remocao a partir da propria biblioteca.
    #
    # O registo de cada query era `{'sql': ..., 'time': ...}`. A chave `stack`
    # existiu no Django antigo e **nao existe no Django 5.2**: verificado por
    # `inspect.signature(CaptureQueriesContext.__init__)` -> `(self, connection)`,
    # sem `force_debug_cursor` nem `stack`, e por leitura do pacote — nenhuma
    # das 120 ocorrencias de "stack" no `django/` e' o registo de uma query.
    #
    # Passar um `force_debug_cursor=True` que nao existe no construtor, ou
    # devolver um `stack` vazio, seriam os dois remendos errados: o primeiro
    # levanta `TypeError` (foi o que aconteceu), e o segundo engole o N+1 que
    # esta sonda existe para mostrar.
    #
    # A via suportada e' `connection.execute_wrapper`, que recebe a **funcao de
    # execucao**: e' o ponto onde o `exc_info` ainda tem a cadeia de chamadas
    # vive. E' mais honesto que ler um `stack` gravado — diz onde foi, ao
    # momento de foi.
    stacks = []

    def _com_stack(execute, sql, params, many, context):
        # `exc_info` e' o traceback VIVO, tirado antes de a query correr.
        stacks.append((sql, traceback.format_exc()))
        return execute(sql, params, many, context)

    settings.DEBUG = True
    from django.db import connection

    with connection.execute_wrapper(_com_stack):
        r = c.get("/api/agenda-analises/")
    print(
        "\n===== AGENDA-ANALISES: q=",
        len(ctx.captured_queries) if False else len(stacks),
    )
    vistas = 0
    for sql, st in stacks:
        if sql.count("app_propriedade") >= 1 and "id" in sql:
            print("SQL:", " ".join(sql.split())[:130])
            print("STACK:")
            linhas = [l for l in st.splitlines() if "Ampliagro" in l]
            for line in linhas[-14:]:
                print("   ", line.strip())
            vistas += 1
            if vistas >= 1:
                break

    # ---- 2. Dashboard: onde vai o tempo? (timing por chamada externa)
    reset_queries()
    orig_fetch = None
    tempos = []

    import app.ia.fontes as fontes_mod

    orig = fontes_mod.fetch_permitido

    def cronometrado(*a, **k):
        t0 = time.perf_counter()
        try:
            return orig(*a, **k)
        finally:
            tempos.append((time.perf_counter() - t0, a[0] if a else ""))

    fontes_mod.fetch_permitido = cronometrado
    try:
        from django.core.cache import cache

        cache.clear()
        t0 = time.perf_counter()
        r = c.get("/api/dashboard/")
        wall = time.perf_counter() - t0
    finally:
        fontes_mod.fetch_permitido = orig

    print(f"\n===== DASHBOARD wall={wall * 1000:.0f}ms")
    print(f"chamadas externas (fetch_permitido): {len(tempos)}")
    for dt, url in sorted(tempos, reverse=True)[:10]:
        print(f"   {dt * 1000:8.1f}ms  {url}")
    if not tempos:
        print("   (nenhuma) -> tempo esta em outro lugar")
    """Mede N+1 com dados reais: cria propriedade + talhoes + safras e repete."""
    from app.models import (
        Animal,
        Cultura,
        Funcionario,
        Maquinario,
        Propriedade,
        Safra,
        Talhao,
    )

    User = get_user_model()
    u = User.objects.create_user(username="perfprobe2", password="x")
    p = Propriedade.objects.create(
        user=u,
        nome="Fazenda Perf",
        cidade="Campo Verde",
        uf="MT",
        area_total=1000,
    )
    cult = Cultura.objects.first() or Cultura.objects.create(nome="Soja")
    for i in range(60):
        t = Talhao.objects.create(
            propriedade=p, nome=f"T{i}", area_hectare=float(i + 1)
        )
        for a in range(2):
            Safra.objects.create(
                propriedade=p,
                talhao=t,
                ano=2025 + a,
                safra_nome=f"S{i}-{a}",
                cultura=cult,
                area_plantada=10.0,
            )
    from datetime import date

    Funcionario.objects.create(
        propriedade=p,
        nome="F1",
        ativo=True,
        salario=1000,
        data_admissao=date(2024, 1, 1),
    )
    for i in range(10):
        Maquinario.objects.create(
            propriedade=p, nome=f"M{i}", tipo="tractor", ativo=True
        )
    Animal.objects.create(propriedade=p, especie="bovino", quantidade=10)

    c = Client()
    c.force_login(u)
    out = []
    for ep in [
        "/api/dashboard/",
        "/api/notificacoes/",
        "/api/agenda/",
        "/api/agenda-producao/",
        "/api/agenda-analises/",
        "/api/custos-producao/",
        "/api/safras/",
        "/api/talhoes/",
    ]:
        try:
            with CaptureQueriesContext(connection) as ctx:
                t0 = time.perf_counter()
                r = c.get(ep)
                dt = time.perf_counter() - t0
            out.append(
                f"{ep:30s} HTTP {r.status_code} q={len(ctx.captured_queries):4d} "
                f"wall={dt * 1000:8.1f}ms"
            )
            norm = Counter(
                " ".join(x["sql"].split())[:110] for x in ctx.captured_queries
            )
            for n, s in sorted(
                ((n, s) for s, n in norm.items() if n > 3), reverse=True
            )[:8]:
                out.append(f"     {n:4d}x  {s}")
        except Exception as e:
            out.append(f"{ep:30s} ERRO {type(e).__name__}: {e}")
    print("\n".join(out))
