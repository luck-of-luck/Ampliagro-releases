"""Propostas de conciliacao: casa o extrato com o lancamento, e EXPLICA.

`app/services/conciliacao.py` ja' existe e faz o casamento. Le-o antes de
mudar alguma coisa la. Este modulo NAO o substitui - faz o que ele nao faz.

## Os quatro problemas do que existe

`conciliar_conta` (45 linhas) casa por **valor exacto + janela de data**, e
quando casa **escreve**: `mov.conciliado = True` e `cand.pago = True`, sem
perguntar a ninguem. Quatro consequencias:

**1. Escreve sem confirmacao.** E' o mais grave, e e' a razao deste modulo
existir. Todo o resto do Ampliagro exige confirmacao para escrever - as
intents da IA passam por `confirm=True`, o cadastro financeiro tem
`confirmar_lancamento`, e o motor proativo so emite alerta. Um caminho que
escreve sem perguntar e' um caminho sem tecto: um `.first()` errado baixa uma
conta a pago e o produtor perde a visao do que ainda deve.

**2. Nao diz PORQUE casou.** Duas contas de R$ 1.000 no mesmo mes sao
identicas para o filtro. O sistema escolhe uma e o produtor nao tem como
auditar a escolha - nem discordar dela.

**3. `.first()` quando ha varios.** Sem ordem explicita, o resultado depende
do plano de execucao da base. A mesma base, com dados inseridos noutra
ordem, da outra resposta. Nao e' um bug observavel; e' um bug que so aparece
quando ja' custou dinheiro.

**4. Nao responde a pergunta que importa.** O produtor toda a mes pergunta
"o que veio no extrato que eu ainda nao registrei?". `conciliar_conta` devolve
a lista do que casou. O que **nao** casou - que e' a resposta - fica no
silencio.

## O que este modulo faz

Le, propoe, e **explica**. Nao escreve. A escrita passa pelo caminho que ja'
existe e exige confirmacao.

Cada proposta traz:

    confianca    "exata" | "provavel" | "duvidosa" | "nenhuma"
    porque       a razao, em texto, com os dois numeros de lado
    custo        o que o produtor paga se aceitar e for wrong

E o mais importante, que nenhum detector faz: **`nao_casadas`**, com o motivo
de cada uma. Um extrato com 40 linhas onde 35 casam e 5 nao explica melhor o
mes do que um extrato onde 35 casam e o sistema nao diz nada sobre as outras 5.

## A caso que mente

`TRANSFERENCIA ENTRE CONTAS DA PROPRIA FAZENDA` nao e' receita nem despesa.

Um sistema que a conta como uma das duas mente nas duas: a receita esta
inflada e a despesa tambem. E o pior caso de todos, porque o erro e'
simetrico e por isso nao aparece em nenhuma das duas colunas - os dois
totais fecham, e ambos estao errados pela mesma quantia.

Este modulo tem uma regra propria para isto, e **nao propoe** - sinaliza.
Um sistema que proposta com confianca "alta" uma transferencia interna esta a
dar ao produtor um numero errado com muita certeza, que e' a combinacao que
faz um sistema perder a confianca mais depressa do que um sistema que falha
com honestidade.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal
from typing import Any

ZERO = Decimal("0")

# Valor exacto e' o unico "exata". Qualquer coisa abaixo e' uma opniao, e
# dizemo-lo. Um sistema que da `0.95` a uma regra fixa ensina o produtor a
# ler numeros como se fossem medidas - e depois nao sabe qual dos 0.95 era
# certo.
CONFIANCA_EXATA = "exata"
CONFIANCA_PROVAVEL = "provavel"
CONFIANCA_DUVIDOSA = "duvidosa"
CONFIANCA_NENHUMA = "nenhuma"

# Tolerancias. Um centavo de diferenca e' arredondamento de banco, nao erro:
# `45.000,00` escrito pelo produtor e `45000.00` no extrato sao o mesmo numero
# visto de dois jeitos.
TOLERANCIA_CENTAVOS = Decimal("0.01")
TOLERANCIA_PORCENTAGEM = Decimal("0.01")  # 1%

JANELA_DIAS = 3

# Palavras que indicam transferencia entre contas proprias. Vem do texto do
# extrato, que e' o banco que escreve - nao o produtor.
PISTAS_TRANSFERENCIA = (
    "transf",
    "transfer",
    "pix",
    "ted",
    "doc",
    "transferencia",
    "entre contas",
    "propria",
    "movimento interno",
    "ted_rc",
)


@dataclass(frozen=True)
class Proposta:
    """Um casamento sugerido. NAO foi feito."""

    movimentacao_id: int
    lancamento_id: int | None
    data_movimentacao: Any
    data_lancamento: Any | None
    valor_movimentacao: Decimal
    valor_lancamento: Decimal | None
    confianca: str
    porque: str
    texto_movimentacao: str
    categoria_lancamento: str | None = None
    suspeita_transferencia: bool = False

    @property
    def exige_confirmacao(self) -> bool:
        """Tudo exige. Este campo existe para o leitor nao ter de adivinhar
        que `duvidosa` e' um nivel diferente de permissao - e' nao. E' para
        deixar visivel que aDUVIDA existe."""
        return self.confianca != CONFIANCA_NENHUMA

    def as_dict(self) -> dict[str, Any]:
        return {
            "movimentacao_id": self.movimentacao_id,
            "lancamento_id": self.lancamento_id,
            "data_movimentacao": str(self.data_movimentacao),
            "data_lancamento": (
                str(self.data_lancamento) if self.data_lancamento else None
            ),
            "valor_movimentacao": float(self.valor_movimentacao),
            "valor_lancamento": (
                float(self.valor_lancamento)
                if self.valor_lancamento is not None
                else None
            ),
            "confianca": self.confianca,
            "porque": self.porque,
            "texto_movimentacao": self.texto_movimentacao,
            "categoria_lancamento": self.categoria_lancamento,
            "suspeita_transferencia": self.suspeita_transferencia,
            "exige_confirmacao": self.exige_confirmacao,
        }


@dataclass(frozen=True)
class NaoCasada:
    """Uma linha do extrato sem destino. E' a resposta, nao o residuo."""

    movimentacao_id: int
    data: Any
    valor: Decimal
    texto: str
    motivo: str
    suspeita_transferencia: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "movimentacao_id": self.movimentacao_id,
            "data": str(self.data),
            "valor": float(self.valor),
            "texto": self.texto,
            "motivo": self.motivo,
            "suspeita_transferencia": self.suspeita_transferencia,
        }


@dataclass
class ResultadoConciliacao:
    """O retrato do mes. `nao_casadas` e' a parte que ninguem mostra."""

    propostas: list[Proposta] = field(default_factory=list)
    nao_casadas: list[NaoCasada] = field(default_factory=list)
    ja_conciliadas: int = 0

    @property
    def por_confianca(self) -> dict[str, int]:
        d: dict[str, int] = {}
        for p in self.propostas:
            d[p.confianca] = d.get(p.confianca, 0) + 1
        return d

    @property
    def total_proposto(self) -> Decimal:
        return sum((p.valor_movimentacao for p in self.propostas), ZERO)

    @property
    def total_nao_casado(self) -> Decimal:
        return sum((n.valor for n in self.nao_casadas), ZERO)

    @property
    def tem_dados(self) -> bool:
        """Conta sem movimento nenhum e' diferente de conta com 50 por
        conciliar. Sem isto a tela mostra uma tabela vazia como se fosse
        'nada para fazer', que e' a leitura oposta da verdadeira.

        MEDIDO 2026-10-06: isto estava escrito so' dentro do `as_dict()`, e
        o `resumo_para_ia` usava-o como atributo - AttributeError em runtime.
        A propriedade tem de existir no objecto, nao so' na serializacao.
        """
        return bool(self.propostas or self.nao_casadas or self.ja_conciliadas)

    @property
    def transferencias_suspeitas(self) -> list[NaoCasada]:
        return [n for n in self.nao_casadas if n.suspeita_transferencia]

    def as_dict(self) -> dict[str, Any]:
        return {
            "propostas": [p.as_dict() for p in self.propostas],
            "nao_casadas": [n.as_dict() for n in self.nao_casadas],
            "ja_conciliadas": self.ja_conciliadas,
            "por_confianca": self.por_confianca,
            "total_proposto": float(self.total_proposto),
            "total_nao_casado": float(self.total_nao_casado),
            # `tem_dados` e' propriedade do objecto (ver a classe), nao um
            # calculo repetido aqui: a serializacao e o resumo tem de
            # responder a mesma pergunta.
            "tem_dados": self.tem_dados,
        }


def _parece_transferencia(texto: str) -> bool:
    t = (texto or "").lower()
    return any(p in t for p in PISTAS_TRANSFERENCIA)


def _mesmo_valor(a: Decimal, b: Decimal) -> bool:
    return abs(a - b) <= TOLERANCIA_CENTAVOS


def _dentro_tolerancia(a: Decimal, b: Decimal) -> bool:
    """1% de folga. Nao e' 'quase igual' - e' 'o banco arredondou'."""
    if _mesmo_valor(a, b):
        return True
    if b == 0:
        return False
    return abs(a - b) / abs(b) <= TOLERANCIA_PORCENTAGEM


def _candidates(mov, lancamentos):
    """Filtro deterministico. A ordem e' EXPLICITA - `order_by`, nunca
    `.first()` sem criterio, porque sem isso o resultado depende do plano de
    execucao da base e muda quando os dados sao inseridos noutra ordem."""
    return lancamentos.filter(
        data__gte=mov.data - timedelta(days=JANELA_DIAS),
        data__lte=mov.data + timedelta(days=JANELA_DIAS),
    ).order_by("data", "id")


def sugerir(user, conta, *, incluir_conciliadas=False) -> ResultadoConciliacao:
    """Le o extrato e o cadastro, e propoe. NAO ESCREVE NADA.

    `incluir_conciliadas=False` e' o default porque um extrato ja'conciliado
    nao e' uma proposta - e' historico. Quem quiser o historico pergunta.
    """
    from app.models import LancamentoFinanceiro, MovimentacaoBancaria

    resultado = ResultadoConciliacao()

    qs_mov = MovimentacaoBancaria.objects.filter(conta=conta)
    qs_mov = qs_mov.order_by("data", "id")

    # MEDIDO 2026-10-06. Este numero estava a ser contado DENTRO do laco, e
    # o laco so' via as nao-conciliadas - porque eram as unicas que passes
    # pelo filtro. Ou seja: contava sempre zero, e o `tem_dados` dependente
    # dele devolvia "conta vazia" para uma conta com 40 movimento ja' feitas.
    #
    # O que e' verdade e' contesta'vel: uma conta CUJO extrato esta' todo
    # conciliado nao esta' vazia, tem so' nada a fazer. Sao estados
    # diferentes e a tela precisa de os distinguir - e sem este numero ela
    # mostrava "sem dados" para quem ja' tinha feito o trabalho.
    resultado.ja_conciliadas = qs_mov.filter(conciliado=True).count()

    if not incluir_conciliadas:
        qs_mov = qs_mov.filter(conciliado=False)

    # `-valor` para o DEBITO (gasto) casar com o valor negativo do extrato.
    # `abs` e' do movimento, nao do lancamento: um `-45.000,00` no extrato e'
    # uma DESPESA de 45.000 no cadastro, e nao uma receita de -45.000.
    lancamentos = LancamentoFinanceiro.objects.filter(
        propriedade=conta.propriedade,
    )

    usados: set[int] = set()

    for mov in qs_mov:
        valor = abs(Decimal(mov.valor))
        transferencia = _parece_transferencia(mov.descricao)

        if transferencia:
            # NUNCA propoe. Uma transferencia entre contas proprias nao e'
            # receita nem despesa; casa-la com um lancamento baixa uma conta
            # a pago que ninguem pagou.
            resultado.nao_casadas.append(
                NaoCasada(
                    movimentacao_id=mov.pk,
                    data=mov.data,
                    valor=valor,
                    texto=mov.descricao,
                    motivo=(
                        "Transferencia entre contas: nao e' receita nem "
                        "despesa. Nao foi casada porque casar diria que "
                        "houve saida de dinheiro quando so mudou de conta."
                    ),
                    suspeita_transferencia=True,
                )
            )
            continue

        if mov.tipo == "DEBITO":
            alvo = lancamentos.filter(tipo="DESPESA", pago=False)
        else:
            alvo = lancamentos.filter(tipo="RECEITA", pago=False)

        cands = [c for c in _candidates(mov, alvo) if c.id not in usados]

        exacto = next(
            (c for c in cands if _mesmo_valor(abs(Decimal(c.valor)), valor)), None
        )
        if exacto is not None:
            resultado.propostas.append(
                Proposta(
                    movimentacao_id=mov.pk,
                    lancamento_id=exacto.id,
                    data_movimentacao=mov.data,
                    data_lancamento=exacto.data,
                    valor_movimentacao=valor,
                    valor_lancamento=Decimal(exacto.valor),
                    confianca=CONFIANCA_EXATA,
                    porque=(
                        f"Valor identico ({_fmt(valor)}) e a data do "
                        f"lancamento ({exacto.data}) cai dentro de "
                        f"{JANELA_DIAS} dias do movimento ({mov.data})."
                    ),
                    texto_movimentacao=mov.descricao,
                    categoria_lancamento=exacto.categoria,
                )
            )
            usados.add(exacto.id)
            continue

        provavel = next(
            (c for c in cands if _dentro_tolerancia(abs(Decimal(c.valor)), valor)), None
        )
        if provavel is not None:
            diferenca = valor - abs(Decimal(provavel.valor))
            resultado.propostas.append(
                Proposta(
                    movimentacao_id=mov.pk,
                    lancamento_id=provavel.id,
                    data_movimentacao=mov.data,
                    data_lancamento=provavel.data,
                    valor_movimentacao=valor,
                    valor_lancamento=Decimal(provavel.valor),
                    confianca=CONFIANCA_PROVAVEL,
                    porque=(
                        f"Valor a {diferenca:+.2f} - dentro de 1%, que e' "
                        f"arredondamento do banco. A data ({provavel.data}) "
                        f"esta dentro de {JANELA_DIAS} dias. Confirme antes "
                        f"de aceitar: se o valor for mesmo diferente, este "
                        f"lancamento NAO e' este."
                    ),
                    texto_movimentacao=mov.descricao,
                    categoria_lancamento=provavel.categoria,
                )
            )
            usados.add(provavel.id)
            continue

        # Nao casou. Diz PORQUE - e' a resposta que o produtor precisa.
        mesmo_valor_fora = lancamentos.filter(
            tipo=("DESPESA" if mov.tipo == "DEBITO" else "RECEITA"),
            valor=mov.valor,
        ).exclude(id__in=usados)
        if mesmo_valor_fora.exists():
            motivo = (
                "Ha um lancamento deste valor, mas a data esta fora da "
                f"janela de {JANELA_DIAS} dias."
            )
        else:
            perto = [
                c
                for c in lancamentos.filter(
                    tipo=("DESPESA" if mov.tipo == "DEBITO" else "RECEITA"),
                    pago=False,
                )
                if abs(abs(Decimal(c.valor)) - valor) <= valor * Decimal("0.05")
            ]
            if perto:
                motivo = (
                    f"Ha {len(perto)} lancamento(s) dentro de 5% deste "
                    "valor, mas nenhum dentro de 1%. Nao e' o mesmo numero, "
                    "e casar seria um chute."
                )
            else:
                motivo = (
                    "Nao ha nenhum lancamento em aberto deste valor. Ou o "
                    "dinheiro nao foi registado no cadastro, ou e' uma "
                    "entrada que nao e' receita nem despesa."
                )
        resultado.nao_casadas.append(
            NaoCasada(
                movimentacao_id=mov.pk,
                data=mov.data,
                valor=valor,
                texto=mov.descricao,
                motivo=motivo,
            )
        )

    return resultado


def _fmt(v: Decimal) -> str:
    return f"R$ {v:,.2f}"


def resumo_para_ia(resultado: ResultadoConciliacao) -> str:
    """Texto curto. A regra: nunca dizer quantas coisas casaram sem dizer
     quantas NAO casaram - o produtor que so ve '18 conciliadas' parte em
    ioures a pensar que acabou."""
    if not resultado.tem_dados:
        return "O extrato desta conta esta vazio, ou ja' esta tudo conciliado."

    partes = []
    por_conf = resultado.por_confianca
    if por_conf:
        det = ", ".join(f"{n} {confianca}" for confianca, n in sorted(por_conf.items()))
        partes.append(
            f"{len(resultado.propostas)} movimento(s) com lancamento sugerido ({det})"
        )

    if resultado.nao_casadas:
        trans = len(resultado.transferencias_suspeitas)
        msg = f"{len(resultado.nao_casadas)} movimento(s) SEM lancamento correspondente"
        if trans:
            msg += f", dos quais {trans} parecem transferencia entre contas"
        partes.append(msg)

    if resultado.ja_conciliadas:
        partes.append(f"{resultado.ja_conciliadas} ja' conciliado(s) anteriormente")

    texto = "Extrato: " + "; ".join(partes) + "."

    if resultado.nao_casadas:
        top = resultado.nao_casadas[0]
        texto += (
            f" O que mais chama atencao: {top.texto} de "
            f"{_fmt(top.valor)} em {top.data} - {top.motivo}"
        )
        resto = len(resultado.nao_casadas) - 1
        if resto > 0:
            texto += f" (e mais {resto})."

    texto += (
        " Nada foi escrito: cada casamento precisa de confirmacao, porque"
        " baixar uma conta a pago sem perguntar faz o produtor perder a"
        " visao do que ainda deve."
    )
    return texto
