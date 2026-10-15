import structlog
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone

from app.models import CentroCusto, Propriedade

logger = structlog.get_logger(__name__)


@receiver(post_save, sender="auth.User")
def garantir_perfil_usuario(sender, instance, created, **kwargs):
    """Todo User nasce com PerfilUsuario.

    Sem este sinal, contas criadas fora de `app/views/auth.py` — o SSO Google
    (django-allauth, `config/urls.py:15`) e o admin do Django — ficavam SEM
    perfil. E `app/hierarquia.py` tratava "sem perfil" como produtor de acesso
    total (`except: return True`), ou seja, um login SSO ganhava permissão de
    produtor e de financeiro sem nenhuma verificação. `get_or_create` mantém o
    perfil que o produtor já definiu (ex.: servidor com área).
    """
    if not created:
        return
    from app.models import PerfilUsuario

    PerfilUsuario.objects.get_or_create(
        user=instance, defaults={"tipo_usuario": "produtor"}
    )


@receiver(post_save, sender=Propriedade)
def criar_centros_padrao(sender, instance, created, **kwargs):
    if not created:
        return
    for tipo, nome in [
        ("AGRICULTURA", "Agricultura"),
        ("PECUARIA", "Pecuária"),
        ("MECANICA", "Mecânica"),
        ("SEDE", "Sede"),
    ]:
        CentroCusto.objects.get_or_create(
            propriedade=instance, tipo=tipo, defaults={"nome": nome}
        )


@receiver(pre_save, sender="app.TarefaEstagio")
def sync_tarefa_status(sender, instance, **kwargs):
    """Sincroniza concluida <-> status e denormaliza propriedade."""
    if instance.concluida and instance.status != "concluido":
        instance.status = "concluido"
        if not instance.concluida_em:
            instance.concluida_em = timezone.now()
    elif instance.status == "concluido" and not instance.concluida:
        instance.concluida = True
        if not instance.concluida_em:
            instance.concluida_em = timezone.now()
    elif instance.status in ["pendente", "andamento"] and instance.concluida:
        instance.concluida = False
        instance.concluida_em = None

    # Denormaliza propriedade via estagio -> registro -> user -> propriedade
    if not instance.propriedade_id and instance.estagio_id:
        try:
            reg_user = instance.estagio.registro.user
            prop = Propriedade.objects.filter(user=reg_user).first()
            if prop:
                instance.propriedade = prop
        except Exception:
            logger.warning(
                "falha_denormalizar_propriedade",
                tarefa_id=getattr(instance, "pk", None),
            )


@receiver(pre_save, sender="app.LancamentoFinanceiro")
def validar_tipo_e_categoria_coerentes(sender, instance, **kwargs):
    """Impede gravar folha/insumo/frete... como RECEITA.

    O `clean()` do model diz o que e' incoerente; este sinal garante que ele
    seja chamado. `Model.save()` NAO chama `full_clean()` — quem chama e' o
    serializer do DRF, e so nos casos que ele cobre. Um POST direto, um
    `objects.create()` num script de importacao ou o admin passariam sem
    verificacao nenhuma.

    Este sinal e' o ponto que nao tem bypass: e' o mesmo lugar onde o saldo de
    insumo ja e' validado, por exatamente este motivo.

    Chama `clean()`, e nao `full_clean()`. `full_clean()` valida TAMBEM os
    campos — e `categoria` e' `blank=False`, entao chamar isso aqui passou a
    exigir categoria em `objects.create()`, num script de importacao ou num
    teste que antes nao precisava dela. Trocou-se um bug de dado por uma
    quebra de contrato em toda a escrita do sistema. O que se quer travar e' a
    invariante entre `tipo` e `categoria`, e `clean()` e' exatamente isso.
    """
    instance.clean()


@receiver(pre_save, sender="app.AplicacaoInsumo")
def validar_saldo_insumo(sender, instance, **kwargs):
    """Bloqueia aplicação sem saldo (vale p/ API, admin e IA)."""
    if instance.pk:
        return  # edição não rebaixa de novo; só criação consome
    from app.models import Insumo

    insumo = Insumo.objects.filter(pk=instance.insumo_id).first()
    if insumo and (insumo.quantidade or 0) < (instance.dose or 0):
        raise ValidationError(
            f"Saldo insuficiente de {insumo.nome}: "
            f"tem {insumo.quantidade} {insumo.unidade}, precisa {instance.dose}."
        )


@receiver(post_save, sender="app.AplicacaoInsumo")
def baixar_estoque_insumo(sender, instance, created, **kwargs):
    """Baixa automática atômica do estoque ao aplicar (F expression)."""
    if not created:
        return
    from app.models import Insumo

    with transaction.atomic():
        n = Insumo.objects.filter(
            pk=instance.insumo_id, quantidade__gte=instance.dose or 0
        ).update(quantidade=F("quantidade") - (instance.dose or 0))
        if not n:
            logger.warning(
                "baixa_estoque_corrida",
                insumo_id=instance.insumo_id,
                aplicacao_id=instance.pk,
            )


@receiver(post_delete, sender="app.AplicacaoInsumo")
def restaurar_estoque_insumo(sender, instance, **kwargs):
    """Excluiu a aplicação → devolve a dose ao estoque."""
    from app.models import Insumo

    Insumo.objects.filter(pk=instance.insumo_id).update(
        quantidade=F("quantidade") + (instance.dose or 0)
    )


def _notificar_tarefa(
    titulo, mensagem, link, propriedade, funcionario=None, cargo_alvo=""
):
    """Entrega instantânea: Notificacao cai no sino do trabalhador na hora.

    Alvos: usuário ligado ao funcionário > usuários com mesmo cargo na
    propriedade. Nunca quebra o save (tudo em try/except).
    """
    try:
        from app.models import Funcionario, Notificacao

        if not propriedade:
            return
        alvos = set()
        if funcionario and getattr(funcionario, "user_id", None):
            alvos.add(funcionario.user_id)
        if cargo_alvo:
            for f in Funcionario.objects.filter(
                propriedade=propriedade, cargo=cargo_alvo, ativo=True
            ).exclude(user=None):
                alvos.add(f.user_id)
        for uid in alvos:
            from django.utils import timezone as _tz

            if Notificacao.objects.filter(
                user_id=uid,
                titulo=titulo,
                criado_em__gte=_tz.now() - _tz.timedelta(hours=24),
            ).exists():
                continue
            Notificacao.objects.create(
                user_id=uid,
                titulo=titulo,
                mensagem=mensagem,
                nivel="info",
                link=link,
            )
    except Exception:
        logger.warning("falha_push_tarefa", titulo=titulo)


@receiver(post_save, sender="app.AtividadePlanejada")
def push_atividade_criada(sender, instance, created, **kwargs):
    """IA/painel criou tarefa → aparece no dispositivo do trabalhador."""
    if not created:
        return
    try:
        prop = instance.plano.safra.propriedade
    except Exception:
        prop = None
    _notificar_tarefa(
        titulo=f"Nova tarefa: {instance.nome[:80]}",
        mensagem=f"{instance.nome[:120]} — prevista para {instance.data_prevista}.",
        link="/servidor/kanban/",
        propriedade=prop,
        funcionario=getattr(instance, "funcionario", None),
        cargo_alvo=getattr(instance, "cargo_alvo", "") or "",
    )


@receiver(post_save, sender="app.TarefaEstagio")
def push_tarefa_kanban_criada(sender, instance, created, **kwargs):
    """Kanban criou tarefa → sino do responsável na hora."""
    if not created:
        return
    _notificar_tarefa(
        titulo=f"Nova tarefa: {(instance.descricao or '')[:80]}",
        mensagem=(instance.descricao or "")[:150],
        link="/servidor/kanban/",
        propriedade=getattr(instance, "propriedade", None),
        funcionario=getattr(instance, "funcionario", None),
        cargo_alvo=getattr(instance, "cargo_alvo", "") or "",
    )
