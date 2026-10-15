# Estrutura e Planejamento: mcp-Ampliagro_amplIA

## 1. O que é o `mcp-Ampliagro_amplIA`?
O **Model Context Protocol (MCP)** é um padrão aberto que permite que Inteligências Artificiais interajam diretamente com sistemas locais, bancos de dados e APIs.
O `mcp-Ampliagro_amplIA` será o **servidor MCP medido** do Ampliagro. Ele é a "mão" e os "olhos" da AmplIA (sua IA interna) dentro do sistema operacional Ampliagro.

Em vez da IA apenas gerar texto, ela usará este MCP para **executar ações reais**: criar ferramentas dinâmicas no banco de dados, alocar chaves MQTT para dispositivos IoT, ler o estado atual das culturas e gerar formulários na tela do usuário.

---

## 2. Técnicas e Padrões Arquiteturais

Para que a AmplIA tenha "livre arbítrio" seguro e funcione offline-first, utilizaremos as seguintes técnicas:

### 2.1. Python + Django ORM Integration
Como o Ampliagro roda em Django/Python, o servidor MCP será escrito em **Python** (usando a SDK oficial do MCP: `mcp`). Ele rodará de forma acoplada (ou paralela) ao backend, importando os modelos do Django nativamente para garantir que a IA respeite as regras de negócio e de governança do sistema.

### 2.2. Schema-Driven Development (Dynamic Models)
A IA não vai criar arquivos `.py` novos para criar tabelas (isso exigiria reiniciar o servidor). A técnica usada será a **Tabela de Entidades Virtuais (EAV - Entity-Attribute-Value)** ou **PostgreSQL JSONFields**.
- O MCP terá ferramentas para "Registrar Nova Entidade". A IA manda um JSON com o nome da ferramenta e os campos, e o MCP salva esses metadados. O frontend renderizará as telas lendo esses metadados.

### 2.3. Abstração de Hardware (IoT Bridge)
Para a integração com IoT, usaremos o padrão de **Gerenciamento Dinâmico de Tópicos MQTT e Webhooks**. O MCP não programa o hardware; ele provisiona a ponte.

### 2.4. RAG de Contexto (Retrieval-Augmented Generation)
Antes da IA tomar uma decisão de criar uma ferramenta nova, o MCP expõe uma rota (Resource) para a IA ler o que já existe no sistema do produtor. Assim, ela não cria uma "ferramenta de geladeira" se já existir uma.

---

## 3. Ferramentas (Tools) que o MCP vai expor para a AmplIA

Para que a AmplIA seja onipotente no sistema, o MCP precisa registrar os seguintes `tools` (funções chamáveis pela IA):

1. `amplia_analyze_context(user_id)`
   - **Descrição:** Lê o perfil do usuário, quais ferramentas ele já possui e qual o seu foco principal (Agro, Indústria, Doméstico).

2. `amplia_create_dynamic_tool(name, description, schema_json, requires_iot)`
   - **Descrição:** O motor principal. A IA usa essa ferramenta para inserir a nova ferramenta no banco de dados, definindo os campos que o usuário terá que preencher na tela (ex: texto, número, foto).

3. `amplia_provision_iot_endpoint(tool_id, protocol="MQTT|HTTP")`
   - **Descrição:** Caso a ferramenta precise de IoT, a IA chama essa função para gerar um Token de Acesso, um Tópico MQTT único e as URLs de API para aquele projeto específico.

4. `amplia_dispatch_developer_ticket(tool_spec_json)`
   - **Descrição:** Cria automaticamente um card/ticket na fila do time de desenvolvimento/parceiros com o escopo técnico do hardware que precisa ser soldado/programado.

---

## 4. Estrutura de Diretórios Recomendada

Podemos acoplar o servidor dentro da estrutura atual:

```text
C:\Trabalho\Projetos\Ativos\Ampliagro\
├── app\
│   ├── amplIA_mcp\               # O pacote principal do servidor MCP
│   │   ├── __init__.py
│   │   ├── server.py             # Instância do mcp.server.Server
│   │   ├── tools\                # As funções que a IA pode chamar
│   │   │   ├── dynamic_db.py     # Lógica de criar ferramentas no banco
│   │   │   ├── iot_manager.py    # Geração de tokens e endpoints
│   │   │   └── broker.py         # Lógica de enviar pro Kanban do dev
│   │   └── resources\            # Contextos que a IA pode ler (Logs, Status)
│   └── ...
```

---

## 5. Plano de Desenvolvimento (Roadmap MCP)

### Etapa 1: Fundação do Servidor MCP
- Criar o arquivo `server.py` rodando o MCP SDK via *stdio* ou *SSE*.
- Conectar o script MCP ao contexto do Django (`django.setup()`) para poder ler e escrever no banco de dados.

### Etapa 2: Motor Dinâmico (Banco de Dados e UI)
- Criar os modelos Django de Metadados: `DynamicApp`, `DynamicField`, `DynamicRecord`.
- Implementar a tool `amplia_create_dynamic_tool` no MCP.
- (No Frontend): Criar o interpretador que lê esses modelos e desenha a tela (Construtor de UI).

### Etapa 3: Ponte IoT e Fila de Desenvolvimento
- Implementar a tool `amplia_provision_iot_endpoint`.
- Gerar chaves aleatórias seguras (Tokens) atreladas à `DynamicApp`.
- Implementar o `amplia_dispatch_developer_ticket`.

## Conclusão
Com o `mcp-Ampliagro_amplIA` rodando, você não precisará programar cada ferramenta nova. Você apenas conversará com a AmplIA. A AmplIA decidirá: *"Ok, preciso usar a tool `amplia_create_dynamic_tool`"* e executará a chamada para o MCP, que alterará o banco do sistema instantaneamente. O usuário só dá "F5" e a ferramenta aparece.
