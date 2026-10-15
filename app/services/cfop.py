"""CFOP: o número que diz se uma NF-e é entrada ou saída.

## O problema que isto resolve

`nfe_import` importava **tudo** como `tipo="DESPESA", categoria="INSUMO"`,
sem olhar o CFOP uma única vez. Uma nota de venda de soja a R$ 78.000 entrava
como despesa — o sinal invertido, e o erro aparecia no DRE, no lucro e no
crédito como se o produtor tivesse *gasto* 78 mil a vender.

## A regra

O primeiro dígito do CFOP é a operação:

| 1º dígito | Operação    | Efeito no estoque e no financeiro |
|---|---|---|
| 1, 2, 3  | **Entrada** | aumenta estoque, `DESPESA`/`INSUMO` |
| 5        | **Saída**   | não toca estoque, `RECEITA`/`VENDA_PROD` |
| 6, 7     | Apuração    | **não entra** |

`6` e `7` sãoapurados de período (GUIAS, inventário, mudança de
formação) — não são compra nem venda. Lancá-los como uma das duas coisas é
inventar. Ficam de fora, nomeados no resultado.

## O que um CFOP desconhecido faz

**Nada.** Descartar um documento que não sabemos ler é perdoável — o produtor
ainda tem o XML. Lançá-lo com o sinal errado **não** é: o lançamento entra no
lucro e ninguém o revê.

Por isso a função devolve sempre `(classe, motivo)`, e o motivo viaja para a
resposta ao produtor. Uma importação que falha em silêncio é pior do que uma
que falha a dizer porquê.

## Por que isto é um serviço e não uma função na view

Porque a classificação vai ser precisa em dois sítios — a importação e a
conciliação (§21.2) — e uma regra de negócio em dois sítios diverge. E porque
uma tabela de CFOP escrita à mão, sem teste, é como o `SEMENTE` do DRE: uma
afirmação de cobertura que ninguém verifica.
"""

from __future__ import annotations

# classe, tipo, categoria, toca_estoque
ENTRADA = "entrada"
SAIDA = "saida"
APURACAO = "apuracao"
DESCONHECIDO = "desconhecido"


class CategoriaCFOP:
    """O que um CFOP significa para o estoque e para o financeiro."""

    def __init__(self, classe, tipo_lancamento, categoria, mexe_estoque, descricao):
        self.classe = classe
        self.tipo_lancamento = tipo_lancamento
        self.categoria = categoria
        self.mexe_estoque = mexe_estoque
        self.descricao = descricao

    def as_dict(self) -> dict:
        return {
            "classe": self.classe,
            "tipo_lancamento": self.tipo_lancamento,
            "categoria": self.categoria,
            "mexe_estoque": self.mexe_estoque,
            "descricao": self.descricao,
        }


# Um CFOP explicitamente nomeado. Não é exaustivo — a tabela oficial tem
# hundreds de códigos — e **essa é a razão de o desconhecido ser descartado**:
# Preferimos perder um item a inventar o sinal de um lançamento.
_TABELA: dict[str, CategoriaCFOP] = {
    # --- Entradas ---
    "1101": CategoriaCFOP(ENTRADA, "DESPESA", "INSUMO", True, "Compra de mercadoria"),
    "1102": CategoriaCFOP(ENTRADA, "DESPESA", "INSUMO", True, "Compra de mercadoria"),
    "1111": CategoriaCFOP(
        ENTRADA, "DESPESA", "INSUMO", True, "Compra de mercadoria importada"
    ),
    "1113": CategoriaCFOP(ENTRADA, "DESPESA", "INSUMO", True, "Compra de mercadoria"),
    "1115": CategoriaCFOP(ENTRADA, "DESPESA", "INSUMO", True, "Compra de mercadoria"),
    "1121": CategoriaCFOP(ENTRADA, "DESPESA", "INSUMO", True, "Compra de insumo"),
    "1201": CategoriaCFOP(ENTRADA, "DESPESA", "OUTRO", True, "Compra de retorno"),
    "1904": CategoriaCFOP(ENTRADA, "DESPESA", "OUTRO", True, "Retorno de venda"),
    "2101": CategoriaCFOP(ENTRADA, "DESPESA", "OUTRO", True, "Compra de serviço"),
    "2201": CategoriaCFOP(
        ENTRADA, "DESPESA", "OUTRO", True, "Transferência de entrada"
    ),
    "2202": CategoriaCFOP(
        ENTRADA, "DESPESA", "OUTRO", True, "Transferência de entrada"
    ),
    "2203": CategoriaCFOP(
        ENTRADA, "DESPESA", "OUTRO", True, "Transferência de entrada"
    ),
    "2211": CategoriaCFOP(ENTRADA, "DESPESA", "OUTRO", True, "Remessa de venda"),
    # --- Saídas ---
    "5101": CategoriaCFOP(SAIDA, "RECEITA", "VENDA_PROD", False, "Venda de mercadoria"),
    "5102": CategoriaCFOP(SAIDA, "RECEITA", "VENDA_PROD", False, "Venda de mercadoria"),
    "5103": CategoriaCFOP(
        SAIDA, "RECEITA", "VENDA_PROD", False, "Venda de mercadoria importada"
    ),
    "5104": CategoriaCFOP(SAIDA, "RECEITA", "VENDA_PROD", False, "Venda de mercadoria"),
    "5115": CategoriaCFOP(SAIDA, "RECEITA", "VENDA_PROD", False, "Venda de mercadoria"),
    "5116": CategoriaCFOP(
        SAIDA, "RECEITA", "VENDA_PROD", False, "Venda de mercadoria importada"
    ),
    "5117": CategoriaCFOP(
        SAIDA, "RECEITA", "VENDA_PROD", False, "Venda de mercadoria importada"
    ),
    "5202": CategoriaCFOP(SAIDA, "RECEITA", "OUTRO", False, "Venda de serviço"),
    "5553": CategoriaCFOP(SAIDA, "RECEITA", "OUTRO", False, "Remessa de venda"),
    "5556": CategoriaCFOP(SAIDA, "RECEITA", "OUTRO", False, "Remessa de venda"),
    # --- Apuração (não entram) ---
    "1202": CategoriaCFOP(APURACAO, None, None, False, "Devolução de venda"),
    "2204": CategoriaCFOP(APURACAO, None, None, False, "Devolução de remessa"),
    "5901": CategoriaCFOP(APURACAO, None, None, False, "GUIAS"),
    "6901": CategoriaCFOP(APURACAO, None, None, False, "Redução de estoque"),
    "7901": CategoriaCFOP(APURACAO, None, None, False, "Redução de estoque"),
}


def classificar(cfop: str | int | None) -> tuple[CategoriaCFOP | None, str | None]:
    """Classifica um CFOP. Devolve `(categoria, motivo_da_recusa)`.

    Regra deliberada: **a tabela acima é uma lista branca**. Um CFOP fora dela
    devolve `(None, motivo)` mesmo que o primeiro dígito sugira uma operação
    conhecida — porque o primeiro dígito sozinho não distingue, por exemplo,
    `1201` (retorno) de `1202` (devolução, apuração), e errar o sinal num
    lançamento é irreversível.

    A excepção é o grupo genérico de cada operação, que a SEFAZ reserva para
    "outros": `1199`, `5199`, etc. Esses entram pela regra do primeiro dígito.
    """
    if cfop is None:
        return None, "item sem CFOP — não dá para saber se é entrada ou saída"

    txt = str(cfop).strip().upper()
    if len(txt) != 4 or not txt[:4].isdigit():
        return None, f"CFOP '{txt}' não tem 4 dígitos"

    achado = _TABELA.get(txt)
    if achado is not None:
        return achado, None

    # "Outros" da operação: a SEFAZ reserva os dois últimos dígitos (`99`)
    # para o genérico de cada operação. `txt[2:]`, não `txt[1:]` — num CFOP
    # de 4 dígitos o `99` é o sufixo, e `txt[1:]` seria "199" em `1199`,
    # que nunca casa. (Os testes apanharam este.)
    if txt[2:] == "99":
        primeiro = txt[0]
        if primeiro in ("1", "2", "3"):
            return (
                CategoriaCFOP(
                    ENTRADA, "DESPESA", "INSUMO", True, "Entrada (CFOP genérico)"
                ),
                None,
            )
        if primeiro == "5":
            return (
                CategoriaCFOP(
                    SAIDA, "RECEITA", "VENDA_PROD", False, "Saída (CFOP genérico)"
                ),
                None,
            )
        if primeiro in ("6", "7"):
            return (
                CategoriaCFOP(APURACAO, None, None, False, "Apuração (CFOP genérico)"),
                None,
            )

    return (
        None,
        f"CFOP {txt} fora da tabela do sistema — o item não foi lançado. "
        "Um CFOP desconhecido pode ser entrada ou saída, e lançar com o "
        "sinal errado altera o lucro.",
    )
