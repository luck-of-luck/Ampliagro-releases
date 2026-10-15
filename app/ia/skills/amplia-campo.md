# AmplIA SKI - Campo (VRA NDVI, SPD, praga AI, guidance)
name: amplia-campo
description: Skill campo para AmplIA - VRA NDVI 10m Sentinel-2, SPD MO 2->3,4%, praga AI foto, guidance A-B.
version: 1.1.0
triggers: ["VRA", "NDVI", "SPD", "praga", "guidance", "as-applied"]
# handlers: intents que EXISTEM no registo. A lista e' conferida por
# `GET /api/amplia/skills/` e por `SkillsTest::test_nenhum_handler_fantasma`.
# Nao e' uma lista de desejos: um nome aqui que nao exista e' uma tool que o
# modelo vai chamar e levar `tool_fora_do_catalogo`.
handlers: ["analise_solo", "recomendacao_adubacao", "automatizar_spd", "monitorar_pragas", "alerta_pragas", "melhor_pulverizar", "ultimas_aplicacoes"]
# sem_intent: a logica existe e e' boa, mas NAO ha intent que a exponha. Um
# agente nao a pode chamar — e, antes desta versao, achava que podia. Um nome
# aqui e' uma promessa que o sistema ainda nao cumpre, dita como promessa.
sem_intent:
  vra_ndvi_prescricao: "VRA/NDVI de 10 m sobre Sentinel-2 vive em app/services/ndvi.py; a intent mais perto e' recomendacao_adubacao."
  praga_ai_foto: "app/services/top_globais.py. Serve por monitorar_pragas e alerta_pragas, que sao o caminho publico."
  guidance_ab: "app/services/top_globais.py. Nenhuma intent expoe."
  as_applied_gap: "app/services/top_globais.py. Nenhuma intent expoe."
performance: {cache: 60, flags: ["campo.read", "iot.read"]}
