import type {
  ItemEstoque,
  Pagina,
  Painel,
  PrevisaoClima,
  Safra,
  Talhao,
} from './tipos';

export const URL_PADRAO = 'http://10.0.2.2:8000';

export class ErroApi extends Error {
  readonly status: number;

  constructor(mensagem: string, status = 0) {
    super(mensagem);
    this.name = 'ErroApi';
    this.status = status;
  }
}

function semBarraFinal(url: string): string {
  return url.replace(/\/+$/, '');
}

type InitFetch = Record<string, unknown>;

function iniciar(init: InitFetch): Parameters<typeof fetch>[1] {
  return init as Parameters<typeof fetch>[1];
}

function csrfDoHeaderSetCookie(cabecalho: string | null): string | null {
  if (!cabecalho) {
    return null;
  }
  const casa = /csrftoken=([^;]+)/i.exec(cabecalho);
  return casa ? casa[1] : null;
}

async function obterCsrfToken(base: string): Promise<string | null> {
  const resposta = await fetch(`${base}/login/`, { credentials: 'include' });
  const bruto = await resposta.text();
  const doHeader = csrfDoHeaderSetCookie(
    resposta.headers.get('set-cookie') ?? resposta.headers.get('Set-Cookie'),
  );
  if (doHeader) {
    return doHeader;
  }
  const doCorpo = /name="csrfmiddlewaretoken" value="([^"]+)"/i.exec(bruto);
  return doCorpo ? doCorpo[1] : null;
}

type Opcoes = {
  metodo?: 'GET' | 'POST';
  corpo?: Record<string, string>;
  tokenCsrf?: string;
  redirecionar?: boolean;
};

async function pedir<T>(
  base: string,
  caminho: string,
  opcoes: Opcoes = {},
): Promise<T> {
  const { metodo = 'GET', corpo, tokenCsrf, redirecionar = false } = opcoes;
  const cabecalhos: Record<string, string> = { Accept: 'application/json' };
  if (corpo) {
    cabecalhos['Content-Type'] = 'application/x-www-form-urlencoded';
  }
  if (tokenCsrf) {
    cabecalhos['X-CSRFToken'] = tokenCsrf;
    cabecalhos['X-Requested-With'] = 'XMLHttpRequest';
  }

  let resposta: Response;
  try {
    resposta = await fetch(
      `${base}${caminho}`,
      iniciar({
        method: metodo,
        headers: cabecalhos,
        credentials: 'include',
        redirect: redirecionar ? 'follow' : 'manual',
        body: corpo
          ? Object.entries(corpo)
              .map(
                ([chave, valor]) =>
                  `${encodeURIComponent(chave)}=${encodeURIComponent(valor)}`,
              )
              .join('&')
          : undefined,
      }),
    );
  } catch (erro) {
    const detalhe = erro instanceof Error ? erro.message : String(erro);
    throw new ErroApi(
      `Não foi possível falar com ${base}. Verifique o endereço do servidor e se o Django está no ar. (${detalhe})`,
    );
  }

  if (resposta.status === 401 || resposta.status === 403) {
    const texto = await resposta.text().catch(() => '');
    const semSessao =
      resposta.status === 401 ||
      /sess[aã]o expirada|login|sess[aã]o/i.test(texto);
    if (semSessao && caminho !== '/login/') {
      throw new ErroApi('Sessão expirada. Entre novamente.', resposta.status);
    }
    throw new ErroApi('Usuário ou senha inválidos.', resposta.status);
  }

  if (!resposta.ok) {
    const texto = await resposta.text().catch(() => '');
    throw new ErroApi(
      `O servidor respondeu ${resposta.status}. ${texto.slice(0, 160)}`.trim(),
      resposta.status,
    );
  }

  if (resposta.status === 204) {
    return null as T;
  }

  const texto = await resposta.text();
  if (!texto) {
    return null as T;
  }
  try {
    return JSON.parse(texto) as T;
  } catch {
    throw new ErroApi('Resposta do servidor não é JSON válido.');
  }
}

function desempacotar<T>(payload: Pagina<T> | T[]): T[] {
  if (Array.isArray(payload)) {
    return payload;
  }
  if (payload && Array.isArray(payload.results)) {
    return payload.results;
  }
  return [];
}

export type ResultadoLogin = { ok: true } | { ok: false; erro: string };

export async function entrar(
  base: string,
  usuario: string,
  senha: string,
  tipoAcesso: 'produtor' | 'servidor',
  nomeFazenda: string,
): Promise<ResultadoLogin> {
  const raiz = semBarraFinal(base);
  let token: string | null = null;
  try {
    token = await obterCsrfToken(raiz);
  } catch {
    token = null;
  }

  const corpo: Record<string, string> = {
    acao: 'login',
    tipo_acesso: tipoAcesso,
    usuario,
    senha,
  };
  if (tipoAcesso === 'servidor') {
    corpo.nome_fazenda = nomeFazenda;
  }

  const resposta = await fetch(
    `${raiz}/login/`,
    iniciar({
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
        'X-Requested-With': 'XMLHttpRequest',
        ...(token ? { 'X-CSRFToken': token } : {}),
      },
      credentials: 'include',
      redirect: 'manual',
      body: Object.entries(corpo)
        .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`)
        .join('&'),
    }),
  );

  const texto = await resposta.text();

  if (resposta.status === 200) {
    if (/name="senha"/i.test(texto)) {
      return { ok: false, erro: 'Usuário ou senha inválidos.' };
    }
    if (texto.trim() === '' || /erro|inv[aá]lid/i.test(texto.slice(0, 400))) {
      return {
        ok: false,
        erro: texto
          .replace(/<[^>]+>/g, ' ')
          .trim()
          .slice(0, 200),
      };
    }
    return { ok: true };
  }

  if (resposta.status === 302 || resposta.status === 301) {
    return { ok: true };
  }

  if (resposta.status === 403) {
    return {
      ok: false,
      erro: token
        ? 'O servidor recusou o login (403).'
        : 'Não foi possível obter o token CSRF. O servidor exige HTTPS ou cookie SameSite=None.',
    };
  }

  return { ok: false, erro: `Login falhou com HTTP ${resposta.status}.` };
}

export async function entrarComoDemo(base: string): Promise<ResultadoLogin> {
  const raiz = semBarraFinal(base);
  try {
    const resposta = await fetch(
      `${raiz}/demo/`,
      iniciar({ credentials: 'include', redirect: 'manual' }),
    );
    return resposta.status >= 200 && resposta.status < 400
      ? { ok: true }
      : {
          ok: false,
          erro: `Sessão demo indisponível (HTTP ${resposta.status}).`,
        };
  } catch (erro) {
    return {
      ok: false,
      erro: erro instanceof Error ? erro.message : String(erro),
    };
  }
}

export async function sair(base: string): Promise<void> {
  try {
    await pedir(raizDe(base), '/logout/', { metodo: 'POST' });
  } catch {
    return;
  }
}

function raizDe(base: string): string {
  return semBarraFinal(base);
}

export async function buscarPainel(base: string): Promise<Painel> {
  return pedir<Painel>(raizDe(base), '/api/dashboard/');
}

export async function buscarTalhoes(base: string): Promise<Talhao[]> {
  return desempacotar(
    await pedir<Pagina<Talhao>>(raizDe(base), '/api/talhoes/'),
  );
}

export async function buscarSafras(base: string): Promise<Safra[]> {
  return desempacotar(await pedir<Pagina<Safra>>(raizDe(base), '/api/safras/'));
}

export async function buscarEstoque(base: string): Promise<ItemEstoque[]> {
  return desempacotar(
    await pedir<Pagina<ItemEstoque>>(raizDe(base), '/api/estoque/'),
  );
}

export async function buscarClima(base: string): Promise<PrevisaoClima> {
  return pedir<PrevisaoClima>(raizDe(base), '/api/previsao-clima/');
}
