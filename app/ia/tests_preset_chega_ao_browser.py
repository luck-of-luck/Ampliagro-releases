"""O preset que a IA grava chega a ser DESENHADO? Uma pergunta que os testes
anteriores nao faziam.

O QUE ESTE FICHEIRO MEDIU, E O QUE DESCOBRIU
==============================================
Escrivi a Fase 2 toda a provar que o servidor GRAVA bem. Nao escrevi um teste
que provasse que o NAVEGADOR DESENHA. A diferenca nao e' academica: e' a
diferenca entre uma feature e um registo na base de dados.

MEDIDO, a 2026-10-09, neste repositorio:

1. `PresetPalco.estrutura` e' escrita em tres sItios (`palco_clonar`,
   `palco_presets.gravar`, `chamado_intents`) e **LIDA em nenhum**. Uma pesquisa
   por `.estrutura` no codigo de producao devolve so escritas.

2. O unico payload que leva presets ao browser e' `meus_presets`, em
   `palco_info` — e devolve `slug`, `nome` e `fixado`. **Nao a `estrutura`.**

3. `meus_presets` nao e' lido por nenhum JavaScript. O dashboard compoe presets
   a partir de `window.PRESETS` (`pagina-index.js:2698`), que e' estrutura do
   cliente, e o widget-bar le `window.PRESETS[presetKey]` — nao o banco.

Conclusao: um preset guardado pela IA — ou pelo botao "Salvar como meu
Dashboard", que usa o MESMO caminho — **aparece por nome e nao desenha**.

ISTO E' PRE-EXISTENTE E NAO E' MEU
==================================
O mesmo vale para `palco_clonar`, que ja existia e produz a mesma forma de
`estrutura`. Este ficheiro nao acusa a Fase 2 de inventar o problema: acusa a
Fase 2 de o **ter herdado**. E' a razao pela qual o teste seguinte mede o
sistema inteiro, e nao so' a minha parte.

O QUE ESTE TESTE FAZ
====================
Marca o que o produto promete com um preset guardado. enquanto o servidor
guarda e o browser nao desenha, o produtor ve um botao que funciona e um menu
que nao muda. Este teste e' a prova de que esse dia chegou.

Ver `docs/PLANO_WIDGET_DINAMICO.md` e a promessa de que "guardar esta tela" e'
util. Sem o ultimo elo, a Fase 2 e' um registo.
"""

import io
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]


class OPresetChegaAoBrowserTest(unittest.TestCase):
    """A ultima ligacao: do preset gravado ao ecrã do produtor."""

    def test_meus_presets_e_lido_por_algum_javascript(self):
        """`palco_info` envia `meus_presets`; alguem tem de o ler.

        MEDIDO: nao ha ninguem. E' este o teste que falha hoje, e tem de
        falhar enquanto a feature nao estiver fechada.
        """
        alvo = RAIZ / "app" / "static" / "js"
        ficheiros = list(alvo.rglob("*.js")) + list(alvo.rglob("*.cjs"))
        consumidores = [
            f
            for f in ficheiros
            if "meus_presets" in f.read_text(encoding="utf-8", errors="ignore")
        ]
        self.assertTrue(
            consumidores,
            "O SERVIDOR ENTREGA `meus_presets` E NINGUEM LE. Um preset "
            "guardado aparece por nome e nao desenha.",
        )

    def test_a_estrutura_do_preset_viaja_para_o_cliente(self):
        """A `estrutura` (a composicao de widgets) tem de chegar ao browser.

        O que a IA grava e' um layout; sem ele no cliente, o dashboard nao tem
        o que desenhar. E e' por isso que `meus_presets` vir so `slug/nome/
        fixado` nao chega.
        """
        alvo = RAIZ / "app" / "api" / "views" / "amplia_palco.py"
        texto = alvo.read_text(encoding="utf-8")
        bloco = texto[
            texto.index('"meus_presets"') : texto.index('"meus_presets"') + 320
        ]
        self.assertIn(
            "estrutura",
            bloco,
            "`meus_presets` nao leva a composicao — o cliente recebe um nome "
            "e nada para desenhar.",
        )
