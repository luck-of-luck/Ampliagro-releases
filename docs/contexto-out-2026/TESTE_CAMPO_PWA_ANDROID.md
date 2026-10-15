# Teste de Campo — PWA Ampliagro no Android

Roteiro manual. Um celular Android real, Chrome, e um cabo de rede. Não precisa de
saber programar — precisa de saber copiar um texto de erro.

**O que este roteiro tenta provar:** que o app instala no Android, que a correção do
IndexedDB (versão 2, 7 object stores) chegou no aparelho, e que **o shell do app
arranca sem rede nenhuma** quando é aberto pelo ícone.

> ### ⚠️ O Caderno de Campo NÃO EXISTE. Não o procures.
>
> Esta é a coisa mais importante deste roteiro, porque é a que faz o tester
> perder a manhã. **Não existe nenhuma tela de Caderno de Campo**, não existe
> botão para ela em lado nenhum, e **não há rota `/caderno/`** no servidor. Se
> procurares "Caderno de Campo" no menu, na paleta de comandos ou na URL, **vai
> parecer que o produto está partido — e não está.** Não é um bug desta fase e
> **não deve ser reportado como tal.**
>
> A camada de dados offline (IndexedDB) está construída e tem o schema certo —
> é o que a Parte B prova. O que não existe é a **tela** que escrevesse nela, e o
> **backend** que receberia o que fosse escrito. Escrever uma anotação de campo
> hoje não é possível: não há onde digitar, e o que fosse gravado chegaria ao
> servidor como **404**, porque **`/api/caderno/notas/`, `/api/caderno/fotos/` e
> `/api/caderno/voice/` não estão implementados no backend.** Ninguém deve perder
> tempo a testar escrita de nota, sincronização de nota, foto ou gravação de voz.
>
> O que se pode — e deve — testar hoje está nas Partes A, B e C. A Parte C
> passou a ser o teste do **app abrir sem rede**, que é o que o código realmente
> garante.

**Verificações feitas por leitura de código antes de escrever este roteiro** (tudo
isto foi conferido, não é suposição):

| Fato | Onde |
|---|---|
| Cache do SW na versão `v19` | `app/static/js/pwa/sw.js:28` |
| IndexedDB `ampliagro-offline` na versão 2, 7 stores | `app/static/js/pwa/indexeddb.js:18-19` |
| Mesma versão 2, mesmos 7 stores, no Service Worker | `app/static/js/pwa/sw.js:32-37` e `336-382` |
| Rotas que servem o SW e o manifest | `app/urls.py:330` e `app/urls.py:332` |
| Registro do SW com `scope: '/'` | `app/templates/base.html:314` |
| Manifest em modo `standalone` | `app/static/manifest.json:6` |
| Botão "Instalar no Celular", `hidden` por desenho | `app/templates/pitch.html:107-118` |
| Login por cookie de sessão (não JWT) | `config/settings/base.py:226` |
| `CSRF_COOKIE_HTTPONLY = False` (o JS precisa de ler o token) | `config/settings/base.py:62` e `283` |

> **REGRA DE OURO DESTE ROTEIRO**
> Este aparelho tem dados de produtor dentro. **NÃO apague dados do produtor para
> testar.** Não use "Limpar dados do site", não desinstale o app, não use
> "Limpar armazenamento" nas DevTools. Se algo der errado, o certain é anotar o
> erro — não varrer o aparelho. Se Precisar mesmo de um aparelho limpo, use um
> aparelho de teste, não o do produtor.

---

## 1. O que precisas

- **Android 5 ou superior.** O `beforeinstallprompt` só existe no Chromium 80+,
  portanto na prática: qualquer Android dos últimos anos, com o Chrome atualizado.
- **Chrome NO Android.** Obrigatório. O Firefox e o Safari **não** emitem
  `beforeinstallprompt`, e por isso o botão de instalar simplesmente não aparece
  neles. **Isso não é defeito** — o botão está `hidden` no HTML e o JavaScript
  só o mostra quando o evento chega. Num browser sem suporte, o evento nunca chega
  e o botão continua escondido. No teste, se não estiver a usar Chrome, pare aqui.
- **Espaço livre no aparelho** (o app pesa poucos MB, mas photos e gravações
  ocupam).
- **Meio de desligar a rede:** modo avião, ou desligar Wi-Fi **e** os dados
  móveis ao mesmo tempo. Um só desligado não chega — o aparelho muda de rede
  sozinho e o teste fica sem valor.
- **PC com cabo USB** para a Parte B. Ver a seção de bloqueio abaixo.

### Antes de começar — a condição que faz tudo o resto ser inútil

Um Service Worker **só funciona em `https://` ou em `localhost`**. Não funciona
numa URL por IP simples, tipo `http://192.168.0.10:8000`.

Se o endereço que for testar for `http://` com um IP no meio, o Service Worker
**não regista**, a Parte B não tem o que mostrar, e a Parte C não tem como
funcionar. Marque isso como **BLOQUEIO** na Parte D e pare: é preciso HTTPS.

Uma forma rápida e sem instalar nada: trocar o backend para `localhost`, mas isso
só funciona com o cabo ligado no PC e o teste a correr no PC — que não é o
objectivo. Para testar num celular de verdade, é preciso um domínio com HTTPS.

---

## 2. Parte A — Instalar (5 min, **com** rede)

> Objectivo: provar que o app instala e abre em modo standalone (sem barra de
> endereço do navegador).

1. **Abra o Chrome no celular** e vá até a página de apresentação:
   `<endereço do servidor>/pitch/`
   *(preencher com o endereço real. A rota `/pitch/` está em `app/urls.py:320`.)*

   **Esperado:** a página carrega com o conteúdo da apresentação do Ampliagro.

2. **Desça até ao cartão "Instala e Abre Sem Sinal"** (o que tem o ícone de
   telefone). É lá que mora o botão de instalar.

   **Esperado:** vê o botão **"Instalar no Celular"**, com um ícone de seta para
   baixo, largo, no fundo do cartão.

3. **Se o botão NÃO aparecer, pare e diagnostique.** Não é defeito do app: o botão
   nasce `hidden` e só aparece quando o Chrome emite `beforeinstallprompt`. As
   três razões mais prováveis, e como distinguir uma da outra:

   | Razão | Como distinguir |
   |---|---|
   | **Já está instalado** | O Chrome não emite o evento para um app já instalado. Confirmo: Veja se já existe um ícone "Ampliagro OS" na sua tela inicial. Se existe, o app **já está instalado** — a Parte A já passou, siga para a Parte B. |
   | **Já está em modo standalone** | O `beforeinstallprompt` não é emitido dentro do app já instalado. Confirmo: se está a ver esta página **dentro** do app (sem barra de endereço), está standalone. Feche o app, volte ao Chrome pelo ícone dele e reabra `/pitch/` no Chrome. O botão deve aparecer aí. |
   | **Browser sem suporte** | Firefox ou Safari no Android. Confirmo: o botão "Instalar no Celular" nunca aparece neles, por desenho. A alternativa no iPhone/iPad é a instrução textual ("Compartilhar → Adicionar à Tela de Início"), que aparece no lugar. Neste caso, **não há como testar** com este browser. |

   **Não escreva "não apareceu porque deu preguiça" no relatório.** Diga qual das
   três era, e como descobriu.

4. **Toque em "Instalar no Celular"** e aceite a instalação. O Chrome mostra um
   diálogo do sistema (o nome do app, o ícone, "Instalar").

   **Esperado:** o diálogo aparece e o ícone **Ampliagro OS** passa a existir na
   tela inicial.

5. **Abra o app pelo ícone** da tela inicial (não pelo Chrome, não pela URL).

   **Esperado:** o app abre em tela inteira.

6. **Olhe para o topo da tela. CONTE A BARRA DE ENDEREÇO DO NAVEGADOR.**

   **Este é o sinal de standalone e é o que conta. Ou:**
   - **NÃO há** barra de endereço, nem "⋮" de menu do Chrome, nem barra de
     navegação embaixo. O conteúdo vai até ao topo e ao fundo do tela.
     → **PASSOU.** O `display: standalone` do manifest está a funcionar.

   **Ou:**
   - Há barra de endereço, ou um botão "⋮" em cima, ou um botão de fechar (X) —
     sinal de que está a ver uma aba do Chrome e não o app.
     → **FALHOU.** Anote na Parte D e confirme que abriu pelo ícone, e não por
     uma ligação no Chrome. Se abriu pelo ícone e mesmo assim tem barra, isso é
     um defeito real.

**Resultado da Parte A:** [ ] PASSOU  [ ] FALHOU — anote em qual dos passos.

---

## 3. Parte B — Provar que a correção do IndexedDB pegou

> **Esta é a parte mais importante do roteiro.** É ela que valida o bug corrigido.
> Sem esta parte, as restantes provam que o app abre — não que os dados param de
> partir.

### O bug que estamos a testar

O `indexeddb.js` e o `sw.js` abrem o mesmo banco (`ampliagro-offline`) com listas
de object stores diferentes. Como o `onupgradeneeded` **só corre uma vez**, se o
Service Worker acordasse primeiro, os stores `field_notes`, `offline_tasks`,
`experiments` e `voice_recordings` **nunca eram criados** — e o Caderno de Campo
offline partia com `NotFoundError` logo na primeira nota.

A correção: subir a versão do banco para **2** e deixar os **7 stores iguais** nos
dois arquivos. Este teste existe para confirmar que, **no aparelho**, os 7
existem.

### Passo a passo

1. **Ligue o PC e o celular na MESMA rede Wi-Fi.** Para o address bar conseguir
   falar com o aparelho.

2. **No celular, ative a "Depuracao USB".**
   - Definições → Sobre o telefone → toque **7 vezes** em "Número da build".
     Aparece "Você é agora um programador".
   - Volte: Definições → **Opções do programador** → ative **Depuracao USB**.

3. **Ligue o celular ao PC por cabo USB.** É por cabo. A depuração por Wi-Fi
   (par sem fio) é mais frágil e não é preciso.
   - Aceite o diálogo no celular quando aparecer "Permitir depuração USB?" e
     marque "Sempre permitir deste computador".

4. **No PC, abra o Chrome e vá a `chrome://inspect`.**
   - Página em branco com um ícone de telemóvel. Se aparecer
     "Nenhum dispositivo", reveja o passo 2 e o cabo.
   - Em **"dispositivos remotos"**, aparecerá o seu celular.
     Se aparecer o nome do aparelho, o cabo funciona.
   - Se o aparelho aparecer mas a lista de páginas estiver vazia: o Service
     Worker **não está registado**, e isso já é achado. Marque na Parte D e veja
     a seção de bloqueio do ponto 1 (tem de ser HTTPS).

5. **Abra o app no celular e deixe-o visível.** Abra pelo ícone, na tela inicial.
   A página tem de estar a correr para aparecer na lista.

6. **Em `chrome://inspect`, na seção "páginas", localize a do Ampliagro e clique
   em "inspect".**
   - As DevTools abrem **no PC**, controlando a página que está **no celular**.
     É este o truque: não precisa de um editor de texto no celular, e o console
     de erros é o do PC.
   - Se a lista não mostrar nada: volte ao passo 5 e ensure que o app está
     **aberto e visível** (não em segundo plano).

7. **Navegue até `Application` (aplicação) → `IndexedDB` → `ampliagro-offline`.**
   - Se `ampliagro-offline` não aparecer na lista de bases de dados: o banco não
     foi criado. Anote como **FALHOU** na Parte D e copie a lista de bases que
     apareceu. É o mesmo bug, um grau atrás.

8. **EXPANDA o banco e ANOTE os object stores.** Cada store é uma linha com o
   nome. **Escreva os 7 nomes num papel** (ou num tela), exatamente como aparecem.

9. **CONFERE CONTRA A LISTA ESPERADA.** Tem de estar aqui dentro, **todos**:

   ```
   mutations
   field_notes
   photos
   observations
   offline_tasks
   experiments
   voice_recordings
   ```

   | # | Store | Existe? |
   |---|---|---|
   | 1 | `mutations` | [ ] sim  [ ] NÃO |
   | 2 | `field_notes` | [ ] sim  [ ] NÃO |
   | 3 | `photos` | [ ] sim  [ ] NÃO |
   | 4 | `observations` | [ ] sim  [ ] NÃO |
   | 5 | `offline_tasks` | [ ] sim  [ ] NÃO |
   | 6 | `experiments` | [ ] sim  [ ] NÃO |
   | 7 | `voice_recordings` | [ ] sim  [ ] NÃO |

   **Também confirme o índice, não só o nome.** Clique em `field_notes` e veja se
   existem os índices `talhao_id`, `cultura_id`, `created_at` e `synced`.
   **Esperado:** os quatro. Um store com o nome certo mas sem os índices é meio
   caminho andado — os índices são o que permite ler as notas por talhão.
   Sem `talhao_id`, o Caderno de Campo não consegue mostrar as notas do talhão.

10. **Se FALTOU algum store: este é o teste que falhou.** Não é um pequeno
    detalhe. Faça assim:
    - Anote **qual** store faltou (ou quais).
    - Copie **a lista exacta** do que apareceu no painel `Object Stores`, para
      baixo, tal e qual. Não resuma, não escreva "os mesmos de sempre".
    - Abra o separador **Console** e carregue no botão de limpar, depois vá a
      `Application → IndexedDB → ampliagro-offline` outra vez: copie o erro que
      aparecer, **texto integral**.
    - **NÃO apague nada para tentar de novo.** Apagar dados do produtor não é
      teste, é estrago. O achado é o store que falta — guarde-o e pare.

11. **Seu teste também tem de cobrir a referência de versão.** Clique com o botão
    direito em `ampliagro-offline` na lista e escolha **"Atualizar"** (Refresh).
    Na janela de atualização, o campo **"Versão antiga"** tem de mostrar `1` (ou
    qualquer coisa menor que `2`).

    **Esperado:** se o aparelho já tinha o banco da versão 1, a migração é a que
    acaba de acontecer, e o upgrade termina. Na janela de atualização, o campo
    **"Nova versão"** tem de mostrar **2**.

    Se **"Versão antiga" e "Nova versão" forem ambos 2**, o banco já estava na 2
    — e então este teste **não provou a migração**, provou só a criação limpa.
    Anote isso com todas as letras: "migração não exercitada, banco já veio na 2".
    Não conte como passou.

12. **Feche as DevTools** (ou deixe-as abertas; a página no celular continua a
    funcionar). Se as fechar, a app no celular **não** pára.

**Resultado da Parte B:** [ ] PASSOU  [ ] FALHOU

Stores anotados (lista exacta do que apareceu no aparelho):

```
<colar aqui>
```

---

## 4. Parte C — O app arranca sem rede

> **Este é o teste de valor: o que o produtor vai sentir com as próprias mãos.**
> As Partes A e B provam que a máquina está bem montada. Esta prova que ela
> **abre no talhão, sem rede nenhuma** — que é o que o código garante hoje.

### Porque é que ESTE é o teste certo agora

Um produto que é instalado no celular e abre no talhão sem sinal já vale muito
para quem trabalha de pé numa lavoura. **Isto é exactamente o que este roteiro
vai provar.**

O que este roteiro **não** vai provar, e não é falta de teste: **gravar dados
offline e sincronizar depois.** Essa parte não está construída — não há tela e
não há endpoint. Ver o aviso no topo deste ficheiro.

### O que esperar, e o que NÃO esperar

| Páginas | Com o modo avião ligado |
|---|---|
| **Dashboard (`/`)** | Abre. É a página que o Service Worker guarda na instalação. Os números podem aparecer vazios ou do cache antigo — **é o esperado**, os dados vêm de API. |
| **Guias (`/guias/vegetal/`)** | Abre do cache. Também é guardada na instalação. |
| **Outras páginas** (Kanban, ecrãs de talhão, …) | **Podem mostrar o Dashboard.** É o que o cache devolve quando a página pedida não foi guardada. **Não é um bug desta fase** — não é registado. |

### Passo a passo

1. **Com o app aberto e COM rede, navega normalmente** — abre o Dashboard, o
   Guia Vegetal e o Quadro de Tarefas. Deixa cada um ser carregado ao menos uma
   vez com rede. Sem isto o conteúdo pode não estar no cache.

2. **LIGUE O MODO AVIÃO.** Ou desligue o Wi-Fi **e** os dados móveis.

   **Esperado:** o topo do ecrã mostra o ícone de avião. O app continua aberto e
   navegável — **é isso que está a ser testado.**

3. **FECHE O APP POR COMPLETO.**
   - Vá à lista de apps recentes (o gesto de "apps recentes" — no Android, deslize
     para cima e mantenha, ou o botão quadrado).
   - **Deslize o Ampliagro para fora da lista** para o matar. Se aparecer a opção
     "Limpar dados" ou "Remover", **NÃO toque** — isso apaga o banco e o teste
     perde todo o sentido. Só o fechar.
   - **Se houver dúvida, force a paragem total** pelo ecrã de Apps →
     Ampliagro OS → **Forçar paragem**.

   > **Porque é que este passo é obrigatório, e não um detalhe.**
   > Deixar o app em segundo plano **mantém tudo em memória**. A página nunca morre,
   > o JavaScript nunca volta a reler do armazenamento, e o app aparece "sem
   > problema" mesmo que o cache estivesse vazio de todo. O teste passaria sem
   > provar nada. **Só fechar de verdade obriga o app a reler tudo do cache** — e
   > é aí que o problema apareceria.

4. **Com o app morto, AINDA NO MODO AVIÃO, reabra o app pela PRIMEIRA VEZ.**
   - Toque no ícone no ecrã inicial.
   - Repare: **é a primeira vez que este arranque acontece sem rede.**

   **Esperado — o que TEM de acontecer:**
   - O app **abre**. Aparece o shell do Ampliagro.
   - **NÃO** aparece uma página de erro.
   - **NÃO** aparece o texto "Offline - Ampliagro OS".
   - **NÃO** fica a carregar eternamente nem cai para o Chrome com a barra de
     endereço.

5. **Vá ao Dashboard e confirme que a página está desenhada** — menus, cartões,
   estrutura. Os **números** podem estar vazios: vêm de API, e não há rede. Isso
   **não é falha**.

6. **Vá ao Guia Vegetal** (é um dos que o Service Worker guarda na instalação).

   **Esperado:** abre com o conteúdo do guia.

   Se não abrir e o ecrã ficar em branco, vá à Parte D e copie o erro do Console.

7. **LIGUE A REDE DE VOLTA** (desligue o modo avião).

   **Esperado:** o app volta a mostrar os números. Não é preciso esperar nem
   recarregar — o `sync.js` reage ao evento `online`.

**Resultado da Parte C:** [ ] PASSOU  [ ] FALHOU — anote em qual dos passos.

**Se o app abriu sem rede mas apareceu "Offline - Ampliagro OS" ou uma página de
erro:** isso é sim um achado — o shell tinha de estar no cache. Vá à Parte D.

---

> ### O QUE ESTA PARTE JÁ NÃO TESTA (e não deve ser reportado como bug)
>
> Não teste, e **não reporte como bug**, nada disto nesta fase:
>
> - **Abrir um "Caderno de Campo".** A tela não existe. Não há rota, não há menu.
> - **Gravar uma anotação de campo**, offline ou com rede.
> - **Fotografias ou gravações de voz.**
> - **Esperar que uma nota offline "sincronize quando a rede volta".** Não há nota
>   para sincronizar, e os endpoints `/api/caderno/*` ainda não existem no
>   backend — qualquer tentativa devolveria **404**.
> - **Conteúdo de API em modo avião.** Os números vêm de API. Verem-se vazios é o
>   comportamento certo, não um defeito.

---

## 5. Parte D — Fechar o que der errado

Preencha **uma linha por achado**. Sem este quadro, o teste não prodz nada: um
roteiro que passa não diz o que não foi verificado.

**A coluna mais importante é a do erro exacto.** Um erro escrito de memória não
serve — não serve nem para diagnosticar, nem para confirmar depois. Copie o texto
crudo do Console e cole-o.

| # | Parte | O que era esperado | O que aconteceu | Erro exacto (texto copiado, não escrito de memória) | Bloqueio? |
|---|---|---|---|---|---|
| 1 | | | | | |
| 2 | | | | | |
| 3 | | | | | |
| 4 | | | | | |
| 5 | | | | | |
| 6 | | | | | |
| 7 | | | | | |
| 8 | | | | | |

**Lista dos object stores que apareceram, para não dar por limpo o que falhou:**
*(se um store faltar, copie aqui a lista completa do que apareceu)*

```
<colar aqui>
```

**Como copiar o erro exacto:**
1. DevTools → separador **Console**.
2. Botão de limpar (o ⊘ no canto, ou "Clear console").
3. Reproduza o erro (feche o app, reabra, faça a operação que falhou).
4. Clique com o botão direito sobre a linha vermelha do erro.
5. **Copy** e cole na tabela, **sem corrigir nada**: mantém os maiúsculos
   minúsculos, os parênteses e o nome do store.

**Achados de bloqueio** (não são bugs do app — são o ambiente. Mas têm de ficar
escritos, ou o teste passa a parecer falhado quando não é):

| Sintoma | Provável causa | O que fazer |
|---|---|---|
| O `chrome://inspect` não vê o aparelho | "Depuracao USB" desligada, ou cabo só a carregar | Ligue a depuração USB e um cabo de dados (não um cabo de carga) |
| `ampliagro-offline` não aparece no IndexedDB | O SW não registou | Verifique se o endereço é `https://`. Um `http://` com IP não regista SW |
| A página não aparece na lista do `chrome://inspect` | O app não está aberto/visível, ou o SW não registou | Abra o app e deixe-o à frente; se continuar, é bloqueio de HTTPS |
| O botão "Instalar" nunca aparece | Browser sem `beforeinstallprompt` | Só Chrome/Edge no Android. Noutro browser, não há como testar |
| "Instalado" mas com barra de endereço | Abriu por link em vez do ícone | Feche e abra pelo ícone; se persistir, é defeito |

---

## 6. O QUE ESTE ROTEIRO NÃO PROVA

Dito de forma direta, para ninguém ler o resultado e supor mais do que foi
verificado:

- **Não prova ausência de bugs.** Prova os três pontos listados no topo e
  nada mais. Passar este roteiro não torna o PWA à prova de defeitos —
  significa apenas que estes três pontos funcionaram neste aparelho, neste dia.

- **Não cobre login por cookie num dispositivo real.** O teste assume que já está
  dentro da conta. A autenticação usa `SessionAuthentication` (cookie), não JWT,
  e `CSRF_COOKIE_HTTPONLY = False` para o SPA conseguir ler o token. **Fechar e
  reabrir o app com a sessão expirada, ou instalar num aparelho novo e fazer
  login de raiz, não foi testado.** Nesses casos o comportamento pode ser
  diferente e este roteiro não diz nada sobre ele.

- **Não cobre iOS.** No iPhone e no iPad, o botão de instalar é só uma
  **instrução textual** (a pessoa usa Compartilhar → Adicionar à Tela de Início).
  O iOS **não emite** `beforeinstallprompt`, por isso o botão de verdade nunca
  aparece lá. Nada disto foi testado em iOS — nem a instalação, nem o
  IndexedDB, nem o offline.

- **Não cobre TLS/HTTPS.** Um Service Worker só funciona em **HTTPS** ou em
  **localhost**. Se o servidor for acedido por IP sem HTTPS, **o SW não regista**:
  não há cache, não há IndexedDB criado pela página, não há offline. Se for esse
  o caso, anote como **BLOQUEIO** na Parte D e diga que é preciso HTTPS. Não é
  um defeito da aplicação.

- **Não cobre a migração a partir de um banco da versão 1 com conteúdo dentro.** Só
  cobre a migração limpa (criação do zero). **Na prática, hoje, não há como ter
  conteúdo:** nenhuma versão do app alguma vez conseguiu escrever nos stores — a
  camada de escrita nunca foi ligada a nenhuma tela. Por isso um aparelho com a
  versão 1 e notas dentro é, hoje, um cenário impossível de montar. Fica
  documentado porque um dia, quando a escrita existir, ele volta a ter de ser
  testado — e nessa altura já não será trivial.

- **Não cobre muitas horas offline**, nem desvio de relógio, nem bateria a acabar,
  nem troca de talhão, nem conteúdos a acumular. **Não há fila de escrita para
  acumular**, porque não há escrita — quando existir, a fila por dia inteiro no
  talhão é uma das coisas que vai precisar de teste.

- **Não cobre multi-utilizador** no mesmo aparelho, nem a coexistência de duas
  contas a usar o mesmo IndexedDB.

- **Não mede desempenho.** Um app que abre em 4 segundos e funciona passa igual.

---

## Resumo para quem preencheu o roteiro

| Parte | O que provava | Resultado |
|---|---|---|
| A | O app instala e abre em modo standalone | [ ] PASSOU [ ] FALHOU |
| B | Os 7 object stores existem, na versão 2 | [ ] PASSOU [ ] FALHOU |
| C | O app arranca sem rede (shell abre pelo ícone, sem erro) | [ ] PASSOU [ ] FALHOU |
| D | Tudo o que deu errado, com o erro exacto | [ ] preenchido [ ] não houve nada |

**Bloqueio registrado?** [ ] não  [ ] sim — qual:

```
<escrever>
```
