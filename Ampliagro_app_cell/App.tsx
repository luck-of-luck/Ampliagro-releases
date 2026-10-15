import React, { useState } from 'react';
import {
  StatusBar,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { SafeAreaProvider, SafeAreaView } from 'react-native-safe-area-context';

import { sair } from './src/api';
import Clima from './src/telas/Clima';
import Estoque from './src/telas/Estoque';
import Login from './src/telas/Login';
import Painel from './src/telas/Painel';
import Safras from './src/telas/Safras';
import Talhoes from './src/telas/Talhoes';
import { cores } from './src/tema';
import type { Aba } from './src/tipos';

const ABAS: Array<{ chave: Aba; rotulo: string }> = [
  { chave: 'painel', rotulo: 'Painel' },
  { chave: 'talhoes', rotulo: 'Talhões' },
  { chave: 'safras', rotulo: 'Safras' },
  { chave: 'estoque', rotulo: 'Estoque' },
  { chave: 'clima', rotulo: 'Clima' },
];

function Conteudo({ aba, base }: { aba: Aba; base: string }) {
  switch (aba) {
    case 'painel':
      return <Painel base={base} />;
    case 'talhoes':
      return <Talhoes base={base} />;
    case 'safras':
      return <Safras base={base} />;
    case 'estoque':
      return <Estoque base={base} />;
    case 'clima':
      return <Clima base={base} />;
  }
}

function App() {
  const [base, setBase] = useState<string | null>(null);
  const [aba, setAba] = useState<Aba>('painel');

  function terminarSessao() {
    if (base) {
      void sair(base);
    }
    setBase(null);
  }

  return (
    <SafeAreaProvider>
      <StatusBar barStyle="light-content" />
      <SafeAreaView style={estilos.raiz} edges={['top', 'bottom']}>
        {base === null ? (
          <Login aoEntrar={servidor => setBase(servidor)} />
        ) : (
          <View style={estilos.corpo}>
            <View style={estilos.topo}>
              <Text style={estilos.topoNome}>Ampliagro</Text>
              <TouchableOpacity onPress={terminarSessao}>
                <Text style={estilos.sair}>Sair</Text>
              </TouchableOpacity>
            </View>
            <View style={estilos.conteudo}>
              <Conteudo aba={aba} base={base} />
            </View>
            <View style={estilos.abas}>
              {ABAS.map(item => (
                <TouchableOpacity
                  key={item.chave}
                  style={estilos.aba}
                  onPress={() => setAba(item.chave)}
                >
                  <Text
                    style={[
                      estilos.abaTexto,
                      aba === item.chave ? estilos.abaTextoAtivo : null,
                    ]}
                  >
                    {item.rotulo}
                  </Text>
                </TouchableOpacity>
              ))}
            </View>
          </View>
        )}
      </SafeAreaView>
    </SafeAreaProvider>
  );
}

const estilos = StyleSheet.create({
  raiz: { flex: 1, backgroundColor: cores.fundo },
  corpo: { flex: 1 },
  topo: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: cores.primariaEscura,
    paddingHorizontal: 16,
    paddingVertical: 12,
  },
  topoNome: { color: '#FFFFFF', fontSize: 17, fontWeight: '800' },
  sair: { color: '#D8EFDF', fontSize: 13, fontWeight: '600' },
  conteudo: { flex: 1 },
  abas: {
    flexDirection: 'row',
    borderTopWidth: 1,
    borderTopColor: cores.borda,
    backgroundColor: cores.superficie,
  },
  aba: { flex: 1, paddingVertical: 12, alignItems: 'center' },
  abaTexto: { fontSize: 12, color: cores.textoSuave, fontWeight: '600' },
  abaTextoAtivo: { color: cores.primariaEscura, fontWeight: '800' },
});

export default App;
