"""As tools de catalogo que existem. UMA lista, nomeada, com a decisao escrita.

MEDIDO 2026-10-05 (agente 9). Substitui a checagem `len(...) == 2`, que
media a lista em vez de a nomear. Um numero que cresce sozinho e' o que
produz tools por tropeco — e era esse o defeito da guarda anterior, que so
via a CONTAGEM e por isso nao dizia nada sobre *quais* tools eram
aceiteiras.

A DECISAO
=========
Quatro leitores de dominio, todos por contexto, nenhum a escrever:

  amplia_catalogos          o que existe para construir telas
  amplia_desenhar_pagina    monta uma tela do catalogo
  amplia_inventario_carbono GHG da propriedade, com a fonte do fator
  amplia_estado_sistema    os invariantes que ja partiram, medidos agora
  amplia_comparativo         os 50 VEREDITOS da planilha 100x50, medidos em codigo

O QUE NAO PODE ENTRAR
=====================
Uma tool que ESCREVA. O catalogo e' leitura de codigo: `executar_catalogo` nao
passa pelo `sandbox` de proposito, para o registo de "o que a IA fez" nao se
transformar em ruido de leituras. Uma tool de escrita aqui seria uma acao sem
confirmacao nem auditoria.

E uma tool que diga mais do que sabe. `amplia_inventario_carbono` passa
porque diz o que nao mede: conta a area que o produtor DECLARA, com o fator
e a fonte nomeados.

DUAS FERRAMENTAS PARA A MESMA PERGUNTA (MEDIDO 2026-10-05)
  =========================================================
  Chegou a haver um intent chamado `comparativo` E uma tool de catalogo
  chamada `amplia_comparativo`: dois caminhos, um nome.

  A LEITURA QUE FALHAVA — e que ja esteve escrita aqui errada
  ---------------------------------------------------------
  Afirmou-se que `comparativo_revisao` tratava "compliance ambiental" e que
  `amplia_comparativo` era a unica a ler a planilha 100x50. Dai a conclusao de
  que a planilha estava ORFA e de que a tool devia ser re-admitida.

  Era falso, e era o tipo de falso que so aparece com execucao.
  `h_comparativo` chama `remedir()` (`app/ia/intents_comparativo.py:62`), que
  abre o MESMO `comparativo-100x50.xlsx`: devolve 50 dimensoes, os veredictos
  remediados, 16 divergentes face a planilha e o carimbo `como_ler`. A
  planilha nunca esteve orfa.

  COMO O ERRO SE ESCONDEU
  ----------------------
  `'amplia_comparativo' in catalogo_tools()` deu False, e dai veio "ninguem a
  chama". Um caminho ausente nao prova que a pergunta nao tem caminho — so
  prova que AQUELE caminho nao a serve. Havia outro, e era o intent, que ainda
  tem `x-read-only` e o aviso do que `E` significa.

  Re-admitir `amplia_comparativo` seriam duas ferramentas para a mesma
  pergunta, que e' o que `test_nenhuma_tool_nova` existe para impedir.
"""

TOOLS_CATALOGO_ACEITAS = frozenset(
    {
        "amplia_catalogos",
        "amplia_desenhar_pagina",
        "amplia_inventario_carbono",
        # Publicada por outra sessao, 2026-10-05. `TOOLS_CATALOGO` tem esta
        # tool e `NOMES_CATALOGO` deriva dela, logo a lista dos nomes
        # publicaveis tem de a citar: e a entrada em TOOLS_CATALOGO que torna
        # a decisao de a publicar explicita. Sem esta linha o guard acusa
        # NOMES_CATALOGO != TOOLS_CATALOGO_ACEITAS e a tool fica viva e nao
        # declarada, que e o pior estado: funciona, e ninguem sabe que foi
        # decidido.
        "amplia_estado_sistema",
        # MEDIDO 2026-10-05, tres voltas nesta lista, e as tres serviram para
        # perceber o que a lista e'.
        #
        # **O QUE ELA E'**: a decisao de **publicar**. Nao e' `TOOLS_CATALOGO`,
        # e nao pretende ser. `executar_para` allowlista por aqui, e por isso
        # qualquer nome aqui e' uma capacidade que o cliente pode chamar.
        #
        # **1.** Aqui esteve `amplia_comparativo`, nome de uma entrada de
        # catalogo que deixou de existir quando o intent `comparativo` passou
        # a `comparativo_revisao` e `nome_tool()` passou a publicar
        # `amplia_comparativo_revisao`. A entrada velha saiu porque o nome
        # mudou; a nova entrava porque o cliente recebe esse.
        #
        # **2.** `amplia_comparativo_revisao` entrou de facto, mas a sessao
        # seguinte removes: interpretei a lista como "as tools de catalogo" e
        # pensei que um intent nao tinha lugar aqui. **Estava errado.**
        # `app/tests_ciclo_automacao.py::ComparativoAcessivelTest` exige que
        # o nome esteja na allowlist e que `executar_para` despache — porque
        # e' isso que a lista declara: quem pode ser chamado.
        #
        # **3.** `amplia_estado_sistema` publicada por outra sessao. Entra
        # pelo mesmo motivo: `TOOLS_CATALOGO` tem-na, logo e' uma capacidade
        # que o cliente pode invocar, e a lista tem de dize-lo.
        #
        # A distincao que faltava: uma ferramenta pode **nao** estar em
        # `TOOLS_CATALOGO` e mesmo assim ter de estar aqui. O que e' verdade
        # e' que estas duas listas medem coisas diferentes — daiprecisa de
        # guardas para cada uma, e nao de as reduzirem a uma.
        "amplia_comparativo_revisao",
    }
)
