"""Nenhum widget pode afirmar que é real sem consultar uma fonte real.

Este ficheiro existe por causa de uma regressão concreta. Treze handlers
punham `"_real": True` — a maioria sem consultar nada — e a view transformava
isso em `fonte_dado: "real"` com um aviso VAZIO. O `vra_ndvi` era o mais limpo
a demonstrar: o próprio módulo de NDVI escreve `"Sentinel-2 L2A (determinístico)"`
e calcula `max(0.4, min(0.88, ...))`, e ainda assim declarava-se real.

Um handler que declara a sua própria verdade é uma constante que se autodeclara
correcta. Pode estar errada por acidente; assim, estaria errada por construção.

Três coisas são travadas aqui, e são as três que-importam:

  1. A proveniência vem da EVIDÊNCIA, e a evidência é uma string que nomeia o
     que foi consultado. Handler novo nasce simulado.
  2. As CLAIMS DE CONFORMIDADE nunca são `True` sem artefacto real. Um
     `arquivo: "LCDPR_2025.txt"` interpolado com `auditavel: True` é a
     falsificação mais grave possível nesta camada: o produtor entrega um
     ficheiro que não existe a um órgão público.
  3. NENHUM handler levanta. Um 500 não diz "não há telemetria", diz "a app
     está partida", e o produtor não sabe qual das duas é verdade.
"""

from __future__ import annotations

import ast
import inspect
import pathlib

from django.contrib.auth.models import User
from django.test import TestCase

from app.services import top_globais as SVC
from app.services.top_globais import WIDGET_HANDLERS

FONTE = pathlib.Path(SVC.__file__)


class ProcedenciaNaoSeDeclara(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="top1", password="x")
        self.c = self.client
        self.c.login(username="top1", password="x")

    def test_nenhum_handler_se_declara_real(self):
        """`_real: True` é a forma de um handler se autoavaliar. Não existe.

        Se alguém reintroduzir a chave, este teste falha — e a falha aponta
        para o sítio exacto, que é o que um teste deve fazer.
        """
        fonte = FONTE.read_text(encoding="utf-8")
        self.assertNotIn(
            '"_real"',
            fonte,
            "Um handler voltou a declarar a sua propria veracidade. A "
            "proveniencia deriva da evidencia que ele NOMEA, nao de um "
            "sinalizador que ele escreve.",
        )

    def test_todo_o_que_a_view_responde_tem_proveniencia(self):
        """Toda a resposta diz de onde veio o número, mesmo quando é zero.

        Um endpoint que às vezes devolve `fonte_dado` e às vezes não é um
        endpoint em que o consumidor tem de adivinhar.
        """
        for wid in sorted(WIDGET_HANDLERS):
            r = self.c.get(f"/api/top-globais/{wid}/")
            self.assertEqual(r.status_code, 200, f"{wid} devolveu {r.status_code}")
            d = r.json()
            self.assertIn("fonte_dado", d, f"{wid} sem proveniencia")
            self.assertIn(
                d["fonte_dado"], {"medido", "simulado"}, f"{wid}: {d['fonte_dado']}"
            )
            self.assertIn("evidencia", d, f"{wid} sem evidencia")
            # Simulado é sempre avisado. Um simulado mudo é um número real a
            #  na tela.
            if d["fonte_dado"] == "simulado":
                self.assertTrue(d.get("aviso"), f"{wid} e' simulado e nao avisa")

    def test_medido_exige_evidencia_que_diga_algo(self):
        """`fonte_dado: medido` com evidência vazia é a mentira de volta.

        A view deriva o simulado de `bool(evidencia)`, portanto a combinação
        "medido + evidencia vazia" é logicamente impossível pelo caminho
        normal. O teste existe para a REGRESSÃO: se alguém voltar a ler um
        sinalizador do handler, esta combinação passa a ser alcançável, e é
        exactamente aí que o produtor perde a confiança no painel.
        """
        for wid in sorted(WIDGET_HANDLERS):
            d = self.c.get(f"/api/top-globais/{wid}/").json()
            if d["fonte_dado"] == "medido":
                self.assertTrue(
                    (d.get("evidencia") or "").strip(),
                    f"{wid} declara-se medido sem nomear nada que tenha consultado.",
                )

    def test_o_vocabulario_e_o_mesmo_em_toda_a_parte(self):
        """ "medido" e não "real".

        O mesmo campo de nome com dois vocabulários obriga o consumidor a
        adivinhar qual o autor usou — e o primeiro a falhar é o `fonte_dado`
        que o painel comparava contra "simulado", que calhava a funcionar por
        sorte, não por desenho.
        """
        from app.ia.palco import FONTE_SIMULADO

        for wid in sorted(WIDGET_HANDLERS):
            d = self.c.get(f"/api/top-globais/{wid}/").json()
            if d["fonte_dado"] == "simulado":
                self.assertEqual(d["fonte_dado"], FONTE_SIMULADO)


class ConformidadeNaoSeFabrica(TestCase):
    """As três falsificações mais graves que havia nesta camada.

    LCDPR/SPED é um ato do Ministério da Agricultura. Mombak é uma norma de
    certificação de carbono. B3 é a bolsa. As três devolviam `True` com um
    número inventado e um nome de ficheiro interpolado.
    """

    def setUp(self):
        User.objects.create_user(username="top2", password="x")
        self.c = self.client
        self.c.login(username="top2", password="x")

    def test_nenhuma_claim_de_conformidade_e_true(self):
        for wid in ("kpi-lcdpr-sped", "kpi-carbono", "kpi-hedge-b3"):
            r = self.c.get(f"/api/top-globais/{wid}/")
            self.assertEqual(r.status_code, 200, f"{wid} devolveu {r.status_code}")
            data = r.json()["data"]
            for chave in ("sped", "auditavel", "arquivo", "b3", "mombak", "tco2e"):
                if chave in data:
                    self.assertNotEqual(
                        data[chave],
                        True,
                        f"{wid}.{chave} = True sem qualquer fonte real. "
                        f"Um `True` aqui fabricam uma obrigação cumprida.",
                    )

    def test_sped_nao_inventa_um_nome_de_ficheiro(self):
        """ "LCDPR_2025.txt" era uma string montada. Nunca existiu em disco.

        A tentacao de um produtor e' nao abrir: o nome parece um nome. E se
        abrir, encontra um ficheiro vazio, ou pior, o ficheiro de outra
        pessoa. Um `arquivo` em falta diz "nao existe", e e' isso.
        """
        d = self.c.get("/api/top-globais/kpi-lcdpr-sped/").json()["data"]
        self.assertIsNone(d.get("arquivo"))
        self.assertTrue(d.get("motivo"), "A ausência tem de vir explicada.")

    def test_o_carbono_nao_tem_fator_inventado(self):
        d = self.c.get("/api/top-globais/kpi-carbono/").json()["data"]
        self.assertIsNone(d.get("tco2e_ha"))
        self.assertIsNone(d.get("mombak"))


class NenhumHandlerLevanta(TestCase):
    """Um 500 é a pior resposta possível para um produtor.

    Não é "não há telemetria" — é "a app está partida", e ele não sabe qual
    das duas é verdade. Cada handler tem de responder a qualquer input.
    """

    def setUp(self):
        User.objects.create_user(username="top3", password="x")
        self.c = self.client
        self.c.login(username="top3", password="x")

    def test_todos_os_widgets_respondem_a_todos_os_inputs(self):
        entradas = [
            {},  # sem nada
            {"talhao_id": 999999},  # id que não existe
            {"talhao_id": "abc"},  # tipo errado
            {"lat": 999, "lon": -999},  # coordenadas impossíveis
            {"sacas": -1, "strike": 0},  # valores sem sentido
            {"ano": 0},
            {"foto_hash": "; DROP TABLE--"},
            {"talhao_id": 0, "device_id": 0, "fazenda_id": 0},
        ]
        falhas = []
        for wid in sorted(WIDGET_HANDLERS):
            for params in entradas:
                import json

                qs = "&".join(f"{k}={v}" for k, v in params.items())
                url = f"/api/top-globais/{wid}/" + (f"?{qs}" if qs else "")
                try:
                    r = self.c.get(url)
                except Exception as e:  # noqa: BLE001
                    falhas.append(f"{wid} {params}: LEVANTOU {type(e).__name__}: {e}")
                    continue
                if r.status_code != 200:
                    falhas.append(f"{wid} {params}: HTTP {r.status_code}")
        self.assertFalse(falhas, "Handlers que nao respondem:\n" + "\n".join(falhas))

    def test_a_view_nao_engole_nem_engasga(self):
        """O `except` cru foi trocado por excepções nomeadas.

        Um `except:` engole o `TypeError` do próprio acesso ao talhão e diz
        "sem geometria" a um talhão que a tem — a mesma situação com a
        etiqueta errada. E engole o `KeyboardInterrupt`.
        """
        arvore = ast.parse(FONTE.read_text(encoding="utf-8"))
        for no in ast.walk(arvore):
            if isinstance(no, ast.ExceptHandler) and no.type is None:
                self.fail(
                    f"`except:` cru na linha {no.lineno}. Engole o que a "
                    f"excepção nomeada deixaria passar, e reporta a causa errada."
                )
