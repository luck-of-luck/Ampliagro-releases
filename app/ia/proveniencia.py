"""proveniencia.py — um número não entra no payload sem dizer de onde veio.

O PROBLEMA, CONTADO
===================
Esta sessão encontrou números inventados em seis camadas, seis mecanismos
diferentes, seis ficheiros que não se conhecem:

  * `culture-metrics-fallback.json` — 468 valores fixos, servidos no `catch`
  * `CULTURE_METRICS.default` no `index.html` — último recurso para todos
  * `cultures-config.json` — `default_metrics`, a mesma global por outro nome
  * `getGenericDefaultMetrics()` — os mesmos números de trinco
  * `getWidgetDataFromAPI()` — `|| 'R$ 450'`, `|| '12,5%'`
  * `kpi-area` — a área somada entre anos, 210 ha viravam 630

Seis bugs parecem independentes. Não são: são a mesma ausência, seis vezes. E a
prova de que é estrutural é que **eu introduzi a sétima** enquanto a curava
(`buildUnavailableResult`, chamada em dois sítios e nunca definida).

Um carimbo de proveniência escrito à mão é uma constante com vestido. A
constante pode estar errada por acidente; aqui, estaria errada por
construção — porque ninguém a obriga a existir.

A REGRA, E PORQUÊ É ESTA
=======================
    NÃO EXISTE CAMINHO PARA CONSTRUIR UM NÚMERO SEM FONTE.

Não é uma convenção que se cumpre. É uma consequência da construção: o
serializador recebe sempre valores embrulhados, e o que ele escreve é a
forma que essa embrrulhado obriga.

SEIS ESTADOS, E NÃO MAIS
=======================
`medido`             — saiu do banco, serve para decidir
`medido_com_ressalva` — saiu do banco, e o sensor está a duvidar; o número
                        serve, a ressalva é obrigatória e accionável
`suspect`            — o sensor disse, e a física não permite o que disse
`sem_dado`           — não há o que mostrar, e diz porquê
`simulado`           — número gerado, e a origem geradora viaja com ele
`declarado`          — um produtor afirmou; não é medição, e quem afirmou
                        viaja com ele

Os três primeiros e o último existiam em `app/validators.py:11-17` desde antes
de este módulo, e **o painel não os conhecia**. Um estado que a escrita aceita
e o painel não sabe desenhar é um estado que o produtor perde — e, no caso de
`medido_com_ressalva` e `suspect`, um dado que o sistema sabia ser duvidoso
e que aparecia no ecrã como se não fosse. Ver
`tests/test_proveniencia_dois_vocabularios.py`, que é o guarda desta
coerência.

Um sétimo estado tentador é "estimado". Resistiu porque um número estimado
que não diz que é estimado é um número medido que mente; e o que se pede a um
produtor que acione a irrigação é que ele saiba em que base.

`simulado` não está no conjunto do validador, e é propositado: um valor
simulado não afirma nada sobre o mundo, é uma pergunta "como ficaria o ecrã
com o dado". O validador valida afirmações; um simulado não afirma.

O QUE ISTO NÃO FAZ
==================
Não valida o cálculo — se a área está somada entre anos, isto não descobre.
Não torna um widget correcto. O que faz é tornar a MENTIRA ESTRUTURALMENTE
DIFÍCIL: um número sem origem deixa de ser escrevível, e o resto passa a ser
questão de cada widget fazer a conta bem.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class Estado:
    """Os estados, e nenhum outro.

    Uma constante de string para cada um, e não um `Literal`: um `Literal`
    deixa passar qualquer string que se pareça, e "parece" é exactamente o
    problema que estamos a resolver.
    """

    MEDIDO = "medido"
    MEDIDO_COM_RESSALVA = "medido_com_ressalva"
    SUSPECT = "suspect"
    SEM_DADO = "sem_dado"
    SIMULADO = "simulado"
    DECLARADO = "declarado"


TODOS = (
    Estado.MEDIDO,
    Estado.MEDIDO_COM_RESSALVA,
    Estado.SUSPECT,
    Estado.SEM_DADO,
    Estado.SIMULADO,
    Estado.DECLARADO,
)


@dataclass(frozen=True)
class Medido:
    """Um número que saiu de uma consulta. A fonte é obrigatória.

    `fonte` é uma string que nomeia o que foi consultado — `"LancamentoFinanceiro
    da propriedade 18"`, não `"api"`. A regra é que tem de ser específica: uma
    fonte que não distingue uma consulta de outra não é uma fonte, é um
    cabeçalho, e um cabeçalho não se audita.
    """

    valor: Any
    fonte: str

    def __post_init__(self):
        if not (self.fonte or "").strip():
            raise ValueError(
                "Um Medido sem fonte não é um dado: é um número com roupa de "
                "dado. A fonte tem de dizer o que foi consultado — e a pergunta "
                "que ela responde é 'isto foi lido de onde?'."
            )

    @property
    def estado(self) -> str:
        return Estado.MEDIDO


@dataclass(frozen=True)
class MedidoComRessalva:
    """O sensor disse, mas com uma anomalia. O número é utilizável; a ressalva
    é obrigatória.

    Este estado existia no validador desde antes de este módulo, e o painel não
    o tinha. A diferença que faz: `Medido` é "isto saiu do banco", este é
    "isto saiu do banco **e o sensor está a duvidar**" — ruído no sinal, uma
    série com um salto implausível, uma leitura isolada que discorda das
    vizinhas.

    Porque é que o número continua a ser utilizável, e porquê é preciso o
    campo `ressalva`: esconder um valor apenas porque o sensor o duvidou é
    devolver `sem_dado` a quem tem uma leitura boa, e quem apaga a ressalva
    volta a ter um `Medido` que mente. Entre "não mostrar", "mostrar sem
    aviso" e "mostrar com aviso" só a terceira é verdadeira.

    `ressalva` é texto **accionável** — "3 de 40 leituras fora de 2 desvios
    padrão", não "anomalia detectada". Um rótulo que não diz o que fazer é
    o mesmo defeito de `SemDado` sem motivo.
    """

    valor: Any
    fonte: str
    ressalva: str

    def __post_init__(self):
        if not (self.fonte or "").strip():
            raise ValueError(
                "Um MedidoComRessalva sem fonte não é um dado: é um número "
                "com roupa de dado."
            )
        if not (self.ressalva or "").strip():
            raise ValueError(
                "Um MedidoComRessalva sem `ressalva` é pior que um Medido: "
                "prometeu a ressalva e não a entrega. O produtor lê 'medido' "
                "e nunca soube que havia algo a duvidar. Se não há nada a "
                "dizer, o estado certo é `Medido`."
            )

    @property
    def estado(self) -> str:
        return Estado.MEDIDO_COM_RESSALVA


@dataclass(frozen=True)
class Suspect:
    """O sensor disse, e não é de confiança. O número não é utilizável.

    A violação aqui é de **plausibilidade física**: `NaN`, `Inf`, uma
    precipitação negativa, uma temperatura de 400 graus, uma humidity de
    900%. O sensor falou, e falou uma frase que a física não permite.

    Este é o estado que impede um `NaN` de chegar a um KPI. Sem ele, o
    `Medido` accepta o número — porque `Medido` só exige uma fonte, e o NaN
    tem uma fonte tan válida como o 23.5 — e o primeiro widget que faz
    `Math.min()` sobre ele fica com o resultado poisoned e não há nada no
    ecrã que diga porque.

    `valor` é `None` **de propósito**: o número não entra no cálculo. Fica o
    motivo, que é o que o produtor precisa de ver. Guardar o `NaN` e marcá-lo
    como suspect seria continuar a transportar um número que ninguém pode usar,
    e algum `float()` algures mais tarde deixa de o olhar.
    """

    motivo: str

    def __post_init__(self):
        if not (self.motivo or "").strip():
            raise ValueError(
                "Um Suspect sem motivo não é accionável: o produtor vê "
                "'suspect' e não sabe se o sensor avariou, se a ligação caiu "
                "ou se o valor era impossível."
            )

    @property
    def estado(self) -> str:
        return Estado.SUSPECT


@dataclass(frozen=True)
class SemDado:
    """Não há o que mostrar. E diz porquê — o motivo é accionável.

    "Sem dado" sem motivo obriga o produtor a adivinhar o que falta, e adivinhar
    mal num painel é pior do que não ter nada. A diferença entre "não há
    lançamentos" e "a consulta falhou" é a diferença entre ir ao cadastro e
    mudar de rede.
    """

    motivo: str

    def __post_init__(self):
        if not (self.motivo or "").strip():
            raise ValueError(
                "SemDado sem motivo não ajuda ninguém: o produtor vê 'sem dado' "
                "e não sabe se o trabalho dele se perdeu ou se falta preencher "
                "alguma coisa."
            )

    @property
    def estado(self) -> str:
        return Estado.SEM_DADO


@dataclass(frozen=True)
class Simulado:
    """Um número gerado. Não é proibido — é que se anuncia.

    Proibí-lo de todo seria perder o que a simulação serve: mostrar a uma
    pessoa o que a tela ficaria COM o dado, para ela decidir se vale a pena
    ir buscar o dado. O que não pode é ser indistinguível do medido.

    `gerador` é o nome do que gerou o número — não é decorativo: é o que
    permite responder "isto veio de onde?" dentro de seis meses, quando já
    ninguém se lembra.
    """

    valor: Any
    gerador: str

    def __post_init__(self):
        if not (self.gerador or "").strip():
            raise ValueError(
                "Um Simulado sem `gerador` não é rastreável. Daqui a seis "
                "meses ninguém se lembra de onde saiu o número, e um número "
                "que ninguém sabe de onde veio é um número que ninguém pode "
                "defender perante um auditor."
            )

    @property
    def estado(self) -> str:
        return Estado.SIMULADO


@dataclass(frozen=True)
class Declarado:
    """Um número que um PRODUTOR affirmed. Não é medição, e é por isso que
    existe esta classe.

    Este estado foi acrescentado depois de `Medido`, `SemDado` e `Simulado`, e
    é o único dos quatro que **não** vem de uma máquina. A sua regra está
    escrita em `app/validators.py:40-41`, e é a mesma que governa este
    ficheiro inteiro:

        o sistema nunca promove uma afirmação a medição.
        Quem mediu foi o sensor; quem afirmou foi a pessoa.

    Porque é que faltava, e porque as duas saídas ruins são mentira:

    1. Guardar como `Medido` — o painel passa a dizer "medido" onde houve um
       dígito. Apaga-se a distinção entre o que a máquina viu e o que a pessoa
       lembrou, e é essa distinção que sustenta a procedência auditável. Um
       comprador que pague mais por um lote rastreado está a pagar por uma
       declaração tratada como medição.
    2. Guardar como `SemDado` — errado pelo outro lado: *há* dado. O produtor
       disse 65 sc/ha. Isso não é ausência, e `sem_dado` faz o produtor
       desconfiar do sistema inteiro ao ver aquilo que ele próprio afirmou
       marcado como desconhecido.

    Vale também para o que é **importado** de uma planilha: é a declaração
    dele. Importar não torna medido. Uma planilha de 2019 continua `declarado`
    em 2026 — marcar isso como medido seria apagar de onde o número veio.
    """

    valor: Any
    #: Quem afirmou. Uma pessoa, ou "f.importada:planilha_produtor.xlsx".
    #: Sem isto, "declarado" é uma etiqueta e não um responsável.
    por: str

    def __post_init__(self):
        if not (self.por or "").strip():
            raise ValueError(
                "Um Declarado sem `por` não é auditável: fica 'alguém afirmou', "
                "que é a mesma vagueza que `Medido` resolve exigindo `fonte`. "
                "A pergunta 'quem disse este número?' tem de ter resposta."
            )

    @property
    def estado(self) -> str:
        return Estado.DECLARADO


#: O que pode ser embrulhado. Um `float` cru NÃO entra: essa é a regra
#: inteira, escrita num tipo.
Valor = Medido | SemDado | Simulado | Declarado | MedidoComRessalva | Suspect


def declarar(valor, por: str) -> Declarado:
    """Atalho para o que o produtor affirms.

    O par de `medir()`: onde aquele diz "isto veio do banco, e a fonte é esta",
    este diz "isto não veio de sensor nenhum — alguém o affirmed, e foi este".

    A separação existe porque as duas coisas não podem sergravadas na mesma
    coluna sem que uma tenha de mentir. Ver `validators.py:19-46`.
    """
    if valor is None or valor == "":
        return SemDado("O produtor não affirmed este valor.")
    return Declarado(valor, por)


def medir(valor, fonte: str) -> Medido | SemDado:
    """Atalho para o caso comum, e o ponto onde a EXCEÇÃO se decide.

    Um valor que o banco devolveu como `None` é `SemDado`, não `Medido(0)`.
    Esta é a conversão que mais vezes esteve errada no Ampliagro: uma área
    que ninguém mediu devolvia 1, um custo sem lançamentos devolvia 0, e os
    dois liam-se como afirmações. `None` e 0 são frases opostas, e o `or 0.0`
    que as juntava era um `if` a engolir a diferença.
    """
    if valor is None or valor == "":
        return SemDado("O valor não existe no registo.")
    return Medido(valor, fonte)


def serializar(valor: Valor, *, chave: str) -> dict[str, Any]:
    """Escreve um valor embrulhado no formato que o frontend já consome.

    O formato NÃO muda — é o mesmo `{custo_por_ha: 418.57, fonte_dado: "medido"}`
    que o palco já lê. O que muda é que este é o ÚNICO caminho para escrever
    um número, e ele não sabe escrever um número sozinho.

    `sem_dado` não escreve o valor: escreve `None` e o motivo. Um `0` aqui
    seria a mentira que este módulo existe para eliminar.
    """
    if isinstance(valor, Medido):
        return {chave: valor.valor, "fonte_dado": Estado.MEDIDO, "fonte": valor.fonte}
    if isinstance(valor, Simulado):
        return {
            chave: valor.valor,
            "fonte_dado": Estado.SIMULADO,
            "fonte": valor.gerador,
        }
    if isinstance(valor, Declarado):
        # `fonte` e não `por` no JSON: o palco já lê `fonte` para os números que
        # vieram de uma máquina, e um consumidor que só conhece essa chave
        # passava a mostrar um dado declarado como se fosse medido — que é o
        # defeito que este estado veio evitar. A MESMA chave, o mesmo formato,
        # e o `fonte_dado` diz qual dos dois é.
        return {
            chave: valor.valor,
            "fonte_dado": Estado.DECLARADO,
            "fonte": valor.por,
        }
    if isinstance(valor, SemDado):
        return {chave: None, "fonte_dado": Estado.SEM_DADO, "motivo": valor.motivo}
    if isinstance(valor, MedidoComRessalva):
        # O número SAI, com a ressalva ao lado. `None` aqui seria dizer "não
        # há dado" quando há — e há, com uma dúvida. Ver a nota da classe.
        return {
            chave: valor.valor,
            "fonte_dado": Estado.MEDIDO_COM_RESSALVA,
            "fonte": valor.fonte,
            "ressalva": valor.ressalva,
        }
    if isinstance(valor, Suspect):
        # `None` e NÃO o valor. Um NaN que chega ao painel é um NaN que
        # alguém vai somar. Ver a nota da classe.
        return {chave: None, "fonte_dado": Estado.SUSPECT, "motivo": valor.motivo}

    # NÃO É UMA MEDIÇÃO.
    #
    # Um rótulo ("tudo o que está registado"), um ano (2025), uma lista de
    # séries, uma coluna de tabela. Embrulhar isto em `Medido` seria a mesma
    # mentira pelo outro lado: um `periodo` não tem fonte porque nao e lido de
    # lado nenhum.
    #
    # E — o que importa — passar por aqui NÃO escreve `fonte_dado`. Se
    # escrevesse, o último campo do config determinaria o estado do config
    # inteiro, e um `kpi-custo` com três números bons e um rótulo no fim
    # voltaria a ser `sem_dado` por causa de uma palavra.
    return {chave: valor}


def serializar_tudo(valores: dict[str, Valor]) -> dict[str, Any]:
    """Serializa um config inteiro."""
    saida: dict[str, Any] = {}
    for chave, valor in valores.items():
        saida.update(serializar(valor, chave=chave))
    return saida


#: Um `config` que tenha passado por aqui tem `fonte_dado` no topo. Um que não
#: passou, não tem. E a diferença é visível sem ler o código.
def tem_proveniencia(config: dict[str, Any]) -> bool:
    return isinstance(config, dict) and "fonte_dado" in config
