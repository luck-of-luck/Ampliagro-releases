from datetime import timedelta

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

from app.validators import validate_json_safe


class PerfilUsuario(models.Model):
    TIPO_USUARIO_CHOICES = [
        ("produtor", "Produtor"),
        ("operario", "Operário"),
        ("agronomo", "Agrônomo"),
        ("mecanico", "Mecânico"),
        ("administrativo", "Administrativo"),
        ("servidor", "Servidor"),
    ]
    AREA_SERVIDOR_CHOICES = [
        ("MECANICA", "Mecânica"),
        ("CAMPO", "Campo / Agrícola"),
        ("PECUARIA", "Pecuária"),
        ("ESTOQUE", "Estoque / Almoxarifado"),
        ("AGRONOMIA", "Agronomia / Técnico"),
        ("ADMIN", "Administrativo"),
        ("FINANCEIRO", "Financeiro"),
        ("GERAL", "Geral"),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="perfil")
    tipo_usuario = models.CharField(
        max_length=20, choices=TIPO_USUARIO_CHOICES, default="produtor"
    )
    propriedade_vinculada = models.ForeignKey(
        "Propriedade",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="usuarios_vinculados",
    )
    funcionario = models.OneToOneField(
        "Funcionario",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="usuario_acesso",
    )
    # --- Servidor (profissional contratado) ---
    area_servidor = models.CharField(
        max_length=20,
        choices=AREA_SERVIDOR_CHOICES,
        blank=True,
        default="",
        help_text="Área de atuação do servidor — define dashboard e permissões padrão",
    )
    permissoes = models.JSONField(
        validators=[validate_json_safe],
        default=dict,
        blank=True,
        help_text='Ex: {"paginas":["estoque_mecanico","agenda_revisao"],"pode_criar":true,"pode_editar":true,"pode_ver_financeiro":false}',
    )
    # MEDIDO 2026-10-06: `api/culture_config.py` lia e gravava
    # `PerfilUsuario.config` para as preferencias por cultura, mas o campo nunca
    # existiu — `config` era o `WidgetUsuario.config`. O POST de registo de
    # producao morria com 500 `AttributeError: 'PerfilUsuario' object has no
    # attribute 'config'` sempre que a cultura tinha campos dinamicos.
    #
    # Sao preferencias de interface (campos escondidos, ordem, valores por
    # omissao), por isso `config` e' um saco JSON separado de `permissoes`:
    # misturar os dois poluiria a leitura das permissoes.
    config = models.JSONField(
        validators=[validate_json_safe],
        default=dict,
        blank=True,
        help_text='Ex: {"culture_preferences":{"fumo":{"compact_mode":true}}}',
    )
    vinculado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="servidores_vinculados",
        help_text="Produtor que cadastrou/vinculou o servidor",
    )
    ativo_servidor = models.BooleanField(
        default=True, help_text="Se desativado, servidor não loga"
    )
    idioma = models.CharField(max_length=10, default="pt-br")
    tema = models.CharField(max_length=50, default="light")

    def __str__(self):
        return f"Perfil de {self.user.username} ({self.get_tipo_usuario_display()})"

    @property
    def is_servidor(self):
        return self.tipo_usuario == "servidor"

    @property
    def is_produtor(self):
        return self.tipo_usuario == "produtor"

    def get_dashboard_config(self):
        """Retorna config padrão por área — usado pelo servidor.js para montar dashboard."""
        defaults = {
            "MECANICA": {
                "titulo": "Mecânica",
                "icone": "bi-tools",
                "paginas": [
                    "estoque_mecanico",
                    "agenda_revisao",
                    "lista_tarefas",
                    "maquinario",
                ],
                "pode_criar": True,
                "pode_editar": True,
                "pode_ver_financeiro": False,
                "descricao": "Estoque de peças, agenda de revisão e tarefas de oficina",
            },
            "CAMPO": {
                "titulo": "Campo",
                "icone": "bi-tree",
                "paginas": [
                    "talhoes",
                    "safras",
                    "aplicacoes",
                    "clima",
                    "tarefas_campo",
                ],
                "pode_criar": True,
                "pode_editar": True,
                "pode_ver_financeiro": False,
            },
            "PECUARIA": {
                "titulo": "Pecuária",
                "icone": "bi-heart-pulse",
                "paginas": ["rebanho", "manejo", "producao", "tarefas_pecuaria"],
                "pode_criar": True,
                "pode_editar": True,
            },
            "ESTOQUE": {
                "titulo": "Estoque",
                "icone": "bi-box-seam",
                "paginas": ["estoque_geral", "insumos", "movimentacoes"],
                "pode_criar": True,
                "pode_editar": True,
            },
            "AGRONOMIA": {
                "titulo": "Agronomia",
                "icone": "bi-flower1",
                "paginas": [
                    "culturas",
                    "analise_solo",
                    "recomendacoes",
                    "tarefas_tecnicas",
                ],
                "pode_criar": True,
                "pode_editar": False,
                "pode_ver_financeiro": False,
            },
            "ADMIN": {
                "titulo": "Administrativo",
                "icone": "bi-briefcase",
                "paginas": ["funcionarios", "financeiro_resumo", "relatorios"],
                "pode_criar": False,
                "pode_editar": False,
            },
            "FINANCEIRO": {
                "titulo": "Financeiro",
                "icone": "bi-cash-coin",
                "paginas": ["lancamentos", "relatorio_financeiro"],
                "pode_criar": True,
                "pode_editar": False,
                "pode_ver_financeiro": True,
            },
            "GERAL": {
                "titulo": "Geral",
                "icone": "bi-grid",
                "paginas": ["tarefas", "agenda"],
                "pode_criar": True,
                "pode_editar": True,
            },
        }
        base = defaults.get(self.area_servidor or "GERAL", defaults["GERAL"]).copy()
        # merge com permissoes custom do produtor (sobrescreve)
        if self.permissoes:
            base.update(self.permissoes)
        return base

    def has_permission(self, pagina, acao="ver"):
        cfg = self.get_dashboard_config()
        if acao == "criar" and not cfg.get("pode_criar"):
            return False
        if acao == "editar" and not cfg.get("pode_editar"):
            return False
        if pagina and pagina not in cfg.get("paginas", []):
            # permite se lista contém "tudo" ou se produtor liberou explicitamente
            if pagina not in (self.permissoes.get("paginas_extra") or []):
                return False
        return True

    class Meta:
        verbose_name = "Perfil de Usuário"
        verbose_name_plural = "Perfis de Usuários"


class DashboardUserState(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    state = models.JSONField(default=dict)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Dashboard de {self.user.username}"

    class Meta:
        verbose_name = "Estado do Dashboard"
        verbose_name_plural = "Estados dos Dashboards"


class WidgetUsuario(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    tipo_widget = models.CharField(max_length=50)
    posicao_x = models.IntegerField()
    posicao_y = models.IntegerField()
    tamanho_w = models.IntegerField()
    tamanho_h = models.IntegerField()
    config = models.JSONField(default=dict)
    # MEDIDO 2026-10-07: estas duas colunas existem na base (`app_widgetusuario.
    # consentido`, `app_widgetusuario.origem`) mas o modelo nao as conhecia. Ao
    # gravar um widget novo, o INSERT nao incluia `consentido` / `origem`,
    # que sao NOT NULL sem default — e a criacao rebentava em 500
    # `IntegrityError: NOT NULL constraint failed: app_widgetusuario.consentido`.
    #
    # Todos os 135 widgets existentes tem `consentido=1` e `origem='sistema'`,
    # por isso e' esse o default que herdam. O efeito e' o mesmo comportamento
    # que a base ja' impunha, agora visivel no modelo.
    consentido = models.BooleanField(default=True)
    origem = models.CharField(max_length=10, default="sistema")

    def __str__(self):
        return f"{self.user.username} - {self.tipo_widget}"

    class Meta:
        verbose_name = "Widget do Usuário"
        verbose_name_plural = "Widgets dos Usuários"


class Notificacao(models.Model):
    NIVEL_CHOICES = [
        ("info", "Informativo"),
        ("warning", "Aviso"),
        ("critical", "Crítico"),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    titulo = models.CharField(max_length=200)
    mensagem = models.TextField(blank=True)
    nivel = models.CharField(max_length=10, choices=NIVEL_CHOICES, default="info")
    lida = models.BooleanField(default=False)
    link = models.CharField(max_length=500, blank=True, null=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-criado_em"]
        verbose_name = "Notificação"
        verbose_name_plural = "Notificações"

    def __str__(self):
        return f"[{self.nivel}] {self.titulo}"


# Regras do gerenciador de alertas: chave -> metadados p/ UI e defaults.
# dias = antecedência (avisar X dias antes); limite = ponto de alerta
# (R$, % ou unidade da regra). None = a regra não usa aquele campo.
REGRAS_ALERTA = {
    "manutencao": {
        "nome": "Manutenção de máquinas",
        "descricao": "Revisão vencida ou próxima",
        "dias": 15,
        "limite": None,
        "un_dias": "dias antes",
        "un_limite": "",
    },
    "estoque_validade": {
        "nome": "Validade do estoque",
        "descricao": "Item vencido ou vencendo",
        "dias": 30,
        "limite": None,
        "un_dias": "dias antes",
        "un_limite": "",
    },
    "estoque_zero": {
        "nome": "Estoque zerado",
        "descricao": "Item com quantidade zero",
        "dias": None,
        "limite": None,
        "un_dias": "",
        "un_limite": "",
    },
    "colheita": {
        "nome": "Colheita pendente",
        "descricao": "Passou da data sem produção registrada",
        "dias": None,
        "limite": None,
        "un_dias": "",
        "un_limite": "",
    },
    "financeiro_mes": {
        "nome": "Despesas acima da receita",
        "descricao": "Despesas do mês superam receitas",
        "dias": None,
        "limite": 20,
        "un_dias": "",
        "un_limite": "% acima",
    },
    "colmeias": {
        "nome": "Colmeias inativas",
        "descricao": "Colmeias marcadas como inativas",
        "dias": None,
        "limite": None,
        "un_dias": "",
        "un_limite": "",
    },
    "insumos_min": {
        "nome": "Insumos abaixo do mínimo",
        "descricao": "Abaixo do estoque mínimo do item",
        "dias": None,
        "limite": None,
        "un_dias": "",
        "un_limite": "",
    },
    "racao": {
        "nome": "Ração vencendo",
        "descricao": "Ração vencida ou vencendo",
        "dias": 30,
        "limite": None,
        "un_dias": "dias antes",
        "un_limite": "",
    },
    "contas_vencidas": {
        "nome": "Contas vencidas",
        "descricao": "Despesas não pagas após o vencimento",
        "dias": None,
        "limite": None,
        "un_dias": "",
        "un_limite": "",
    },
    "contas_sem_vencimento": {
        "nome": "Despesas sem vencimento",
        "descricao": "Despesas em aberto sem data de vencimento registrada",
        "dias": None,
        "limite": None,
        "un_dias": "",
        "un_limite": "",
    },
    "parcelas_vencidas": {
        "nome": "Parcelas vencidas",
        "descricao": "Parcelas não pagas após o vencimento",
        "dias": None,
        "limite": None,
        "un_dias": "",
        "un_limite": "",
    },
    "mip": {
        "nome": "MIP crítico",
        "descricao": "Praga acima do nível de controle",
        "dias": None,
        "limite": None,
        "un_dias": "",
        "un_limite": "",
    },
    "vacinas": {
        "nome": "Vacinas atrasadas",
        "descricao": "Dose com data passada",
        "dias": None,
        "limite": None,
        "un_dias": "",
        "un_limite": "",
    },
    "bateria": {
        "nome": "Bateria de sensores",
        "descricao": "Device abaixo do nível",
        "dias": None,
        "limite": 20,
        "un_dias": "",
        "un_limite": "% bateria",
    },
    "tarefas": {
        "nome": "Tarefas atrasadas",
        "descricao": "Atividade passada sem conclusão",
        "dias": None,
        "limite": None,
        "un_dias": "",
        "un_limite": "",
    },
    "saldo_contas": {
        "nome": "Saldo bancário baixo",
        "descricao": "Conta abaixo do ponto",
        "dias": None,
        "limite": 1000,
        "un_dias": "",
        "un_limite": "R$",
    },
    "devices_offline": {
        "nome": "Sensores offline",
        "descricao": "Sem push há dias",
        "dias": 2,
        "limite": None,
        "un_dias": "dias sem push",
        "un_limite": "",
    },
    "contas_a_vencer": {
        "nome": "Contas a vencer",
        "descricao": "Despesas vencendo em breve",
        "dias": 7,
        "limite": None,
        "un_dias": "dias antes",
        "un_limite": "",
    },
    "parcelas_a_vencer": {
        "nome": "Parcelas a vencer",
        "descricao": "Parcelas vencendo em breve",
        "dias": 7,
        "limite": None,
        "un_dias": "dias antes",
        "un_limite": "",
    },
    "ordens_paradas": {
        "nome": "Ordens paradas",
        "descricao": "Rascunho antigo sem andamento",
        "dias": 30,
        "limite": None,
        "un_dias": "dias parado",
        "un_limite": "",
    },
    "talhoes_sem_safra": {
        "nome": "Talhões sem safra",
        "descricao": "Sem safra no ano corrente",
        "dias": None,
        "limite": None,
        "un_dias": "",
        "un_limite": "",
    },
}


class AlertaConfig(models.Model):
    """Ponto de alerta por usuário/regra: liga/desliga + dias + limite."""

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="alertas_config"
    )
    regra = models.CharField(
        max_length=30, choices=[(k, v["nome"]) for k, v in REGRAS_ALERTA.items()]
    )
    ativo = models.BooleanField(default=True)
    dias = models.IntegerField(
        null=True, blank=True, help_text="Antecedência em dias (quando a regra usa)"
    )
    limite = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Ponto de alerta (quando a regra usa)",
    )

    class Meta:
        verbose_name = "Configuração de Alerta"
        verbose_name_plural = "Configurações de Alerta"
        unique_together = [("user", "regra")]

    def __str__(self):
        return f"{self.user.username}/{self.regra} ({'on' if self.ativo else 'off'})"

    def get_dias(self):
        if self.dias is not None:
            return self.dias
        return REGRAS_ALERTA.get(self.regra, {}).get("dias")

    def get_limite(self):
        if self.limite is not None:
            return float(self.limite)
        return REGRAS_ALERTA.get(self.regra, {}).get("limite")
