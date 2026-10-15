import React, { useCallback } from 'react';
import { FlatList, RefreshControl, StyleSheet, Text, View } from 'react-native';

import { buscarTalhoes } from '../api';
import { Aviso, Carregando, Vazio } from '../componentes';
import { cores, numero } from '../tema';
import { useRecurso } from '../useRecurso';

export default function Talhoes({ base }: { base: string }) {
  const carregar = useCallback(() => buscarTalhoes(base), [base]);
  const { dados, carregando, erro, recarregar } = useRecurso(carregar, [base]);

  if (carregando && !dados) {
    return <Carregando texto="A carregar talhões…" />;
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
      ListEmptyComponent={<Vazio mensagem="Nenhum talhão cadastrado." />}
      renderItem={({ item }) => (
        <View style={estilos.item}>
          <View style={estilos.itemTopo}>
            <Text style={estilos.nome}>{item.nome}</Text>
            <Text style={estilos.area}>{numero(item.area_hectare, 2)} ha</Text>
          </View>
          <View style={estilos.etiquetas}>
            <Text style={estilos.etiqueta}>
              {item.cultura_nome ?? 'Sem cultura'}
            </Text>
            {item.tipo_solo ? (
              <Text style={estilos.etiqueta}>{item.tipo_solo}</Text>
            ) : null}
          </View>
          {item.propriedade_nome ? (
            <Text style={estilos.propriedade}>{item.propriedade_nome}</Text>
          ) : null}
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
  area: { fontSize: 14, fontWeight: '600', color: cores.primariaEscura },
  etiquetas: { flexDirection: 'row', flexWrap: 'wrap', marginTop: 8 },
  etiqueta: {
    fontSize: 11,
    color: cores.primariaEscura,
    backgroundColor: cores.primariaClara,
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 10,
    marginRight: 6,
    marginTop: 4,
    overflow: 'hidden',
  },
  propriedade: { fontSize: 11, color: cores.textoSuave, marginTop: 8 },
});
