from rest_framework import serializers

from app.models import (
    AlertaTelemetria,
    ComandoDevice,
    Device,
    FonteDadosExterna,
    Gateway,
    RegraAlertaTelemetria,
    TelemetryData,
)


def _valida_dono(value, request):
    """Recusa gravar FK apontando para objeto de OUTRO usuário.

    O permission class (`IsOwnerPropriedade`) só roda em detalhe — no
    create/PATCH o `propriedade`/`device` vinha direto do payload e o
    objeto nascia/sobrevivia no tenant alheio (ex.: enfileirar comando
    para o dispositivo do vizinho). Cobre create E update, porque a
    validação é do serializer.
    """
    if request is None or value is None:
        return value
    if hasattr(value, "user_id"):  # o valor é a própria Propriedade
        dono_id = value.user_id
    else:
        prop = getattr(value, "propriedade", None)
        if prop is None:
            prop = getattr(getattr(value, "device", None), "propriedade", None)
        dono_id = getattr(prop, "user_id", None)
    if dono_id != request.user.id:
        raise serializers.ValidationError("Este item não pertence à sua propriedade.")
    return value


def _valida_fk_dono(campo):
    """Factory: `validate_<campo>` que delega a `_valida_dono`."""

    def validator(self, value):
        return _valida_dono(value, self.context.get("request"))

    validator.__name__ = f"validate_{campo}"
    return validator


class GatewaySerializer(serializers.ModelSerializer):
    dispositivos = serializers.IntegerField(source="devices.count", read_only=True)

    class Meta:
        model = Gateway
        fields = [
            "id",
            "propriedade",
            "nome",
            "tipo",
            "gateway_eui",
            "api_key",
            "latitude",
            "longitude",
            "status",
            "firmware_version",
            "intervalo_push_seg",
            "ultimo_contato",
            "config",
            "dispositivos",
            "criado_em",
        ]
        read_only_fields = ["api_key", "criado_em", "ultimo_contato"]
        extra_kwargs = {"propriedade": {"required": True}}

    validate_propriedade = _valida_fk_dono("propriedade")


class DeviceSerializer(serializers.ModelSerializer):
    topic = serializers.CharField(read_only=True)

    class Meta:
        model = Device
        fields = [
            "id",
            "gateway",
            "propriedade",
            "talhao",
            "estacao",
            "maquinario",
            "animal",
            "device_eui",
            "nome",
            "tipo",
            "protocolo",
            "mqtt_topic",
            "topic",
            "intervalo_seg",
            "bateria_pct",
            "rssi",
            "snr",
            "ativo",
            "ultimo_push",
            "profile",
            "raw_config",
            "criado_em",
        ]
        read_only_fields = ["criado_em", "ultimo_push", "bateria_pct", "rssi", "snr"]

    validate_propriedade = _valida_fk_dono("propriedade")
    validate_gateway = _valida_fk_dono("gateway")
    validate_talhao = _valida_fk_dono("talhao")
    validate_estacao = _valida_fk_dono("estacao")
    validate_maquinario = _valida_fk_dono("maquinario")
    validate_animal = _valida_fk_dono("animal")


class TelemetryDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = TelemetryData
        fields = [
            "id",
            "device",
            "estacao",
            "propriedade",
            "talhao",
            "metric",
            "value",
            "unit",
            "timestamp",
            "qualidade",
            "raw_payload",
            "criado_em",
        ]
        read_only_fields = ["criado_em"]


class RegraAlertaSerializer(serializers.ModelSerializer):
    class Meta:
        model = RegraAlertaTelemetria
        fields = [
            "id",
            "propriedade",
            "nome",
            "metric",
            "tipo",
            "valor_ref",
            "janela_min",
            "severidade",
            "ativa",
            "config",
            "criado_em",
        ]

    validate_propriedade = _valida_fk_dono("propriedade")


class AlertaTelemetriaSerializer(serializers.ModelSerializer):
    class Meta:
        model = AlertaTelemetria
        fields = [
            "id",
            "regra",
            "propriedade",
            "device",
            "metric",
            "valor",
            "severidade",
            "mensagem",
            "resolvido",
            "timestamp",
            "criado_em",
        ]


class ComandoDeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = ComandoDevice
        fields = [
            "id",
            "device",
            "comando",
            "payload",
            "status",
            "resposta",
            "criado_em",
            "enviado_em",
        ]
        # status/resposta/criado_em/enviado_em são preenchidos pelo
        # broker de telemetria, não pelo cliente.
        read_only_fields = ["status", "resposta", "criado_em", "enviado_em"]

    validate_device = _valida_fk_dono("device")


class FonteDadosExternaSerializer(serializers.ModelSerializer):
    class Meta:
        model = FonteDadosExterna
        fields = [
            "id",
            "propriedade",
            "tipo",
            "nome",
            "config",
            "ultimo_sync",
            "ativo",
            "criado_em",
        ]

    validate_propriedade = _valida_fk_dono("propriedade")
