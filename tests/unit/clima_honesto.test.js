/**
 * O clima no chat da AmplIA: o que o produtor lê tem de dizer de onde veio.
 *
 * O QUE ESTE TESTE TRAVA
 * ----------------------
 * Três defeitos que já existiram ao mesmo tempo, e que um teste de "a função
 * devolve uma string" não apanharia — porque todos devolvem uma string:
 *
 *  1. O servidor diz `fonte: "simulado"` quando não tem INMET nem chave, e o
 *     chat nunca lia essa palavra. O produtor recebia "temp: 28, Ensolarado"
 *     de uma fonte que ninguém mediu, com a forma de uma previsão.
 *  2. O ramo lia `temperatura_max`, `precipitacao`, `chuva`… e a resposta real
 *     é `{cidade, fonte, atual, previsao}`. Nenhum desses campos existe, e
 *     `previsao` é uma LISTA — logo `partes` ficava vazio e a função devolvia
 *     um despejo de JSON cru. Um produtor lia `[dia:Hoje,temp:26,...]`.
 *  3. Ausência e zero tinham de ser coisas diferentes. `null` é "a fonte não
 *     disse"; `0` é um número. Trocá-los transforma uma falta de dados numa
 *     medição — que foi exactamente o que o `or 25` fez no INMET.
 *
 * POR QUE EXTRAIR O RAMO EM VEZ DE IMPORTAR O FICHEIRO
 * ----------------------------------------------------
 * `ia-local.js` tem seis mil linhas e é um script de browser: importá-lo
 * puxa `window`, `document` e afins. O ramo do clima, esse, é uma função pura
 * sobre `data`. Extraí-lo e correr só essa parte testa o código que está em
 * produção — não uma cópia, não uma transcrição.
 *
 * O fixture do payload é a MESMA forma que `_get_real_weather` devolve nas
 * três fontes (INMET, OpenWeatherMap e o fallback). `tests/test_clima_
 * sem_invencao.py` fixa essa forma do lado do Python; este fixa o lado do
 * JavaScript. Se alguém mudar uma sem mudar a outra, um dos dois falha.
 */

import { describe, it, expect } from 'vitest';
import fs from 'fs';
import path from 'path';

const caminhoJS = path.resolve(__dirname, '../../app/static/js/ia-local/ia-local.js');

/** Extrai `if (recurso === 'clima' …)` e o fecha, contando chavetas. */
function extrairRamoClima() {
  const fonte = fs.readFileSync(caminhoJS, 'utf-8');
  const inicio = fonte.indexOf("if (recurso === 'clima'");
  if (inicio === -1) {
    throw new Error('ramo do clima não encontrado em ia-local.js — o nome do recurso mudou?');
  }
  let nivel = 0;
  let fim = -1;
  for (let i = inicio; i < fonte.length; i++) {
    if (fonte[i] === '{') nivel++;
    else if (fonte[i] === '}') {
      nivel--;
      if (nivel === 0) {
        fim = i + 1;
        break;
      }
    }
  }
  if (fim === -1) throw new Error('não consegui fechar o ramo do clima');
  return fonte.slice(inicio, fim);
}

/** Corre o ramo com os payloads de teste. */
function responderClima(data) {
  const corpo = `
    function formatarDadosNatural(recurso, data) {
      const fmtNum = (v, d = 0) => (v === null || v === undefined ? '—' : Number(v).toFixed(d));
      ${extrairRamoClima()}
      return '(o ramo não devolveu nada)';
    }
  `;
  const fn = new Function(`${corpo}; return formatarDadosNatural;`)();
  return fn('clima', data);
}

// A forma real, tal como `app/api/views/utils.py::_get_real_weather` a devolve.
const INMET = {
  cidade: 'Muzambinho/MG',
  fonte: 'inmet',
  atual: { dia: 'Hoje', icone: 'bi-sun', temp: 26, umidade: 71, descricao: 'Parcialmente nublado' },
  previsao: [
    { dia: 'Hoje', temp: 26, umidade: 71, descricao: 'Parcialmente nublado' },
    { dia: 'Amanhã', temp: 22, umidade: 80, descricao: 'Chuva' },
  ],
};

const OPENWEATHER = {
  cidade: 'Muzambinho/MG',
  fonte: 'openweathermap',
  atual: { dia: 'Hoje', temp: 25, umidade: 65, descricao: 'Ensolarado' },
  previsao: [{ dia: 'Hoje', temp: 25, umidade: 65, descricao: 'Ensolarado' }],
};

const SIMULADO = {
  cidade: 'Primavera do Leste/MT',
  fonte: 'simulado',
  atual: { dia: 'Hoje', icone: 'bi-sun', temp: 28, umidade: 65, descricao: 'Ensolarado' },
  previsao: [
    { dia: 'Hoje', temp: 28, umidade: 65, descricao: 'Ensolarado' },
    { dia: 'Amanhã', temp: 26, umidade: 70, descricao: 'Parcialmente nublado' },
  ],
};

describe('clima no chat da AmplIA', () => {
  describe('quando a fonte é medida', () => {
    it('diz a temperatura, a humidade e a descrição em português corrente', () => {
      const texto = responderClima(INMET);
      expect(texto).toContain('26');
      expect(texto).toContain('71');
      expect(texto).toContain('Parcialmente nublado');
    });

    it('diz de onde veio o número', () => {
      // Sem isto, o produtor não distingue uma medição de outra fonte.
      expect(responderClima(INMET)).toMatch(/fonte/i);
      expect(responderClima(OPENWEATHER)).toMatch(/fonte/i);
    });

    it('não devolve JSON cru', () => {
      // Este foi o defeito visível: `[dia:Hoje,temp:26,...]`
      for (const payload of [INMET, OPENWEATHER]) {
        const texto = responderClima(payload);
        expect(texto).not.toMatch(/\{"dia"/);
        expect(texto).not.toMatch(/\[dia:/);
        expect(texto).not.toContain('icone');
      }
    });

    it('menciona que há mais dias quando os há', () => {
      expect(responderClima(INMET)).toMatch(/dia(s)?\b/i);
    });
  });

  describe('quando a fonte é SIMULADA', () => {
    it('não apresenta o número inventado como previsão', () => {
      const texto = responderClima(SIMULADO);
      // O 28 do fallback nunca foi medido por ninguém nesta fazenda.
      expect(texto).not.toMatch(/28/);
      expect(texto).not.toMatch(/Ensolarado/);
    });

    it('diz que não tem previsão, e porquê', () => {
      const texto = responderClima(SIMULADO);
      expect(texto).toMatch(/não tenho previsão/i);
    });

    it('diz o que fazer em vez de desistir', () => {
      // Um "não sei" sem saída é um beco. O produtor tem de conseguir
      // resolver: é a estação meteorológica que falta.
      expect(responderClima(SIMULADO)).toMatch(/estação/i);
    });

    it('nunca devolve despejo de JSON', () => {
      expect(responderClima(SIMULADO)).not.toMatch(/\[dia:/);
    });
  });

  describe('quando a fonte calou', () => {
    it('diz "sem dado" em vez de mostrar 0', () => {
      // `null` é "não disse". Mostrar 0 seria fabricar uma medição.
      const calado = {
        cidade: 'Muzambinho/MG',
        fonte: 'inmet',
        atual: { dia: 'Hoje', temp: null, umidade: null, descricao: null },
        previsao: [],
      };
      const texto = responderClima(calado);
      expect(texto).toMatch(/sem dado|não tenho previsão que sirva/i);
      expect(texto).not.toMatch(/\b0\s*°C/);
      expect(texto).not.toMatch(/umidade 0%/);
    });

    it('diz que a fonte respondeu mas não serve para decidir', () => {
      const calado = {
        cidade: 'Muzambinho/MG',
        fonte: 'inmet',
        atual: { dia: 'Hoje', temp: null, umidade: null, descricao: null },
        previsao: [],
      };
      expect(responderClima(calado)).toMatch(/para decidir/i);
    });

    it('aceita só `atual`, sem `previsao`', () => {
      const soAtual = {
        cidade: 'X/MG',
        fonte: 'inmet',
        atual: { dia: 'Hoje', temp: 30, umidade: 55, descricao: 'Sol' },
      };
      const texto = responderClima(soAtual);
      expect(texto).toContain('30');
      expect(texto).not.toMatch(/\[dia:/);
    });

    it('não rebenta com um payload vazio', () => {
      expect(() => responderClima({})).not.toThrow();
      expect(() => responderClima(null)).not.toThrow();
      expect(() => responderClima({ previsao: [] })).not.toThrow();
    });
  });
});
