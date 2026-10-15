from datetime import timedelta

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

from app.seguranca import EncryptedCharField
from app.validators import validate_json_safe

GATEWAY_STATUS = [
    ("online", "Online"),
    ("offline", "Offline"),
    ("manutencao", "Manutenção"),
]

PUSH_PROTOCOLO = [
    ("MQTT", "MQTT"),
    ("HTTP", "HTTP/HTTPS"),
    ("LORAWAN", "LoRaWAN (uplink)"),
    ("COAP", "CoAP"),
]

TELEMETRY_METRIC_CHOICES = [
    # Meteo
    ("temperatura", "Temperatura (°C)"),
    ("umidade_ar", "Umidade Ar (%)"),
    ("pressao", "Pressão (hPa)"),
    ("chuva", "Chuva (mm)"),
    ("chuva_acum", "Chuva Acumulada (mm)"),
    ("vento_vel", "Vento Vel (m/s)"),
    ("vento_dir", "Vento Dir (°)"),
    ("vento_rajada", "Rajada (m/s)"),
    ("radiacao", "Radiação (W/m²)"),
    ("uv", "Índice UV"),
    ("ponto_orvalho", "Ponto Orvalho (°C)"),
    # Solo
    ("umidade_solo", "Umidade Solo (%)"),
    ("temp_solo", "Temp Solo (°C)"),
    ("condutividade", "Condutividade (dS/m)"),
    ("ph_solo", "pH Solo"),
    ("npk_n", "Nitrogênio (mg/kg)"),
    ("npk_p", "Fósforo (mg/kg)"),
    ("npk_k", "Potássio (mg/kg)"),
    # Água
    ("nivel", "Nível (m)"),
    ("vazao", "Vazão (L/s)"),
    ("ph_agua", "pH Água"),
    ("turbidez", "Turbidez (NTU)"),
    # Maquinário
    ("gps_lat", "GPS Lat"),
    ("gps_lon", "GPS Lon"),
    ("gps_alt", "GPS Alt (m)"),
    ("velocidade", "Velocidade (km/h)"),
    ("rpm", "RPM"),
    ("combustivel", "Combustível (%)"),
    ("horimetro", "Horímetro (h)"),
    ("temp_motor", "Temp Motor (°C)"),
    # Animal
    ("peso", "Peso (kg)"),
    ("temp_corporal", "Temp Corporal (°C)"),
    ("passos", "Passos"),
    ("ruminação", "Ruminação (min)"),
    # Energia
    ("potencia", "Potência (W)"),
    ("energia_dia", "Energia Dia (kWh)"),
    ("tensao", "Tensão (V)"),
    ("corrente", "Corrente (A)"),
    # Genérico
    ("bateria", "Bateria (%)"),
    ("rssi", "RSSI (dBm)"),
    ("outro", "Outro"),
    # Exóticos — 12 pendências 50 vídeos (Aveconfort, Morcego, Tilápia pele, etc.)
    ("aveconfort", "Aveconfort (índice bem-estar 0-100)"),
    ("fotogrametria_angulo", "Fotogrametria ângulo ósseo (°)"),
    ("movimento_ave", "Movimento ave (Big Brother Agrisolus)"),
    ("consumo_agua_ave", "Consumo água ave (mL/dia)"),
    ("mormaco_tilapia", "Tilápia pele curativo (unidades)"),
    ("biomassa_eucalipto", "Biomassa eucalipto (m³/ha)"),
    ("plantio_orquidea", "Orquídea cultivo (umidade %)"),
    ("sono_cavalo", "Sono cavalo em pé (min/dia)"),
    ("atividade_morcego", "Atividade morcego (detecções/noite)"),
    ("qualidade_mel_camoatim", "Mel camoatim (°Brix)"),
    ("flat_iron_rendimento", "Flat iron rendimento (%)"),
]

DEVICE_TIPO = [
    ("METEO", "Estação Meteorológica"),
    ("SOLO", "Sensor de Solo (umidade/temp/EC/pH)"),
    ("NIVEL", "Nível / Vazão (reservatório/rio)"),
    ("MAQUINARIO", "Rastreador Maquinário (GPS/CAN)"),
    ("ANIMAL", "Colar Animal (GPS/acelerômetro)"),
    ("DRONE", "Drone (telemetria voo)"),
    ("ENERGIA", "Medidor Energia (solar/rede)"),
    ("SILAGEM", "Sensor Silo/Silagem (temp/umidade)"),
    ("GENERIC", "Genérico"),
]

GATEWAY_TIPO = [
    ("LORAWAN", "LoRaWAN (TTN/ChirpStack)"),
    ("CELLULAR", "Celular 4G/NB-IoT"),
    ("WIFI", "Wi-Fi / Ethernet"),
    ("SATELITE", "Satélite (Swarm/Iridium)"),
    ("HELIUM", "Helium IoT"),
]


class Gateway(models.Model):
    propriedade = models.ForeignKey(
        "Propriedade", on_delete=models.CASCADE, related_name="gateways"
    )
    nome = models.CharField(max_length=100)
    tipo = models.CharField(max_length=20, choices=GATEWAY_TIPO, default="LORAWAN")
    gateway_eui = models.CharField(
        max_length=32, unique=True, help_text="EUI/ID único do gateway (hex 16 chars)"
    )
    api_key = EncryptedCharField(
        max_length=255,
        unique=True,
        blank=True,
        help_text="Chave para push autenticado (criptografada; busca por api_key_hash)",
    )
    api_key_hash = models.CharField(
        max_length=64,
        blank=True,
        db_index=True,
        help_text="SHA-256 da chave (índice cego p/ autenticação)",
    )
    latitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )
    longitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )
    status = models.CharField(max_length=15, choices=GATEWAY_STATUS, default="offline")
    firmware_version = models.CharField(max_length=20, blank=True)
    intervalo_push_seg = models.IntegerField(
        default=900, help_text="Intervalo padrão de push em segundos"
    )
    ultimo_contato = models.DateTimeField(null=True, blank=True)
    config = models.JSONField(
        default=dict, blank=True, help_text="Config JSON: ttn_app_id, mqtt_topic, etc."
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Gateway IoT"
        verbose_name_plural = "Gateways IoT"
        ordering = ["propriedade", "nome"]

    def __str__(self):
        return f"{self.nome} [{self.get_tipo_display()}] - {self.propriedade.nome}"

    def save(self, *args, **kwargs):
        if not self.api_key:
            import secrets

            self.api_key = secrets.token_urlsafe(32)
        from app.seguranca import hash_cego

        self.api_key_hash = hash_cego(self.api_key or "")
        super().save(*args, **kwargs)


class Device(models.Model):
    gateway = models.ForeignKey(
        "Gateway",
        on_delete=models.CASCADE,
        related_name="devices",
        null=True,
        blank=True,
    )
    propriedade = models.ForeignKey(
        "Propriedade", on_delete=models.CASCADE, related_name="devices"
    )
    talhao = models.ForeignKey(
        "Talhao",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="devices",
    )
    estacao = models.ForeignKey(
        "EstacaoMeteo",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="devices",
        help_text="Vincula device a estação legada se for METEO",
    )
    maquinario = models.ForeignKey(
        "Maquinario",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="devices",
    )
    animal = models.ForeignKey(
        "Animal",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="devices",
    )
    device_eui = models.CharField(
        max_length=32, unique=True, help_text="DevEUI / serial (hex)"
    )
    nome = models.CharField(max_length=100)
    tipo = models.CharField(max_length=20, choices=DEVICE_TIPO, default="GENERIC")
    protocolo = models.CharField(max_length=10, choices=PUSH_PROTOCOLO, default="MQTT")
    mqtt_topic = models.CharField(
        max_length=200,
        blank=True,
        help_text="Tópico MQTT custom; vazio = ampliagro/{prop}/{gw}/{dev}/telemetry",
    )
    intervalo_seg = models.IntegerField(default=900)
    bateria_pct = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    rssi = models.IntegerField(null=True, blank=True, help_text="RSSI último uplink")
    snr = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    ativo = models.BooleanField(default=True)
    ultimo_push = models.DateTimeField(null=True, blank=True)
    # Perfil: métricas esperadas, unidades, calibração, limites
    profile = models.JSONField(
        validators=[validate_json_safe],
        default=dict,
        blank=True,
        help_text="Profile JSON: metrics[], units, calibration, thresholds",
    )
    raw_config = models.JSONField(
        default=dict, blank=True, validators=[validate_json_safe]
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Device IoT"
        verbose_name_plural = "Devices IoT"
        ordering = ["propriedade", "nome"]
        indexes = [
            models.Index(fields=["device_eui"]),
            models.Index(fields=["tipo", "ativo"]),
        ]

    def __str__(self):
        return f"{self.nome} ({self.device_eui[:8]}...) [{self.get_tipo_display()}]"

    @property
    def topic(self):
        if self.mqtt_topic:
            return self.mqtt_topic
        gw = self.gateway.gateway_eui if self.gateway else "nogw"
        return f"ampliagro/{self.propriedade_id}/{gw}/{self.device_eui}/telemetry"


class TelemetryData(models.Model):
    """
    Tabela principal de telemetria — hypertable no TimescaleDB em produção.
    Cada linha = 1 métrica em 1 timestamp (formato narrow, otimizado para timeseries).
    LeituraSensor legado é mantido para compatibilidade; novos devices usam este modelo.
    """

    device = models.ForeignKey(
        "Device",
        on_delete=models.CASCADE,
        related_name="telemetrias",
        null=True,
        blank=True,
    )
    estacao = models.ForeignKey(
        "EstacaoMeteo",
        on_delete=models.CASCADE,
        related_name="telemetrias",
        null=True,
        blank=True,
    )
    propriedade = models.ForeignKey(
        "Propriedade", on_delete=models.CASCADE, related_name="telemetrias"
    )
    talhao = models.ForeignKey(
        "Talhao", on_delete=models.SET_NULL, null=True, blank=True
    )
    metric = models.CharField(max_length=30, choices=TELEMETRY_METRIC_CHOICES)
    value = models.DecimalField(max_digits=12, decimal_places=4)
    unit = models.CharField(max_length=20, blank=True)
    timestamp = models.DateTimeField(db_index=True)
    qualidade = models.CharField(
        max_length=20, default="good", help_text="good/suspect/bad/calibrated"
    )
    raw_payload = models.JSONField(
        validators=[validate_json_safe],
        default=dict,
        blank=True,
        help_text="Payload original para auditoria",
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Telemetria"
        verbose_name_plural = "Telemetrias"
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["propriedade", "metric", "timestamp"]),
            models.Index(fields=["device", "metric", "timestamp"]),
            models.Index(fields=["timestamp"]),
        ]

    def __str__(self):
        return (
            f"{self.metric}={self.value}{self.unit} @ {self.timestamp:%Y-%m-%d %H:%M}"
        )


class RegraAlertaTelemetria(models.Model):
    TIPO_CHOICES = [
        ("threshold_max", "Limite Máximo"),
        ("threshold_min", "Limite Mínimo"),
        ("delta", "Variação Rápida (delta)"),
        ("offline", "Device Offline"),
        ("anomalia", "Anomalia (z-score)"),
    ]
    propriedade = models.ForeignKey(
        "Propriedade", on_delete=models.CASCADE, related_name="regras_alerta"
    )
    nome = models.CharField(max_length=100)
    metric = models.CharField(max_length=30, choices=TELEMETRY_METRIC_CHOICES)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    valor_ref = models.DecimalField(
        max_digits=12, decimal_places=4, null=True, blank=True
    )
    janela_min = models.IntegerField(
        default=15, help_text="Janela em minutos para avaliar"
    )
    severidade = models.CharField(
        max_length=10,
        choices=[("info", "Info"), ("warning", "Warning"), ("critical", "Crítico")],
        default="warning",
    )
    ativa = models.BooleanField(default=True)
    config = models.JSONField(
        validators=[validate_json_safe],
        default=dict,
        blank=True,
        help_text='Ex: {"delta_pct": 20, "z_threshold": 3}',
    )
    # Auto-criação de tarefa quando alerta dispara (associação)
    criar_tarefa = models.BooleanField(
        default=False,
        help_text="Se marcado, cria Tarefa no Kanban quando alerta dispara",
    )
    titulo_tarefa = models.CharField(
        max_length=120,
        blank=True,
        help_text="Ex: Verificar sistema de irrigação — será usado como descrição da tarefa",
    )
    cargo_tarefa = models.CharField(
        max_length=30,
        blank=True,
        help_text="Cargo/Área alvo: MECANICA, CAMPO, PECUARIA, ESTOQUE, GERAL",
    )
    setor_tarefa = models.CharField(max_length=100, blank=True)
    prioridade_tarefa = models.CharField(
        max_length=10,
        choices=[
            ("baixa", "Baixa"),
            ("media", "Média"),
            ("alta", "Alta"),
            ("urgente", "Urgente"),
        ],
        default="media",
    )
    # Automação física: ao disparar, enfileira comando no device (opt-in
    # explícito do produtor; dedupe + rate-limit do enfileirar protegem).
    acao_fisica = models.CharField(
        max_length=15,
        choices=[
            ("", "Só alertar"),
            ("abrir_valvula", "Abrir válvula"),
            ("fechar_valvula", "Fechar válvula"),
        ],
        default="",
        blank=True,
    )
    device_alvo = models.ForeignKey(
        "Device",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="regras_acao",
        help_text="Device acionado (vazio = o device da leitura)",
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Regra de Alerta"
        verbose_name_plural = "Regras de Alerta"

    def __str__(self):
        return f"{self.nome} [{self.metric} {self.tipo}]"


class AlertaTelemetria(models.Model):
    regra = models.ForeignKey(
        "RegraAlertaTelemetria",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="alertas",
    )
    propriedade = models.ForeignKey(
        "Propriedade", on_delete=models.CASCADE, related_name="alertas_telemetria"
    )
    device = models.ForeignKey(
        "Device", on_delete=models.SET_NULL, null=True, blank=True
    )
    metric = models.CharField(max_length=30)
    valor = models.DecimalField(max_digits=12, decimal_places=4)
    severidade = models.CharField(max_length=10)
    mensagem = models.TextField()
    resolvido = models.BooleanField(default=False)
    timestamp = models.DateTimeField()
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Alerta Telemetria"
        verbose_name_plural = "Alertas Telemetria"
        ordering = ["-timestamp"]

    def __str__(self):
        return (
            f"[{self.severidade}] {self.metric}={self.valor} @ {self.timestamp:%H:%M}"
        )


class ComandoDevice(models.Model):
    STATUS_CHOICES = [
        ("pendente", "Pendente"),
        ("enviado", "Enviado"),
        ("ack", "ACK"),
        ("erro", "Erro"),
    ]
    device = models.ForeignKey(
        "Device", on_delete=models.CASCADE, related_name="comandos"
    )
    comando = models.CharField(
        max_length=50, help_text="Ex: set_interval, reboot, calibrate, valve_open"
    )
    payload = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="pendente")
    resposta = models.JSONField(default=dict, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    enviado_em = models.DateTimeField(null=True, blank=True)
    # Governança IA (P3): timeout/retry + anti-toggling
    tentativas = models.IntegerField(default=0)
    expira_em = models.DateTimeField(
        null=True, blank=True, help_text="após este horário, pendente/enviado vira erro"
    )
    ultimo_erro = models.CharField(max_length=200, blank=True)

    class Meta:
        verbose_name = "Comando Device"
        verbose_name_plural = "Comandos Device"
        ordering = ["-criado_em"]

    def __str__(self):
        return f"{self.comando} -> {self.device.device_eui[:8]} [{self.status}]"


class FonteDadosExterna(models.Model):
    TIPO_CHOICES = [
        ("INMET", "INMET (estações oficiais)"),
        ("NASA_POWER", "NASA POWER"),
        ("OPEN_METEO", "Open-Meteo"),
        ("SENTINEL", "Sentinel-2 NDVI"),
        ("CHIRPSTACK", "ChirpStack LoRaWAN"),
        ("TTN", "The Things Network"),
    ]
    propriedade = models.ForeignKey(
        "Propriedade",
        on_delete=models.CASCADE,
        related_name="fontes_externas",
        null=True,
        blank=True,
    )
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    nome = models.CharField(max_length=100)
    config = models.JSONField(
        default=dict, help_text='Ex: {"inmet_codigo": "A001", "lat": -15, "lon": -47}'
    )
    ultimo_sync = models.DateTimeField(null=True, blank=True)
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Fonte Dados Externa"
        verbose_name_plural = "Fontes Dados Externas"

    def __str__(self):
        return f"{self.get_tipo_display()} - {self.nome}"


class EstacaoMeteo(models.Model):
    propriedade = models.ForeignKey(
        "Propriedade", on_delete=models.CASCADE, related_name="estacoes_meteo"
    )
    nome = models.CharField(max_length=100)
    codigo_inmet = models.CharField(
        max_length=20, blank=True, null=True, help_text="Código da estação INMET"
    )
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    ativa = models.BooleanField(default=True)
    data_instalacao = models.DateField(blank=True, null=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Estação Meteorológica"
        verbose_name_plural = "Estações Meteorológicas"

    def __str__(self):
        return f"{self.nome} ({self.propriedade.nome})"


class LeituraSensor(models.Model):
    TIPO_CHOICES = [
        ("temperatura", "Temperatura (°C)"),
        ("umidade", "Umidade (%)"),
        ("pressao", "Pressão (hPa)"),
        ("chuva", "Chuva (mm)"),
        ("vento_vel", "Velocidade Vento (m/s)"),
        ("vento_dir", "Direção Vento (°)"),
        ("radiacao", "Radiação Solar (W/m²)"),
        ("umidade_solo", "Umidade Solo (%)"),
        ("condutividade", "Condutividade (dS/m)"),
        ("ph", "pH"),
        ("nivel", "Nível (m)"),
        ("vazao", "Vazão (L/s)"),
        ("outro", "Outro"),
    ]
    estacao = models.ForeignKey(
        "EstacaoMeteo", on_delete=models.CASCADE, related_name="leituras"
    )
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    valor = models.DecimalField(max_digits=10, decimal_places=3)
    unidade = models.CharField(max_length=10)
    timestamp = models.DateTimeField()
    qualidade = models.CharField(
        max_length=20, default="good", help_text="good, suspect, bad"
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-timestamp"]
        verbose_name = "Leitura de Sensor"
        verbose_name_plural = "Leituras de Sensores"
        indexes = [
            models.Index(fields=["estacao", "tipo", "timestamp"]),
        ]

    def __str__(self):
        return f"{self.estacao.nome} - {self.get_tipo_display()}: {self.valor} {self.unidade}"
