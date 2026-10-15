"""
Prova REAL contra o banco de desenvolvimento, sem mocks, com um usuario
criado de verdade. E a simulacao do roteiro que o enunciado descreve:

    produtor: "crie um controle de geladeira"
      IA:     cria_entidade(nome, campos)
    produtor: "coloca 12 kg de racao"
      IA:     inserir_registro(slug, {alimento, quantidade_kg})
    produtor: "quanto tem?"
      IA:     consultar_registros(slug)

e, no meio, o que um modelo de 1.7B faz de verdade: inventa um campo.

Este script NAO faz parte da suite (nao escreve em dados de ninguem). E uma
ferramenta de verificacao: `python docs/verificar_build2.py`.
"""

import os
import pathlib
import sys

# O script vive em docs/, entao sys.path[0] e' docs/ e `config` nao seria
# importavel. Uma ferramenta de verificacao tem de rodar de qualquer lugar.
RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
os.chdir(RAIZ)

import django  # noqa: E402

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
django.setup()

from django.contrib.auth.models import User  # noqa: E402

from app.amplia_mcp import executar_para  # noqa: E402
from app.models import DynamicRecord  # noqa: E402

OK, ERRO = "  ok  ", " FALHA"


def linha(t):
    print("\n" + "=" * 72)
    print(t)
    print("=" * 72)


def checa(nome, cond, detalhe=""):
    print(
        f"[{OK if cond else ERRO}] {nome}"
        + (f"  -> {detalhe}" if detalhe and not cond else "")
    )
    return cond


resultado = True

# ---------------------------------------------------------------- 1. o produtor
linha("1. O produtor cria a conta e pede uma ferramenta que nao existe")

ana = User.objects.create_user("build2_ana", "build2@exemplo.com", "p")
print(f"  usuario: {ana.username}")

r = executar_para(
    ana,
    "amplia_criar_entidade",
    {
        "nome": "Controle de Geladeira",
        "descricao": "O que tem na geladeira e quanto",
        "campos": [
            {"rotulo": "Alimento", "tipo": "TEXTO", "obrigatorio": True},
            {"rotulo": "Quantidade kg", "tipo": "DECIMAL", "obrigatorio": False},
        ],
    },
)
resultado &= checa("sem confirmacao, a IA nao grava", r.get("needs_confirm") is True, r)
print(f"  a IA diz: {r.get('resposta', '')[:100]}")

# ------------------------------------------------------- 2. o produtor confirma
linha("2. O produtor confirma")

r = executar_para(
    ana,
    "amplia_criar_entidade",
    {
        "nome": "Controle de Geladeira",
        "descricao": "O que tem na geladeira e quanto",
        "campos": [
            {"rotulo": "Alimento", "tipo": "TEXTO", "obrigatorio": True},
            {"rotulo": "Quantidade kg", "tipo": "DECIMAL", "obrigatorio": False},
        ],
        "confirm": True,
    },
)
slug = (r.get("dados") or {}).get("slug", "")
resultado &= checa("ferramenta criada", r.get("ok") and bool(slug), r)
print(f"  slug: {slug}")
print(f"  a IA le: {r.get('resposta', '')[:150]}")

# ------------------------------------------- 3. o modelo ALUCINA um campo
linha("3. O produtor manda 12 kg. O modelo inventa um campo (o caso real)")

r = executar_para(
    ana,
    "amplia_inserir_registro",
    {
        "entity_slug": slug,
        "dados": {"alimento": "Racao", "quantidade_kg": 12, "idade_da_vaca": 10},
        "confirm": True,
    },
)
resultado &= checa("gravacao RECUSADA", r.get("ok") is False, r)
resultado &= checa(
    "o erro nomeia o campo inventado",
    "idade_da_vaca" in str(r.get("erro", "")),
    r.get("erro"),
)
resultado &= checa(
    "o erro lista os campos validos (o modelo consegue corrigir)",
    "alimento" in str(r.get("erro", "")) and "quantidade_kg" in str(r.get("erro", "")),
    r.get("erro"),
)
print(f"  a IA le: {r.get('erro', '')[:210]}")
print(
    f"  registros no banco: {DynamicRecord.objects.filter(user=ana).count()}  (tem de ser 0)"
)

# ------------------------------------------------------- 4. o modelo corrige
linha("4. O modelo corrige usando a lista que recebeu")

r = executar_para(
    ana,
    "amplia_inserir_registro",
    {
        "entity_slug": slug,
        "dados": {"alimento": "Racao", "quantidade_kg": 12},
        "confirm": True,
    },
)
resultado &= checa("agora grava", r.get("ok"), r.get("erro"))
print(f"  a IA le: {r.get('resposta', '')[:120]}")

# ------------------------------------------------------------- 5. valor invalido
linha("5. Valor alucinado: 'muito' num campo DECIMAL")

r = executar_para(
    ana,
    "amplia_inserir_registro",
    {
        "entity_slug": slug,
        "dados": {"alimento": "Sal", "quantidade_kg": "muito"},
        "confirm": True,
    },
)
resultado &= checa("erro, e nao 500", r.get("ok") is False, r)
print(f"  a IA le: {r.get('erro', '')[:160]}")

# --------------------------------------------------------------- 6. leitura
linha("6. O produtor pergunta quanto tem")

r = executar_para(ana, "amplia_consultar_registros", {"entity_slug": slug})
resultado &= checa("leitura ok", r.get("ok"), r.get("erro"))
print(f"  a IA le:\n    {(r.get('resposta') or '')[:220]}")

r = executar_para(
    ana,
    "amplia_consultar_registros",
    {"entity_slug": slug, "filtros": {"idade_da_vaca": 3}},
)
resultado &= checa(
    "filtro com chave alucinada RECUSA (nao devolve vazio)", r.get("ok") is False, r
)
print(f"  a IA le: {r.get('erro', '')[:180]}")

# --------------------------------------------------------------- 7. tenancy
linha("7. OUTRO produtor tenta usar a ferramenta da Ana")

bob = User.objects.create_user("build2_bob", "build2b@exemplo.com", "p")
r = executar_para(
    bob,
    "amplia_inserir_registro",
    {"entity_slug": slug, "dados": {"alimento": "Invadido"}, "confirm": True},
)
resultado &= checa("gravacao BLOQUEADA", r.get("ok") is False, r)
print(f"  a IA le: {r.get('erro', '')[:200]}")

r = executar_para(bob, "amplia_consultar_registros", {"entity_slug": slug})
resultado &= checa("leitura BLOQUEADA", r.get("ok") is False, r)
resultado &= checa("nenhum dado da Ana vazou", "Racao" not in str(r), r)

# ------------------------------------------------------------ 8. limpeza
linha("8. Limpeza (este script criou dados de teste)")
DynamicRecord.objects.filter(user__in=[ana, bob]).delete()
ana.delete()
bob.delete()
print("  registros e usuarios de teste removidos")

print("\n" + "=" * 72)
print("TODAS AS VERIFICACOES PASSARAM" if resultado else "HOUVE FALHA")
print("=" * 72)
raise SystemExit(0 if resultado else 1)
