# Alta Frequência de Disparo de Alertas — Ampliagro2

## Objetivo

Documentar os alertas cujo disparo é **muito frequente** (diário ou múltiplas vezes ao dia) e os limiares mínimos para evitar ruído excessivo no painel do produtor.

## Categorias de Alertas de Alta Frequência

### 1. Alertas de Condições Climáticas
- **Limiar de disparo:** mudança brusca de temperatura (>3°C em 1h) ou umidade relativa < 40%
- **Frequência esperada:** 1-3x por dia
- **Fonte de dados:** estações do usuário + Open-Meteo (padrão)
- **Exemplos:** "frio intenso", "calor extremo", "risco de geada"

### 2. Alertas de Pragas e Doenças
- **Limiar de disparo:** variação do NDVI > 15% em relação à média do talhão
- **Frequência esperada:** 1-2x por semana
- **Fonte de dados:** Sentinel-2 (10m), imagens de drone
- **Exemplos:** "praga detectada no talhão 3", "ataque de lagarta"

### 3. Alertas de Irrigação
- **Limiar de disparo:** déficit hídrico acumulado > 20mm ou umidade do solo < 30%
- **Frequência esperada:** 1-2x por dia (semanas secas)
- **Fonte de dados:** sensores IoT de solo + evapotranspiração
- **Exemplos:** "irrigar talhão 5", "déficit hídrico crítico"

### 4. Alertas Financeiros (Custo)
- **Limiar de disparo:** custo operacional > R$ 50.000 em 24h ou ultrapassagem de 10% do orçamento diário
- **Frequência esperada:** 1-3x por dia
- **Fonte de dados:** ERP, planilhas de custeio
- **Exemplos:** "custo de fertilizante acima do previsto"

### 5. Alertas de Colheita
- **Limiar de disparo:** teor de matéria seca > 85% ou índice de colheita > 0.9
- **Frequência esperada:** 1x por dia (período de colheita)
- **Fonte de dados:** satélites + modelos fenológicos
- **Exemplos:** "milho pronto para colheita no talhão 2"

## Padrões de Implementação

- Todos os alertas usam o mesmo padrão de resposta: `{ok: true, resposta: ..., dados: {...}}`
- Limiares são parametrizáveis via configuração da propriedade
- Histórico de disparos é mantido no painel (4x2 grid)

## Monitoramento

- Logs de disparo em Prometheus/Grafana
- Dashboard de alertas por frequência de disparo
- Métricas de ruído (alertas falsos / totais)
