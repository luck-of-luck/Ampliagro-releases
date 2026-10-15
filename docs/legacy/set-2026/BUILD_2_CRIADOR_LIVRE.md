# BUILD 2 — O Motor de Geração Dinâmica (Criador Livre)

> Estado: **implementado**. 68 tools no catálogo (eram 65). Suíte em
> **432/432 OK**. Verificação de ponta a ponta: `python docs/verificar_build2.py`.

## O que a IA faz (e o que ela não faz)

A IA **não escreve `.py`** e **não roda `makemigrations`**. Ela escreve
**metadados** — um schema de campos — e código genérico já existente
(`app/ia/dinamicos.py`) aplica esses metadados. Um "App Geladeira" criado por
voz é uma linha em `DynamicApp` mais N linhas em `DynamicField`.

```
"crie um controle de geladeira"
   → amplia_criar_entidade(nome, campos)      → DynamicApp + DynamicField
"coloca 12 kg de ração"
   → amplia_insert_record(slug, {alimento, quantidade_kg})  → DynamicRecord
"quanto tem?"
   → amplia_query_records(slug, filtros)      → leitura
```

## As três Tools Divinas

| tool | escreve? | confirma? | o que faz |
|---|---|---|---|
| `amplia_criar_entidade` | sim | **sim** | cria a ferramenta virtual |
| `amplia_inserir_registro` | sim | **sim** | grava um registro |
| `amplia_consultar_registros` | não | não | lê registros |

Por que **criar** precisa de confirmação, e não é preciosismo: criar schema é
uma decisão do produtor, não efeito colateral de conversa. Sem confirmação, uma
alucinação do modelo ("crie uma ferramenta de impostos") materializaria
estrutura na conta do produtor sem ele ter visto nada.

## A defesa contra alucinação de chave

Um SmolLM2 de 1,7B produz `{"alimento": "X", "idade_da_vaca": 10}` para um
schema que tem `alimento`/`quantidade_kg`. Isso não é hipotético: é o
comportamento esperado de um modelo sem restrição de schema, treinado para
continuar texto plausível.

**O comportamento anterior era "descartar e seguir"** — a chave ia para
`descartadas` e o registro era gravado com `ok: True`. Isso é a falha mais cara
possível num sistema de campo: o produtor pedia "registre a vacina da vaca", o
modelo mandava um campo a mais, esse campo sumia, e **ninguém era avisado**. Ele
confia no registro e volta a confiar no mês seguinte. E o modelo não recebia
nenhum indício de ter errado, então repetia o erro no registro seguinte.

Agora:

```
a IA envia:  {alimento: "Racao", quantidade_kg: 12, idade_da_vaca: 10}
a IA recebe: campo(s) inexistente(s): idade_da_vaca. Campos validos: alimento,
             quantidade_kg
o banco:     0 registros
```

A mensagem existe **para o modelo se corrigir**. Sem o nome do campo válido, a
defesa existe mas não é utilizável — e um modelo que não se corrige repete o
erro a cada registro. O ciclo completo (erro → corrige → grava) tem teste.

O modo tolerante (`estrito=False`) continua existindo para a rota do
formulário, onde um campo recém-removido do schema não pode custar ao produtor
a gravação inteira. **A decisão é do chamador, não da biblioteca.**

### Três camadas, e só uma depende do modelo

1. o modelo **declara** a chave (o `inputSchema` da tool);
2. a tool **recusa** a chave que não existe (validação contra o schema salvo);
3. `registrar()` **valida de novo** antes do `save`, dentro de
   `transaction.atomic`.

A terceira não depende do modelo se comportar. E a atomicidade significa que um
campo alucinado não deixa registro pela metade: o produtor não encontra estado
intermediário.

## Tenancy — onde mora o perigo real

`slug` tem unique constraint em **`(user, slug)`**, não global. O teste
`test_slug_unico_entre_usuarios_e_independente` fixa isso: **dois produtores
podem ter `slug="geladeira"` ao mesmo tempo.**

Logo `DynamicApp.objects.filter(slug=X).first()` pode devolver a ferramenta de
**outro produtor**. Se a tool combinar resolução + escrita, a gravação inteira
cai na ferramenta alheia. `resolver_app()` compõe `user` E `slug` no mesmo
`filter` — não há caminho que aceite slug sem dono, nem usuário anônimo.

Complemento: o erro de "não encontrei" **lista as ferramentas do próprio
usuário**. Isso é o que permite corrigir numa segunda chamada, e tem um teste
garantindo que o nome da tool alheia **não** aparece nessa lista.

## Filtro com chave errada devolve vazio — e isso é um bug disfarçado

`json_portatil.contem()` monta `dados__<chave>`. Chave alucinada → **VAZIO**.
SQL seguro, significado péssimo: o modelo lê "0 registros" e conclui que o
produtor não tem ração, quando o que houve foi ele ter errado o nome do campo.

Erro que vira conclusão errada é pior que exceção. `listar()` agora **levanta**,
e a tool devolve: `campo(s) de filtro inexistente(s): idade_da_vaca. Campos
filtráveis: alimento, quantidade_kg`.

## Parâmetros declarados (`params_schema`)

Medido antes de mudar: **0 de 68 tools declarava `properties`** no
`inputSchema`. `_schema_de_params` deduz de `exemplos` em dict, e nenhuma intent
do projeto usa exemplo em dict.

Para estas três tools isso é a **primeira** camada da defesa — o modelo saber o
nome exato do parâmetro. Adicionei `params_schema` com precedência no catálogo,
em vez de reciclar `exemplos`: `exemplos` tem duas funções diferentes hoje
(alimentar detecção e alimentar schema), e quando uma ganha conteúdo a outra
passa a depender de um detalhe. Verifiquei antes: `sandbox.catalogo()` só copia
`exemplos` para exibição, e a detecção não o lê.

## Performance

| decisão | motivo |
|---|---|
| `LIMITE_REGISTROS = 200` | é limite de **contexto**, não só de performance: o SmolLM2 tem janela de 4096 tokens |
| `MAX_RESULTADOS = 20` na resposta da tool | 200 registros JSON estouram o prompt e a resposta inteira se perde |
| `MAX_CAMPOS = 20` no schema | 60 campos estouram o prompt; e um modelo de 1,7B não planeja 60 campos |
| valor truncado em 60 chars na leitura | um valor de 2.000 caracteres derruba a janela |
| `prefetch_related` em `listar_ferramentas` | a paleta chama `descrever()` em cada app: sem isto, 1+N queries |
| `select_related` implícito nos índices `(app, user)` | toda listagem é pelo par |

## Bugs que os testes acharam

**1. `decimal.InvalidOperation` derrubava a tool com 500.** `_coagir` fazia
`Decimal(str(valor))` e o `except` do fim capturava `(ValueError, TypeError)` —
mas `InvalidOperation` herda de `ArithmeticError`. Um valor alucinado num campo
DECIMAL produzia erro 500 em vez de erro corrigível. **A defesa contra alucinação
de valor simplesmente não existia.** Vinha do D3 e era invisível porque nada
chamava `_coagir` com entrada de IA.

**2. `descrever_erro` quebrava no caminho de erro.** Eu escrevi
`values_list("slug")` (que devolve strings) e acessava `a.slug` → crash. Ou
seja: a função que dá a pista para o modelo se corrigir era justamente a que
quebrava quando o modelo errava o slug.

**3. A mensagem de erro era inutilizável em três pontos** — e os testes passavam.
Olhando a saída real, não o verde:

| antes | depois |
|---|---|
| `quantidade_kg: [<class 'decimal.ConversionSyntax'>]` | `quantidade_kg: 'muito' nao e um numero decimal` |
| `Campos validos: a, b. Campos validos em x: a, b` (2×) | `Campos validos: a, b` |
| `__filtros__: campo(s) de filtro inexistente(s)…` | `campo(s) de filtro inexistente(s)…` |

O `__filtros__` é o exemplo do porquê: uma chave interna que ajuda a camada de
código e não ajuda ninguém que lê. E a lista repetida é pior que não listar —
faz o modelo achar que são dois conjuntos e escolher um.

**4. As flags não estavam registradas.** `test_flags_conhecidas` (que já
existia) pegou. Flag não registrada é silenciosamente ignorada, e a tool passa
a valer como "sem permissão nenhuma". Registrei `criador_livre.read` /
`criador_livre.write` — namespace próprio porque estas tools mexem em
**metadados do sistema**, e o produtor precisa autorizar "crie uma ferramenta"
como ato diferente de "grave uma avaliação".

## O que o teste E2E provou que o teste direto não provava

`tests_dinamico_ponta_a_ponta.py` chama `executar_para()` — o caminho real —
e não o handler direto. Isso atravessou três camadas que também falham:

- a **allowlist** de `/api/amplia/exec/` (que exige o prefixo `amplia_`, como
  deve ser);
- o **cache** de resultado do `sandbox.executar`: uma recusa não pode entrar no
  cache como sucesso — há teste fazendo a mesma chamada duas vezes;
- a **serialização**: o `erro` precisa chegar ao modelo como texto.

Se a defesa só funciona quando chamada direto, ela não funciona.

Também há um teste que **verifica a promessa** — criar ferramenta não gera
arquivo `.py` — comparando o conjunto de arquivos antes e depois.

## Verificação manual

```bash
python docs/verificar_build2.py
```

Roda contra o banco de desenvolvimento, com usuário real, seguindo o roteiro
inteiro: criar → confirmar → aluncar campo → recusar → corrigir → gravar →
valor inválido → ler → filtro errado → invasão de outro produtor. Cria e apaga
os próprios dados ao final.

## O que não está pronto

- **Não há UI.** As tools existem e são governadas; falta a tela que desenha o
  formulário a partir de `descrever()`.
- **Não há `alterar_schema`**: uma ferramenta criada não muda de campos. É
  deliberado — migrar registro com schema alterado é a parte perigosa do
  Criador Livre e merece build própria.
- **Sem versionamento de schema.** Cada registro guarda `schema_snapshot`, o que
  dá a base para auditar, mas não para migrar.
