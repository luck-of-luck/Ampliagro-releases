export const cores = {
  fundo: '#F4F7F4',
  superficie: '#FFFFFF',
  primaria: '#1B7A3D',
  primariaEscura: '#11572B',
  primariaClara: '#E6F4EA',
  texto: '#15241A',
  textoSuave: '#5C6B60',
  borda: '#DCE5DD',
  perigo: '#C0392B',
  perigoClaro: '#FBE9E7',
  atencao: '#B26A00',
  atencaoClaro: '#FDF3E3',
  info: '#1F6F8B',
  infoClaro: '#E4F1F5',
};

export function numero(
  valor: number | string | null | undefined,
  casas = 0,
): string {
  const n = typeof valor === 'string' ? Number(valor) : valor;
  if (n === null || n === undefined || Number.isNaN(n)) {
    return '—';
  }
  return n.toLocaleString('pt-BR', {
    minimumFractionDigits: casas,
    maximumFractionDigits: casas,
  });
}

export function moeda(valor: number | string | null | undefined): string {
  const n = typeof valor === 'string' ? Number(valor) : valor;
  if (n === null || n === undefined || Number.isNaN(n)) {
    return '—';
  }
  return `R$ ${n.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}`;
}

export function dataCurta(iso: string | null | undefined): string {
  if (!iso) {
    return '—';
  }
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) {
    return iso;
  }
  return d.toLocaleDateString('pt-BR', { timeZone: 'America/Sao_Paulo' });
}

export function corDoNivel(nivel: string | null | undefined): {
  texto: string;
  fundo: string;
} {
  switch (nivel) {
    case 'critical':
      return { texto: cores.perigo, fundo: cores.perigoClaro };
    case 'warning':
      return { texto: cores.atencao, fundo: cores.atencaoClaro };
    default:
      return { texto: cores.info, fundo: cores.infoClaro };
  }
}
