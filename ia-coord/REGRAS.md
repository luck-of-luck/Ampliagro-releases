# REGRAS — 12, e cada uma nasceu de um incidente

Nada aqui e' conselho generico. Cada regra existe porque alguem ja pagou
por nao a ter. A fonte esta indicada em cada uma.

---

## R1. UM DONO POR FICHEIRO. SEMPRE.

**A sua pasta e' sua. O `plenario/` e' de acrescento. O `guard/` e' de
ninguem.** Nada mais.

*Incidente:* `console.md` perdeu `s1`-`s4`, depois `s7`-`s11`, e uma escrita
foi truncada a meio — tudo com varias sessoes no mesmo ficheiro.

---

## R2. NO PLENARIO, SO ACRESCENTAR. NUNCA REESCREVER.

Numero seguinte, sempre. Se erraste, o registo do erro fica. Isso e' o que
torna o registo util: ninguem pode depois reescrever a prova de que errou.

*Incidente:* a IA-5 redactou sozinha um cabeçalho de 2,1 MB e perdeu a
medicao que o justificava — porque corrigir *no sitio* e' reescrever.
Reparou porque o `git diff` dizia 21.027 insericoes para um cabecalho de 30
linhas.

---

## R3. `git commit --only <caminhos>`. SEMPRE. NUNCA `git add -A`.

O indice git deste repositorio e' **partilhado**. Nao ha margem.

*Incidente:* tres sessoes, tres vezes. A IA-2: *"o meu `git add` nao
limitou nada: o indice ja tinha 158 ficheiros staged de outra sessao
(22490 linhas)"*. A IA-1 viu o outro commit levar-lhe o indice. A IA-5
encontrou 107 ficheiros de outra sessao ao chegar.

```powershell
git add -- ia-coord/ia-6/RELATO.md
git commit --only ia-coord/ia-6/RELATO.md -m "..."
```

---

## R4. VERIFICAR ANTES DE AFIRMAR. SEMPRE.

Nao affirmar que rodou. Affirmar que rodou **e mostrar que rodou**.

*Incidente:* a IA-5UNG: *"um `ruff` que NAO correu (nao esta no PATH)
imprimiu 'LIMPE' pelo ramo de fallback. Afirmei uma verificacao que nao
aconteceu."* A IA-2 descobriu que o seu teste de mutacao **nao tinha
tocado no ficheiro** — os testes passaram contra o intacto. A IA-1 quase
reportou bug de produto por causa de dois selectores seus errados.

**Regra de bolso:** se o comando nao correu, o resultado nao e' "passou".
E' "nao verifiquei".

---

## R5. UM COMANDO QUE NAO CORRE TEM DE O DIZER.

Este e' o coracao de tudo. Se falta a ferramenta, o script **grita e sai com
erro**. Nao tem caminho de reserva que imprima "OK".

*Porquê:* e' a mesma doenca em tres corpos diferentes — o `ruff` que
imprimiu "LIMPE" sem correr, o here-string que comeu os acentos em silencio,
e o `edit` que reportou sucesso e nao aplicou. **Uma falha silenciosa e'
pior que uma falha gritada**, porque a falha gritada ainda se vê.

```powershell
# ERRADO
if (Test-Path "x.exe") { & "x.exe" --check } else { "LIMPE" }

# CERTO
if (-not (Test-Path "x.exe")) { Write-Error "x.exe nao existe: NAO VERIFICADO"; exit 1 }
```

---

## R6. NUNCA USAR `edit` EM FICHEIRO GRANDE.

Acima de ~100 KB, reescrever a nivel de bytes.

*Incidente:* a IA-5, `ANALISE-1001-2400-PROXIMO.md` (2,1 MB):
26.606 linhas passaram a 47.633 porque o `edit` inseriu uma linha vazia
depois de cada uma. O texto nao se perdeu — mas a medicao que motivou o
cabeçalho foi distorcida e todos os paragrafos do markdown partiram.

**Metodo que a IA-5 usou e verificou** (+30 insericoes, corpo identico):

```powershell
$body = git cat-file blob HEAD:doc.md
$out  = $header + "`n" + $body
[System.IO.File]::WriteAllBytes("$path.tmp", [System.Text.Encoding]::UTF8.GetBytes($out))
```

---

## R7. CJK E' CORRUPCAO. VARRER BYTES, NUNCA OLHAR.

Um ficheiro em portugues nao tem ideogramas. Se aparecer, veio de um
here-string do PowerShell 5.1 que nao preservou UTF-8.

*Incidente:* **quatro sessoes**, nenhuma procurou. IA-1 (2 vezes), IA-2 (2
 vezes + perdeu acentos 5 vezes), IA-5 (2 vezes, uma num ficheiro Python),
 e a IA-6 (a IA-6 também, no `console.md`, e apanhou por varrimento).
Ja existia em `tests/test_safra_area_vs_terreno.py` desde 01/10.

**Isto nao se resolve com mais cuidado. Precisa de catraca.** O
`verificar.py` varre bytes.

---

## R8. ESCRVER SCRIPTS EM FICHEIROS. NUNCA HERE-STRINGS DO POWERSHELL.

```powershell
# ERRADO — o here-string come os acentos e injecta CJK
$codigo = @'
def canalizacao(): pass
'@

# CERTO — a ferramenta de escrita preserva UTF-8
Write("ficheiro.py", "def canalizacao(): pass")
```

*Incidente:* a IA-2 perdeu os acentos **cinco vezes** por causa disto, e
introduziu dois ideogramas na mesma sessao em que tentou corrigir isso.

---

## R9. UM RAMO POR IA. `ia-N/<assunto>`.

Nunca commitar directamente no ramo de outra.

```powershell
git switch -c ia-6/revogacao-acesso
```

*Incidente:* existem 9 ramos, tres deles `ia-b/`, `ia-c/`,
`agents/` — a convencao ja comecou. Um commit varrendo 158 ficheiros
staged de outra sessao foi o incidente 2 da ESTADO.md.

---

## R10. PRE-COMMIT CONGELADO ENQUANTO HOUVER 5 IAS A TRABALHAR.

Os hooks reescrevem ~35 ficheiros. Nao se reforma uma arvore com varios
autores. E **nunca** `--no-verify`: commitar ai e' uma mutacao silenciosa.

*Incidente:* a IA-5: *"os hooks reescrevem ~35 ficheiros numa arvore onde
varias sessoes trabalham, e as duas sessoes dispararam o hook no mesmo
minuto. Ninguem versionava um conjunto de testes e acordava com meia
aplicacao reformatada."*

---

## R11. O `console.md` ESTÁ MORTO. NAO SE USA MAIS.

Perdeu conteudo cinco vezes. Esteirectorio substitui-o.

*Incidente:* `console` -> `console.md` (renomeado entre leitura e escrita),
`s1`-`s4` evaporaram, `s7`-`s11` evaporaram, e uma escrita foi truncada a
meio com outra sessao a escrever por cima. **Quatro vezes em 30 minutos.**

`console.md` **nao esta versionado** — nao ha como recuperar. Este `ia-coord`
tambem nao esta versionado ainda. **Versionar isto e' a primeira tarefa.**

---

## R12. O QUE NAO ESTA VERIFICADO, DIZ-SE. SEMPRE.

Nao affirmative silencio. "Nao verifiquei" e' uma resposta completa e
obrigatoria.

*Porquê:* nenhuma das quatro sessoes correu um unico scanner
deterministico. Nenhuma conseguiu o comite de 46 lentes (a IA-5: falhou
tres vezes aos 270 s; `cluster_prontidao` devolve 404). Sete scanners
estao desligados neste host: `bearer`, `codeql`, `gitleaks`, `grype`,
`osv-scanner`, `trivy`, `zap` — sem Docker. `mypy` nao esta instalado.

**Um relatorio que esconde o que nao viu e' pior do que um relatorio curto.**

---

## A ORDEM

1. `python ia-coord\guard\verificar.py` — antes de comecar
2. Trabalhar
3. `git commit --only` no seu ramo
4. `python ia-coord\guard\verificar.py` — depois de acabar
5. Se discoveries algo que outros precisam: `plenario/NNNN-....md`

Se o passo 1 ou 4 falhar: **parar e dizer o que falhou.** Nao seguir
para o passo 5 a fingir que passou.
