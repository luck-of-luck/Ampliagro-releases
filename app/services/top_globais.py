"""
Top Globais — 16 widgets FieldView/JD/Trimble/Solinftec clonados
Cada função é pura, determinística, sem HTTP externo (usa ndvi.py determinístico, Device, Talhao).
"""

import hashlib
from datetime import datetime, timedelta


def vra_ndvi_prescricao(talhao_id: int, ndvi_threshold: float = 0.6, user=None) -> dict:
    """Prescrição VRA a partir do NDVI.

    Sem NDVI medido, não há prescrição. Este handler fazia três coisas que
    não podia fazer:

    1. Marcava `fonte_real` só porque `COPERNICUS_USER` ou
       `SENTINEL_USER` existiam no ambiente. Ter a chave no `.env` não
       descarrega um pixel — e essa linha sozinha transformava um `None` em
       "medido", sem aviso, para qualquer instalação com a credencial
       configurada.
    2. Prescrevia `dose: 180` kg de NPK 20-10-10 a partir de um NDVI que era
       um sha256 do id do talhão.
    3. Emitia um XML ISO11783 — o formato que uma máquina de aplicação lê
       para espalhar produto no campo — com essa dose.

    together: uma aplicação de fertilizante com o formato que um tractor
    consome, a partir de um número que ninguém mediu. `_evidencia` fica
    vazia, que é o que faz a view marcar `simulado`, e a dose vai a None.

    A lógica de dose, quando houver NDVI real, pertence a um agrónomo e a
    uma tabela de recomendação — não a um `if` num widget.
    """
    from app.services.ndvi import NDVIService

    ndvi = NDVIService.process_talhao_ndvi(talhao_id, user=user)

    if ndvi.get("ndvi_medio") is None:
        return {
            "ndvi": ndvi,
            "prescricao": None,
            "xml_preview": None,
            "acao": None,
            "dose": None,
            "fonte": None,
            "motivo": ndvi.get("motivo") or "Sem NDVI medido não há prescrição de VRA.",
            "_evidencia": "",
        }

    if ndvi["ndvi_medio"] < ndvi_threshold:
        return {
            "ndvi": ndvi,
            "prescricao": {
                "talhao_id": talhao_id,
                "ndvi": ndvi["ndvi_medio"],
                "dose": None,
                "produto": None,
                "motivo": "NDVI abaixo do limiar, mas a tabela de "
                "recomendação de dose não está implementada. "
                "Sem dose não há prescrição.",
            },
            "xml_preview": None,
            "acao": "Vigor abaixo do limiar — dose por definir",
            "fonte": ndvi.get("satelite"),
            "_evidencia": str(ndvi.get("satelite") or ""),
        }
    return {
        "ndvi": ndvi,
        "acao": "Vigor OK",
        "fonte": ndvi.get("satelite"),
        "_evidencia": str(ndvi.get("satelite") or ""),
    }


def can_bus_telemetria(device_id: int, user=None) -> dict:
    from app.models import Device, TelemetryData

    # `user` filtra. Sem ele, `?device_id=<id alheio>` devolvia o `dtc` — o
    # código de avaria — e o histórico de seis pontos da máquina de outra
    # fazenda. `device_id` é um identificador, não autorização.
    qs = Device.objects.filter(id=device_id) if device_id else Device.objects.none()
    if user is not None:
        qs = qs.filter(propriedade__user=user)
    device = qs.first()

    rpm = 0
    consumo = 0.0
    dtc = None
    estado = "Offline"
    labels = [
        (datetime.now() - timedelta(hours=5 - i)).strftime("%H:%M") for i in range(6)
    ]
    rpm_hist = [0] * 6
    consumo_hist = [0.0] * 6
    # `latest` vive aqui fora do `if` de proposito. Antes vivia la dentro, e
    # a evidencia — que o le do `if` — levantava NameError sem device. A
    # view devolvia 500, e um 500 nao diz "nao ha telemetria": diz "a app
    # esta partida", e o produtor nao sabe qual das duas e' verdade.
    latest = None

    if device:
        estado = "OK"
        mais_recentes = list(
            TelemetryData.objects.filter(device=device).order_by("-timestamp")[:6]
        )
        latest = mais_recentes[0] if mais_recentes else None
        for reg in reversed(mais_recentes):
            # `raw_payload`, e `payload` — o campo chamava-se `payload` e não
            # existe em `TelemetryData` (`app/models/iot.py:289`). Como a leitura
            # estava dentro de `if device:` mas APOS o `mais_recentes` ja estar
            # calculado, o `AttributeError` subia do meio do handler e o widget
            # devolvia 500 sempre que havia telemetria — isto é, nunca
            # funcionou. Ver `tests_top_globais_isolamento.py`.
            payload = reg.raw_payload if isinstance(reg.raw_payload, dict) else {}
            rpm_hist.append(float(payload.get("rpm", 0) or 0))
            consumo_hist.append(float(payload.get("consumo", 0.0) or 0.0))
        # A janela e' de 6 pontos. Corta a lista em vez de a deixar crescer
        # com o numero de registos: um grafico de 40 pontos dentro de um cartao
        # de KPI nao cabe, e o que sobra e' ilegivel.
        rpm_hist = rpm_hist[-6:]
        consumo_hist = consumo_hist[-6:]
        if latest and isinstance(latest.raw_payload, dict):
            rpm = latest.raw_payload.get("rpm", 0)
            consumo = latest.raw_payload.get("consumo", 0.0)
            dtc = latest.raw_payload.get("dtc")
            if dtc or rpm > 2200:
                estado = "Manutencao"
        elif not mais_recentes:
            # Ha device, mas nunca enviou nada. Nao e' "Offline" por falta de
            # telemetria num instante — e' um device que nunca reportou, que e
            # uma coisa diferente e mais grave.
            estado = "Nunca reportou"

    return {
        "device_id": device_id,
        "rpm": rpm,
        "consumo_lh": consumo,
        "dtc": dtc,
        "estado": estado,
        "chart": {"labels": labels, "rpm": rpm_hist, "consumo": consumo_hist},
        # A evidencia e' a LEITURA, nao a existencia do device. Um device
        # registado que nunca transmite nao e' telemetria medida.
        "_evidencia": (
            f"TelemetryData do device {device_id}, {len(mais_recentes)} registos, "
            f"ultimo em {latest.timestamp}"
            if latest
            else ""
        ),
    }


def guidance_ab(talhao_id: int, user=None) -> dict:
    """Guias de aplicação em linha (AB).

    `_evidencia` era `f"Talhao {talhao.nome}"` — bastava o talhão existir
    para o widget ser considerado medido. Mas o `precisao_cm: 2.5` não sai
    de lado nenhum: não há sensor de aplicação com_builder ligado ao talhão,
    e a constante estava escrita à mão na fonte.

    A distinção que importa: existe uma guia de aplicação guardada? — sim,
    é o talhão. E a aplicação foi feita com que precisão? — isso não se
    sabe. As duas coisas estavam a ser respondidas pelo mesmo campo.

    `_evidencia` vazia porque não consultámos nada que seja uma medição.
    A existência do talhão continua no payload, com outro nome, para o
    frontend poder mostrar o contexto sem o confundir com prova.
    """
    from app.models import Talhao

    qs = Talhao.objects.filter(id=talhao_id)
    if user is not None:
        qs = qs.filter(propriedade__user=user)
    talhao = qs.first()
    return {
        "talhao_id": talhao_id,
        "linha": f"A-B {talhao.nome if talhao else talhao_id}",
        "talhao_nome": talhao.nome if talhao else None,
        "auto_section": None,
        "precisao_cm": None,
        "motivo": (
            "Nenhuma guia de aplicação registada para este talhão, e nenhum "
            "sensor de aplicação ligado. A precisão de aplicação é lida de "
            "uma guia ou de um registo de máquina, não inventada."
        ),
        # Vazio: existe um talhão, mas isso não é uma medição de aplicação.
        "_evidencia": "",
    }


def ai_detecta_cultura(lat: float, lon: float) -> dict:
    """Detecta a cultura de uma coordenada.

    Não há detecção. O que existia era `sha256(f"{lat},{lon}") % 7` a
    escolher entre sete culturas, com uma confiança de 0.78 a 0.97 e o
    carimbo "Sentinel-2 AI deterministico".

    Verificado por execução: Brasília (-23.5, -46.6) dava `algodao`,
    Brasília central (-15.8, -47.9) dava `eucalipto`, e um ponto no Chade
    (10, 20) dava `arroz`. Nenhuma das três tem qualquer relação com a
    geografia. Um hash de coordenadas não sabe o que grows lá — sabe só
    que já lá esteve.

    A detecção de cultura a partir de imagem de satélite é um problema real,
    com modelos treinados e servicões de classificação. Enquanto não houver
    um, a resposta honesta é "não sei": a cultura de um talhão sabe-se
    lendo a safra que o produtor registou, e isso está na base de dados.
    """
    return {
        "lat": lat,
        "lon": lon,
        "cultura": None,
        "confianca": None,
        "fonte": None,
        "motivo": (
            "Sem serviço de classificação de imagem de satélite configurado. "
            "A cultura de um talhão lê-se da safra registada pelo produtor "
            "(Safra.cultura), não de uma estimativa."
        ),
        "_evidencia": "",
    }


def chuva_1km(lat: float, lon: float) -> dict:
    # Retorna zerado se nao ha integracao configurada
    return {
        "lat": lat,
        "lon": lon,
        "mm_15min": 0.0,
        "mm_1h": 0.0,
        "alerta": False,
        "_evidencia": "",
    }


def as_applied_gap(talhao_id: int, user=None) -> dict:
    from app.services.ndvi import NDVIService

    ndvi = NDVIService.process_talhao_ndvi(talhao_id, user=user)

    # `ndvi_medio` e' None quando nao ha fonte Copernicus. Sem NDVI nao ha
    # gap, e sem gap nao ha acao: "Reaplicar" com um so a recomendacao de
    # aplicacao de produto, e decide-se com o indice que nao existe.
    if ndvi.get("ndvi_medio") is None:
        return {
            "talhao_id": talhao_id,
            "ndvi": None,
            "gap_pct": None,
            "acao": None,
            "motivo": ndvi.get("motivo") or "NDVI indisponivel",
            "_evidencia": "",
        }

    # O `abs()` que aqui estava era o defeito.
    #
    # `gap_pct = abs(ndvi - 0.65)` diz que um talhão com NDVI 0,90 está "25
    # pontos longe" do alvo — e então diz "Reaplicar". Medido por execução:
    #
    #     NDVI=0.90 -> Reaplicar (25,0)      <- lavoura vigorosa, mandada gastar
    #     NDVI=0.80 -> Reaplicar (15,0)
    #     NDVI=0.65 -> OK         ( 0,0)
    #     NDVI=0.50 -> Reaplicar (15,0)
    #
    # Isto não era invenção (o NDVI é medido a sério), era uma MEDIDA
    # lida ao contrário: só a faixa 0,55–0,75 dava "OK", e o produtor mais
    # bem adubado levava com a instrução de gastar mais. O gap aqui é
    # "distância para o alvo" por um lado só — acima do alvo não há falta
    # nenhuma a repor.
    ndvi_medido = float(ndvi["ndvi_medio"])
    alvo = 0.65
    gap_pct = round(max(0.0, alvo - ndvi_medido) * 100, 1)
    acima_do_alvo = ndvi_medido > alvo
    return {
        "talhao_id": talhao_id,
        "ndvi": ndvi_medido,
        "gap_pct": gap_pct,
        # `Reaplicar` só existe para falta. Acima do alvo não se repõe nada.
        "acao": "Reaplicar" if gap_pct > 10 else "OK",
        "_motivo": (
            "acima do alvo — nao ha falta a repor"
            if acima_do_alvo
            else ("abaixo do alvo" if gap_pct > 10 else "dentro da faixa")
        ),
        "_evidencia": "",
    }


def praga_ai_foto(foto_hash: str = "") -> dict:
    """Diagnóstico de praga a partir de uma fotografia.

    Não há modelo. O que existia era `sha256(foto_hash) % 4` a escolher
    entre quatro pragas, com confiança de 0.82 a 0.96 e — o que importa —
    uma acção de **`"Pulverizar"`**.

    Verificado por execução: com o hash `demo` e com `outra_foto` deu
    `ferrugem` e `Pulverizar` nos dois casos. Um hash de uma string não vê
    uma folha; e a acção que saía dele não era um diagnóstico, era uma
    instrução de aplicação de produto.

    "Pulverizar" a partir de um hash pode custar o cultivo e o dinheiro do
    produtor, e é a única recomendação de acção de todo este ficheiro que
    tinha consequências. Por isso não fica degradado para "simulado": fica
    sem acção, e diz porquê.

    Diagnóstico de praga por imagem é um problema real — modelo de
    classificação treinado, folha a folha. Sem isso, a resposta é "não sei",
    e quem decide pulverizar é quem olha para a folha.
    """
    return {
        "praga": None,
        "confianca": None,
        "acao": None,
        "foto_hash": foto_hash or None,
        "motivo": (
            "Sem modelo de classificação de imagem de praga configurado. "
            "Não há diagnóstico, e sobretudo não há acção: pulverizar é "
            "decisão de quem conhece a lavoura, não de um hash da foto."
        ),
        "_evidencia": "",
    }


def rota_70_colheitadeiras(fazenda_id: int, user=None) -> dict:
    """Rota de 70 colheitadeiras.

     A `_evidencia` era o nome da propriedade e a contagem de máquinas. É
     verdade que a propriedade tem 2 máquinas activas — e não prova nada
     sobre quilómetros, economia ou tempo de uma rota que ninguém calculou.

    Três zeros com evidência ao lado é a pior forma desta mentira: o 0
    parece uma medição (a rota é mesmo de 0 km?) e a evidência desliga o
    mecanismo de dúvida. `_evidencia` vazia: o que sabemos é que a
    propriedade existe, e isso não é uma rota.

     A rota existe como problema real — planeamento de ceifa com CPA, com
     fazenda, TAL e velocidade. Sem esses dados de entrada não há caminho
     honesto para o cálculo, e um 0 aqui seria um plano de ceifa que não
     existe.
    """
    from app.models import Maquinario, Propriedade

    prop_qs = Propriedade.objects.filter(id=fazenda_id)
    if user is not None:
        prop_qs = prop_qs.filter(user=user)
    prop = prop_qs.first()
    maqs = prop.maquinarios.filter(ativo=True).count() if prop else 0
    return {
        "fazenda_id": fazenda_id,
        "km_total": None,
        "economia_pct": None,
        "tempo_h": None,
        "colheitadeiras_ativas": maqs,
        "propriedade_nome": prop.nome if prop else None,
        "motivo": (
            "Planeamento de ceifa precisa de capacidade de colheitadeira, "
            "tempo de Operação e Fileira de Ceifa. Sem esses dados não há "
            "rota a calcular — e 0 km seria um plano de ceifa que não "
            "existe."
        ),
        "_evidencia": "",
        "_colheitadeiras": maqs,
    }


def weigh_scale_tempo_real(talhao_id: int, user=None) -> dict:
    """Balança de pesagem em tempo real.

    Não há balança ligada. O `sc_ha` antigo era `ndvi * 80` — um
    rendimento em sacas por hectare derivado de um hash, com
    `"tempo_real": True` por cima. Quem visse aquilo multiplicava pela sua
    area e tinha um total de colheita que não vinha de lado nenhum. Era o
    defeito que `paginas.py` já descrevia: uma balança desligada a devolver
    50,4 sc/ha com a confiança de uma ligada.

    Sem balança: `sc_ha` a None, `tempo_real` a False, e o motivo.
    """
    from app.services.ndvi import NDVIService

    ndvi = NDVIService.process_talhao_ndvi(talhao_id, user=user)
    tem_balanca = False  # nenhum dispositivo de pesagem registado

    if not tem_balanca:
        return {
            "talhao_id": talhao_id,
            "sc_ha": None,
            "ndvi": ndvi.get("ndvi_medio"),
            "tempo_real": False,
            "motivo": "Nenhuma balança ligada a este talhão. "
            "Rendimento em sacas/ha só existe com leitura de balança.",
            "_evidencia": "",
        }

    return {
        "talhao_id": talhao_id,
        "sc_ha": None,
        "ndvi": ndvi.get("ndvi_medio"),
        "tempo_real": True,
        "_evidencia": "",
    }


def hedge_b3_real(sacas: int = 1000, strike: float = 85) -> dict:
    """SEM FONTE. Este widget não pode afirmar que existe uma cobertura B3.

    A B3 tem book público e um contrato real. Dizer `b3: True` sem ler nada
    dela é afirmar que o produtor tem uma proteção financeira que não tem — e
    o nome da função (`hedge_b3_real`) dizia "real" no próprio nome, que é a
    forma mais difícil de auditar de cima.

    Para isto ficar honesto falta uma integração com a B3. Até lá, a resposta
    é a ausência declarada, e não um sim.
    """
    from app.services.hedge import hedge_recomendado

    rec = hedge_recomendado(80, strike, sacas, 65)
    return {
        "sacas": sacas,
        "strike": strike,
        "recomendado": rec,
        "b3": None,  # NUNCA True sem ler a B3. Ver a docstring.
        "motivo": "Sem integração com a B3: nenhuma cobertura foi consultada.",
        "_evidencia": "",
    }


def benchmark_fbn(propriedade_id: int, user=None) -> dict:
    """A SUA produção é real. A MÉDIA com que se compara é inventada.

    Este widget tinha o pior arranjo possível: metade real, metade constante, e a
    procedência a dizer "real" para o conjunto. O `seu_custo_ha` vinha de
    lançamentos verdadeiros; o `media_2k` era 50,0 hardcoded; e o
    `vs_media_pct` — a conclusao do widget, o numero que o produtor lê para
    decidir se está bem ou mal — era a divisa entre um número verdadeiro e um
    número inventado.

    Um carimbo de procedência que vale para o conjunto é pior do que não ter
    carimbo: enquanto a widget disser "real", ninguém pergunta qual das metades
    é real.

    Para isto ficar honesto falta a base de comparação — o custo por hectare
    médio da região, de uma fonte datada. Até lá: o número do produtor
    continua a vir (é real e é útil), o `vs_media_pct` deixa de existir, e a
    widget é marcada como simulada, porque é a conclusão que é falsa.
    """
    from django.db.models import Sum

    from app.models import Propriedade

    prop_qs = Propriedade.objects.filter(id=propriedade_id)
    if user is not None:
        prop_qs = prop_qs.filter(user=user)
    prop = prop_qs.first()
    seu = None
    if prop:
        area = float(prop.area_total or 0)
        desp = (
            prop.lancamentos.filter(tipo="DESPESA").aggregate(s=Sum("valor"))["s"] or 0
        )
        # Divisao por area zero daria um custo por hectare que nao existe.
        # Sem area medida, nao ha custo por hectare que se possa dizer.
        seu = round(float(desp) / area, 1) if area > 0 else None

    return {
        "propriedade_id": propriedade_id,
        "seu_custo_ha": seu,
        "media_2k": None,  # NUNCA uma constante. Ver a docstring.
        "vs_media_pct": None,  # NUNCA a divisa entre um numero e uma constante.
        "motivo": (
            "A comparacao regional precisa de uma base de custo por hectare de "
            "uma fonte datada. Sem ela nao ha 'vs media' para dizer."
        ),
        # Vazio, apesar de a propriedade existir: e' a COMPARACAO que nao tem
        # fonte, e e' a comparacao que o widget promete.
        "_evidencia": "",
    }


def seguro_chuva_param(lat: float, lon: float, dias: int = 60) -> dict:
    """SEM FONTE. Nao ha apolice de seguro linkada a este produto.

    Antes devolvia `{"chuva_60d": 0, "limite": 200, "paga": False, ...}`. O
    `paga: False` e' o pior dos campos: num indice de seguro parametrico, dizer
    que nao foi pago afirma que NAO ha perda a indenizar. E `limite: 200` era
    uma politica de subscricao inventada — nenhuma fonte a sustenta.

    Um indice de seguro mede chuva E apolice. Nao medimos nenhum dos dois.
    """
    return {
        "chuva_60d": None,
        "limite": None,
        "paga": None,
        "valor": None,
        "motivo": (
            "Sem fonte. Nao ha indice de seguro apolado a esta propriedade, "
            "nem serie de chuva com origem identificada. Devolver 0 aqui "
            "afirmaria que nao houve perda a indenizar."
        ),
        "_evidencia": "",
    }


def lcdpr_sped(ano: int = 2025) -> dict:
    """SEM FONTE. Este widget não pode afirmar que um LCDPR/SPED existe.

    O nome de ficheiro era INTERPOLADO: `LCDPR_{ano}.txt` — uma string
    montada, nunca escrita em lado nenhum. Ao lado, `sped: True` e
    `auditavel: True`.

    Isto é a falsificação mais grave que há nesta camada. As outras inventam um
    número num painel; esta inventa um ARQUIVO que o produtor pode entregar a um
    órgão público, e diz-lhe que é auditável. Um `arquivo` inventado é pior que
    um `arquivo` em falta, porque o produtor não vai verificar um ficheiro que
    tem nome de ficheiro.

    O LCDPR real exige o conjunto de safras, área, culturas e custos do produtor,
    assinado e transmitido ao MDA. Não há como sintetizar isso aqui. A resposta
    é a ausência declarada.
    """
    return {
        "ano": ano,
        "sped": None,  # NUNCA True sem gerar o ficheiro. Ver a docstring.
        "auditavel": None,
        "arquivo": None,
        "motivo": (
            "LCDPR/SPED exige os dados reais da safra e transmissao ao MDA. "
            "Nada foi gerado; nao existe ficheiro para entregar."
        ),
        "_evidencia": "",
    }


def carbono_mombak(area_ha: float = 10000) -> dict:
    """SEM FONTE. Este widget não pode afirmar que há carbono certificado.

    O `tco2e_ha` era 12,5 hardcoded e o `mombak: True` era um carimbo de
    certificação. A Mombak é uma norma com registo: quem a cumpre pode vender
    crédito de carbono. Um carimbo sem inventário de carbono, sem medição de
    solo e sem registo é uma certificação falsa com o nome de uma norma
    verdadeira.

    Carbono que não foi medido não é carbono. Calculá-lo exigiria o inventário
    de gases por parcela e o factor de emissão auditado — que é trabalho de
    agrónomo, não um número gerado a partir da área.
    """
    # NAO calculamos tCO2e: a conta antiga era `area_ha * 12.5`, e esse 12,5
    return {
        "area_ha": area_ha,
        "tco2e": None,  # NUNCA inventado. Ver a docstring.
        "tco2e_ha": None,
        "mombak": None,  # NUNCA True sem medicao e registo. Ver a docstring.
        "motivo": (
            "Carbono nao foi medido. Sem inventario de gases por parcela nao ha "
            "credito a certificar."
        ),
        "_evidencia": "",
    }


def voz_assistente(texto: str) -> dict:
    """SEM FONTE. Nao existe motor de voz medido neste produto.

    Antes devolvia `tts: True, stt: True` escritos a mao. Um boolean `True` e'
    uma afirmacao de capacidade, e foi a forma mais direta que este ficheiro
    teve de mentir: nao ha motor, nao ha teste, nao ha fonte.
    """
    return {
        "texto": texto,
        "tts": False,
        "stt": False,
        "voz": None,
        "motivo": (
            "Sem fonte. Nao existe motor de sintese ou de reconhecimento de voz "
            "medido neste produto. `tts` e `stt` estao a False porque e' isso "
            "que medimos: nada."
        ),
        "_evidencia": "",
    }


def copilot_hedge(texto: str) -> dict:
    """SEM FONTE. Nao ha cotacao de Chicago nem LLM por tras disto.

    Antes emitia prosa persuasiva: `copilot: True` e uma frase que reprendia o
    `recomendado` de `hedge_b3_real(1000, 65)` — com `1000` e `65` literais no
    codigo. `hedge_recomendado` ja nao le cotacao nenhuma (ver a nota la em
    cima); repetir o numero em prosa e' pior do que o numero, porque a frase
    convence.

    E o mais grave: o `if "hedge" in texto.lower() and "65" in texto` devolvia o
    hedge a um SIMULO que nao tem preco. Removido: um simulador que responde
    com um numero fixo a um cenario nao e' um simulador.
    """
    return {
        "copilot": False,
        "resposta": None,
        "motivo": (
            "Sem fonte. Nao ha cotacao de Chicago lida, nem modelo de linguagem "
            "por tras desta resposta. O hedge_so`'a um cenario, e um cenario "
            "com preco fixo no codigo nao e' uma Cotacao."
        ),
        "_evidencia": "",
    }


# Mapa widget_id -> handler
#
# O segundo argumento é o `user` que vem do `request`. Os handlers que recebem
# um id da query string usam-no para filtrar — `p.get("talhao_id")` e
# `p.get("device_id")` são identificadores, não autorização, e sem o filtro
# qualquer produtor autenticado lia a geometria e a telemetria de outro
# (ver `tests_top_globais_isolamento.py`).
#
# `user=None` nos que não tocam a base é o mesmo `None` de sempre: a assinatura
# fica uniforme e o handler não precisa de saber se é de dados ou não.
WIDGET_HANDLERS = {
    "kpi-vra-ndvi": lambda p, u=None: vra_ndvi_prescricao(
        p.get("talhao_id", 1), user=u
    ),
    "kpi-can-bus": lambda p, u=None: can_bus_telemetria(p.get("device_id", 1), user=u),
    "kpi-guidance-ab": lambda p, u=None: guidance_ab(p.get("talhao_id", 1), user=u),
    "kpi-ai-cultura": lambda p, u=None: ai_detecta_cultura(
        p.get("lat", -15), p.get("lon", -47)
    ),
    "kpi-chuva-1km": lambda p, u=None: chuva_1km(p.get("lat", -15), p.get("lon", -47)),
    "kpi-as-applied": lambda p, u=None: as_applied_gap(p.get("talhao_id", 1), user=u),
    "kpi-praga-ai": lambda p, u=None: praga_ai_foto(p.get("foto_hash", "demo")),
    "kpi-rota-otimizada": lambda p, u=None: rota_70_colheitadeiras(
        p.get("fazenda_id", 1), user=u
    ),
    "kpi-weigh-scale": lambda p, u=None: weigh_scale_tempo_real(
        p.get("talhao_id", 1), user=u
    ),
    "kpi-hedge-b3": lambda p, u=None: hedge_b3_real(
        p.get("sacas", 1000), p.get("strike", 85)
    ),
    "kpi-benchmark-fbn": lambda p, u=None: benchmark_fbn(
        p.get("propriedade_id", 1), user=u
    ),
    "kpi-seguro-chuva": lambda p, u=None: seguro_chuva_param(
        p.get("lat", -15), p.get("lon", -47)
    ),
    "kpi-lcdpr-sped": lambda p, u=None: lcdpr_sped(p.get("ano", 2025)),
    "kpi-carbono": lambda p, u=None: carbono_mombak(p.get("area_ha", 10000)),
    "kpi-voz": lambda p, u=None: voz_assistente(
        p.get("texto", "quanto choveu no talhao 3?")
    ),
    "kpi-copilot-hedge": lambda p, u=None: copilot_hedge(
        p.get("texto", "simula hedge 65sc se Chicago -5%")
    ),
}
