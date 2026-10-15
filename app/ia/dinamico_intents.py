"""
dinamico_intents.py — BUILD 2: as "Tools Divinas", o caminho pelo qual a IA
expande o sistema.

O QUE ESTE ARQUIVO É
--------------------
A IA do AmplIA não escreve `.py` nem roda `makemigrations`. Ela escreve
**metadados** — um schema de campos — e código genérico (que já existe, em
`app/ia/dinamicos.py`) aplica esses metadados. Um "App Geladeira" criado por
voz é uma linha em `DynamicApp` mais N linhas em `DynamicField`.

Três tools:

    create_entity(nome, campos)        cria a ferramenta
    insert_record(entity_slug, dados)  grava um registro
    query_records(entity_slug, ...)    lê registros

O PROBLEMA CENTRAL: MODELO PEQUENO INVENTA CHAVE
------------------------------------------------
Um SmolLM2 de 1.7B Parameters em 1.7B é capaz de produzir
`{"alimento": "X", "idade_da_vaca": 10}` para um schema que tem
`alimento`/`quantidade_kg`. Isso não é hypothetical: é o comportamento
esperado de um modelo que não temrestricao de schema e é treinado para continuar
texto plausível, não para obedecer contrato.

Há duas formas de responder, e uma delas é uma armadilha:

  (a) ACEITAR e descartar a chave que não existe.
      Proibido. O produtor pediu "registre a vacina", o registro foi gravado
      sem a idade que o MODELO inventou ter visto, e ninguém foi avisado. Ele
      confia no registro e volta a confiar no mês seguinte. Um sistema que
      perde dado em silêncio é pior que um que não tem o dado.

  (b) RECUSAR e dizer exatamente qual chave é inválida e quais são válidas.
      É o que `validar_dados(..., estrito=True)` faz, e a mensagem é montada
      para ser lida por um modelo pequeno: nome exato, lista ordenada.

O ponto de (b) que importa: a recusa precisa voltar para o modelo como um
erro **utilizável**, não como um booleano. Sem o nome do campo válido, o
modelo não tem como se corrigir — e um modelo que não se corrige repete o
erro a cada registro.

A DEFESA NÃO É SÓ DO MODELO
---------------------------
Quem garante a integridade é o schema no banco, não o bom comportamento do
modelo. Mesmo que o modelo se comporte, a tool é estrita; e mesmo que a tool
fosse contornada, `registrar()` valida de novo antes do `save`, dentro da
`transaction.atomic`. São três camadas, e a última não depende do modelo.
"""

import re
from typing import Any

from app.ia import compliance
from app.ia.dinamicos import (
    ErroDinamico,
    criar_app,
    descrever,
    descrever_erro,
    listar,
    registrar,
    resolver_app,
)

#: Tipos que o modelo pode declarar. A lista é a mesma de `TIPOS_CAMPO` nos
#: models — mas é declarada aqui de novo porque ela vai para o `inputSchema`
#: que o modelo lê, e um enum que o modelo não conhece é um enum que ele
#: inventa. `create_entity` valida contra ESTA lista, então divergência entre
#: as duas é impossivel de corrigir em tempo de execução.
TIPOS_ACEITOS = [
    "TEXTO",
    "TEXTO_LONGO",
    "NUMERO",
    "DECIMAL",
    "BOOLEANO",
    "DATA",
    "DATA_HORA",
    "OPCOES",
    "REFERENCIA",
    "JSON",
]

#: Quantos campos uma tool aceita criar. Teto de DUAS RAZÕES, e as duas
#: importam:
#:  1. o `inputSchema` da tool é montado a partir disto e vai para o prompt do
#:     modelo — 60 camposdescription estouram a janela de 4096 tokens do
#:     SmolLM2 e matam o contexto inteiro;
#:  2. um modelo pequeno não planeja 60 campos. Ele vai tentar, falhar, e
#:     devolver um schema pela metade.
MAX_CAMPOS = 20

#: Quantos registros uma resposta de leitura carrega. Mesmo motivo.
MAX_RESULTADOS = 20


def _campos_legiveis(app) -> str:
    """Linha por campo, para o modelo corrigir um insert sem chamar antes."""
    campos = list(app.dynamic_fields.filter(ativo=True).order_by("ordem", "id"))
    if not campos:
        return "(nenhum campo)"
    partes = []
    for c in campos:
        extra = ""
        if c.obrigatorio:
            extra += ", obrigatorio"
        if c.tipo == "OPCOES" and c.opcoes:
            vals = [str(o.get("valor") if isinstance(o, dict) else o) for o in c.opcoes]
            extra += f", opcoes: {'|'.join(vals)}"
        if c.tipo == "REFERENCIA" and c.app_relacionada_id:
            extra += f", referencia: {c.app_relacionada.slug}"
        partes.append(f"{c.chave} ({c.tipo}{extra})")
    return "; ".join(partes)


def _texto_de_resultado(registros) -> str:
    """Serializa registros para o modelo sem despejar o JSONField cru.

    O `dados` cru é a tentação do implementador e o erro: o modelo recebe
    `{"alimento": "X", "quantidade_kg": 12}` e tem que adivinhar o que é
    id, o que é campo, e qual é a data. Com o rótulo do campo junto, a
    resposta fica utilizável, e continua curta o bastante para a janela.
    """
    linhas = []
    for r in registros:
        rotulos = []
        dados = r.dados if isinstance(r.dados, dict) else {}
        for chave, valor in list(dados.items())[:12]:
            texto = str(valor)
            if len(texto) > 60:
                texto = texto[:57] + "..."
            rotulos.append(f"{chave}={texto}")
        linhas.append(f"#{r.pk} " + ", ".join(rotulos))
    return "\n".join(linhas)


# --------------------------------------------------------------------------
# 1. create_entity
# --------------------------------------------------------------------------


def _registrar_bloqueio(user, nome, campos, recusa) -> None:
    """Grava a recusa de compliance na trilha de auditoria.

    `try/except` com log: uma falha de auditoria NÃO pode transformar um
    bloqueio em recusa-silenciosa. Se o evento não grava, o comportamento seguro
    é o de recusar mesmo assim (que é o que o chamador faz) — mas o operador
    precisa saber que a trilha falhou, e é isso que o log registra.
    """
    import logging

    from app.models import IAEvento

    try:
        IAEvento.objects.create(
            user=user,
            tipo="compliance",
            resumo=(f"criacao bloqueada: {recusa['termo']!r} em {recusa['onde']}")[
                :200
            ],
            dados={
                "acao": "criar_entidade",
                "bloqueio": "compliance_ambiental",
                "termo": recusa["termo"],
                "motivo": recusa["motivo"],
                "base_legal": recusa["base_legal"],
                "onde": recusa["onde"],
                "texto_encontrado": recusa["texto"],
                "nome_pedido": str(nome)[:120],
                "campos_pedidos": [
                    str(c.get("rotulo") or c.get("label") or "")[:80]
                    for c in (campos or [])
                    if isinstance(c, dict)
                ][:20],
            },
        )
    except Exception as e:  # noqa: BLE001
        logging.getLogger(__name__).error(
            "compliance: nao foi possivel gravar o evento de auditoria (%s). "
            "O bloqueio foi mantido mesmo assim.",
            e,
        )


def h_criar_entidade(user, params, ctx):
    """Cria uma ferramenta virtual a partir de metadados.

    ESCRITA, e por isso pede confirmação: criar estrutura é uma decisão do
    produtor, não um efeito colateral de uma conversa. Sem a confirmação, uma
    alucinação do modelo ("crie uma ferramenta de impostos") materializaria um
    schema na conta do produtor sem ele ter visto nada.
    """
    nome = str(params.get("nome") or "").strip()
    if not nome:
        return {
            "ok": False,
            "erro": "informe 'nome' da ferramenta. Ex: nome='Controle de Geladeira'",
        }

    campos = params.get("campos") or params.get("definicao_schema") or []

    # BUILD 3 — COMPLIANCE, primeira coisa depois de ler o pedido.
    #
    # Antes de qualquer validacao de tipo, antes do teto de campos, e —
    # acima de tudo — ANTES de pedir confirmacao ao produtor. A ordem importa:
    # pedir "crio esta ferramenta?" e so entao recusar faria o produtor
    # confirmar um pedido que nunca vai acontecer, e treinaria ele a confirmar
    # sem ler. A recusa tem de ser a primeira coisa que ele ve.
    #
    # Determinista de proposito: `compliance.py` nao chama o modelo. Regra de
    # compliance que depende de inferencia falha no dia em que mais importa.
    #
    # A auditoria vai para `IAEvento` com `dados` estruturado: quem pode
    # responder "quem tentou criar o que, e aonde" sem ler a conversa.
    recusa = compliance.analisar(nome, campos)
    if recusa["bloqueado"]:
        _registrar_bloqueio(user, nome, campos, recusa)
        return {
            "ok": False,
            "erro": (
                f"criacao BLOQUEADA por politica de compliance ambiental: "
                f"{recusa['motivo']} (encontrado em: {recusa['onde']}, "
                f"texto={recusa['texto']!r}). Base: {recusa['base_legal']}. "
                "Nao ha como criar esta ferramenta. Se voce quer registrar "
                "compromisso ambiental de forma legal (APP, CAR, area "
                "protegida), use termos como 'controle', 'monitoramento' ou "
                "'compliance' e descreva a area em outro campo."
            ),
            "dados": {
                "bloqueio": "compliance_ambiental",
                "termo": recusa["termo"],
                "onde": recusa["onde"],
                "base_legal": recusa["base_legal"],
            },
        }
    # Aceita a forma que um modelo pequeno naturalmente produz: o schema como
    # STRING JSON. Recusar por formato, quando o conteúdo está certo, é
    # desperdiçar a chance de a tool funcionar.
    if isinstance(campos, str):
        import json

        try:
            campos = json.loads(campos)
        except (ValueError, TypeError) as e:
            return {
                "ok": False,
                "erro": f"campos nao e JSON valido: {e}. Mande uma lista de campos.",
            }

    if not isinstance(campos, list) or not campos:
        return {
            "ok": False,
            "erro": (
                "informe 'campos': lista de {rotulo, tipo, obrigatorio}. "
                f"Tipos aceitos: {', '.join(TIPOS_ACEITOS)}"
            ),
        }
    if len(campos) > MAX_CAMPOS:
        return {
            "ok": False,
            "erro": (
                f"maximo de {MAX_CAMPOS} campos por ferramenta; voce mandou "
                f"{len(campos)}. Divida em duas ferramentas."
            ),
        }

    # tipo invalido é erro ANTES da confirmacao: nao ha ganho em perguntar ao
    # produtor "cria esta ferramenta?" para uma ferramenta que nao pode ser criada
    tipos_vistos = set()
    for i, c in enumerate(campos):
        if not isinstance(c, dict):
            return {"ok": False, "erro": f"campo {i + 1} nao e um objeto"}
        tipo = str(c.get("tipo") or "TEXTO").upper()
        if tipo not in TIPOS_ACEITOS:
            return {
                "ok": False,
                "erro": (
                    f"campo {i + 1} ({c.get('rotulo')!r}) com tipo {tipo!r} "
                    f"invalido. Tipos aceitos: {', '.join(TIPOS_ACEITOS)}"
                ),
            }
        tipos_vistos.add(tipo)

    # OPCOES sem lista, e REFERENCIA sem alvo: barrados aqui para que o
    # produtor nao confirme e depois receba um erro de validacao do model
    for i, c in enumerate(campos):
        tipo = str(c.get("tipo") or "TEXTO").upper()
        if tipo == "OPCOES" and not c.get("opcoes"):
            return {
                "ok": False,
                "erro": (
                    f"campo {i + 1} ({c.get('rotulo')!r}) e OPCOES mas nao mandou "
                    "'opcoes'. Ex: opcoes=[{valor: 'A', rotulo: 'Alta'}]"
                ),
            }
        if tipo == "REFERENCIA" and not (c.get("ref_app") or c.get("app_relacionada")):
            return {
                "ok": False,
                "erro": (
                    f"campo {i + 1} ({c.get('rotulo')!r}) e REFERENCIA mas nao "
                    "mandou 'ref_app' com o slug de outra ferramenta sua"
                ),
            }

    if not params.get("confirm"):
        resumo = "; ".join(
            f"{c.get('rotulo')} ({str(c.get('tipo', 'TEXTO')).upper()})"
            + (", obrigatorio" if c.get("obrigatorio") else "")
            for c in campos
        )
        return {
            "ok": True,
            "needs_confirm": True,
            "resposta": (
                f'Vou criar a ferramenta "{nome}" com {len(campos)} campo(s): '
                f"{resumo}. Confirme com confirm=true para criar."
            ),
            "dados": {"nome": nome, "qtd_campos": len(campos)},
        }

    resultado = criar_app(
        user,
        nome,
        descricao=str(params.get("descricao") or ""),
        campos=campos,
        icone=str(params.get("icone") or ""),
    )
    if not resultado["ok"]:
        return {
            "ok": False,
            "erro": "; ".join(
                f"{k}: {v}" for k, v in (resultado.get("erros") or {}).items()
            )
            or "nao foi possivel criar a ferramenta",
        }

    app = resultado["app"]
    return {
        "ok": True,
        "resposta": (
            f'Ferramenta "{app.nome}" criada (slug: {app.slug}). '
            f"Campos: {_campos_legiveis(app)}. "
            f"Agora use insert_record com entity_slug='{app.slug}'."
        ),
        "dados": {
            "slug": app.slug,
            "nome": app.nome,
            "estado": app.estado,
            "campos": [c.chave for c in app.dynamic_fields.all()],
        },
    }


# --------------------------------------------------------------------------
# 2. insert_record — a defesa contra alucinação
# --------------------------------------------------------------------------


def h_inserir_registro(user, params, ctx):
    """Grava um registro, validado contra o schema gravado.

    O caminho crítico é `registrar(..., estrito=True)`: chave que não existe
    no schema **recusa a gravação** e devolve o nome do erro com a lista das
    chaves válidas.
    """
    slug = str(params.get("entity_slug") or params.get("slug") or "").strip()
    if not slug:
        return {"ok": False, "erro": "informe 'entity_slug' (o slug da ferramenta)"}

    # Resolução SEMPRE escopada no dono. Dois produtores podem ter o mesmo
    # slug — ver `resolver_app`.
    app = resolver_app(user, slug)
    if app is None:
        return {"ok": False, "erro": descrever_erro(app, user)}

    dados = params.get("dados") or params.get("dados_json") or {}
    if isinstance(dados, str):
        import json

        try:
            dados = json.loads(dados)
        except (ValueError, TypeError) as e:
            return {"ok": False, "erro": f"dados nao e JSON valido: {e}"}
    if not isinstance(dados, dict):
        return {"ok": False, "erro": "dados deve ser um objeto JSON"}

    # Valida ANTES de pedir confirmacao. Perguntar "confirma o gravamento?"
    # para um payload que vai ser recusado faz o produtor confirmar uma
    # coisa que nao vai acontecer — e o modelo recebe "ok" num caso que
    # deveria ser erro, o que o ensina a tentar de novo a toa.
    campos = list(app.dynamic_fields.filter(ativo=True).order_by("ordem", "id"))
    checagem = validar_dados_pub(campos, dados, user=user)
    if not checagem["ok"]:
        return {
            "ok": False,
            "erro": _erro_de_validacao(checagem, app),
            "dados": {
                "campos_validos": [c.chave for c in campos],
                "erros": checagem["erros"],
            },
        }

    if not params.get("confirm"):
        resumo = ", ".join(
            f"{k}={str(v)[:40]}" for k, v in list(checagem["dados"].items())[:10]
        )
        return {
            "ok": True,
            "needs_confirm": True,
            "resposta": (
                f'Vou registrar em "{app.nome}": {resumo}. Confirme com confirm=true.'
            ),
            "dados": {"entity_slug": app.slug, "campos": list(checagem["dados"])},
        }

    resultado = registrar(user, app, checagem["dados"], estrito=True)
    if not resultado["ok"]:
        return {
            "ok": False,
            "erro": _erro_de_validacao(
                {"ok": False, "erros": resultado["erros"], "dados": {}}, app
            ),
        }

    registro = resultado["registro"]
    return {
        "ok": True,
        "resposta": (
            f"Registro #{registro.pk} gravado em {app.nome} "
            f"({', '.join(registro.dados.keys())})."
        ),
        "dados": {"id": registro.pk, "entity_slug": app.slug, "dados": registro.dados},
    }


#: Chaves internas do validador. São prefixo de `__` porque colidem com nome de
#: campo real é impossível — o `chave_de_rotulo` nunca produz `__algo__`.
#: Elas existem para separar "erro do conjunto" de "erro de um campo", e não
#: devem aparecer no texto que o modelo lê: o nome interno não ajuda ninguém a
#: corrigir, e ocupa precious tokens da janela de 4096.
_CHAVES_INTERNAS = ("__campos__", "__filtros__", "__user__", "__raiz__")


def _erro_de_validacao(checagem, app) -> str:
    """Monta o erro que o modelo vai corrigir.

    Não é `json.dumps(erros)`: um modelo de 1.7B lê pior um dicionário do que
    uma frase, e o que precisa aqui é que ele identifique a chave exata e
    substitua por uma válida.

    Quatro regras, todas nascidas de olhar a saída real — e não só o teste
    verde. Foi olhando que apareceram:

      1. a lista de campos válidos aparece UMA vez. Repetir "Campos validos: …"
         duas vezes gasta contexto e — pior — faz o modelo achar que são dois
         conjuntos diferentes, e escolher um;
      2. chave interna (`__campos__`, `__filtros__`) não vaza. O texto é para o
         modelo, e o nome interno não ajuda ninguém a corrigir;
      3. o valor recusado vem com o que ele deveria ser, senão o modelo repete
         a mesma string inválida na segunda tentativa;
      4. a decisão de acrescentar a lista é tomada sobre o texto JÁ montado.
         Testar chave a chave erra: a mensagem do filtro chega com a chave
         "filtro" (não-interna) e o teste nunca marcava, duplicando a lista.
    """
    partes = []
    for chave, msg in (checagem.get("erros") or {}).items():
        texto = str(msg)
        # remove prefixo `__algo__:` que venha embutido no texto
        texto = re.sub(r"__[a-z_]+__\s*:\s*", "", texto)
        if chave in _CHAVES_INTERNAS or chave == "":
            partes.append(texto)
        else:
            partes.append(f"{chave}: {texto}")

    joined = " | ".join(p for p in partes if p)
    if not re.search(r"Campos (validos|filtr)", joined, re.IGNORECASE):
        validas = ", ".join(c.chave for c in app.dynamic_fields.filter(ativo=True))
        if validas:
            joined = (
                f"{joined} | Campos validos: {validas}"
                if joined
                else (f"Campos validos: {validas}")
            )
    return joined


def validar_dados_pub(campos, dados, *, user=None):
    """Wrapper nomeado do validador, em modo estrito.

    Existe para deixar explícito no handler que a rota da IA é estrita — e
    para que um futuro navegador da camada veja num lugar só onde a política
    é decidida, em vez de um `True` solto no meio de uma chamada.
    """
    from app.ia.dinamicos import validar_dados

    return validar_dados(campos, dados, user=user, estrito=True)


# --------------------------------------------------------------------------
# 3. query_records
# --------------------------------------------------------------------------


def h_consultar_registros(user, params, ctx):
    """Lê registros, com filtro validado contra o schema.

    O ponto não-óbvio está em `listar`, que LEVANTA em filtro inválido. Sem
    isso, `json_portatil.contem()` montaria `dados__<chave>` e devolveria
    vazio — e "0 registros" é indistinguível de "não existe esse dado", que é
    a pior conclusão possível para o produtor tomar.
    """
    slug = str(params.get("entity_slug") or params.get("slug") or "").strip()
    if not slug:
        return {"ok": False, "erro": "informe 'entity_slug' (o slug da ferramenta)"}

    app = resolver_app(user, slug)
    if app is None:
        return {"ok": False, "erro": descrever_erro(app, user)}

    filtros = params.get("filtros") or params.get("filtro") or {}
    if isinstance(filtros, str):
        import json

        try:
            filtros = json.loads(filtros)
        except (ValueError, TypeError) as e:
            return {"ok": False, "erro": f"filtros nao e JSON valido: {e}"}

    limite = int(params.get("limite") or 10)
    limite = max(1, min(limite, MAX_RESULTADOS))

    try:
        registros = list(listar(user, app, filtros=filtros or None, limite=limite))
    except ErroDinamico as e:
        campos = ", ".join(
            c.chave
            for c in app.dynamic_fields.filter(ativo=True).order_by("ordem", "id")
        )
        return {
            "ok": False,
            "erro": _erro_de_validacao({"erros": {"": str(e)}}, app),
            "dados": {"campos_validos": campos},
        }

    if not registros:
        where = (
            " com filtro " + ", ".join(f"{k}={v}" for k, v in (filtros or {}).items())
            if filtros
            else ""
        )
        return {
            "ok": True,
            "resposta": f"Nenhum registro em {app.nome}{where}.",
            "dados": {"total": 0, "entity_slug": app.slug},
        }

    texto = _texto_de_resultado(registros)
    return {
        "ok": True,
        "resposta": (
            f"{len(registros)} registro(s) em {app.nome}"
            f"{' (fatiado)' if len(registros) >= limite else ''}:\n{texto}"
        ),
        "dados": {
            "total": len(registros),
            "entity_slug": app.slug,
            "ids": [r.pk for r in registros],
        },
    }


# --------------------------------------------------------------------------
# Registro
# --------------------------------------------------------------------------

INTENTS_DINAMICO = {
    "criar_entidade": {
        # ESCRITA — e por isso PEDE CONFIRMACAO.
        #
        # Sem esta flag, `sandbox.py:569` nao entra: o handler corre logo e
        # grava. O gate de confianca M3 nao cobre — so avisa, e so quando o
        # cliente manda um score, o que nao e' o caso comum.
        #
        # E o handler `h_criar_entidade` ja o diz no docstring: "ESCRITA, e
        # por isso pede confirmacao". A intencao estava escrita; a flag
        # ficou de fora.
        "requires_confirmation": True,
        # Texto PARA O PRODUTOR. `texto.py:113` usa este campo e so cai na
        # descricao — que e' escrita para o MODELO — quando o vazio.
        "prompt_confirmacao": (
            "Criar esta ferramenta na tua conta? Fica disponivel para registos."
        ),
        "descricao": (
            "INSTRUÇÃO IA: use para criar uma ferramenta virtual nova quando o "
            "produtor pedir algo que o sistema ainda nao tem ('crie um controle "
            "de geladeira', 'preciso registrar vacinas'). Voce escreve METADADOS, "
            "nunca codigo: a ferramenta vira uma linha de schema, e a tela e "
            "desenhada a partir dela. Cada campo: {rotulo, tipo, obrigatorio, "
            "opcoes?, ref_app?}. Tipos: " + ", ".join(TIPOS_ACEITOS) + "."
        ),
        "exemplos": [
            "crie uma ferramenta de controle de geladeira",
            "preciso de um app para registrar vacinas",
            "cria um controle de estoque de-thread",
            "monte uma ferramenta para anotações de manejo",
            "quero registrar a temperatura do silo",
        ],
        "params_schema": {
            "nome": {
                "type": "string",
                "description": "Nome da ferramenta. Ex: Controle de Geladeira",
            },
            "descricao": {"type": "string", "description": "Para que serve"},
            "icone": {
                "type": "string",
                "description": "Icone no painel. Ex: bi-thermometer-snow",
            },
            "campos": {
                "type": "array",
                "description": "Lista de campos: [{rotulo, tipo, obrigatorio, opcoes?}]. tipo em "
                + ", ".join(TIPOS_ACEITOS),
                "items": {"type": "object"},
            },
            "confirm": {
                "type": "boolean",
                "description": "true apos o produtor confirmar",
            },
        },
        "flags": ["criador_livre.write"],
        "handler": h_criar_entidade,
    },
    "inserir_registro": {
        "descricao": (
            "INSTRUÇÃO IA: use para gravar um registro em uma ferramenta criada "
            "pela IA. NUNCA invente o nome do campo: use exatamente as chaves que "
            "'criar_entidade'(devolveu ou que 'query_records' sem filtro mostrar). "
            "A tool RECUSA a gravacao se mandar uma chave que nao existe no schema, "
            "e a resposta traz as chaves válidas para voce corrigir."
        ),
        "exemplos": [
            "registra 12 kg de ração no inventário",
            "anota a temperatura da geladeira",
            "grava a vacina da vaca no registro de vacinas",
            "salva esse lançamento no controle de Fertilizantes",
        ],
        "params_schema": {
            "entity_slug": {
                "type": "string",
                "description": "Slug da ferramenta (o que criar_entidade devolveu)",
            },
            "dados": {
                "type": "object",
                "description": "Valores por campo. Use EXATAMENTE as chaves do schema: chave a mais e recusada.",
            },
            "confirm": {
                "type": "boolean",
                "description": "true apos o produtor confirmar",
            },
        },
        "flags": ["criador_livre.write"],
        # ESCRITA — e por isso PEDE CONFIRMACAO.
        #
        # Sem esta flag, `sandbox.py:569` nao entra: o handler corre
        # logo e grava. O gate de confianca M3 nao cobre — so avisa, e
        # so quando o cliente manda um score, o que nao e' o caso comum.
        "requires_confirmation": True,
        # Texto PARA O PRODUTOR. `texto.py:113` usa este campo e so cai
        # na descricao — que e' escrita para o MODELO — quando o vazio.
        "prompt_confirmacao": (
            "Gravar este registo? Vai para a ferramenta que indicares."
        ),
        "handler": h_inserir_registro,
    },
    "consultar_registros": {
        "descricao": (
            "INSTRUÇÃO IA: use para LER registros de uma ferramenta da IA. "
            "Suporta filtro por campo, e a tool RECUSA filtro com chave "
            "inexistente — se ela disser que o campo nao existe, use um dos "
            "campos validos que ela lista, em vez de concluir que nao ha dados."
        ),
        "exemplos": [
            "quaisrance tem no inventário",
            "lista as vacinas registradas",
            "o que ha registrado na geladeira",
            "consulta o controle de Fertilizantes",
        ],
        "params_schema": {
            "entity_slug": {"type": "string", "description": "Slug da ferramenta"},
            "filtros": {
                "type": "object",
                "description": "Filtro por campo. Chave inexistente e recusada.",
            },
            "limite": {"type": "integer", "description": "Quantos registros devolver"},
        },
        "flags": ["criador_livre.read"],
        "handler": h_consultar_registros,
    },
}
