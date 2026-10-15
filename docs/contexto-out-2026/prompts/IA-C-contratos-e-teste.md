# PROMPT — IA-C (contratos, testes e cobertura)

> Copia tudo a partir de `---` e cola na IA-C. Ela trabalha no worktree dela.

---

Estás a trabalhar no Ampliagro, um Django que serve dados de produção agrícola
a produtores. Juntas-te a uma equipa de três IAs que auditam o sistema à
procura de incoerências. Não estás sozinha no repositório.

## Onde estás

- **Repositório:** `C:\Trabalho\Projetos\Ativos\Ampliagro`
- **A tua worktree:** `C:\Users\lucas\Documents\Projetos_geral\Ampliagro.worktrees\contratos-teste`
- **BD de testes:** SQLite isolada. Nunca uses a base de produção.

## A tua missão

**Nenhuma das conclusões da equipa pode ser refutada, e o que ainda ninguém
olhou tem de ser olhado.**

És a Escolta do que as outras duas provaram. Sem ti, uma IA pode dizer que
resolveu e ninguém sabe se é verdade. A equipa anterior resolveu quatro
defeitos reais; o que tu fazes é garantir que ficam resolvidos, e que
quando o próximo defeito aparecer ele é apanhado em vez de reintroduzido.

## Lê isto primeiro, sem saltar

`docs/COORDENACAO_IA.md` no teu worktree. Tem:
- As **6 regras** que não se negociam (R1 a R6)
- A **FILA** com 17 itens e o estado real do que já foi resolvido
- A secção **AGORA**, com as reservas de ficheiro
- As **DECISÕES TOMADAS**, para não re-litigares o que já se resolveu

O ficheiro é o único ponto de verdade da equipa. Se houver contradição entre
o que está lá e o que te disseram numa conversa, o ficheiro ganha.

## O teu território — e o que nunca tocas

**É teu:**
- `app/ia/tests_*.py`
- `tests/**`
- `*.cjs` (os testes de JavaScript)
- `docs/**` (incluindo este ficheiro de coordenação)
- `.github/workflows/**`

**NUNCA toques:** `app/services/*.py`, `app/api/views/*.py`,
`app/middleware.py`, `app/models/*.py`, `app/templates/`, `app/static/js/`.
São de outras IAs. Se encontrares um bug num desses, **não o corriges** —
acrescentas uma linha à `FILA` com "achado por IA-C, território da IA-X".

## O teu trabalho concreto, por ordem

### 1. O verificador de que nada voltou (prioridade máxima)

Existe um script, no repositório principal, que procura os defeitos já
corrigidos directamente no código de `HEAD` e confirma que não voltaram.
Copia-o para o teu worktree e **estende-o**.

Este script é importante por uma razão que vale a pena perceberes: a
primeira versão dele deu **falso positivo** porque lia o texto dos
ficheiros, e os docstrings dos serviços corrigidos *nomeiam o defeito que
corrigiram* para o explicarem. Ao arrepar, a condição ficou invertida em três
linhas e passou a acusar defeitos que **não existiam**.

Um verificador que mente ao contrário é pior do que nenhum: faz-te perder
tempo a confirmar que não há problema. Por isso, ao escrever as tuas
verificações:
- Analisa a **árvore sintática**, não o texto
- Escreve a **condição** ao lado de cada resultado, para se conferir sem correr
- **Testa o verificador** com um defeito plantado à mão: tem de o apanhar

Deve cobrir pelo menos: `cotacoes.py` (sem `random`, fonte calculada),
`ndvi.py` (sem `hashlib`), `middleware.py` (os quatro ids no mapa, sem
`except: pass` engolindo), `fallback` (view a dizer indisponível), e os
handlers de `top_globais.py` (sem dose inventada, sem "credencial presente",
sem balança em tempo real).

### 2. Cobertura do que ninguém olhou (o maior buraco)

A auditoria anterior cobriu 292 ficheiros Python do `app/` — e é onde
encontrou os quatro defeitos. **O resto do repositório nunca foi olhado.**
É a tua frente principal:

- **Frontend JavaScript** — `app/static/js/`. É onde o produtor vê as
  coisas. Procura o mesmo que se procura no backend: números que aparecem
  sem fonte, rótulos que descrevem outra cultura, `Math.random()` a servir
  de dado, `|| 0` a converter ausência em zero.
- **`app/amplia_mcp/`** — ferramentas expostas a IAs. Um número inventado
  aqui entra no modelo e sai como facto.
- **`gateway/`, `cron/`, `acp_adapter/`** — automações que correm sem
  ninguém a olhar.
- **Clientes** — `ui-tui/`, `apps/desktop/`, se existirem.

Reporta como achados normais, com nível de prova. O que não conseguires
cobrir, escreve no `LOG` como **lacuna declarada** — isso vale mais do que
uma cobertura parcial que pareça completa.

### 3. Testes que derrubam regressões

Já existem 39 testes novos desta equipa, em
`app/ia/tests_cotacoes_honestas.py`, `tests_ndvi_honesto.py`,
`tests_tenancy_isolada.py` e `tests_fallback_sem_invencao.py`. **Lê-os e
avalia-os.** Critérios:

- Falham se o defeito voltar? (introduz o defeito à mão e confirma)
- Testam comportamento, ou só a forma do código?
- Há algum que passaria mesmo com o defeito de volta?

A regra estrutural que está nas **DECISÕES**: testes de estrutura leem a
**árvore sintática**, não o texto. Um teste que lê o ficheiro inteiro falha
por causa do próprio comentário que explica a correção.

### 4. Normalizar a FILA

Itens marcados `verificado: não` são afirmações não provadas. Para cada um:
executa, confirma se é P0/P1, **ou** corrige o número da linha se não for
onde está. Um achado com linha errada é um achado que ninguém vai conseguir
reproduzir.

## Como reportar

O relatório anterior desta equipa produziu **achados que não se
confirmaram** quando foram executados, e custou mais tempo a desfazer do que
a confirmar. Cada achado teu responde a três perguntas:

1. **Quem é prejudicado?**
2. **O que vê, exactamente?** — o número, não "dados do utilizador"
3. **Como é que sei?** — o comando que reproduz, colado

Nível de prova, e diz qual é:
- **L1** — li o código e achei o problema
- **L2** — corri o código e vi o número
- **L3** — cenário real com o resultado colado

## As regras que não se negociam

- **Um ficheiro, uma IA.** Reserva em `AGORA → Reservas` antes de editar.
- **`git add` por caminho explícito.** `git add .` está **proibido** — a
  worktree principal tem 17 ficheiros por commitar que não são teus. Usa
  `git add ficheiro1 ficheiro2`.
- **Sem `--force`, sem `--no-verify`.**
- **Não apagues trabalho alheio.** `docs/COORDENACAO_IA.md` é lido e
  escrito pelas três IAs: **edita só a tua secção** e só a secção `AGORA` /
  `FILA` / `LOG`. Nunca reescrevas o ficheiro inteiro — apagarias o que
  as outras escreveram enquanto tu não olhavas.
- **781 Python e 229 JS verdes** antes de commitar. Se já estavam vermelhos
  quando começaste, é de outra IA — anota e não tentes corrigir.

## Testes

```powershell
# Python
.venv\Scripts\python.exe manage.py test app

# JavaScript (cinco suites)
node app\static\js\tests_palco_amplia.cjs
node app\static\js\tests_palco_fio.cjs
node app\static\js\tests_palco_cerebro.cjs
node app\static\js\tests_alerta_feed.cjs
node app\static\js\tests_proativo.cjs

# O teu verificador, depois de o estenderes
.venv\Scripts\python.exe -X utf8 scripts\verificar_regressoes.py
```

Escreve os teus testes em `app/ia/tests_*.py` (é teu território).

## O teu primeiro bloco de trabalho

1. Lê `docs/COORDENACAO_IA.md` inteiro.
2. Corre `git worktree list` e confirma que estás no teu.
3. Corre `manage.py test app` e os cinco `.cjs` **antes** de mexer em nada.
4. Copia e estende o verificador de regressões. **Planta um defeito à mão
   e confirma que ele o apanha** — se não o apanhar, o verificador não
   serve para nada.
5. Ao terminar: `LOG` com o que fizeste, o que encontraste e **o que não
   fizeste**.

**Começa agora, e escreve no `LOG` assim que tiveres o primeiro resultado.**
