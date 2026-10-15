import json

from django.core.exceptions import ValidationError

MAX_UPLOAD_MB = 10

#: Os estados de `fonte_dado`.
#:
#: `declarado` foi acrescentado em 2026-10-03, e é o mais importante dos cinco —
#: ver a nota longa abaixo.
#:
#: São CINCO. A nota abaixo diz "o vocabulário só tinha quatro" — o que é
#: verdade na altura em que foi escrita, e continua a ser verdade como história.
#: O que não é verdade é o "seis" que este cabeçalho dizia: contar os estados
#: à mão num comentário é exactamente o que a doutrina proíbe. Um contador
#: fixo que erra é pior do que nenhum, porque passa a ser verdade citável.
ESTADOS_FONTE = {
    "medido",  # um sensor disse isto
    "medido_com_ressalva",  # um sensor disse, mas algum campo é suspect
    "suspect",  # o sensor disse, e não é de confiança
    "sem_dado",  # ninguém mediu. Ausência, nunca zero.
    "declarado",  # alguém afirmou. Não é medição.
}

#: Porquê `declarado` — e porque não era `medido`
#: --------------------------------------------------
#: MEDIDO no producto: tudo o que um sensor mede tem carimbo. Tudo o que um
#: produtor **escreve** — uma produtividade de que se lembra, um custo de
#: fertilizante que pagou, o nome de um talhão — não tem sensor nenhum. E o
#: vocabulário só tinha três estados, nenhum dos quais era esse caso.
#:
#: As saídas ruins eram duas, e as duas são mentira:
#:
#: 1. Marcar como `medido`. O painel passa a dizer "medido" onde houve um
#:    digito. Perde-se a distincao entre o que a maquina viu e o que a pessoa
#:    lembrou — e é essa distincao que sustenta o §4.3 da carta (procedencia
#:    auditavel). Um comprador que pague mais por um lote rastreado esta a pagar
#:    por uma declaracao tratada como medicao.
#:
#: 2. Marcar como `sem_dado`. Errado pelo outro lado: *ha* dado. O produtor
#:    disse 65 sc/ha. Isso nao e' ausencia, e `sem_dado` faz o produtor
#:    desconfiar do sistema inteiro ao ver o que ele proprio Affirmou marcado
#:    como desconhecido.
#:
#: A regra que fecha isto, e que e' a mesma que manda a `validate_evidencia`:
#: **o sistema nunca promove uma afirmacao a medicao.** Quem mediu foi o sensor;
#: quem afirmou foi a pessoa; o registo tem de dizer qual dos dois foi.
#:
#: E vale para o que e' **importado** de uma planilha: e' a declaracao dele.
#: Importar nao torna medido. Uma planilha de 2019 continua `declarado` em 2026,
#: e marcar isso como medido seria apagar de onde o numero veio.

#: Os estados que **afirmam** que ha dado. `sem_dado` nao esta aqui porque nao
#: afirma nada; `suspect` e' o sensor a duvidar de si.
#:
#: A distinção importa num sitio concreto: um cálculo de rentabilidade sobre
#: dados `medido` e um sobre dados `declarado` nao sao o mesmo numero, e
#: apresentar os dois como "produtividade" e' a forma como um sistema perde a
#: confiança de quem depende dele para decidir.
ESTADOS_DE_RAIZ = {"medido", "declarado"}


def validate_upload_size(value):
    """Barra upload gigante (DoS de disco/memória)."""
    limite = MAX_UPLOAD_MB * 1024 * 1024
    if getattr(value, "size", 0) and value.size > limite:
        raise ValidationError(f"Arquivo maior que {MAX_UPLOAD_MB} MB.")


def validate_json_safe(value):
    """Rejeita JSON com strings que parecem código malicioso."""
    serialized = json.dumps(value)
    dangerous = ["<script", "javascript:", "eval(", "Function(", "__proto__"]
    for pattern in dangerous:
        if pattern.lower() in serialized.lower():
            raise ValidationError(
                f"JSON contém conteúdo potencialmente perigoso: {pattern}"
            )


def validate_evidencia(value):
    """A evidencia tem de dizer de onde veio cada numero — ou nao vir nada.

    O PROBLEMA QUE ESTE VALIDADOR FECHA
    -----------------------------------
    `PrescricaoVRA.contexto_recomendacao` e' um `JSONField` livre. Aceitava
    `{"temp": 24}` sem carimbo — e o README vende "dados honestos" como o
    diferencial do produto:

        `fonte_dado: medido | sem_dado | simulado`

    Um campo livre e' uma porta dos fundos: a disciplina existe na camada da IA
    (as MCP `amplia_*` recusam devolver `sem_dado` como 0) e desaparece aqui, onde
    o numero entra na base. Um investidor que abre a procedencia e encontra
    `{"temp": 24}` sem carimbo leva a conclusao oposta a que o produto promete —
    e a culpa e' do produto, nao do dado.

    A REGRA — e porquê esta e nao outra
    -----------------------------------
        `{}`  ->  ACEITE. Ausencia declarada e' honestidade, nao erro. O
                 produtor nao e' obrigado a ter sensor para semear.

        qualquer outra coisa  ->  cada folha tem de trazer o seu `fonte_dado`.

    A alternativa — obrigar `fonte_dado` em tudo — transformaria "nao tenho
    sensor" num erro de validacao, e o resultado seria o produtor a escrever
    `sem_dado` apressado em tudo para o formulario passar. **Um campo obrigatorio
    nao produz dados honestos; produz dados conformes.** E' o mesmo motivo pelo
    qual `produtividade_esperada` e' NULL e nao 0.

    O QUE E' UMA "FOLHA"
    -------------------
    Um valor que carrega um numero: `{"valor": 24, "fonte_dado": "medido"}`.
    Um `{"fonte_dado": "..."}` sem numero tambem e' folha (a ausencia tambem
    precisa de carimbo — e' o ponto).

    Nao e' folha: um texto solto como `{"origem": "LeituraSensor"}`, que e'
    metadado do bloco e nao medicao.
    """
    if value in (None, {}, []):
        return  # ausencia declarada: aceite, e e' o caminho honesto

    if not isinstance(value, dict):
        raise ValidationError(
            f"A evidencia tem de ser um objecto JSON, não {type(value).__name__}."
        )

    estado = value.get("fonte_dado")
    if estado is not None and estado not in ESTADOS_FONTE:
        raise ValidationError(
            f"fonte_dado inválido: {estado!r}. "
            f"Valores aceites: {sorted(ESTADOS_FONTE)}."
        )

    # As chaves de topo que sao metadado do bloco, e nao medicoes.
    METADADO = {"fonte_dado", "origem", "motivo", "capturado_em"}

    problemas: list[str] = []
    _percorrer_evidencia(value, "", METADADO, problemas)

    if problemas:
        # A mensagem tem de dizer **o que escrever**, e nao so o que esta mal.
        # MEDIDO: a primeira versao dizia `Sem carimbo: clima.temp` e o produtor
        # ficava a adivinhar um vocabulario. Um erro que nao diz o caminho e' um
        # beco — em qualquer sitio, e este e' o sitio onde o produtor aprende a
        # mentir em vez de admitir a ausencia.
        dica = ""
        if any("fonte_dado=" in p for p in problemas):
            dica = f" Valores aceites: {', '.join(sorted(ESTADOS_FONTE))}."
        raise ValidationError(
            "Cada medição na evidência tem de trazer o seu fonte_dado. "
            'Sem sensor use "fonte_dado": "sem_dado", ou deixe o contexto '
            "vazio (um objeto {}), que significa 'não gravei evidência'."
            f"{dica} Sem carimbo: {', '.join(sorted(problemas))}."
        )


def _percorrer_evidencia(no, caminho: str, metadado: set, problemas: list) -> None:
    """Desce a evidencia ate às folhas.

    MEDIDO: a primeira versao disto nao descia. Tratava `clima` como folha,
    porque `{"clima": {...}}` nao tem `fonte_dado` — e acrescentava
    `"clima"` à lista de problemas. O cliente produz `clima.temp`, **dois
    niveis**, e nenhuma medicao era vista. O validador passava em tudo o que
    era mal formado e recusava em tudo o que era bom — o pior dos dois.

    A regra de descer e' a presenca de `fonte_dado`: um dict que o tem e' uma
    folha (uma medicao, mesmo que sem numero); um dict que nao o tem e' um
    contentor e' percorre-se.
    """
    if isinstance(no, dict):
        if "fonte_dado" in no:
            estado = no["fonte_dado"]
            if estado not in ESTADOS_FONTE:
                onde = caminho or "(bloco)"
                problemas.append(f"{onde}.fonte_dado={estado!r}")
            return
        for chave, filho in no.items():
            if not caminho and chave in metadado:
                continue
            _percorrer_evidencia(
                filho, f"{caminho}.{chave}" if caminho else chave, metadado, problemas
            )
        return

    if isinstance(no, list):
        for i, filho in enumerate(no):
            _percorrer_evidencia(filho, f"{caminho}[{i}]", metadado, problemas)
        return

    # Um numero sem chaves em volta e' o caso que a porta dos fundos
    # explorava: {"temp": 24} nao diz nada sobre a origem do 24.
    if isinstance(no, (int, float)) and not isinstance(no, bool):
        problemas.append(f"{caminho} (número sem fonte_dado)")
        return

    if isinstance(no, str) and caminho:
        # Texto solto dentro de `clima`/`solo` nao e' medicao. Se o produtor
        # quiser anotar, e' no `motivo` do bloco, que e' metadado.
        problemas.append(f"{caminho} (texto solto dentro da evidência)")
