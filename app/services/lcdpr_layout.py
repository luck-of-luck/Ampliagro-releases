"""O layout do LCDPR, num sítio só.

POR QUE ESTE FICHEIRO EXISTE
============================
MEDIDO 2026-10-04: o Ampliagro tinha **dois** geradores de ficheiro LCDPR com
layouts **incompativeis**, e ambos estavam em producao:

  - `app/services/lcdpr.py`       -> `LCDPRGenerator`
      chamado por `app/api/views/financial.py:436` (API DRF)
      e por `app/ia/intents3.py:1006` (a IA, no intent de exportar)

  - `app/services/lcdpr_export.py` -> `LCDPRExporter`
      chamado por `app/views/financeiro.py:137` (o BOTAO da UI)

O `tests/test_lcdpr_fiscal_unico.py` já registava que ha tres geradores e que
o teste so auditava um — mas auditava o **separador decimal**, e nao o
**layout**. Os dois geradores divergem no separador decimal E na ordem e no
numero dos campos. O divergences do layout nao tinha nenhum teste.

O QUE ESTE FICHEIRO FAZ
=======================
E' a **fonte unica da ordem dos campos**. Nao decide valores de negocio —
so declara, para cada registo, quantos campos existem e em que ordem. Um
gerador que escreva `Q100` com 12 campos quando a ordem aqui diz 13 levanta
erro no proprio momento, em vez de o ficheiro ser rejeitado em Abril.

O QUE NAO ESTE FICHEIRO INVENTA
===============================
As listas de campos abaixo sao as que constam do **Manual de Preenchimento do
LCDPR, leiaute 1.3** (Receita Federal), nos Registros cujo enunciado de campos
a pesquisa viu por inteiro: `0000`, `0010`, `Q100`, `Q200`, `9999`.

`0030`, `0040`, `0045` e `0050` **nao** estao aqui. O enunciado de campos
completo deles nao foi obtido — o manual é um PDF que a ferramenta de fetch nao
consegue extrair, e escrever um registo fiscal com campos inventados e' PIOR
do que nao o escrever: o produtor levaria um ficheiro rejeitado em vez de um
erro honesto. Ficam como estao, e `PENDENTE_CONFORMIDADE` marca o que falta
para eles serem validados contra o manual.

O PRINCIPIO
===========
> Numa saida fiscal, um campo que nao se sabe nao se preenche com um palpite.
> Preenche-se a falta, ou o sistema diz que nao sabe.

"""

from __future__ import annotations

# ──────────────────────────────────────────────────────────────────────────
# Versao do leiaute
# ──────────────────────────────────────────────────────────────────────────
#: Codigo da versao do leiaute, escrito no registo 0000. Ato Declaratorio
#: Executivo no 1/2020 dispoe sobre o leiaute 1.3.
VERSAO_LEIAUTE = "0013"

#: Identificador de tipo de arquivo no registo 0000. O manual escreve
#: literalmente `LCDPR` neste campo.
TIPO_ARQUIVO = "LCDPR"

# ──────────────────────────────────────────────────────────────────────────
# Dominios de valores (o manual escreve-os entre colchetes)
# ──────────────────────────────────────────────────────────────────────────

#: `0010.FORMA_APURACAO` — como o resultado da atividade rural e' apurado.
#: 1 = apurou com base nos lancamentos do Livro Caixa
#: 2 = apurou pelo art. 5o da Lei 8.023/1990 (20% da receita bruta)
FORMA_APURACAO_LIVRO_CAIXA = "1"
FORMA_APURACAO_20_POR_CENTO = "2"
FORMAS_APURACAO = (FORMA_APURACAO_LIVRO_CAIXA, FORMA_APURACAO_20_POR_CENTO)

#: `Q100.TIPO_LANC` — tipo do lancamento.
TIPO_LANC_RECEITA = "1"
TIPO_LANC_CUSTEIO_E_INVESTIMENTO = "2"
TIPO_LANC_ADIANTAMENTO = "3"
TIPOS_LANCAMENTO = (
    TIPO_LANC_RECEITA,
    TIPO_LANC_CUSTEIO_E_INVESTIMENTO,
    TIPO_LANC_ADIANTAMENTO,
)

#: `Q100.TIPO_DOC` — tipo do documento comprovatorio.
TIPO_DOC_NOTA_FISCAL = "1"
TIPO_DOC_FATURA = "2"
TIPO_DOC_RECIBO = "3"
TIPO_DOC_CONTRATO = "4"
TIPO_DOC_FOLHA_PAGAMENTO = "5"
TIPO_DOC_OUTROS = "6"
TIPOS_DOCUMENTO = (
    TIPO_DOC_NOTA_FISCAL,
    TIPO_DOC_FATURA,
    TIPO_DOC_RECIBO,
    TIPO_DOC_CONTRATO,
    TIPO_DOC_FOLHA_PAGAMENTO,
    TIPO_DOC_OUTROS,
)

#: `Q100.COD_CONTA` — casos especiais que nao sao uma conta do registo 0050.
#: O manual: "Caso tenha sido pago em especie, registrar como '000' e, caso
#: utilize numerario em transito, utilizar o codigo '999'".
COD_CONTA_ESPECIE = "000"
COD_CONTA_TRANSITO = "999"

#: `Q100.NAT_SLD_FIN` e `Q200.NAT_SLD_FIN` — natureza do saldo final.
#: O manual escreve o dominio como `[N:P]`: **Negativo** ou **Positivo**.
#:
#: ISTO FOI UM BUG. `LCDPRExporter` escrevia `S` para saldo positivo:
#:
#:     sld_str = f"{valor} {'S' if saldo >= 0 else 'N'}"
#:
#: `S` nao pertence a `[N:P]`. O validador da Receita le o dominio e rejeita.
#: Como o erro so aparece na entrega, com multa, em cima de um sistema que
#: nao se queixou — e o produtor nunca mais sabe porque o ficheiro foi
#: recusado. Corrigido em `NAT_SLD_POSITIVO`/`NAT_SLD_NEGATIVO`.
NAT_SLD_NEGATIVO = "N"
NAT_SLD_POSITIVO = "P"
NATUREZAS_SALDO = (NAT_SLD_NEGATIVO, NAT_SLD_POSITIVO)

# ──────────────────────────────────────────────────────────────────────────
# Ordem dos campos, por registo
# ──────────────────────────────────────────────────────────────────────────

#: Registro 0000 — Abertura do Arquivo Digital e Identificacao da Pessoa Fisica.
#:
#: A linha de exemplo do manual e':
#:
#:     |0000|LCDPR|0013|11111111191|JOSÉ DA SILVA|0|0||01012019|31122019|
#:
#: Repara que `dt_ini` e `dt_fim` sao os **ultimos dois** campos, precedidos
#: pelo indicador de inicio de periodo e pela situacao especial. O
#: `LCDPRExporter` antigo escrevia `dt_ini`/`dt_fim` logo a seguir ao nome,
#: o que deslocava todos os campos seguintes uma posicao para a esquerda.
CAMPOS_0000 = (
    "REG",
    "TIPO_ARQUIVO",
    "VERSAO_LEIAUTE",
    "CPF",
    "NOME",
    "IND_INI_PERIODO",
    "SIT_ESPECIAL",
    "DATA_SIT_ESPECIAL",
    "DT_INI",
    "DT_FIM",
)

#: Indicador de inicio de periodo: 0 = regular, comecando no primeiro dia do ano.
IND_INI_PERIODO_REGULAR = "0"

#: Situacao especial: 0 = normal, sem evento.
SIT_ESPECIAL_NORMAL = "0"

#: Registro 0010 — Parametros de Tributacao. Um campo: a forma de apuracao.
CAMPOS_0010 = ("REG", "FORMA_APURACAO")

#: Registro Q100 — Demonstrativo do Resultado da Atividade Rural.
#:
#: Treze campos. O manual lista, por ordem:
#:
#:     REG | DATA | COD_IMOVEL | COD_CONTA | NUM_DOC | TIPO_DOC | HISTORICO |
#:     CNPJ_CPF_PARTICIPANTE | TIPO_LANC | VL_ENTRADA | VL_SAIDA |
#:     SLD_FIN | NAT_SLD_FIN
#:
#: DOIS ERROS AQUI, ambos do `LCDPRExporter`:
#:
#: 1. `SLD_FIN` e `NAT_SLD_FIN` eram escritos **juntos num campo so**,
#:    separados por um espaco. Sao dois campos no manual.
#: 2. `NAT_SLD_FIN` escrevia `S`/`N` em vez de `P`/`N` — ver `NATUREZAS_SALDO`.
#:
#: E o `LCDPRGenerator` erra pelo outro lado: põe o CPF do participante na
#: posicao do numero do documento (5.a em vez de 8.a), e escreve o historico
#: como campo vazio.
CAMPOS_Q100 = (
    "REG",
    "DATA",
    "COD_IMOVEL",
    "COD_CONTA",
    "NUM_DOC",
    "TIPO_DOC",
    "HISTORICO",
    "CNPJ_CPF_PARTICIPANTE",
    "TIPO_LANC",
    "VL_ENTRADA",
    "VL_SAIDA",
    "SLD_FIN",
    "NAT_SLD_FIN",
)

#: Registro Q200 — Resumo Mensal do Demonstrativo. Seis campos.
#:
#: `SLD_FIN` do Q200 e' o saldo **cumulativo ate o mes**: o saldo dos lancamentos
#: do mes acrescido do saldo final do mes imediatamente anterior. Nao e' o saldo
#: do mes isolado.
CAMPOS_Q200 = (
    "REG",
    "MES",
    "VL_ENTRADA",
    "VL_SAIDA",
    "SLD_FIN",
    "NAT_SLD_FIN",
)

#: Registro 9999 — Identificacao do Signatario e Encerramento.
CAMPOS_9999 = ("REG", "QTD_LINHAS")

# ══════════════════════════════════════════════════════════════════════════
# ENUNCIADO OFICIAL — transcrito em 2026-10-05
# ══════════════════════════════════════════════════════════════════════════
#
# FONTE PRIMARIA, e' a secção que faltava:
#   * Manual de Preenchimento do LCDPR 1.3 — Receita Federal, secção 3.3
#     "Campos dos Registros", gov.br/receitafederal/.../manual-lcdpr-1-3
#   * Leiaute do LCDPR 1.3 — Receita Federal, tabela de registos
#     (4-leiaute-1-3.xlsx)
#
# Estes quatro registos estavam em `REGISTOS_SEM_ENUNCIADO_VALIDADO` porque o
# enunciado nao tinha sido obtido. **Foi obtido.** O que fica abaixo e'
# transcricao, nao interpretacao: nomes e ordem, como o manual lista.
#
# Os nomes vem SEM ACENTO porque sao identificadores usados em codigo. O manual
# escreve `COD_IMÓVEL`, `NOME_IMÓVEL`, `TIPO_EXPLORAÇÃO`; o `Q100` ja usava
# `COD_IMOVEL`, e um ficheiro com nomes divergentes para o mesmo campo e' pior
# do que um sem acento.

#: Registro 0030 — Dados Cadastrais. O [1:1], obrigatorio. Dez campos.
#: O manual marca `COMPL` e `NUM_TEL` como **Nao** obrigatorios; todos os
#: outros sao **Sim** — incluindo `COD_MUN` e `CEP`, que o exportador emitia
#: vazios.
CAMPOS_0030 = (
    "REG",
    "ENDERECO",
    "NUM",
    "COMPL",
    "BAIRRO",
    "UF",
    "COD_MUN",
    "CEP",
    "NUM_TEL",
    "EMAIL",
)

#: Registro 0040 — Cadastro dos Imoveis Rurais. [1:N], obrigatorio.
#: **Dezassete campos.** O exportador escrevia treze, e a partir do 5.o todos
#: estavam deslocados: `caepf` ia para `CAD_ITR`, a inscricao estadual para
#: `CAEPF`, o nome para `INSCR_ESTADUAL`, o endereco para `NOME_IMOVEL`, e a
#: participacao para `CEP`. Ver `PENDENTE_0040`.
CAMPOS_0040 = (
    "REG",
    "COD_IMOVEL",
    "PAIS",
    "MOEDA",
    "CAD_ITR",
    "CAEPF",
    "INSCR_ESTADUAL",
    "NOME_IMOVEL",
    "ENDERECO",
    "NUM",
    "COMPL",
    "BAIRRO",
    "UF",
    "COD_MUN",
    "CEP",
    "TIPO_EXPLORACAO",
    "PARTICIPACAO",
)

#: Registro 0045 — Cadastro de Terceiros. [1:N].
#: **Condicionalmente obrigatorio**: se `0040.PARTICIPACAO` for menor que 100%
#: **ou** `0040.TIPO_EXPLORACAO` for diferente de "1". Esta e' a condicao
#: completa, e o manual escreve-a nos dois ramos da tabela.
#:
#: O 4.o campo aparece como `ID_CONTRAPARTE` no manual e como
#: `CPF_CONTRAPARTE` na documentacao da Senior. **Coincidem em posicao e
#: tamanho (11, 14)**; so o nome diverge. Adota-se o do manual, e a divergencia
#: fica registada aqui em vez de escolhida em silencio.
CAMPOS_0045 = (
    "REG",
    "COD_IMOVEL",
    "TIPO_CONTRAPARTE",
    "ID_CONTRAPARTE",
    "NOME_CONTRAPARTE",
    "PERC_CONTRAPARTE",
)

#: Tipos de contraparte, campo 3 do 0045. Lista fechada do manual.
TIPOS_CONTRAPARTE = {
    "1": "Condomínio",
    "2": "Arrendador",
    "3": "Parceiro",
    "4": "Comodante",
    "5": "Outros",
}

#: Registro 0050 — Cadastro das Contas Bancarias. [1:N], obrigatorio. Sete
#: campos. **Este ja estava conforme** — contagem e ordem correctas.
CAMPOS_0050 = (
    "REG",
    "COD_CONTA",
    "PAIS_CTA",
    "BANCO",
    "NOME_BANCO",
    "AGENCIA",
    "NUM_CONTA",
)

#: Mapa de registo -> campos, para validacao.
CAMPOS_POR_REGISTRO = {
    "0000": CAMPOS_0000,
    "0010": CAMPOS_0010,
    "0030": CAMPOS_0030,
    "0040": CAMPOS_0040,
    "0045": CAMPOS_0045,
    "0050": CAMPOS_0050,
    "Q100": CAMPOS_Q100,
    "Q200": CAMPOS_Q200,
    "9999": CAMPOS_9999,
}

# ──────────────────────────────────────────────────────────────────────────
# Registros que EXISTEM no manual e ainda NAO tem enunciado validado aqui
# ──────────────────────────────────────────────────────────────────────────

#: O manual tem estes registos. Nao estao em `CAMPOS_POR_REGISTRO` porque o
#: enunciado de campos nao foi obtido — ver o cabecalho. Um gerador que precise
#: de um destes tem de o declarar aqui explicitamente, com a fonte, e nao
#: inventar a ordem.
REGISTROS_SEM_ENUNCIADO_VALIDADO = {
    "0030": "Cadastro do produtor rural pessoa fisica declarante",
    "0040": "Cadastro dos imoveis rurais (CAFIR, CAEPF, tipo de exploracao)",
    "0045": "Cadastro de terceiros — **OBRIGATORIO**, ver `PENDENTE_0045`",
    "0050": "Cadastro das contas Bancarias",
}

PENDENTE_0045 = """
REGISTRO 0045 — CADASTRO DE TERCEIROS: IMPLEMENTADO, MAS NAO CONFORME

MEDIDO 2026-10-04: o registo 0045 nao existia em nenhum dos dois geradores.
Sem ele o ficheiro LCDPR nao valida no e-CAC, porque o Q100 exige o
CNPJ/CPF do participante da relacao contratual e esse dado tem de estar
declarado num registo do Bloco 0.

`LancamentoFinanceiro` tem `participante` e `participante_doc`, portanto o
DADO existe. O que falta e' o enunciado de campos do 0045, e um ficheiro
fiscal nao se escreve por suposicao.

O QUE ESTA FEITO: o bloco 0045 e' escrito, com um codigo sequencial, o
CPF/CNPJ e o nome de cada terceiro distinto.

O QUE FALTA: a posicao e o nome exactos dos campos seguintes no enunciado
oficial. Um gerador que remova ou acrescente um campo sem o manual muda o
ficheiro de forma silenciosa.

COMO FECHAR: abrir o Manual de Preenchimento do LCDPR leiaute 1.3, capitulo
"3.5 Leiaute dos Registros", e transcrever `0045` para `CAMPOS_0045` ao lado
dos outros. Ate' la, `TEMPO_0045_VALIDADO` e' `False` e o teste
`tests/test_lcdpr_conformidade.py` diz isso ao leitor em vez de fingir que o
registo esta certo.
"""


class LayoutInvalido(ValueError):
    """Uma linha nao corresponde ao enunciado de campos do registo.

    Existe para o erro aparecer **quando o ficheiro e' gerado**, e nao quatro
    meses depois na entrega. Um `ValueError` com o nome do registo e a contagem
    esperada diz ao programador exactamente o que falta; um ficheiro silenciosamente
    errado diz ao produtor que a Receita o recusou, sem dizer porquê.
    """

    def __init__(self, registro: str, esperado: int, recebido):
        self.registro = registro
        self.esperado = esperado
        self.recebido = len(recebido)

        # NOTA DE CONCURENCIA (2026-10-04): esta chamada estava ao nivel do
        # modulo, fora do `__init__`, e por isso levava
        # `RuntimeError: super(): no arguments` sempre que uma linha do LCDPR
        # tinha o numero errado de campos — ou seja, sempre que o gerador
        # tentava dizer o que estava errado. O erro de contagem de campos
        # ficava tapado por um erro de programacao.

        super().__init__(
            f"Registo {registro}: o LCDPR espera {esperado} campos e a linha "
            f"tem {len(recebido)}. Enunciado: "
            # MEDIDO 2026-10-05: usava-se `registo`, que nao existe neste
            # scope — o parametro chama-se `registro`. O resultado era um
            # `NameError` a *construir a excecao*, que escondia o erro real
            # (a contagem de campos) debaixo de um erro de programacao.
            #
            # O `get` com `()` tambem estava errado: sem o registo no
            # enunciado, `join(())` devolve string vazia e a mensagem perdia
            # a unica parte que dizia o que esperar.
            # NOTA DE CONCURENCIA (2026-10-04): escrevia-se
            # `CAMPOS_POR_REGISTRO`, que nao existe — o nome do modulo e'
            # `CAMPOS_POR_REGISTRO` (linha 205). O `NameError`happened dentro
            # do `__init__` de `LayoutInvalido`, ou seja: sempre que uma
            # linha do LCDPR tinha o numero errado de campos, a excecao que
            # devia explicar o erro falhava a ser construida, e o produtor
            # recebia um `NameError` em vez de "esperava 13 campos, tem 14".
            f"{', '.join(CAMPOS_POR_REGISTRO.get(registro) or ['(registo desconhecido — o enunciado nao esta carregado)'])}. "
            "Um campo a mais ou a menos desloca todos os seguintes e o "
            "validador da Receita recusa o ficheiro."
        )


def linha(registro: str, *valores) -> str:
    """Monta uma linha do LCDPR e **verifica a contagem** de campos.

    `|Q100|...` fica com um separador `|` no fim, como no enunciado do manual.

    Levanta `LayoutInvalido` se o numero de campos nao bater certo com
    `CAMPOS_POR_REGISTRO`. E' a razao de este ficheiro existir: tornar um
    erro de layout impossivel de ignorar.

    OFF-BY-ONE, E EU TROPEEI NELE (MEDIDO 2026-10-05)
    ================================================
    `CAMPOS_0000` tem **10** nomes, o primeiro dos quais e' `REG`. Mas quem
    chama `linha()` nao passa `REG`: a funcao prepoe o proprio nome do
    registo. A comparacao certa e' `len(valores) == len(CAMPOS) - 1`.

    Escrevi `len(valores) != len(esperado)` e o validador levantou
    `LayoutInvalido` no **primeiro** ficheiro gerado — sobre o registo 0000,
    com "a linha tem 9" quando a linha estava certa. O aviso是对的 sobre a
    contagem e' falso sobre a linha: eu estava a contar o `REG` duas vezes.

    Fica escrito porque o sintoma (excepcao num gerador que produz a linha
    correcta) faz pensar que o enunciado esta errado, e nao o codigo. O
    enunciado esta certo; o `-1` faltava.
    """
    esperado = CAMPOS_POR_REGISTRO.get(registro)
    if esperado is not None:
        # `REG` e' o primeiro campo do enunciado e nao vem em `valores`.
        esperado_valores = len(esperado) - 1
        if len(valores) != esperado_valores:
            raise LayoutInvalido(registro, esperado_valores, valores)
    return (
        "|"
        + registro
        + "|"
        + "|".join("" if v is None else str(v) for v in valores)
        + "|"
    )


def formatar_valor(valor) -> str:
    """Um valor monetario como o Leiaute 1.3 o escreve: PONTO decimal.

    MEDIDO 2026-10-05 (agente 9). Este numero andou em dois sitios e divergiu.

    `app/services/lcdpr.py::_formatar_valor` escrevia ponto. O
    `LCDPRExporter.formatar_valor` de `app/services/lcdpr_export.py` escrevia
    `f"{valor:.2f}".replace(".", ",")`, produzindo `1234,56` no ficheiro
    `LCDPR_<id>_<ano>.txt` — que e' exactamente o ficheiro que o produtor
    entrega no e-CAC.

    Virgula decimal e' o formato brasileiro de **TELA**. O Leiaute 1.3 e'
    texto delimitado por `|` com numero em ponto. Com virgula, o validador le
    a linha como texto ou recusa-a, e o problema so aparece em Abril, com
    multa, em cima de um sistema que nao se queixou.

    Fica aqui, e nao em nenhum dos dois geradores, porque este modulo e' o
    sitio onde as regras do Leiaute vivem: quem quiser saber "como e' que o
    Ampliagro escreve um valor" le uma pagina, e nao tres. Os dois geradores
    delegam aqui.

    As duas casas decimais mantem-se: o Leiaute e' um valor com duas casas, e
    um valor truncado aqui e' um valor diferente da ficha.

    O `None` e' declarado como `0.00` e nao levanta `TypeError`: um saldo a
    aberto tem `None` com frequencia, e `formatar_valor` e' chamado em
    caminhos onde isso nao pode ser uma avaria. A distincao entre "zero" e
    "nao ha valor" e' feita pelo chamador deixar o campo **vazio** — e o que
    `linha()` faz com `None`.
    """
    if valor is None:
        return "0.00"
    return f"{float(valor):.2f}"


def natureza_saldo(valor) -> str:
    """`P` para saldo maior ou igual a zero, `N` para negativo.

    Zero e' positivo: `P` significa "saldo credor", e um saldo exactamente zero
    nao e' um saldo devedor. O manual so diz `[N:P]`; o zero pertence ao
    credor por omissao no regime de caixa — e e' o que o `Q200` antigo ja
    fazia (`"P" if saldo >= 0 else "N"`), que estava certo.
    """
    return NAT_SLD_POSITIVO if float(valor) >= 0 else NAT_SLD_NEGATIVO


def validar_dominio(registro: str, campo: str, valor: str, dominio) -> None:
    """Recusa um valor fora do dominio que o manual declara entre colchetes.

    Chamar disto e' opcional, mas e' o que impede que `S` volte a entrar no
    lugar de `P` sem ninguem dar por isso.
    """
    if valor not in dominio:
        raise LayoutInvalido(
            registro,
            1,
            [f"{campo}={valor!r} fora de {dominio}"],
        )
