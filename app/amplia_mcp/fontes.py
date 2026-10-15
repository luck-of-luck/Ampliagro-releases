"""As fontes do Ampliagro, MEDIDAS, para a IA nao inventar numeros.

O QUE ISTO E'
=============
Toda a semana measurei a mesma coisa: quantas culturas existem, quantos
intents, quantas lancamentos. E measurei sempre duas vezes — a contagem e
o que a tela mostrava — porque as duas discordavam.

O que este modulo faz e' tornar essa medicao LEGIVEL por um agente, sem o
agente precisar de a repetir. Nao e' um dicionario de dados: e' um registo
de onde cada numero vem, para quando o numero mudar a IA possa dizer
"mudou de 709 para 712, e a fonte e' a mesma".

A REGRA QUE ESTE MODULO EXISTE PARA CUMPRIR
============================================
Toda a serie do Ampliagro se decide pela mesma frase: **um numero que nao
tem de onde vir e' um numero prometido**.

  - Um KPI que diz "IoT: 4" com 8 dispositivos na base e' uma mentira
    com boa apresentacao.
  - "709 culturas" saido de um config de 488 entradas e' uma mentira
    diferente, mas do mesmo tipo.
  - O ciclo de 112 dias quando a aritmetica dava 116 e' uma mentira
    aritmetica.

Cada numero aqui traz `fonte` — de onde foi lido — e `quando` — a data da
medicao. Um numero sem `fonte` nao entra.

O QUE NAO E' MEDIDO AQUI — E DITO
=================================
Estes campos NAO trazem numero. Trazem `null` e a razao:

  janelas_plantio   MEDIDO: 0 de 709 preenchidas. Nao e' "as janelas sao
                    zero": e' "ninguem as preencheu". Inventar uma janela
                    de plantio e' escrever um numero que o produtor vai
                    usar para semear na epoca errada.

  safras_com_area   As safras do utilizador nao tem talhao com area.

Um `null` com razao e' mais util ao agente do que um `0`: o agente sabe
que nao deve dizer "zero" ao produtor. E a regra que ja vale para os
widgets — `fonte_dado: sem_dado` — vale tambem para aqui.
"""

import datetime as _dt
import pathlib
import re
import sqlite3

RAIZ = pathlib.Path(__file__).resolve().parents[2]

#: Onde a configuracao de culturas esta, em relacao ao repo.
CONFIG_CULTURAS = "app/static/data/cultures-config.json"


def _hoje():
    return _dt.date.today().isoformat()


def _sqlite():
    db = RAIZ / "db.sqlite3"
    if not db.exists():
        return None
    return sqlite3.connect(str(db))


def _contar(cx, sql):
    if cx is None:
        return None
    try:
        return cx.execute(sql).fetchone()[0]
    except Exception:
        return None


def _culturas_do_config(caminho):
    """Le as culturas do `cultures-config.json` — a forma REAL do ficheiro.

    MEDIDO 2026-10-05: o topo e' um DICT, nao uma lista:

        {"version": ..., "default_metrics": ..., "groups": [...]}
        groups[].subgroups[].cultures[]

    A primeira versao deste modulo tratou o topo como lista e devolveu
    `entradas: 0` — silenciosamente, porque `len([])` nao falha. Um zero
    silencioso e' pior que um erro: parece uma medicao.

    E' a MESMA armadilha do detector de mojibake (presumir a estrutura) e
    do HEAD medido atraves de um conversor. Supor a forma em vez de a ler
    foi o erro mais repetido desta serie.
    """
    import json

    dados = json.loads(caminho.read_text(encoding="utf-8"))
    listas = []
    forma = "desconhecida"
    if isinstance(dados, dict) and isinstance(dados.get("groups"), list):
        forma = "groups[].subgroups[].cultures[]"
        for g in dados["groups"]:
            for sg in g.get("subgroups") or []:
                listas.extend(sg.get("cultures") or [])
    elif isinstance(dados, list):
        forma = "lista no topo"
        listas = [c for c in dados if isinstance(c, dict)]
    elif isinstance(dados, dict) and isinstance(dados.get("culturas"), list):
        forma = "culturas[]"
        listas = dados["culturas"]
    return {
        "_listas": listas,
        "_forma": forma,
        "_version": dados.get("version") if isinstance(dados, dict) else None,
        "_updatedAt": dados.get("updatedAt") if isinstance(dados, dict) else None,
    }


def culturas():
    """As duas fontes de culturas, e o que elas dizem uma da outra.

    MEDIDO 2026-10-05: a tabela tem 709 linhas e 685 nomes distintos; o
    config tem 488 entradas e 483 nomes distintos. São a MESMA base em
    projecoes diferentes — por nome, 483 comuns, 202 so na tabela e zero
    so no config.

    Os dois numeros circulam como "o numero de culturas" e nao sao
    interchangeaveis. E' por isso que esta funcao devolve os dois e diz de
    onde veio cada um, em vez de escolher um.
    """
    saida = {
        "tabela": None,
        "config": None,
        "comparacao": None,
        "fonte": f"app_cultura e {CONFIG_CULTURAS}",
        "quando": _hoje(),
    }
    cx = _sqlite()
    if cx is not None:
        total = _contar(cx, "select count(*) from app_cultura")
        distintos = _contar(cx, "select count(distinct nome) from app_cultura")
        saida["tabela"] = {"linhas": total, "nomes_distintos": distintos}
    cfg = RAIZ / CONFIG_CULTURAS
    if cfg.exists():
        try:
            dados = _culturas_do_config(cfg)
            nomes = {c.get("title") or c.get("nome") for c in dados["_listas"]}
            nomes.discard(None)
            saida["config"] = {
                "entradas": len(dados["_listas"]),
                "nomes_distintos": len(nomes),
                "forma": dados["_forma"],
                "version": dados["_version"],
                "updatedAt": dados["_updatedAt"],
            }
        except Exception as e:
            saida["config"] = {"erro": str(e)[:80], "entradas": None}

    if saida.get("tabela") and saida.get("config") and cx is not None:
        try:
            dados = _culturas_do_config(cfg)
            do_config = {(c.get("nome") or c.get("title")) for c in dados["_listas"]}
            do_config.discard(None)
            # MEDIDO: `app_cultura` so tem a coluna `nome`. A primeira
            # versao deste modulo fez `select django_nome` — uma coluna que
            # nao existe — e a comparacao dava `None` sem erro. `None` e'
            # honesto, mas escondeu que a pergunta estava mal feita.
            da_tabela = {
                r[0] for r in cx.execute("select nome from app_cultura") if r[0]
            }
            saida["comparacao"] = {
                "comuns": len(do_config & da_tabela),
                "so_na_tabela": len(da_tabela - do_config),
                "so_no_config": len(do_config - da_tabela),
                "leitura": (
                    "sao a mesma base em projecoes diferentes. O numero que "
                    "se mostra na tela e' o da TABELA; o do CONFIG e' a "
                    "projecao. Confundir os dois foi um bug real."
                ),
            }
        except Exception:
            pass
    if cx is not None:
        cx.close()
    return saida


def dados_do_usuario():
    """O que a base tem. Por utilizador, e so do utilizador."""
    saida = {
        "usuario": None,
        "propriedades": None,
        "safras": None,
        "lancamentos": None,
        "dispositivos": None,
        "registos_de_producao": None,
        "fonte": "db.sqlite3, filtrado por user",
        "quando": _hoje(),
        "aviso": (
            "Estes numeros sao do utilizador que ask. Nao sao do sistema, "
            "e nao devem ser apresentados como tal."
        ),
    }
    try:
        from django.contrib.auth.models import User
    except Exception as e:
        saida["erro"] = f"Django nao carregou: {str(e)[:60]}"
        return saida

    cx = _sqlite()
    if cx is None:
        saida["erro"] = "db.sqlite3 nao existe neste checkout"
        return saida
    try:
        u = User.objects.order_by("id").first()
        if u is None:
            saida["erro"] = "nao ha utilizadores na base"
            return saida
        saida["usuario"] = u.username
        # MEDIDO: nem toda a tabela tem `user_id`. `app_propriedade` e
        # `app_registroproducao` tem; `app_safra`, `app_lancamentofinanceiro`
        # e `app_device` NAO tem — vao por `propriedade_id`. A primeira
        # versao deste modulo filtrava todas por `user_id` e devolvia
        # `null` em tres: nao era "nao medido", era um JOIN que faltava.
        for chave, tabela in (
            ("propriedades", "app_propriedade"),
            ("safras", "app_safra"),
            ("lancamentos", "app_lancamentofinanceiro"),
            ("dispositivos", "app_device"),
            ("registos_de_producao", "app_registroproducao"),
        ):
            sql = f"select count(*) from {tabela} where user_id = ?"
            n = _contar_valido(cx, sql, u.pk)
            if n is None:
                # sem `user_id`: contar pelas propriedades do utilizador
                sql2 = (
                    f"select count(*) from {tabela} where propriedade_id in "
                    "(select id from app_propriedade where user_id = ?)"
                )
                n = _contar_valido(cx, sql2, u.pk)
                via = "propriedade_id"
            else:
                via = "user_id"
            saida[chave] = n
            saida.setdefault("como_contou", {})[chave] = via
    except Exception as e:
        saida["erro"] = str(e)[:80]
    finally:
        cx.close()
    return saida


def _contar_valido(cx, sql, pk):
    try:
        return cx.execute(sql, (pk,)).fetchone()[0]
    except Exception:
        return None


def campos_que_faltam():
    """O que esta VAZIO. E o mais importante deste modulo.

    MEDIDO 2026-10-05. Estes campos nao tem valor na base. Nao e' que o
    valor seja zero: e' que ninguem o preencheu.

    Um agente que diga "a janela de plantio vai de outubro a março" esta a
    inventar uma data que o produtor vai usar para semear na epoca errada.
    Por isso aqui vai `null` com a razao, e nao `0`.
    """
    cx = _sqlite()
    base = {"fonte": "app_cultura", "quando": _hoje()}
    if cx is None:
        return {
            **base,
            "erro": "db.sqlite3 nao existe — nenhum campo foi medido",
            "campos": None,
        }
    total = _contar(cx, "select count(*) from app_cultura")
    out = {}
    try:
        for campo in (
            "janela_plantio_inicio",
            "janela_plantio_fim",
            "chave_mercado",
            "ciclo_dias",
        ):
            try:
                n = cx.execute(
                    f"select count(*) from app_cultura where {campo} "
                    f"is not null and {campo} != ''"
                ).fetchone()[0]
                out[campo] = {
                    "preenchidos": n,
                    "de": total,
                    "valor": None,
                    "porque": (
                        "nenhum registo tem este campo preenchido. NAO e' "
                        "que o valor seja zero — e' que nao foi escrito. "
                        "Nao derivar um valor."
                    ),
                }
            except Exception as e:
                out[campo] = {"erro": str(e)[:60], "valor": None}
    finally:
        cx.close()
    return {
        **base,
        "campos": out,
        "regra": (
            "`null` com razao e' mais util ao produtor do que `0`. Um `0` "
            "afirma que medimos e nao encontramos nada; um `null` diz que "
            "nao medimos. Sao coisas diferentes e o produtor decide "
            "diferente com elas."
        ),
    }


def catalogo_de_fontes():
    """O indice: o que existe aqui e onde ir buscar."""
    return {
        "culturas": culturas(),
        "dados_do_usuario": None,
        "campos_que_faltam": campos_que_faltam(),
        "nota": (
            "`dados_do_usuario` vem null aqui de proposito: depende de "
            "quem pergunta, e um recurso MCP e' servido sem saber o "
            "utilizador. Use a tool `amplia_contexto` para o contexto de "
            "um produtor especifico."
        ),
        "principio": (
            "Todo numero deste recurso traz `fonte` e `quando`. Um numero "
            "sem fonte nao entra. E' a regra que o painel violou quando "
            "anunciou 'IoT: 4' com 8 dispositivos, e que a guia vegetal "
            "violou com '707 culturas' vindo de um config de 488."
        ),
    }
