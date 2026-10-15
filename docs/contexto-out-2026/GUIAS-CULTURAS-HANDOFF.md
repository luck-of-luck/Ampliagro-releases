# Guias de cultura e de ferramentas — o que foi feito, e o que NÃO tocar

> **Este documento é para quem vai continuar, não para quem vai substituir.**
> Escrevi-o porque os quatro commits abaixo partilham uma ideia que não
> está escrita em nenhum sítio do código, e sem ela a próxima pessoa
> "simplifica" e reintroduz os bugs.

---

## 1. O padrão que une tudo isto

Os quatro commits são **o mesmo erro, quatro vezes**, em quatro sítios
diferentes. O erro é sempre:

> **Um número escrito à mão que não tem de onde vir — e que a leitura
> correcta do bug seria "o produtor não registou nada".**

| commit | o número inventado | a resposta certa era |
|---|---|---|
| `f782051` | `icontains=""` casava com todas as linhas | "cultura arbitrária" |
| `809b62a`/`363a0f3` | contagem por `grupo='animal'` | "0 registos" — e havia 8 |
| `c81a0e6` | 15 cores literais | (não era número) |
| `e6d193e` | `IoT: 4` com 8 dispositivos | "4 sensores" — tinha 8 |

Repara no padrão: **em três dos quatro, o bug produzia uma resposta
plausível e errada.** Nenhum deles produzia um erro visível. Um contador
que devolve 0, um `icontains` que devolve a primeira linha, um `stat-value`
que devolve 4 — todos parecem funcionar. É por isso que os testes
escritos *depois* do sintoma são o que os apanha.

---

## 2. `e6d193e` — a guia de ferramentas anunciava números inventados

### O que estava errado

`app/templates/guia-ferramentas.html` tinha quatro `stat-value`
**hardcoded no HTML**, e a vista passava contexto nenhum:

```python
# ANTES — literalmente nada
return _no_store(render(request, "guia-ferramentas.html", {}))
```

MEDIDO 2026-10-05, contando o template e a base:

| | anunciado no HTML | real |
|---|---|---|
| Calculadoras | 4 | **7** |
| Simuladores | 3 | **5** |
| **IoT** | **4** | **8** |
| Utilitários | 5 | 5 |

### A regra que escrevi no código

Os três primeiros são **inventário de cartões do template** — não há
tabela que os conte. Vão para `N_CALCULADORAS` e companhia no `guias.py`,
**com um teste que os ata ao que existe**. A ausência de uma tabela que
conte cartões é o que deixou o número escrito à mão em primeiro lugar.

O quarto — IoT — é **dado**, e vem de:
```python
Device.objects.filter(propriedade__user=request.user)
```

### O que NÃO substituir

Os quatro testes em `tests/test_guia_ferramentas_numeros.py` estão escritos
para **travar a regressão**, não para descrever o estado atual:

- `test_nenhum_numero_hardcoded_no_cabecalho` — falha se alguém voltar a
  escrever um dígito num `stat-value`. É a ratchet.
- `test_o_numero_de_iot_vem_dos_dispositivos_dele` — cria 3 sensores,
  exige 3. Um número que não muda com a base não é uma contagem.
- `test_o_numero_nao_conta_o_vizinho` — 1 sensor próprio vs 6 no total.
  `Device` é por `propriedade`; o número tem de respeitar isso.
- `test_o_numero_de_calculadoras_bate_com_o_que_existe` — conta duas vezes
  (HTML gerado e ficheiro) e compara. **As duas metades não se validam a si
  próprias.**

---

## 3. O botão NDVI está VERMELHO DE PROPÓSITO

**`tests/test_guia_ferramentas_ndvi.py` falha. Não o apagues e não o faças
passar.** Isto é o mais importante deste documento.

`window.ndviFerramenta` pede `/api/ia/super/?talhao=1`. MEDIDO:

```
resolve('/api/ia/super/')               -> Resolver404
Client().get('/api/ia/super/?talhao=1') -> HTTP 404
```

**A rota não existe.** Então `fetch` devolve 404, `r.json()` sobre HTML
**lança** `SyntaxError`, e o `catch` entra — e o `catch` mostra:

```js
alert('NDVI 0.72 • zonas A/B/C geradas');
```

O ramo de falha **é o ramo normal**, porque o `try` nunca executa uma vez.
E o `|| '0.72'` no outro ramo põe o mesmo número: **três caminhos, dois
inventam, nenhum mostra "sem leitura".**

Isto é pior que o "707 culturas". O 707 estava num cartão que se lê uma
vez; este está num botão que o produtor **acciona** e recebe 0.72 como se
fosse a leitura de um sensor que ele não tem.

### Como resolver, quando a rota existir

1. Criar a rota (ou apontar para a que já serve NDVI — ver §5).
2. **O `catch` tem de deixar de ter número.** É a segunda parte do teste
   (`test_o_catch_nao_mostra_um_ndvi`) e vale tanto como a primeira.
3. Sem leitura → dizer que não há leitura. Nunca 0.72.

---

## 4. `809b62a` + `363a0f3` — a ponte `cultura_id`

A guia animal filtra `Cultura.grupo IN ('bovinos', ...)`. O produtor escreve
`RegistroProducao.grupo = 'animal'`. **Nenhuma das duas colunas está
ligada a outra.** A contagem por `grupo` dava **zero**, com 8 registos
existentes.

A ponte é o `cultura_id`, preenchido em **100%** dos 66 registos:

```
Ayrshire  -> 28533 -> bovinos
Tilápia   -> 28709 -> peixes
```

Porquê um serviço novo e não `historico_cultura.py`: **`historico_cultura`
conta ciclos de plantio. Um boi não tem ciclo de plantio** — tem lactação
(305 dias), gestação (283). Aplicar ciclo de safras a um cartão de gado é
escrever "128 dias" num bovino, com a minha assinatura em baixo. Por isso
`app/services/registro_por_cultura.py`, com métricas que fazem sentido
para gado.

### Duas armadilhas que estes testes fecham

1. **O `@login_required` ficou por cima de `_contexto_com_registos`** — que
   não é uma vista, é uma auxiliar. Dava
   `AttributeError: 'dict' object has no attribute 'user'` e as duas guias
   davam 500. Um decorador numa auxiliar é um erro de leitura: o nome da
   função não diz o que ela é. **Se moveres `_contexto_com_registos`,
   confirma que o decorador ficou em `guia_animal_view`.**
2. **`RegistroProducao` não tem campo `propriedade`** — tem `user`. As
   fixtures que tentam `propriedade=self.prop` rebentam. O tenancy entra
   pelo filtro na vista, e a assinatura do serviço tem um teste que a fixa.

---

## 5. Referências medidas (2026-10-05, `db.sqlite3`)

Guarda isto. Foi medido, não suposto:

| facto | número |
|---|---|
| `app_cultura` | 709 linhas, **685 nomes distintos** |
| `cultures-config.json` | 488 entradas, 483 nomes distintos |
| por nome | 483 comuns, 202 só na tabela, **0 órfãos no config** |
| `app_device` | **8 dispositivos** |
| `RegistroProducao` | 66 registos, 7 `animal` + 1 `aquatica` |
| janelas de plantio | **0 de 709** |
| ciclo de días | 2 de 709 |
| safras reais | 9 safras, **6 culturas** |

Números que **não** são globais e confundem:

- **`VEGETAL_GRUPOS` cobre 16 grupos** — 709 é o total da tabela, **inclui
  animal/aquática**. A guia vegetal não mostra 709. E o bucket "outras"
  dela apanha tudo o que não está nesses 16 grupos — **o que inclui
  animal/aquática**, que já têm guia própria. Isto está por resolver (§6).
- **22 nomes exactamente duplicados** na tabela, 25 colisões normalizadas.
  `Café`/`Cafe` parte 1 + 4 safras. Decisão de produto, com o registo
  pronto no teste (`?dedupe=1`, commits `7d4e364` e `dda7a96` da outra
  sessão).

`quantidade` em `RegistroProducao` é 6 de 66 e ficou **de fora** de
propósito: num cartão de gado a quantidade é *de quê* — @unidades, outro,
peso, ração. Número solto sem unidade é pior que nada.

---

## 6. Fica pendente (por decisão, não por esquecimento)

1. **Botão NDVI** — §3. Vermelho de propósito.
2. **`guia-sistemas`** — agrupa 4 culturas em "outras" sem registo. Não
   foi auditada.
3. **Escopo da guia vegetal** — o "outras" inclui animal/aquática.
4. **Duplicados** — §5.
5. **Janelas de plantio** — precisam de fonte (Embrapa) e **não se
   escrevem de memória**. Zero de 709 preenchido.

---

## 7. Como correr isto

```powershell
Set-Location "C:\Trabalho\Projetos\Ativos\Ampliagro"
python -m pytest tests/test_guia_ferramentas_numeros.py `
                 tests/test_guia_animal_registos.py `
                 tests/test_registro_por_cultura.py `
                 tests/test_historico_cultura.py `
                 tests/test_guia_mostra_historico.py `
                 -p no:cacheprovider --no-cov -q
```

**Regra da casa, e não é minha:** `git add -A` está proibido. Há várias
sessões a trabalhar no mesmo repositório. Usa `git commit --only` com os
ficheiros explícitos, e nunca faças push de trabalho que não committaste.

Ratchets que existem e que **não se baixam em silêncio**:
`tests/test_aparencia_invariante.py` e `tests/test_token_violacao.py`. Se
crescerem, a baseline aceita-se com `python tests/gen_aparencia_baseline.py
--motivo "<a razão>"` — **escrevendo a razão**. Baixar uma ratchet sem
explicação é exactamente o que ela existe para impedir.
