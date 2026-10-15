docs(verificacao): porque cada decisao foi tomada, para outro agente nao a reverter

Commit sem mudanca de codigo. A purpose e' deixar escrito o PORQUE das
decisoes que ja estao no historico -- em especial as que parecem erros e
sao deliberadas.

Porque este ficheiro existe
==========================

Tres pessoas/agentes trabalharam nesta arvore no mesmo dia. Uma delas (outro
processo) fez `git add -A` e levou estas 9 alteracoes dentro do commit
d19736f. O codigo esta commitado; o RACIOCINIO nao estava. Um agente a ler
`d19736f` ve um `required_fields` que falta e uma excepcao `i.name` que
parece descuido -- e "corrige" os dois, partindo coisas.

Fica escrito o que cada uma destas coisas e'.

AS TRES QUE PARECEM ERRO E NAO SAO
==================================

1. `required_fields` AUSENTE em `feedback` e `concluir_tarefa`
   ------------------------------------------------------------
   `feedback` aceita `gostou` OU `texto`. `concluir_tarefa` aceita `id` OU
   `titulo`. `required_fields` exige TODOS os campos listados, e nao existe
   forma de escrever "um destes".

   Adicionei `["texto"]` e `["titulo"]`. Partiu os dois caminhos
   documentados: uma chamada so com `gostou` passava a pedir o campo em vez
   de executar, e a confirmacao a escrever para a tarefa errada ficava
   bloqueada. Revertido.

   O contrato real e' o do handler, nao o do catalogo. Um intent com campos
   alternativos fica SEM `required_fields`. O motivo esta em comentario no
   proprio `intents.py` -- leia antes de mexer.

2. `i.name` em vez de `i["name"]`
   -----------------------------
   Um `django.db.models.Index` e' um objecto com atributos. Subscriptar
   levanta `TypeError: 'Index' object is not subscriptable`. Nao e' estilo;
   o subscript nunca funcionou.

3. `connection.execute_wrapper` em vez de `captured_queries["stack"]`
   -----------------------------------------------------------------
   A chave `'stack'` foi REMOVIDA do Django. Este projecto corre 5.2.17.
   Verificado por `inspect.signature(CaptureQueriesContext.__init__)` ->
   `(self, connection)`: nao ha `force_debug_cursor`, nao ha `stack`. E por
   leitura do pacote: das 120 ocorrencias de "stack" no `django/`, nenhuma e'
   o registo de uma query.

   Passar `force_debug_cursor=True` levanta `TypeError`. Devolver `stack`
   vazio engole o N+1 que a sonda existe para mostrar. A via suportada e'
   `execute_wrapper`, que ve o traceback VIVO -- mais honesto que ler um
   `stack` gravado, porque diz onde foi ao momento de foi.

O AVISO QUE CUSTOU UM DIA
=========================

`__pycache__` DESACTUALIZADO FAZ O TESTE MENTIR.

Limpar cache nao e' opcional antes de contar falhas nesta arvore:

    find . -name __pycache__ -type d -exec rm -rf {} +
    rm -rf .pytest_cache

Aconteceu duas vezes, no mesmo dia, e nas duas contei errado:

  * `lcdpr_export.py` tem 898 linhas com 0045/Q200/0010. O teste via 130
    linhas sem nenhum deles. E' um `.pyc` de uma versao anterior. Reportei
    "regressao de codigo" -- e nao era verdade nenhuma das duas coisas. Nao
    era regressao, nem bug de teste: era bytecode obsoleto.

  * Seis suites deram `ERROR` na coleccao por causa disso. Desapareceram
    so com o cache limpo. Nenhuma tinha defeito.

Nao reporteie "regressao real" sem prove-la. A segunda vez que isso aconteceu
foi porque nao aprendi com a primeira.

OS DOIS ERROS QUE FORAM MEUS, E QUE FICAM AQUI PARA NAO SE REPETIREM
====================================================================

8. O score de deteccao era SOMA, nao media
   ----------------------------------------
   `total += acertos / len(ew)` por exemplo, sem nunca dividir pelo numero de
   exemplos. Uma intent com 26 exemplos tinha vantagem de 43% sobre uma com 3
   -- por ter mais exemplares, nao por casar melhor. O limiar 0.60 media
   coisa nenhuma.

   Agora `total / n_exemplos`. Se alguem voltar a somar "porque o limiar esta
   calibrado para a soma": o limiar tem de se mover com a media.

9. O `elif` que nunca corria
   -------------------------
   O filtro era `if quer_escrever: ... elif e_pergunta: ...`. O `elif` era
   INALCANCAVEL sempre que `quer_escrever` era True -- e `quer_escrever` e'
   True sempre que a frase tem verbo de escrita. "Voce pode excluir a
   safra?" chegava ao handler de escrita.

   A pergunta e' verificada PRIMEIRO. Nao inverter outra vez.

PORQUE EXISTE tests/__init__.py
===============================

`tests/` NAO ERA UM PACOTE. `from tests.lcpr_fixtures import ...` dava
`ModuleNotFoundError` com o ficheiro AO LADO. Nao faltava o ficheiro: faltava
o pacote. 22 testes davam ERROR na COLECCAO e pareciam estar errados.

Ha dois estilos de import em `tests/` e ambos precisam de arranjo:
  * com prefixo -- `from tests.X import ...`   -> precisa de `__init__.py`
  * sem prefixo -- `from test_X import ...`     -> precisa do `sys.path`

`conftest.py` mete `tests/` no `sys.path` para o segundo. Sem os dois, metade
das suites nao chega a correr.

ONDE O CODIGO DESTE COMMIT ESTA
===============================

`app/views/guias.py` -- `order_by("id")` em cinco `.first()` sem ordem, e a
ordem exacto-antes-de-normalizado em `_resolver_cultura_key` (para "Café" e
"Cafe" nao colapsarem no mesmo id) -- esta em f782051 e 21541c3. Nao esta
neste commit porque ja foi feito. NAO REVERTER: e' o que faz
`test_guia_resolve_cultura.py` passar.

PORQUE `lcdpr.py` GANHOU UMA GUARDA
===================================

Havia DOIS geradores de LCDPR e so um guardava. `lcdpr_export.py` levantava
`LCDPRDadosIncompletos` sem CPF/CNPJ; `lcdpr.py` punha `""` e seguia. Sem o
registo 0000 a Receita recusa o ficheiro e o produtor so descobre na entrega.
Nao reintroduzir um gerador sem guarda.

O QUE NAO FOI VERIFICADO
========================

Scanner estatico (sast, astgrep, semgrep) nao correu: os tres servidores
estavam a timeout o dia inteiro. A verificacao foi toda por pytest, que e'
determinista mas mais estreito -- nao apanha seguranca, dependencias
vulneraveis nem segredos.

**ESTE TRABALHO NAO FOI AUDITADO DE SEGURANCA.** Isto e' um facto, nao uma
ressalva de forma: nao ha evidencia de que esteja limpo, e ausencia de
evidencia nao e' evidencia.

COMO VERIFICAR
==============

    find . -name __pycache__ -type d -exec rm -rf {} + ; rm -rf .pytest_cache
    pytest tests app/api/tests_regressao.py app/ia/tests.py -p no:cacheprovider --no-cov -q

Estado no momento: 0 falhas. Nao assuma que se mantem -- havia outro
processo a escrever nesta arvore enquanto isto era feito. Meça.