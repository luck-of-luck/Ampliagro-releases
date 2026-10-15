import React, { useState } from 'react';
import {
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';

import { entrar, entrarComoDemo, URL_PADRAO } from '../api';
import { cores } from '../tema';

export default function Login({
  aoEntrar,
}: {
  aoEntrar: (base: string) => void;
}) {
  const [base, setBase] = useState(URL_PADRAO);
  const [usuario, setUsuario] = useState('');
  const [senha, setSenha] = useState('');
  const [tipoAcesso, setTipoAcesso] = useState<'produtor' | 'servidor'>(
    'produtor',
  );
  const [fazenda, setFazenda] = useState('');
  const [erro, setErro] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState(false);

  async function submeter() {
    setOcupado(true);
    setErro(null);
    try {
      const resultado = await entrar(
        base.trim(),
        usuario.trim(),
        senha,
        tipoAcesso,
        fazenda.trim(),
      );
      if (resultado.ok) {
        aoEntrar(base.trim());
      } else {
        setErro(resultado.erro);
      }
    } catch (e) {
      setErro(e instanceof Error ? e.message : String(e));
    } finally {
      setOcupado(false);
    }
  }

  async function usarDemo() {
    setOcupado(true);
    setErro(null);
    try {
      const resultado = await entrarComoDemo(base.trim());
      if (resultado.ok) {
        aoEntrar(base.trim());
      } else {
        setErro(resultado.erro);
      }
    } finally {
      setOcupado(false);
    }
  }

  const podeEntrar = usuario.trim().length > 0 && senha.length > 0 && !ocupado;

  return (
    <KeyboardAvoidingView
      style={estilos.fundo}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
    >
      <ScrollView
        contentContainerStyle={estilos.conteudo}
        keyboardShouldPersistTaps="handled"
      >
        <View style={estilos.marca}>
          <Text style={estilos.marcaNome}>Ampliagro</Text>
          <Text style={estilos.marcaSub}>Gestão agrícola no campo</Text>
        </View>

        <Text style={estilos.rotulo}>Servidor</Text>
        <TextInput
          style={estilos.campo}
          value={base}
          onChangeText={setBase}
          autoCapitalize="none"
          autoCorrect={false}
          keyboardType="url"
          placeholder="http://10.0.2.2:8000"
          placeholderTextColor={cores.textoSuave}
        />

        <View style={estilos.separador} />

        <Text style={estilos.rotulo}>Tipo de acesso</Text>
        <View style={estilos.conector}>
          {(['produtor', 'servidor'] as const).map(opcao => (
            <TouchableOpacity
              key={opcao}
              style={[
                estilos.conectorBotao,
                tipoAcesso === opcao ? estilos.conectorBotaoAtivo : null,
              ]}
              onPress={() => setTipoAcesso(opcao)}
            >
              <Text
                style={[
                  estilos.conectorTexto,
                  tipoAcesso === opcao ? estilos.conectorTextoAtivo : null,
                ]}
              >
                {opcao === 'produtor' ? 'Produtor' : 'Servidor'}
              </Text>
            </TouchableOpacity>
          ))}
        </View>

        {tipoAcesso === 'servidor' ? (
          <>
            <Text style={estilos.rotulo}>Nome da fazenda</Text>
            <TextInput
              style={estilos.campo}
              value={fazenda}
              onChangeText={setFazenda}
              placeholder="Fazenda que te cadastrou"
              placeholderTextColor={cores.textoSuave}
            />
          </>
        ) : null}

        <Text style={estilos.rotulo}>Usuário</Text>
        <TextInput
          style={estilos.campo}
          value={usuario}
          onChangeText={setUsuario}
          autoCapitalize="none"
          autoCorrect={false}
          placeholder="seu usuário"
          placeholderTextColor={cores.textoSuave}
        />

        <Text style={estilos.rotulo}>Senha</Text>
        <TextInput
          style={estilos.campo}
          value={senha}
          onChangeText={setSenha}
          secureTextEntry
          placeholder="sua senha"
          placeholderTextColor={cores.textoSuave}
        />

        {erro ? <Text style={estilos.erro}>{erro}</Text> : null}

        <TouchableOpacity
          style={[estilos.botao, !podeEntrar ? estilos.botaoDesligado : null]}
          onPress={submeter}
          disabled={!podeEntrar}
        >
          <Text style={estilos.botaoTexto}>
            {ocupado ? 'A entrar…' : 'Entrar'}
          </Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={estilos.link}
          onPress={usarDemo}
          disabled={ocupado}
        >
          <Text style={estilos.linkTexto}>Entrar como demonstração</Text>
        </TouchableOpacity>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const estilos = StyleSheet.create({
  fundo: { flex: 1, backgroundColor: cores.fundo },
  conteudo: { padding: 24, paddingTop: 56, paddingBottom: 40 },
  marca: { marginBottom: 32 },
  marcaNome: { fontSize: 30, fontWeight: '800', color: cores.primariaEscura },
  marcaSub: { fontSize: 14, color: cores.textoSuave, marginTop: 4 },
  rotulo: {
    fontSize: 12,
    fontWeight: '700',
    color: cores.textoSuave,
    marginBottom: 6,
    marginTop: 12,
    letterSpacing: 0.4,
  },
  campo: {
    backgroundColor: cores.superficie,
    borderWidth: 1,
    borderColor: cores.borda,
    borderRadius: 10,
    paddingHorizontal: 14,
    paddingVertical: 11,
    fontSize: 15,
    color: cores.texto,
  },
  separador: { height: 1, backgroundColor: cores.borda, marginVertical: 8 },
  conector: {
    flexDirection: 'row',
    backgroundColor: cores.borda,
    borderRadius: 10,
    padding: 3,
  },
  conectorBotao: {
    flex: 1,
    paddingVertical: 9,
    alignItems: 'center',
    borderRadius: 8,
  },
  conectorBotaoAtivo: { backgroundColor: cores.superficie },
  conectorTexto: { fontSize: 14, color: cores.textoSuave, fontWeight: '600' },
  conectorTextoAtivo: { color: cores.primariaEscura },
  erro: {
    marginTop: 16,
    color: cores.perigo,
    fontSize: 13,
    backgroundColor: cores.perigoClaro,
    padding: 12,
    borderRadius: 8,
  },
  botao: {
    marginTop: 24,
    backgroundColor: cores.primaria,
    borderRadius: 12,
    paddingVertical: 15,
    alignItems: 'center',
  },
  botaoDesligado: { backgroundColor: cores.textoSuave, opacity: 0.5 },
  botaoTexto: { color: '#FFFFFF', fontSize: 16, fontWeight: '700' },
  link: { marginTop: 18, alignItems: 'center' },
  linkTexto: { color: cores.primaria, fontSize: 13, fontWeight: '600' },
});
