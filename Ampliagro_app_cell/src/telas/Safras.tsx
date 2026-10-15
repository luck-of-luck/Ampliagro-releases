import React, { useCallback } from 'react';
import { FlatList, RefreshControl, StyleSheet, Text, View } from 'react-native';

import { buscarSafras } from '../api';
import { Aviso, Carregando, Linha, Vazio } from '../componentes';
import { cores, dataCurta, moeda, numero } from '../tema';
import { useRecurso } from '../useRecurso';

export default function Safras({ base }: { base: string }) {
  const carregar = useCallback(() => buscarSafras(base), [base]);
  const { dados, carregando, erro, recarregar } = useRecurso(carregar, [base]);

  if (carregando && !dados) {
    return <Carregando texto="A carregar safras…" />;
  }
  if (erro) {
    return <Aviso mensagem={erro} aoTentarNovamente={recarregar} />;
  }

  return (
    <FlatList
      style={estilos.scroll}
      contentContainerStyle={estilos.conteudo}
      data={dados ?? []}
      keyExtractor={item => String(item.id)}
      refreshControl={
        <RefreshControl
          refreshing={carregando}
          onRefresh={recarregar}
          tintColor={cores.primaria}
        />
      }
      ListEmptyComponent={<Vazio mensagem="Nenhuma safra registada." />}
      renderItem={({ item }) => (
        <View style={estilos.item}>
          <View style={estilos.itemTopo}>
            <Text style={estilos.nome}>
              {item.safra_nome ?? `Safra ${item.ano ?? ''}`}
            </Text>
            <Text style={estilos.cultura}>{item.cultura_nome ?? '—'}</Text>
          </View>
          {item.talhao_nome ? (
            <Text style={estilos.talhao}>{item.talhao_nome}</Text>
          ) : null}
          <View style={estilos.linhas}>
            <Linha
              rotulo="Área plantada"
              valor={`${numero(item.area_plantada, 2)} ha`}
            />
            <Linha
              rotulo="Área colhida"
              valor={`${numero(item.area_colhida, 2)} ha`}
            />
            <Linha
              rotulo="Produtividade"
              valor={`${numero(item.produtividade, 2)} sc/ha`}
            />
            <Linha rotulo="Produção" valor={numero(item.producao_total, 0)} />
            <Linha
              rotulo="Receita estimada"
              valor={moeda(item.receita_estimada)}
            />
            <Linha
              rotulo="Plantio / colheita"
              valor={`${dataCurta(item.data_plantio)} → ${dataCurta(item.data_colheita)}`}
            />
          </View>
        </View>
      )}
    />
  );
}

const estilos = StyleSheet.create({
  scroll: { flex: 1, backgroundColor: cores.fundo },
  conteudo: { padding: 14, paddingBottom: 32 },
  item: {
    backgroundColor: cores.superficie,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: cores.borda,
    padding: 14,
    marginBottom: 10,
  },
  itemTopo: { flexDirection: 'row', justifyContent: 'space-between' },
  nome: {
    fontSize: 15,
    fontWeight: '700',
    color: cores.texto,
    flex: 1,
    marginRight: 10,
  },
  cultura: { fontSize: 13, fontWeight: '600', color: cores.primariaEscura },
  talhao: { fontSize: 12, color: cores.textoSuave, marginTop: 4 },
  linhas: { marginTop: 10 },
});
