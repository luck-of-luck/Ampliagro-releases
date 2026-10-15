import React from 'react';
import {
  ActivityIndicator,
  StyleSheet,
  Text,
  View,
  type StyleProp,
  type ViewStyle,
} from 'react-native';

import { cores } from './tema';

export function Cartao({
  titulo,
  children,
  estilo,
}: {
  titulo?: string;
  children: React.ReactNode;
  estilo?: StyleProp<ViewStyle>;
}) {
  return (
    <View style={[estilos.cartao, estilo]}>
      {titulo ? <Text style={estilos.cartaoTitulo}>{titulo}</Text> : null}
      {children}
    </View>
  );
}

export function Indicador({
  rotulo,
  valor,
  detalhe,
  cor,
}: {
  rotulo: string;
  valor: string;
  detalhe?: string;
  cor?: string;
}) {
  return (
    <View style={estilos.indicador}>
      <Text style={estilos.indicadorRotulo} numberOfLines={1}>
        {rotulo}
      </Text>
      <Text style={[estilos.indicadorValor, cor ? { color: cor } : null]}>
        {valor}
      </Text>
      {detalhe ? (
        <Text style={estilos.indicadorDetalhe} numberOfLines={2}>
          {detalhe}
        </Text>
      ) : null}
    </View>
  );
}

export function Linha({ rotulo, valor }: { rotulo: string; valor: string }) {
  return (
    <View style={estilos.linha}>
      <Text style={estilos.linhaRotulo} numberOfLines={1}>
        {rotulo}
      </Text>
      <Text style={estilos.linhaValor}>{valor}</Text>
    </View>
  );
}

export function Carregando({ texto = 'A carregar…' }: { texto?: string }) {
  return (
    <View style={estilos.estado}>
      <ActivityIndicator size="large" color={cores.primaria} />
      <Text style={estilos.estadoTexto}>{texto}</Text>
    </View>
  );
}

export function Aviso({
  mensagem,
  aoTentarNovamente,
}: {
  mensagem: string;
  aoTentarNovamente?: () => void;
}) {
  return (
    <View style={estilos.estado}>
      <Text style={estilos.estadoErro}>{mensagem}</Text>
      {aoTentarNovamente ? (
        <Text style={estilos.acao} onPress={aoTentarNovamente}>
          Tentar de novo
        </Text>
      ) : null}
    </View>
  );
}

export function Vazio({
  mensagem = 'Nada por aqui ainda.',
}: {
  mensagem?: string;
}) {
  return (
    <View style={estilos.estado}>
      <Text style={estilos.estadoTexto}>{mensagem}</Text>
    </View>
  );
}

const estilos = StyleSheet.create({
  cartao: {
    backgroundColor: cores.superficie,
    borderRadius: 14,
    padding: 16,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: cores.borda,
  },
  cartaoTitulo: {
    fontSize: 13,
    fontWeight: '700',
    color: cores.textoSuave,
    letterSpacing: 0.6,
    textTransform: 'uppercase',
    marginBottom: 12,
  },
  grade: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    marginHorizontal: -6,
  },
  indicador: {
    width: '50%',
    paddingHorizontal: 6,
    paddingVertical: 8,
  },
  indicadorRotulo: {
    fontSize: 12,
    color: cores.textoSuave,
  },
  indicadorValor: {
    fontSize: 22,
    fontWeight: '700',
    color: cores.texto,
    marginTop: 2,
  },
  indicadorDetalhe: {
    fontSize: 11,
    color: cores.textoSuave,
    marginTop: 2,
  },
  linha: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 7,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: cores.borda,
  },
  linhaRotulo: {
    fontSize: 14,
    color: cores.textoSuave,
    flexShrink: 1,
    marginRight: 12,
  },
  linhaValor: {
    fontSize: 14,
    fontWeight: '600',
    color: cores.texto,
  },
  estado: {
    padding: 28,
    alignItems: 'center',
    gap: 10,
  },
  estadoTexto: {
    fontSize: 14,
    color: cores.textoSuave,
    textAlign: 'center',
  },
  estadoErro: {
    fontSize: 14,
    color: cores.perigo,
    textAlign: 'center',
  },
  acao: {
    fontSize: 14,
    fontWeight: '700',
    color: cores.primaria,
  },
});
