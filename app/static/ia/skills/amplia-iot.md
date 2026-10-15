# AmplIA SKI - IoT (CAN bus, BigBrother, mormaco, pivo, carbono, aerador)
name: amplia-iot
description: Skill IoT para AmplIA - CAN bus, BigBrother avicola, mormaco tilapia, pivo BME280, carbono, aerador.
version: 1.1.0
triggers: ["CAN bus", "BigBrother", "mormaco", "pivo", "carbono", "aerador", "irrigador"]
# handlers: intents que EXISTEM no registo. As de `iot.comando` exigem
# confirmacao em dois passos — a primeira devolve `needs_confirm` e nao
# executa. E' o unico caminho para mexer num equipamento.
handlers: ["status_sensores", "ultima_leitura", "alertas_telemetria", "listar_devices", "automatizar_pivo", "automatizar_aerador", "automatizar_bigbrother", "automatizar_moba", "ligar_irrigador", "desligar_irrigador", "melhor_pulverizar"]
# sem_intent: a logica existe e nao ha botao. Uma SKI que as escondesse
# ensinava a IA a procurar um botao que nao existe.
sem_intent:
  can_bus_telemetria: "CAN bus e' leitura de sensor: o caminho publico e' status_sensores e alertas_telemetria."
  avicultura_bigbrother: "existe como automatizar_bigbrother. O nome antigo nao existe."
  tilapia_mormaco: "resumo_aquatico e' o caminho publico; nao ha intent com este nome."
  pivo_bme280: "existe como automatizar_pivo. O nome antigo nao existe."
  carbono_mombak: "app/services/top_globais.py. Nenhuma intent expoe."
performance: {cache: 60, flags: ["iot.read", "iot.comando"]}
