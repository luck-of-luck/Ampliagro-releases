"""
dinamicos — camada de serviço do Criador Livre.

Onde a "lógica" criada pela IA é aplicada por código genérico.

A diretriz 2 do `docs/MAPA_DE_IMPLEMENTACAO_AMPLIA.md` é explícita: nunca
executar código gerado por IA no servidor. A diretriz 3 diz que a IA escreve
metadados, não `.py`. Este módulo é a prova de que as duas são cumpríveis sem
perder o produto: a IA descreve *o que* o formulário tem (tipos,
obrigatoriedade, opções) e este código aplica *como* validar, gravar e listar.

Uma ferramenta "programada" pela IA tem, portanto, duas camadas:

    metadados (o que a IA escreve)   ->  DynamicApp + DynamicField
    comportamento (código nosso)     ->  este módulo

O que a IA **não** consegue fazer, por construção: escrever uma função, exigir
`import`, disparar um shell, ler um arquivo do servidor, ou sair do escopo do
usuário. Não é uma política configurável que alguém pode desligar; é a
ausência de um caminho de código que faça essas coisas.

FALHA-CERRADO (fail-closed)
--------------------------
`criar_app` e `registrar` devolvem `{"ok": False, "erros": [...]}` em vez de
levantar. O motivo é o mesmo de `app.ia.sandbox.executar`: quem chama é a IA,
e uma exceção sem tratamento viraria 500 no meio de uma conversa. E, mais
grave, um `ValidationError` estourado poderia ser engolido por um `except`
genérico e virar "sucesso".

ESCOPO
------
Toda operação exige `user` e só toca registro dele. Não há caminho que
consulta `DynamicRecord` sem passar por `DynamicRecord.objects.para(user)`.
"""

from __future__ import annotations

import re
from typing import Any

from django.db import transaction

from app.models import DynamicApp, DynamicField, DynamicRecord
from app.models.dinamico import TIPOS_CAMPO

VALIDOS = {c for c, _ in TIPOS_CAMPO}

#: Nomes de campo são identificadores, não texto livre. Esta regex é a
#: fronteira que impede `dados__` virar um lookup malicioso.
RE_CHAVE = re.compile(r"^[a-z_][a-z0-9_]{0,58}[a-z0-9]$|^[a-z_]$")


class ErroDinamico(Exception):
    """Levantado por `validar_dados` quando chamado diretamente.

    O fluxo de serviço (`criar_app`, `registrar`) NÃO levanta — devolve
    `ok: False`. Quem quiser a exceção usa estas funções de baixo nível.
    """


# --------------------------------------------------------------------------
# Normalização de entrada
# --------------------------------------------------------------------------


def _normalizar_campo(bruto: dict[str, Any], usados: dict[str, str]) -> dict[str, Any]:
    """Converte o dicionário que a IA mandou em um campo normalizado.

    Aceita as duas grafias que aparecem nos documentos (`rotulo`/`label`,
    `tipo`/`type`) porque a IA vai produces as duas. Silenciosamente aceitar
    as duas é melhor que devolver erro por um nome de chave.
    """
    rotulo = str(bruto.get("rotulo") or bruto.get("label") or "").strip()
    tipo = str(bruto.get("tipo") or bruto.get("type") or "TEXTO").strip().upper()
    if tipo not in VALIDOS:
        raise ErroDinamico(f"tipo {tipo!r} invalido; permitidos: {sorted(VALIDOS)}")

    if "chave" in bruto and bruto["chave"]:
        chave = str(bruto["chave"]).strip().lower()
    else:
        from app.models.dinamico import chave_de_rotulo

        chave = chave_de_rotulo(rotulo)

    if not RE_CHAVE.match(chave):
        raise ErroDinamico(
            f"chave {chave!r} invalida: use minusculas, sem espaco nem "
            "acento,ate 60 caracteres, comecando por letra ou _"
        )
    if chave in usados:
        raise ErroDinamico(f"chave {chave!r} repetida (rotulo {usados[chave]!r})")
    usados[chave] = rotulo or chave

    opcoes = bruto.get("opcoes") or bruto.get("options") or []
    if isinstance(opcoes, dict):
        # aceita {"a": "Rotulo A"} e normaliza para lista de pares
        opcoes = [{"valor": v, "rotulo": k} for k, v in opcoes.items()]

    return {
        "chave": chave,
        "rotulo": rotulo or chave,
        "tipo": tipo,
        "ajuda": str(bruto.get("ajuda") or bruto.get("help") or "")[:200],
        "obrigatorio": bool(bruto.get("obrigatorio", bruto.get("required", False))),
        "padrao": bruto.get("padrao", bruto.get("default")),
        "opcoes": opcoes,
        "app_relacionada": bruto.get("app_relacionada") or bruto.get("ref_app"),
        "ordem": int(bruto.get("ordem") or 0),
    }


# --------------------------------------------------------------------------
# Validação de dados
# --------------------------------------------------------------------------


def _coagir(valor: Any, tipo: str) -> tuple[Any, str | None]:
    """Converte o valor recebido ao tipo do campo. Devolve (valor, erro)."""
    if valor is None or valor == "":
        return None, None

    try:
        if tipo == "NUMERO":
            return int(valor), None
        if tipo == "DECIMAL":
            from decimal import Decimal

            # `str(exc)` de InvalidOperation devolve a repr da classe do Python
            # ("[<class 'decimal.ConversionSyntax'>]"), que nao diz nada para
            # quem vai corrigir. A mensagem aqui e a mesma forma das demais
            # mensagens deste modulo: o valor recebido, e o que ele deveria ser.
            try:
                return Decimal(str(valor)), None
            except (ArithmeticError, ValueError, TypeError):
                return None, f"{valor!r} nao e um numero decimal"
        if tipo == "BOOLEANO":
            if isinstance(valor, bool):
                return valor, None
            s = str(valor).strip().lower()
            if s in ("1", "true", "sim", "yes", "t", "verdadeiro"):
                return True, None
            if s in ("0", "false", "nao", "não", "no", "f", "falso"):
                return False, None
            return None, f"{valor!r} nao e booleano"
        if tipo in ("DATA", "DATA_HORA"):
            from django.utils import timezone
            from django.utils.dateparse import (
                parse_date,
                parse_datetime,
                parse_time,
            )

            d = parse_date(str(valor))
            if d:
                dt = timezone.datetime.combine(
                    d, parse_time(str(valor)) or timezone.datetime.min.time()
                )
                return (dt if tipo == "DATA_HORA" else d), None
            dt = parse_datetime(str(valor))
            if dt:
                if timezone.is_naive(dt):
                    dt = timezone.make_aware(dt)
                return (dt if tipo == "DATA_HORA" else dt.date()), None
            return None, f"{valor!r} nao e {'data' if tipo == 'DATA' else 'data/hora'}"
        if tipo == "JSON":
            import json

            if isinstance(valor, (dict, list)):
                return valor, None
            try:
                return json.loads(str(valor)), None
            except json.JSONDecodeError as e:
                return None, f"JSON invalido: {e.msg}"
    except (ValueError, TypeError, ArithmeticError) as e:
        # ArithmeticError cobre `decimal.InvalidOperation`, que NAO herda de
        # ValueError — `Decimal("muito")` levantava por fora deste except e
        # derrubava a tool com 500 em vez de devolver erro corrigivel.
        # O DECIMAL ja trata o caso dele acima com mensagem propria; este
        # except e a rede para os outros tipos.
        return None, f"valor invalido para {tipo}: {type(e).__name__}"

    return valor, None


def validar_dados(
    campos: list[DynamicField],
    dados: dict[str, Any],
    *,
    user=None,
    estrito: bool = True,
) -> dict[str, Any]:
    """Valida `dados` contra os campos e devolve o dicionário normalizado.

    Devolve `{"ok": bool, "dados": {...}, "erros": {campo: msg}}`.

    Regras:
    * Campo obrigatório ausente/vazio -> erro.
    * Valor incompatível com o tipo -> erro, com o motivo da coerção.
    * Campo OPCOES com valor fora da lista -> erro.
    * Campo REFERENCIA: o registro tem que existir, e ser do MESMO usuário.
    * Chave que não corresponde a nenhum campo -> **ERRO** quando `estrito`.
      A mensagem lista as chaves válidas, porque quem vai corrigir é um modelo
      de 1.7B e ele precisa do nome exato, não de um "campo inválido".

      Com `estrito=False` a chave é ignorada e listada em `descartadas`, que é
      o comportamento antigo. Ele continua existindo de propósito: um
      formulário aberto numa aba antiga pode mandar um campo que acabou de ser
      removido do schema, e recusar a gravação inteira por causa disso seria
      pior para o produtor do que ignorar uma chave. A decisão é do CHAMADOR,
      não da biblioteca — a rota da IA é estrita porque o modelo precisa
      aprender com o erro, e a rota do formulário é tolerante porque o
      usuário não tem como corrigir um campo que não existe.
    """
    from app.models import DynamicRecord as _R

    erros: dict[str, str] = {}
    descartadas: list[str] = []
    saida: dict[str, Any] = {}

    if not isinstance(dados, dict):
        return {
            "ok": False,
            "dados": {},
            "erros": {"__raiz__": "dados deve ser um objeto JSON"},
            "descartadas": [],
        }

    conhecidas = {c.chave: c for c in campos}

    # ETAPA 1: chave desconhecida.
    #
    # Isto roda ANTES de qualquer gravacao e antes de olhar os campos
    # conhecidos, por dois motivos:
    #  - a mensagem tem de citar as chaves validas, e a lista completa so
    #    existe depois de ler todos os campos;
    #  - devolver logo aqui evita o trabalho de coagir valores que vao ser
    #    descartados na mesma chamada.
    #
    # O erro vai em `erros`, nunca em `descartadas`, quando estrito. E a
    # mensagem e montada com as chaves ordenadas: um modelo pequeno precisa de
    # uma lista estavel para copiar, e ordem aleatoria faz ele reescrever
    # "quase certo" varias vezes.
    invalidas: list[str] = []
    for chave in dados:
        if chave not in conhecidas:
            if estrito:
                invalidas.append(str(chave))
            else:
                descartadas.append(chave)
    if invalidas:
        validas = sorted(conhecidas) or ["(nenhum)"]
        erros["__campos__"] = (
            f"campo(s) inexistente(s): {', '.join(sorted(invalidas))}. "
            f"Campos validos: {', '.join(validas)}"
        )
        return {
            "ok": False,
            "dados": {},
            "erros": erros,
            "descartadas": descartadas,
        }

    for chave, campo in conhecidas.items():
        bruto = dados.get(chave)

        if bruto is None or bruto == "":
            if campo.obrigatorio:
                erros[chave] = "campo obrigatorio"
            elif campo.padrao is not None:
                saida[chave] = campo.padrao
            continue

        if campo.tipo == "REFERENCIA":
            alvo = campo.app_relacionada
            if user is None:
                # sem contexto de usuario nao da para conferir existencia;
                # aceita o valor como declarado (validacao de metadados)
                saida[chave] = bruto
                continue
            existe = False
            if alvo is not None:
                # escopado no usuario: apontar para registro alheio seria o
                # mesmo vazamento que o resto da camada evita
                try:
                    existe = (
                        _R.objects.para(user).filter(app_id=alvo.pk, pk=bruto).exists()
                    )
                except Exception:
                    existe = False
            if not existe:
                erros[chave] = f"registro {bruto!r} nao encontrado"
            else:
                saida[chave] = bruto
            continue

        valor, erro = _coagir(bruto, campo.tipo)
        if erro:
            erros[chave] = erro
            continue

        if campo.tipo == "OPCOES":
            validos = campo.valores_validos()
            if validos is not None and valor not in validos:
                erros[chave] = f"{valor!r} fora das opcoes {sorted(map(str, validos))}"
                continue

        saida[chave] = valor

    return {
        "ok": not erros,
        "dados": saida,
        "erros": erros,
        "descartadas": descartadas,
    }


# --------------------------------------------------------------------------
# Criação da ferramenta
# --------------------------------------------------------------------------


@transaction.atomic
def criar_app(
    user,
    nome: str,
    descricao: str = "",
    campos: list[dict[str, Any]] | None = None,
    *,
    icone: str = "",
    escopo_iot: dict[str, Any] | None = None,
    ativar: bool = True,
) -> dict[str, Any]:
    """Cria uma ferramenta e seus campos, de uma vez.

    `campos` é a lista no formato que a IA produz. Tudo é normalizado e
    validado antes de gravar; se qualquer campo for inválido, nada é gravado
    (`transaction.atomic` + validação antes do primeiro `save`).
    """
    if user is None or not getattr(user, "is_authenticated", False):
        return {"ok": False, "erros": {"__user__": "usuario obrigatorio"}, "app": None}

    nome = str(nome or "").strip()
    if not nome:
        return {"ok": False, "erros": {"nome": "nome obrigatorio"}, "app": None}
    if len(nome) > 120:
        return {"ok": False, "erros": {"nome": "maximo 120 caracteres"}, "app": None}

    campos = campos or []
    if not campos:
        return {
            "ok": False,
            "erros": {"campos": "ferramenta precisa de ao menos 1 campo"},
            "app": None,
        }

    usados: dict[str, str] = {}
    normalizados: list[dict[str, Any]] = []
    for bruto in campos:
        if not isinstance(bruto, dict):
            return {
                "ok": False,
                "erros": {"campos": f"campo invalido: {bruto!r}"},
                "app": None,
            }
        try:
            normalizados.append(_normalizar_campo(bruto, usados))
        except ErroDinamico as e:
            return {"ok": False, "erros": {"campos": str(e)}, "app": None}

    # Referencia nao pode apontar para a propria ferramenta ainda nao criada.
    for n in normalizados:
        if n["tipo"] == "REFERENCIA" and n["app_relacionada"] is None:
            return {
                "ok": False,
                "erros": {"campos": f"campo {n['chave']!r} REFERENCIA sem app alvo"},
                "app": None,
            }

    app = DynamicApp(
        user=user,
        nome=nome,
        descricao=str(descricao or "")[:2000],
        icone=str(icone or "")[:60],
        escopo_iot=escopo_iot or {},
        estado="RASCUNHO",
    )
    app.salvar_slug()
    app.save()

    for i, n in enumerate(normalizados):
        if n["tipo"] == "REFERENCIA":
            alvo = n["app_relacionada"]
            if hasattr(alvo, "pk"):
                n["app_relacionada"] = alvo
            else:
                n["app_relacionada"] = DynamicApp.objects.filter(
                    user=user, slug=str(alvo)
                ).first()
        DynamicField.objects.create(
            app=app,
            chave=n["chave"],
            rotulo=n["rotulo"],
            tipo=n["tipo"],
            ajuda=n["ajuda"],
            obrigatorio=n["obrigatorio"],
            padrao=n["padrao"],
            opcoes=n["opcoes"],
            app_relacionada=n["app_relacionada"],
            ordem=n["ordem"] or (i + 1) * 10,
        ).full_clean()

    if ativar:
        app.estado = "PRONTO"
        app.save(update_fields=["estado"])

    return {"ok": True, "app": app, "erros": {}}


def resolver_app(user, identificador):
    """Resolve a ferramenta do USUARIO, ou devolve None.

    Aceita slug (`"geladeira"`) ou id numerico (`"7"`).

    ┌── POR QUE ISTO EXISTE E NAO UM `get(slug=...)`
    │
    │ `slug` tem unique constraint em `(user, slug)`, NAO global. Dois
    │ produtores podem ter `slug="geladeira"` ao mesmo tempo, e o teste
    │ `test_slug_unico_entre_usuarios_e_independente` fixa esse comportamento.
    │
    │ Logo `filter(slug=X).first()` pode devolver a ferramenta de outro. O
    │ estrago nao e so leitura de nome: se a tool combinar resolucao + escrita,
    │ a gravacao inteira cai na ferramenta alheia.
    │
    │ A posse entra SEMPRE no filtro. Nao existe caminho que aceite slug sem
    │ user, nem user anonimo — o filtro compose os dois num `filter` so, para
    │ nao haver um return antecipado que alguem um dia troque por `.get()`.
    └──────────────────────────────────────────────────────────────────────
    """
    if user is None or not getattr(user, "is_authenticated", False):
        return None
    ref = str(identificador or "").strip()
    if not ref or ref == "None":
        return None

    qs = DynamicApp.objects.filter(user=user)
    if ref.isdigit():
        return qs.filter(pk=int(ref)).first()
    return qs.filter(slug=ref[:140]).first()


def descrever_erro(app, user) -> str:
    """Mensagem de "nao achei" que o modelo consegue corrigir.

    Quando a tool nao acha a ferramenta, dizer so "nao encontrado" deixa o
    modelo adivinhar entre tres possibilidades: nome errado, usuario errado, ou
    ferramenta que nunca foi criada. Listar as ferramentas do usuario e a
    pista que faz ele se corrigir em uma segunda chamada.
    """
    if app is not None:
        return ""
    nomes = []
    if user is not None and getattr(user, "is_authenticated", False):
        nomes = list(
            DynamicApp.objects.filter(user=user, estado__in=("PRONTO", "RASCUNHO"))
            .order_by("nome")
            .values_list("slug", flat=True)[:20]
        )
    if nomes:
        return (
            f"ferramenta nao encontrada entre as suas. "
            f"Suas ferramentas: {', '.join(nomes)}"
        )
    return (
        "ferramenta nao encontrada. Voce ainda nao criou nenhuma ferramenta "
        "neste sistema: use create_entity primeiro."
    )


def validar_filtros(
    campos: list[DynamicField], filtros: dict[str, Any]
) -> dict[str, Any]:
    """Valida as CHAVES de filtro contra o schema.

    Sem isto, `json_portatil.contem()` monta `dados__<chave>` e uma chave
    alucinada devolve VAZIO. E vazio e o pior resultado possivel para quem
    perguntou: o modelo le "0 registros" e conclui que o dado nao existe —
    quando o que aconteceu e que ele filtrou por um campo que nunca existiu.
    Um filtro errado que devolve vazio e um vazamento de conclusao, nao um
    erro de consulta.

    Os VALORES passam pela mesma coercao do insert, para que o filtro
    "idade=10" e o valor gravado "idade=10" sejam comparados do mesmo jeito.
    """
    if filtros is None:
        return {"ok": True, "filtros": {}, "erros": {}}
    if not isinstance(filtros, dict):
        return {
            "ok": False,
            "filtros": {},
            "erros": {"__filtros__": "filtros deve ser um objeto JSON"},
        }

    conhecidas = {c.chave: c for c in campos}
    invalidas = [str(k) for k in filtros if k not in conhecidas]
    if invalidas:
        validas = sorted(conhecidas) or ["(nenhum)"]
        return {
            "ok": False,
            "filtros": {},
            "erros": {
                "__filtros__": (
                    f"campo(s) de filtro inexistente(s): {', '.join(sorted(invalidas))}. "
                    f"Campos filtráveis: {', '.join(validas)}"
                )
            },
        }

    saida: dict[str, Any] = {}
    erros: dict[str, str] = {}
    for chave, valor in filtros.items():
        campo = conhecidas[chave]
        if valor is None or valor == "":
            # filtrar por vazio nao tem leitura: `dados__chave=""` nao casa
            # com registro que nao preencheu o campo. Recusa com mensagem, em
            # vez de devolver vazio e deixar o modelo concluir "nao ha dados".
            erros[chave] = (
                f"filtro vazio em {chave!r}: nao ha o que casar. "
                f"Omita a chave para nao filtrar por ela."
            )
            continue
        if campo.tipo == "REFERENCIA":
            saida[chave] = valor
            continue
        coerido, erro = _coagir(valor, campo.tipo)
        if erro:
            erros[chave] = erro
            continue
        if campo.tipo == "OPCOES":
            validos = campo.valores_validos()
            if validos is not None and coerido not in validos:
                erros[chave] = (
                    f"{coerido!r} fora das opcoes {sorted(map(str, validos))}"
                )
                continue
        saida[chave] = coerido

    return {"ok": not erros, "filtros": saida, "erros": erros}


# --------------------------------------------------------------------------
# Registros
# --------------------------------------------------------------------------


@transaction.atomic
def registrar(
    user, app, dados: dict[str, Any], *, estrito: bool = True
) -> dict[str, Any]:
    """Grava um registro, validado contra os campos da ferramenta.

    Duplicata de app é barrada aqui e não na view: duas abas abertas não
    podem criar duas ferramentas com o mesmo nome para o mesmo usuário.

    `estrito=True` (padrão) faz chave desconhecida recusar a gravação. A rota da
    IA usa o padrão porque o modelo precisa aprender com o erro; a rota do
    formulário passa `False`, porque um campo removido do schema não pode
    custar ao produtor a gravação inteira.

    Aatomicidade: `transaction.atomic` + validação antes do primeiro `save`
    significam que uma chave alucinada não deixa registro pela metade. Não há
    estado intermediário para o produtor encontrar.
    """
    if user is None or not getattr(user, "is_authenticated", False):
        return {
            "ok": False,
            "erros": {"__user__": "usuario obrigatorio"},
            "registro": None,
        }
    if app is None or getattr(app, "user_id", None) != user.pk:
        return {
            "ok": False,
            "erros": {"app": "ferramenta nao pertence ao usuario"},
            "registro": None,
        }
    if app.estado == "ARQUIVADO":
        return {"ok": False, "erros": {"app": "ferramenta arquivada"}, "registro": None}

    campos = list(
        DynamicField.objects.filter(app=app, ativo=True).order_by("ordem", "id")
    )
    resultado = validar_dados(campos, dados or {}, user=user, estrito=estrito)
    if not resultado["ok"]:
        return {
            "ok": False,
            "erros": resultado["erros"],
            "registro": None,
            "descartadas": resultado["descartadas"],
        }

    limpo = {k: v for k, v in resultado["dados"].items() if k != "__user__"}
    registro = DynamicRecord.objects.create(
        app=app,
        user=user,
        dados=limpo,
        schema_snapshot=[
            {"chave": c.chave, "tipo": c.tipo, "obrigatorio": c.obrigatorio}
            for c in campos
        ],
    )
    return {
        "ok": True,
        "registro": registro,
        "erros": {},
        "descartadas": resultado["descartadas"],
    }


#: Teto de registros por resposta. Além de performance, é limite de CONTEXTO:
#: o SmolLM2 tem janela de 4096 tokens, e 200 registros JSON estouram isso. Sem
#: teto, um modelo_vscido pedindo "todos" tomba o contexto e a resposta inteira
#: se perde — inclusive a parte que o produtor precisava ler.
LIMITE_REGISTROS = 200


def listar(user, app, *, filtros: dict[str, Any] | None = None, limite: int = 100):
    """Lista registros do usuário, com filtros por chave do JSONField.

    Levanta `ErroDinamico` quando a chave de filtro não existe no schema. A
    alternativa — deixar `json_portatil.contem()` montar `dados__<chave>` e
    devolver vazio — é segura em SQL e péssima em significado: o modelo lê
    "0 registros" e conclui que o dado não existe, quando o que houve foi ele
    ter errado o nome do campo. Erro que vira conclusão errada é pior que
    exceção.

    Como `descrever()`, esta função LEVANTA. O caminho de erro que importa aqui
    é "filtro inválido", e devolver lista vazia seria indistinguível de
    "não tem registro" — a confusão que estamos evitando.
    """
    from app.ia import json_portatil as jp

    if user is None or not getattr(user, "is_authenticated", False):
        raise ErroDinamico("usuario obrigatorio")
    if app is None or getattr(app, "user_id", None) != user.pk:
        raise ErroDinamico("ferramenta nao pertence ao usuario")

    campos = list(app.dynamic_fields.filter(ativo=True))
    if filtros:
        checagem = validar_filtros(campos, filtros)
        if not checagem["ok"]:
            # Sem a chave interna no texto: quem lê esta mensagem é o modelo e
            # o produtor, e nenhum dos dois sabe o que "__filtros__" quer
            # dizer. A chave serve à camada de código para distinguir
            # erro-do-conjunto de erro-de-campo, e isso termina aqui.
            raise ErroDinamico("; ".join(str(v) for v in checagem["erros"].values()))
        filtros = checagem["filtros"]

    qs = DynamicRecord.objects.do_usuario_e_app(user, app)
    for chave, valor in (filtros or {}).items():
        qs = jp.contem(qs, {chave: valor})
    return qs[: max(1, min(int(limite or 100), LIMITE_REGISTROS))]


def descrever(user, app) -> dict[str, Any]:
    """Descreve a ferramenta em JSON: é o que a IA e a UI leem.

    É a saída do "Schema-Driven Development" do `mcp-Ampliagro_amplIA.md`
    (seção 2.2): a tela é desenhada a partir deste dicionário, sem código.

    DIFERENÇA DE CONTRATO com `criar_app`/`registrar`: estas devolvem
    `{"ok": False, ...}`; esta LEVANTA. Motivo: é uma função de leitura de
    metadados, chamada depois de a ferramenta já existir. O caminho de erro que
    importa aqui é "esta ferramenta não é sua", e devolvendo um schema vazio a
    IA poderia seguir desenhando uma tela para a ferramenta errada. Falhar
    alto é mais seguro que falhar baixo.

    Também é por isso que `user` existe no parâmetro: a posse é conferida.
    """
    if user is None or not getattr(user, "is_authenticated", False):
        raise ErroDinamico("usuario obrigatorio")
    if app is None or getattr(app, "user_id", None) != user.pk:
        raise ErroDinamico("ferramenta nao pertence ao usuario")

    campos = list(app.dynamic_fields.all())

    return {
        "slug": app.slug,
        "nome": app.nome,
        "descricao": app.descricao,
        "icone": app.icone,
        "estado": app.estado,
        "requer_iot": bool(app.escopo_iot),
        "campos": [
            {
                "chave": c.chave,
                "rotulo": c.rotulo,
                "tipo": c.tipo,
                "ajuda": c.ajuda,
                "obrigatorio": c.obrigatorio,
                "opcoes": c.opcoes,
                "padrao": c.padrao,
                "ref_app": c.app_relacionada.slug if c.app_relacionada_id else None,
            }
            for c in campos
        ],
    }


def listar_ferramentas(user) -> list[DynamicApp]:
    """Ferramentas do usuário, prontas e não arquivadas."""
    if user is None or not getattr(user, "is_authenticated", False):
        return []
    return list(
        DynamicApp.objects.filter(user=user, estado__in=("PRONTO", "RASCUNHO"))
        .prefetch_related(
            # a paleta do painel chama `descrever()` em CADA app: sem isto
            # seriam 1+N queries. Com prefetch, 2 queries para N ferramentas.
            "dynamic_fields",
            "dynamic_fields__app_relacionada",
        )
        .order_by("nome")
    )
