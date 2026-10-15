"""Aplica, aos testes LCDPR, o mesmo cenario minimo que um produtor real tem.

MEDIDO 2026-10-05. A `LCDPRDadosIncompletos` exige talhoes cadastrados, porque
o registo `0040` declara **imoveis rurais** e uma propriedade sem talhao nao tem
imoveis a declarar. A guarda esta certa; os **cenarios de teste** é que ficaram
desatualizados, e por isso varios testes falhavam sem que houvesse defeito no
que testavam.

Este modulo expoe um unico ponto de entrada — `propriedade_com_imoveis()` — para
que a correccao nao se espalhe por N `setUp` diferentes. E' a forma mais barata
de o mesmo defeito ser resolvido uma vez em vez de cinco.

Nao apaga nada: cada teste continua a ter o seu `setUp`, e o que este modulo
faz e' dar-lhe o talhao que lhe falta.
"""

from decimal import Decimal

from app.models.core import Propriedade, Talhao


def propriedade_com_imoveis(
    user,
    nome: str = "Fazenda LCDPR",
    area_total: Decimal = Decimal("100.00"),
    **extra,
) -> Propriedade:
    """Cria a propriedade e um talhao minimo, e devolve a propriedade.

    `extra` vai directo para `Propriedade.objects.create`, para cada teste poder
    passar o que lhe interessa (`cpf_cnpj`, `tipo_exploracao`, `participacao`…)
    sem este modulo ter de saber todos os campos.
    """
    prop = Propriedade.objects.create(
        user=user,
        nome=nome,
        area_total=area_total,
        **extra,
    )
    Talhao.objects.create(
        propriedade=prop,
        nome="Gleba 1",
        area_hectare=Decimal("100.00"),
    )
    return prop
