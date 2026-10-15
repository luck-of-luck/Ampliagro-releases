# Plano de Ação: Criador Livre de Ferramentas (Ampliagro OS)

## 1. Visão Geral e Posicionamento

> *"Plataforma única, offline-first, que unifica do solo ao mercado 11 cadeias produtivas em 707 culturas, da gestão do talhão à comercialização. Entrega governança, rastreabilidade e continuidade operacional mesmo sem conectividade, com inteligência local aplicada. Seu diferencial é a arquitetura extensível: permite o cadastro de APIs e dispositivos de IoT pelos próprios usuários, assegurando soberania sobre os dados e eliminando a necessidade de construir novos sistemas a cada demanda. Projetos, sensores e bases de terceiros passam a ser administrados integralmente no mesmo aplicativo, sem nova fragmentação."*

> **NUMERO MEDIDO, 2026-10-05.** A citacao acima e' o texto da proposta e
> fica como foi submetida — altera'-la seria falsificar um registo. Mas o
> numero que ela promete **nao e' o que o sistema tem**:
> `app/static/data/cultures-config.json` mede **488 culturas em 40 subgrupos**.
>
> A divergencia e' guardada por `tests/test_promessas_numericas.py`, que compara
> o catalogo com a constante `CULTURAS_PROMETIDAS = 488`. A escolha foi corrigir
> a promessa e nao fabricar 219 culturas: inventar dados agronomicos para bater
> num numero de slide e' o oposto da doutrina do projecto
> (`app/validators.py`: *"o sistema nunca promove uma afirmacao a medicao"*).
>
> Se a lista crescer, o teste falha ate a constante e este texto serem
> actualizados. E' assim que a promessa continua a ser verificavel.

O objetivo principal é materializar esse diferencial tecnológico transformando o Ampliagro em um verdadeiro "Sistema Operacional" universal. Nele, o usuário não fica restrito às ferramentas nativas. Ele tem liberdade absoluta para criar, via inteligência artificial, suas próprias soluções de software e integrações IoT (Internet das Coisas), para qualquer finalidade (do agronegócio à gestão doméstica).

## 2. A Jornada do Usuário (O Fluxo)
1. **O Desejo:** O usuário tem um problema ou necessidade específica (ex: "Quero saber quem pegou o último pedaço de bolo na geladeira").
2. **A Interação (Interface Assistida por IA):** O usuário abre a área "Criar Ferramenta" e descreve o que quer em linguagem natural, sem precisar saber programar.
3. **O Refinamento (IA Ativa):** A IA do sistema analisa o pedido e faz perguntas direcionadas para refinar a ideia e os requisitos (ex: "Você quer usar uma câmera ou um sensor de peso na geladeira? Como prefere ser notificado?").
4. **A Geração (Backend Dinâmico):** Com base nas respostas, a IA estrutura a lógica, o modelo de dados e o "código backend" necessário para suportar a ferramenta.
5. **O Encaminhamento (Broker de Desenvolvimento/IoT):**
   - *Se for apenas software (formulários, painéis, alertas):* A ferramenta é gerada e fica imediatamente disponível na interface do usuário.
   - *Se envolver hardware (IoT):* O sistema empacota o escopo técnico (código, requisitos de endpoints, casos de uso) e envia (ou abre um chamado) para um programador profissional, ou para a própria empresa, para a criação física do dispositivo.
6. **A Utilização:** O usuário passa a ter a ferramenta integrada ao seu painel, funcionando como um app nativo.

## 3. Arquitetura Técnica Necessária (Como implementar)

### 3.1. Módulo Assistente (Frontend / IA)
- Uma interface de chat conversacional focada em **Elicitação de Requisitos**.
- Integração com LLMs usando um *System Prompt* especialista em Análise de Sistemas e Arquitetura de Software. O papel da IA aqui não é apenas responder, mas *entrevistar* o usuário.

### 3.2. Motor de Geração Dinâmica (Core Backend)
- **Armazenamento Flexível:** Uso de bancos NoSQL ou `JSONFields` (no PostgreSQL do Django) para armazenar os dados de entidades que não existiam previamente.
- **APIs Virtuais:** Criação de rotas dinâmicas ou GraphQL. Quando a IA desenha uma ferramenta, ela gera os *schemas*, e o backend sabe automaticamente como receber POSTs e responder GETs para aqueles schemas.
- **Renderização Dinâmica (UI Driven by Data):** O frontend (React/Vue/Templates) deve ter componentes genéricos (Construtor de Formulários, Tabelas, Gráficos) que se montam baseados nas instruções JSON geradas pela IA.

### 3.3. Portal de "Fábrica" (Marketplace/Broker IoT)
- Um painel (tipo Kanban) onde os "Projetos de Hardware" demandados pelos usuários caem já perfeitamente documentados pela IA.
- O programador recebe: A rota da API que ele deve bater, o formato do JSON que ele tem que enviar e a regra de negócio. Ele só precisa focar no C++ do microcontrolador (ESP32, Arduino, Raspberry).

## 4. Desafios e Soluções

- **Segurança e Sandboxing:** Permitir que o usuário "crie código" pode abrir brechas de segurança.
  - *Solução:* A IA não gera "código Python" que roda no servidor. Ela gera **metadados e configurações (JSON/YAML)**. O nosso servidor lê essas configurações e aplica as regras de forma contida e segura.
- **Protocolos IoT (O Gargalo Físico):**
  - *Solução:* O Ampliagro disponibiliza um Gateway MQTT genérico. Toda vez que uma ferramenta IoT é criada, a IA gera credenciais únicas (Topic + Token MQTT) e essa é a "ponte" entre o hardware do programador e o sistema.

## 5. Próximos Passos (Proposta de MVP)

Para tornar essa ideia gigantesca em algo executável rapidamente, podemos dividir em fases:

1. **Fase 1: O "No-Code" Conversacional (Apenas Software)**
   - Criar o chat onde a IA entende um problema e gera formulários e relatórios dinâmicos. (Ex: "Ferramenta para anotar quanto gasto de ração para o cachorro" -> Cria a tabela, a tela de inserir e o gráfico).
2. **Fase 2: Mock de IoT e Webhooks**
   - Permitir que a ferramenta criada gere um Webhook (URL). Assim, é possível simular (via Postman ou pequenos scripts) o envio de dados externos para o sistema do usuário.
3. **Fase 3: O "Uber" dos Dispositivos Físicos**
   - Lançamento do portal onde a equipe de desenvolvimento recebe as requisições geradas pela IA e começa a enviar o hardware para a casa do cliente.
