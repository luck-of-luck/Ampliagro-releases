"""
Configuração dinâmica de campos por cultura baseada em cultures-config.json v2.0.0.
Carrega a configuração e expõe helpers para serializers dinâmicos.

NOVO (v2.1): Regras de negócio, templates de tarefas, automações e personalização do usuário.
"""

import json
from datetime import date
from pathlib import Path

from django.conf import settings
from django.core.cache import cache

#: O sentinel de "sem valor" do DRF. Vive em `rest_framework.fields`, e nao
#: em `django.forms.fields` — a primeira tentativa de o importar de la deu
#: ImportError. E' o mesmo objecto que o DRF usa internamente para
#: distinguir "nao passou default" de "passou default=None".
from rest_framework.fields import empty as _VAZIO

CONFIG_PATH = (
    Path(settings.BASE_DIR) / "app" / "static" / "data" / "cultures-config.json"
)
CACHE_KEY = "cultures_config_v2"
CACHE_TIMEOUT = 3600  # 1h
#: O índice `slug -> cultura` derivado de `groups`. Cache separado do config
#: porque tem TTL igual mas invalidação diferente: muda quando o ficheiro
#: muda, e não quando o `load_cultures_config` é chamado.
CACHE_KEY_INDICE = "cultures_indice_v1"


def load_cultures_config():
    """Carrega o JSON de configuração de culturas (com cache)."""
    data = cache.get(CACHE_KEY)
    if data:
        return data
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            data = json.load(f)
        cache.set(CACHE_KEY, data, CACHE_TIMEOUT)
        return data
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# O INDEX DE CULTURAS
# ---------------------------------------------------------------------------
# MEDIDO em 2026-10-03, e é a correcção que fecha o V1.
#
# Este módulo lia `config.get("culturas", {})` e devolvia `{}` SEMPRE. O
# ficheiro `cultures-config.json` não tem a chave `culturas` — tem `groups`,
# uma lista de grupos, cada um com `subgroups`, cada um com `cultures`.
# `.get(chave, {})` num dicionário sem a chave dá `{}` e não dá erro, que é
# a pior forma de falhar: 527 linhas de motor a correr sem uma única regra.
#
# A estrutura correcta NÃO É HIPÓTESE. `app/static/js/cultures-loader.js`
# (o que o browser executa) já a percorre, em `applyConfig()`:
#
#     (config.groups || []).forEach(function (g) {
#       if (g.cultures) { ... }
#       if (g.subgroups) { (sg.cultures || []).forEach(...) }
#
# Ou seja: o browser e o Python já estão a falar de formatos diferentes, e o
# PWA é que tem razão. A correção é alinhar o Python com o PWA — não o
# contrário. Migrar o JSON para a forma antiga significava alterar um ficheiro
# de 241 KB que uma app de 546 linhas já consome sem queixas.
#
# As duas posições de onde uma cultura pode estar (direto no grupo, ou num
# subgroup) são as duas que o loader trata, pelas mesmas linhas.
# ---------------------------------------------------------------------------


def _indice_culturas() -> dict:
    """{django_nome com accentos preguicosos: cultura} a partir de `groups`.

    A chave é derivada como em `alert_engine.py:267-273` — o único outro
    lugar que sabe fazer esta ligação — para que o motor e os alertas
    encontrem a mesma cultura.

    O resultado é cacheado à parte do config: aplanar 488 culturas a cada
    chamada seria caro num endpoint, e `load_cultures_config` já tem o seu
    próprio cache.
    """
    indice = cache.get(CACHE_KEY_INDICE)
    if indice is not None:
        return indice

    indice = {}
    for grupo in load_cultures_config().get("groups", []):
        # Direto no grupo, como o loader faz primeiro.
        for cultura in grupo.get("cultures", []) or []:
            _guarda(indice, cultura, grupo)
        for sub in grupo.get("subgroups", []) or []:
            for cultura in sub.get("cultures", []) or []:
                _guarda(indice, cultura, grupo)

    cache.set(CACHE_KEY_INDICE, indice, CACHE_TIMEOUT)
    return indice


def _preguicosos(texto):
    """`Café` -> `cafe`. Uma cultura por qualquer das chaves do índice.

    MEDIDO: a sequência de `.replace()` que estava aqui antes só cobria
    `é`/`á`/`ç`, e só em minúscula. **43 das 488 culturas (9%) não ficavam
    normalizáveis** — `Algodão` (o `ã` fica), `Cana-de-açúcar` (o `ç` e o `ú`),
    e qualquer nome com a maiúscula acentuada. Para essas,
    `evaluate_culture_alerts` derivava um slug que não batia com nada, e a
    cultura do produtor nunca encontrava a sua regra. Nomes com acento: á em 22,
    ç em 14, é em 6, ã em 3, í em 2, ú em 1, Á em 1.

    NÃO é `unicodedata.normalize`: essa decompõe `ç` em `c` + cedilha
    combinante, e o resultado não é o slug que o resto do sistema já usa.

    `app/iot/alert_engine.py` chama ESTA função, pelo nome público
    `cultura_slug`. Duas funções a normalizar o mesmo nome, uma delas
    incompleta, são a origem do defeito — não a correcção dele.
    """
    texto = str(texto or "")
    # `lower()` ANTES de trocar: é o que torna a tabela abaixo suficiente
    # (`É`.lower() == `é`). Ao contrário, `É` ficava de fora.
    saida = texto.lower().replace(" ", "-")
    for de, para in _ACENTOS.items():
        saida = saida.replace(de, para)
    return saida


#: O mesmo nome, público, para quem precisar de um slug de cultura sem o
#: índice. `alert_engine.py` usa este.
cultura_slug = _preguicosos


#: De/para da normalização, em minúsculas (o `.lower()` já correu).
#: MEDIDO a partir das 488 culturas do ficheiro — são estes que aparecem.
_ACENTOS = {
    "á": "a",  # á
    "à": "a",  # à
    "â": "a",  # â
    "ã": "a",  # ã
    "é": "e",  # é
    "ê": "e",  # ê
    "í": "i",  # í
    "ó": "o",  # ó
    "ô": "o",  # ô
    "õ": "o",  # õ
    "ú": "u",  # ú
    "ç": "c",  # ç
    "ñ": "n",  # ñ
}


def _guarda(indice, cultura, grupo):
    """Mete a cultura no índice, sob o nome e sob o id.

    O id (`cult-graos-milho`) é a chave que o browser usa como
    `window.CULTURE_METRICS[c.id]` e `window.WIDGET_TYPES[c.id]`. Guardar
    os dois faz o backend aceitar o mesmo identificador que o frontend já
    manda, seja qual for o que o chamador tenha à mão.
    """
    if not isinstance(cultura, dict):
        return
    reg = dict(cultura)
    reg.setdefault("django_grupo", grupo.get("id", "outro"))
    reg.setdefault("django_nome", cultura.get("title", ""))

    for chave in {
        _preguicosos(reg.get("django_nome")),
        _preguicosos(reg.get("title")),
        reg.get("django_nome") or "",
        reg.get("title") or "",
        cultura.get("id") or "",
    }:
        if chave:
            indice.setdefault(chave, reg)


def _cultura(cultura_slug):
    """A cultura, ou `{}`. Nunca levanta: quem chama decide o que fazer."""
    if not cultura_slug:
        return {}
    return _indice_culturas().get(str(cultura_slug).strip().lower(), {})


def get_culture_fields(cultura_slug):
    """
    Retorna a lista de campos customizados para uma cultura.
    Cada item: {key, label, type, unit, required, default, options?, validation?}
    """
    return _cultura(cultura_slug).get("fields", [])


def get_culture_metrics(cultura_slug):
    """Retorna métricas padrão da cultura (dashboard, cards, etc.)."""
    cultura = _cultura(cultura_slug)
    if cultura.get("metrics"):
        return cultura["metrics"]
    # O browser (`cultures-loader.js:130-147`) faz o mesmo: parte de
    # `default_metrics` e sobrepõe com `metrics_override` da cultura. Aqui só
    # a metade do backend — quando `default_metrics` estiver vazio, isto dá
    # `{}`, como dava antes, e o browser continua a ser a fonte do que o
    # produtor vê no ecrã.
    base = load_cultures_config().get("default_metrics", {}) or {}
    override = cultura.get("metrics_override") or {}
    # MEDIDO 2026-10-05: era `if not (base and override)`. Com o `and`, a
    # funcao so devolvia metricas se as DUAS coisas existissem — e como
    # `default_metrics` esta' vazio no config, ela era estruturalmente
    # incapaz de devolver uma unica metrica, para qualquer cultura. O
    # `override` e' o que sobrescreve: e' opcional por definicao. O que tem
    # de existir e' a base.
    if not base:
        return {}
    metrics = {k: dict(v) if isinstance(v, dict) else v for k, v in base.items()}
    for k, ov in override.items():
        if k in metrics and isinstance(ov, dict):
            metrics[k] = {**metrics[k], **ov}
    return metrics


def get_culture_stages(cultura_slug):
    """Retorna estágios (phenology) da cultura para painel de tarefas."""
    return _cultura(cultura_slug).get("stages", [])


def get_culture_business_rules(cultura_slug):
    """
    Retorna regras de negócio da cultura:
    - planting_window: {start_month, end_month, region_overrides?}
    - alerts: [{trigger, message, level, condition?}]
    - validation_rules: [{field, rule, message}]
    - defaults: {field: value}
    """
    return _cultura(cultura_slug).get("business_rules", {})


def get_culture_task_templates(cultura_slug):
    """
    Retorna templates de tarefas por estágio.
    Usado para auto-criar tarefas ao avançar/mudar estágio.
    Formato: {stage_name: [{titulo, descricao, cargo_alvo, setor, dias_offset, obrigatoria}]}
    """
    return _cultura(cultura_slug).get("task_templates", {})


def get_culture_automations(cultura_slug):
    """
    Retorna regras de automação da cultura.
    Formato: {trigger: {action, params, condition?}}
    Triggers: 'stage_enter', 'stage_complete', 'task_complete', 'date_reached', 'alert_threshold'
    Actions: 'create_task', 'send_notification', 'update_field', 'create_registro', 'webhook'
    """
    return _cultura(cultura_slug).get("automations", {})


def get_user_culture_preferences(user, cultura_slug):
    """
    Retorna preferências do usuário para uma cultura (personalização).
    Busca no PerfilUsuario ou cria defaults.
    """
    from app.models import PerfilUsuario

    try:
        perfil = PerfilUsuario.objects.get(user=user)
        prefs = perfil.config.get("culture_preferences", {}).get(cultura_slug, {})
    except PerfilUsuario.DoesNotExist:
        prefs = {}

    # Defaults sensíveis
    defaults = {
        "show_advanced_fields": False,
        "compact_mode": False,
        "auto_advance_stage": False,
        "notification_channels": ["in_app"],
        "preferred_units": {},
        "custom_field_order": [],
        "hidden_fields": [],
        "default_values": {},
    }
    defaults.update(prefs)
    return defaults


def set_user_culture_preferences(user, cultura_slug, preferences):
    """Salva preferências do usuário para uma cultura."""
    from app.models import PerfilUsuario

    perfil, _ = PerfilUsuario.objects.get_or_create(user=user)
    config = perfil.config or {}
    culture_prefs = config.setdefault("culture_preferences", {})
    culture_prefs[cultura_slug] = {**culture_prefs.get(cultura_slug, {}), **preferences}
    perfil.config = config
    perfil.save(update_fields=["config"])
    return culture_prefs[cultura_slug]


def get_unit_config(unit_key):
    """Retorna configuração de unidade (label, grupo, conversão SI)."""
    config = load_cultures_config()
    return config.get("units", {}).get(unit_key, {})


def build_dynamic_serializer_fields(cultura_slug, user=None):
    """
    Constrói dict de campos DRF para uma cultura específica.
    Se user fornecido, aplica preferências (oculta campos, reordena, defaults).
    """
    from rest_framework import serializers

    fields_cfg = get_culture_fields(cultura_slug)
    prefs = get_user_culture_preferences(user, cultura_slug) if user else {}

    hidden = set(prefs.get("hidden_fields", []))
    custom_order = prefs.get("custom_field_order", [])
    defaults = prefs.get("default_values", {})

    # Ordena: custom_order primeiro, depois ordem original
    ordered = sorted(
        [f for f in fields_cfg if f["key"] not in hidden],
        key=lambda f: custom_order.index(f["key"]) if f["key"] in custom_order else 999,
    )

    dynamic_fields = {}
    for f in ordered:
        key = f["key"]
        field_type = f.get("type", "string")
        required = f.get("required", False)

        # MEDIDO 2026-10-05: os 6 ramos abaixo passavam `required=required` E
        # `default=default` ao mesmo tempo. O DRF recusa isso na inicializacao
        # do campo:
        #
        #     AssertionError: May not set both `required` and `default`
        #
        # que e' um 500 a correr. Basta uma cultura ter UM campo obrigatorio
        # com valor por omissao para `get_registro_producao_serializers` levantar
        # — e `fields` passou a existir em culturas reais (soja, milho, cafe),
        # pelo que deixou de ser hipotetico.
        #
        # A correccao e' AQUI, e nao em cada ramo: `required=True` significa
        # "sem omissao", que e' a definicao. Um campo obrigatorio nao tem
        # default que se lhe aplique — se o produtor nao o preencher, o
        # serializer tem de recusar, e nao inventar o valor.
        #
        # E o valor a por nao e' `None` (primeira tentativa, e' errada): o DRF
        # compara com o sentinel `empty`, e `None` E' um valor. Passar
        # `default=None` continua a disparar a assertiva. Tem de ser
        # `django.forms.fields.empty`, que e' o que o DRF usa internamente.
        default = _VAZIO if required else defaults.get(key, f.get("default", None))

        if field_type in ("number", "decimal", "integer"):
            if field_type == "integer":
                field_cls = serializers.IntegerField
            elif field_type == "decimal":
                max_digits = f.get("max_digits", 12)
                decimal_places = f.get("decimal_places", 2)
                dynamic_fields[key] = serializers.DecimalField(
                    required=required,
                    default=default,
                    max_digits=max_digits,
                    decimal_places=decimal_places,
                    help_text=f.get("label", key),
                )
                continue
            else:
                field_cls = serializers.FloatField
            dynamic_fields[key] = field_cls(
                required=required,
                default=default,
                help_text=f.get("label", key),
            )
        elif field_type == "boolean":
            dynamic_fields[key] = serializers.BooleanField(
                required=required,
                default=default,
                help_text=f.get("label", key),
            )
        elif field_type == "date":
            dynamic_fields[key] = serializers.DateField(
                required=required,
                default=default,
                help_text=f.get("label", key),
            )
        elif field_type == "choice":
            choices = f.get("options", [])
            dynamic_fields[key] = serializers.ChoiceField(
                choices=[(c, c) for c in choices],
                required=required,
                default=default,
                help_text=f.get("label", key),
            )
        else:
            dynamic_fields[key] = serializers.CharField(
                required=required,
                default=default,
                allow_blank=not required,
                help_text=f.get("label", key),
            )

    return dynamic_fields


def get_estagios_json(cultura_slug):
    """Retorna estágios formatados para o template JS (nome, cor, ordem)."""
    stages = get_culture_stages(cultura_slug)
    if not stages:
        return []
    return [
        {
            "nome": s.get("nome", f"Estágio {i + 1}"),
            "cor": s.get("cor", "#0f9d6e"),
            "icone": s.get("icone", "bi-circle-fill"),
            "ordem": s.get("ordem", i),
        }
        for i, s in enumerate(stages)
    ]


# ============================================================================
# ENGINE DE REGRAS DE NEGÓCIO & AUTOMAÇÕES
# ============================================================================


class CultureBusinessEngine:
    """
    Motor de regras de negócio e automações por cultura.
    Uso:
        engine = CultureBusinessEngine('cafe')
        engine.validate_planting_date(plantio_date, uf='MG')
        engine.get_active_alerts(registro)
        engine.run_automations(trigger='stage_enter', context={...})
    """

    def __init__(self, cultura_slug):
        self.cultura_slug = cultura_slug
        self.rules = get_culture_business_rules(cultura_slug)
        self.task_templates = get_culture_task_templates(cultura_slug)
        self.automations = get_culture_automations(cultura_slug)

    # --- Janela de plantio ---
    def is_planting_season(self, check_date=None, uf=None):
        """A data esta dentro da janela de plantio?

        MEDIDO 2026-10-05. Antes devolvia `True` quando a cultura nao tinha
        regra: *"sem regra = sempre permitido"* (a linha era a 412).

        Isso e o sistema a **afirmar** que se pode plantar quando nao sabe. E
        exactamente o que `validators.py:40` proibe — *"o sistema nunca
        promove uma afirmacao a medicao"* — feito ao contrario, e em silencio:
        sem `suspect`, sem `sem_dado`, sem aviso no ecra. O plano §1.1 classifica
        isto como a incoerencia mais cara que resta.

        Agora devolve **tres** valores, e quem chama tem de os distinguir:

            True   — dentro da janela, e a janela existe
            False  — fora da janela, e a janela existe
            None   — **nao se sabe**: a cultura nao tem janela definida

        `None` e o estado `sem_dado` da proveniencia, aplicado a uma janela.
        Nao e um valor de omissao — e a unica resposta honesta para quem nao
        tem o dado.

        Por que `None` e nao `False`: `False` significa "esta fora da janela",
        que e' uma **afirmacao**. `None` significa "ha regra?". Um e' medicao, o
        outro e' ausencia. Trocar `True` por `False` seria trocar uma
        mentira por outra, e mais subtil — porque `False` parece uma resposta.
        """
        check_date = check_date or date.today()
        window = self.rules.get("planting_window", {})
        if not window:
            return None  # sem regra: nao se sabe. Ver docstring.

        start = window.get("start_month", 1)
        end = window.get("end_month", 12)

        # Override por UF
        if uf and "region_overrides" in window:
            override = window["region_overrides"].get(uf.upper())
            if override:
                start = override.get("start_month", start)
                end = override.get("end_month", end)

        month = check_date.month
        if start <= end:
            dentro = start <= month <= end
        else:  # janela cruza ano (ex: out-mar)
            dentro = month >= start or month <= end
        return dentro

    def get_planting_window_message(self, uf=None):
        """A janela de plantio em linguagem de produtor, ou `None`.

        MEDIDO 2026-10-05: `None` significava duas coisas diferentes — "esta
        cultura nao tem janela" e "ha janela mas nao ha para mostrar". Agora
        dizemos as duas ao jogador, porque a segunda e' a que importa: uma
        cultura com regra e sem mensagem e' um espaco morto na UI.

        Este `None` e' o mesmo `None` de `is_planting_season`: **nao se sabe**.
        """
        window = self.rules.get("planting_window", {})
        if not window:
            # A UI tem de distinguir isto de "fora da janela" e dizer
            # "nao temos regra agronomica para esta cultura", nao sugerir
            # que pode plantar porque sim. O painel trata `None` como
            # `sem_dado` — ver `proveniencia.py`.
            return None
        start = window.get("start_month", 1)
        end = window.get("end_month", 12)
        meses = [
            "Jan",
            "Fev",
            "Mar",
            "Abr",
            "Mai",
            "Jun",
            "Jul",
            "Ago",
            "Set",
            "Out",
            "Nov",
            "Dez",
        ]
        if start <= end:
            return f"Janela ideal: {meses[start - 1]} a {meses[end - 1]}"
        return f"Janela ideal: {meses[start - 1]}-Dez e Jan-{meses[end - 1]}"

    # --- Validação customizada ---
    def validate_field(self, field_name, value, context=None):
        """Aplica regras de validação declarativas do business_rules.validation_rules."""
        for rule in self.rules.get("validation_rules", []):
            if rule.get("field") == field_name:
                rule_type = rule.get("rule")
                msg = rule.get("message", f"Valor inválido para {field_name}")
                if (
                    rule_type == "min"
                    and value is not None
                    and value < rule.get("value", 0)
                ):
                    return False, msg
                if (
                    rule_type == "max"
                    and value is not None
                    and value > rule.get("value", 0)
                ):
                    return False, msg
                if (
                    rule_type == "required"
                    and rule.get("value")
                    and (value is None or value == "")
                ):
                    return False, msg
                if (
                    rule_type == "regex"
                    and value
                    and not __import__("re").match(rule.get("pattern"), str(value))
                ):
                    return False, msg
        return True, None

    # --- Alertas ativos ---
    def get_active_alerts(self, registro, context=None):
        """Retorna lista de alertas baseados nas regras e estado do registro."""
        alerts = []
        now = date.today()
        for alert in self.rules.get("alerts", []):
            trigger = alert.get("trigger")
            condition = alert.get("condition")
            should_alert = False

            if trigger == "planting_window":
                # `is_planting_season` devolve tres valores. O `None` e' o
                # caso que interessava e que o `not ...` engolia: sem regra,
                # `not None` e' `True`, e o sistema disparava um alerta de
                # "fora da janela" para uma cultura **cuja janela nao
                # conhece**. Trocava-se uma omissao por um alarme falso.
                #
                # So_ha_ha_regra e' o sinal honesto: existe janela, e a data
                # esta fora dela.
                estado = self.is_planting_season(now)
                if estado is False:
                    should_alert = True
            elif trigger == "stage_overdue" and context:
                # context deve ter 'stage_start_date' e 'max_days'
                start = context.get("stage_start_date")
                max_days = context.get("max_days", 30)
                if start and (now - start).days > max_days:
                    should_alert = True
            elif trigger == "field_threshold" and context:
                field = condition.get("field")
                threshold = condition.get("threshold")
                operator = condition.get("operator", ">")
                val = context.get(field)
                if val is not None:
                    if operator == ">" and val > threshold:
                        should_alert = True
                    if operator == "<" and val < threshold:
                        should_alert = True
                    if operator == ">=" and val >= threshold:
                        should_alert = True
                    if operator == "<=" and val <= threshold:
                        should_alert = True
                    if operator == "==" and val == threshold:
                        should_alert = True

            if should_alert:
                alerts.append(
                    {
                        "type": trigger,
                        "message": alert.get("message", "Atenção necessária"),
                        "level": alert.get("level", "warning"),
                        "action": alert.get("action"),  # ex: 'create_task', 'notify'
                    }
                )
        return alerts

    # --- Templates de tarefas ---
    def get_tasks_for_stage(self, stage_name):
        """Retorna templates de tarefas para um estágio."""
        return self.task_templates.get(stage_name, [])

    def create_tasks_from_template(self, registro, stage_name, user=None):
        """
        Cria tarefas reais a partir dos templates do estágio.
        Retorna lista de TarefaEstagio criadas.
        """
        from app.models import EstagioCultura, Funcionario, TarefaEstagio

        templates = self.get_tasks_for_stage(stage_name)
        if not templates:
            return []

        estagio = EstagioCultura.objects.filter(
            registro=registro, nome=stage_name
        ).first()
        if not estagio:
            return []

        created = []
        for tpl in templates:
            # Resolve responsável se cargo_alvo
            funcionario = None
            cargo = tpl.get("cargo_alvo")
            if cargo and registro.user:
                funcionario = Funcionario.objects.filter(
                    propriedade__user=registro.user, cargo=cargo, ativo=True
                ).first()

            tarefa = TarefaEstagio.objects.create(
                estagio=estagio,
                descricao=tpl.get("descricao", tpl.get("titulo", "Tarefa")),
                funcionario=funcionario,
                cargo_alvo=cargo or "",
                setor=tpl.get("setor", ""),
                concluida=False,
                ordem=tpl.get("ordem", 0),
            )
            created.append(tarefa)

            # Se automação 'task_create' -> notificação
            self._run_automation(
                "task_create",
                {
                    "registro": registro,
                    "tarefa": tarefa,
                    "stage": stage_name,
                },
                user,
            )

        return created

    # --- Automações ---
    def _run_automation(self, trigger, context, user=None):
        """Executa automações configuradas para um trigger."""
        for _name, config in self.automations.items():
            if config.get("trigger") == trigger:
                # Avalia condição se houver
                condition = config.get("condition")
                if condition and not self._eval_condition(condition, context):
                    continue

                action = config.get("action")
                params = config.get("params", {})
                self._execute_action(action, params, context, user)

    def _eval_condition(self, condition, context):
        """Avalia condição simples (field op value)."""
        field = condition.get("field")
        op = condition.get("operator", "==")
        expected = condition.get("value")
        actual = context.get(field)
        if actual is None:
            return False
        ops = {
            "==": lambda a, b: a == b,
            "!=": lambda a, b: a != b,
            ">": lambda a, b: a > b,
            "<": lambda a, b: a < b,
            ">=": lambda a, b: a >= b,
            "<=": lambda a, b: a <= b,
            "in": lambda a, b: a in b if isinstance(b, (list, tuple)) else False,
        }
        return ops.get(op, lambda a, b: False)(actual, expected)

    def _execute_action(self, action, params, context, user):
        """Executa uma ação de automação."""
        from app.models import EstagioCultura, Notificacao

        if action == "create_task":
            estagio = context.get("stage")
            if estagio:
                self.create_tasks_from_template(context["registro"], estagio, user)

        elif action == "send_notification":
            usuario = user or context.get("registro").user
            Notificacao.objects.create(
                user=usuario,
                titulo=params.get("title", "Automação"),
                mensagem=params.get("message", "Ação automática executada"),
                nivel=params.get("level", "info"),
                link=params.get("link", ""),
            )

        elif action == "update_field":
            # Atualiza campo no registro (fields_json)
            registro = context.get("registro")
            if registro:
                fields = registro.fields_json or {}
                fields.update(params.get("fields", {}))
                registro.fields_json = fields
                registro.save(update_fields=["fields_json", "atualizado_em"])

        elif action == "auto_advance_stage":
            # Avança estágio automaticamente se condições atendidas
            registro = context.get("registro")
            target_stage = params.get("target_stage")
            if registro and target_stage:
                estagio = EstagioCultura.objects.filter(
                    registro=registro, nome=target_stage
                ).first()
                if estagio and not estagio.concluido:
                    estagio.concluido = True
                    estagio.save(update_fields=["concluido", "atualizado_em"])
                    # Dispara trigger stage_complete
                    self._run_automation(
                        "stage_complete", {**context, "stage": target_stage}, user
                    )

        elif action == "webhook":
            # Placeholder para webhook externo
            pass


def get_business_engine(cultura_slug):
    """Factory para CultureBusinessEngine."""
    return CultureBusinessEngine(cultura_slug)
