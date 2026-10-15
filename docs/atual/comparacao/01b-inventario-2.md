
## 2.3 Financeiro, custos e fiscal

| Entidade | Campos-chave |
|---|---|
| `LancamentoFinanceiro` | tipo, categoria (12), valor, data, participante + doc cripto, talhão, safra, pago, conta bancária, doc LCDPR |
| `LancamentoDetalhado` + `CentroCusto` + `CustoProducao` | 30 categorias detalhadas; custo safra/talhão → total, R$/ha, R$/saca, receita, lucro, margem |
| `ContaAPagar` / `ContaAReceber` (`contas.py`) | vencimento, contraparte, estado, fonte_dado, baixa gera lançamento |
| `ContaBancaria` + `MovimentacaoBancaria` + `ConciliacaoBancaria` | banco/agência/conta; OFX; conciliação |
| `NotaFiscalImportada` | chave 44 dígitos anti-duplicidade, fornecedor, total |
| `RelatorioTemplate` / `RelatorioGerado` | PDF/Excel/CSV, config JSON |

## 2.4 Máquinas, logística, equipe

| Entidade | Campos-chave |
|---|---|
| `Maquinario` + `ManutencaoMaquinario` | tipo (8), marca/modelo/ano, horas_uso, depreciação linear calculada |
| `Rota` + `Romaneio` + `Frete` | origem/destino, km, GeoJSON OSRM; pesos bruto/líquido, quebra, CT-e; frete valor/pago |
| `Funcionario` (~100 cargos) | nome, cargo, salário, admissão/demissão, login operário |

## 2.5 Pecuária, aquicultura, apicultura, agrofloresta

| Entidade | Campos-chave |
|---|---|
| `Animal` + `AnimalIndividual` | espécie (9), raça, qtd; brinco, brinco eletrônico, sexo, nascimento, pai/mãe |
| `Pesagem`, `EventoSanitario`, `ProtocoloSanitario` | peso/data; vacina/vermífugo/tratamento, dose, próxima dose |
| `Piquete` | área, UA/ha, status descanso/pastejo/manutenção, animais M2M |
| `Racao` | estoque kg, espécie-alvo, fase, composição, custo/kg |
| `LoteAquatico` + `Despesca` | espécie (9), sistema (6: viveiro, tanque-rede, bioflocos…), biomassa média; kg, valor |
| `ApiarioColmeia` + `ProducaoApiario` | identificação, abelha, local; mel kg, cera kg, valor |
| `Agrofloresta` / `BiomassaEucalipto` | consórcio, área, carbono (t) |

## 2.6 IoT, clima e criador livre

| Entidade | Campos-chave |
|---|---|
| `Gateway` + `Device` + `TelemetryData` | LoRaWAN/celular/Wi-Fi/satélite; tipos METEO/SOLO/NIVEL/MAQUINARIO/ANIMAL/DRONE/ENERGIA; ~40 métricas |
| `RegraAlertaTelemetria` + `ComandoDevice` | limiares; comando MQTT/HTTP/LoRaWAN/CoAP |
| `FonteDadosExterna` | INMET, NASA POWER, Open-Meteo, Sentinel-2 NDVI, ChirpStack, TTN |
| `EstacaoMeteo` + `LeituraSensor` | código INMET, lat/lon; qualidade good/suspect/bad |
| `DynamicApp` + `DynamicField` + `DynamicRecord` | criador livre: 9 tipos de campo, escopo por usuário |
