export type Pagina<T> = {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
};

export type PrevDia = {
  dia: string;
  icone?: string | null;
  temp: number;
  temp_min?: number | null;
  umidade?: number | null;
  chuva_prob?: number | null;
  descricao?: string | null;
};

export type ClimaAtual = {
  dia?: string;
  icone?: string | null;
  temp?: number | null;
  umidade?: number | null;
  chuva_mm?: number | null;
  descricao?: string | null;
};

export type Alerta = {
  tipo: string;
  msg: string;
  icone?: string | null;
  nivel: 'critical' | 'warning' | 'info' | string;
  data?: string | null;
};

export type Painel = {
  sem_propriedade?: boolean;
  roi?: number | null;
  custo_ha?: number | null;
  despesa_ano?: number | null;
  custo_ha_periodo?: string | null;
  area_total?: number | null;
  area_medida?: boolean;
  alertas?: number | null;
  os_pendentes?: number | null;
  umidade?: number | null;
  temperatura?: number | null;
  clima_descricao?: string | null;
  clima_fonte?: string | null;
  clima?: {
    cidade?: string | null;
    fonte?: string | null;
    atual?: ClimaAtual | null;
    previsao?: PrevDia[] | null;
  } | null;
  alertas_list?: Alerta[] | null;
  resumo?: {
    total_talhoes?: number | null;
    total_funcionarios?: number | null;
    total_maquinarios?: number | null;
    total_animais?: number | null;
  } | null;
  financeiro?: {
    total_receitas?: number | null;
    total_despesas?: number | null;
    saldo?: number | null;
    total_lancamentos?: number | null;
  } | null;
  safras?: Array<{
    cultura?: string | null;
    area?: number | null;
    sacas?: number | null;
    ano?: number | null;
    propriedade?: string | null;
  }> | null;
  propriedade?: { nome?: string | null } | null;
};

export type Talhao = {
  id: number;
  nome: string;
  area_hectare: string | null;
  cultura_nome: string | null;
  tipo_solo: string | null;
  propriedade_nome: string | null;
  ativo?: boolean;
};

export type Safra = {
  id: number;
  safra_nome: string | null;
  ano: number | null;
  cultura_nome: string | null;
  talhao_nome: string | null;
  propriedade_nome: string | null;
  area_plantada: string | null;
  area_colhida: string | null;
  producao_total: string | null;
  produtividade: string | null;
  receita_estimada: string | null;
  data_plantio: string | null;
  data_colheita: string | null;
};

export type ItemEstoque = {
  id: number;
  nome: string;
  categoria_display: string | null;
  quantidade: string | null;
  unidade: string | null;
  local: string | null;
  propriedade_nome: string | null;
  data_validade: string | null;
};

export type PrevisaoClima = {
  latitude?: number | null;
  longitude?: number | null;
  elevation?: number | null;
  fonte?: string | null;
  fonte_dados?: string | null;
  capturado_em?: string | null;
  daily: {
    time: string[];
    temperature_2m_max: number[];
    temperature_2m_min: number[];
    precipitation_sum: number[];
    precipitation_probability_max: number[];
  };
};

export type Aba = 'painel' | 'talhoes' | 'safras' | 'estoque' | 'clima';
