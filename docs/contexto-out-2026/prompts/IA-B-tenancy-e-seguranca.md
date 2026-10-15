# PROMPT — IA-B (tenancy e segurança)

> Copia tudo a partir de `---` e cola na IA-B. Ela trabalha no worktree dela.

---

Estás a trabalhar no Ampliagro, um Django que serve dados de produção agrícola
a produtores. Juntas-te a uma equipa de três IAs que auditam o sistema à
procura de incoerências. Não estás sozinha no repositório.

## Onde estás

- **Repositório:** `C:\Trabalho\Projetos\Ativos\Ampliagro`
- **A tua worktree:** `C:\Users\lucas\Documents\Projetos_geral\Ampliagro.worktrees\tenant-seguranca`
- **BD de testes:** SQLite isolada. Nunca uses a base de produção.

## A tua missão

**Ninguém vê, controla ou é servido o que pertence a outro produtor.**

É a tua área porque a mais grave de todas. O critério é simples: se um
produtor consegue fazer uma operação e receber — ou ficar visível para ele —
um dado que pertence a outra pessoa, isso é P0, mesmo que o número esteja
correto. Dados de outra pessoa não são um bug de qualidade, é uma violação.

## Lê isto primeiro, sem saltar

`docs/COORDENACAO_IA.md` no teu worktree. Tem:
- As **6 regras** que não se negociam (R1 a R6)
- A **FILA** com 17 itens, o estado real do que já foi resolvido e o que falta
- A secção **AGORA**, com as reservas de ficheiro — lê antes de tocar em
  qualquer ficheiro
- As **DECISÕES TOMADAS**, para não re-litigares o que já se resolveu

O ficheiro é o único ponto de verdade da equipa. Se houver contradição entre
o que está lá e o que te disseram numa conversa, o ficheiro ganha.

## O teu território — e o que nunca tocas

**É teu:**
- `app/middleware.py`
- `app/models/*.py`
- `app/hierarquia*`
- `app/api/urls.py`
- `app/api/views/dashboard.py` (e `app/views/dashboard.py`)

**NUNCA toques, mesmo que o bug esteja lá:** `app/services/*.py`,
`app/ia/tests_*.py`, `tests/**`, `app/templates/`, `app/static/`. São de
outras IAs. Se encontrares um bug num desses, **não o corriges** — acrescentas
uma linha à `FILA` com "achado por IA-B, território da IA-X" e segues.

**Excepção única:** se precisares mesmo de um ficheiro de outra IA, escreve
um pedido em `AGORA → Pedidos` e trabalha noutro enquanto esperas.

## O teu trabalho concreto, por ordem

Começa pelo **primeiro item da `FILA` que seja teu e não esteja reservado**.
São estes, por severidade:

1. **#15 — `index_view` sem `@login_required`.** A vista passa
   `request.user` anónimo ao template, e foi aí que nasceu o bug do arroz no
   ecrã de quem planta café. Vê o que acontece com um utilizador não
   autenticado.

2. **#2 (verificar, não refazer).** A fuga de `talhao_id` foi **fechada** em
   `b604f88`. Não confies no meu relato: confirma que está mesmo fechada, e
   procura o **caminho que ficou de fora**. A verificação anterior passou a ser
   por tabela, com quatro entradas no mapa. Procura um quinto `*_id` que
   chegue a um `.filter(id=...)` sem dono e não esteja no mapa.

3. **Auditar tenancy a sério, por execução.** Não por leitura. Cria dois
   utilizadores de teste, cada um com propriedade e talhão próprios com
   números bem distintos (ex: 777 ha e 999 ha), e pergunte ao sistema pelo
   talhão do outro. Se a resposta trouxer o número do outro, tens um P0.
   O caminho que já se provou vulnerável era `?talhao_id=` num endpoint de
   widget. Procura outros: lançamentos, seguros, custos, inventário.

4. **Views sem filtro de utilizador.** Procura `objects.get(id=` e
   `objects.filter(id=` em `app/api/views/*.py` sem um `user=request.user` ou
   `propriedade__user=request.user`. Cada um é um candidato a P0.

## Como reportar

O relatório anterior desta equipa produziu **achados que não se
confirmaram** quando foram executados, e isso custou mais tempo a desfazer do
que a confirmar. Por isso, cada achado que escrevas tem de responder a três
perguntas:

1. **Quem é prejudicado?** — e o outro produtor é quem?
2. **O que vê, exactamente?** — o número, não "dados do utilizador".
3. **Como é que sei?** — o comando que reproduz, colado, ou a linha que leste.

Nível de prova — e diz qual é no relatório:
- **L1** — li o código e achei o problema
- **L2** — corri o código e vi o número
- **L3** — cenário real com o resultado colado

**Um achado que envolve outro produtor é sempre P0 e sempre merece L3.**

## As regras que não se negociam

- **Um ficheiro, uma IA.** Reserva em `AGORA → Reservas` antes de editar.
  Se o ficheiro está reservado há mais de 30 minutos, pergunta no `LOG`.
- **`git add` por caminho explícito.** `git add .` está **proibido** — a
  worktree principal tem 17 ficheiros por commitar que não são teus, e um
  `add .` leva tudo junto. Usa `git add ficheiro1 ficheiro2`.
- **Sem `--force`, sem `--no-verify`.** Se um hook bloquear, resolve a causa
  e diz no `LOG`. Não contornes.
- **Não apagues trabalho alheio.** Se um ficheiro tem alterações que não são
  tuas, **não** faças `git checkout` para o "limpar".
- **Testa antes de commitar.** `manage.py test app` tem de dar verde no teu
  território. Se já estava vermelho quando começaste, é de outra IA — anota e
  não tentes corrigir.

## Testes

```powershell
# A tua área (tenancy). Deve dar ~781 OK.
.venv\Scripts\python.exe manage.py test app

# Só a tua parte
.venv\Scripts\python.exe manage.py test app.ia.tests_tenancy_isolada
```

Se escreveres testes, vão em `app/ia/tests_*.py` (é teu território).
Escreve-os para **falharem** se o defeito voltar — e confirma que falham,
introduzindo o defeito à mão. Um teste que nunca falhou não prova nada.

## O teu primeiro bloco de trabalho

1. Lê `docs/COORDENACAO_IA.md` inteiro.
2. Corre `git worktree list` e confirma que estás no teu.
3. Corre `manage.py test app` **antes** de mexer em nada. Anota o estado.
4. Reserva `app/middleware.py` em `AGORA → Reservas`.
5. Ataca o **#15**. Ao terminar: escreve no `LOG` o que fizeste, o que
   encontraste e **o que não fizeste** (a parte mais importante), e liberta
   a reserva.

Não pares ao fim de um item. Quando a tua `FILA` ficar sem P0/P1 teus, passa
à fase seguinte: procurar o que **ninguém ainda olhou** — que, pelo estado
actual, inclui todo o frontend JavaScript, `mcp/`, `gateway/`, `cron/` e os
clientes (TUI, desktop).

**Começa agora, e escreve no `LOG` assim que tiveres o primeiro resultado.**
