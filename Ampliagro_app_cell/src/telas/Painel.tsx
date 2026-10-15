import React, { useCallback } from 'react';
import {
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';

import { buscarPainel } from '../api';
import { Aviso, Carregando, Cartao, Indicador, Linha } from '../componentes';
import { cores, corDoNivel, dataCurta, moeda, numero } from '../tema';
import { useRecurso } from '../useRecurso';

export default function Painel({ base }: { base: string }) {
  const carregar = useCallback(() => buscarPainel(base), [base]);
  const { dados, carregando, erro, recarregar } = useRecurso(carregar, [base]);

  if (carregando && !dados) {
    return <Carregando texto="A carregar o painel…" />;
  }
  if (erro) {
    return <Aviso mensagem={erro} aoTentarNovamente={recarregar} />;
  }
  if (!dados) {
    return null;
  }

  if (dados.sem_propriedade) {
    return (
      <View style={estilos.centro}>
        <Text style={estilos.semPropriedadeTitulo}>Sem propriedade</Text>
        <Text style={estilos.semPropriedadeTexto}>
          Esta conta ainda não tem nenhuma fazenda cadastrada. Cadastre a
          propriedade no Ampliagro para ver o painel.
        </Text>
      </View>
    );
  }

  const resumo = dados.resumo;
  const financeiro = dados.financeiro;
  const previsao = dados.clima?.previsao ?? [];
  const alertas = dados.alertas_list ?? [];

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
      {dados.propriedade?.nome ? (
        <Text style={estilos.fazenda}>{dados.propriedade.nome}</Text>
      ) : null}

      <Cartao titulo="Clima agora">
        <View style={estilos.climaTopo}>
          <Text style={estilos.climaTemp}>
            {dados.temperatura !== null && dados.temperatura !== undefined
              ? `${dados.temperatura}°`
              : '—'}
          </Text>
          <View style={estilos.climaInfo}>
            <Text style={estilos.climaDesc}>
              {dados.clima_descricao ?? '—'}
            </Text>
            <Text style={estilos.climaMeta}>
              {dados.clima?.cidade ?? 'localização desconhecida'}
            </Text>
            {dados.umidade !== null && dados.umidade !== undefined ? (
              <Text style={estilos.climaMeta}>Humidade {dados.umidade}%</Text>
            ) : null}
          </View>
        </View>
        {previsao.length > 0 ? (
          <View style={estilos.previsao}>
            {previsao.slice(0, 4).map(dia => (
              <View key={dia.dia} style={estilos.previsaoDia}>
                <Text style={estilos.previsaoRotulo}>{dia.dia}</Text>
                <Text style={estilos.previsaoTemp}>{numero(dia.temp, 0)}°</Text>
                <Text style={estilos.previsaoMin}>
                  {numero(dia.temp_min, 0)}°
                </Text>
                <Text style={estilos.previsaoChuva}>
                  {numero(dia.chuva_prob)}%
                </Text>
              </View>
            ))}
          </View>
        ) : null}
        {dados.clima_fonte ? (
          <Text style={estilos.rodape}>Fonte: {dados.clima_fonte}</Text>
        ) : null}
      </Cartao>

      <Cartao titulo="Indicadores">
        <View style={estilos.grade}>
          <Indicador
            rotulo="Área total"
            valor={dados.area_medida ? `${numero(dados.area_total)} ha` : '—'}
            detalhe={dados.area_medida ? 'medida' : 'sem área declarada'}
          />
          <Indicador
            rotulo="ROI"
            valor={numero(dados.roi, 1)}
            detalhe="retorno sobre investimento"
          />
          <Indicador
            rotulo="Custo por hectare"
            valor={moeda(dados.custo_ha)}
            detalhe={dados.custo_ha_periodo ?? undefined}
          />
          <Indicador
            rotulo="Alertas"
            valor={numero(dados.alertas)}
            detalhe={`${numero(dados.os_pendentes)} ordens abertas`}
            cor={dados.alertas ? cores.perigo : cores.texto}
          />
        </View>
      </Cartao>

      {financeiro ? (
        <Cartao titulo="Financeiro do ano">
          <Linha rotulo="Receitas" valor={moeda(financeiro.total_receitas)} />
          <Linha rotulo="Despesas" valor={moeda(financeiro.total_despesas)} />
          <Linha rotulo="Saldo" valor={moeda(financeiro.saldo)} />
          <Linha
            rotulo="Lançamentos"
            valor={numero(financeiro.total_lancamentos)}
          />
        </Cartao>
      ) : null}

      {resumo ? (
        <Cartao titulo="Fazenda">
          <Linha rotulo="Talhões" valor={numero(resumo.total_talhoes)} />
          <Linha
            rotulo="Funcionários"
            valor={numero(resumo.total_funcionarios)}
          />
          <Linha
            rotulo="Maquinários"
            valor={numero(resumo.total_maquinarios)}
          />
          <Linha rotulo="Animais" valor={numero(resumo.total_animais)} />
        </Cartao>
      ) : null}

      {alertas.length > 0 ? (
        <Cartao titulo={`Alertas (${alertas.length})`}>
          {alertas.map((alerta, indice) => {
            const paleta = corDoNivel(alerta.nivel);
            return (
              <View
                key={`${alerta.tipo}-${alerta.data ?? indice}`}
                style={estilos.alerta}
              >
                <View
                  style={[
                    estilos.alertaMarca,
                    { backgroundColor: paleta.fundo },
                  ]}
                >
                  <Text style={[estilos.alertaNivel, { color: paleta.texto }]}>
                    {alerta.nivel === 'critical'
                      ? 'CRÍTICO'
                      : alerta.nivel === 'warning'
                        ? 'ATENÇÃO'
                        : 'INFO'}
                  </Text>
                </View>
                <View style={estilos.alertaCorpo}>
                  <Text style={estilos.alertaMsg}>{alerta.msg}</Text>
                  {alerta.data ? (
                    <Text style={estilos.alertaData}>
                      {dataCurta(alerta.data)}
                    </Text>
                  ) : null}
                </View>
              </View>
            );
          })}
        </Cartao>
      ) : null}
    </ScrollView>
  );
}

const estilos = StyleSheet.create({
  scroll: { flex: 1, backgroundColor: cores.fundo },
  conteudo: { padding: 14, paddingBottom: 32 },
  fazenda: {
    fontSize: 13,
    color: cores.textoSuave,
    marginBottom: 10,
    fontWeight: '600',
  },
  climaTopo: { flexDirection: 'row', alignItems: 'center' },
  climaTemp: { fontSize: 42, fontWeight: '800', color: cores.texto },
  climaInfo: { marginLeft: 16, flex: 1 },
  climaDesc: { fontSize: 16, fontWeight: '600', color: cores.texto },
  climaMeta: { fontSize: 12, color: cores.textoSuave, marginTop: 2 },
  previsao: {
    flexDirection: 'row',
    marginTop: 16,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: cores.borda,
    paddingTop: 12,
  },
  previsaoDia: { flex: 1, alignItems: 'center' },
  previsaoRotulo: { fontSize: 11, color: cores.textoSuave },
  previsaoTemp: {
    fontSize: 16,
    fontWeight: '700',
    color: cores.texto,
    marginTop: 4,
  },
  previsaoMin: { fontSize: 12, color: cores.textoSuave },
  previsaoChuva: { fontSize: 11, color: cores.info, marginTop: 4 },
  rodape: { fontSize: 11, color: cores.textoSuave, marginTop: 10 },
  grade: { flexDirection: 'row', flexWrap: 'wrap', marginHorizontal: -6 },
  alerta: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 9,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: cores.borda,
  },
  alertaMarca: {
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 6,
    marginRight: 10,
  },
  alertaNivel: { fontSize: 10, fontWeight: '800' },
  alertaCorpo: { flex: 1 },
  alertaMsg: { fontSize: 13, color: cores.texto },
  alertaData: { fontSize: 11, color: cores.textoSuave, marginTop: 2 },
  centro: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: 32,
  },
  semPropriedadeTitulo: { fontSize: 20, fontWeight: '700', color: cores.texto },
  semPropriedadeTexto: {
    fontSize: 14,
    color: cores.textoSuave,
    textAlign: 'center',
    marginTop: 10,
    lineHeight: 20,
  },
});
