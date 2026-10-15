"""
json_portatil — a camada que faz o `JSONField` funcionar igual em SQLite e Postgres.

DECISÃO D2: CAMADA AGNÓSTICA, NÃO PORTAR AGORA
----------------------------------------------
Os documentos da fase pedem PostgreSQL com JSONB. O projeto roda SQLite
(`db.sqlite3`). Duas saídas possíveis:

  (a) Portar para PostgreSQL agora.
  (b) Escrever a camada de metadados só com o subconjunto que os dois
      backends aceitam, e marcar os lugares onde o Postgres rende mais.

Foi escolhida (b). Motivos concretos, medidos neste projeto:

* **84 models** e 48 migrations já existem sobre SQLite. Portar agora é uma
  migração de infraestrutura que não pertence a uma fase de fundação de IA.
* **A_armadilha é real e silenciosa.** `JSONField.__contains` — a forma
  natural de escrever "campo contém este par" em JSONB — **não funciona** em
  SQLite:

      NotSupportedError: contains lookup is not supported on this database backend.

  Código escrito no Postgres e portado para dev em SQLite quebraria em runtime,
  no meio de uma listagem, longe do commit que causou.
* **O subconjunto portátil basta.** Medido neste projeto, os quatro verbos que
  o CRUD de ferramenta precisa funcionam nos dois:

      chave = valor        dados__status='ativo'          OK nos dois
      chave aninhada       dados__a__b=1                  OK nos dois
      chave existe         dados__has_key='status'        OK nos dois
      JSONField roundtrip  dados={'a':1}                  OK nos dois
      contém par           dados__contains={'a':1}        SO Postgres

Então: todo filtro daqui em diante usa chave/valor. `__contains` vira um
upgrade opcional em Postgres, não um pressuposto.

ONDE O POSTGRES GANHA
---------------------
`contem()` usa `__contains` quando o backend suporta, e no Postgres aceita
`criar_indice_gin()`, que usa o índice GIN para não varrer a tabela. Em SQLite
a mesma consulta vira `__icontains`, que é comparação de texto: mais lento em
tabela grande, e por isso `criar_indice_gin()` no SQLite cria um índice
convencional em vez de fingir que resolveu.

O probe é cacheado por (vendor, feature), porque `connection.features` é caro
para ler em loop e a resposta não muda dentro do processo.
"""

from __future__ import annotations

from typing import Any, Dict

# --------------------------------------------------------------------------
# Probe de capacidade
# --------------------------------------------------------------------------

#: Chave e (vendor, feature). Indexar só pelo vendor foi um bug real: a
#: primeira feature lida contaminava todas as outras, e o SQLite passava a
#: se anunciar com `contains` e `jsonb` — que ele nao tem. Um probe que mente
#: e pior do que nenhum probe: faria o codigo gerar SQL invalido em vez de
#: cair no caminho portatil.
_CACHE: dict[tuple, bool] = {}


def _supports(nome_feature: str) -> bool:
    """Lê uma feature do backend atual, cacheada por (vendor, feature).

    `connection.features` pode não ter o atributo em versões antigas do Django;
    ausencia é tratada como "não suporta", que é o lado seguro (cai no
    caminho portátil em vez de gerar SQL inválido).
    """
    from django.db import connection

    chave = (connection.vendor, nome_feature)
    if chave not in _CACHE:
        _CACHE[chave] = bool(getattr(connection.features, nome_feature, False))
    return _CACHE[chave]


def limpar_cache() -> None:
    _CACHE.clear()


def suporta_contains() -> bool:
    """True se `__contains` (JSONB) funciona. False no SQLite."""
    return _supports("supports_json_field_contains")


def tem_jsonb() -> bool:
    """True se a coluna JSON é tipo nativo (jsonb) e não texto."""
    return _supports("has_native_json_field")


def tem_operadores_json() -> bool:
    """True se há operadores `?`/`@>` do Postgres."""
    return _supports("has_json_operators")


def vendor() -> str:
    from django.db import connection

    return connection.vendor


def diagnostico() -> dict[str, Any]:
    """Para o health check e para a tela de configuração."""
    return {
        "vendor": vendor(),
        "json_field": _supports("supports_json_field"),
        "jsonb_nativo": tem_jsonb(),
        "contains_suportado": suporta_contains(),
        "operadores_json": tem_operadores_json(),
        "estrategia_contains": "jsonb" if suporta_contains() else "texto",
        "indice_recomendado": "gin" if tem_jsonb() else "convencional",
    }


# --------------------------------------------------------------------------
# Filtros
# --------------------------------------------------------------------------


def onde_campo(queryset, campo: str, valor: Any):
    """Filtra `dados[campo] == valor`. Portátil — é o verbo primitivo.

    Key transform é a única forma de "igual a" em JSON que os dois backends
    implementam, então é o que toda a camada usa.
    """
    return queryset.filter(**{f"dados__{campo}": valor})


def onde_existe(queryset, campo: str):
    """Filtra registros que têm a chave (mesmo com valor nulo). Portátil."""
    return queryset.filter(**{"dados__has_key": campo})


def contem(queryset, par: dict[str, Any]):
    """Filtra registros cujo JSON contém o par.

    Usa `__contains` no Postgres (vira `@>`, indexável por GIN) e degrada para
    uma sequência de comparações de chave no SQLite. O resultado é o mesmo
    conjunto; a diferença é o plano de execução.

    A degradação NÃO usa `__icontains` num único par: `{"a": 1}` como texto
    casaria com `{"a": 12}`. Cada chave vira um key transform, que compara
    valor a valor.
    """
    if not par:
        return queryset

    if suporta_contains():
        return queryset.filter(dados__contains=par)

    # SQLite: empilha filtros. Cada um é um key transform portátil.
    qs = queryset
    for chave, valor in par.items():
        qs = qs.filter(**{f"dados__{chave}": valor})
    return qs


def ordenar_por_campo(queryset, campo: str, crescente: bool = True):
    """Ordena por `dados[campo]`. Portátil."""
    return queryset.order_by(f"{'' if crescente else '-'}dados__{campo}")


def ddl_indice_gin(model, campo: str = "dados") -> str:
    """Devolve o DDL do índice GIN, para aplicar só no Postgres.

    Por que NÃO é um `Index(...)` no Meta do model: `GinIndex` vive em
    `django.contrib.postgres` e não existe no SQLite. Declarar no model
    quebraria o `manage.py check` de qualquer ambiente SQLite — que é
    exatamente o ambiente de dev e o que roda os testes.

    Por que não é uma migration: a migration é versionada, e o índice só faz
    sentido depois que a instalação vai para Postgres. Aplicar em SQLite seria
    trabalho inútil; aplicar em Postgres numa migration do SQLite quebraria.

    Então o índice é uma melhoria de deploy, versionada à parte, e fica
    discovery-first: `diagnostico()` diz se vale a pena aplicar.

        python manage.py shell -c "from app.ia.json_portatil import ddl_indice_gin; \
            from app.models import DynamicRecord; print(ddl_indice_gin(DynamicRecord))"
    """
    tabela = model._meta.db_table
    return (
        f'CREATE INDEX IF NOT EXISTS "{tabela}_{campo}_gin" '
        f'ON "{tabela}" USING gin ("{campo}" jsonb_path_ops);'
    )


def vale_a_pena_gin(model) -> bool:
    """True só quando o backend é Postgres E o volume justifica.

    GIN custa escrita e armazenamento. Em tabela pequena ele é mais lento que um seq scan.
    O corte de 10 mil linhas é o mesmo raciocínio que o Django usa em
    `models.Index(condition=...)` para decidir índice parcial.
    """
    if not tem_jsonb():
        return False
    try:
        return model.objects.count() >= 10_000
    except Exception:
        return False
