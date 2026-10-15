# AmplIA OS - Mapa de Implementação e Contexto para Agentes de Código

> **⚠️ ATENÇÃO AGENTE DE CÓDIGO (SUPER CONSTRUTOR) ⚠️**
> Você está assumindo a arquitetura do **AmplIA OS**, o núcleo de inteligência e extensão do sistema **Ampliagro**. Leia todo este contexto atentamente antes de escrever qualquer código. Seu objetivo é estruturar o sistema em módulos (Packs) seguindo as regras de negócio abaixo. A prioridade é segurança (sandboxing), arquitetura orientada a metadados (EAV/JSONB) e escalabilidade offline-first.

---

## 1. O CONTEXTO (O que estamos construindo)
O Ampliagro é uma plataforma de gestão agrícola offline-first (4 cadeias, 488 culturas).
O **AmplIA OS** é a evolução desse sistema: um Companheiro Cognitivo medido. Ele não é apenas um chat. A IA deve ter "braços e asas" para ler cadernos velhos via OCR, processar ordens em áudio do campo, criar formulários e aplicativos dinâmicos sem alterar código-fonte, barrar intenções ilícitas do usuário e, no futuro, despachar drones e acionar irrigação via IoT.

**A regra de ouro:** O sistema entrega valor massivo e mágico hoje (Pack 0), para gerar o vício e permitir o domínio físico pago no futuro (Pack 5).

---

## 2. A STACK TECNOLÓGICA OBRIGATÓRIA
- **Core Backend:** Python + Django (Framework principal) e Django REST Framework / FastAPI.
- **Protocolo de IA:** Servidor MCP (Model Context Protocol).
- **Banco de Dados:** PostgreSQL (Uso pesado de `JSONField` / `JSONB` para armazenamento de dados flexíveis gerados pela IA).
- **Assincronismo e Agentes:** Celery (com Redis) ou Temporal.io.
- **Edge / IoT:** Mosquitto (MQTT) ou HiveMQ para telemetria e controle de hardware.
- **Segurança (Guardrails):** NeMo Guardrails ou LlamaGuard.

---

## 3. MAPA DE BUILDS (As Fases de Implementação)

O agente deve implementar as funcionalidades seguindo rigorosamente a ordem das BUILDS abaixo:

### 🏗️ BUILD 0: A Fundação MCP e Conexão Django
**Objetivo:** Criar a ponte para a IA enxergar e interagir com o sistema.
- Criar a estrutura do app Django `amplia_mcp`.
- Configurar um servidor MCP (stdio ou SSE) rodando em background ou paralelo.
- **Conexão de Contexto:** O script do MCP deve carregar o contexto do Django (`django.setup()`) para poder fazer queries nativas no ORM e respeitar o multitenant (cada usuário só vê seus dados).

### 🧲 BUILD 1: O Efeito Hook (OCR Mágico e Áudio Natural)
**Objetivo:** Implementar o "Pack 0" - valor imediato sem hardware.
- Criar endpoints e workers (Celery) para receber fotos de NFe e "cadernos sujos".
- Integrar chamadas à API de OCR e LLM Vision (ex: GPT-4o ou Claude 3.5 Sonnet) para extrair os dados e popular os modelos Django nativos de talhões, histórico e estoque.
- Criar o endpoint de **Áudio Operacional**: Recebe áudio sujo (ex: WhatsApp), passa no Whisper (OpenAI/Local) e o LLM converte em ações (`update_stock()`, `create_service_order()`).

### 🧬 BUILD 2: O Motor de Geração Dinâmica (Criador Livre)
**Objetivo:** Permitir que a IA crie ferramentas novas e armazene dados que não existem no schema original.
- Criar os modelos base em Django:
  - `DynamicEntity` (Nome da ferramenta criada pela IA, ex: "Controle de Geladeira").
  - `DynamicSchema` (Definição dos campos em JSON, gerado pela IA).
  - `DynamicRecord` (As linhas da tabela de fato, com `JSONField` guardando as informações).
- Implementar as *Tools* no MCP: `amplia_create_entity(schema)`, `amplia_insert_record(data)`.

### 🛡️ BUILD 3: O Guardião Neural (AI Guardrails)
**Objetivo:** Garantir que a IA não permita a criação de ferramentas ou processos ilícitos.
- Criar um middleware / interceptador antes de qualquer chamada do MCP de criação.
- Implementar prompt de validação ética rigoroso ou integrar biblioteca de Guardrails. Exemplo: Bloquear criação de metadados focados em "desmatamento" ou "lavagem de grãos".

### 🪽 BUILD 4: As Asas (Agentes Proativos e IoT Bridge)
**Objetivo:** Autonomia em background e geração de credenciais de hardware.
- **Workers Autônomos:** Criar rotinas agendadas (Cron/Celery) onde um Agente LLM acorda, olha a previsão do tempo, cruza com tarefas agendadas e *sugere* re-agendamento via Push Notification.
- **Ponte IoT:** Tool `amplia_provision_iot_endpoint()`. Gera uma chave JWT, cria um ID de Tópico MQTT (ex: `fazenda/1/device/534`) e devolve para o usuário/desenvolvedor o escopo técnico para conectar a válvula/drone.

### 🎨 BUILD 5: O Front-End Vivo e Dashboards Dinâmicos (Generative UI)
**Objetivo:** A IA não apenas devolve texto; ela constrói "mesas de operação" dinâmicas. Toda vez que a IA precisar expor dados complexos (ex: histórico de um talhão), ela usará um Dashboard reservado chamado **Preset "Amplia"**.
- **O Preset "Amplia" (Imutável e Fluido):** Este é o painel oficial da IA. Quando o produtor pergunta *"o que aconteceu hoje no talhão 2?"*, a IA busca o contexto e desenha *Widgets* (gráficos de clima, cards de custo, tabelas de aplicação) diretamente nesse preset. O preset se molda à pergunta atual.
- **Feedback Loop (Like / Dislike):** O painel gerado terá botões de avaliação.
  - *Like:* O sistema salva essa estrutura de widgets como uma preferência de sucesso (ajudando o Machine Learning a acertar de primeira no futuro).
  - *Dislike:* A IA limpa a tela, entende que errou o contexto, e faz perguntas para repensar e desenhar um novo dashboard mais completo.
- **A Efetivação (Clonar Preset):** Se o produtor amar o painel temporário que a IA gerou no Preset "Amplia", ele clica em "Salvar como meu Preset". O sistema clona a estrutura e transforma aquele dashboard dinâmico em uma visão fixa e persistente para o usuário usar todos os dias.
- **Protocolo de Renderização:** A IA usará *Tools* (ex: `render_widget(tipo, dados)`) para instruir o frontend (JS/React) a montar as peças do Bento Grid na tela em tempo real.

---

## 4. DIRETRIZES DE ARQUITETURA PARA O AGENTE
1. **Abstração Total de IA:** Isole as chamadas de LLM (GPT, Claude, Llama) em uma camada `llm_gateway`. O resto do sistema não pode saber qual IA estamos usando hoje, para ser fácil trocar no futuro (Local vs Cloud).
2. **Segurança de Execução:** Nunca, em hipótese alguma, use a função `eval()` ou `exec()` do Python para rodar código gerado pela IA no servidor. Todas as lógicas customizadas criadas pela IA devem ser traduzidas em regras estruturadas (JSON) ou usar WebAssembly se no futuro precisarem ser compiladas.
3. **Não poluir Migrations:** A magia da IA "criar ferramentas" ocorre no banco de dados lendo `DynamicSchema`. Não crie arquivos `.py` dinamicamente no `models/`. Use tabelas dinâmicas.
4. **Offline-First Resilience:** Se a API de IA da nuvem cair, o sistema principal de registro (Django) tem que continuar de pé.

> **AGENTE:** Ao iniciar a implementação, comece sempre pela `BUILD 0`. Valide a arquitetura do projeto atual (Django) antes de inserir pastas MCP. Boa codificação.
