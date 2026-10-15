"""
Sensores exóticos — resolve 5 dos 12 "com restrições" do estudo 50 vídeos
- Aveconfort (bem-estar ave) — Bibi, Lego, Big Brother
- Morcego restauração (áreas desmatadas)
- Tilápia pele curativo (UFC curativo queimados)
- Eucalipto biomassa + Agrofloresta
- Cavalo sono (por que dorme em pé)
"""

# Métricas novas para TELEMETRY_METRIC_CHOICES (iot/models)
METRICAS_EXOTICAS = [
    ("aveconfort", "Aveconfort (índice bem-estar 0-100)"),
    ("fotogrametria_angulo", "Fotogrametria ângulo ósseo (°)"),
    ("movimento_ave", "Movimento ave (Big Brother Agrisolus)"),
    ("consumo_agua_ave", "Consumo água ave (mL/dia)"),
    ("mormaco_tilapia", "Tilápia pele curativo (unidades)"),
    ("biomassa_eucalipto", "Biomassa eucalipto (m³/ha)"),
    ("plantio_orquidea", "Orquídea cultivo (umidade %)"),
    ("sono_cavalo", "Sono cavalo em pé (min/dia)"),
    ("atividade_morcego", "Atividade morcego (detecções/noite)"),
    ("qualidade_mel_camoatim", "Mel camoatim (°Brix)"),
    ("flat_iron_rendimento", "Flat iron rendimento (%)"),
]

# Regras de alerta exóticas (alert_engine)
REGRAS_EXOTICAS = [
    dict(
        metric="aveconfort",
        tipo="threshold_min",
        valor_ref=65,
        mensagem="Aveconfort baixo (<65) — estresse térmico, ligar pad cooling",
    ),
    dict(
        metric="fotogrametria_angulo",
        tipo="threshold_max",
        valor_ref=12,
        mensagem="Ângulo ósseo >12° — risco má formação perna",
    ),
    dict(
        metric="movimento_ave",
        tipo="threshold_min",
        valor_ref=30,
        mensagem="Ave parada >2h — risco coccidiose (Big Brother)",
    ),
    dict(
        metric="atividade_morcego",
        tipo="threshold_min",
        valor_ref=15,
        mensagem="Morcego <15 detecções/noite — falha restauração",
    ),
    dict(
        metric="mormaco_tilapia",
        tipo="threshold_min",
        valor_ref=100,
        mensagem="Estoque pele tilápia <100 — acionar UFC fábrica",
    ),
    dict(
        metric="biomassa_eucalipto",
        tipo="threshold_min",
        valor_ref=180,
        mensagem="Biomassa eucalipto <180m³/ha — adubar",
    ),
    dict(
        metric="sono_cavalo",
        tipo="threshold_max",
        valor_ref=180,
        mensagem="Cavalo em pé >180min — verificar cólica",
    ),
]

# Mapeamento vídeo → sensor
VIDEO_SENSOR_MAP = {
    "Bibi garnizé": ["aveconfort", "movimento_ave"],
    "Rosella": ["aveconfort"],
    "Pônei": ["sono_cavalo"],
    "Cavalo dorme em pé": ["sono_cavalo"],
    "Tilápia pele": ["mormaco_tilapia"],
    "Morcego": ["atividade_morcego"],
    "Eucalipto biomassa": ["biomassa_eucalipto"],
    "Orquídea": ["plantio_orquidea"],
    "Camoatim mel": ["qualidade_mel_camoatim"],
    "Flat iron": ["flat_iron_rendimento"],
    "Aveconfort": ["aveconfort", "fotogrametria_angulo"],
}


def registrar_metricas_exoticas():
    """Chamado em migrate/check para garantir que choices existam."""
    return METRICAS_EXOTICAS
