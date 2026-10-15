"""Compatibilidade com o antigo gerador; a saída fiscal tem uma única implementação."""
from app.models.core import Propriedade
from app.services.lcdpr_export import LCDPRExporter
from app.services.lcdpr_layout import formatar_valor


class LCDPRGenerator:
    def __init__(self, propriedade_id, ano_base):
        self.propriedade = Propriedade.objects.get(pk=propriedade_id)
        self.ano_base = ano_base

    _formatar_valor = staticmethod(formatar_valor)

    def gerar_arquivo(self):
        return LCDPRExporter(self.propriedade, self.ano_base).gerar_arquivo()
