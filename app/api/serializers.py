"""
Serializers DRF profissionais com:
- Campos explícitos (sem __all__)
- Validação estrita
- Campos read_only apropriados
- Factory dinâmico para RegistroProducao por cultura (baseado em cultures-config.json)
"""

from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework import serializers
from app.api.fiscal_serializers import CadastroFiscalSerializer

from app.models import (
    Cultivar,
    LoteSemente,
    EnsaioCultivar,
    FaixaEnsaio,
    IAAlertaProativo,
    Viveiro,
    LoteMuda,
    MixPastagem,
    ZARC,
    Animal,
    ApiarioColmeia,
    AplicacaoInsumo,
    CentroCusto,
    ConciliacaoBancaria,
    ContaBancaria,
    Cultura,
    CustoProducao,
    Despesca,
    ErroReport,
    EstacaoMeteo,
    EstagioCultura,
    EstoqueItem,
    Experimento,
    Funcionario,
    Insumo,
    LancamentoDetalhado,
    LancamentoFinanceiro,
    LeituraSensor,
    LoteAquatico,
    ManutencaoMaquinario,
    Maquinario,
    MedicaoExperimental,
    MonitoramentoPraga,
    MovimentacaoBancaria,
    MovimentoEstoque,
    Notificacao,
    NotificacaoTemplate,
    Parcelamento,
    PerfilUsuario,
    PrescricaoVRA,
    ProducaoAnimal,
    ProducaoApiario,
    Propriedade,
    PushSubscription,
    Racao,
    RastreabilidadeSafra,
    RastroItem,
    ReceituarioAgronomico,
    RegistroProducao,
    RelatorioGerado,
    RelatorioTemplate,
    Safra,
    SafraTalhao,
    Talhao,
    TalhaoGeometria,
    TarefaEstagio,
    WidgetUsuario,
)

from .culture_config import build_dynamic_serializer_fields

# ============================================================================
# BASE SERIALIZERS & PERMISSIONS
# ============================================================================


class IsOwnerPermission:
    """Mixin para verificar ownership via propriedade.user ou user direto."""

    def check_object_permission(self, obj, request):
        if hasattr(obj, "user"):
            return obj.user == request.user
        if hasattr(obj, "propriedade") and hasattr(obj.propriedade, "user"):
            return obj.propriedade.user == request.user
        return False


# ============================================================================
# CULTURA & PROPRIEDADE
# ============================================================================


class CulturaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cultura
        fields = [
            "id",
            "nome",
            "grupo",
            "unidade_comercial",
            "janela_plantio_inicio",
            "janela_plantio_fim",
            "chave_mercado",
            "ibge_codigo",
            "agrodoc_produto",
            "ciclo_dias",
            "ativo",
        ]
        read_only_fields = ["id"]


class PropriedadeSerializer(serializers.ModelSerializer):
    cadastro_fiscal = CadastroFiscalSerializer(required=False)
    talhao_count = serializers.IntegerField(read_only=True)
    safra_count = serializers.IntegerField(read_only=True)
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())

    class Meta:
        model = Propriedade
        fields = [
            "id",
            "user",
            "nome",
            "area_total",
            "uf",
            "cidade",
            "endereco",
            "bioma",
            "pais",
            "moeda",
            "culturas",
            "data_cadastro",
            "talhao_count",
            "safra_count",
            "cpf_cnpj",
            "cadastro_fiscal",
            "forma_apuracao",
            "caepf",
            "inscricao_estadual",
            "tipo_exploracao",
            "participacao",
            # Endereco e identificadores fiscais. MEDIDO 2026-10-05: sem estes,
            # `CAD_MUN` e `CEP` do LCDPR 1.3 sao **Sim** e sao escritos vazios —
            # ficheiro que a Receita recusa. Vem com o enunciado transcrito; o
            # modelo e' `0070_propriedade_endereco_fiscal`.
            "cod_municipio",
            "cep",
            "bairro",
            "telefone",
            "cad_itr",
        ]
        read_only_fields = ["id", "data_cadastro", "talhao_count", "safra_count"]

    def validate_area_total(self, value):
        if value <= 0:
            raise serializers.ValidationError("Área total deve ser maior que zero.")
        return value

    def validate_uf(self, value):
        if value and len(value) != 2:
            raise serializers.ValidationError("UF deve ter 2 caracteres.")
        return value.upper() if value else value


# ============================================================================
# TALHÃO & SAFRA
# ============================================================================


class TalhaoSerializer(serializers.ModelSerializer):
    cultura_nome = serializers.CharField(source="cultura_atual.nome", read_only=True)
    propriedade_nome = serializers.CharField(source="propriedade.nome", read_only=True)

    class Meta:
        model = Talhao
        fields = [
            "id",
            "propriedade",
            "propriedade_nome",
            "nome",
            "area_hectare",
            "cultura_atual",
            "cultura_nome",
            "tipo_solo",
            "coordenadas",
            "ativo",
        ]
        read_only_fields = ["id"]

    def validate_area_hectare(self, value):
        if value <= 0:
            raise serializers.ValidationError("Área deve ser maior que zero.")
        return value

    def validate_propriedade(self, value):
        request = self.context.get("request")
        if request and value.user != request.user:
            raise serializers.ValidationError(
                "Esta propriedade não pertence ao seu usuário."
            )
        return value


class SafraSerializer(serializers.ModelSerializer):
    cultura_nome = serializers.CharField(source="cultura.nome", read_only=True)
    talhao_nome = serializers.CharField(source="talhao.nome", read_only=True)
    propriedade_nome = serializers.CharField(source="propriedade.nome", read_only=True)

    class Meta:
        model = Safra
        fields = [
            "id",
            "propriedade",
            "propriedade_nome",
            "talhao",
            "talhao_nome",
            "cultura",
            "cultura_nome",
            "ano",
            "safra_nome",
            "area_plantada",
            "area_colhida",
            "producao_total",
            "produtividade",
            "receita_estimada",
            "data_plantio",
            "data_colheita",
            "observacao",
            "criado_em",
        ]
        read_only_fields = ["id", "criado_em"]

    def validate_area_plantada(self, value):
        if value <= 0:
            raise serializers.ValidationError("Área plantada deve ser maior que zero.")
        return value

    def validate_propriedade(self, value):
        request = self.context.get("request")
        if request and value.user != request.user:
            raise serializers.ValidationError(
                "Esta propriedade não pertence ao seu usuário."
            )
        return value

    def validate(self, attrs):
        if attrs.get("data_colheita") and attrs.get("data_plantio"):
            if attrs["data_colheita"] < attrs["data_plantio"]:
                raise serializers.ValidationError(
                    "Data de colheita não pode ser anterior ao plantio."
                )
        self._validar_area_contra_o_terreno(attrs)
        return attrs

    #: Uma safra pode ocupar a área do talhão inteiro, e um pouco mais sem
    #: drama (talhões que se sobrepõem num shapefile, ou um talhão cadastrado
    #: "a olho" que ficou pequeno). Acima disso já não é imprecisão: é outro
    #: número. A Fazenda Modelo tem uma safra de 45.000 ha apontada para um
    #: talhão de 15 ha — 3.000x — e nenhuma validação a recusou.
    TOLERANCIA_TALHAO = 1.10

    def _validar_area_contra_o_terreno(self, attrs):
        """A área da safra tem de caber no terreno onde ela foi registada.

        POR QUE UM VALIDADOR E NÃO UM COMANDO DE SANEAMENTO
        ===================================================
        O dado já está no banco: 45.000 ha num talhão de 15 ha, numa
        propriedade de 1.240 ha. Nenhum `checar_drift` o apanha — o drift
        compara SCHEMA (o banco e os modelos dizem o mesmo), e este registo
        tem o schema certo e o valor errado. O valor errado é o que produz
        o número impossível no painel, e o número impossível é o que o
        produtor multiplica pelo preço da saca.

        Corrigir em silêncio seria pior que aceitar: ninguém sabe qual era
        o valor certo, e um número inventado para tapar outro é uma segunda
        mentira. O que se faz é RECUSAR a entrada nova com uma mensagem que
        diz o que se passou e onde — e deixar a correção dos registos
        existentes para quem conhece a fazenda.
        """
        area = attrs.get("area_plantada")
        if area is None:
            return
        area = float(area)

        # 1. O talhão. É a medida mais específica: uma safra vive num talhão.
        # O que não veio no payload, lê-se do registo que está a ser editado.
        #
        # Numa edição, `attrs` traz só o que mudou: corrigir a área sem
        # tocar no talhão produz um `attrs` sem `talhao`, e a validação
        # comparava a área nova com... nada. O `create` era validado e o
        # `update` passava limpo — a porta ficava aberta exactamente por
        # onde o defeito tinha entrado.
        instance = getattr(self, "instance", None)
        if instance is not None:
            talhao = attrs.get("talhao", getattr(instance, "talhao", None))
            propriedade = attrs.get(
                "propriedade", getattr(instance, "propriedade", None)
            )
        else:
            talhao = attrs.get("talhao")
            propriedade = attrs.get("propriedade")
        if talhao is not None:
            area_talhao = float(getattr(talhao, "area_hectare", 0) or 0)
            if area_talhao > 0 and area > area_talhao * self.TOLERANCIA_TALHAO:
                raise serializers.ValidationError(
                    {
                        "area_plantada": (
                            f"A área plantada ({area:,.2f} ha) é maior do que o "
                            f"talhão '{talhao.nome}' ({area_talhao:,.2f} ha). Uma "
                            "safra não ocupa mais terra do que o talhão onde "
                            "está registada — reveja o talhão ou divida a "
                            "safra por talhões."
                        )
                    }
                )

        # 2. A propriedade, com folga. Isto apanha o caso em que não há
        #    talhão ligado: a área de uma safra não passa de várias vezes a
        #    área declarada da fazenda. Uma fazenda pode plantar duas safras
        #    no mesmo ano (soja e safrinha), por isso o limite é generoso —
        #    mas 45.000 ha numa fazenda de 1.240 ha não é imprecisão de
        #    cadastro, é outro número.
        if propriedade is not None:
            area_prop = float(getattr(propriedade, "area_total", 0) or 0)
            if area_prop > 0 and area > area_prop * 3:
                raise serializers.ValidationError(
                    {
                        "area_plantada": (
                            f"A área plantada ({area:,.2f} ha) é mais de três "
                            f"vezes a área da propriedade "
                            f"({area_prop:,.2f} ha). Isto não é uma safra — "
                            "é outro número. Reveja a área declarada da "
                            "propriedade ou a área desta safra."
                        )
                    }
                )


# ============================================================================
# INSUMOS & APLICAÇÃ•ES
# ============================================================================


class InsumoSerializer(serializers.ModelSerializer):
    propriedade_nome = serializers.CharField(source="propriedade.nome", read_only=True)

    class Meta:
        model = Insumo
        fields = [
            "id",
            "propriedade",
            "propriedade_nome",
            "categoria",
            "nome",
            "quantidade",
            "unidade",
            "valor_unitario",
            "estoque_minimo",
            "data_aquisicao",
            "fornecedor",
            "nota_fiscal",
        ]
        read_only_fields = ["id"]

    def validate_quantidade(self, value):
        if value < 0:
            raise serializers.ValidationError("Quantidade não pode ser negativa.")
        return value

    def validate_valor_unitario(self, value):
        if value < 0:
            raise serializers.ValidationError("Valor unitário não pode ser negativo.")
        return value

    def validate_estoque_minimo(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError("Estoque mínimo não pode ser negativo.")
        return value

    def validate_propriedade(self, value):
        request = self.context.get("request")
        if request and value.user != request.user:
            raise serializers.ValidationError(
                "Esta propriedade não pertence ao seu usuário."
            )
        return value


class AplicacaoInsumoSerializer(serializers.ModelSerializer):
    insumo_nome = serializers.CharField(source="insumo.nome", read_only=True)
    talhao_nome = serializers.CharField(source="talhao.nome", read_only=True)

    class Meta:
        model = AplicacaoInsumo
        fields = [
            "id",
            "insumo",
            "insumo_nome",
            "talhao",
            "talhao_nome",
            "data",
            "dose",
            "responsavel",
            "observacao",
        ]
        read_only_fields = ["id"]

    def validate_dose(self, value):
        if value <= 0:
            raise serializers.ValidationError("Dose deve ser maior que zero.")
        return value


# ============================================================================
# FUNCIONÁRIOS & MÃO DE OBRA
# ============================================================================


class FuncionarioSerializer(serializers.ModelSerializer):
    propriedade_nome = serializers.CharField(source="propriedade.nome", read_only=True)
    cargo_display = serializers.CharField(source="get_cargo_display", read_only=True)
    user_id = serializers.IntegerField(
        source="user.id", read_only=True, allow_null=True
    )

    class Meta:
        model = Funcionario
        fields = [
            "id",
            "propriedade",
            "propriedade_nome",
            "user",
            "user_id",
            "nome",
            "cargo",
            "cargo_display",
            "salario",
            "data_admissao",
            "data_demissao",
            "telefone",
            "email",
            "ativo",
            "nome_fazenda_login",
        ]
        # `user` é OneToOneField com a conta de login: gravável, permitia
        # apontar o funcionário para a conta de outra pessoa e, pela action
        # remover_login (user.py), deletar a vítima em CASCADE.
        read_only_fields = [
            "id",
            "user",
            "user_id",
            "cargo_display",
            "propriedade_nome",
        ]

    def validate_salario(self, value):
        if value < 0:
            raise serializers.ValidationError("Salário não pode ser negativo.")
        return value

    def validate_propriedade(self, value):
        request = self.context.get("request")
        if request and value.user != request.user:
            raise serializers.ValidationError(
                "Esta propriedade não pertence ao seu usuário."
            )
        return value


class OperarioRegistroSerializer(serializers.ModelSerializer):
    """Serializer para registro de operário com login"""

    username = serializers.CharField(write_only=True, required=True)
    senha = serializers.CharField(
        write_only=True, required=True, style={"input_type": "password"}
    )
    propriedade = serializers.PrimaryKeyRelatedField(
        queryset=Propriedade.objects.all(), required=True, write_only=True
    )
    user_id = serializers.IntegerField(read_only=True)
    nome_fazenda_login = serializers.CharField(
        source="funcionario.nome_fazenda_login", read_only=True
    )

    class Meta:
        model = Funcionario
        fields = [
            "id",
            "nome",
            "cargo",
            "email",
            "propriedade",
            "username",
            "senha",
            "user_id",
            "nome_fazenda_login",
        ]
        read_only_fields = ["id", "user_id", "nome_fazenda_login"]

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("Este nome de usuário já está em uso.")
        return value

    def validate_propriedade(self, value):
        request = self.context.get("request")
        if request and value.user != request.user:
            raise serializers.ValidationError(
                "Esta propriedade não pertence ao seu usuário."
            )
        return value

    def create(self, validated_data):
        username = validated_data.pop("username")
        senha = validated_data.pop("senha")
        propriedade = validated_data.pop("propriedade")

        funcionario = Funcionario.objects.create(
            propriedade=propriedade, **validated_data
        )

        if not funcionario.nome_fazenda_login:
            funcionario.nome_fazenda_login = funcionario.propriedade.nome
            funcionario.save()

        user = User.objects.create_user(
            username=username,
            password=senha,
            email=funcionario.email or "",
            first_name=funcionario.nome.split()[0] if funcionario.nome else "",
        )

        PerfilUsuario.objects.create(
            user=user,
            tipo_usuario="operario",
            propriedade_vinculada=funcionario.propriedade,
            funcionario=funcionario,
        )

        funcionario.user = user
        funcionario.save()
        funcionario.user_id = user.id
        return funcionario


# ============================================================================
# MÁQUINARIOS & FINANCEIRO
# ============================================================================


class MaquinarioSerializer(serializers.ModelSerializer):
    propriedade_nome = serializers.CharField(source="propriedade.nome", read_only=True)
    tipo_display = serializers.CharField(source="get_tipo_display", read_only=True)

    class Meta:
        model = Maquinario
        fields = [
            "id",
            "propriedade",
            "propriedade_nome",
            "tipo",
            "tipo_display",
            "nome",
            "marca",
            "modelo",
            "ano_fabricacao",
            "horas_uso",
            "ultima_manutencao",
            "proxima_manutencao",
            "ativo",
        ]
        read_only_fields = ["id", "tipo_display", "propriedade_nome"]

    def validate_horas_uso(self, value):
        if value < 0:
            raise serializers.ValidationError("Horas de uso não pode ser negativo.")
        return value

    def validate_propriedade(self, value):
        request = self.context.get("request")
        if request and value.user != request.user:
            raise serializers.ValidationError(
                "Esta propriedade não pertence ao seu usuário."
            )
        return value


class LancamentoFinanceiroSerializer(serializers.ModelSerializer):
    talhao_nome = serializers.CharField(source="talhao.nome", read_only=True)
    safra_nome = serializers.CharField(source="safra.safra_nome", read_only=True)
    tipo_display = serializers.CharField(source="get_tipo_display", read_only=True)
    categoria_display = serializers.CharField(
        source="get_categoria_display", read_only=True
    )

    class Meta:
        model = LancamentoFinanceiro
        fields = [
            "id",
            "propriedade",
            "tipo",
            "tipo_display",
            "categoria",
            "categoria_display",
            "valor",
            "data",
            "descricao",
            "participante",
            "participante_doc",
            "talhao",
            "talhao_nome",
            "safra",
            "safra_nome",
            "comprovante",
            "pago",
            "data_pagamento",
            "conta_bancaria",
            "tipo_documento_lcdpr",
            "numero_documento",
            "tipo_lancamento_lcdpr",
        ]
        read_only_fields = ["id", "tipo_display", "categoria_display"]

    def validate_valor(self, value):
        if value <= 0:
            raise serializers.ValidationError("Valor deve ser maior que zero.")
        return value

    def validate_propriedade(self, value):
        request = self.context.get("request")
        if request and value.user != request.user:
            raise serializers.ValidationError(
                "Esta propriedade não pertence ao seu usuário."
            )
        return value


# ============================================================================
# ANIMAL & PRODUÇÃO ANIMAL
# ============================================================================


class AnimalSerializer(serializers.ModelSerializer):
    propriedade_nome = serializers.CharField(source="propriedade.nome", read_only=True)
    especie_display = serializers.CharField(
        source="get_especie_display", read_only=True
    )
    tipo_producao_display = serializers.CharField(
        source="get_tipo_producao_display", read_only=True
    )

    class Meta:
        model = Animal
        fields = [
            "id",
            "propriedade",
            "propriedade_nome",
            "especie",
            "especie_display",
            "tipo_producao",
            "tipo_producao_display",
            "raca",
            "quantidade",
            "peso_medio",
            "data_entrada",
            "observacao",
        ]
        read_only_fields = [
            "id",
            "especie_display",
            "tipo_producao_display",
            "propriedade_nome",
        ]

    def validate_quantidade(self, value):
        if value <= 0:
            raise serializers.ValidationError("Quantidade deve ser maior que zero.")
        return value

    def validate_propriedade(self, value):
        request = self.context.get("request")
        if request and value.user != request.user:
            raise serializers.ValidationError(
                "Esta propriedade não pertence ao seu usuário."
            )
        return value


class ProducaoAnimalSerializer(serializers.ModelSerializer):
    animal_info = serializers.CharField(source="animal.__str__", read_only=True)
    animal_especie = serializers.CharField(
        source="animal.get_especie_display", read_only=True
    )

    class Meta:
        model = ProducaoAnimal
        fields = [
            "id",
            "animal",
            "animal_info",
            "animal_especie",
            "data",
            "quantidade_produzida",
            "unidade",
            "valor_estimado",
            "observacao",
        ]
        read_only_fields = ["id", "animal_info", "animal_especie"]

    def validate_quantidade_produzida(self, value):
        if value < 0:
            raise serializers.ValidationError(
                "Quantidade produzida não pode ser negativa."
            )
        return value


# ============================================================================
# AQUÁTICO (LOTES & DESPESCAS)
# ============================================================================


class LoteAquaticoSerializer(serializers.ModelSerializer):
    propriedade_nome = serializers.CharField(source="propriedade.nome", read_only=True)
    especie_display = serializers.CharField(
        source="get_especie_display", read_only=True
    )
    sistema_display = serializers.CharField(
        source="get_sistema_display", read_only=True
    )

    class Meta:
        model = LoteAquatico
        fields = [
            "id",
            "propriedade",
            "propriedade_nome",
            "especie",
            "especie_display",
            "sistema",
            "sistema_display",
            "ambiente",
            "quantidade",
            "biomassa_media",
            "data_povoamento",
            "observacao",
        ]
        read_only_fields = [
            "id",
            "especie_display",
            "sistema_display",
            "propriedade_nome",
        ]

    def validate_quantidade(self, value):
        if value <= 0:
            raise serializers.ValidationError("Quantidade deve ser maior que zero.")
        return value

    def validate_propriedade(self, value):
        request = self.context.get("request")
        if request and value.user != request.user:
            raise serializers.ValidationError(
                "Esta propriedade não pertence ao seu usuário."
            )
        return value


class DespescaSerializer(serializers.ModelSerializer):
    lote_info = serializers.CharField(source="lote.__str__", read_only=True)
    lote_especie = serializers.CharField(
        source="lote.get_especie_display", read_only=True
    )

    class Meta:
        model = Despesca
        fields = [
            "id",
            "lote",
            "lote_info",
            "lote_especie",
            "data",
            "quantidade_kg",
            "valor_estimado",
            "observacao",
        ]
        read_only_fields = ["id", "lote_info", "lote_especie"]

    def validate_quantidade_kg(self, value):
        if value < 0:
            raise serializers.ValidationError("Quantidade (kg) não pode ser negativa.")
        return value


# ============================================================================
# ESTOQUE & APIÁRIO
# ============================================================================


class EstoqueItemSerializer(serializers.ModelSerializer):
    propriedade_nome = serializers.CharField(source="propriedade.nome", read_only=True)
    categoria_display = serializers.CharField(
        source="get_categoria_display", read_only=True
    )

    class Meta:
        model = EstoqueItem
        fields = [
            "id",
            "propriedade",
            "propriedade_nome",
            "categoria",
            "categoria_display",
            "nome",
            "quantidade",
            "unidade",
            "local",
            "data_validade",
            "observacao",
        ]
        read_only_fields = ["id", "categoria_display", "propriedade_nome"]

    def validate_quantidade(self, value):
        if value < 0:
            raise serializers.ValidationError("Quantidade não pode ser negativa.")
        return value

    def validate_propriedade(self, value):
        request = self.context.get("request")
        if request and value.user != request.user:
            raise serializers.ValidationError(
                "Esta propriedade não pertence ao seu usuário."
            )
        return value


class ApiarioColmeiaSerializer(serializers.ModelSerializer):
    propriedade_nome = serializers.CharField(source="propriedade.nome", read_only=True)

    class Meta:
        model = ApiarioColmeia
        fields = [
            "id",
            "propriedade",
            "propriedade_nome",
            "identificacao",
            "tipo_abelha",
            "data_instalacao",
            "ativa",
            "localizacao",
            "observacao",
        ]
        read_only_fields = ["id", "propriedade_nome"]

    def validate_propriedade(self, value):
        request = self.context.get("request")
        if request and value.user != request.user:
            raise serializers.ValidationError(
                "Esta propriedade não pertence ao seu usuário."
            )
        return value


class ProducaoApiarioSerializer(serializers.ModelSerializer):
    colmeia_id = serializers.CharField(source="colmeia.identificacao", read_only=True)
    colmeia_propriedade = serializers.CharField(
        source="colmeia.propriedade.nome", read_only=True
    )

    class Meta:
        model = ProducaoApiario
        fields = [
            "id",
            "colmeia",
            "colmeia_id",
            "colmeia_propriedade",
            "data_extracao",
            "producao_mel_kg",
            "producao_cera_kg",
            "valor_venda",
            "observacao",
        ]
        read_only_fields = ["id", "colmeia_id", "colmeia_propriedade"]

    def validate_colmeia(self, value):
        request = self.context.get("request")
        if request and value.propriedade.user != request.user:
            raise serializers.ValidationError(
                "Esta colmeia não pertence ao seu usuário."
            )
        return value


# ============================================================================
# WIDGETS, PERFIL, NOTIFICAÇÃ•ES
# ============================================================================


class WidgetUsuarioSerializer(serializers.ModelSerializer):
    class Meta:
        model = WidgetUsuario
        fields = [
            "id",
            "user",
            "tipo_widget",
            "posicao_x",
            "posicao_y",
            "tamanho_w",
            "tamanho_h",
            "config",
        ]
        read_only_fields = ["id", "user"]


class PerfilUsuarioSerializer(serializers.ModelSerializer):
    user_username = serializers.CharField(source="user.username", read_only=True)
    user_email = serializers.CharField(source="user.email", read_only=True)

    class Meta:
        model = PerfilUsuario
        fields = [
            "id",
            "user",
            "user_username",
            "user_email",
            "tipo_usuario",
            "propriedade_vinculada",
            "funcionario",
            "idioma",
            "tema",
        ]
        # tipo_usuario / propriedade_vinculada / funcionario são a CHAVE de
        # escopo do sistema (app/hierarquia.py: propriedades_visiveis(),
        # pode_acessar(), propriedade_financeira()). Graváveis, viravam
        # escalada de privilégio: PATCH /api/perfis-usuario/<id>/ com a
        # fazenda de outro usuário passava a ler o financeiro alheio, e
        # {"tipo_usuario": "produtor"} contornava toda a hierarquia.
        # Alteração de vínculo acontece só nos fluxos internos (signals,
        # onboarding e telas do produtor dono), nunca por este serializer.
        read_only_fields = [
            "id",
            "user",
            "user_username",
            "user_email",
            "tipo_usuario",
            "propriedade_vinculada",
            "funcionario",
        ]


class NotificacaoSerializer(serializers.ModelSerializer):
    nivel_display = serializers.CharField(source="get_nivel_display", read_only=True)

    class Meta:
        model = Notificacao
        fields = [
            "id",
            "user",
            "titulo",
            "mensagem",
            "nivel",
            "nivel_display",
            "lida",
            "link",
            "criado_em",
        ]
        read_only_fields = ["id", "user", "criado_em", "nivel_display"]


# ============================================================================
# ESTAÇÃ•ES METEOROLÓGICAS & SENSORES
# ============================================================================


class EstacaoMeteoSerializer(serializers.ModelSerializer):
    propriedade_nome = serializers.CharField(source="propriedade.nome", read_only=True)

    class Meta:
        model = EstacaoMeteo
        fields = [
            "id",
            "propriedade",
            "propriedade_nome",
            "nome",
            "codigo_inmet",
            "latitude",
            "longitude",
            "ativa",
            "data_instalacao",
            "criado_em",
        ]
        read_only_fields = ["id", "criado_em", "propriedade_nome"]

    def validate_propriedade(self, value):
        request = self.context.get("request")
        if request and value.user != request.user:
            raise serializers.ValidationError(
                "Esta propriedade não pertence ao seu usuário."
            )
        return value


class LeituraSensorSerializer(serializers.ModelSerializer):
    tipo_display = serializers.CharField(source="get_tipo_display", read_only=True)
    estacao_nome = serializers.CharField(source="estacao.nome", read_only=True)

    class Meta:
        model = LeituraSensor
        fields = [
            "id",
            "estacao",
            "estacao_nome",
            "tipo",
            "tipo_display",
            "valor",
            "unidade",
            "timestamp",
            "qualidade",
            "criado_em",
        ]
        read_only_fields = ["id", "criado_em", "tipo_display", "estacao_nome"]


# ============================================================================
# GEOMETRIA & RELATÓRIOS
# ============================================================================


class TalhaoGeometriaSerializer(serializers.ModelSerializer):
    talhao_nome = serializers.CharField(source="talhao.nome", read_only=True)

    class Meta:
        model = TalhaoGeometria
        fields = [
            "id",
            "talhao",
            "talhao_nome",
            "geojson",
            "area_calculada_ha",
            "centroide_lat",
            "centroide_lon",
            "atualizado_em",
        ]
        read_only_fields = [
            "id",
            "talhao_nome",
            "area_calculada_ha",
            "centroide_lat",
            "centroide_lon",
            "atualizado_em",
        ]


class RelatorioTemplateSerializer(serializers.ModelSerializer):
    user_username = serializers.CharField(source="user.username", read_only=True)
    tipo_display = serializers.CharField(source="get_tipo_display", read_only=True)
    formato_display = serializers.CharField(
        source="get_formato_display", read_only=True
    )

    class Meta:
        model = RelatorioTemplate
        fields = [
            "id",
            "user",
            "user_username",
            "nome",
            "tipo",
            "tipo_display",
            "formato",
            "formato_display",
            "configuracao",
            "ativo",
            "criado_em",
            "atualizado_em",
        ]
        read_only_fields = [
            "id",
            "user",
            "user_username",
            "tipo_display",
            "formato_display",
            "criado_em",
            "atualizado_em",
        ]


class RelatorioGeradoSerializer(serializers.ModelSerializer):
    template_nome = serializers.CharField(source="template.nome", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = RelatorioGerado
        fields = [
            "id",
            "template",
            "template_nome",
            "user",
            "status",
            "status_display",
            "arquivo",
            "parametros",
            "erro_msg",
            "criado_em",
            "concluido_em",
        ]
        read_only_fields = [
            "id",
            "user",
            "template_nome",
            "status_display",
            "criado_em",
            "concluido_em",
        ]


# ============================================================================
# ERRO REPORT
# ============================================================================


class ErroReportSerializer(serializers.ModelSerializer):
    tipo_display = serializers.CharField(source="get_tipo_display", read_only=True)

    class Meta:
        model = ErroReport
        fields = [
            "id",
            "user",
            "email",
            "tipo",
            "tipo_display",
            "descricao",
            "passos",
            "enviar_rastreamento",
            "contexto",
            "navegador",
            "url",
            "resolvido",
            "criado_em",
            "atualizado_em",
        ]
        read_only_fields = [
            "id",
            "user",
            "email",
            "tipo_display",
            "criado_em",
            "atualizado_em",
            "resolvido",
        ]


# ============================================================================
# ESTÁGIOS & TAREFAS DE CULTURA
# ============================================================================


class TarefaEstagioSerializer(serializers.ModelSerializer):
    funcionario_nome = serializers.SerializerMethodField()
    estagio_nome = serializers.CharField(source="estagio.nome", read_only=True)

    class Meta:
        model = TarefaEstagio
        fields = [
            "id",
            "estagio",
            "estagio_nome",
            "descricao",
            "funcionario",
            "funcionario_nome",
            "cargo_alvo",
            "setor",
            "concluida",
            "concluida_em",
            "status",
            "prioridade",
            "data_limite",
            "propriedade",
            "ordem",
            "criado_em",
        ]
        read_only_fields = ["id", "criado_em", "funcionario_nome", "estagio_nome"]

    def get_funcionario_nome(self, obj):
        return obj.funcionario.nome if obj.funcionario else ""


class EstagioCulturaSerializer(serializers.ModelSerializer):
    sub_estagios = TarefaEstagioSerializer(many=True, read_only=True)
    tarefas = TarefaEstagioSerializer(many=True, read_only=True)
    concluido = serializers.BooleanField(required=False)
    registro_id = serializers.IntegerField(source="registro.id", read_only=True)

    class Meta:
        model = EstagioCultura
        fields = [
            "id",
            "registro",
            "registro_id",
            "estagio_pai",
            "nome",
            "cor",
            "icone",
            "ordem",
            "tipo",
            "concluido",
            "data_inicio",
            "data_fim",
            "criado_em",
            "atualizado_em",
            "sub_estagios",
            "tarefas",
        ]
        read_only_fields = ["id", "criado_em", "atualizado_em", "registro_id"]

    def validate_cor(self, value):
        if value and not value.startswith("#"):
            raise serializers.ValidationError(
                "Cor deve ser um código hexadecimal (ex: #0f9d6e)."
            )
        return value


# ============================================================================
# REGISTRO PRODUÇÃO - SERIALIZER BASE + FACTORY DINÂMICO
# ============================================================================


class RegistroProducaoBaseSerializer(serializers.ModelSerializer):
    """Serializer base para RegistroProducao - campos comuns a todas as culturas."""

    cultureId = serializers.SerializerMethodField()
    culturaNome = serializers.SerializerMethodField()
    groupId = serializers.CharField(source="grupo", read_only=True)
    name = serializers.CharField(source="nome", read_only=True)
    location = serializers.CharField(read_only=True)
    date = serializers.SerializerMethodField()
    quantity = serializers.SerializerMethodField()
    unit = serializers.CharField(source="unidade", read_only=True)
    observations = serializers.CharField(source="observacoes", read_only=True)
    fields = serializers.JSONField(source="fields_json", read_only=True)  # type: ignore[assignment]
    treatments = serializers.JSONField(read_only=True)
    createdAt = serializers.SerializerMethodField()
    updatedAt = serializers.SerializerMethodField()

    class Meta:
        model = RegistroProducao
        fields = [
            "id",
            "cultureId",
            "culturaNome",
            "groupId",
            "name",
            "status",
            "location",
            "date",
            "quantity",
            "unit",
            "observations",
            "fields",
            "treatments",
            "createdAt",
            "updatedAt",
        ]
        read_only_fields = fields

    def get_cultureId(self, obj):
        return obj.cultura_id if obj.cultura_id else obj.cultura_key

    def get_culturaNome(self, obj):
        return obj.cultura.nome if obj.cultura else ""

    def get_date(self, obj):
        if isinstance(obj.data_registro, str):
            return obj.data_registro
        return obj.data_registro.isoformat() if obj.data_registro else ""

    def get_quantity(self, obj):
        return float(obj.quantidade) if obj.quantidade is not None else None

    def get_createdAt(self, obj):
        return obj.criado_em.isoformat() if obj.criado_em else ""

    def get_updatedAt(self, obj):
        return obj.atualizado_em.isoformat() if obj.atualizado_em else ""


class RegistroProducaoWriteSerializer(serializers.ModelSerializer):
    """Serializer para CREATE/UPDATE - aceita campos do frontend (camelCase)."""

    cultureId = serializers.CharField(write_only=True, required=False, allow_blank=True)
    groupId = serializers.CharField(write_only=True, required=False, default="vegetal")
    name = serializers.CharField(write_only=True, required=True)
    status = serializers.CharField(write_only=True, required=False, default="ativo")
    location = serializers.CharField(write_only=True, required=False, allow_blank=True)
    date = serializers.DateField(write_only=True, required=False, allow_null=True)
    quantity = serializers.FloatField(write_only=True, required=False, allow_null=True)
    unit = serializers.CharField(write_only=True, required=False, allow_blank=True)
    observations = serializers.CharField(
        write_only=True, required=False, allow_blank=True
    )
    fields = serializers.JSONField(write_only=True, required=False, default=dict)  # type: ignore[assignment]
    treatments = serializers.JSONField(write_only=True, required=False, default=list)  # type: ignore[arg-type]

    class Meta:
        model = RegistroProducao
        fields = [
            "cultureId",
            "groupId",
            "name",
            "status",
            "location",
            "date",
            "quantity",
            "unit",
            "observations",
            "fields",
            "treatments",
        ]

    def validate_name(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Nome é obrigatório.")
        return value.strip()

    def validate_quantity(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError("Quantidade não pode ser negativa.")
        return value


def DynamicRegistroProducaoSerializerFactory(cultura_slug, user=None):
    """
    Factory que cria um serializer dinâmico para uma cultura específica.
    Injeta campos customizados baseados em cultures-config.json.
    Se user fornecido, aplica preferências (oculta campos, reordena, defaults).
    """

    dynamic_fields = build_dynamic_serializer_fields(cultura_slug, user)

    class DynamicRegistroProducaoSerializer(RegistroProducaoBaseSerializer):
        # MEDIDO 2026-10-06: `dynamic_fields` estava em `Meta.fields` sem estar
        # declarado. O DRF so' aceita um nome extra se a classe o declara ou se
        # existe no modelo — e nao existe. O `create()` responde com este
        # serializer, entao qualquer cultura COM config (cafe e' o default)
        # rebentava em 500 `ImproperlyConfigured: Field name 'dynamic_fields' is
        # not valid for model 'RegistroProducao'`.
        #
        # Declarar resolve: o DRF passa a ligar o campo, e o `to_representation`
        # abaixo substitui o valor pelo `fields_json` real.
        dynamic_fields = serializers.JSONField(required=False, default=dict)  # type: ignore[assignment]

        # Sobrescreve 'fields' para incluir campos dinâmicos na leitura
        class Meta(RegistroProducaoBaseSerializer.Meta):
            fields = RegistroProducaoBaseSerializer.Meta.fields + ["dynamic_fields"]

        def to_representation(self, instance):
            data = super().to_representation(instance)
            # Injeta campos dinâmicos do fields_json se existirem
            if instance.fields_json:
                data["dynamic_fields"] = instance.fields_json
            else:
                data["dynamic_fields"] = {}
            return data

    # Adiciona campos dinâmicos ao serializer de escrita também
    class DynamicRegistroProducaoWriteSerializer(RegistroProducaoWriteSerializer):
        class Meta(RegistroProducaoWriteSerializer.Meta):
            fields = RegistroProducaoWriteSerializer.Meta.fields

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            # Adiciona campos dinâmicos como write-only
            for key, field in dynamic_fields.items():
                self.fields[key] = field

    return DynamicRegistroProducaoSerializer, DynamicRegistroProducaoWriteSerializer


# Serializer padrão (fallback para culturas sem config)
RegistroProducaoSerializer = RegistroProducaoBaseSerializer


# ============================================================================
# HELPER PARA VIEWS OBTER SERIALIZER DINÂMICO
# ============================================================================


def campos_dinamicos_de(cultura_slug) -> tuple:
    """`(tem_campos, total)` — os campos dinamicos declarados para a cultura.

    MEDIDO 2026-10-05. Este facto era **invisivel**. `get_culture_fields`
    devolve `[]` para uma cultura sem `fields` no `cultures-config.json`, e
    o `get_registro_producao_serializers` abaixo cai para os serializers
    base — sem aviso, sem `sem_dado`, sem nada no corpo da resposta.

    MEDIDO no mesmo dia: `fields` existe em **3 das 488** culturas. Ou seja,
    485 degradam em silencio para o schema generico, e o produtor ve campos
    que nao tem nada a ver com a cultura que escolheu, sem nenhuma pista de
    que o especifico nao existe.

    Isto e' a mesma doutrina do resto do projecto: a ausencia de um dado e'
    visivel, e nao se disfarca de campo generico. E' por isso que isto
    existe como funcao com nome em vez de ficar dentro do `if`.

    ## O QUE FALTA, E PORQUÊ NAO ESTÁ FEITO AQUI
    Tornar isto visivel **ao produtor** exige que a resposta da API carregue
    o facto — e a assinatura de `get_registro_producao_serializers` e' usada
    em 5 sitios (`production.py:41,44,111,166` e aqui). Mudar a assinatura
    parte callers que ninguem esta a mexer, e o texto que o produtor leria
    ("campos dinamicos por definir para esta cultura") e' decisao de produto,
    nao de engenharia.

    Deixar a funcao com nome e um teste que a exercita e' o que torna o
    proximo passo barato: quem o der precisa de uma linha, nao de
    redescobrir o mecanismo.
    """
    from .culture_config import get_culture_fields

    campos = get_culture_fields(cultura_slug) or []
    return bool(campos), len(campos)


def get_registro_producao_serializers(cultura_slug, user=None):
    """
    Retorna tupla (ReadSerializer, WriteSerializer) para uma cultura.
    Se não houver config, retorna os serializers base.
    Se user fornecido, aplica preferências do usuário.

    NOTA: a queda para os serializers base é **silenciosa** e hoje é
    documentada por `campos_dinamicos_de()` acima, não comunicada ao
    produtor. Ver a docfunction dela para o porquê.
    """
    from .culture_config import get_culture_fields

    if get_culture_fields(cultura_slug):
        return DynamicRegistroProducaoSerializerFactory(cultura_slug, user)
    return RegistroProducaoBaseSerializer, RegistroProducaoWriteSerializer


# ============================================================================
# RASTREABILIDADE & CUSTOS (Plano v2.0 — Semana 3-4)
# ============================================================================


class RastroItemSerializer(serializers.ModelSerializer):
    insumo_nome = serializers.CharField(source="insumo.nome", read_only=True)
    propriedade_nome = serializers.CharField(source="propriedade.nome", read_only=True)
    lote_semente = serializers.SerializerMethodField()

    def get_lote_semente(self, obj):
        lote = getattr(obj, "lote_semente", None)
        return LoteSementeSerializer(lote, context=self.context).data if lote else None

    # PERF: prefere o campo annotated (saldo_calculado, anexado por
    # RastroItemViewSet.with_saldo) e cai para a @property .saldo apenas quando o
    # queryset nao tem a anotacao. Antes o ModelSerializer usava a property
    # direto -> 2 aggregates por linha (107 queries numa pagina de 50).
    saldo = serializers.SerializerMethodField(read_only=True)
    vencido = serializers.BooleanField(read_only=True)
    dias_para_vencer = serializers.IntegerField(read_only=True, allow_null=True)

    def get_saldo(self, obj):
        valor = getattr(obj, "saldo_calculado", None)
        if valor is None:
            valor = obj.saldo
        return valor

    class Meta:
        model = RastroItem
        fields = [
            "id",
            "propriedade",
            "propriedade_nome",
            "insumo",
            "insumo_nome",
            "numero_lote",
            "numero_serie",
            "nf_entrada",
            "quantidade_recebida",
            "unidade",
            "data_recebimento",
            "fornecedor",
            "data_validade",
            "qr_code_hash",
            "observacao",
            "criado_em",
            "saldo",
            "vencido",
            "dias_para_vencer",
            "lote_semente",
        ]
        read_only_fields = [
            "id",
            "qr_code_hash",
            "criado_em",
            "saldo",
            "vencido",
            "dias_para_vencer",
        ]

    def validate_quantidade_recebida(self, value):
        if value <= 0:
            raise serializers.ValidationError("Quantidade deve ser maior que zero.")
        return value

    def validate_propriedade(self, value):
        request = self.context.get("request")
        if request and value.user != request.user:
            raise serializers.ValidationError("Propriedade não pertence ao usuário.")
        return value

    def validate(self, attrs):
        insumo = attrs.get("insumo")
        prop = attrs.get("propriedade") or (
            self.instance.propriedade if self.instance else None
        )
        if insumo and prop and insumo.propriedade_id != prop.id:
            raise serializers.ValidationError(
                {"insumo": "Insumo não pertence a esta propriedade."}
            )
        return attrs


class MovimentoEstoqueSerializer(serializers.ModelSerializer):
    rastro_lote = serializers.CharField(
        source="rastro_item.numero_lote", read_only=True
    )
    tipo_display = serializers.CharField(source="get_tipo_display", read_only=True)

    class Meta:
        model = MovimentoEstoque
        fields = [
            "id",
            "rastro_item",
            "rastro_lote",
            "tipo",
            "tipo_display",
            "quantidade",
            "data_movimento",
            "talhao",
            "funcionario",
            "nota_fiscal",
            "motivo",
            "criado_em",
        ]
        read_only_fields = ["id", "criado_em"]

    def validate_quantidade(self, value):
        if value <= 0:
            raise serializers.ValidationError(
                "Quantidade deve ser > 0 (direção é dada por tipo)."
            )
        return value


class RastreabilidadeSafraSerializer(serializers.ModelSerializer):
    insumo_nome = serializers.SerializerMethodField()
    talhao_nome = serializers.SerializerMethodField()

    class Meta:
        model = RastreabilidadeSafra
        fields = [
            "id",
            "safra",
            "aplicacao",
            "insumo",
            "rastro_item",
            "talhao",
            "quantidade_aplicada",
            "custo_unitario",
            "custo_total",
            "operacao",
            "data_aplicacao",
            "observacao",
            "criado_em",
            "insumo_nome",
            "talhao_nome",
        ]
        read_only_fields = [
            "id",
            "custo_total",
            "criado_em",
            "insumo_nome",
            "talhao_nome",
        ]

    def get_insumo_nome(self, obj):
        eff = obj.insumo_efetivo
        return eff.nome if eff else None

    def get_talhao_nome(self, obj):
        eff = obj.talhao_efetivo
        return eff.nome if eff else None

    def validate_quantidade_aplicada(self, value):
        if value <= 0:
            raise serializers.ValidationError("Quantidade deve ser maior que zero.")
        return value

    def validate_custo_unitario(self, value):
        if value < 0:
            raise serializers.ValidationError("Custo unitário não pode ser negativo.")
        return value

    def validate(self, attrs):
        if not attrs.get("aplicacao") and not attrs.get("insumo"):
            raise serializers.ValidationError("Informe aplicacao ou insumo.")
        if not attrs.get("aplicacao") and not attrs.get("talhao"):
            raise serializers.ValidationError("Informe aplicacao ou talhao.")
        return attrs


class CentroCustoSerializer(serializers.ModelSerializer):
    tipo_display = serializers.CharField(source="get_tipo_display", read_only=True)

    class Meta:
        model = CentroCusto
        fields = [
            "id",
            "propriedade",
            "nome",
            "descricao",
            "tipo",
            "tipo_display",
            "ativo",
        ]
        read_only_fields = ["id", "tipo_display"]

    def validate_propriedade(self, value):
        request = self.context.get("request")
        if request and value.user != request.user:
            raise serializers.ValidationError("Propriedade não pertence ao usuário.")
        return value


class CustoProducaoSerializer(serializers.ModelSerializer):
    safra_nome = serializers.CharField(source="safra.safra_nome", read_only=True)
    talhao_nome = serializers.CharField(
        source="talhao.nome", read_only=True, allow_null=True
    )

    class Meta:
        model = CustoProducao
        fields = [
            "id",
            "safra",
            "safra_nome",
            "talhao",
            "talhao_nome",
            "centro_custo",
            "insumos",
            "maquina",
            "mao_de_obra",
            "embalagem",
            "frete",
            "impostos",
            "outros",
            "custo_total",
            "custo_por_ha",
            "custo_por_saca",
            "receita",
            "lucro",
            "margem",
            "observacao",
            "criado_em",
            "atualizado_em",
        ]
        read_only_fields = [
            "id",
            "custo_total",
            "custo_por_ha",
            "custo_por_saca",
            "lucro",
            "margem",
            "criado_em",
            "atualizado_em",
        ]


class LancamentoDetalhadoSerializer(serializers.ModelSerializer):
    categoria_display = serializers.CharField(
        source="get_categoria_detalhada_display", read_only=True
    )
    propriedade_nome = serializers.SerializerMethodField()

    class Meta:
        model = LancamentoDetalhado
        fields = [
            "id",
            "lancamento",
            "_propriedade",
            "propriedade_nome",
            "centro_custo",
            "safra",
            "talhao",
            "categoria_detalhada",
            "categoria_display",
            "valor_rateado",
            "observacao",
            "criado_em",
        ]
        read_only_fields = ["id", "categoria_display", "propriedade_nome", "criado_em"]

    def get_propriedade_nome(self, obj):
        p = obj.propriedade
        return p.nome if p else None

    def validate_valor_rateado(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError("Valor rateado não pode ser negativo.")
        return value


# ============================================================================
# BANCO & PUSH (S17)
# ============================================================================


class ContaBancariaSerializer(serializers.ModelSerializer):
    propriedade_nome = serializers.CharField(source="propriedade.nome", read_only=True)
    movimentacoes_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = ContaBancaria
        fields = [
            "id",
            "propriedade",
            "propriedade_nome",
            "banco",
            "agencia",
            "conta",
            "digito",
            "tipo",
            "saldo_atual",
            "ativa",
            "movimentacoes_count",
        ]
        read_only_fields = ["id", "saldo_atual", "movimentacoes_count"]

    def validate_tipo(self, value):
        if value not in dict(ContaBancaria._meta.get_field("tipo").choices):
            raise serializers.ValidationError("Tipo de conta inválido.")
        return value


class MovimentacaoBancariaSerializer(serializers.ModelSerializer):
    conta_nome = serializers.CharField(source="conta.__str__", read_only=True)

    class Meta:
        model = MovimentacaoBancaria
        fields = [
            "id",
            "conta",
            "conta_nome",
            "data",
            "descricao",
            "valor",
            "tipo",
            "categoria",
            "documento",
            "conciliado",
            "data_conciliacao",
            "hash_unico",
            "criado_em",
        ]
        read_only_fields = ["id", "hash_unico", "criado_em"]

    def validate_valor(self, value):
        if value <= 0:
            raise serializers.ValidationError("Valor deve ser maior que zero.")
        return value


class ParcelamentoSerializer(serializers.ModelSerializer):
    propriedade_nome = serializers.CharField(source="propriedade.nome", read_only=True)
    lancamento_info = serializers.SerializerMethodField()
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Parcelamento
        fields = [
            "id",
            "propriedade",
            "propriedade_nome",
            "lancamento",
            "lancamento_info",
            "tipo",
            "numero",
            "total_parcelas",
            "valor_total",
            "valor_parcela",
            "data_vencimento",
            "status",
            "status_display",
            "juros_mes",
            "multa_atraso",
            "data_pagamento",
            "data_cancelamento",
            "observacao",
        ]
        read_only_fields = ["id"]

    def get_lancamento_info(self, obj):
        if obj.lancamento:
            return f"{obj.lancamento.get_tipo_display()} - {obj.lancamento.valor}"
        return None

    def validate_valor_total(self, value):
        if value <= 0:
            raise serializers.ValidationError("Valor total deve ser maior que zero.")
        return value

    def validate_valor_parcela(self, value):
        if value <= 0:
            raise serializers.ValidationError(
                "Valor da parcela deve ser maior que zero."
            )
        return value


class ConciliacaoBancariaSerializer(serializers.ModelSerializer):
    conta_nome = serializers.CharField(source="conta.__str__", read_only=True)
    criado_por_nome = serializers.CharField(
        source="criado_por.username", read_only=True, allow_null=True
    )
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = ConciliacaoBancaria
        fields = [
            "id",
            "conta",
            "conta_nome",
            "data_inicio",
            "data_fim",
            "saldo_sistema_inicio",
            "saldo_banco_inicio",
            "saldo_sistema_fim",
            "saldo_banco_fim",
            "diferenca",
            "status",
            "status_display",
            "criado_em",
            "fechada_em",
            "criado_por",
            "criado_por_nome",
            "observacao",
        ]
        read_only_fields = ["id", "criado_em", "fechada_em", "diferenca"]

    def validate(self, attrs):
        if attrs.get("data_fim") and attrs.get("data_inicio"):
            if attrs["data_fim"] < attrs["data_inicio"]:
                raise serializers.ValidationError(
                    "Data fim não pode ser anterior à data início."
                )
        return attrs


class PushSubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PushSubscription
        fields = ["id", "endpoint", "p256dh", "auth", "ativa", "criada_em"]
        read_only_fields = ["id", "criada_em"]


class NotificacaoTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificacaoTemplate
        fields = [
            "id",
            "nome",
            "titulo",
            "mensagem",
            "nivel",
            "canais",
            "ativa",
            "variaveis",
        ]
        read_only_fields = ["id"]


# ============================================================================
# VRA & ZARC (S16)
# ============================================================================


class PrescricaoVRA_Serializer(serializers.ModelSerializer):
    safra_nome = serializers.CharField(source="safra.safra_nome", read_only=True)
    talhao_nome = serializers.CharField(source="talhao.nome", read_only=True)
    cultura_nome = serializers.CharField(source="cultura.nome", read_only=True)
    insumo_nome = serializers.CharField(
        source="insumo.nome", read_only=True, allow_null=True
    )

    # --- A2: a procedencia, legivel por API -------------------------------
    #
    # Estas tres sao properties do modelo, nao campos. Nao e' um esquecimento:
    # sao a leitura das duas pontas (prevista e realizada), e por isso nunca
    # podem divergir do que esta gravado. Se um dia forem campos, ha de ser
    # porque o desfecho parou de mudar — e isso e' uma decisao, nao um bugfix.
    #
    # `fonte_dado_erro` viaja ao lado do `erro_percentual` **de proposito**: um
    # `null` sem o carimbo nao diz ao cliente se falta a previsao, se falta a
    # colheita, ou se a produtividade foi zero e o erro relativo e' indefinivel.
    # Sao tres situacoes que o cliente tem de tratar de maneira diferente.
    #
    # Ver `tests/test_prescricao_proveniencia.py`, em especial
    # `test_fonte_dado_erro_concorda_sempre_com_erro_percentual`.
    produtividade_realizada = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True, allow_null=True
    )
    erro_percentual = serializers.FloatField(read_only=True, allow_null=True)
    fonte_dado_erro = serializers.CharField(read_only=True)

    class Meta:
        model = PrescricaoVRA
        fields = [
            "id",
            "safra",
            "safra_nome",
            "talhao",
            "talhao_nome",
            "cultura",
            "cultura_nome",
            "tipo_insumo",
            "insumo",
            "insumo_nome",
            "dose_ha",
            "unidade",
            "grade_geojson",
            "iso_xml",
            "arquivo_iso",
            # A2 — o lado da previsao e da evidencia
            "produtividade_esperada",
            "contexto_recomendacao",
            "versao_analise",
            # A2 — o lado do desfecho, lido da safra
            "produtividade_realizada",
            "erro_percentual",
            "fonte_dado_erro",
            "criado_em",
            "atualizado_em",
        ]
        read_only_fields = [
            "id",
            "iso_xml",
            "arquivo_iso",
            "criado_em",
            "atualizado_em",
        ]

    def validate_dose_ha(self, value):
        if value <= 0:
            raise serializers.ValidationError(
                "Dose por hectare deve ser maior que zero."
            )
        return value


class ZARC_Serializer(serializers.ModelSerializer):
    cultura_nome = serializers.CharField(source="cultura.nome", read_only=True)

    class Meta:
        model = ZARC
        fields = [
            "id",
            "cultura",
            "cultura_nome",
            "uf",
            "municipio",
            "data_inicio_plantio",
            "data_fim_plantio",
            "ciclo_dias",
            "risco_climatico",
        ]
        read_only_fields = ["id"]

    def validate(self, attrs):
        if attrs.get("data_inicio_plantio") and attrs.get("data_fim_plantio"):
            if attrs["data_fim_plantio"] < attrs["data_inicio_plantio"]:
                raise serializers.ValidationError(
                    "Data fim não pode ser anterior à data início."
                )
        return attrs


class MonitoramentoPraga_Serializer(serializers.ModelSerializer):
    talhao_nome = serializers.CharField(source="talhao.nome", read_only=True)
    cultura_nome = serializers.CharField(
        source="cultura.nome", read_only=True, allow_null=True
    )
    acima_controle = serializers.BooleanField(read_only=True)

    class Meta:
        model = MonitoramentoPraga
        fields = [
            "id",
            "talhao",
            "talhao_nome",
            "cultura",
            "cultura_nome",
            "safra",
            "data",
            "praga",
            "nivel_infestacao",
            "nivel_controle",
            "acao_recomendada",
            "foto",
            "acima_controle",
            "criado_em",
        ]
        read_only_fields = ["id", "criado_em"]

    def validate_nivel_infestacao(self, value):
        if value < 0:
            raise serializers.ValidationError(
                "Nível de infestação não pode ser negativo."
            )
        return value


class RacaoSerializer(serializers.ModelSerializer):
    propriedade_nome = serializers.CharField(source="propriedade.nome", read_only=True)

    class Meta:
        model = Racao
        fields = [
            "id",
            "propriedade",
            "propriedade_nome",
            "nome",
            "tipo",
            "quantidade",
            "fornecedor",
            "data_validade",
            "especie_alvo",
            "fase",
            "composicao",
            "custo_kg",
            "criado_em",
        ]
        read_only_fields = ["id", "criado_em"]

    def validate_quantidade(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError("Quantidade não pode ser negativa.")
        return value

    def validate_custo_kg(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError("Custo por kg não pode ser negativo.")
        return value


class Experimento_Serializer(serializers.ModelSerializer):
    talhao_a_nome = serializers.CharField(
        source="talhao_a.nome", read_only=True, default=None
    )
    talhao_b_nome = serializers.CharField(
        source="talhao_b.nome", read_only=True, default=None
    )
    total_medicoes = serializers.IntegerField(read_only=True)

    class Meta:
        model = Experimento
        fields = [
            "id",
            "uid",
            "propriedade",
            "safra",
            "cultura",
            "nome",
            "hypothesis",
            "variavel",
            "tratamento_a",
            "tratamento_b",
            "talhao_a",
            "talhao_a_nome",
            "talhao_b",
            "talhao_b_nome",
            "metricas",
            "significance_level",
            "status",
            "data_inicio",
            "data_fim",
            "contexto_inicial",
            "versao_analise",
            "total_medicoes",
            "criado_em",
            "atualizado_em",
        ]
        read_only_fields = ["criado_em", "atualizado_em"]

    def validate_significance_level(self, value):
        if not 0 < value < 1:
            raise serializers.ValidationError(
                "A barra de significancia tem de estar entre 0 e 1 (ex.: 0.05)."
            )
        return value

    def validate_metricas(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("metricas tem de ser uma lista.")
        return value


class MedicaoExperimental_Serializer(serializers.ModelSerializer):
    class Meta:
        model = MedicaoExperimental
        fields = [
            "id",
            "uid",
            "experimento",
            "prescricao",
            "tratamento",
            "talhao",
            "dados",
            "contexto",
            "fonte_dado",
            "registado_em",
            "sincronizado_em",
        ]
        # `sincronizado_em` e' do servidor — o cliente nao pode fingir que a
        # medicao chegou antes de chegar. `registado_em` e' do cliente, e e'
        # read-only por ser um DateTimeField normal: se fosse auto_now_add,
        # perder-se-ia a condicao em que o produtor mediu, que e' o que explica
        # o resultado.
        read_only_fields = ["sincronizado_em"]

    def validate_registado_em(self, value):
        """Nao aceitar uma medicao no futuro.

        O relogio do cliente pode estar errado — e o produtor que muda a hora
        no aparelho. Mas um `registado_em` muito no futuro é sempre um bug de
        sincronizacao, e gravá-lo significa que a análise vai comparar uma
        medição que "aconteceu depois da colheita".
        """
        if value and value > timezone.now():
            raise serializers.ValidationError(
                "registado_em esta no futuro. O relogio do aparelho esta errado?"
            )
        return value

    def validate(self, attrs):
        """A ligacao `prescricao` tem de ser do mesmo produtor.

        Sem isto, o A2b e' um vector: um produtor envia o `prescricao_id` de
        outro e a medicao entra na base alheia — lendo depois a proveniencia
        que o §4.3 promete proteger.

        MEDIDO: a primeira versao disto comparava `request.user` com o dono do
        **experimento**. Passava sempre, porque o experimento recem-criado e'
        do proprio remetente — o check nao media nada. O que tem de ser
        verificado e' o dono da **prescricao**, que vem de fora. O
        `test_uma_prescricao_alheia_e_recusada` e' o que apanhou.
        """
        request = self.context.get("request")
        if request is None:
            return attrs

        prescricao = attrs.get("prescricao") or getattr(
            self.instance, "prescricao", None
        )
        if prescricao is None:
            return attrs

        # Percorre a cadeia ate ao dono. `Safra.talhao` e' opcional e
        # `Safra.propriedade` e' obrigatoria, por isso o corte e' no `propriedade`.
        dono = prescricao.safra.propriedade.user_id if prescricao.safra_id else None
        if dono is None or dono != request.user.id:
            raise serializers.ValidationError(
                {"prescricao": "Essa prescricao nao e' tua."}
            )
        return attrs


class IAAlertaProativoSerializer(serializers.ModelSerializer):
    """G-05/G-06: expõe o alerta já gravado (visualização de produtor)."""

    nivel_display = serializers.CharField(source="get_nivel_display", read_only=True)

    class Meta:
        model = IAAlertaProativo
        fields = [
            "id",
            "origem",
            "nivel",
            "nivel_display",
            "titulo",
            "mensagem",
            "estado",
            "regra",
            "evidencia",
            "visto_em",
            "criado_em",
        ]
        read_only_fields = ["id", "fingerprint", "criado_em"]

    def validate(self, attrs):
        request = self.context.get("request")
        if request is not None and hasattr(self, "instance"):
            if self.instance.user_id != request.user_id:
                raise serializers.ValidationError(
                    {"non_field_errors": ["Esta operação não é permitida."]}
                )
        return attrs


class ViveiroSerializer(serializers.ModelSerializer):
    """G-04: estrutura que produz mudas."""

    class Meta:
        model = Viveiro
        fields = ["id", "nome", "tipo", "protocolo", "fonte_dado", "propriedade"]
        read_only_fields = ["id", "criado_em"]


class LoteMudaSerializer(serializers.ModelSerializer):
    """G-04: lote de muda clonal. Datas são NULAS até acontecer."""

    cultura_nome = serializers.CharField(source="cultura.nome", read_only=True)
    talhao_destino_id = serializers.IntegerField(
        source="talhao_destino.id", read_only=True
    )
    viveiro_nome = serializers.CharField(source="viveiro.nome", read_only=True)

    def validate(self, attrs):
        """Talhão de destino deve pertencer à mesma propriedade do viveiro.

        Caso contrário, a muda vincula um talhão alheio — vetor de escrita
        na base alheia (mesmo risco do `talhao_alheio_recusado` em
        PrescricaoVRA).
        """
        talhao_destino = attrs.get("talhao_destino")
        viveiro = attrs.get("viveiro")
        if (
            talhao_destino is not None
            and viveiro is not None
            and talhao_destino.propriedade_id != viveiro.propriedade_id
        ):
            raise serializers.ValidationError(
                {
                    "talhao_destino": "O talhão de destino não pertence à propriedade do viveiro.",
                }
            )
        return attrs

    class Meta:
        model = LoteMuda
        fields = [
            "id",
            "origem_matriz",
            "qtd_produzida",
            "qtd_expedida",
            "data_repique",
            "data_aclimatacao",
            "data_expedicao",
            "sobrevivencia_pct",
            "observacao",
            "cultura",
            "cultura_nome",
            "talhao_destino",
            "talhao_destino_id",
            "viveiro",
            "viveiro_nome",
            "criado_em",
        ]
        read_only_fields = ["id", "criado_em"]


class MixPastagemSerializer(serializers.ModelSerializer):
    """G-06: mix de pastagem. `pct` soma <= 100; taxa/data NULAS até declaração."""

    pct_nao_atribuido = serializers.DecimalField(
        max_digits=5, decimal_places=2, read_only=True
    )
    cultura_nome = serializers.CharField(source="cultura.nome", read_only=True)

    class Meta:
        model = MixPastagem
        fields = [
            "id",
            "pct",
            "pct_nao_atribuido",
            "taxa_semeadura_kg_ha",
            "data_semeadura",
            "fonte_dado",
            "criado_em",
            "cultura",
            "cultura_nome",
            "piquete",
        ]
        read_only_fields = ["id", "criado_em"]

    def validate(self, attrs):
        """`pct` deve ser 0-100 e soma com existentes nao passa 100."""
        from decimal import Decimal as D
        from django.core.exceptions import ValidationError as DjangoValidationError
        from django.db.models import Sum

        piquete = attrs.get("piquete")
        pct = attrs.get("pct")
        if piquete is not None and pct is not None:
            try:
                pct_dec = D(str(pct))
            except Exception:
                raise DjangoValidationError({"pct": "Valor inválido para percentual."})
            if pct_dec < 0 or pct_dec > 100:
                raise DjangoValidationError(
                    {"pct": "O percentual deve estar entre 0% e 100%."}
                )
            soma_outros = piquete.mixes.aggregate(s=Sum("pct"))["s"] or D("0")
            soma_total = soma_outros + pct_dec
            if soma_total > 100:
                raise DjangoValidationError(
                    {"pct": f"Soma do mix ({soma_total}%) passa de 100%."}
                )
        return attrs


class EnsaioCultivarSerializer(serializers.ModelSerializer):
    """G-03: ensaio de cultivar. `user` e `propriedade` são OBRIGATÓRIOS."""

    class Meta:
        model = EnsaioCultivar
        fields = [
            "id",
            "uid",
            "nome",
            "data_plantio",
            "status",
            "fonte_dado",
            "criado_em",
            "cultura",
            "propriedade",
            "safra",
            "talhao",
            "testemunha",
            "user",
        ]
        read_only_fields = ["id", "uid", "criado_em", "user"]


class FaixaEnsaioSerializer(serializers.ModelSerializer):
    """G-03: uma faixa/repetição de medida."""

    cultivar_nome = serializers.CharField(
        source="cultivar.nome_comercial", read_only=True
    )

    class Meta:
        model = FaixaEnsaio
        fields = [
            "id",
            "repeticao",
            "area_m2",
            "produtividade_sc_ha",
            "umidade_pct",
            "registada_em",
            "sincronizado_em",
            "cultivar",
            "cultivar_nome",
            "ensaio",
        ]
        read_only_fields = ["id", "sincronizado_em"]


class EnsaioRankingSerializer(serializers.Serializer):
    """G-03: linha de ranking (sem BD, chamada pela view anterior a
    `ranking_ensaio`). Ordena por média; Nones vão por último."""

    cultivar_id = serializers.IntegerField()
    media_sc_ha = serializers.FloatField(allow_null=True)
    delta_pct = serializers.FloatField(allow_null=True)

    class Meta:
        fields = ["cultivar_id", "media_sc_ha", "delta_pct"]


# ============================================================================
# G-01..G-06 — NOVO CORE PLANO-CORREÇÃO
# ============================================================================
# Campos explícitos, validação estrita e escopo por dono (não por
# "browse" aberto). Cada viewset respeita `piquete__propriedade__user` para
# leitura e `perform_create` recusa escrita em propriedade alheia (403).
# ============================================================================


class RastroItemLoteSementeSerializer(serializers.ModelSerializer):
    """Lote de semente aninhado no RastroItem - apenas o essencial."""

    cultivar_nome = serializers.CharField(
        source="cultivar.nome_comercial", read_only=True
    )

    class Meta:
        model = LoteSemente
        fields = ["id", "cultivar_nome", "germinacao_pct", "vigor_pct"]


class CultivarSerializer(serializers.ModelSerializer):
    """G-01: cultivar. `cultura` é OBRIGATÓRIO no POST (catálogo)."""

    class Meta:
        model = Cultivar
        fields = [
            "id",
            "nome_comercial",
            "obtentor",
            "evento",
            "tecnica",
            "grupo_maturacao",
            "ciclo_min",
            "ciclo_max",
            "habito",
            "densidade_mil_plantas_ha",
            "tol_seca",
            "tol_sal",
            "resistencias",
            "fonte_dado",
            "ativo",
            "cultura",
        ]
        read_only_fields = ["id"]


class LoteSementeSerializer(serializers.ModelSerializer):
    """G-02: laudo de qualidade do lote. `rastro` é OBRIGATÓRIO no POST."""

    cultivar_nome = serializers.CharField(
        source="cultivar.nome_comercial", read_only=True
    )

    class Meta:
        model = LoteSemente
        fields = [
            "id",
            "categoria",
            "germinacao_pct",
            "vigor_pct",
            "pureza_pct",
            "peneira",
            "tsi_produto",
            "tsi_dose_ml_100kg",
            "tsi_funcao",
            "tsi_prestador",
            "tsi_data",
            "revestimento",
            "fonte_dado",
            "cultivar",
            "cultivar_nome",
            "rastro",
        ]
        read_only_fields = ["id"]
