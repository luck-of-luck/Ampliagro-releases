# PLANO DE 4 BLOCOS — prompts de arranque (2026-10-01)

> Copia o bloco do teu bloco a partir de `---` e cola na sessão correspondente.
> Os prompts de 29/09 em `IA-B-tenancy-e-seguranca.md` e
> `IA-C-contratos-e-teste.md` estão **67–69 commits atrás** e aFILA mudou de
> 17 para 73 itens. Usa estes.

---

## ⚠️ ANTES DE TUDO — a worktree está parada

```
tenant-seguranca   HEAD=bd7690b   69 commits ATRÁS de main   0 à frente
contratos-teste    HEAD=9b5785e   67 commits ATRÁS de main   0 à frente
```

Tens de actualizar **antes de começar**, ou vais medir um código que já não
existe:

```powershell
cd <a tua worktree>
git fetch origin
git rebase main        # ou: git merge main
pytest app/ -q         # tem de dar exit=0
pytest tests/ -q       # tem de dar exit=0
```

Se o rebase tiver conflito, **não o resolvas sozinho**: escreve em
`docs/converça-agentes.txt → [PEDIDO]` e trabalha noutro.

E atenção: se a tua worktree tiver trabalho por commitar, **commita-o antes**.
Houve um `git checkout` partilhado que apagou trabalho inteiro nesta
repositório uma vez.

---

# BLOCO IA-B — #23, `Funcionario.user` é `OneToOneField`

> Worktree: `...\Ampliagro.worktrees\tenant-seguranca`, branch `ia-b/tenant-seguranca`

---

## A tua missão, num item

**Um produtor não consegue registar dois funcionários na mesma conta.**

Verificado hoje, não herdado da FILA:

```
Funcionario._meta.get_field('user')
  -> user field: OneToOneField | unique= True
  -> dois funcionários na MESMA conta: BLOQUEADO
```

O `IntegrityError: UNIQUE constraint failed: app_funcionario.user_id` que
travou o "Leandro" é disto. O produtor lê "o sistema está partido" — e tem
razão: está.

Isto é a única coisa que pede **migration**, e migration é território teu.
É por isso que o bloco é teu e não de outra.

## Porquê PRIMEIRO na fila

É o único item da FILA que é **dados e dinheiro ao mesmo tempo**. Todo o
restante é qualidade ou técnica. E é o único onde o modelo, e não o código,
está errado — os outros blocos mexem em código, tu mexes no schema.

## Como, por ordem

**1. Medir (L3, não L2).** Script que tenta criar dois funcionários na mesma
conta e guarda o traceback. O erro já está reportado, mas confirma-o na tua
base — e confirma que o traceback é este e não outro.

**2. A decisão é tua, e tem um custo que ninguém te vai explicar.**

`OneToOneField` → `ForeignKey` é o caminho óbvio. Mas olha para quem tem
conta: um funcionário é a **pessoa** que usa a aplicação; a conta é a
**autenticação** dessa pessoa. Uma conta por pessoa costuma ser o certo. O
modelo ser `unique` não é necessariamente um erro de catálogo — pode ser uma
decisão que alguém tomou e tu vais desfazer.

Antes de mudar, responde a uma pergunta que está no código e não no ticket:
**há código que dependa de `funcionario.user` ser único?** Procura
`user=` em `Funcionario.objects.create`, `funcionario.user`, e o
`app/ia/` (que cria funcionário por conversa). Se o `registro.py` ou
`intents3.py` assumem um-por-conta, mudar o campo parte esse caminho e o
problema volta por outro lado.

Se a resposta for "ninguém depende", muda. Se a resposta for "depende",
**escreve isso no LOG e decide em vez de decidir por omissão** — este é
exatamente o tipo de item onde se finge estar a arranjar e se quebra outra
coisa.

**3. A migração, e o `_meta` limpo depois.**

```powershell
python manage.py makemigrations app
python manage.py migrate
python manage.py makemigrations --check --dry-run   # tem de dizer "No changes"
```

**4. Provar que o produtor consegue.** Teste que cria dois funcionários na
mesma conta e passa. Sem ele, tens uma migração e não uma correcção.

**5. As duas suites verdes nos dois lados.** `pytest app/` **e** `pytest tests/`,
ambas exit=0. Não vale a pena entregar uma que parta a outra.

**6. A outra metade — e é a mesma história.** `app/tests_regressao_ambiente_real.py`
aponta `testuser` (id 21) e `test_nav` (id 22) como **órfãos**: contas no
banco de *desenvolvimento* sem `PerfilUsuario`. Depende de
`app/management/commands/limpar_contas_teste.py`. Decide com o #23 feito,
porque as duas coisas se tocam: se mudares a semântica de `Funcionario.user`,
o que a limpeza considera "conta de teste" pode mudar.

## Reservas

Posta isto **antes** de abrir o primeiro ficheiro:

```
app/models/equipe.py
app/migrations/
app/management/commands/limpar_contas_teste.py
tests/test_*.py  (o teste novo que escreveres)
```

## O que NÃO fazes

- **Não mexes em `models/` além de `Funcionario.user`.** Há mais uma sessão
  a trabalhar nesta área e há reservas em curso.
- **Não mexes em `app/ia/`** (é da IA-A nem da IA-H neste momento) nem em
  `app/static/js/`, `src/` (é da IA-C).
- **Não mexes no `verificar_regressoes.py`** — há a #73 aberta e não é teu.
- **Não fazes `git add -A`.** O stage é partilhado. Stageia por caminho
  explícito e confere `git diff --cached --name-only` antes de commitar.
  Já aconteceu haver 8 ficheiros alheios num stage.

## Como fechas

No `docs/converça-agentes.txt`, com `[ENTRADA]`, data e hora, e a parte
**"NÃO FIZ"** — que é a mais útil e é obrigatória. Se não disseres o que não
fizeste, a próxima IA repete o teu trabalho.

---

# BLOCO IA-C — #17, a cobertura que nunca foi auditada

> Worktree: `...\Ampliagro.worktrees\contratos-teste`, branch `ia-c/contratos-teste`

---

## A tua missão

**A lista da #17 está errada, e isso é o primeiro trabalho.**

A linha da FILA diz que a cobertura não auditada é:

```
gateway/   cron/   acp_adapter/   ui-tui/   apps/desktop/
```

**Nenhum desses directórios existe neste repositório.** Quem ler a linha vai
procurar ficheiros que não lá estão — e perde o turno inteiro antes de
descobrir que a lista estava desatualizada. Esse é o teu primeiro acto:
corrigir a linha com o que existe **de facto**.

O que existe, medido hoje:

```
app/static/js/**                  75 ficheiros .js
src/**                            46 ficheiros .ts/.tsx
app/management/commands/**        26 ficheiros .py
```

E o que já passa:

```
npm test    exit=0    141 vitest + as 7 suites .cjs
pytest app/ exit=0
pytest tests/ exit=0
```

## A pergunta certa não é "faltam testes"

141 testes passam. Isso não é a pergunta. A pergunta é:

> **O que o produtor vê no browser e não está medido?**

Há uma pista no teu próprio histórico: `#45` e `#53` foram testes que
revelaram que um valor aparecia no ecrã sem dizer de onde veio. E o bloco da
IA-A teve o mesmo tema pelos dois lados — nos KPIs, um número de fabrico
("acumulado anual") que não correspondia ao que o gráfico mostrava.

O padrão é: **um número no cartão, sem fonte**. Não é o número estar errado —
é não se poder conferir.

## Como, por ordem

**1. Corrigir a #17 na FILA.** O que existe, e o que está por medir. Medido,
não estimado.

**2. Inventariar o que o produtor toca sem cobertura.** Não todos os 121
ficheiros — os que aparecem no ecrã dele. Dashboard, painel de widgets
(`widgetbar-windows.js`), os cartões de KPI, `palco-amplia.js`.

**3. Escolher 3–5 alvos** e escrever o que cada um promete. Não mais. Um
bloco que escreve 40 testes não acaba, e um teste que não acaba não protege
nada.

**4. Instrumentar, não supor.** Para cada alvo: qual é o número que o
produtor lê, e de onde vem. Se não souberes responder, **é esse o achado** —
e vai para a FILA com o ficheiro e a linha.

É a mesma regra do teu `README`/`AGENTS.md`: não se escreve um teste que
lê o código-fonte a perguntar "aqui ainda está?". Está-se a medir o
comportamento.

**5. Cuidado com o padrão que já mordeu duas vezes** (FILA #69): um teste de
JS novo que extrai um bocado do ficheiro por **índices de texto** parte a
execução do resto da suite. Se write de testes que leem `ia-local.js`, usa
import/export ou injeta dependências — não recorte por posição no texto.

## Reservas

```
src/**
app/static/js/**    (o que não esteja em uso por outra sessão)
tests/unit/**
```

Confirma no `AGORA` antes: já houve `ia-local.js` reservado duas vezes.

## O que NÃO fazes

- **Não mexes em `app/ia/`** nem em `app/services/`. Se encontrares um bug
  lá, põe na FILA com "achado por IA-C, território da IA-X" e segue.
- **Não mexes em `models/`, `migrations/`, `middleware.py`** — é da IA-B.
- **Não ligas o lint** (é a #66, e tem blast radius — medir antes, decisão
  à parte).
- **Não reescreves a #17 inteira sem medir primeiro.**

## Como fechas

`[ENTRADA]` no `converça-agentes.txt`, com o **"NÃO FIZ"**. E actualiza a
linha da #17 na FILA com o que ficou por medir — que é o que o próximo
precisa de saber.

---

# BLOCO IA-A — #20 e #22, o cadastro por conversa

> Onde estás depende de como foste arrancada. O plano assume `main`.

---

## A tua missão, num par

Dois P1 abertos que são **a mesma conversa a partir de dois lados**:

**#20 — "como se cadastrar" não casa em nenhum matcher.**
Os regexes exigem verbo *seguido de* nome de recurso:
`/cadastrar.*?funcion/`. Em "como se cadastrar" o verbo está no **fim** — não
há nada depois. Cai no fallback genérico.

**#22 — a pergunta repete-se.**
```
"Qual o nome?" → Carlos → "✓ Nome: Carlos  Cargo:  Salário:  Admissão:
                                        Qual o nome?"
```
O ciclo não avança. O produtor responde e recebe a mesma pergunta.

Andam juntos. Corrigir o #20 sem o #22 deixa o produtor a chegar ao
formulário e a ficar preso nele — o que, para quem tentava cadastrar-se, é
pior do que o fallback genérico.

## Antes de começar: o código pode ter mudado

O commit `31a9be4` (bloco 006) mexeu na **confiança com sinal trocado**, e
o `76e15f3` mexeu em `intents3.py` (`h_melhor_pulverizar`, o `or 99` que
deitava fora as melhores horas para pulverizar).

**Mede o que existe hoje.** Se o matcher já não é o que a #20 descreve, o
item mudou de forma — e isso é tão importante quanto corrigi-lo. Uma FILA
que descreve um código que já não existe consome o turno de quem a vai
executar.

## Como, por ordem

**1. Medir as frases de facto, não as que o matcher imaginou.**

O defeito não é "o regex é curto" — é que se testaram regex com frases
escritas para o regex. Escreve a lista de frases que um produtor diz de
verdade a alguém a_phone: ("quero cadastrar um vaqueiro", "como se cadastra
um funcionário", "adiciona um mecânico", "preciso de registar o pessoal").

**2. O verbo no fim é um caso, não o caso.** Talvez o mesmo sintoma venha de
*"como se cadastra"*, *"como cadastro"*, *"adicionar"*, *"registrar"*. O que
o bloco precisa é da **classe** de frases, medida — não de um regex novo.

**3. #22: medir a sequência, não a frase.** O ciclo completo, do "Qual o
nome?" até ao fim. E encontra onde é que o campo pedido não avança. O sintoma
provavelmente é: o handler responde, o estado não muda, e o próximo passo
volta a pedir o primeiro campo.

**4. Um teste por caso, com a frase no nome.** `test_vaqueiro_no_fim_da_frase`
diz o que partiu. Um teste chamado `test_regex_3` não diz nada daqui a seis
meses.

## Reservas

```
app/ia/intents*.py
app/ia/sandbox.py
app/ia/tests_*.py  (os teus)
```

**Confirma `app/static/js/ia-local/**` antes** — já esteve reservado duas
vezes por sessões diferentes. Se houver reserva viva, não toques e escreves
um pedido.

## O que NÃO fazes

- **Não mexes em `app/services/`** (é da IA-A no outro sentido — serviços de
  dados), **`models/`**, **`middleware.py`**.
- **Não mexes em `app/static/js/**` sem confirmar a reserva.**
- **Não corriges o `stdout` nem o `TestCase`** — isso foi feito no `1b7e17f`.
  Se voltares a ver `I/O operation on closed file`, é outra coisa.

## Como fechas

`[ENTRADA]` com o **"NÃO FIZ"**. E se discoveres que a #20 ou a #22 já não
são o que a FILA diz, **corrige a linha** — é mais útil do que fechar o item.

---

## Regra que vale para os três

Se dois blocos precisarem do mesmo ficheiro: **o mais severo ganha** e a
decisão vai para `DECISÕES TOMADAS`, com o porquê. Não se resolve a vote
dentro de um ficheiro partilhado — escreve-se e avança-se.

E se discordares do plano: escreve no `converça-agentes.txt`. O ficheiro é o
único ponto de verdade. O que estiver escrito ganha ao que qualquer uma se
lembre de ter dito numa conversa.