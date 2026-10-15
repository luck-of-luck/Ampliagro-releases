# Plano de Implementação: Composição Dinâmica de Widgets por Intent

## 0. Contexto e Alinhamento com VISAO.MD

Este plano está alinhado com os princípios estabelecidos em docs/VISAO.md:

- Seção 0.2 (Honestidade): A solução propõe que a IA sugira composições de widgets existentes sem inventar dados. O campo `widget_composicao` é opcional e indica apenas como os dados já obtidos pelos intents devem ser apresentados.

- Seção 0.1 (Diferencial): Mantém o vocabulário de `fonte_dado` (medido, declarado, sem_dado, suspect, simulado) intacto - nenhuma alteração na fonte dos dados.

- Seção 5.1: Segue o processo: escolheu problema, escolheu fase, escreveu critério de saída, implementará, rodará scanner.

- Seção 5.2 #1: Não gera conteúdo para cumprir metas - apenas sugere como apresentar dados já verificados.

- Seção 5.2 #5: Toda escrita na base de dados declara `fonte_dado` - nenhuma alteração na camada de dados.

## 1. Problema

A IA interna não consegue adaptar a apresentação dos resultados às perguntas específicas do usuário. Perguntas como:

- "O que foi feito na última semana?"
- "Vai chover nesta semana?"

Recebem apenas texto de resposta, sem poder mostrar múltiplos widgets relevantes ou formatos adequados.

## 2. Solução: Fase 1 - Implementação Rápida

### 2.1 Objetivo
Adicionar campo opcional `widget_composicao` aos resultados dos intents, permitindo que a IA sugira como os dados devem ser apresentados usando widgets existentes do `CATALOGO_IA`.

### 2.2 O que muda (sem invenção)

Backend (app/ia/sandbox.py):
- Campo opcional `widget_composicao` extraído de resultados de intents
- Quando presente: frontend renderiza widgets sugeridos
- Quando ausente: comportamento atual (sem mudar)

Frontend (JavaScript do dashboard):
- Verificar se `widget_composicao` está presente
- Renderizar múltiplos widgets conforme a composição sugerida
- Fallback para widget padrão quando campo ausente

Funções auxiliares (app/ia/palco.py):
- `compor_historico_semana()` -> retorna [kpi-linha, tabela]
- `compor_previsao_chuva()` -> retorna [kpi-linha, kpi-numero]
- `compor_gastos_por_categoria()` -> retorna [tabela, kpi-numero]

### 2.3 Exemplo de fluxo

Pergunta: "O que foi feito na última semana?"

Resposta com `widget_composicao`:

```json
{
  "ok": true,
  "resposta": "15 operações, R$ 25.000 em insumos",
  "widget_composicao": [
    {"tipo": "kpi-linha", "titulo": "Operações por dia", "config": {...}},
    {"tipo": "tabela", "titulo": "Top 5 operações", "config": {...}}
  ]
}
```

Frontend mostra: texto + gráfico de linhas + tabela

## 3. Arquivos a modificar

1. app/ia/sandbox.py - extrair widget_composicao do retorno dos intents
2. Frontend JS - renderizar composição quando presente
3. app/ia/palco.py - funções auxiliares para composições comuns
4. Handlers de intents relevantes - incluir widget_composicao quando aplicável

## 4. Testes necessários

```python
def test_intent_retorna_widget_composicao_quando_aplicavel():
    Testa widget_composicao em intents relevantes
    # Pergunta sobre ultima semana -> retorna composição
    # Pergunta sobre previsão de chuva -> retorna composição
    # Pergunta irrelevante -> comportamento atual (sem widget_composicao)
```

## 5. Critério de Saída (colocar em console.md ANTES de codar)

```
CRITERIO DE SAIDA PARA WIDGET_DINAMICO_FASE_1:
- [ ] python manage.py test app.amplia_mcp app.ia.tests_texto -> OK
- [ ] Intent de resumo semanal retorna layout adequado
- [ ] Intent de previsao de chuva retorna layout adequado
- [ ] Frontend renderiza multiplos widgets quando widget_composicao presente
- [ ] Sem widget_composicao, comportamento identico ao atual
- [ ] Nenhum dado inventado - apenas sugestao de apresentacao
- [ ] semgrep/bandit clean
- [ ] Documentacao atualizada
```

## 6. Estimativa

- Backend: 1-2 dias
- Frontend: 1-2 dias
- Testes: 1 dia
- Revisao: 0.5 dia
- Total: ~3.5 dias

## 7. Próximos passos

1. Colocar critério de saída em console.md
2. Implementar backend (sandbox + handlers)
3. Implementar frontend
4. Escrever testes
5. Rodar scanner de seguranca
6. Merge e deploy
