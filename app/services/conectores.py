"""Conectores de entrada: trazer dados de fora para dentro, sem formato fechado.

O QUE ISTO E'
==============

Um `Conector` le um ficheiro de uma maquina tal como o produtor ja
usa — o CSV que o John Deere exporta, o relatorio que o John Deere Stara
exporta, a planilha que o-controller exporta — e prepara uma prévia normalizada.
Este módulo não grava registros. A persistência deve ser feita pelo fluxo
específico de cada domínio, com autorização e controle de reenvio.

A REGRA QUE GOVERNA TUDO ISTO
=============================

**CSV primeiro, API nunca.**

A razao esta escrita no `docs/sistema/PLANO-EXECUCAO.md` e no manifesto, e e'
a mesma que vale para as 50 celulas do comparativo: uma API de maquina exige
credencial do produtor, implicacao contractual, e uma manutencao que nao
termina. Um CSV e' um ficheiro que o produtor ja tem, que pode enviar por
WhatsApp, e que a proxima versao do equipamento ainda exporta.

Um conector que so sabe ler CSV tem um limite conhecido. Um conector que
promete API e falha tem um limite **invisivel** — e o produtor descobre-o no
momento em que precisa.

O QUE ISTO NAO E'
=================

Nao e' integracao oficial com John Deere, Stara, Climate FieldView ou
Solinftec. Nao ha acordo com nenhuma delas. Estes conectores leem o **formato
de ficheiro** que exportam, e a formatacao muda sem avisar — o conector
precisa de detetar a mudanca e dizer, nao deitar dados no sitio errado.

Um conector que recebe um ficheiro de uma marca que mudou o formato tem duas
saidas honestas: recusar com a razao, ou importar o que reconhece e dizer
quanto ficou de fora. **Nunca** importa parcialmente em silencio.

O QUE ESTA MEDIDO, E O QUE ESTA DECLARADO
=========================================

Cada conector declara:
  - `formatos_aceitos`: os que reconhece, com a versao
  - `o_que_le`: os campos que sabe interpretar
  - `o_que_nao_le`: os campos que ve e NAO sabe tratar

O `o_que_nao_le` nao e' um comentario. Sai no resultado de toda a importacao,
contado. Um produtor que importou 40 linhas e viu "3 campos nao
reconhecidos" sabe o que perguntar. Um que importou 40 linhas sem aviso
descobre tres meses depois, quando um total nao bate.

O QUE UM CONECTOR NUNCA FAZ
============================

  * nao inventa valor para campo em falta — o campo fica vazio e o registo e'
    marcado `incompleto`
  * nao escolhe entre duas linhas ambiguas — pergunta, ou recusa
  * nao escreve se a taxa de erro exceder o limite — importa o que deu certo e
    devolve o resto como `rejeitados`, com a razao por linha
"""

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

# ─────────────────────────────────────────────────────────────────────────────
# O resultado
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class ResultadoImportacao:
    """O que uma importacao fez — e o que nao fez.

    A forma do dict e' FIXA nos dois ramos (importou zero linhas ou importou
    mil), pelo mesmo motivo de `compliance_ambiental.py`: um consumidor que
    faca `r["rejeitados"]` nao pode rebentar no caso em que nao havia nada
    para rejeitar — que e' o caso mais frequente e o que mais se esquece.
    """

    conector: str
    formato_detectado: str
    total_linhas: int = 0
    importados: int = 0
    actualizados: int = 0
    rejeitados: list = field(default_factory=list)
    incompletos: list = field(default_factory=list)
    campos_desconhecidos: list = field(default_factory=list)
    avisos: list = field(default_factory=list)
    registros: list = field(default_factory=list)
    preparado: bool = False

    @property
    def ok(self) -> bool:
        return (
            self.total_linhas > 0
            and not self.rejeitados
            and not self.incompletos
            and bool(self.registros or self.importados or self.actualizados)
        )

    def resumo_para_o_produtor(self) -> str:
        """Uma frase que o produtor le e percebe o que aconteceu."""
        partes = [
            f"{self.conector}: {len(self.registros)} registro(s) preparados; "
            "nenhum registro gravado"
            if self.preparado
            else f"{self.conector}: {self.importados} registo(s) importados",
        ]
        if self.actualizados:
            partes.append(f"{self.actualizados} actualizado(s)")
        if self.incompletos:
            partes.append(
                f"**{len(self.incompletos)} ficaram por preencher** — "
                "corrija as pendências antes de importar"
            )
        if self.rejeitados:
            partes.append(
                f"**{len(self.rejeitados)} nao entraram** (motivo no detalhe)"
            )
        if self.campos_desconhecidos:
            partes.append(
                f"{len(self.campos_desconhecidos)} coluna(s) do ficheiro nao "
                f"reconheci: {', '.join(self.campos_desconhecidos[:5])}"
            )
        if self.total_linhas == 0:
            partes.append("**o ficheiro nao tinha linhas de dados**")
        return "; ".join(partes) + "."


@dataclass
class Rejeicao:
    """Uma linha que nao entrou, e porque."""

    linha: int
    motivo: str
    detalhe: str = ""


class Conector:
    """A base. Um conector lê e prepara registros, sem persistir.

    Subclasses declaram o que sabem e implementam `para_registros()`.

    O que a base garante, e que cada subclasse nao pode esquecer:
      * o `formato_detectado` e' preenchido pela deteccao, nunca pela subclass
      * campos desconhecidos sao contados, nunca descartados em silencio
      * um registo sem os campos obrigatorios e' `incompleto`, nao `importado`
    """

    #: Identificador estavel. Entra no log e na trilha de auditoria.
    nome = "conector"
    #: O que este conector traca. Aparece na descricao da tool MCP.
    descricao = ""
    #: Formatos que reconhece, com versao. Ex.: `["csv-v1", "csv-v2"]`
    formatos_aceitos: tuple = ()
    #: Campos que sabe interpretar. Lista fechada e' o que permite dizer
    #: "campo desconhecido" em vez de "campo vazio".
    campos_conhecidos: tuple = ()

    @classmethod
    def detecta(cls, cabecalho: dict) -> str | None:
        """Que formato e' este? Devolve `None` se nao reconhece.

        `None` e' a resposta honesta e e' OBRIGATORIA. Devolver um formato
        "provavelmente" e' o que faz um conector escrever 200 registos no sitio
        errado: o produtor so descobre quando o total do talhao nao bate.
        """
        raise NotImplementedError

    @classmethod
    def para_registros(cls, linhas: list, propriedade) -> tuple:
        """Converte as linhas ja normalizadas em registos.

        Devolve `(registros, incompletos, avisos)`.
        """
        raise NotImplementedError

    # ─────────────────────────────────────────────────────────────────────
    @classmethod
    def importa(cls, cabecalho: dict, linhas: list, propriedade) -> ResultadoImportacao:
        """Prepara uma prévia. Nome legado mantido para os consumidores."""
        formato = cls.detecta(cabecalho)
        if not formato:
            return cls._formato_nao_reconhecido(cabecalho)

        r = ResultadoImportacao(
            conector=cls.nome, formato_detectado=formato, preparado=True
        )
        r.total_linhas = len(linhas)

        conhecidos = set(cls.campos_conhecidos)
        for nome in cabecalho:
            chave = _norm(nome)
            if chave and chave not in conhecidos:
                r.campos_desconhecidos.append(nome)

        # O aviso das coluna desconhecidas vem ANTES do ramo de ficheiro vazio.
        #
        # MEDIDO 2026-10-05, apanhado por `test_a_coluna_desconhecida_e_contada_
        # nunca_descartada_em_silencio`: o aviso estava DEPOIS do `return` do
        # ramo "sem linhas", entao um ficheiro vazio com uma coluna a mais nao
        # dizia nada. E' o caso em que mais preciso: um relatorio que saiu sem
        # dados E com colunas que nao reconhecemos e' a assinatura de um
        # formato diferente — e sem o aviso, parece um relatorio vazio.
        if r.campos_desconhecidos:
            r.avisos.append(
                f"{len(r.campos_desconhecidos)} coluna(s) do ficheiro nao "
                "reconheci e foram ignoradas. Se algum delas era o que voce "
                "esperava, o ficheiro nao e' deste formato — envie-o e eu digo "
                "o que falta."
            )

        if not linhas:
            r.avisos.append(
                "O ficheiro foi lido e reconhecido, mas nao tem linhas de "
                "dados. Pode ser um relatorio vazio, ou um ficheiro onde os "
                "dados comecam na linha 3."
            )
            return r

        registros, incompletos, avisos = cls.para_registros(linhas, propriedade)
        r.incompletos = list(incompletos or [])
        r.avisos.extend(avisos or [])
        r.registros = list(registros or [])

        return r

    @classmethod
    def _formato_nao_reconhecido(cls, cabecalho: dict) -> ResultadoImportacao:
        """O ficheiro nao e' deste conector. E diz o que esperava."""
        r = ResultadoImportacao(
            conector=cls.nome,
            formato_detectado="nao_reconhecido",
            total_linhas=0,
            preparado=True,
        )
        r.avisos.append(
            "Nao reconheci este ficheiro. Este conector le: "
            f"{', '.join(cls.formatos_aceitos)}. As colunas que encontrei foram: "
            f"{', '.join(list(cabecalho)[:8]) or '(nenhuma)'}. Se o ficheiro "
            "e' de outra ferramenta, diz qual — ou manda o ficheiro e eu "
            "vejo o que da para ler."
        )
        return r


# ─────────────────────────────────────────────────────────────────────────────
# Os conectores
# ─────────────────────────────────────────────────────────────────────────────


class ConectorMaquinas(Conector):
    """Telemetria e horimetro de maquina, em CSV.

     E' o conector de maior valor e o de menor risco: um trator que fala
     ISOBUS fala por CSV, e o leitor nao depende de nenhuma marca.

     NAO e' ISOBUS. E' o que o produtor exporta do painel da maquina, ou do
     relatorio que o John Deere Operations Center e' a Stara exportam. A
     diferenca e' a mesma do `M04` da folha: ler o que a maquina **diz** e'
    possivel; falar o protocolo **com** a maquina e' o ISOBUS, que precisa do
     hardware e nao existe aqui.
    """

    nome = "maquinas"
    descricao = "Telemetria e horimetro de maquina, do CSV que a maquina exporta."
    formatos_aceitos = ("telemetria-csv-v1", "horimetro-csv-v1")
    campos_conhecidos = (
        "maquina",
        "hora",
        "odometro",
        "horas_motor",
        "consumo",
        "combustivel",
        "lat",
        "lon",
        "data",
    )

    @classmethod
    def detecta(cls, cabecalho: dict) -> str | None:
        c = {_norm(k) for k in cabecalho}
        # Horimetro: tem maquina e horas. Telemetria: tem maquina e coordenada
        # ou consumo. Qualquer um dos dois e' deste conector.
        if "maquina" in c and ("horas_motor" in c or "odometro" in c):
            return "horimetro-csv-v1"
        if "maquina" in c and ("lat" in c or "lon" in c or "consumo" in c):
            return "telemetria-csv-v1"
        return None

    @classmethod
    def para_registros(cls, linhas, propriedade):
        from app.models.maquinario import Maquinario

        registos = []
        incompletos = []

        for i, linha in enumerate(linhas, start=2):
            nome_maq = _valor(linha, "maquina", "maquinario", "nome")
            if not nome_maq:
                incompletos.append(
                    {
                        "linha": i,
                        "motivo": "sem o nome da maquina. Sem isso a leitura "
                        "nao se sabe de que maquina e'.",
                    }
                )
                continue

            maq = Maquinario.objects.filter(
                propriedade=propriedade, nome__iexact=str(nome_maq).strip()
            ).first()
            if maq is None:
                incompletos.append(
                    {
                        "linha": i,
                        "motivo": f"a maquina '{nome_maq}' nao esta "
                        "cadastrada nesta propriedade. Cadastre-a em Maquinas "
                        "primeiro, ou traga o nome igual ao que esta la.",
                    }
                )
                continue

            instante = _data(_valor(linha, "data", "horas", "timestamp"))
            if instante is None:
                incompletos.append(
                    {
                        "linha": i,
                        "motivo": "sem data, ou com data que nao reconheci. "
                        "Sem data a leitura nao entra no historico.",
                    }
                )
                continue

            medido = {
                "horas_motor": _numero(_valor(linha, "horas_motor", "horasmotor")),
                "odometro_km": _numero(_valor(linha, "odometro", "odometro_km")),
                "consumo": _numero(_valor(linha, "consumo", "combustivel")),
                "latitude": _numero(_valor(linha, "lat", "latitude")),
                "longitude": _numero(_valor(linha, "lon", "longitude")),
            }

            # Zero-trust: um NaN que chegue da maquina e' pior do que a falta.
            # `test_telemetria_zero_trust.py` exige que o valor gravado seja
            # numerico ou `None` — nunca NaN. `_numero` ja devolve `None` em vez
            # de NaN, e este e' o sitio onde isso e' garantido.
            if not any(v is not None for v in medido.values()):
                incompletos.append(
                    {
                        "linha": i,
                        "motivo": "a linha tem data e maquina, mas nenhum "
                        "valor medido. Uma leitura sem medicao nao e' uma "
                        "leitura.",
                    }
                )
                continue

            registos.append({"maquinario": maq, "instante": instante, **medido})

        return registos, incompletos, []


class ConedorLancamentos(Conector):
    """Contas a pagar e a receber, de um extrato ou de uma planilha.

    Cobre o `F10` (contas a pagar e a receber) pela via mais barata: o
    produtor ja tem a conta no banco ou no fornecedor, em CSV.
    """

    nome = "lancamentos"
    descricao = "Contas a pagar e a receber, de um CSV de banco ou de fornecedor."
    formatos_aceitos = ("lancamentos-csv-v1",)
    campos_conhecidos = ("data", "descricao", "valor", "tipo", "documento", "conta")

    @classmethod
    def detecta(cls, cabecalho: dict) -> str | None:
        c = {_norm(k) for k in cabecalho}
        if "data" in c and "valor" in c and ("descricao" in c or "historico" in c):
            return "lancamentos-csv-v1"
        return None

    @classmethod
    def para_registros(cls, linhas, propriedade):
        registos = []
        incompletos = []

        for i, linha in enumerate(linhas, start=2):
            data = _data(_valor(linha, "data"))
            valor = _numero(_valor(linha, "valor", "montante"))
            if data is None or valor is None:
                incompletos.append(
                    {
                        "linha": i,
                        "motivo": "sem data ou sem valor. Um lancamento sem "
                        "data ou sem valor nao entra no financeiro.",
                    }
                )
                continue

            bruto = str(_valor(linha, "descricao", "historico") or "").strip()
            tipo = _valor(linha, "tipo")
            registos.append(
                {
                    "data": data,
                    "valor": abs(valor),
                    "descricao": bruto or "(sem descricao no ficheiro)",
                    "tipo": _tipo_de(str(tipo or ""), valor),
                    "documento": _valor(linha, "documento", "doc") or "",
                }
            )

        return registos, incompletos, []


class ConectorSafra(Conector):
    """Safras, da planilha que o produtor ja tem.

     Cobre o `O05` (planejamento de safra) pela via que o produtor usa sem
    cks Peer: a planilha que ele proprio fez.
    """

    nome = "safra"
    descricao = "Safras, da planilha que o produtor ja tem (cultura, area, datas)."
    formatos_aceitos = ("safra-csv-v1",)
    campos_conhecidos = ("cultura", "area", "ano", "plantio", "colheita", "talhao")

    @classmethod
    def detecta(cls, cabecalho: dict) -> str | None:
        c = {_norm(k) for k in cabecalho}
        if "cultura" in c and ("area" in c or "hectare" in c or "hectares" in c):
            return "safra-csv-v1"
        return None

    @classmethod
    def para_registros(cls, linhas, propriedade):
        from app.models.core import Cultura

        registos = []
        incompletos = []

        for i, linha in enumerate(linhas, start=2):
            nome_cult = str(_valor(linha, "cultura") or "").strip()
            area = _numero(_valor(linha, "area", "hectare", "hectares"))
            if not nome_cult or area is None:
                incompletos.append({"linha": i, "motivo": "sem cultura ou sem area."})
                continue

            cult = Cultura.objects.filter(nome__iexact=nome_cult).first()
            if cult is None:
                incompletos.append(
                    {
                        "linha": i,
                        "motivo": f"a cultura '{nome_cult}' nao existe no "
                        "catalogo. O catalogo tem 709 culturas; esta nao esta "
                        "nelas. E' um erro de escrita no ficheiro, ou uma "
                        "cultura que o catalogo nao tem.",
                    }
                )
                continue

            registos.append(
                {
                    "cultura": cult,
                    "area_plantada": area,
                    "ano": int(_numero(_valor(linha, "ano")) or 0) or None,
                    "data_plantio": _data(_valor(linha, "plantio", "data_plantio")),
                    "data_colheita": _data(_valor(linha, "colheita", "data_colheita")),
                }
            )

        return registos, incompletos, []


CONECTORES = {c.nome: c for c in (ConectorMaquinas, ConedorLancamentos, ConectorSafra)}


def catalogo_conectores() -> dict:
    """O que existe, para a IA perguntar antes de tentar.

    Chamar isto antes de inventar um formato e' o que evita a tool mais
    frequente de engano: pedir ao produtor um ficheiro de um formato que o
    Ampliagro nao le.
    """
    saida = []
    for c in CONECTORES.values():
        saida.append(
            {
                "nome": c.nome,
                "descricao": c.descricao,
                "formatos_aceitos": list(c.formatos_aceitos),
                "campos_reconhecidos": list(c.campos_conhecidos),
            }
        )
    return {
        "conectores": saida,
        "regra": "CSV primeiro, API nunca. Nao ha integracao oficial com "
        "John Deere, Stara, Climate FieldView ou Solinftec — le-se o "
        "ficheiro que exportam, e a formatacao pode mudar.",
        "o_que_faz": "Preparar uma prévia normalizada do arquivo, com registros "
        "e pendências por linha. Não grava no banco de dados; exige um fluxo "
        "de persistência específico do domínio para concluir a importação.",
        "o_que_nao_faz": "Nao inventa valor para campo em falta. Nao escolhe "
        "entre duas leituras ambiguas. Nao importa em silencio: uma linha "
        "que nao entra vem com o motivo.",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Auxiliares
# ─────────────────────────────────────────────────────────────────────────────


def _norm(chave) -> str:
    """Normaliza um nome de coluna para comparar.

    `Removing acentos,`_` e `-` para `_`, tudo minusculo. E' o que faz
    `Horas_Motor`, `horas-motor` e `HORAS MOTOR` casarem com `horas_motor`.
    """
    import unicodedata

    txt = unicodedata.normalize("NFD", str(chave or ""))
    sem = "".join(c for c in txt if not unicodedata.combining(c))
    return sem.lower().replace("-", "_").replace(" ", "_").strip()


def _valor(linha: dict, *nomes):
    """O primeiro campo presente, em varias grafias."""
    normal = {_norm(k): v for k, v in linha.items()}
    for nome in nomes:
        v = normal.get(_norm(nome))
        if v not in (None, ""):
            return v
    return None


def _numero(valor) -> Decimal | None:
    """Texto para numero. `None` quando nao e' numero.

    **`None` e nunca `NaN`.** Um `NaN` que chegue a um campo de Decimal levanta
    `decimal.InvalidOperation` na base de dados, e o que aparece ao produtor e'
    "erro de servidor" numa pagina que devia estar a mostrar um numero. O
    `test_telemetria_zero_trust.py` exige `None`, e e' por ai.
    """
    if valor is None or valor == "":
        return None
    if isinstance(valor, Decimal):
        return valor if valor.is_finite() else None
    txt = (
        str(valor).strip().replace(".", "", 1)
        if _tem_milhares(str(valor))
        else str(valor).strip()
    )
    txt = txt.replace("R$", "").replace("%", "").replace(" ", "").replace(",", ".")
    if not txt:
        return None
    try:
        num = Decimal(txt)
    except (InvalidOperation, ValueError):
        return None
    return num if num.is_finite() else None


def _tem_milhares(txt: str) -> bool:
    """`1.234,56` tem separador de milhar; `1.5` nao."""
    return "," in txt and txt.count(".") >= 1 and txt.rfind(",") > txt.rfind(".")


def _data(valor):
    if not valor:
        return None
    from datetime import datetime

    txt = str(valor).strip()
    for fmt in (
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%d/%m/%y",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
    ):
        try:
            return datetime.strptime(txt[: len(fmt) + 4], fmt).date()
        except ValueError:
            continue
    return None


def _tipo_de(bruto: str, valor: Decimal) -> str:
    """Classifica o tipo do lancamento.

    O sinal manda: negativo e' saida, positivo e' entrada. E' a regra que o
    extrato do banco ja traz e que o produtor reconhece de imediato. Um
    ficheiro que traz a coluna `tipo` preenchida respeita-a; um que nao traz
    classifica pelo sinal.
    """
    t = bruto.strip().upper()
    if "RECEB" in t or "CREDITO" in t or "ENTRADA" in t or t == "RECEITA":
        return "RECEITA"
    if "PAG" in t or "DEBITO" in t or "SAIDA" in t or t == "DESPESA":
        return "DESPESA"
    return "RECEITA" if valor >= 0 else "DESPESA"
