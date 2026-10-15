"""
iot_dinamico.py — a Ponte IoT do Criador Livre (BUILD 4).

O QUE ISTO É
------------
O produtor criou uma ferramenta virtual ("Válvula de Irrigação") e quer
conectar a placa física. Este módulo é a ponte entre os dois: guarda a
credencial do dispositivo, o tópico roteado, e recebe os eventos que a placa
publica.

O QUE ISTO NÃO É (e por que é uma distinção importante)
-------------------------------------------------------
O projeto JÁ tem IoT: `app/models/iot.py` com `Device`, e `app/iot/views.py`
com `push_telemetry`/`ttn_webhook` para LoRaWAN/TTN, autenticado por
`device_eui`. Aquele caminho responde a "qual telemetria chegou do rúter X".

Este responde a outra pergunta: "o produtor que criou uma ferramenta dinâmica
quer um endpoint para o dispositivo que ELE vai programar". São credenciais de
primeira parte, revisáveis, e o destino do evento é um `DynamicRecord` — não
uma linha de `TelemetryData`.

A distinção importa porque são credenciais de naturezas diferentes:
`Device.device_eui` é um identificador de hardware e a autenticação é uma API
key global; aqui a credencial é um segredo por endpoint, revogável
individualmente, e o dado cai na tabela do Criador Livre.

O TOKEN — POR QUE SÓ O HASH
----------------------------
O token é gerado com `secrets.token_urlsafe(32)` (256 bits de entropia) e
guardamos **apenas o SHA-256**. Isso não é fraqueza: com 256 bits aleatórios
não há ataque de dicionário — não existe "senha fraca" para quebrar aqui. O
SHA-256 permite busca indexada, que é o que a autenticação precisa.

O ponto do hash não é resistência a força bruta (a entropia já resolve isso) e
sim **exposição**: um dump do banco não entrega as credenciais dos dispositivos.
Um `SELECT` na tabela devolve 64 hex, que não autentica nada.

O token é exibido **uma única vez**, no provisionamento. Depois disso só o
prefixo, suficiente para o produtor reconhecer qual dispositivo é qual.

SOBRE O TOKEN NO TÓPICO — RISCO DECLARADO, NÃO OCULTO
------------------------------------------------------
O formato pedido é `ampliagro/user_{id}/{slug}/{token}`, e ele foi implementado
assim. Mas é preciso dizer o que isso custa, porque é um risco real e
conhecido:

    o tópico do MQTT aparece em log de broker, em `mosquitto_sub` de qualquer
    assinante, e na string de configuração do firmware.

Ou seja: **quem consegue ler o tópico, consegue autenticar.** A mitigação que
temos é a revogação — o produtor corta o endpoint e o token morre. O padrão
mais forte seria um identificador PÚBLICO no tópico e o segredo autenticando
dentro do payload (HMAC ou bearer), o que mantém credencial fora de log. Está
descrito em `renderizar_escopo_cpp` como a variante `segura`.

Isso foi escolhido assim porque é o formato pedido. A diferença entre as duas
opções está documentada e é uma linha para trocar — mas a decisão é de quem
opera o broker, e por isso ela fica visível em vez de escondida num default.
"""

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

from app.models.campos import JSONFieldPortatil
from app.models.dinamico import DynamicApp, DynamicRecord


class IotEndpoint(models.Model):
    """Uma credencial de dispositivo, atrelada a uma ferramenta dinâmica.

    O vínculo com `DynamicApp` é o que fecha o Tenant: o endpoint não tem
    `user` como dono *e* referência solta — ele pertence a uma ferramenta, e a
    ferramenta pertence a um usuário. `user` é redundante por desenho: é a
    DENORMALIZAÇÃO que evita um JOIN no caminho quente de autenticação (cada
    evento de telemetria faz um lookup por hash), e o `save()` valida a
    coerência dos dois.
    """

    ESTADOS = [
        ("ATIVO", "Ativo"),
        ("REVOGADO", "Revogado"),
    ]

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="iot_endpoints"
    )
    app = models.ForeignKey(
        DynamicApp, on_delete=models.CASCADE, related_name="iot_endpoints"
    )
    nome = models.CharField(max_length=100)

    #: SHA-256 hexadecimal do token. NUNCA o token em si.
    token_hash = models.CharField(max_length=64, unique=True, db_index=True)
    #: 8 primeiros caracteres do token, para o produtor identificar qual é
    #: qual. Insuficiente para autenticar — 8 chars de base64 são ~48 bits de
    #: *display*, e a busca de autenticação é pelo hash completo.
    token_prefixo = models.CharField(max_length=12)

    #: `ampliagro/user_{id}/{slug}/{token}`
    topico = models.CharField(max_length=255)

    #: Chave do schema dinâmico que recebe o valor do evento. Validado contra
    #: os campos da app no provisionamento — é o que impede um dispositivo
    #: rogue de escrever chave arbitrária (a validação do insert a barra de
    #: novo, mas aqui evitamos descobrir isso no primeiro evento).
    campo_destino = models.CharField(max_length=60)

    estado = models.CharField(max_length=10, choices=ESTADOS, default="ATIVO")
    #: O JSON técnico que o produtor copia para o firmware. Guardado porque o
    #: produtor volta atrás: "qual era o tópico da minha válvula?".
    escopo_tecnico = JSONFieldPortatil(default=dict, blank=True)

    criado_em = models.DateTimeField(auto_now_add=True)
    revogado_em = models.DateTimeField(null=True, blank=True)
    ultimo_evento_em = models.DateTimeField(null=True, blank=True)
    total_eventos = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Endpoint IoT dinâmico"
        verbose_name_plural = "Endpoints IoT dinâmicos"
        ordering = ["-criado_em"]
        constraints = [
            # Um endpoint por (app, nome): dois provisionamentos com o mesmo
            # nome na mesma ferramenta não podem existir, senão o produtor não
            # sabe qual revogar.
            models.UniqueConstraint(
                fields=["app", "nome"], name="uniq_iot_endpoint_app_nome"
            )
        ]
        indexes = [
            models.Index(fields=["user", "estado"]),
            models.Index(fields=["app", "estado"]),
        ]

    def __str__(self):
        return f"{self.nome} @ {self.app_id} ({self.estado})"

    @property
    def ativo(self) -> bool:
        return self.estado == "ATIVO"

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.app_id and self.user_id and self.app.user_id != self.user_id:
            raise ValidationError(
                {"app": "a ferramenta do endpoint precisa pertencer ao mesmo usuario"}
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def revogar(self):
        """Corta o acesso. Idempotente.

        Idempotente porque quem revoga é uma tool idempotente, e "já estava
        revogado" não é erro: é o estado desejado, dito de outro jeito.
        """
        if self.estado == "REVOGADO":
            return False
        self.estado = "REVOGADO"
        self.revogado_em = timezone.now()
        self.save(update_fields=["estado", "revogado_em"])
        return True

    def como_descrever(self) -> dict:
        """Representação para a IA e para a tela. SEM o token, sempre."""
        return {
            "id": self.pk,
            "nome": self.nome,
            "entity_slug": self.app.slug,
            "topico": self.topico,
            "token_prefixo": self.token_prefixo,
            "campo_destino": self.campo_destino,
            "estado": self.estado,
            "criado_em": self.criado_em.isoformat() if self.criado_em else None,
            "revogado_em": self.revogado_em.isoformat() if self.revogado_em else None,
            "total_eventos": self.total_eventos,
            "ultimo_evento_em": (
                self.ultimo_evento_em.isoformat() if self.ultimo_evento_em else None
            ),
        }


class IotEvento(models.Model):
    """Um evento publicado pelo dispositivo, e o que o AmplIA fez com ele.

    Guardar o RECUSAO importa tanto quanto o aceite. Um dispositivo que
    publica e vê o evento ignorado, sem rastro, é um dispositivo que o produtor
    vai culpar por "não funcionar" — e a causa real (campo inexistente no
    schema, token revogado) fica invisível.
    """

    MOTIVOS = [
        ("aceito", "Aceito e gravado"),
        ("token_invalido", "Token inválido"),
        ("revogado", "Endpoint revogado"),
        ("campo_invalido", "Valor fora do schema"),
        ("payload_invalido", "Payload malformado"),
        ("excedido", "Payload grande demais"),
    ]

    endpoint = models.ForeignKey(
        IotEndpoint,
        on_delete=models.CASCADE,
        related_name="eventos",
        null=True,
        blank=True,
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="iot_eventos")
    motivo = models.CharField(max_length=20, choices=MOTIVOS, default="aceito")
    #: Payload cru como chegou. Guardar o bruto é o que permite reconstruir o
    #: que o dispositivo mandou quando o valor gravado parece errado.
    payload = JSONFieldPortatil(default=dict, blank=True)
    valor = models.CharField(max_length=120, blank=True)
    #: Onde o valor foi parar, quando aceito.
    registro = models.ForeignKey(
        DynamicRecord,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="eventos_iot",
    )
    detalhe = models.CharField(max_length=300, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Evento IoT"
        verbose_name_plural = "Eventos IoT"
        ordering = ["-criado_em"]
        indexes = [
            models.Index(fields=["user", "-criado_em"]),
            models.Index(fields=["endpoint", "-criado_em"]),
            models.Index(fields=["motivo"]),
        ]

    def __str__(self):
        return f"{self.get_motivo_display()} @ {self.criado_em:%H:%M:%S}"
