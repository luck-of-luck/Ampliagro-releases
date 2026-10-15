import React, { useCallback } from 'react';
import {
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';

import { buscarClima } from '../api';
import { Aviso, Carregando, Cartao, Linha } from '../componentes';
import { cores, numero } from '../tema';
import { useRecurso } from '../useRecurso';

function diaCurto(iso: string): string {
  const d = new Date(`${iso}T12:00:00`);
  if (Number.isNaN(d.getTime())) {
    return iso;
  }
  return d.toLocaleDateString('pt-BR', {
    weekday: 'short',
    day: '2-digit',
    timeZone: 'America/Sao_Paulo',
  });
}

export default function Clima({ base }: { base: string }) {
  const carregar = useCallback(() => buscarClima(base), [base]);
  const { dados, carregando, erro, recarregar } = useRecurso(carregar, [base]);

  if (carregando && !dados) {
    return <Carregando texto="A carregar previsão…" />;
  }
  if (erro) {
    return <Aviso mensagem={erro} aoTentarNovamente={recarregar} />;
  }
  if (!dados) {
    return null;
  }

  const { daily } = dados;

  return (
    <ScrollView
      style={estilos.scroll}
      contentContainerStyle={estilos.conteudo}
      refreshControl={
        <RefreshControl
          refreshing={carregando}
          onRefresh={recarregar}
          tintColor={cores.primaria}
        />
      }
    >
      <Cartao titulo="Previsão do período">
        {daily.time.map((iso, indice) => (
          <View
            key={iso}
            style={[estilos.dia, indice === 0 ? estilos.diaPrimeiro : null]}
          >
            <Text style={estilos.diaNome}>{diaCurto(iso)}</Text>
            <View style={estilos.diaNumeros}>
              <Text style={estilos.diaMax}>
                {numero(daily.temperature_2m_max[indice], 0)}°
              </Text>
              <Text style={estilos.diaMin}>
                {numero(daily.temperature_2m_min[indice], 0)}°
              </Text>
            </View>
            <Text style={estilos.diaChuva}>
              {numero(daily.precipitation_probability_max[indice])}% ·{' '}
              {numero(daily.precipitation_sum[indice], 1)} mm
            </Text>
          </View>
        ))}
      </Cartao>

      <Cartao titulo="Origem">
        <Linha rotulo="Fonte dos dados" valor={dados.fonte_dados ?? '—'} />
        <Linha rotulo="Coordenadas" valor={dados.fonte ?? '—'} />
        <Linha
          rotulo="Latitude"
          valor={
            dados.latitude !== null && dados.latitude !== undefined
              ? numero(dados.latitude, 4)
              : '—'
          }
        />
        <Linha
          rotulo="Longitude"
          valor={
            dados.longitude !== null && dados.longitude !== undefined
              ? numero(dados.longitude, 4)
              : '—'
          }
        />
        <Linha
          rotulo="Altitude"
          valor={
            dados.elevation !== null && dados.elevation !== undefined
              ? `${numero(dados.elevation)} m`
              : '—'
          }
        />
        <Linha rotulo="Capturado em" valor={dados.capturado_em ?? '—'} />
      </Cartao>
    </ScrollView>
  );
}

const estilos = StyleSheet.create({
  scroll: { flex: 1, backgroundColor: cores.fundo },
  conteudo: { padding: 14, paddingBottom: 32 },
  dia: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: 10,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: cores.borda,
  },
  diaPrimeiro: { borderBottomWidth: 0 },
  diaNome: { fontSize: 14, fontWeight: '600', color: cores.texto, width: 92 },
  diaNumeros: { flexDirection: 'row', alignItems: 'baseline', flex: 1 },
  diaMax: { fontSize: 17, fontWeight: '700', color: cores.texto, width: 46 },
  diaMin: { fontSize: 13, color: cores.textoSuave },
  diaChuva: { fontSize: 12, color: cores.info, fontWeight: '600' },
});
