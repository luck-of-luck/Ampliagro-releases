import { useCallback, useEffect, useState } from 'react';

import { ErroApi } from './api';

type Estado<T> = {
  dados: T | null;
  carregando: boolean;
  erro: string | null;
  recarregar: () => void;
};

export function useRecurso<T>(
  carregar: () => Promise<T>,
  dependencias: ReadonlyArray<unknown>,
): Estado<T> {
  const [dados, setDados] = useState<T | null>(null);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState<string | null>(null);
  const [tentativa, setTentativa] = useState(0);

  useEffect(() => {
    let vivo = true;
    setCarregando(true);
    setErro(null);
    carregar()
      .then(valor => {
        if (vivo) {
          setDados(valor);
        }
      })
      .catch((e: unknown) => {
        if (vivo) {
          setErro(e instanceof Error ? e.message : String(e));
        }
      })
      .finally(() => {
        if (vivo) {
          setCarregando(false);
        }
      });
    return () => {
      vivo = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...dependencias, tentativa]);

  return {
    dados,
    carregando,
    erro,
    recarregar: useCallback(() => setTentativa(n => n + 1), []),
  };
}
