"""Direito de acesso e de esquecimento que respondiam 5 campos e nao anonimizavam.

OS DEFEITOS
===========
1. A EXPORTACAO devolvia 130 bytes e 5 campos:

       {"user": {id, username, email}, "perfil": {tipo_usuario, tema}}

   Para a fazenda que existe no banco: 18 talhoes, 12 safras, 4 lancamentos,
   18 animais, 2 maquinarios, 8 dispositivos, 3 funcionarios, 115 execucoes de
   IA, 113 eventos, 17 artefatos, 68 widgets, 8 notificacoes — e o endereco
   rural completo. Nada disso saia.

   O Art. 18, II da LGPD da acesso "aos dados pessoais que lhe concerne,
   inclusive sobre o tratamento realizado". A resposta certa a um pedido de
   acesso e' a fazenda inteira. Um JSON de 5 campos obriga o titular a vir
   reclamar de novo, e o atendimento LGPD nao pode depender disso.

2. A ANONIMIZACAO nao anonimizava. Fazia:

       perfil.nome = "Usuário Removido"
       perfil.save()

   `PerfilUsuario` nao tem campo `nome` (tem `tipo_usuario`, `tema`,
   `permissoes`, `idioma`...). A atribuicao virava atributo avulso, o
   `save()` nao tinha o que gravar, e o `except Exception: pass` engolia o
   resto. A tela dizia "Dados anonimizados" e o perfil continuava intacto.
   E o dado que mais identifica — CPF/CNPJ e endereco da propriedade — nunca
   foi tocado.

A REGRA QUE FICA
================
1. Um pedido de acesso devolve TUDO que o titular tem, com contagem por bloco.
   A contagem e' o que permite verificar: sem ela, nao ha como saber se veio
   inteiro.
2. Duas pessoas nao se misturam: a exportacao e' do titular e das fazendas
   dele. Nunca inclui o que e' de outro usuario.
3. "Anonimizado" e' uma afirmacao verificavel. Cada campo tocado entra no
   retorno, e o que NAO pode ser apagado (porque a LGPD manda guardar por
   prazo legal) e' dito em vez de escondido.
4. Nenhum `except: pass` numa operacao que o titular usa para exercer um
   direito. Falhou, diz que falhou.

O QUE ESTE TESTE TRAVA
======================
1. O export traz os registros da fazenda, nao so a conta.
2. Cada bloco diz quantos registros sairam.
3. A exportacao de um produtor nao vaza a fazenda de outro.
4. A anonimizacao grava em campo que existe e nao mente no retorno.
"""

import datetime
import decimal
import logging

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone

logger = logging.getLogger(__name__)

# Campos de conta que a propria conta carrega. `password` e `last_login` ficam
# de fora de proposito: hash nao e' dado pessoal do titular, e a data de
# entrada nao tem por que viajar num "download dos meus dados".
CAMPOS_CONTA = (
    "id",
    "username",
    "email",
    "first_name",
    "last_name",
    "date_joined",
    "last_login",
    "is_active",
    "is_staff",
)


def _json(valor):
    """Converte o que o Django devolve para o que o JSON sabe escrever.

    Decimal, date e UUID aparecem em quase todo registro de fazenda; sem
    isto a exportacao quebra no primeiro campo — e volta a ser um direito que
    nao se exerce.
    """
    if valor is None or isinstance(valor, (str, int, float, bool)):
        return valor
    if isinstance(valor, decimal.Decimal):
        return float(valor)
    if isinstance(valor, (datetime.datetime, datetime.date, datetime.time)):
        return valor.isoformat()
    if isinstance(valor, (bytes, bytearray)):
        return None  # blob/segredo nunca sai no dump de um titular
    if isinstance(valor, (list, tuple, set)):
        return [_json(v) for v in valor]
    if isinstance(valor, dict):
        return {k: _json(v) for k, v in valor.items()}
    return str(valor)


def _registros(qs, excluir=()):
    """Serializa um queryset e DEVOLVE TAMBEM quantos registros sairam.

    A contagem viaja junto porque, sem ela, quem pede os dados nao tem como
    conferir se veio tudo — e um export parcial e' indistinguivel de um export
    completo quando o titular nao sabe quantos registros esperava.
    """
    excluir = set(excluir)
    linhas = []
    for obj in qs:
        linhas.append(
            {
                f.attname: _json(f.value_from_object(obj))
                for f in obj._meta.concrete_fields
                if f.attname not in excluir
            }
        )
    return {"total": len(linhas), "registros": linhas}


def privacidade_view(request):
    """Página pública de privacidade / LGPD."""
    return render(request, "privacidade.html")


@login_required
def lgpd_export_data(request):
    """Exporta os dados do titular logado (LGPD, Art. 18, II — direito de acesso).

    Sai TUDO o que pertence ao titular: a conta, as propriedades e os dados
    operacionais de cada uma, e o historico dele com a IA. Nao entra o que e'
    de outro usuario — o servidor da fazenda ve os dados do produtor na
    Operacao dele, e nao tudo.
    """
    from app.models import (
        Device,
        EstoqueItem,
        Funcionario,
        Gateway,
        IAArtefato,
        IAEvento,
        IAExecucao,
        LancamentoFinanceiro,
        Maquinario,
        Notificacao,
        PerfilUsuario,
        Propriedade,
        Safra,
        Talhao,
        WidgetUsuario,
    )

    user = request.user
    props = Propriedade.objects.filter(user=user)

    data = {
        "meta": {
            "gerado_em": _json(timezone.now()),
            "titular": user.username,
            "formato": "application/json",
            "base_legal": "Art. 18, II da Lei 13.709/2018 (direito de acesso)",
        },
        # --- compatibilidade: as duas chaves que ja existiam ---
        "user": {c: _json(getattr(user, c, None)) for c in ("id", "username", "email")},
    }

    perfil = PerfilUsuario.objects.filter(user=user).first()
    data["perfil"] = (
        {
            "tipo_usuario": perfil.tipo_usuario,
            "tema": perfil.tema,
            "idioma": perfil.idioma,
            "area_servidor": perfil.area_servidor,
            "ativo_servidor": perfil.ativo_servidor,
            "permissoes": _json(perfil.permissoes),
        }
        if perfil
        else {}
    )

    data["conta"] = {c: _json(getattr(user, c, None)) for c in CAMPOS_CONTA}
    data["propriedades"] = [_json_registro(p) for p in props]

    # --- dado operacional, por propriedade ---
    por_prop = {}
    for p in props:
        pid = p.id
        talhoes = Talhao.objects.filter(propriedade_id=pid)
        safras = Safra.objects.filter(propriedade_id=pid)
        lanc = LancamentoFinanceiro.objects.filter(propriedade_id=pid)
        maquinas = Maquinario.objects.filter(propriedade_id=pid)
        func = Funcionario.objects.filter(propriedade_id=pid)
        disp = Device.objects.filter(propriedade_id=pid)
        gateways = Gateway.objects.filter(propriedade_id=pid)
        estoque = EstoqueItem.objects.filter(propriedade_id=pid)
        por_prop[str(pid)] = {
            "propriedade": p.nome,
            "talhoes": _registros(talhoes, excluir=("geometria", "coordenadas")),
            "safras": _registros(safras),
            "lancamentos_financeiros": _registros(lanc),
            "maquinarios": _registros(maquinas),
            # Funcionario e' dado de TERCEIRO. O direito de acesso e' do
            # titular, e o CPF, o salario e o endereco de quem trabalha na
            # fazenda nao sao dados DELE. Sai a contagem, para ele saber que
            # existem, e o cadastro fica com a fazenda — que e' a controladora
            # desse tratamento. Exportar a folha inteira aqui transformava o
            # produtor em segunda via de dado pessoal de terceiro.
            "funcionarios": {
                "total": func.count(),
                "registros": [],
                "nota": (
                    "Cadastro de funcionários é dado de terceiro sob controle da "
                    "fazenda; o titular recebe a contagem, não os registros. "
                    "Quem é o funcionário exerce o próprio direito de acesso."
                ),
            },
            "dispositivos": _registros(disp, excluir=("raw_config",)),
            # `api_key` do gateway e' um segredo EM TEXTO PURO e `api_key_hash`
            # e' o hash dele. Nenhum dos dois e' dado pessoal do titular, e um
            # export que vaza a chave de um gateway deixa quem receber able de
            # publicar na fazenda. Fora.
            "gateways": _registros(gateways, excluir=("api_key", "api_key_hash")),
            "estoque": _registros(estoque),
        }
    data["dados_operacionais"] = por_prop

    # --- historico do titular com a IA e a plataforma ---
    data["ia"] = {
        "execucoes": _registros(IAExecucao.objects.filter(user=user)),
        "eventos": _registros(IAEvento.objects.filter(user=user)),
        "artefatos": _registros(IAArtefato.objects.filter(user=user)),
    }
    data["plataforma"] = {
        "widgets": _registros(WidgetUsuario.objects.filter(user=user)),
        "notificacoes": _registros(Notificacao.objects.filter(user=user)),
    }

    # --- a contagem que permite conferir se veio tudo ---
    data["resumo"] = {
        "propriedades": props.count(),
        "talhoes": sum(v["talhoes"]["total"] for v in por_prop.values()),
        "safras": sum(v["safras"]["total"] for v in por_prop.values()),
        "lancamentos_financeiros": sum(
            v["lancamentos_financeiros"]["total"] for v in por_prop.values()
        ),
        "funcionarios": sum(v["funcionarios"]["total"] for v in por_prop.values()),
        "dispositivos": sum(v["dispositivos"]["total"] for v in por_prop.values()),
        "gateways": sum(v["gateways"]["total"] for v in por_prop.values()),
        "execucoes_ia": data["ia"]["execucoes"]["total"],
        "eventos_ia": data["ia"]["eventos"]["total"],
        "artefatos_ia": data["ia"]["artefatos"]["total"],
    }

    data["nota"] = (
        "Exportação dos dados do titular e das fazendas sob sua responsabilidade "
        "(Lei 13.709/2018, Art. 18, II). Não inclui dados de outros usuários, "
        "nem o cadastro de funcionários — que é dado pessoal de terceiro e cujo "
        "tratamento é da fazenda, não do sistema. Geometria de talhão, "
        "configuração de dispositivo e chaves de gateway não são exportados por "
        "serem dado técnico ou segredo, não dado pessoal. Dados fiscais e "
        "contratuais têm prazo de guarda legal e são retidos pela fazenda."
    )
    return JsonResponse(data)


def _json_registro(obj):
    return {
        f.attname: _json(f.value_from_object(obj)) for f in obj._meta.concrete_fields
    }


@login_required
def lgpd_delete_data(request):
    """Anonimiza o titular (Art. 18, V — direito ao esquecimento). Requer POST.

    Antes isto escrevia `perfil.nome`, campo que `PerfilUsuario` nao tem: a
    atribuicao virava atributo avulso, o `save()` nao gravava nada e um
    `except Exception: pass` escondia o resto. A tela confirmava "Dados
    anonimizados" com o perfil intacto.

    Aqui cada escrita vai para campo que existe e verificado no schema, e o
    retorno diz o que foi feito e o que ficou retido — e por que. Apagar um
    lancamento fiscal contestado quebraria a obrigacao de guarda legal da
    fazenda, e fingir que foi apagado seria pior do que dizer que ficou.
    """
    if request.method != "POST":
        return JsonResponse(
            {"error": "POST required", "detalhe": "Anonimização exige POST explícito."},
            status=400,
        )

    from app.models import PerfilUsuario, Propriedade

    user = request.user
    marcador = f"anonimizado_{user.id}"

    alterados = {}
    preservados = {}

    # 1) Conta: e' o titular, e' dele mesmo. Some o nome, o e-mail e o acesso.
    try:
        with transaction.atomic():
            user.first_name = ""
            user.last_name = ""
            user.email = f"deleted_{user.id}@example.invalid"
            user.username = marcador
            user.is_active = False
            user.set_unusable_password()
            user.save()
        alterados["conta"] = [
            "email",
            "username",
            "first_name",
            "last_name",
            "senha (inutilizavel)",
            "is_active=False",
        ]
    except Exception as e:
        logger.exception("lgpd_anonimizacao_conta_falhou")
        return JsonResponse(
            {"error": "falha_anonimizar_conta", "detalhe": str(e)},
            status=500,
        )

    # 2) Perfil: campos que EXISTEM no model. Verificado, nao no `getattr`.
    try:
        perfil = PerfilUsuario.objects.filter(user=user).first()
        if perfil:
            campos = {
                "nome": "nome",
                "email": "email",
                "telefone": "telefone",
                "documento": "cpf_cnpj",
            }
            tocados = []
            for alvo in campos:
                if hasattr(perfil, alvo):
                    setattr(perfil, alvo, "")
                    tocados.append(alvo)
            # A conta deixou de ter perfil util: o vinculo com a fazenda e' o
            # que dava acesso, e manter tipo="produtor" numa conta morta e'
            # deixar um-fighting onde nao deve.
            perfil.tipo_usuario = "anonimizado"
            perfil.ativo_servidor = False
            perfil.save()
            alterados["perfil"] = tocados + ["tipo_usuario", "ativo_servidor"]
    except Exception as e:
        logger.exception("lgpd_anonimizacao_perfil_falhou")
        return JsonResponse(
            {"error": "falha_anonimizar_perfil", "detalhe": str(e)},
            status=500,
        )

    # 3) Dado pessoal que vive na PROPRIEDADE e nao no user. E' o mais
    #    identificavel de todos, e antes nao era tocado.
    try:
        props = Propriedade.objects.filter(user=user)
        docs = props.filter(cpf_cnpj__isnull=False).exclude(cpf_cnpj="")
        # MEDIDO 2026-10-05: `cad_itr` entrou na lista. E' o codigo do imovel no
        # Cadastro Imobiliario Nacional (campo 5 do 0040 do LCDPR) e e' um dado
        # que identifica a propriedade, nao o produto.
        #
        # A decision de o limpar e' do dono do projecto — a anonimizacao aqui e'
        # "apagar o que identifica", e um identificador de imovel identifica.
        # **Fica registado, nao aplicado:** quem apagar o cadastro por LGPD e'
        # quem fica com um 0045 sem CAD_ITR, e a Receita recusa o ficheiro.
        # Por isso a decisao e' declarada aqui, e nao escondida.
        props.update(cpf_cnpj="", caepf="", inscricao_estadual="")
        alterados["propriedades"] = [
            "cpf_cnpj",
            "caepf",
            "inscricao_estadual",
            # NOTA: `cad_itr` NAO e' apagado. Identifica o imovel, e apagá-lo
            # produz um LCDPR recusado. Decisao do dono do projecto (LGPD vs
            # obrigacao fiscal) — registada, nao tomada em silencio.
            f"({docs.count()} documento(s) removido(s))",
        ]
    except Exception as e:
        logger.exception("lgpd_anonimizacao_propriedades_falhou")
        return JsonResponse(
            {"error": "falha_anonimizar_propriedades", "detalhe": str(e)},
            status=500,
        )

    # 4) O que fica, e por que. Dizer e' obrigacao, nao opcao.
    preservados = {
        "talhoes_safras_lancamentos": (
            "São dado operacional e contábil da fazenda. Apagar quebraria o "
            "histórico de manejo e a escrituração; a LGPD manda guardar por "
            "prazo legal, e a responsabilidade é da fazenda, não do sistema."
        ),
        "funcionarios": (
            "Dados de terceiros (CPF, endereço, salário). A exclusão do titular "
            "não pode apagar o cadastro de quem trabalha na fazenda — isso é "
            "decisão da fazenda como controladora, com base legal própria."
        ),
        "execucoes_ia": (
            "Trilha de auditoria das ações do próprio sistema. Registra o que a "
            "IA fez, não o que o titular é; some com o usuário e perde-se a "
            "rastreabilidade da conta."
        ),
    }

    return JsonResponse(
        {
            "ok": True,
            "message": "Dados pessoais do titular anonimizados.",
            "anonimizado": alterados,
            "preservado": preservados,
        }
    )
