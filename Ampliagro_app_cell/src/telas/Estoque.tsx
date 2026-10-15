import React, { useCallback } from 'react';
import { FlatList, RefreshControl, StyleSheet, Text, View } from 'react-native';

import { buscarEstoque } from '../api';
import { Aviso, Carregando, Vazio } from '../componentes';
import { cores, dataCurta, numero } from '../tema';
import { useRecurso } from '../useRecurso';

export default function Estoque({ base }: { base: string }) {
  const carregar = useCallback(() => buscarEstoque(base), [base]);
  const { dados, carregando, erro, recarregar } = useRecurso(carregar, [base]);

  if (carregando && !dados) {
    return <Carregando texto="A carregar estoque…" />;
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
      ListEmptyComponent={<Vazio mensagem="Estoque vazio." />}
      renderItem={({ item }) => (
        <View style={estilos.item}>
          <View style={estilos.itemTopo}>
            <Text style={estilos.nome}>{item.nome}</Text>
            <Text style={estilos.quantidade}>
              {numero(item.quantidade, 2)} {item.unidade ?? ''}
            </Text>
          </View>
          <View style={estilos.rodape}>
            {item.categoria_display ? (
              <Text style={estilos.etiqueta}>{item.categoria_display}</Text>
            ) : null}
            {item.local ? (
              <Text style={estilos.local}>{item.local}</Text>
            ) : null}
            {item.data_validade ? (
              <Text style={estilos.validade}>
                Validade: {dataCurta(item.data_validade)}
              </Text>
            ) : null}
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
  quantidade: { fontSize: 14, fontWeight: '700', color: cores.primariaEscura },
  rodape: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    alignItems: 'center',
    marginTop: 8,
  },
  etiqueta: {
    fontSize: 11,
    color: cores.info,
    backgroundColor: cores.infoClaro,
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 10,
    marginRight: 8,
    overflow: 'hidden',
  },
  local: { fontSize: 11, color: cores.textoSuave, marginRight: 10 },
  validade: { fontSize: 11, color: cores.atencao, fontWeight: '600' },
});
