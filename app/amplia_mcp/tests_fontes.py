"""As fontes medidas: de onde vem cada numero, e o que NAO tem numero.

O QUE ESTES TESTES TRAVAM
==========================
1. **Nenhum numero sem `fonte` e `quando`.** E' a regra que o painel
   violou quando anunciou "IoT: 4" com 8 dispositivos, e que a guia
   vegetal violou com "707 culturas" vindo de um config de 488.

2. **Um zero silencioso e' pior que um erro.** A primeira versao deste
   modulo tratou o `cultures-config.json` como uma lista, quando o topo e'
   um DICT com `groups`. Deu `entradas: 0` — e `len([])` nao falha, entao
   parececia uma medicao. Este teste falha se o config voltar a dar 0
   quando tem conteudo.

3. **Vazio nao e' zero.** Os campos sem um unico registo preenchido
   devolvem `null` com a razao. Um agente que leia isto tem de poder dizer
   ao produtor "isto nao esta preenchido" em vez de "sao zero".

4. **A forma do config e' a forma real.** Se o ficheiro mudar de
   `groups[].subgroups[].cultures[]` para outra coisa, o teste diz, em vez
   de o modulo devolver 0 em silencio.

O QUE ESTES TESTES NAO FAZEM
=============================
Nao medem a qualidade do dado. Nao decidem se 709 e' o numero certo de
culturas — so que o numero tem fonte, e que a fonte foi lida da forma que
o ficheiro realmente tem.
"""

import json
import pathlib
import unittest

from app.amplia_mcp.fontes import (
    CONFIG_CULTURAS,
    RAIZ,
    _culturas_do_config,
    catalogo_de_fontes,
    culturas,
    dados_do_usuario,
)


class FontesTemFonteTest(unittest.TestCase):
    def test_cada_bloco_traz_fonte_e_quando(self):
        cat = catalogo_de_fontes()
        for bloco in ("culturas", "campos_que_faltam"):
            self.assertIn(bloco, cat)
            item = cat[bloco]
            if item is None:
                continue
            self.assertIn("fonte", item, f"{bloco} sem `fonte`")
            self.assertIn("quando", item, f"{bloco} sem `quando`")

    def test_a_comparacao_diz_qual_e_a_fonte_do_numero_da_tela(self):
        """709 e 488 nao sao o mesmo numero.

        O que a tela mostra vem da TABELA. O config e' a projecao. Um
        agente que responda "sao 488 culturas" quando a tela diz 709 esta a
        dar um numero que existe e nao e' o que o produtor ve.
        """
        c = culturas()
        comp = c.get("comparacao")
        if comp is None:
            self.skipTest("a comparacao nao foi medida neste ambiente")
        self.assertIn("leitura", comp)
        self.assertIn("TABELA", comp["leitura"])

    def test_os_dois_numeros_de_cultura_vem_presentes(self):
        c = culturas()
        if c.get("tabela"):
            self.assertIn("linhas", c["tabela"])
        if c.get("config"):
            self.assertIn("entradas", c["config"])
            self.assertIn("nomes_distintos", c["config"])


class ZeroSilenciosoTest(unittest.TestCase):
    """A forma do config e' a forma REAL — nao uma lista."""

    def setUp(self):
        self.cfg = RAIZ / CONFIG_CULTURAS

    def test_a_forma_do_config(self):
        if not self.cfg.exists():
            self.skipTest("o config nao existe neste checkout")
        dados = json.loads(self.cfg.read_text(encoding="utf-8"))
        self.assertIsInstance(
            dados,
            dict,
            "o topo do config deixou de ser um dict. Se mudou, "
            "`_culturas_do_config` precisa de mudar tambem — e este "
            "teste existe para o dizer em vez de deixar o modulo devolver "
            "zero.",
        )
        self.assertIn("groups", dados)

    def test_o_config_nao_devolve_zero(self):
        """O teste que teria apanhado o meu erro.

        A primeira versao tratou o topo como lista e devolveu
        `entradas: 0`. `len([])` nao levanta — devolveu um numero que
        PARECIA uma medicao. Este teste falha se o config tiver conteudo
        e o modulo reportar zero.
        """
        if not self.cfg.exists():
            self.skipTest("o config nao existe neste checkout")
        bruto = self.cfg.read_text(encoding="utf-8")
        self.assertGreater(
            len(bruto),
            1000,
            "o config esta praticamente vazio; a medicao de zero seria "
            "correcta e o teste na diria nada",
        )
        dados = _culturas_do_config(self.cfg)
        self.assertGreater(
            len(dados["_listas"]),
            0,
            "`_culturas_do_config` devolveu zero culturas de um ficheiro com "
            f"{len(bruto)} bytes. Zero silencioso e' pior que erro: parece "
            "uma medicao.",
        )

    def test_a_forma_esta_declarada_no_retorno(self):
        """Quem lê precisa de saber de que forma foi lido."""
        if not self.cfg.exists():
            self.skipTest("o config nao existe neste checkout")
        dados = _culturas_do_config(self.cfg)
        self.assertEqual(dados["_forma"], "groups[].subgroups[].cultures[]")


class VazioNaoEZeroTest(unittest.TestCase):
    def test_os_campos_sem_ponto_vem_null(self):
        cat = catalogo_de_fontes()
        campos = cat.get("campos_que_faltam", {})
        if campos is None or "campos" not in campos:
            self.skipTest("os campos nao foram medidos neste ambiente")
        for nome, item in campos["campos"].items():
            if "preenchidos" in item:
                self.assertIsNone(
                    item["valor"],
                    f"{nome} tem {item['preenchidos']} preenchidos e mesmo assim "
                    "devolveu um valor. Vazio nao e' zero.",
                )
                self.assertIn(
                    "porque",
                    item,
                    f"{nome} diz que esta vazio sem dizer PORQUE. O agente nao "
                    "sabe o que dizer ao produtor.",
                )

    def test_a_regra_do_teto(self):
        """O recurso tem de dizer a regra, nao so os factos."""
        cat = catalogo_de_fontes()
        regras = [
            v
            for v in (cat.get("campos_que_faltam") or {},)
            if isinstance(v, dict) and "regra" in v
        ]
        self.assertTrue(
            regras,
            "`campos_que_faltam` devia trazer a regra do topo. Um agente "
            "que so veja os factos pode concluir que zero e' um valor.",
        )


class DadosDoUsuarioTest(unittest.TestCase):
    def test_avisa_que_os_numeros_sao_de_uma_pessoa(self):
        """O numero de safras de um produtor nao e' o numero do sistema."""
        u = dados_do_usuario()
        if "erro" in u and u.get("erro"):
            self.skipTest("Django nao carregou neste ambiente")
        self.assertIn("aviso", u)
        self.assertIn("utilizador", str(u.get("aviso", "")).lower())

    def test_diz_como_contou(self):
        """`user_id` ou `propriedade_id` — a escolha muda o numero.

        MEDIDO: `app_safra` e `app_device` nao tem `user_id`. Filtrar por
        `user_id` dava `null`; o certo e ir por `propriedade_id`. O
        modulo tem de dizer qual usou, para se poder conferir.
        """
        u = dados_do_usuario()
        if "erro" in u and u.get("erro"):
            self.skipTest("Django nao carregou neste ambiente")
        como = u.get("como_contou")
        if como is None:
            return  # nenhuma tabela foi contavel neste ambiente
        for tabela, via in como.items():
            self.assertIn(
                via,
                ("user_id", "propriedade_id"),
                f"{tabela} foi contada por {via!r}, que nao e' nenhuma via "
                "conhecida. Um numero sem via declarada nao se pode "
                "conferir.",
            )


if __name__ == "__main__":
    unittest.main()
