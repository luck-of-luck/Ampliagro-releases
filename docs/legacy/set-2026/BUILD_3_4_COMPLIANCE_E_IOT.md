# BUILD 3 (fecho) + BUILD 4 — Compliance e a Ponte IoT

> **BUILD 3**: blocklist determinística de compliance ético/ambiental.
> **BUILD 4**: a Ponte IoT — credencial, tópico MQTT e escopo C++.
> 71 tools no catálogo (eram 68). Suíte em **468/468 OK**.

---

# BUILD 3 — A Blocklist de Compliance

## Determinístico, sem uma única chamada de inferência

Uma lista de termos é uma **regra**, e regra implementada com modelo de linguagem
é regra que falha no dia em que mais importa. Se o sistema precisa dizer "não,
isso aqui não entra", essa resposta não pode depender de como o modelo "sentiu"
a frase. Logo: regex, sem inferência, sem fallback que "deixa passar se não
sabe".

## Onde se procura

No **nome** da ferramenta E nos **rótulos e chaves** de cada campo. Verificar só
o nome seria trivial de contornar:

```
criar_entidade("Controle de Área", campos=[{"rotulo": "Área desmatada"}])
```

O nome é inocente; o campo não. A ameaça real mora no campo que vai registrar a
infração.

## A ordem importa

A compliance roda **antes de tudo** — antes de validar tipo, antes do teto de
campos, e acima de tudo **antes de pedir confirmação**:

| ordem | comportamento | por que está errado |
|---|---|---|
| pedir "crio esta ferramenta?" → depois recusar | o produtor confirma algo que nunca vai acontecer | treina o produtor a confirmar sem ler |
| recusar primeiro | ele vê a recusa como primeira coisa | o custo de um clique é zero |

Há teste travando isso.

## Duas fronteiras deliberadas

**1. "queimada" NÃO entra.** Queimada de pasto é manejo conservacionista
legalizado, sob autorização do órgão ambiental. Bloquear a palavra bloquearia
uma técnica legítima.

**2. "desmatamento" entra; "desmatada" (particípio) NÃO.**

| escrito | resultado | por quê |
|---|---|---|
| `Desmatamento` | bloqueado | nomeia o ato |
| `Área desmatada` | **permitido** | é como se chama a ferramenta de *compliance* que verifica APP e CAR |

A segunda é decisão de produto, reversível em uma linha. O que a motivou: o
particípio é a forma natural de nomear um campo que **registra** área já
mapeada, e bloquear isso impediria justamente a ferramenta de controle que o
produtor precisa para trabalhar dentro da lei. Quem decide é o produtor e o
jurídico — por isso o termo recusado volta **sempre nomeado**, e nunca em
silêncio.

## Um furo de um caractere, encontrado por teste

`normalizar()` trocava `[_.-]+` por um espaço, mas não colapsava espaços já
existentes:

```
"madeira ilegal"  -> bloqueado
"madeira  ilegal" -> PASSAVA
```

Blocklist com furo de um espaço não é blocklist — e um LLM pequeno gera espaço
duplo com frequência não-negligível, porque o tokenizer BPE **tem token de espaço
duplo**. Corrigido com `re.sub(r"\s+", " ", t)`.

## A auditoria

`IAEvento` ganhou o tipo `compliance` — tipo próprio, e não um `erro` com texto
específico, porque a pergunta que o produtor faz ao auditor é *"o que foi
BLOQUEADO e por lei"*, e isso se responde por consulta:

```python
IAEvento.objects.filter(tipo="compliance")
```

Com `termo`, `onde`, `base_legal` (Lei 9.605/1998, art. 55) e o nome pedido.

---

# BUILD 4 — A Ponte IoT

## Integração, não duplicação

O projeto **já tem** IoT: `app/models/iot.py` com `Device`, e
`app/iot/views.py` com `push_telemetry`/`ttn_webhook` para LoRaWAN/TTN, por
`device_eui`. Aquele caminho responde *"qual telemetria chegou do rúter X"*.

Este responde a outra pergunta: *"o produtor que criou uma ferramenta dinâmica
quer um endpoint para a placa que ELE vai programar"*. São credenciais de naturezas
diferentes:

| | caminho legado | Ponte IoT (BUILD 4) |
|---|---|---|
| credencial | `device_eui` + API key global | segredo por endpoint, revogável |
| dono | `Device.propriedade` | `IotEndpoint.app` → `DynamicApp` → `user` |
| destino | `TelemetryData` | `DynamicRecord` (a tabela do Criador Livre) |

## As três tools

| tool | escreve? | confirma? | o que faz |
|---|---|---|---|
| `amplia_provisionar_endpoint_iot` | sim | **sim** | credencial + tópico + escopo C++ |
| `amplia_revogar_endpoint_iot` | sim | **sim** | corta o acesso |
| `amplia_consultar_endpoints_iot` | não | não | lista, **sem** o token |

## O token: 256 bits, só o hash, uma vez

```
secrets.token_urlsafe(32)   -> 256 bits de entropia
guardado                    -> sha256 em hex (64) + prefixo de 8
```

**Por que SHA-256 e não bcrypt:** com 256 bits aleatórios não existe ataque de
dicionário — não há senha fraca para quebrar. O hash existe para **exposição**:
um dump do banco não vira lista de credenciais no caminho de autenticação.

**Por que o prefixo:** o produtor precisa reconhecer *"qual é a válvula da
propriedade de Sorriso"*. 8 caracteres não autenticam nada.

## O token no tópico — risco declarado, não escondido

O formato pedido (`ampliagro/user_{id}/{slug}/{token}`) foi implementado. Mas o
custo precisa estar escrito:

> **Tópico MQTT aparece em log de broker, em qualquer `mosquitto_sub`, e na
> string de configuração do firmware. Quem lê o tópico, autentica.**

A mitigação é revogação. O padrão mais forte é **identificador público no
tópico + segredo no header**, e ele está entregue: `cpp_esp32_modo_seguro` usa
`ampliagro/u1/e1` (sem segredo) com `Authorization: Bearer`.

Implementado como pedido porque é decisão de quem opera o broker — mas a
diferença entre as duas opções está à vista, e é uma linha para trocar.

## O evento passa por `registrar()`

Este é o ponto de arquitetura da BUILD 4:

```python
registrar(endpoint.user, endpoint.app, {endpoint.campo_destino: valor}, estrito=True)
```

O caminho de escrita do dispositivo é **o mesmo** da digitação do produtor, com
a mesma validação estrita e o mesmo tenancy. Um dispositivo rogue não tem via
mais fácil que um dedo — escreve `{"temperatura": "quente"}` e é recusado, com
o nome do campo e o tipo esperado.

Se este módulo tivesse o próprio `INSERT`, existiria um **segundo lugar** onde
uma chave arbitrária entraria no banco — e é sempre o segundo lugar que ninguém
revisa.

## O endpoint público e sua postura

`POST /api/iot/dinamico/evento/` é o **único** endpoint anônimo do AmplIA.

| decisão | por quê |
|---|---|
| `csrf_exempt` | obrigatório. O cliente não tem token CSRF — e CSRF existe para sequestrar o *navegador* do usuário, que um ESP32 não tem |
| token inválido e revogado → **mesmo 401, mesmo texto** | 401 que distingue "não existe" de "revogado" é oráculo de enumeração, e endpoint público é onde se testa oráculo |
| valor fora do schema → **422** | o pedido está certo, o valor não é. 400 diria "arrume a requisição" |
| corpo binário → 400, nunca 500 | parsear bytes crus levantaria `UnicodeDecodeError`, e um 500 derruba o endpoint |
| `never levanta` em `receber_evento` | um 500 em endpoint público é convite para scanner |

## As recusas também viram registro

`IotEvento` guarda **recusa e aceite**. Um dispositivo que publica e vê o
evento ignorado, sem rastro, é um dispositivo que o produtor vai culpar por *"não
funcionar"* — e a causa real (campo inexistente no schema, token revogado) fica
invisível.

---

# Bugs que os testes acharam nesta entrega

**1. A propriedade "o token aparece uma vez" era falsa.** Eu gravava
`escopo_tecnico` no banco **com o token dentro** — no payload, no C++ e no
tópico embutido no C++. O segredo ficava no banco para sempre e apareceria em
qualquer tela que desenhasse o escopo. Corrigido na origem: o que persiste é o
escopo **com o segredo redigido** (`<TOKEN-REDIGIDO>`), e o completo vive só
na resposta. A primeira versão da redigir trocava um marcador que ninguém
inseria — não redigia nada, e o teste acusou.

**2. Bypass de um caractere na blocklist** (espaço duplo), descrito acima.

**3. Um teste meu afirmava o impossível.** Escrevi
`test_token_nunca_e_guardado_em_claro` e ele **falhou** — porque o formato de
tópico pedido coloca o token na coluna `topico`. Reescrevi o teste em vez de
ajustar: um teste que afirma o impossível é removido no primeiro *"arrume"*, e a
garantia real (o hash) ficaria sem cobertura. Agora ele afirma o que é
verdadeiro e **nomeia** onde o segredo aparece.

---

# O que não está pronto

- **Sem broker MQTT.** O escopo aponta para `mqtt.ampliagro.com:8883` (TLS),
  que não existe. O pedido era exatamente não subir o broker.
- **A publicação MQTT não está implemented.** Só o caminho HTTP
  (`/api/iot/dinamico/evento/`), que é o que o `cpp_esp32` **não** usa ainda —
  ele só faz `mqtt.publish`. Falta o assinante no broker.
- **Um endpoint por dispositivo, sem provisionamento em lote.** Dez sensores
  exigem dez chamadas; dá para fazer `provisionar` com lista depois.
- **Sem UI de configuração** dos endpoints.
- **`secure.setInsecure()` no C++** está marcado com aviso no próprio
  comentário. Para produção, o certificado do broker tem de ser fixado — é
  decisão de implantação, não de código.
