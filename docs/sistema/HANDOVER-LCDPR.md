# HANDOVER — LCDPR e promessas: o que mudou e o que NÃO tocar

**Data:** 2026-10-05
**Autor:** este commit
**Para:** quem vai continuar a trabalhar no LCDPR, no cadastro de propriedade ou
nas promessas do produto.

Este ficheiro existe por uma razão concreta: **esta sessão teve mais erros meus
do que achados, e todos foram da mesma classe.** Se não souberdes onde não pisar,
vais repetir os mesmos.

---

## 1. O QUE ESTÁ FEITO, E COMO VERIFICAR

### O enunciado oficial foi obtido

O `lcdpr_layout.py` tem agora os **nove registos** do Manual de Preenchimento do
LCDPR 1.3 (Receita Federal, secção 3.3), transcritos com nomes **e ordem**.

```python
from app.services.lcdpr_layout import CAMPOS_POR_REGISTRO
len(CAMPOS_POR_REGISTRO)   # 9
```

Contagens oficiais, todas a bater:

| registo | campos | | registo | campos |
|---|---|---|---|---|
| `0000` | 10 | | `0045` | 6 |
| `0010` | 2 | | `0050` | 7 |
| `0030` | 10 | | `Q100` | 13 |
| `0040` | **17** | | `Q200` | 6 |
| | | | `9999` | 2 |

### Corrigi registos que estavam escritos errados

| registo | antes | agora |
|---|---|---|
| `0040` | **13 campos**, e do 5.º em diante todos na posição errada | **17 campos**, ordem oficial |
| `0045` | **4 campos** — sem `COD_IMOVEL`, `TIPO_CONTRAPARTE`, `PERC_CONTRAPARTE` | **6 campos** |
| `0030` | `COD_MUN` e `CEP` **vazios**, ambos `Sim` no manual | escrevem o que o produtor cadastrou |

No `0040`, o pior era `INSCR_ESTADUAL` receber **o nome da fazenda** e `CEP`
receber **a participação**.

### Uma função só monta linhas

`lcdpr_layout.linha(registo, *valores)` é a **única** montadora, e valida a
contagem contra `CAMPOS_POR_REGISTRO` — levanta `LayoutInvalido` se bater certo
ao número errado.

```python
linha('0045', '001', '3', '12345678901', 'Maria Parceira', '')
# |0045|001|3|12345678901|Maria Parceira||
```

**Se precisares de gerar um registo novo, usa `linha()`.** E' o que impede a
divergência de voltar.

### Campos novos no modelo

`0070_propriedade_endereco_fiscal.py` acrescenta cinco campos, todos `blank=True`:

| campo | para que serve |
|---|---|
| `cod_municipio` | `COD_MUN`, **código IBGE de 7 dígitos** — **não é** `cidade`, que é o nome |
| `cep` | 8 dígitos |
| `bairro` | `BAIRRO`, `Sim` |
| `telefone` | `NUM_TEL`, opcional |
| `cad_itr` | campo 5 do `0040`. **Não é o `caepf`** |

Expostos no serializer, no formulário (`cadastro-propriedade.html`, secção
*"Configurações Fiscais (LCDPR)"*) e no JavaScript que os envia — este último
**não** os enviava, e era um formulário que mentia: preenchia e descartava.

---

## 2. NÃO TOCAR — e porquê

### 2.1 `PERC_CONTRAPARTE` fica vazio, de propósito

O `0045` é condicionalmente obrigatório quando há parceria ou condomínio, e o
campo 6 é a percentagem de cada contraparte. Está a sair **vazio**.

**Não é uma omissão.** Não existe campo no modelo para a percentagem de cada
terceiro. `Propriedade.participacao` é a percentagem do produtor **declarante**,
e `MembroPropriedade` é sobre *acesso ao sistema*, não sobre exploração agrícola.

Deduzir *"os outros dividem o resto a partes iguais"* seria inventar a estrutura
de propriedade de uma empresa de outra pessoa. Pode haver dois parceiros a 40% e
10%. Um repartição errada no ficheiro fiscal é rectificação que só fecha em anos.

Se quiseres fechar isto, o caminho é um modelo novo — e é decisão de domínio.

### 2.2 `cad_itr` não é apagado na anonimização LGPD

`app/views/lgpd.py` limpa `cpf_cnpj`, `caepf` e `inscricao_estadual`. **`cad_itr`
não entra**, e há um comentário a dizer porquê.

É um conflito real entre LGPD e obrigação fiscal, e a decisão **não é minha**.
Está registado no código, não escondido.

### 2.3 `exigir_talhoes` e `exigir_campos_fiscais` são opcionais

Por defeito, `pode_exportar()` não exige nada disto. Um produtor no primeiro ano
pode não ter código cadastrado, e **recusar-lhe a exportação não o ajuda** — o
que o ajuda é ver a linha incompleta e saber o que falta.

Um produtor existente **não fica inválido** com a migração: os cinco campos vêm
`""`. A guarda é para quem a quiser ligar.

---

## 3. O QUE ESTÁ POR VERIFICAR

### 3.1 O validador da Receita nunca correu

**Este é o limite honesto deste trabalho.** O enunciado oficial foi transcrito e
as contagens batem — mas **transcrever uma especificação não é ter um ficheiro
aceite**.

O validador é Java. Nesta máquina não há `java`, `javac`, nem JDK em disco. Não
há caminho lateral. **Qualquer afirmação de "o LCDPR está conforme" é falsa até
que alguém o corra.**

### 3.2 O que o enunciado não resolveu

| | |
|---|---|
| `0030.COD_MUN` e `CEP` | `Sim` no manual; vazios enquanto o produtor não cadastrar |
| `0040.CAD_ITR` | o modelo agora tem o campo; vazio até ser cadastrado |
| `PERC_CONTRAPARTE` | sem fonte — ver 2.1 |

---

## 4. A CLASSE DE ERRO — LEIA ISTO ANTES DE MEDIR

Três erros meus, nesta sessão, **todos a mesma coisa**: afirmação sem fonte
primária, transformada em facto.

| o que fiz | como foi apanhado |
|---|---|
| Reportei o `0040` como *"dois geradores, um partido"*, com código e tudo | O `grep` casou com uma **docstring** que descrevia a correcção. O código estava certo |
| Escrevi que o LCDPR tem *"Bloco Z"* com totalizadores | A fonte foi um **blog de concorrente**. O Bloco Z é de **outro arquivo** (CONFAZ Anexo II, grupos societários). O LCDPR não tem |
| Quase reportei uma chave Fernet como segredo hardcoded | O ficheiro era `config/settings/test.py` — settings de **teste**, com o comentário *"nunca produção"* na linha de cima |

**As regras que saíram daqui, e que estão nos ficheiros:**

1. **Um `grep` que casa numa docstring, num comentário ou num teste não é um
   achado.** É um achado sobre a *documentação* do achado.
2. **Concorrente é pista de pesquisa, nunca fonte.** Só o enunciado oficial.
3. **Sem enunciado, escreve-se "não verificado"** — e isso basta. Uma lacuna
   declarada é útil; uma lacuna inventada é armadilha.

O `9.md` §A.0 descreve o mesmo em relação ao medidor que deu 21 "OK" em coisas
inexistentes. **Os três casos são esse caso.**

---

## 5. GUARDAS NOVAS — o que passaram a falhar, e quando

Não são testes de qualidade que passam. São guardas que **reprovam** quando algo
regressa.

| ficheiro | o que prende |
|---|---|
| `test_dependencias_declaradas.py` | Qualquer módulo do `MIDDLEWARE` de uma distribuição não declarada. `django-csp` **e** `whitenoise` estavam exactamente assim |
| `test_agendador_unico.py` | Celery BEAT armado **e** tarefas do Windows instaladas |
| `test_promessas_absolutas.py` | A volta de "Sistema **absoluto**" à meta description |
| `test_lcdpr_campos_fiscais.py` | A cadeia modelo → guarda → gerador → ficheiro, elo por elo |
| `test_lcdpr_conformidade.py` | As contagens dos nove registos contra o manual |
| `test_manifesto_confere_com_codigo.py` | Promessas do manifesto, com `xfail(strict=True)` |

### O `xfail(strict=True)` merece atenção

Os dez testes de promessa não cumprida levam `@pytest.mark.xfail(strict=True)` e
asserção **invertida**. O efeito:

| estado | pytest | suite |
|---|---|---|
| promessa em aberto | `x` XFAIL | **verde** |
| promessa cumprida | `F` XPASS(strict) | **vermelha** |

**Implementar a promessa deixa de ser silencioso.** O marcador obriga a ser
removido. Sem `strict`, o `xfail` mente: a lacuna fecha e o marcador fica lá a
dizer falsehoods.

**É por isso que `test_nfe_nao_tem_implementacao` passou a
`test_a_leitura_de_nfe_existe_e_a_emissao_nao`** — porque "tem NF-e" não é uma
condição, são três: ler (feito), ir buscar à SEFAZ (não, exige certificado A1),
emitir (não, e de propósito).

---

## 6. CONVENÇÕES

**Nomes de campo do LCDPR sem acento.** O manual escreve `COD_IMÓVEL`;
o código usa `COD_IMOVEL`. Um ficheiro com nomes divergentes para o mesmo campo
é pior do que um sem acento.

**`PERC_CONTRAPARTE` vs `CPF_CONTRAPARTE`.** O manual diz `ID_CONTRAPARTE`, a
documentação da Senior diz `CPF_CONTRAPARTE`. Coincidem em posição e tamanho
(11, 14). Adota-se o do manual e a divergência fica registada em
`lcdpr_layout.CAMPOS_0045` — em vez de escolhida em silêncio.

**Ao acrescentar um campo ao `0040`:** 17 campos, e `linha()` valida. Se o
número não bater, a excepção é tua, e o manual tem a resposta.

---

## 7. O QUE NÃO SEI

- **Se o ficheiro é aceite pela Receita.** (§3.1)
- **A matriz completa de regras de validação do validador** — o enunciado dá a
  estrutura; as regras de consistência entre registos são um conjunto separado
  que não transcrevi.
- **`PERC_CONTRAPARTE` na prática** — não tenho caso real de parceria com
  percentagens, só o enunciado.
- **Preço, custo e TCO.** Ninguém mediu. Não inventei números.
