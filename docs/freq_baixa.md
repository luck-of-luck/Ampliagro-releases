# Baixa Frequência de Disparo de Alertas — Ampliagro2

## Objetivo

Documentar os alertas cujo disparo é **raro** (semanal, quinzenal ou mensal) e que indicam eventos significativos de longo prazo ou mudança de estado do sistema.

## Categorias de Alertas de Baixa Frequência

### 1. Alertas de Evolução de Safra
- **Limiar de disparo:** produtividade final divergente > 20% do planejado
- **Frequência esperada:** 1x por safra
- **Fonte de dados:** colheita real vs. planejado (ERP)
- **Exemplos:** "safra 2024/25 fechou 25% abaixo do orçado"

### 2. Alertas de Sustentabilidade do Solo
- **Limiar de disparo:** matéria orgânica < 2% ou pH fora de 5.5-6.5 por 2 safras consecutivas
- **Frequência esperada:** 1x por ano
- **Fonte de dados:** análises laboratoriais + histórico
- **Exemplos:** "solo acidificado no talhão 7", "teor de MO crítico"

### 3. Alertas de Rotação de Culturas
- **Limiar de disparo:** mesma cultura no mesmo talhão > 2 ciclos consecutivos
- **Frequência esperada:** 1x por 2-3 anos
- **Fonte de dados:** histórico de plantio
- **Exemplos:** "recomenda rotação: soja → milho → cobertura"

### 4. Alertas de Manutenção de Equipamentos
- **Limiar de disparo:** horas de operação > 80% do intervalo de revisão
- **Frequência esperada:** 1-2x por mês
- **Fonte de dados:** IoT / horímetro do equipamento
- **Exemplos:** "trator 1: revisão em 50h", "pivô 3: troca de óleo"

### 5. Alertas de Compliance e Documentação
- **Limiar de disparo:** licença ambiental < 60 dias para vencer ou NF-e não emitida > 5 dias
- **Frequência esperada:** 1x por trimestre
- **Fonte de dados:** ERP / documentos fiscais
- **Exemplos:** "licença de uso de água vence em 45 dias"

### 6. Alertas de Mercado / Comercialização
- **Limiar de disparo:** preço futuro (hedge) > 15% acima do custo total ou < 90% do custo
- **Frequência esperada:** 1-2x por mês
- **Fonte de dados:** cotações B3 / CEPEA
- **Exemplos:** "oportunidade de hedge milho mar/25 a R$ 68/sc"

## Padrões de Implementação

- Alertas de baixa frequência **não** entram no grid 4x2 diário
- São exibidos no painel "Visão Geral" ou relatório semanal/quinzenal
- Podem acionar notificações por e-mail/Telegram (configurável)
- Têm prioridade de exibição **abaixo** dos alertas de alta frequência

## Monitoramento

- Contagem de disparos por mês (esperado ≤ 5)
- Taxa de conversão em ação (alertas que geraram task/atividade)
- Tempo médio de resolução

## Relacionamento com `alta_frequencia.md`

| Característica          | Alta Frequência        | Baixa Frequência       |
|-------------------------|------------------------|------------------------|
| **Intervalo típico**    | Horas / 1-3x/dia       | Semanas / 1-2x/mês     |
| **Grid 4x2**            | Sim (topo)             | Não (painel lateral)   |
| **Ação imediata**       | Sim (irrigar, pulverizar) | Planejada (rotação, hedge) |
| **Risco de ruído**      | Alto — exige threshold | Baixo — eventos reais  |