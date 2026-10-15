"""Pontos de extensão para serviços que exigem contrato ou habilitação externa.

Nenhum adaptador é instalado por padrão. Credenciais ficam no ambiente do
servidor; o catálogo público contém apenas o estado e os requisitos.
"""

from dataclasses import dataclass
from typing import Protocol

from django.conf import settings
from django.utils.module_loading import import_string


@dataclass(frozen=True)
class Integracao:
    codigo: str
    nome: str
    requisitos: tuple[str, ...]
    alternativa: str


INTEGRACOES = (
    Integracao("nfe_emissao", "Emissão de NF-e", (
        "Credenciamento fiscal do emitente e configuração tributária",
        "Certificado e autorização do titular",
        "Adaptador do provedor testado em homologação",
    ), "Importar XML de notas já emitidas"),
    Integracao("dfe_consulta", "Busca automática de documentos fiscais", (
        "Autorização do titular e certificado",
        "Adaptador de distribuição DF-e com controle de NSU e consumo",
    ), "Importar o XML recebido do fornecedor"),
    Integracao("lcdpr_transmissao", "Entrega do LCDPR", (
        "Arquivo revisado e validação no serviço oficial",
        "Identificação digital ou procuração aceita pela Receita",
        "Canal oficial de entrega verificado; não há adaptador instalado",
    ), "Gerar arquivo e entregar pelo serviço oficial da Receita"),
    Integracao("open_finance", "Sincronização bancária", (
        "Consentimento vigente do titular e contrato com provedor",
        "Adaptador que trate renovação, revogação e duplicidades",
    ), "Importar extrato OFX ou CSV"),
    Integracao("maquinas", "Telemetria dos fabricantes", (
        "Autorização do produtor e acesso à API do fabricante",
        "Mapeamento de equipamentos, unidades e propriedade",
    ), "Usar os conectores de arquivo e a telemetria IoT já disponíveis"),
    Integracao("erp", "ERP e contabilidade", (
        "Contrato e credenciais do sistema de destino",
        "Mapeamento de contas, propriedades e retorno de erros",
    ), "Exportar os relatórios e arquivos para conferência"),
)


class AdaptadorAgro(Protocol):
    """Implementar no provedor; chave deve impedir repetição no destino."""

    def executar(self, *, propriedade_id: int, operacao: str,
                 dados: dict, chave_idempotencia: str) -> dict: ...


class IntegracaoIndisponivel(ValueError):
    pass


def _configuracao(codigo):
    configuracoes = getattr(settings, "AMPLIAGRO_INTEGRACOES", {})
    if not isinstance(configuracoes, dict):
        return {}
    config = configuracoes.get(codigo, {})
    return config if isinstance(config, dict) else {}


def _adaptador(config):
    caminho = config.get("adaptador")
    if not isinstance(caminho, str) or not caminho:
        return None
    try:
        classe = import_string(caminho)
    except (ImportError, AttributeError, ValueError):
        return None
    return classe if isinstance(classe, type) and callable(getattr(classe, "executar", None)) else None


def catalogo_integracoes():
    """Estado de configuração, nunca uma alegação de conexão ou homologação."""
    resultado = []
    for integracao in INTEGRACOES:
        config = _configuracao(integracao.codigo)
        classe = _adaptador(config)
        habilitada = config.get("habilitada") is True
        homologacao_registrada = config.get("homologacao_registrada") is True
        pronta = bool(classe and habilitada and homologacao_registrada)
        resultado.append({
            "codigo": integracao.codigo,
            "nome": integracao.nome,
            "estado": "configurada" if pronta else "pendente",
            "adaptador_instalado": classe is not None,
            "habilitada": habilitada,
            "homologacao_registrada": homologacao_registrada,
            "requisitos": integracao.requisitos,
            "alternativa": integracao.alternativa,
            "mensagem": (
                "Configuração habilitada; a conexão depende do serviço contratado."
                if pronta else "Aguardando configuração e habilitação."
            ),
        })
    return resultado


def executar_integracao(codigo, *, user, propriedade_id, operacao, dados,
                       chave_idempotencia):
    """Porta interna para futuros adaptadores, isolada por propriedade.

    O chamador deve obter confirmação da operação no seu fluxo. Nenhuma rota
    pública de transmissão é oferecida enquanto não houver provedor instalado.
    """
    from app.hierarquia import propriedades_financeiras

    if codigo not in {item.codigo for item in INTEGRACOES}:
        raise IntegracaoIndisponivel("Integração desconhecida.")
    if not getattr(user, "is_authenticated", False) or not propriedades_financeiras(user).filter(pk=propriedade_id).exists():
        raise IntegracaoIndisponivel("Sem acesso à propriedade.")
    config = _configuracao(codigo)
    classe = _adaptador(config)
    if not classe or config.get("habilitada") is not True or config.get("homologacao_registrada") is not True:
        raise IntegracaoIndisponivel("Integração ainda não habilitada.")
    if not isinstance(chave_idempotencia, str) or not chave_idempotencia.strip() or len(chave_idempotencia) > 128:
        raise IntegracaoIndisponivel("Informe uma chave de operação de até 128 caracteres.")
    if not isinstance(dados, dict) or not isinstance(operacao, str) or not operacao.strip():
        raise IntegracaoIndisponivel("Operação e dados inválidos.")
    return classe().executar(propriedade_id=propriedade_id, operacao=operacao,
                            dados=dados, chave_idempotencia=chave_idempotencia)
