# A próxima peça: conciliação bancária

MEDIDO 2026-10-06, antes de escolher. Fui ver o que existe e o que falta.

## O que já está em `app/models/financeiro.py`

| classe | o que é |
|---|---|
| `ContaBancaria` | a conta, com `unique_together` por (propriedade, banco, agencia, conta, digito) |
| `MovimentacaoBancaria` | o extrato, com `conciliado`, `data_conciliacao`, `hash_unico` |
| `ConciliacaoBancaria` | a ligação entre os dois |
| `Parcelamento` | a conta a pagar/receber parcelada |
| `NotaFiscalImportada` | a NF-e que já entra pelo `app/services/nfe.py` |

## Isto é o que decide o próximo passo

O que faz o Ampliagro ganhar de uma contabilidade isolada é a cadeia que liga o dinheiro do **banco** ao **talhão**, ao **insumo** e à **safra**. Cada peça já existe — nenhuma está ligada à outra.

```
conta no banco
  -> movimentacao (extrato OFX)
    -> conciliacao (isto está no banco, e um lançamento?)
      -> LancamentoFinanceiro (com talhao e propriedade)
        -> custo_talhao (orcado x realizado, por hectare)
```

A cadeia está inteira em `app/models/financeiro.py`. O que falta é **o degrau do meio**: `conciliado` é um booleano, e a pergunta que um produtor faz todo o mês é *"o que veio no extrato que eu ainda não registrei?"*. Hoje essa pergunta não tem resposta — e é a pergunta que um contabilista resolve numa tarde por mês.

## Porquê esta peça, e não outra

Uma conciliação automática de extrato é uma caixa-negra para quem tenta copiar. Acertar 90% é fácil. Acertar os 10% que importam é o trabalho — e os 10% são exactamente a proposta de valor:

- `JANEIRO FERTILIZANTE 45.000` numa fazenda com três talhões — qual talhão?
- `PAGAMENTO NF 12345` — qual nota? já foi conciliada noutra conta?
- `TRANSF AUT MENES` entre contas da própria fazenda — transferência interna não é receita nem despesa, e um sistema que a conta como uma das duas mente nas duas.

**É aqui que a IA entra com vantagem, e não como enfeite.** Casar uma linha de extrato com um lançamento é reconhecimento de padrões sobre texto que cada banco escreve à sua maneira. Tarefa de LLM. E um sistema que acerta pela IA, *mostrando as duas opções e a razão*, é mais útil do que um sistema que acerta por regra fixa — porque a regra fixa erra sempre nos mesmos casos, e o produtor aprende a não confiar nela.

## O que NÃO entra no primeiro degrau

- **Conciliar sozinho.** O `app/ia/proveniencia.py` obriga a mostrar as opções. Um sistema que escreve no banco sem o produtor ver perde a conta — foi o que aconteceu com o dashboard que lia um cookie HTTP-only.
- **Inventar uma categoria.** A proposta traz a categoria que o sistema *sugere*, com o motivo. O dinheiro só entra depois de confirmado — o mesmo caminho de `confirmar_lancamento` que já existe.
- **Tratar `None` como `0`.** Uma movimentação sem conciliação é `None`, e a tela tem de dizer "3 não conciliadas", não "saldo 0".

## O fosso verdadeiro

O fosso de uma conciliação não é o código. É a **regra de duplicata**.

O `hash_unico` de `MovimentacaoBancaria` já existe e garante que o mesmo movimento não entra duas vezes. O fosso é o critério de *"isto já foi registado?"*, que tem de sobreviver a um ano de extratos, a um produtor que digita `1.234,56` em vez de `1234.56`, e a um banco que muda o texto da descrição todos os meses.

Copiar o resto é trabalho. Copiar isso é experiência.

---

## O que este documento não é

Não é um plano. É o registo de **porquê** a próxima peça é esta e o que fica de fora. Se a escolha mudar, o porquê muda com ela — não o porquê.

**E o que eu não prometo:** que isto faça o Ampliagro melhor que cada um dos 100 da folha. Esses têm anos, equipas e dinheiro.

O que este módulo faz é **tornar o Ampliagro melhor do que já é num nicho específico** — e o nicho onde ele já está é o único que junta dados agrícolas a dados financeiros. Nenhum amongst os 100 tem a safra **e** o extrato do mesmo produtor no mesmo lugar. Essa é a aposta.
