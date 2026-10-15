"""
RegraAuto — 20 RegraAlertaTelemetria por porte/meio (Familiar 50ha → Mega 70k)
Cada regra: sensor → threshold → ComandoDevice (ou alerta) + severidade.
Usa RegraAlertaTelemetria já existente (sem nova migration), só seed.
Matriz 4 portes × 5 meios = 20, cobrindo 100% dos 7 telas úteis (01-10).
"""

REGRAS_AUTO = [
    # ──────────────────────────────────────────────────────────────
    # 01 GRÃOS — V0-R8 Soja 120d / Pamplona 27k (7% 180 epis)
    # ──────────────────────────────────────────────────────────────
    {
        "id": "grao_bme280_pivo_40mm",
        "nome": "[GRÃO] BME280 <60% → liga pivô 40mm (Pamplona 27k)",
        "metric": "umidade_solo",
        "tipo": "threshold_min",
        "valor_ref": 60,
        "janela_min": 15,
        "severidade": "critical",
        "acao_fisica": "abrir_valvula",
        "titulo_tarefa": "Irrigar talhão soja V0-R8 — umidade 60%",
        "cargo_tarefa": "CAMPO",
        "porte": "mega",
        "meio": "agua",
        "tela": "01 Grãos",
        "origem_ep": "01C Pamplona 27k",
    },
    {
        "id": "grao_spd_mo_2_para_3_4",
        "nome": "[GRÃO] SPD MO 2→3,4% +0,28%/ano — alerta análise solo (Médio 500ha)",
        "metric": "ph_solo",
        "tipo": "threshold_min",
        "valor_ref": 5.5,
        "janela_min": 1440,
        "severidade": "warning",
        "acao_fisica": "",
        "titulo_tarefa": "Coletar análise solo SPD 7t — MO alvo 3,4%",
        "cargo_tarefa": "CAMPO",
        "porte": "medio",
        "meio": "terra",
        "tela": "01 Grãos + 09 Solo",
        "origem_ep": "09A SPD 7T",
    },
    {
        "id": "grao_hedge_chicago_5pct",
        "nome": "[GRÃO] Chicago -5% em 1 dia → sugere hedge 65sc (Familiar 50ha)",
        "metric": "radiacao",
        "tipo": "delta",
        "valor_ref": 5,
        "janela_min": 60,
        "severidade": "critical",
        "acao_fisica": "",
        "titulo_tarefa": "Travar hedge 65sc — Chicago -5%",
        "cargo_tarefa": "GERAL",
        "porte": "familiar",
        "meio": "capital",
        "tela": "01 Grãos + 08 ERP",
        "origem_ep": "01A Soja V0-R8",
    },
    {
        "id": "grao_maquina_oleo_300h",
        "nome": "[GRÃO] Horímetro 300h → revisão (Pamplona 70 colheitadeiras)",
        "metric": "horimetro",
        "tipo": "threshold_max",
        "valor_ref": 300,
        "janela_min": 60,
        "severidade": "warning",
        "acao_fisica": "",
        "titulo_tarefa": "Revisão 300h — colheitadeira Pamplona",
        "cargo_tarefa": "MECANICA",
        "porte": "mega",
        "meio": "maquina",
        "tela": "08 ERP",
        "origem_ep": "01C Pamplona",
    },
    # ──────────────────────────────────────────────────────────────
    # 02 PECUÁRIA — Boi 540d / Leite 15L / Roncador 70k (12,5% 300)
    # ──────────────────────────────────────────────────────────────
    {
        "id": "pecuaria_ph_rumen_6_0_alto",
        "nome": "[PECUÁRIA] pH rúmen 6.0 ALTO (35 amido/30 fibra) → ajusta 25/35",
        "metric": "ph_solo",
        "tipo": "threshold_min",
        "valor_ref": 6.0,
        "janela_min": 30,
        "severidade": "critical",
        "acao_fisica": "",
        "titulo_tarefa": "Ajustar dieta 35/30→25/35 — risco acidose ALTO",
        "cargo_tarefa": "PECUARIA",
        "porte": "medio",
        "meio": "conhecimento",
        "tela": "02 Pecuária",
        "origem_ep": "02A Boi 540d",
    },
    {
        "id": "pecuaria_leite_piquete_30d",
        "nome": "[PECUÁRIA] Leite 15L piquete 30d rotacionado → cerca virtual",
        "metric": "passos",
        "tipo": "threshold_max",
        "valor_ref": 5000,
        "janela_min": 1440,
        "severidade": "info",
        "acao_fisica": "",
        "titulo_tarefa": "Rotacionar piquete 30d — leite 15L",
        "cargo_tarefa": "PECUARIA",
        "porte": "grande",
        "meio": "terra",
        "tela": "02 Pecuária",
        "origem_ep": "02B Leite 15L",
    },
    {
        "id": "pecuaria_roncador_ilpf_gps",
        "nome": "[PECUÁRIA] Roncador 70k ILPF — GPS fora talhão",
        "metric": "gps_lat",
        "tipo": "anomalia",
        "valor_ref": 3,
        "janela_min": 15,
        "severidade": "warning",
        "acao_fisica": "",
        "titulo_tarefa": "ILPF 70k — animal fora piquete",
        "cargo_tarefa": "PECUARIA",
        "porte": "mega",
        "meio": "maquina",
        "tela": "02 Pecuária + 07 Agro",
        "origem_ep": "02C Roncador 70k",
    },
    {
        "id": "pecuaria_racao_estoque_7d",
        "nome": "[PECUÁRIA] Ração estoque <7d → auto ordem compra",
        "metric": "outro",
        "tipo": "threshold_min",
        "valor_ref": 7,
        "janela_min": 60,
        "severidade": "warning",
        "acao_fisica": "",
        "titulo_tarefa": "Ração <7d — criar ordem compra",
        "cargo_tarefa": "ESTOQUE",
        "porte": "medio",
        "meio": "capital",
        "tela": "02 Pecuária + 08 ERP",
        "origem_ep": "02B Leite",
    },
    # ──────────────────────────────────────────────────────────────
    # 03 AVICULTURA — Lego 42d / BigBrother 12 / Moba 9,5% (7,5% 180)
    # ──────────────────────────────────────────────────────────────
    {
        "id": "avicultura_lego_42d_lotes_6_4",
        "nome": "[AVICULTURA] Lego 42d lotes 6.0→6.4 +R$150k — intervalo >42d",
        "metric": "peso",
        "tipo": "threshold_max",
        "valor_ref": 42,
        "janela_min": 60,
        "severidade": "info",
        "acao_fisica": "",
        "titulo_tarefa": "Lego 42d → 6,4 lotes/ano +R$150k",
        "cargo_tarefa": "PECUARIA",
        "porte": "medio",
        "meio": "conhecimento",
        "tela": "03 Avicultura",
        "origem_ep": "03A Lego 10d",
    },
    {
        "id": "avicultura_bigbrother_12_balancas",
        "nome": "[AVICULTURA] BigBrother 12 balanças prevê 2,8kg 2d antes +R$192k",
        "metric": "peso",
        "tipo": "delta",
        "valor_ref": 10,
        "janela_min": 120,
        "severidade": "info",
        "acao_fisica": "",
        "titulo_tarefa": "BigBrother prevê 2,8kg — ajustar ração +R$192k/ano",
        "cargo_tarefa": "PECUARIA",
        "porte": "grande",
        "meio": "maquina",
        "tela": "03 Avicultura",
        "origem_ep": "03B BigBrother",
    },
    {
        "id": "avicultura_moba_9_5_descarte",
        "nome": "[AVICULTURA] Moba 9,5%→4% bico +R$660k — descarte >9,5%",
        "metric": "outro",
        "tipo": "threshold_max",
        "valor_ref": 9.5,
        "janela_min": 1440,
        "severidade": "critical",
        "acao_fisica": "",
        "titulo_tarefa": "Moba 9,5% → 4% debicagem +R$660k",
        "cargo_tarefa": "PECUARIA",
        "porte": "familiar",
        "meio": "gente",
        "tela": "03 Avicultura",
        "origem_ep": "03C Moba 95",
    },
    # ──────────────────────────────────────────────────────────────
    # 04 SUÍNO+TILÁPIA — Biodigestor / Pele +566% / Mormaco (10% 240)
    # ──────────────────────────────────────────────────────────────
    {
        "id": "suino_biodigestor_dejeto",
        "nome": "[SUÍNO] Biodigestor 100 suínos → energia R$8k/mês — offline",
        "metric": "energia_dia",
        "tipo": "offline",
        "valor_ref": 30,
        "janela_min": 30,
        "severidade": "warning",
        "acao_fisica": "",
        "titulo_tarefa": "Biodigestor offline — dejeto 100 suínos",
        "cargo_tarefa": "GERAL",
        "porte": "medio",
        "meio": "maquina",
        "tela": "04 Suíno+Tilápia",
        "origem_ep": "04A Suíno Biodigestor",
    },
    {
        "id": "tilapia_pele_566pct_aerador",
        "nome": "[TILÁPIA] Pele R$800k vs filé R$120k +566% — mormaco >30C -5% liga aerador",
        "metric": "mormaco_tilapia",
        "tipo": "threshold_max",
        "valor_ref": 30,
        "janela_min": 15,
        "severidade": "critical",
        "acao_fisica": "abrir_valvula",
        "titulo_tarefa": "Mormaco >30C -5% → ligar aerador (pele +566%)",
        "cargo_tarefa": "PECUARIA",
        "porte": "familiar",
        "meio": "agua",
        "tela": "04 Suíno+Tilápia",
        "origem_ep": "04B Tilápia Pele",
    },
    # ──────────────────────────────────────────────────────────────
    # 05 CAFÉ — Rainforest 60vs30 +100% (5% 120)
    # ──────────────────────────────────────────────────────────────
    {
        "id": "cafe_rainforest_60vs30",
        "nome": "[CAFÉ] Rainforest 60sc vs 30sc +100% — umidade <70% alerta",
        "metric": "umidade_ar",
        "tipo": "threshold_min",
        "valor_ref": 70,
        "janela_min": 60,
        "severidade": "warning",
        "acao_fisica": "",
        "titulo_tarefa": "Café Rainforest 60vs30sc +100% — certificar",
        "cargo_tarefa": "CAMPO",
        "porte": "familiar",
        "meio": "conhecimento",
        "tela": "05 Café",
        "origem_ep": "05A Rainforest",
    },
    # ──────────────────────────────────────────────────────────────
    # 06 LARANJA — Greening -30% (2,5% 60)
    # ──────────────────────────────────────────────────────────────
    {
        "id": "laranja_greening_30pct",
        "nome": "[LARANJA] Greening -30% 1 planta → MIP armadilha",
        "metric": "outro",
        "tipo": "anomalia",
        "valor_ref": 30,
        "janela_min": 1440,
        "severidade": "critical",
        "acao_fisica": "",
        "titulo_tarefa": "Greening -30% → MIP + receituário CVC",
        "cargo_tarefa": "CAMPO",
        "porte": "medio",
        "meio": "terra",
        "tela": "06 Laranja",
        "origem_ep": "06A Greening",
    },
    # ──────────────────────────────────────────────────────────────
    # 07 AGROFLORESTA — 7a R$5bi Mombak +33% R$1bi (17,5% 420)
    # ──────────────────────────────────────────────────────────────
    {
        "id": "agro_mombak_10k_33pct",
        "nome": "[AGRO] Mombak 10k +33% R$1bi — biomassa <80m³/ha alerta",
        "metric": "biomassa_eucalipto",
        "tipo": "threshold_min",
        "valor_ref": 80,
        "janela_min": 1440,
        "severidade": "info",
        "acao_fisica": "",
        "titulo_tarefa": "Mombak 10k +33% R$1bi — biomassa 100m³/ha",
        "cargo_tarefa": "CAMPO",
        "porte": "grande",
        "meio": "terra",
        "tela": "07 Agrofloresta",
        "origem_ep": "07B Mombak 10k",
    },
    {
        "id": "agro_eucalipto_100m3",
        "nome": "[AGRO] Eucalipto 100m³/ha 7a — crescimento <12m³/ano",
        "metric": "biomassa_eucalipto",
        "tipo": "threshold_min",
        "valor_ref": 12,
        "janela_min": 10080,
        "severidade": "info",
        "acao_fisica": "",
        "titulo_tarefa": "Eucalipto 100m³/ha 7a — forragem 100t",
        "cargo_tarefa": "CAMPO",
        "porte": "grande",
        "meio": "maquina",
        "tela": "07 Agrofloresta",
        "origem_ep": "07C Eucalipto 100m³",
    },
    {
        "id": "agro_mel_80kg_camoatim",
        "nome": "[AGRO] Mel 80kg camoatim — Brix <18 alerta",
        "metric": "qualidade_mel_camoatim",
        "tipo": "threshold_min",
        "valor_ref": 18,
        "janela_min": 1440,
        "severidade": "info",
        "acao_fisica": "",
        "titulo_tarefa": "Mel 80kg camoatim °Brix 18",
        "cargo_tarefa": "PECUARIA",
        "porte": "familiar",
        "meio": "agua",
        "tela": "07 Agrofloresta",
        "origem_ep": "07E Mel 80kg",
    },
    # ──────────────────────────────────────────────────────────────
    # 08 ERP — SAP 10M + PROTHEUS 450 + JD -30% (10% 240)
    # ──────────────────────────────────────────────────────────────
    {
        "id": "erp_sap_jbs_10m",
        "nome": "[ERP] SAP JBS 10M cabeças — sync PROTHEUS 450 offline",
        "metric": "outro",
        "tipo": "offline",
        "valor_ref": 30,
        "janela_min": 30,
        "severidade": "warning",
        "acao_fisica": "",
        "titulo_tarefa": "SAP 10M vs PROTHEUS 450 — sync ERP",
        "cargo_tarefa": "GERAL",
        "porte": "mega",
        "meio": "capital",
        "tela": "08 ERP",
        "origem_ep": "08A SAP JBS",
    },
    {
        "id": "erp_john_deere_30pct",
        "nome": "[ERP] John Deere -30% R$120k/1000ha — horímetro >250h",
        "metric": "horimetro",
        "tipo": "threshold_max",
        "valor_ref": 250,
        "janela_min": 60,
        "severidade": "info",
        "acao_fisica": "",
        "titulo_tarefa": "John Deere -30% R$120k/1000ha — revisão 250h",
        "cargo_tarefa": "MECANICA",
        "porte": "grande",
        "meio": "maquina",
        "tela": "08 ERP",
        "origem_ep": "08C John Deere IA",
    },
]


def seed_regras_auto(propriedade, dry_run=False, *, apenas=None):
    """
    Cria (ou atualiza) as 20 RegraAlertaTelemetria para a propriedade.
    Idempotente: usa nome como chave (propriedade+nome unique não existe, então filtra).
    Retorna (criadas, atualizadas).

    `apenas` — iterável de `id` de REGRAS_AUTO. `None` (omissão) semeia todas,
    que é o comportamento anterior e não muda. Uma lista semeia só essas.

    POR QUE EXISTE O PARÂMETRO
    --------------------------
    A IA tem nove intents `automatizar_*` e, até agora, NENHUM deles semeava
    uma regra: todos delegavam numa função que só imprimia uma lista. Esta
    função era código morto — definida, correcta, e sem callers.

    Sem o filtro, "automatizar o pivô" semeia as vinte regras e diz ao
    produtor que configurou uma. Com o filtro, semeia uma — a que ele pediu —
    e a resposta é verdadeira. `id` e não `nome` porque o nome é o que o
    produtor lê e contém caracteres que mudam entre versões ("[GRÃO] BME280
    <60% → liga pivô 40mm"); o `id` é estável e é a chave natural.

    Levanta `ValueError` para um `id` desconhecido em vez de semear zero: um
    `id` errado é um bug de código, e um `ValueError` diz qual foi — ao
    contrário de devolver `(0, 0)`, que o handler reportaria ao produtor
    como "nada foi configurado" sem dizer porquê.
    """
    from app.models.iot import RegraAlertaTelemetria

    if apenas is None:
        regras = REGRAS_AUTO
    else:
        pedidos = set(apenas)
        regras = [r for r in REGRAS_AUTO if r.get("id") in pedidos]
        if not regras:
            raise ValueError(
                f"nenhum id de REGRAS_AUTO corresponde a {sorted(pedidos)!r}. "
                f"Ids validos: {sorted(r['id'] for r in REGRAS_AUTO)}"
            )
        desconhecidos = pedidos - {r["id"] for r in regras}
        if desconhecidos:
            raise ValueError(
                f"id(s) de regra inexistente(s): {sorted(desconhecidos)!r}. "
                f"Ids validos: {sorted(r['id'] for r in REGRAS_AUTO)}"
            )

    criadas = 0
    atualizadas = 0
    for r in regras:
        defaults = {
            "metric": r["metric"],
            "tipo": r["tipo"],
            "valor_ref": r["valor_ref"],
            "janela_min": r["janela_min"],
            "severidade": r["severidade"],
            "acao_fisica": r["acao_fisica"],
            "titulo_tarefa": r["titulo_tarefa"],
            "cargo_tarefa": r["cargo_tarefa"],
            "criar_tarefa": True,
            "ativa": True,
            "config": {
                "porte": r["porte"],
                "meio": r["meio"],
                "tela": r["tela"],
                "origem_ep": r["origem_ep"],
            },
        }
        if dry_run:
            exists = RegraAlertaTelemetria.objects.filter(
                propriedade=propriedade, nome=r["nome"]
            ).exists()
            if not exists:
                criadas += 1
            else:
                atualizadas += 1
            continue
        obj, created = RegraAlertaTelemetria.objects.update_or_create(
            propriedade=propriedade,
            nome=r["nome"],
            defaults=defaults,
        )
        if created:
            criadas += 1
        else:
            atualizadas += 1
    return criadas, atualizadas
