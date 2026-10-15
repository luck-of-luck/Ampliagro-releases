"""Guardas para a landing pública não voltar a vender número inventado."""

from __future__ import annotations

import re
from pathlib import Path

from django.test import SimpleTestCase
from django.urls import reverse

from app.guias.catalogo import CATALOGO, EXISTE, NAO_EXISTE, PARCIAL

RAIZ = Path(__file__).resolve().parents[1]
PITCH = RAIZ / "app" / "templates" / "pitch.html"


def _template() -> str:
    return PITCH.read_text(encoding="utf-8")


def _conta(estado: str) -> int:
    return sum(
        1 for classe in CATALOGO for item in classe["itens"] if item["estado"] == estado
    )


def _s(*partes: str) -> str:
    return "".join(partes)


class PitchHonestoTest(SimpleTestCase):
    def test_claims_sem_prova_nao_voltam(self):
        """A landing não pode voltar a vender prémio, hectares ou clientes demo."""
        texto = _template()
        proibidos = [
            _s("Vence", "dor JOSIF"),
            _s("Final", "ista FEBRACE"),
            _s("500", "+ mil"),
            _s("Grupo Agro", "Norte"),
            _s("Fazenda Santa ", "Luzia"),
            _s("Cooperativa Vale do ", "Rio"),
            _s("100", "+"),
            _s("1", "39"),
            _s("Pronto para ", "auditoria"),
            _s("Outros ", "(ERPs)"),
        ]
        achados = [p for p in proibidos if p in texto]
        self.assertEqual(achados, [], "claims sem prova voltaram ao pitch")

    def test_cards_do_pitch_vem_do_catalogo(self):
        """Os números do topo vêm do catálogo testado, não de texto escrito à mão."""
        texto = _template()
        inicio = texto.find('<div class="pitch-stats">')
        fim = texto.find("<!-- Features -->")
        self.assertNotEqual(inicio, -1, "não encontrei os cards de estatística")
        self.assertNotEqual(fim, -1, "não encontrei o fim dos cards de estatística")
        bloco = texto[inicio:fim]

        for variavel in ("n_catalogo", "n_existe", "n_parcial", "n_ausente"):
            self.assertIn("{{ " + variavel + " }}", bloco)

        sem_contexto = re.sub(r"\{\{.*?\}\}", "", bloco, flags=re.S)
        self.assertEqual(
            re.findall(r"\d+", sem_contexto),
            [],
            "os cards de estatística voltaram a escrever números à mão",
        )

    def test_pitch_renderiza_contagens_reais_do_catalogo(self):
        html = self.client.get(reverse("pitch")).content.decode("utf-8")

        esperados = {
            "n_catalogo": sum(len(classe["itens"]) for classe in CATALOGO),
            "n_existe": _conta(EXISTE),
            "n_parcial": _conta(PARCIAL),
            "n_ausente": _conta(NAO_EXISTE),
        }
        for valor in esperados.values():
            self.assertIn(f'<div class="pitch-stat-value">{valor}</div>', html)

        self.assertEqual(esperados, {
            "n_catalogo": 57,
            "n_existe": 27,
            "n_parcial": 17,
            "n_ausente": 13,
        })
