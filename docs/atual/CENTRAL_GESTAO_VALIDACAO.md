# Central de Gestão — evidência de verificação

## Navegador, 08/10/2026

Servidor local isolado em 127.0.0.1, banco SQLite temporário e usuário fictício.
Login e CSRF permaneceram ativos. Nenhum registro de produção foi alterado.

- Marcar pagamento sem data mostrou o erro e preservou os campos preenchidos.
- Informar a data e salvar atualizou o resumo para saída de R$ 250,00 e saldo
  de R$ -250,00; a tabela passou a mostrar a data efetiva do pagamento.
- O formulário foi conferido em 390×844, sem campos ultrapassando a largura.
  A tabela mantém rolagem horizontal nesse tamanho.
- A inspeção levou à formatação brasileira dos valores, confirmação de salvamento
  e separação entre rótulos e erros, mantendo a identificação dos campos estável.
- A confirmação de salvamento e os valores atualizados foram verificados após
  recarregar o código. A aba e o servidor temporários foram encerrados.

Captura com dados fictícios: `scratch/central-ui/central-mobile.png`.

## Testes após os ajustes

`python -m pytest tests/test_central_revisao_lancamento.py tests/test_central_gestao.py -o addopts='' --no-cov -q --tb=short`

Resultado: **42 testes passaram**, com aviso de diretório de estáticos de teste
ausente. A suíte inclui NF-e → revisão → Q100, preservação de valor/vínculos,
isolamento por propriedade e erros sem gravação parcial. `git diff --check` não
apontou erros de espaços.

## Limites da evidência

Não houve teste de upload bancário nem dos três formulários cadastrais nesta
sessão de navegador. Alguns assets globais retornaram 404 no ambiente isolado
(`legacy.D1-d0q-E.js` e `widgetbar-windows.js`); esta verificação não comprova a
integridade do carregamento de toda a aplicação, homologação fiscal ou transmissão.

O objetivo de unificação permanece em andamento. Este registro documenta somente
a evidência da Central, sem substituir o plano geral nem declarar outras fases concluídas.

## Paginação de movimentos, 08/10/2026

A lista deixa de ocultar definitivamente os registros após o centésimo. Exibe
100 por página com intervalo e total, links anterior/próxima e ordenação estável
por data e identificador. Propriedade, ano e escopo acompanham a navegação; a
revisão e o salvamento preservam a página de origem. O diagnóstico e o arquivo
fiscal continuam abrangendo todo o período, sem receber o recorte da página.

**58 testes passaram** nas suítes `test_central_paginacao.py`,
`test_central_revisao_lancamento.py`, `test_central_gestao.py` e
`test_lcdpr_consolidado.py`. O cenário de 101 movimentos comprova acesso a todos
sem duplicação e resumo integral nas duas páginas. Também foram verificados
retorno após edição, página inválida, página além do fim e lista vazia.
Os novos controles de paginação ainda não foram conferidos no navegador.

## Importação bancária, 08/10/2026

OFX e CSV agora rejeitam valores ausentes, não finitos, maiores que o campo
bancário suporta ou com fração de centavo. A resposta informa a linha ou a
transação a corrigir antes de importar. CSV sem valor deixa de criar um zero
artificial. A gravação do lote é atômica: uma falha posterior reverte as
movimentações anteriores do mesmo envio.

Os testes reproduziram as falhas antes da correção. Depois, passaram **39 testes
e 9 subtestes** de importação e Central, incluindo reversão após falha na segunda
gravação, rejeição integral de arquivo com valor inválido, reenvio e centavos
brasileiros. Houve 25 avisos de diretório estático ausente no ambiente de testes.
Ruff e revisão do diff passaram nos arquivos alterados.

`npm test`, `npm run lint` e `npm run typecheck` foram tentados, mas não
executaram as verificações: os executáveis `vitest`, `eslint` e `tsc` estão
ausentes neste ambiente. A suíte completa não foi executada.

Esta entrega não comprova a conclusão da conciliação bancária nem da unificação
completa. As limitações de identidade sem FITID estão descritas abaixo.

### Reenvio após conciliação

Movimentos conciliados com o mesmo identificador bancário são preservados quando
o conteúdo coincide. Divergências de data, valor, crédito/débito, descrição ou
documento rejeitam o envio com orientação para revisar a conciliação; a transação
reverte também as alterações anteriores do lote. A resposta separa conciliados
preservados de movimentos pendentes atualizados.

Os testes reproduziram a sobrescrita antes da correção. A verificação posterior
passou com **41 testes e 13 subtestes** de importação e Central, com 27 avisos
de diretório estático ausente. Ruff passou nos três arquivos Python alterados;
`git diff --check` passou. Os três comandos npm foram novamente tentados e
continuam sem executar por ausência dos respectivos executáveis. Não houve
teste de concorrência em PostgreSQL nem execução da suíte completa.

### Datas obrigatórias no extrato

Uma data ausente ou impossível agora rejeita o arquivo inteiro, identificando
a transação OFX ou a linha CSV que precisa de correção. A persistência também
rejeita transações sem data recebidas diretamente pelo serviço. O campo
`sem_data` permanece na resposta por compatibilidade, com zero em importações
bem-sucedidas. Arquivos vazios continuam sem ser considerados importados.

Sete casos reproduziram a perda silenciosa antes da correção. Depois passaram
**42 testes e 20 subtestes**, com 28 avisos de diretório estático ausente, nas
suítes de importação e Central. Ruff passou nos arquivos modificados.

### Identidade sem código bancário

A identidade passa a considerar valor com duas casas, descrição integral e
número da ocorrência no arquivo. Duas linhas iguais são preservadas como duas
movimentações; reenviar o mesmo conteúdo com `100` ou `100,00` reutiliza os
registros. Descrições com o mesmo prefixo de 60 caracteres deixam de se fundir.

Registros antigos com conteúdo integral e hash reconhecíveis recebem a nova
identidade preservando chave primária e conciliação. Coincidências com registros
manuais, múltiplos candidatos ou formatos antigos não reconhecidos rejeitam o
lote para revisão, sem criar duplicatas silenciosamente. Não recupera conteúdo
que já tenha sido sobrescrito por importações anteriores.

Sem identificador externo, arquivos parciais com transações indistinguíveis
não permitem provar se uma ocorrência é nova. A resposta inclui contagem e
aviso para conferir extratos sobrepostos; o procedimento preferível nesses
casos é importar extrato com identificadores bancários.

Os três casos principais falharam antes da correção. Depois passaram **46 testes
e 20 subtestes**, com 32 avisos de diretório estático ausente, nas suítes de
importação e Central. Ruff e `git diff --check` passaram. Os comandos npm foram
tentados e continuam sem executar por ausência de `vitest`, `eslint` e `tsc`.
Não foram executados testes de concorrência em PostgreSQL ou a suíte completa.

## Verificação JavaScript recuperada, 08/10/2026

`npm ci --ignore-scripts --no-audit --no-fund` instalou as dependências do lock
existente, sem modificar `package.json` ou `package-lock.json`. Os avisos de
instalação incluem `tsconfck` sem manutenção, `eslint` sem suporte nessa versão,
`glob` antigo com aviso de vulnerabilidades e `whatwg-encoding` descontinuado.
Nenhuma versão foi migrada nesta etapa.

O upload da Central bloqueia novo envio enquanto aguarda a resposta. Falha de
rede ou resposta que não seja JSON agora orienta conferir os registros antes de
reenviar, sem expor mensagens internas do navegador. Erros de validação do
servidor continuam visíveis como texto. Os cinco testes em
`tests/unit/central_upload.test.js` verificam conta, CSRF, resultado, erro de
validação, envio repetido e respostas incertas; três falharam antes da correção
e todos passaram depois.

Verificação geral executada:

- TypeScript passou; ESLint dos dois arquivos JavaScript desta alteração passou.
- `npm test`: 170 testes passaram, quatro falharam e dez foram ignorados;
  três arquivos falharam, incluindo duas falhas de preparação de suíte.
- `clima_render.test.js`: falta o dump exigido por `tests/gerar_clima_render.py`.
- `widgets_registro.test.js`: o teste não encontra `WIDGET_CATALOG` em `index.html`.
- `presets_renderizador.test.js`: quatro testes não encontram
  `renderWidgetbarPresets` (delegação/DOM, handlers inline, ordem persistida e
  diagnóstico do DOM).
- `npm run test:cjs`, executado separadamente após a interrupção do comando
  principal: 12 de 13 suítes passaram. `tests_consentimento_ia.cjs` teve 11
  falhas e cinco checks aprovados, envolvendo a pergunta do download, tamanho,
  armazenamento local, alternativa do servidor, pouca memória e persistência
  da recusa. Saída registrada em `scratch/frontend-cjs.log`.
- Lint geral: três erros em `app/static/js/pagina-index.js`: `hasOwnProperty`
  direto nas linhas 3010 e 10007 e chave duplicada `#0f9d6e` na linha 8230.
- `git diff --check` passou para a alteração. Não houve teste de navegador
  nesta etapa.

As pendências gerais não foram corrigidas nesta alteração de upload. Os logs
locais estão em `scratch/frontend-tests.log`, `scratch/frontend-lint.log` e
`scratch/frontend-typecheck.log`. Esses resultados substituem a limitação
anterior de executáveis JavaScript ausentes; não comprovam conclusão da suíte.

### Revisão da falha de consentimento de IA

O teste CJS estava desatualizado em relação à verificação de adaptador WebGPU:
simulava `navigator.gpu` com objeto vazio e esperava download do modelo menor
mesmo sem GPU. O produto atual encaminha esses casos ao servidor antes de
perguntar sobre downloads inviáveis. Não foi alterado esse comportamento.

O teste foi substituído por cenários que importam o módulo completo e usam o
carregador de runtime injetável já existente. Agora observa chamadas ao runtime
e `reload` diretamente, eliminando a dependência de mensagens de console e da
falha de imports HTTPS no Node. Verifica recusa, consentimento antes do runtime,
persistência em novo módulo, isolamento por usuário, ausência de GPU, aviso de
memória, consentimento específico do modelo menor após liberar o principal e
inicializações concorrentes.

Passaram **25 verificações de consentimento e as 13 suítes CJS**; TypeScript
passou. Isso resolve a falha CJS registrada acima, sem resolver os erros de
Vitest e lint geral. O runtime simulado não comprova execução real em Android
ou compatibilidade de drivers. Não houve download de modelos nesta verificação.

## Conectores de arquivos externos: prévia recuperável

A inspeção de `app/services/conectores.py` mostrou que `importa()` não persistia
dados: apenas contava dicionários normalizados como importados e os descartava.
O resultado passa a devolver `registros`, com `preparado=True` e contadores de
gravação zerados. O resumo informa que nenhum registro foi gravado. Linhas com
pendências impedem `ok=True`; os registros válidos permanecem disponíveis para
revisão. O catálogo descreve essa capacidade real.

Passaram os 12 testes de `tests/test_conectores_puro.py`, incluindo retenção do
valor normalizado e identificação da linha incompleta sem sucesso integral.
Esta etapa não entrega persistência de safras ou lançamentos pelo conector.
Ainda é necessário ligar a prévia a um fluxo autorizado de confirmação e
persistência, registrar origem, validar relações e impedir duplicação por
reenvio. O comando existente de maquinário é um fluxo separado.

O objetivo desta conversa continua sendo a unificação das ferramentas do agro.
O documento `UNIFICACAO_AGRO_2026.md` contém uma orientação diferente, alterada
em paralelo, e não foi usado para substituir ou reduzir esse objetivo.

### Persistência de CSV financeiro na Central

A Central oferece importação de lançamentos com colunas obrigatórias
`id;data;valor;descricao` e opcionais `tipo;documento`. Aceita UTF-8 (com ou sem
BOM), vírgula ou ponto e vírgula, até 5 MB. O tipo explícito aceita `RECEITA`
ou `DESPESA`; sem tipo, usa o sinal do valor. O nome de origem informado deve
permanecer igual nos reenvios. Não é um formato oficial de fornecedor.

Somente o proprietário pode gravar. O serviço usa transação por lote e bloqueio
da propriedade; mantém identidade única por propriedade, origem e ID externo.
Reenvio equivalente reutiliza o lançamento, preservando revisões posteriores;
conteúdo diferente para a mesma identidade rejeita o lote inteiro. Cabeçalhos
ambíguos, linhas inválidas, precisão incompatível e IDs repetidos também rejeitam
o envio. Colunas desconhecidas não são descartadas.

`LinhaFinanceiraImportada` registra usuário, arquivo, origem, ID e hash do
conteúdo, vinculados ao lançamento. A Central mostra `Declarado`, origem e ID.
Entram com categoria `OUTRO`, pagamento não confirmado e classificação LCDPR
em branco, para revisão do produtor. A trilha protege a exclusão do lançamento.

A migration `0083_linha_financeira_importada` foi aplicada com sucesso em SQLite
isolado, incluindo suas dependências. **Não foi aplicada ao banco de uso**;
precisa integrar a execução de migrations antes de disponibilizar esta versão.
Não houve teste de concorrência em PostgreSQL ou verificação visual do formulário.

Passaram **49 testes e quatro subtestes** de importação, Central e revisão fiscal,
com 34 avisos de diretório estático ausente. Ruff dos arquivos novos e TypeScript
passaram. `npm test` mantém 170 aprovados, quatro falhas, dez ignorados e duas
falhas de preparação de suíte descritas acima. Lint geral mantém três erros em
`pagina-index.js` (agora linhas 2724, 8020 e 9797 após alterações paralelas).
O diff desta implementação passou; o diff geral encontrou uma linha vazia final
em `console.md`, fora desta alteração.

A persistência de safras, maquinários pelo conector genérico e adaptadores de
formatos específicos de fornecedores continuam pendentes. A unificação completa
não está concluída.

### Conferência no navegador da importação financeira

Em 08/10/2026, o formulário foi exercitado no navegador com servidor local e
SQLite temporário, usando somente usuário e arquivo fictícios. O CSV criou
receita de R$ 1.200,00 e despesa de R$ 85,50. A tabela mostrou origem, ID externo,
estado declarado, pagamento em aberto e revisão fiscal necessária. Reenviar o
mesmo arquivo exibiu zero criados e dois já importados, mantendo três registros
na tabela (os dois importados e o lançamento inicial do ambiente).

A captura está em `scratch/central-ui/csv-importado.jpg`. O servidor e a aba
temporários foram encerrados. Os dados de uso não foram modificados. O ambiente
de desenvolvimento ainda registrou arquivos JavaScript globais ausentes; esta
conferência valida o formulário, sem certificar todos os recursos da página.

`makemigrations app --dry-run --check`, com migrações habilitadas e banco em
memória, retornou `No changes detected in app 'app'`. A migration continua sem
aplicação ao banco de uso. O teste visual de erro de arquivo e a concorrência em
PostgreSQL permanecem pendentes; os erros do serviço têm cobertura automatizada.

## Confirmação de estoque após OCR

A revisão encontrou gravação parcial em `confirmar_estoque`: itens inválidos
eram ignorados, quantidades viravam float e formatos incorretos podiam causar
erro interno. O endpoint agora valida o lote com serializers de classe antes
de gravar, usando Decimal compatível com o modelo. Rejeita valores não finitos,
zero, negativos, excesso de precisão, nomes e unidades longos, listas vazias
e formatos incorretos. Uma transação reverte o lote em falhas de persistência.
O isolamento por proprietário e a seleção exigida entre várias propriedades
foram preservados. Quantidades devolvidas no JSON usam representação decimal
textual, sem perda dos centavos.

Passaram **47 testes e 14 subtestes** de confirmação, ingestão e ponte de execução,
com cinco avisos de diretório estático ausente. Ruff dos arquivos alterados e
TypeScript passaram; o diff da alteração passou. `npm test` continua com as
quatro falhas de presets e duas falhas de preparação (clima e catálogo de
widgets), e o lint geral mantém os três erros de `pagina-index.js` registrados
acima. Não houve teste real de reconhecimento OCR ou conferência no navegador
nesta etapa. A proteção contra confirmações repetidas foi implementada na
etapa seguinte; o fluxo completo ainda não está certificado.

### Reenvio da confirmação de estoque

Em 09/10/2026, cada documento passou a gerar um rascunho independente, sem
sobrescrever o documento anterior. A confirmação bloqueia o rascunho durante
a transação e registra os itens revisados, a propriedade e os IDs criados.
Reenviar os mesmos dados devolve o resultado anterior com `reutilizado: true`;
alterar os itens ou a propriedade após confirmar retorna HTTP 409, sem gravar
outro lote. O rascunho de outro usuário retorna HTTP 404.

**Compatibilidade:** `POST /api/ia/confirmar-estoque/` agora exige `artefato_id`,
obtido de `POST /api/ia/imagem-estoque/`. Consumidores que enviavam somente
`itens` precisam encaminhar esse identificador. A leitura aceita texto manual
para gerar o rascunho. `itens` pode ser omitido na confirmação para usar os
itens salvos; `propriedade_id` continua obrigatório quando há várias propriedades.
Quantidades na resposta são strings decimais. Não há nova migration nesta etapa.

Passaram **53 testes e 14 subtestes** de confirmação, ingestão e ponte, com
11 avisos de diretório estático ausente. Ruff dos arquivos alterados e a
conferência de whitespace do diff passaram. `npm test` executou 181 testes
aprovados, quatro falhas e dez ignorados, além das duas falhas de preparação
de suíte já registradas: dump de clima ausente e catálogo de widgets não
encontrado. As quatro falhas continuam na extração de `renderWidgetbarPresets`
(delegação/DOM, handlers inline, ordem persistida e diagnóstico). O comando
interrompe antes dos testes CJS; eles não foram reexecutados nesta etapa.
TypeScript passou. O lint geral continua com três erros em `pagina-index.js`:
duas chamadas diretas a `hasOwnProperty` (linhas 2724 e 9797) e a chave duplicada
`#0f9d6e` (linha 8020), fora dos arquivos desta etapa.

Não foram executados reconhecimento OCR real, conferência visual, teste de
concorrência em PostgreSQL ou suíte Python completa. A proteção reconhece
reenvios do mesmo rascunho; enviar a mesma imagem novamente cria outro rascunho
e não constitui deduplicação do documento de origem.
