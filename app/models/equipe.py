from datetime import timedelta

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

from app.validators import validate_json_safe

CARGOS = [
    # Gestão
    ("GERENTE", "Gerente de Fazenda"),
    ("CAPATAZ", "Capataz / Encarregado"),
    ("SUPERVISOR_AGRICOLA", "Supervisor Agrícola"),
    ("SUPERVISOR_PECUARIA", "Supervisor de Pecuária"),
    ("ADMIN", "Administrativo"),
    ("AUX_ADMIN", "Auxiliar Administrativo"),
    ("CONTADOR_RURAL", "Contador Rural"),
    ("COMPRADOR_RURAL", "Comprador Rural"),
    ("VENDEDOR_INSUMOS", "Vendedor de Insumos"),
    # Operação Campo
    ("TRATORISTA", "Tratorista"),
    ("OPERADOR_COLHEITADEIRA", "Operador de Colheitadeira"),
    ("OPERADOR_PULVERIZADOR", "Operador de Pulverizador"),
    ("OPERADOR_PLANTADEIRA", "Operador de Plantadeira"),
    ("OPERADOR_ROCADEIRA", "Operador de Roçadeira"),
    ("OPERADOR_MOTOSSERRA", "Operador de Motosserra"),
    ("OPERADOR_IRRIGACAO", "Operador de Irrigação"),
    ("TEC_IRRIGACAO", "Técnico em Irrigação"),
    ("AUX_CAMPO", "Auxiliar de Campo"),
    ("RURICOLA", "Rurícola"),
    ("DIARISTA", "Diarista Rural"),
    ("JARDINEIRO", "Jardineiro"),
    ("VIVEIRISTA", "Viveirista"),
    # Mecânica / Manutenção
    ("MECANICO_AGRICOLA", "Mecânico Agrícola"),
    ("MECANICO_PESADOS", "Mecânico de Máquinas Pesadas"),
    ("MECANICO_CAMINHAO", "Mecânico de Caminhão"),
    ("ELETRICISTA_RURAL", "Eletricista Rural"),
    ("SOLDADOR", "Soldador"),
    ("BORRACHEIRO", "Borracheiro"),
    ("LUBRIFICADOR", "Lubrificador"),
    ("LAVADOR_MAQUINAS", "Lavador de Máquinas"),
    ("CHEFE_OFICINA", "Chefe de Oficina"),
    ("AUX_OFICINA", "Auxiliar de Oficina"),
    ("CALDEIREIRO", "Caldeireiro"),
    # Logística / Transporte
    ("MOTORISTA", "Motorista"),
    ("MOTORISTA_CAMINHAO", "Motorista de Caminhão"),
    ("OPERADOR_MUNCK", "Operador de Caminhão Munck"),
    ("OPERADOR_EMPILHADEIRA", "Operador de Empilhadeira"),
    ("CONFERENTE", "Conferente"),
    ("AUX_LOGISTICA", "Auxiliar de Logística"),
    ("OPERADOR_ARMAZEM", "Operador de Armazém"),
    ("CLASSIFICADOR_GRAOS", "Classificador de Grãos"),
    ("OPERADOR_SECADOR", "Operador de Secador"),
    ("OPERADOR_BENEFICIAMENTO", "Operador de Beneficiamento"),
    ("OPERADOR_SILO", "Operador de Silo"),
    # Pecuária
    ("VAQUEIRO", "Vaqueiro"),
    ("PEAO", "Peão"),
    ("ORDENHADOR", "Ordenhador"),
    ("INSEMINADOR", "Inseminador"),
    ("AUX_PECUARIA", "Auxiliar de Pecuária"),
    ("TRATADOR", "Tratador de Animais"),
    ("TOSQUIADOR", "Tosquiador"),
    ("CASQUEADOR", "Casqueador"),
    ("QUEIJEIRO", "Queijeiro"),
    ("VETERINARIO", "Veterinário"),
    ("ZOOTECNISTA", "Zootecnista"),
    ("TEC_NUTRICAO", "Técnico em Nutrição Animal"),
    ("TEC_PASTAGEM", "Técnico em Pastagem"),
    ("AUX_CONFINAMENTO", "Auxiliar de Confinamento"),
    ("OPERADOR_CONFINAMENTO", "Operador de Confinamento"),
    ("AUX_FABRICA_RACAO", "Auxiliar de Fábrica de Ração"),
    ("OPERADOR_FABRICA_RACAO", "Operador de Fábrica de Ração"),
    ("DOMADOR", "Domador"),
    ("FERRADOR", "Ferreiro / Casqueamento"),
    # Apicultura / Outros
    ("APICULTOR", "Apicultor"),
    ("AUX_APICULTURA", "Auxiliar de Apicultura"),
    # Tecnologia / Precisão
    ("OPERADOR_DRONE", "Operador de Drone Agrícola"),
    ("PILOTO_AGRICOLA", "Piloto Agrícola"),
    ("OPERADOR_GPS", "Operador de GPS Agrícola"),
    ("AGRIMENSOR", "Agrimensor"),
    ("TOPOGRAFO", "Topógrafo"),
    ("TEC_SEGURANCA", "Técnico em Segurança do Trabalho"),
    ("TEC_MEIO_AMBIENTE", "Técnico em Meio Ambiente"),
    ("ENG_AMBIENTAL", "Engenheiro Ambiental"),
    ("ENG_FLORESTAL", "Engenheiro Florestal"),
    ("TEC_FLORESTAL", "Técnico Florestal"),
    ("BIOLOGO", "Biólogo"),
    # Construção Rural
    ("CARPINTEIRO_RURAL", "Carpinteiro Rural"),
    ("PEDREIRO_RURAL", "Pedreiro Rural"),
    ("PINTOR", "Pintor"),
    ("ENCANADOR_RURAL", "Encanador Rural"),
    # Operação Pesada
    ("OPERADOR_ESTEIRA", "Operador de Trator de Esteira"),
    ("OPERADOR_ESCAVADEIRA", "Operador de Escavadeira"),
    ("OPERADOR_PA_CARREGADEIRA", "Operador de Pá Carregadeira"),
    ("OPERADOR_RETRO", "Operador de Retroescavadeira"),
    # Gerais
    ("TECNICO", "Técnico Agrícola"),
    ("TECNICO_AGROPECUARIA", "Técnico em Agropecuária"),
    ("ENGENHEIRO", "Engenheiro Agrônomo"),
    ("GERENTE_FAZENDA", "Gerente de Fazenda (Sênior)"),
    ("FISCAL_CAMPO", "Fiscal de Campo"),
    ("ENCARREGADO_TURMA", "Encarregado de Turma"),
    ("AUX_SERVICOS_GERAIS", "Auxiliar de Serviços Gerais"),
    ("SERVICO", "Serviços Gerais"),
    ("CASEIRO", "Caseiro"),
    ("COZINHEIRO_RURAL", "Cozinheiro Rural"),
    ("SEGURANCA_RURAL", "Segurança Rural"),
    ("VIGIA", "Vigia"),
    ("AUX_LIMPEZA", "Auxiliar de Limpeza Rural"),
    ("ALMOXARIFE", "Almoxarife"),
    ("ESTOQUISTA", "Estoquista"),
    ("ESTOQUISTA_PECAS", "Estoquista de Peças"),
    ("AUX_ARMAZEM", "Auxiliar de Armazém"),
    ("AUX_SILAGEM", "Auxiliar de Silagem"),
    ("OPERADOR_SILAGEM", "Operador de Silagem"),
    ("COLETOR_SEMENTES", "Coletor de Sementes"),
    ("OPERADOR_VIVEIRO", "Operador de Viveiro"),
    # Apontamento / liderança operacional
    ("APONTADOR_RURAL", "Apontador Rural"),
    ("FEITOR", "Feitor"),
    ("LIDER_COLHEITA", "Líder de Colheita"),
    ("AMOSTRADOR_SOLO", "Amostrador de Solo"),
    # Oficina (auxiliares)
    ("AJUDANTE_MECANICO", "Ajudante de Mecânico"),
    ("AUX_ELETRICISTA", "Auxiliar de Eletricista"),
    # Culturas especiais
    ("HORTICULTOR", "Horticultor"),
    ("FRUTICULTOR", "Fruticultor"),
    ("PODADOR", "Podador"),
    # Máquinas (faltantes)
    ("OPERADOR_GRADE", "Operador de Grade Aradora"),
    # Apoio técnico
    ("AUX_VETERINARIO", "Auxiliar de Veterinário"),
    ("AUX_TOPOGRAFIA", "Auxiliar de Topografia"),
    ("OUTRO", "Outro"),
]


# Profissão -> área operacional (roteamento de tarefas e filtro do trabalhador).
# Sem correspondência = GERAL (todos veem).
CARGO_AREA = {
    # MECÂNICA
    "MECANICO_AGRICOLA": "MECANICA",
    "MECANICO_PESADOS": "MECANICA",
    "MECANICO_CAMINHAO": "MECANICA",
    "ELETRICISTA_RURAL": "MECANICA",
    "SOLDADOR": "MECANICA",
    "BORRACHEIRO": "MECANICA",
    "LUBRIFICADOR": "MECANICA",
    "LAVADOR_MAQUINAS": "MECANICA",
    "CHEFE_OFICINA": "MECANICA",
    "AUX_OFICINA": "MECANICA",
    "CALDEIREIRO": "MECANICA",
    "AJUDANTE_MECANICO": "MECANICA",
    "AUX_ELETRICISTA": "MECANICA",
    # CAMPO
    "TRATORISTA": "CAMPO",
    "OPERADOR_COLHEITADEIRA": "CAMPO",
    "OPERADOR_PULVERIZADOR": "CAMPO",
    "OPERADOR_PLANTADEIRA": "CAMPO",
    "OPERADOR_ROCADEIRA": "CAMPO",
    "OPERADOR_MOTOSSERRA": "CAMPO",
    "OPERADOR_IRRIGACAO": "CAMPO",
    "TEC_IRRIGACAO": "CAMPO",
    "AUX_CAMPO": "CAMPO",
    "RURICOLA": "CAMPO",
    "DIARISTA": "CAMPO",
    "OPERADOR_ESTEIRA": "CAMPO",
    "OPERADOR_ESCAVADEIRA": "CAMPO",
    "OPERADOR_PA_CARREGADEIRA": "CAMPO",
    "OPERADOR_RETRO": "CAMPO",
    "OPERADOR_GRADE": "CAMPO",
    "FISCAL_CAMPO": "CAMPO",
    "ENCARREGADO_TURMA": "CAMPO",
    "APONTADOR_RURAL": "CAMPO",
    "FEITOR": "CAMPO",
    "LIDER_COLHEITA": "CAMPO",
    "AMOSTRADOR_SOLO": "CAMPO",
    "HORTICULTOR": "CAMPO",
    "FRUTICULTOR": "CAMPO",
    "PODADOR": "CAMPO",
    "JARDINEIRO": "CAMPO",
    "VIVEIRISTA": "CAMPO",
    "COLETOR_SEMENTES": "CAMPO",
    "OPERADOR_VIVEIRO": "CAMPO",
    "AUX_SILAGEM": "CAMPO",
    "OPERADOR_SILAGEM": "CAMPO",
    "MOTORISTA": "CAMPO",
    "MOTORISTA_CAMINHAO": "CAMPO",
    "OPERADOR_MUNCK": "CAMPO",
    "OPERADOR_EMPILHADEIRA": "CAMPO",
    # PECUÁRIA
    "VAQUEIRO": "PECUARIA",
    "PEAO": "PECUARIA",
    "ORDENHADOR": "PECUARIA",
    "INSEMINADOR": "PECUARIA",
    "AUX_PECUARIA": "PECUARIA",
    "TRATADOR": "PECUARIA",
    "TOSQUIADOR": "PECUARIA",
    "CASQUEADOR": "PECUARIA",
    "QUEIJEIRO": "PECUARIA",
    "VETERINARIO": "PECUARIA",
    "ZOOTECNISTA": "PECUARIA",
    "TEC_NUTRICAO": "PECUARIA",
    "TEC_PASTAGEM": "PECUARIA",
    "AUX_CONFINAMENTO": "PECUARIA",
    "OPERADOR_CONFINAMENTO": "PECUARIA",
    "AUX_FABRICA_RACAO": "PECUARIA",
    "OPERADOR_FABRICA_RACAO": "PECUARIA",
    "DOMADOR": "PECUARIA",
    "FERRADOR": "PECUARIA",
    "AUX_VETERINARIO": "PECUARIA",
    "APICULTOR": "PECUARIA",
    "AUX_APICULTURA": "PECUARIA",
    "SUPERVISOR_PECUARIA": "PECUARIA",
    # ESTOQUE
    "ALMOXARIFE": "ESTOQUE",
    "ESTOQUISTA": "ESTOQUE",
    "ESTOQUISTA_PECAS": "ESTOQUE",
    "AUX_ARMAZEM": "ESTOQUE",
    "OPERADOR_ARMAZEM": "ESTOQUE",
    "CONFERENTE": "ESTOQUE",
    "AUX_LOGISTICA": "ESTOQUE",
    "CLASSIFICADOR_GRAOS": "ESTOQUE",
    "OPERADOR_SECADOR": "ESTOQUE",
    "OPERADOR_BENEFICIAMENTO": "ESTOQUE",
    "OPERADOR_SILO": "ESTOQUE",
    # ADMIN
    "GERENTE": "ADMIN",
    "GERENTE_FAZENDA": "ADMIN",
    "CAPATAZ": "ADMIN",
    "ADMIN": "ADMIN",
    "AUX_ADMIN": "ADMIN",
    "COMPRADOR_RURAL": "ADMIN",
    "VENDEDOR_INSUMOS": "ADMIN",
    "AUX_SERVICOS_GERAIS": "ADMIN",
    "SERVICO": "ADMIN",
    "CASEIRO": "ADMIN",
    "COZINHEIRO_RURAL": "ADMIN",
    "SEGURANCA_RURAL": "ADMIN",
    "VIGIA": "ADMIN",
    "AUX_LIMPEZA": "ADMIN",
    # AGRONOMIA
    "ENGENHEIRO": "AGRONOMIA",
    "TECNICO": "AGRONOMIA",
    "TECNICO_AGROPECUARIA": "AGRONOMIA",
    "SUPERVISOR_AGRICOLA": "AGRONOMIA",
    "OPERADOR_DRONE": "AGRONOMIA",
    "PILOTO_AGRICOLA": "AGRONOMIA",
    "OPERADOR_GPS": "AGRONOMIA",
    "AGRIMENSOR": "AGRONOMIA",
    "TOPOGRAFO": "AGRONOMIA",
    "AUX_TOPOGRAFIA": "AGRONOMIA",
    "TEC_SEGURANCA": "AGRONOMIA",
    "TEC_MEIO_AMBIENTE": "AGRONOMIA",
    "ENG_AMBIENTAL": "AGRONOMIA",
    "ENG_FLORESTAL": "AGRONOMIA",
    "TEC_FLORESTAL": "AGRONOMIA",
    "BIOLOGO": "AGRONOMIA",
    # FINANCEIRO
    "CONTADOR_RURAL": "FINANCEIRO",
    # GERAL (infraestrutura e apoio geral)
    "CARPINTEIRO_RURAL": "GERAL",
    "PEDREIRO_RURAL": "GERAL",
    "PINTOR": "GERAL",
    "ENCANADOR_RURAL": "GERAL",
}


def area_do_cargo(cargo):
    """Área operacional de um cargo (GERAL se desconhecido)."""
    return CARGO_AREA.get((cargo or "").upper(), "GERAL")


class Funcionario(models.Model):
    propriedade = models.ForeignKey(
        "Propriedade", on_delete=models.CASCADE, related_name="funcionarios"
    )
    user = models.OneToOneField(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="funcionario",
    )
    nome = models.CharField(max_length=150)
    cargo = models.CharField(max_length=30, choices=CARGOS)
    salario = models.DecimalField(max_digits=8, decimal_places=2)
    data_admissao = models.DateField()
    data_demissao = models.DateField(null=True, blank=True)
    telefone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    ativo = models.BooleanField(default=True)
    # Para login do operário: nome da fazenda + usuário/senha
    nome_fazenda_login = models.CharField(
        max_length=100,
        blank=True,
        help_text="Nome da fazenda usado no login do operário",
    )

    def __str__(self):
        return f"{self.nome} - {self.get_cargo_display()}"

    class Meta:
        verbose_name = "Funcionário"
        verbose_name_plural = "Funcionários"
        ordering = ["nome"]
        indexes = [
            models.Index(fields=["propriedade", "nome"]),
            models.Index(fields=["propriedade", "cargo"]),
        ]
