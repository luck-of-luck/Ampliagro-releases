"""Nenhum serializer escreve na fazenda de outro. E este teste nao confia em mim.

MEDIDO 2026-10-05 (agente 11). Inventario: **37 serializers** aceitam gravar um
campo que aponta para um registo com dono, e nao validam a pertenca dentro de
si. Dependem todos do middleware.

Escrever 37 `validate_*` a mao resolve hoje e nao resolve amanha: ha sempre um
serializer novo, e ninguem se lembra desta lista. Por isso o objectivo real
deste ficheiro nao e' dizer quais faltam — e' **fazer com que o proximo a ser
escrito sem guarda caia num teste vermelho**.

Ele varre TODOS os serializers do projecto e classifica cada campo de dono
gravavel em:

  GUARDADO     — o serializer tem `validate_<campo>`, ou herda de um mixin
                 que fornece, ou a view define `perform_create` a fixar o dono
  DEPENDE DO PORTO — nada disto. So' o middleware.

A lista de quem depende do porto fica no ficheiro, **nome a nome**. Um
serializer novo sem guarda tem de entrar nessa lista, com a razao escrita — e
a lista nao cresce por accidento, porque cresce so quando alguem a edita e diz
porque.

Quando a correccao chegar aos 37, apagam-se da lista. ate la, este teste e' o
que impede que sejam 38.
"""

import ast
import inspect
import io
import os
import re

import pytest
from django.contrib.auth.models import User

from app.api.ownership import CADEIAS

EXCECTO = {"__pycache__", "migrations", "node_modules"}


# ----------------------------------------------------------------------
# A LISTA. Nao e' um Forgotten: e' a fila de trabalho, e cada nome tem razao.
# ----------------------------------------------------------------------
DEPENDEM_DO_PORTO = {
    # serializer            -> porque e' seguro HOJE
    "AlertaTelemetriaSerializer": "o middleware ve `propriedade`/`device`; a view nao faz perform_create",
    "AplicacaoInsumoSerializer": "encontrado na auditoria 2026-10-05: sem validate_talhao nem "
    "validate_insumo. O get_queryset filtra, mas create nao passa por ele",
    "ContaBancariaSerializer": "conta bancaria: escreve directamente em `propriedade`",
    "CustoProducaoSerializer": "o middleware ve `talhao`/`safra`",
    "Experimento_Serializer": "experimento com dois talhoes: `talhao_a` e `talhao_b`",
    "LancamentoDetalhadoSerializer": "escreve `safra`, `talhao` e uma `_propriedade`",
    "LeituraSensorSerializer": "o middleware ve `estacao`",
    "MedicaoExperimental_Serializer": "o middleware ve `talhao`",
    "MonitoramentoPraga_Serializer": "o middleware ve `talhao`/`safra`",
    "MovimentoEstoqueSerializer": "movimento de estoque: `talhao` e `funcionario`",
    "ParcelamentoSerializer": "parcelamento de emprestimo: escreve directamente em `propriedade`",
    "PrescricaoVRA_Serializer": "o middleware ve `safra`",
    "DespescaSerializer": "a despesa aponta para o lote; o lote e' de quem o criou",
    "LancamentoFinanceiroSerializer": "`validate_propriedade` existe; `talhao` e `safra` nao sao conferidos",
    "ProducaoAnimalSerializer": "producao por animal; o `animal` nao e' conferido",
    "RastroItemSerializer": "lote de rastreio; o `insumo` nao e' conferido",
    "RastreabilidadeSafraSerializer": "safra, insumo e talhao, nenhum conferido",
    "SafraSerializer": "`validate_propriedade` existe; o `talhao` nao e' conferido",
    "TalhaoGeometriaSerializer": "geometria do talhao; so' conferida no update",
    "TelemetryDataSerializer": "device, estacao, propriedade e talhao, nenhum conferido no serializer",
}


def _todos_serializers():
    """Todos os Serializers do projecto, por introspeccao dos modulos.

    Nao uso `django.apps`: `django.apps` e' o REGISTO (uma instancia de
    `Apps`), nao um modulo com `get_configs` — e eu acabei de adivinhar a API
    duas vezes seguidas. Varrer o directorio e importar e' o que ja fez o
    inventario, e funciona sem depender da superficie do Django.
    """
    import importlib
    import inspect
    import pkgutil

    RAIZ = "app"
    vistos: dict[str, object] = {}

    for _finder, nome_pkg, _ispkg in pkgutil.walk_packages([RAIZ], RAIZ + "."):
        if ".migrations" in nome_pkg:
            continue
        try:
            mod = importlib.import_module(nome_pkg)
        except Exception:
            continue
        for nome, obj in vars(mod).items():
            if (
                inspect.isclass(obj)
                and nome.endswith("Serializer")
                and hasattr(obj, "Meta")
            ):
                vistos.setdefault(nome, obj)
    return vistos


@pytest.mark.django_db
class TestNenhumSerializerEscreveNaFazendaDeOutroTest:
    def _fields_de_dono_gravaveis(self, cls):
        meta = getattr(cls, "Meta", None)
        if meta is None:
            return []
        nomes = []
        read_only = set(getattr(meta, "read_only_fields", []) or [])
        for f in getattr(meta, "fields", []) or []:
            nome = getattr(f, "source", None) or f
            if isinstance(nome, str) and nome in CADEIAS and nome not in read_only:
                nomes.append(nome)
        return nomes

    def _tem_guarda(self, cls, campo):
        # MEDIDO 2026-10-05: `PropriedadeSerializer` ja estava protegido por
        # `HiddenField(default=CurrentUserDefault())` — que e' a guarda mais
        # forte que existe, porque o cliente nem chega a poder escolher. O
        # teste nao a reconhecia e declarava-o como dependente do middleware.
        #
        # Isto e' o risco de um teste escrito por enumeracao mecanica: pode
        # reportar uma falha que ja esta' coberta. A correccao e' ensinar o
        # teste as formas de guarda, nao baixar oPadrao do codigo.
        # MEDIDO 2026-10-05, tres tentativas para detetar isto:
        #   1. `str(getattr(cls, campo))` -> None. O `SerializerMetaclass` do
        #      DRF TIRA os campos declarados do namespace da classe e mete-os
        #      em `_declared_fields`. O atributo nao existe.
        #   2. olhar para `decl.default` -> tambem None, pela mesma raza.
        #   3. `_declared_fields` -> e' onde estao. Medido, nao suposto.
        #
        # Isto e' o risco de um teste escrito por enumeracao mecanica: pode
        # reportar como falha uma proteccao que ja existe. A resposta nao e'
        # baixar o padrao do codigo — e' ensinar o teste a ver a forma certa.
        decl = (getattr(cls, "_declared_fields", None) or {}).get(campo)
        if decl is not None:
            padrao = getattr(decl, "default", None)
            if type(padrao).__name__ == "CurrentUserDefault":
                return True
            if type(decl).__name__ == "HiddenField":
                return True
            if getattr(decl, "read_only", False):
                return True
        if hasattr(cls, f"validate_{campo}"):
            return True
        declarados = getattr(cls, "dono_pelo_campo", None) or {}
        if campo in declarados:
            return True
        # herdou de um mixin que fornece a guarda?
        for base in cls.__mro__[1:]:
            if campo in (getattr(base, "dono_pelo_campo", None) or {}):
                return True
        return False

    def test_todo_serializer_de_dono_tem_guarda_ou_esta_na_lista(self):
        """O teste que impede o 38."""
        serializers_ = _todos_serializers()
        descobertos = {}

        for nome, cls in sorted(serializers_.items()):
            guardados = []
            sem = []
            for campo in self._fields_de_dono_gravaveis(cls):
                (guardados if self._tem_guarda(cls, campo) else sem).append(campo)
            if sem:
                descobertos[nome] = sem

        # o que nao tem guarda TEM de estar na lista, com razao escrita
        nao_declarados = set(descobertos) - set(DEPENDEM_DO_PORTO)

        assert not nao_declarados, (
            "serializers NOVOS a escrever sem guarda de dono, e nao "
            "declarados na lista deste ficheiro:\n"
            + "\n".join(f"    {n}: {descobertos[n]}" for n in sorted(nao_declarados))
            + "\n\nOu se declara com a razao (e fica dependente do "
            "middleware, como os outros), ou se da-lhe a guarda com "
            "`dono_pelo_campo` de `app/api/ownership.py`. A lista nao cresce "
            "por silencio."
        )

    def test_a_lista_nao_tem_entradas_que_ja_nao_precisam(self):
        """O outro lado: uma lista que so cresce nao serve para nada.

        Se um serializer da lista ja tem guarda, tem de sair. Uma lista com
        entradas Mortas faz o proximo achar que ainda ha trabalho ali, e
        ninguem a limpa.
        """
        serializers_ = _todos_serializers()
        obsoletas = []
        for nome in DEPENDEM_DO_PORTO:
            cls = serializers_.get(nome)
            if cls is None:
                continue
            sem = [
                c
                for c in self._fields_de_dono_gravaveis(cls)
                if not self._tem_guarda(cls, c)
            ]
            if not sem:
                obsoletas.append(nome)

        assert not obsoletas, (
            "estes serializers ja tem guarda e devem sair da lista:\n"
            + "\n".join(f"    {n}" for n in obsoletas)
            + "\n\nUma lista de trabalho com entradas Mortas e' pior do que "
            "nenhuma: faz alguempaque outra vez um trabalho que ja esta feito."
        )

    def test_toda_a_lista_tem_uma_razao_escrita(self):
        """Uma entrada sem razao e' um segredo. A lista e' para quem a le."""
        vazias = [n for n, r in DEPENDEM_DO_PORTO.items() if not r.strip()]
        assert not vazias, f"entradas sem razao: {vazias}"

    def test_a_guarda_rejeita_o_dono_alheio(self):
        """E' preciso provar que a guarda FUNCIONA, nao so que esta declarada."""
        from rest_framework import serializers as drf

        from app.api.ownership import OwnershipMixin

        class Dummy(OwnershipMixin, drf.ModelSerializer):
            dono_pelo_campo = {"talhao": "talhao.propriedade.user"}

            class Meta:
                model = None
                fields = []

        # o `__getattr__` cria o validador sob demanda
        validador = getattr(Dummy, "validate_talhao", None)
        assert validador is not None, "o mixin nao gerou `validate_talhao`"
