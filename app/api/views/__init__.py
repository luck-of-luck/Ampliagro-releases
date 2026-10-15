# ---------------------------------------------------------------------------
# Reaponta os submódulos locais -- MANTER COMO ULTIMAS LINHAS DO ARQUIVO.
#
# Os `from .X import *` acima trazem junto tudo o que `app.models` exporta,
# inclusive os nomes dos proprios submódulos de `app.models` (iot, estoque,
# pecuaria, core, ...). Como o atributo de pacote e "a ultima escrita que
# vence", `app.api.views.iot` terminava apontando para `app.models.iot` --
# 38 nomes de modulo apontavam para o modulo errado, 10 deles colidindo com
# um submódulo local de verdade (iot, estoque, mip, apiario, aquatico, core,
# financial, maquinario, pecuaria, production). Qualquer `from app.api.views
# import iot` ou `views.iot.X` pegaria o modulo errado (silenciosamente).
#
# Nao da para usar `from . import iot`: o import com fromlist consulta o
# atributo antes de importar, e o atributo ja existe (sujo), entao ele
# apenas re-usaria o modulo errado. O importlib resolve pelo sys.modules,
# que nao e enganado pelo atributo.
#
# Novo `from .Y import *` la em cima? Acrescente o nome em _SUBMODULOS_LOCAIS.
# ---------------------------------------------------------------------------
from importlib import import_module as _import_module

from .apiario import *
from .aquatico import *
from .busca import busca_geral_data, contexto_ia_data
from .core import *
from .cultures import *
from .custos import CentroCustoViewSet, CustoProducaoViewSet, LancamentoDetalhadoViewSet
from .estoque import *
from .faltantes import *
from .financial import *
from .iot import *
from .kanban import *
from .maquinario import *
from .pecuaria import *
from .production import *
from .rastreabilidade import (
    MovimentoEstoqueViewSet,
    RastreabilidadeSafraViewSet,
    RastroItemViewSet,
)
from .cultivar import CultivarViewSet
from .ensaio_cultivar import EnsaioCultivarViewSet, FaixaEnsaioViewSet
from .lote_semente import LoteSementeViewSet
from .mix_pastagem import MixPastagemViewSet
from .viveiro import LoteMudaViewSet, ViveiroViewSet
from .relatorios import *
from .user import *

_SUBMODULOS_LOCAIS = (
    "apiario",
    "aquatico",
    "busca",
    "core",
    "cultures",
    "custos",
    "estoque",
    "faltantes",
    "financial",
    "iot",
    "kanban",
    "maquinario",
    "mip",
    "pecuaria",
    "production",
    "rastreabilidade",
    "relatorios",
    "utils",
    "user",
)
for _subnome in _SUBMODULOS_LOCAIS:
    globals()[_subnome] = _import_module(f"{__name__}.{_subnome}")
del _subnome
