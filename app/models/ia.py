from django.contrib.auth.models import User
from django.db import models

from app.models.core import Propriedade
from app.seguranca import EncryptedCharField, hash_cego


class ChaveIA(models.Model):
    """Chave de API para agentes da nuvem (Gemini, OpenAI, etc.).

    Segue o padrão do Gateway IoT: cifra em repouso com `EncryptedCharField`
    (Fernet via `app/seguranca.py`) e mantém um hash cego (SHA-256) para
    autenticar/consultar sem descriptografar. Um registro por propriedade.
    """

    STATUS_CHOICES = [
        ("online", "Online"),
        ("offline", "Offline"),
        ("manutencao", "Manutenção"),
    ]

    PROVEDORES_CHOICES = [
        ("gemini", "Google Gemini"),
        ("openai-compatible", "OpenAI Compatible"),
    ]

    propriedade = models.OneToOneField(
        Propriedade,
        on_delete=models.CASCADE,
        related_name="chave_ia",
    )
    chave = EncryptedCharField(
        max_length=500,
        help_text="Chave da API do provedor (ex: GEMINI_API_KEY).",
    )
    chave_hash = models.CharField(
        max_length=64,
        blank=True,
        db_index=True,
        help_text="SHA-256 da chave (índice cego p/ autenticação).",
    )
    provedor = models.CharField(
        max_length=30,
        choices=PROVEDORES_CHOICES,
        default="gemini",
        help_text="Provedor LLM usado pelo agente da nuvem.",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="online",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Chave IA"
        verbose_name_plural = "Chaves IA"
        ordering = ["-atualizado_em"]

    def __str__(self):
        return f"{self.get_provedor_display()} - {self.propriedade.nome}"

    def save(self, *args, **kwargs):
        """Popula `chave_hash` antes de persistir — índice cego p/ busca."""
        self.chave_hash = hash_cego(self.chave or "")
        super().save(*args, **kwargs)

    @classmethod
    def buscar_por_hash(cls, hash_chave: str):
        """Busca a chave pelo hash cego (sem descriptografar)."""
        return cls.objects.filter(chave_hash=hash_chave).first()


class IAContextoConversa(models.Model):
    """
    Máquina de estados para a IA.
    Mantém o contexto de fluxos de cadastro multi-turno e confirmações.
    """

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="ia_contexto"
    )
    estado_atual = models.CharField(max_length=50, default="NENHUM")
    intent_pendente = models.CharField(max_length=50, blank=True)
    dados_coletados = models.JSONField(default=dict)
    atualizado_em = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - {self.estado_atual} ({self.intent_pendente})"


class IAArtefato(models.Model):
    """Artifactory local da IA: toda informação que a IA produz/lê fica aqui,
    no BD do sistema — nunca solta na internet, nunca em serviço externo."""

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="ia_artefatos"
    )
    chave = models.CharField(
        max_length=100, help_text="Ex: clima/12/2026-09-17, tarefa/ultima"
    )
    tipo = models.CharField(
        max_length=30,
        default="resultado",
        help_text="resultado, clima, comando, tarefa, sensor, nota",
    )
    dados = models.JSONField(default=dict)
    origem = models.CharField(
        max_length=50, blank=True, help_text="intent que gerou (ex: vai_chover)"
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.chave} ({self.tipo})"

    class Meta:
        verbose_name = "Artefato IA"
        verbose_name_plural = "Artefatos IA"
        ordering = ["-atualizado_em"]
        unique_together = [("user", "chave")]
        indexes = [
            models.Index(fields=["user", "tipo"]),
        ]


class IAExecucao(models.Model):
    """Auditoria do sandbox: cada intent executada registra flags usadas,
    parâmetros, fontes consultadas e resultado. Rastreabilidade total."""

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="ia_execucoes"
    )
    intent = models.CharField(max_length=50)
    entrada = models.TextField(
        blank=True, help_text="texto bruto que o usuário escreveu"
    )
    deteccao = models.JSONField(
        default=dict, help_text="{metodo, scores, escolhido} — como a IA entendeu"
    )
    passos = models.JSONField(
        default=list, help_text="timeline: [{etapa, detalhe, ms}] — tudo que a IA fez"
    )
    params = models.JSONField(default=dict)
    flags = models.JSONField(default=list, help_text="flags de capacidade usadas")
    fontes = models.JSONField(
        default=list, help_text="fontes consultadas (internas + externas permitidas)"
    )
    via = models.CharField(
        max_length=20,
        default="sessao",
        help_text="sessao (painel) ou chave (serviço local)",
    )
    ok = models.BooleanField(default=True)
    resposta = models.TextField(blank=True)
    erro = models.TextField(blank=True)
    duracao_ms = models.IntegerField(
        default=0, help_text="latência da execução (otimização IA)"
    )
    satisfeito = models.BooleanField(
        null=True,
        blank=True,
        help_text="feedback ML: True/False quando o usuário avalia",
    )
    artefato = models.ForeignKey(
        "IAArtefato",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="execucoes",
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.intent} ({'ok' if self.ok else 'erro'})"

    class Meta:
        verbose_name = "Execução IA"
        verbose_name_plural = "Execuções IA"
        ordering = ["-criado_em"]
        indexes = [
            models.Index(fields=["user", "intent"]),
        ]


class IAEvento(models.Model):
    """Console de registros: TUDO que a IA faz vira evento —
    acessar, ler, editar, raciocinar, entender, procurar, ler instruções."""

    TIPOS = [
        ("acesso", "Acesso"),
        ("entendimento", "Entendeu o texto"),
        ("raciocinio", "Raciocínio"),
        ("busca", "Procura"),
        ("leitura", "Leitura"),
        ("instrucao", "Leu instruções"),
        ("edicao", "Edição"),
        ("resposta", "Resposta"),
        ("erro", "Erro"),
        # BUILD 3: recusa de compliance etico/ambiental. Tipo proprio (e nao um
        # "erro" com texto especifico) porque a pergunta que o produtor faz ao
        # auditor e' "o que foi BLOQUEADO e por lei", e isso se responde por
        # consulta: IAEvento.objects.filter(tipo="compliance").
        ("compliance", "Compliance"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="ia_eventos")
    tipo = models.CharField(max_length=15, choices=TIPOS)
    resumo = models.CharField(max_length=200)
    dados = models.JSONField(default=dict)
    execucao = models.ForeignKey(
        "IAExecucao",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="eventos",
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.get_tipo_display()}: {self.resumo[:60]}"

    class Meta:
        verbose_name = "Evento IA"
        verbose_name_plural = "Eventos IA (console)"
        ordering = ["-criado_em"]
        indexes = [
            models.Index(fields=["user", "tipo"]),
        ]
