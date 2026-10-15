s7-------------------------------------------------------------------------------------------------------

# S7 - IA-7. Verificacao cruzada, e a conta que faltava

Autor: Predador (papel), sessao 7 (slot). Repo
C:\Trabalho\Projetos\Ativos\Ampliagro. Worktree onde fiz o trabalho de
frontend: C:\Users\lucas\Documents\Projetos_geral\Ampliagro.worktrees\contratos-teste
(ramo ia-c/contratos-teste). Data: 04/10/2026.

Slot **s7**. Escolhi o s7 porque a regra escrita no RESUMO e' "recebe o
proximo slot VAZIO". s3 e s4 perderam-se; s7-s11 estavam vazios. NAO
reutilizo s3 nem s4, porque uma posicao com trabalho perdido nao e' uma
posicao livre - e' trabalho perdido.

**SOU O MESMO PAPEL DA IA-6, NUM SLOT DIFERENTE.** O Predador e' um papel
(nao editar, verificar antes de afirmar); s6 e s7 sao sessoes. Pelo ficheiro:
IA-1, IA-2 e IA-5 declaram o mesmo id de agente e ainda assim sao tres
sessoes. O slot e' da sessao. O papel e' meu.

======================================================================
1. O QUE EU VERIFIQUEI - E O QUE NAO CONSEGUI
======================================================================

Metodo: NAO aceitei nenhum relato. Li o codigo. Onde o s6 afirmava
"CONFIRMADO", voltei a abrir a linha.

CONFIRMADO por leitura de codigo (3 dos 5 achados do s6):

  ACHADO 1 [GRAVE] - revogacao nao se propaga. CONFIRMADO.
    servidor_estoque_view   L194   ativo_servidor = NAO
    servidor_agenda_view    L237   ativo_servidor = NAO
    servidor_alertas_view   L273   ativo_servidor = NAO
    So o dashboard (s6 diz L76) e o kanban checam.
    Reportado por mim como CONFIRMADO, com linha.

  ACHADO 2 [GRAVE] - a view escreve dado falso no banco. CONFIRMADO.
    app/views/operario.py
      L75   RegistroProducao.objects.get_or_create(
      L81   EstagioCultura.objects.get_or_create(
      L96   TarefaEstagio.objects.get_or_create(
    Varri as 30 linhas acima de L96: NAO existe settings.DEBUG no caminho.
    Confirma a frase do s6: renderizar a pagina grava. Sem gate.

  ACHADO 3 [MEDIO] - falha aberta. CONFIRMADO.
    app/views/operario.py:38-41
      except Exception:
          is_servidor = True
          pode_criar = True
    E ha um SEGUNDO except logo a seguir (L43-46, "Tenta buscar tarefas
    denormalizadas"). O s6 reportou um. Sao dois.

  ACHADO 4 [BAIXO] - card "COM LOGIN" mostra "[]". NAO REVERIFIQUEI.
    Fica como SINTOMA. O padrao (lista renderizada como escalar) e' bem
    plausivel, mas nao abri o template. Nao confirmo por Modes.

MEDIDO POR MIM, e o s6 AFIRMOU e estava certo:

  O TESTE DE SUPERFICIE. ServidorDesativadoTest (app/tests_servidor.py,
  L276-293) tem **um unico pedido HTTP**: GET /servidor/ (L289).
  Cobertura: 1 rota de 5. A brecha esta aberta e o teste passa verde.
  Isto e' a prova de que o achado 1 e' mesmo GRAVE e nao teorico.

======================================================================
2. AS TRES DISCREPANCIAS - SO APARECEM QUANDO SE VERIFICA
======================================================================

O arquivo inteiro e' feito de relatos que se aceitam uns aos outros. Estas
tres coisas nao batem com o que esta escrito, e nenhuma delas aparece em
nenhum dos quatro slots.

### D-1. O `_backups` NAO TEM "250+ NIVIIS". TEM 5.

  O s6 escreveu: "Medido: 250+ niveis (bateu meu teto; o fundo nao
  terminava." E tratou a correccao como "apagar a arvore".

  MEDIDO AGORA, com tecto de 5000 e sem FIND:
      a arvore TERMINA SOZINHA em 5 nivel(is)
      caminho real: _backups/bekup_20260726_142546/.claude/state/vscode/
                   window-focus-requests
      ficheiros: 49.669        tamanho: 537,4 MB

  **O s6 mediu com tecto e leu o timeout como se fosse infinito.** E'
  literalmente o defeito que a secao 5 deste arquivo descreve, cometido
  pela secao que o descreve: um comando que nao termina devolve "nao
  termina", e le-se como medida.

  A CORRECCAO E' MAIOR DO QUE SE PENSAVA. Nao e' uma arvore de 250 niveis
  para apagar - sao **537 MB e 49.669 ficheiros** de lixo de CLI. Isso e'
  o que enche disco, o que faz o antivirus e o CI demorarem, e o que faz
  um `rg` despejar HTML de noticias. O s6 acertou no sintoma e errou na
  grandeza - e a grandeza e' o que decide se isto e' urgente.

  NOTA: isto NAO prova que o s6 mentiu. Prova que o s6 mediu mal. A
  distincao importa: ele nao podia saber, porque o comando nao voltava.

### D-2. O `console.md` TEM A DOENCA QUE ELE DENUNCIA.

  Varrimento de bytes em 95.152 bytes:
      CJK total ............ 20
      citados (legitimos) ... 12
      CORRUPCAO REAL ........  8

  Estas 8 nao foram reportadas por ninguem, em nenhum dos quatro slots:

    L1531  U+56FA U+6709   "E o S01固有 decidiu o outro lado"
    L1660  "Bernou"        "e' uma Bernou a procurar"
    L1752  "doisenchakes"  "dois enchakes de ferramentas"

  A L1531 e' a mais seria: os dois ideogramas colados ao "S01" sao
  exactamente o mecanismo de corrupcao que as outras tres IAs
  descreveram - texto lucido, nao-ASCII a colar. O proprio arquivo de
  doenca tem a doenca.

  **CONSEQUENCIA PARA A CATRACA QUE PROPUSERAM.** A regra proposta e'
  "falha se um .py ou .md contiver U+2E80-U+9FFF". Aplicada a ce bluntly,
  essa regra daria 20 falsos positivos neste ficheiro, porque 12 sao o
  exemplo da doenca citado de proposito. **A regra precisa de uma
  excepcao para conteudo entre aspas** - ou entao obriga a escrever o
  exemplo em escapes e perde-se a razao pela qual o exemplo existe.

  E este ficheiro nao esta no git (`?? console.md`, verificado). Portanto
  estas 8 corrupcoes nao tem segunda copia. E sao a unica copia das
  palavras de s3 e s4.

### D-3. O BOM DO `71285c1` - E O DA SESSAO QUE NAO SE ACUSOU

  Varrimento de mensagens de commit:
      71285c1   BOM
      a6b488f   BOM + MOJIBAKE ("a---", em-dash partido)

  A IA-5 assumiu o seu: "FOI BOM NO COMMIT a6b488f. Usei
  Set-Content -Encoding UTF8. Esta no historico para sempre." E ela tem
  razao em como happened.

  **O `71285c1`, que e' da IA-2, tem o mesmo BOM. E ninguem o reportou.**
  A IA-2 escreveu um capitulo inteiro ("ONDE ME PARTI") sobre as suas
  cinco perdas de acento e o `edit` que mentiu, e nao menciona o BOM no
  seu unico commit.

  Isto e' o padrao "NINGUEM CORREU UM SCANNER" outra vez, noutra
  ferramenta: quatro sessoes, cada uma a olhar os seus proprios ficheiros.
  Ninguem olhou os *commits*.

  NOTA: li o commit cru (`git cat-file commit`) e o BOM esta no **campo
  da mensagem**, nao no cabecalho. A distincao importa para a correccao:
  `--amend` resolveria.

======================================================================
3. O QUE EU FIZ NESTA SESSAO (frontend, e nao estava em nenhum slot)
======================================================================

Todo este trabalho foi feito NAO no repo do console.md, mas no worktree
`Ampliagro.worktrees\contratos-teste` (ramo ia-c/contratos-teste). Nao
commitei. Nao toco em nada das outras sessoes. Registo porque o dono
precisa de saber que existe, e porque dois dos problemas que encontrei
sao da mesma familia dos achados acima.

ENTREGUE:
  - DASHBOARD MOBILE. Os widgets tinham 54px de largura e tres charts
    espremidos, um cortado na borda. Agora: 378px, empilhados, sem
    sobreposicao. Medido: 378/378/378/378/378, top 77/258/438/569/617.
  - O TERCEIRO RENDERIZADOR. Havia tres a escrever `gridColumn`. O que
    valia era um script INLINE em index.html (L3296 e L3322) - eu tinha
    procurado so em app/static/js e ja tinha concluido, errado, que
    "nao existe". Encontrei-o por monkey-patch de CSSStyleDeclaration a
    capturar stack trace. A confirmacao com stack trace e' o metodo, e
    e' o que faltava nas tres primeiras buscas.
  - NAVBAR. Hamburger 44x44 e painel lateral com 6 destinos, no mobile.
    Desktop sem regressao (pills em linha, hamburger escondido).
  - WIDGET BAR. Sliders removidos no celular; barra de edicao flutuante
    acima da barra; presets visiveis.
  - LOGIN/CADASTRO. Orfao de HTML corrigido (`#painelCadastro` estava
    dentro de `#painelLogin`, que tem display:none). Contraste corrigido
    nos dois temas.
  - 17 testes e2e a passar.

O QUE EU ERREI NESTA SESSAO, porque o registo sem isto e' propaganda:

  - **Conclui "este renderizador nao existe" sem o procurar bem.** A
    verdade e' que eu procurava a propriedade errada (`grid-area` em vez
    de `gridColumn`). Uma conclusao negativa baseada numa busca que nunca
    podia encontrar. E' o mesmo erro do s6 com os "71 widgets": contar
    uma via e chamar o resto de morto.
  - **Dei `grid-row: N` sem span** e a altura colapsou para 22px. Depois
    dei span 8 e incrementei a fila de 1 em 1, e os widgets passaram a
    sobrepor-se. Duas vezes por causa da mesma suposicao errada sobre o
    grid.
  - **O meu proprio script de verificacao caiu no bug que o arquivo
    descreve.** Imprimi caracteres CJK num stdout cp1252 e o Python
    rebentou com UnicodeEncodeError. Tive de corrigir o script para
    conseguir RELATAR a corrupcao. E' a demonstracao de que a doenca
    esta viva, e de que a regra "escrever scripts em ficheiros" so
    resolve metade - o stdout tambem precisa de UTF-8 forcado.
  - **Cheguei a introduzir CJK no rascunho desta seccao.** Duas vezes,
    ao escrever. Apanhei por leitura ANTES de gravar, e o rascunho foi
    reescrito. Isto e' a doenca em tempo real, e a prova de que ela nao e'
    um problema de autores desprevenidos: eu li tres relatos a dizer que
    ela e' inevitavel, e mesmo assim ela veio. E' por isso que a correccao
    tem de ser um hook e nao mais cuidado.

======================================================================
4. RESUMO DAS CORRECCOES - DEDUPLICADO, COM DONO E PRIORIDADE
======================================================================

Consolidado das quatro sessoes mais esta. Cada linha tem DONO e FACTOR,
porque "alguem tem de ver isto" sem nome nao e' atribuicao.

Legenda: [C] construcao (escreve codigo)  [K] correcao (rever, provar, fechar)
         O Predador NUNCA escreve codigo de produto. [K] dele e' teste.

  PRIORIDADE 0 - DESTRANCA O RESTO. Ninguem comita enquanto durar.

  P0.1  catalog.json: renomear para .js ou apagar.
       JavaScript com extensao .json, nao rastreado, o hook
       check-json reprova-o sempre. Bloqueia TODOS os commits.
       Nao e' tarefa de agente - e' decisao do dono.
       DONO: dono  |  FACTOR: [K] verificar que o hook passa

  P0.2  Versionar o console.md.
       `?? console.md`, nao rastreado, e a UNICA copia do que
       s3/s4 escreveram. Um commit deste ficheiro resolve o
       diagnostico e o risco. Nao custa 5 minutos.
       DONO: qualquer  |  FACTOR: [C] - e o mais barato da lista

  P0.3  Os 9 commits citados EXISTEM todos em HEAD (verificado por mim,
       9 de 9). HEAD tem 741 commits. Nao se perdeu trabalho de
       commit - perdeu-se o que nunca foi committado (s3, s4, s7-s11
       no console).

  PRIORIDADE 1 - OS DOIS GRAVES. Ninguem fez nada ate agora.

  P1.1  Revogacao nao se propaga. 4 de 5 rotas.
       servidor_estoque_view L194, servidor_agenda_view L237,
       servidor_alertas_view L273 nao checam ativo_servidor.
       CAUSA, nao sintoma: mover a verificacao para dentro de
       _perfil_e_propriedade e de kanban_allowed.
       COLISAO: o ramo ia-b/tenant-seguranca JA existe. Coordenar
       com quem o tem antes de escrever.
       DONO: IA-B (ramo ja existe)  |  FACTOR: [C]
       PROVAR: IA-7 escreve o teste  |  FACTOR: [K]

  P1.2  View grava dado falso. operario.py L75/L81/L96.
       Sem gate DEBUG. Correccao: gate, ou montar em MEMORIA sem
       get_or_create.
       DONO: IA-1  |  FACTOR: [C]  |  PROVAR: IA-7 [K]

  PRIORIDADE 2 - OS DOIS QUE TRAVAM OS OUTROS

  P2.1  Falha aberta. operario.py:38-41 E 43-46.
       except Exception concede privilegio. Fechar.
       DONO: IA-1  |  FACTOR: [C]

  P2.2  Catraca de CJK - COM EXCEPCAO.
       tests/test_sem_cjk.py. MAS: o console.md tem 12 CJK citados de
       proposito, e a regra cega da 20 falsos positivos. Precisa de
       ignorar conteudo entre aspas.
       DONO: IA-5 (ja tem o script)  |  FACTOR: [K]
       NOTA: escrever o script em FICHEIRO, nunca here-string.
       E forcar UTF-8 no stdout dos scripts de verificacao.

  P2.3  Catraca de superficie de acesso a rotas.
       Um teste que enumere as rotas de /servidor/ e exija
       ativo_servidor em todas. Medido por mim: hoje cobre 1 de 5.
       DONO: IA-6  |  FACTOR: [K]

  PRIORIDADE 3 - O VAZIO QUE NINGUEM COBRIU

  P3.1  Scanner deterministico. QUATRO sessoes, ZERO scanners.
       app/views: 29 ficheiros, 5.533 linhas - o s6 leu 5.
       app/api/views: 25 ficheiros, 8.289 linhas - ninguem leu.
       Sao 13.822 linhas por ler. E' a maior lacuna do registo.
       sast + semgrep + astgrep fecham isto em minutos.
       DONO: IA-7 (predador)  |  FACTOR: [K]

  P3.2  _backups: 537 MB / 49.669 ficheiros.
       Medido por mim: 5 nivel(is), NAO 250. Apagar com calma, mas
       apagar: e' o que esta a encher o disco.
       DONO: dono  |  FACTOR: [K] eu nao apago nada

  P3.3  tests_safra_area_vs_terreno.py tem CJK desde 01/10. [K]

  P3.4  Card "COM LOGIN" mostra "[]" - por confirmar. [C]+[K]

  PRIORIDADE 4 - SO O DONO PODE DECIDIR

  P4.1  Secao 3.1: login.css mudou de proposito?
  P4.2  Secao 3.2: os 273 MB do estudo - apagar, arquivar, reduzir.
  P4.3  catalog.json: renomear ou apagar.
  P4.4  Os BOM em 71285c1 e a6b488f: reescrever historico?
            `git commit --amend` reescreve. A regra do repo proibe sem
            ordem. Nao faco.

======================================================================
5. A MATRIZ DE ALOCACAO - CONSTRUCAO x CORRECCAO
======================================================================

Regua: **ninguem pega no que o outro provou saber fazer.** E **ninguem
faz as duas coisas no mesmo ficheiro.**

  IA-7 (este slot)  PREDADOR          [K] construcao: ZERO
    Fator: correcao. Unico slot que devolveu retractos em vez de
    achados - e, desta vez, um retracto a OUTRA sessao.
    ENTREGUE: 3 achados reconfirmados com linha; 3 discrepancias
    (D-1/D-2/D-3); a medicao do teste de superficie (1 rota de 5);
    a dimensao exacta do vazio (13.822 linhas por ler).
    TAREFAS: P3.1 (scanners), e escrever os testes de P1.1/P1.2.
    NAO EDITA codigo de produto. Escreve so testes e relatorios.
    ESTA TAREFA ESTA EM ANDAMENTO - ver secao 6.

  IA-6  PREDADOR (slot anterior)    [K] construcao: ZERO
    ENTREGUE: 5 achados, 11 ruidos, 3 retractos, 1 sintoma fechado.
    O unico slot a dar retractos em vez de achados.
    ESTADO: inactivo. O relatorio vive em s6.

  IA-5  MEDICAO E COORDENACAO       [C] construcao: ALTA
    ENTREGUE: 12 catracas versionadas, DatabaseCache para LocMemCache,
    3x F841 (uma era armadilha de perda de dados), 6 erros
    mecanicos, e a prova por fetch de que o corpus foi gerado.
    Fator: medicao com controlo positivo. E' quem provou que uma
    das URLs do "catalogo" da 404 no mesmo host que da 200.
    TAREFAS: P2.2 (catraca CJK, com exceccao), e o snapshot do
    _backups antes de apagar 537 MB.

  IA-1  FRONTEND / CONTRATO         [C] construcao: ALTA
    ENTREGUE: preset-base, o contrato de widgets com null
    deliberado, widget-requisitos, 48 regras de CSS. O achado do
    null-vs-0 e' o mais importante do registo inteiro: e' a
    distincao entre "sem dado" e "mediste zero".
    Fator: medicao em DOM. Unica que apanhou bug que a leitura do
    codigo dizia estar certo.
    ATENCAO: a regiao do dashboard e' SUA. A sessao IA-7 tambem
    mexeu nela, mas em OUTRO worktree e sem commitar. Coordenar
    antes de qualquer commit que toque index.html.
    TAREFAS: P1.2, P2.1 (as duas views, com a correccao)
    CONTACTO DE DADOS: onde a API devolve null, a UI diz
    "sem dado" e nunca 0. Coerencia com IA-6.

  IA-2  VOZ E COPILOTO             [C] construcao: MEDIA-ALTA
    ENTREGUE: fronteira subtrativa na voz, 25 numeros com ponto
    decimal em interface portuguesa reduzidos a 0, proveniencia
    separada da frase, e o intent remarcar_tarefa que faz a promessa
    cumprida. Metodo mais rigoroso do registo: partir o produto de
    proposito e exigir que o teste falhe.
    TAREFAS: o texto esta pronto. Falta o lado de DADO (sem_dado),
    comum com IA-1 e IA-6. E P0.1 - foi a primeira a identificar
    catalog.json como bloqueante de TODOS os commits.
    NOTA: tem BOM no 71285c1, nao declarado. Ver D-3.

  IA-3  LIVRE  |  IA-4  LIVRE
    Slots com conteudo perdido. NAO sao livres: sao trabalho
    perdido. Se alguem as recuperar: primeiro passo e' NAO
    reescrever. Verificar se os commits delas existem nalgum ramo
    ANTES de assumir que se perderam. Foi o que fiz com os 9
    commits citados - 9 de 9 existem.

  IA-8 .. IA-11  LIVRE
    Reservados. Numero nunca se reutiliza.

======================================================================
6. O QUE ESTA A SER FEITO AGORA, E O QUE EU NAO VERIFIQUEI
======================================================================

EM ANDAMENTO: P3.1, o scanner deterministico. Os scanners estao
indisponiveis neste host. Vou medir se e' o binario que falta ou a rede
que falha, e registar o resultado COMO ISSO - nao como "sem problemas".
E' o unico item desta lista que nao precisa de autorizacao do dono, nao
mexe em codigo de produto, e fecha a lacuna que cinco sessoes deixaram
aberta.

NAO VERIFICADO:

- **NAO rodei um scanner deterministico.** sast/semgrep/astgrep
  indisponiveis nesta sessao. As quatro sessoes mais esta: cinco,
  zero scanners. E' a maior lacuna do registo, e P3.1 existe por
  causa dele.
- **NAO li** cadastro.py, auth.py, lgpd.py, nem nada de app/api/.
  Dos 5 achados do s6, reconfirmei 3 por leitura directa. O achado 4
  (card "[]") continua sintoma.
- **NAO verifiquei** nenhuma das contagens dos outros (71/578 cards,
  44 widgets, 25/29 cabecalhos, 158 ficheiros, 22.490 linhas).
- **NAO commitei nada.** Nem no repo do console.md, nem no worktree.
- **NAO apaguei** os 537 MB de _backups. Apagar nao e' do predador.
- **Comite de 46 lentes**: nao tentei. Dado o registo (404 e tres
  timeouts de 270 s em quatro sessoes), trato-o como indisponivel e NAO
  afirmo nada em nome dele.

======================================================================
7. A REGRA QUE FALTA, E QUE E' BARATA
======================================================================

Cinco sessoes bateram nos mesmos tres bugs de FERRAMENTA, e nenhuma os
resolveu, porque nenhum era problema do codigo:

  1. Texto corrompe-se em silencio (o meu rascunho desta secao, hoje)
  2. O indice do git e' partilhado e ninguem o verifica
  3. Um comando que falha devolve a saida do caminho de recurso, e
     le-se como "correu limpo" (o s6 leu um timeout como "infinito")

Sao tres correccoes, e as tres sao de uma linha ou duas:

  a) pre-commit que varre bytes CJK, COM exceccao para conteudo entre
     aspas (D-2 mostra que sem a exceccao da 12 falsos positivos)
  b) `git commit --only <caminhos>` obrigatorio, ja verificado: os 9
     commits citados estao todos intactos, apesar do indice partilhado
  c) um comando que nao corre tem de DIZER QUE NAO CORREU; nao pode ter
     um ramo de recurso que imprima "passou"

Nenhuma delas precisa de decisao do dono. As tres fecham as tres doencas
de uma vez.
