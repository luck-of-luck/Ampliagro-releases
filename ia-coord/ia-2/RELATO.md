DONA: IA-2
# IA-2 — Voz da AmplIA, copiloto e formato

**Slot:** `s2` · **Ramo:** `fix/agente-local-loop-conflito`
**Relatorio completo:** `console.md:261-614`
**Commits:** `2c0fe44`, `a19f7aa`, `71285c1` · **Fator:** construcao

## ENTREGUE

| entrega | essence |
|---|---|
| Fronteira subtrativa da voz, em `sandbox.executar` | nunca reescreve palavras |
| 8 prompts de `automatizar_*` para 1a pessoa | "Quer que eu...?" |
| `remarcar_tarefa` — intent novo, com a accao completa | o "sim" funciona |
| 25 numeros com ponto decimal convertidos | medido |
| Nome do sitio em vez de URL de geocodificacao | o produtor deixou de ler tubagem |

## A DECISAO DE DESENHO QUE MAIS IMPORTA

A limpeza entra em `sandbox.executar`, **antes** da resposta voltar. Nao em
cada handler. Um handler NOVO escreve **negrito** e nenhum lint o apanha. Uma
regra por handler e' uma regra que se aplica enquanto ninguem se lembra dela.

## A PRIMEIRA VERSAO, E PORQUE A FIZ REVERTER

A `limpar()` tambem traduzia. Parecia mais inteligente. Produzia:

```
"o sync fica offline"      ->  "a ligacao fica sem ligacao"
"• diesel 200 L"           ->  "Diesel 200 L"
```

Eu tinha escrito no meu docstring que *"uma voz que reescreve o sentido e'
pior do que uma voz robotica"* — e depois reescrevi.

**Um transformador que reescreve MENTE, e mente com a confianca de quem parece
ter cuidado.** O produtor que le "a ligacao fica sem ligacao" perde mais
confianca do que quem le "o sync fica offline": a segunda frase reconhece; a
primeira nao existe em portugues nenhum.

A fronteira **so subtrai**: formatacao, emoji, setas, espacamento.

## O METODO QUE VALE A PENA HERDAR

**Um teste que passa nao prova nada sobre o produto. Parti o produto de
proposito e exigi que os testes falhassem.**

Primeira tentativa: **nao fez nada.** `[IO.File]::ReadAllText` com caminho
relativo usa o directorio do .NET, nao o do PowerShell — os testes passaram
contra o ficheiro intacto. Teria sido um teste de mutacao a provar que eu
nao parti nada.

## ONDE ME PARTI

1. **Parti o `intents4.py`** — slice errada em script de reescrita em lote:
   `SyntaxError`, e o registo perdeu os 8 intents de `automatizar_*`. Foi a
   **setima** vez que um script meu anunciava sucesso sem verificar.
2. **Perdi os acentos cinco vezes** — here-string do PowerShell nao preserva
   UTF-8. Ver R8.
3. **Um `edit` reportou sucesso e nao aplicou.** So nao avancei porque verifiquei
   com `git diff`.
4. **O commit da outra sessao varreu 158 ficheiros.** Ver R3.
5. **Proclamei uma familia de bugs fechada e nao estava** — a data ISO na frase
   era a **mesma classe** da URL de geocodificacao, dois commits antes.

## O QUE NAO VERIFIQUEI

- `mypy` **nao esta instalado** neste host.
- `pytest app/ia` como directoria **penda 15 minutos**. Nao afirmo 100% verde.
- **COBERTURA SO POR PYTHON.** Nao medi Rust, Go, C, Java, TypeScript.
- 7 scanners desligados (sem Docker): `bearer`, `codeql`, `gitleaks`, `grype`,
  `osv-scanner`, `trivy`, `zap`.
- Sem comite de 46 lentes.

## A NOTA QUE LHEI NO RESUMO CONSOLIDADO

O resumo consolidado atribui-me o **metodo de verificacao** e as **tres
correccoes** (CJK, git, `edit`). Como o comite nao corre, essa parte do meu
relato **nao foi executada**: e' proposta minha, baseada nos 39 handlers que
rodei, e **nao e' comite**.
