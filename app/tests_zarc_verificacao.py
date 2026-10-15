"""ZARC: a lavoura está dentro da janela de plantio?

## O teste que mais importa

`test_sem_zarc_nao_e_fora_da_janela`.

Se ausência de ZARC devolvesse `False`, o sistema mostraria ao produtor
"FORA DA JANELA — sua indenização pode ser indeferida" **sem ter o dado para
dizer**. O produtor perderia o sono por uma informação que o sistema não tem.
É o mesmo defeito de `custo_producao.py` e `cotacoes.py`: **fabricar um
veredito a partir da falta de dado**.

Este ficheiro fixa a distinção:

| Situação | `dentro_da_janela` | Leitura |
|---|---|---|
| Dentro da janela | `True` | medido |
| Fora da janela | `False` | medido, e há aviso |
| Sem ZARC para a geografia | `None` + motivo | **ausência** |
| Sem município | `None` + motivo | **ausência** |
| Sem data de plantio | `None` + motivo | **ausência** |

Só as duas primeiras linhas são diagnóstico. As outras são honestidade.
"""

from __future__ import annotations

from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase

from app.models import (
    Cultura,
    Propriedade,
    Safra,
)
from app.models.producao import ZARC
from app.services.zarc import (
    safras_fora_da_janela,
    verificar_propriedade,
    verificar_safra,
)


class ZarcVerificacaoTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("ana", password="x")
        self.prop = Propriedade.objects.create(
            user=self.user,
            nome="Fazenda Boa",
            area_total=100,
            uf="MT",
            cidade="Sorriso",
        )
        self.cultura = Cultura.objects.create(nome="Soja", ativo=True)
        self.zarc = ZARC.objects.create(
            cultura=self.cultura,
            uf="MT",
            municipio="Sorriso",
            data_inicio_plantio=date(2026, 9, 15),
            data_fim_plantio=date(2026, 10, 20),
            ciclo_dias=120,
            risco_climatico=0.20,
        )

    def _safra(self, **kw):
        defaults = {
            "propriedade": self.prop,
            "cultura": self.cultura,
            "ano": 2026,
            "area_plantada": "50.00",
            "producao_total": "30000.00",
        }
        defaults.update(kw)
        return Safra.objects.create(**defaults)

    # ------------------------------------------------------------------
    # As duas respostas reais
    # ------------------------------------------------------------------

    def test_dentro_da_janela(self):
        s = self._safra(data_plantio=date(2026, 10, 1))
        r = verificar_safra(s.id)
        self.assertIs(r["dentro_da_janela"], True, r)
        self.assertEqual(r["zarc_id"], self.zarc.id)
        self.assertEqual(r["dias_fora_da_janela"], 0)
        self.assertIsNone(r["aviso"])

    def test_fora_da_janela_com_aviso_e_dias(self):
        s = self._safra(data_plantio=date(2026, 11, 15))
        r = verificar_safra(s.id)
        self.assertIs(r["dentro_da_janela"], False, r)
        self.assertEqual(
            r["dias_fora_da_janela"], 26, "o produtor precisa de saber quantos dias"
        )
        self.assertIsNotNone(r["aviso"])
        self.assertIn("indemnização", r["aviso"])

    def test_antes_da_janela_tambem_conta(self):
        s = self._safra(data_plantio=date(2026, 9, 1))
        r = verificar_safra(s.id)
        self.assertIs(r["dentro_da_janela"], False, r)
        self.assertEqual(r["dias_fora_da_janela"], 14)

    def test_limites_sao_inclusive(self):
        """O primeiro e o último dia são dentro — é o que o MAPFRE considera."""
        for dia in (date(2026, 9, 15), date(2026, 10, 20)):
            with self.subTest(dia=dia):
                s = self._safra(data_plantio=dia)
                self.assertIs(verificar_safra(s.id)["dentro_da_janela"], True)

    # ------------------------------------------------------------------
    # Ausência NUNCA é diagnóstico
    # ------------------------------------------------------------------

    def test_sem_zarc_nao_e_fora_da_janela(self):
        """O teste mais importante do ficheiro.

        Sem ZARC para a geografia, o sistema **não sabe**. Se disser "fora",
        está a inventar um risco contra o produtor.
        """
        outra = Propriedade.objects.create(
            user=self.user,
            nome="Onde não há ZARC",
            area_total=10,
            uf="MS",
            cidade="Ponta Porã",
        )
        s = Safra.objects.create(
            propriedade=outra,
            cultura=self.cultura,
            ano=2026,
            area_plantada="10.00",
            producao_total="100.00",
            data_plantio=date(2026, 10, 1),
        )

        r = verificar_safra(s.id)

        self.assertIsNone(
            r["dentro_da_janela"],
            "ausencia de ZARC virou 'fora da janela': o produtor foi avisado "
            "de um risco que o sistema não tem como avaliar",
        )
        self.assertIn("ZARC", r["motivo"])

    def test_sem_municipio_e_ausencia(self):
        prop = Propriedade.objects.create(
            user=self.user, nome="Sem cidade", area_total=10, uf="MT", cidade=""
        )
        s = Safra.objects.create(
            propriedade=prop,
            cultura=self.cultura,
            ano=2026,
            area_plantada="10.00",
            producao_total="100.00",
            data_plantio=date(2026, 10, 1),
        )
        r = verificar_safra(s.id)
        self.assertIsNone(r["dentro_da_janela"])
        self.assertIn("município", r["motivo"])

    def test_sem_data_plantio_e_ausencia(self):
        s = self._safra(data_plantio=None)
        r = verificar_safra(s.id)
        self.assertIsNone(r["dentro_da_janela"])
        self.assertIn("data de plantio", r["motivo"])
        # E traz a janela, para o produtor saber o que devia ter plantado.
        self.assertIn("janela", r)

    def test_safra_inexistente(self):
        r = verificar_safra(999999)
        self.assertIsNone(r["dentro_da_janela"])
        self.assertIn("não encontrada", r["motivo"])

    def test_ausencia_tem_sempre_motivo(self):
        """Nenhum veredito `None` sem motivo — o produtor precisa saber o que
        preencher.

        Só testo `data_plantio`: `cultura` é NOT NULL no model
        (`models/safra.py:51`), então "safra sem cultura" não é um estado que o
        banco permita — e testar uma impossibilidade só daria um falso sinal
        de que o caminho está coberto.
        """
        r = verificar_safra(self._safra(data_plantio=None).id)
        self.assertIsNone(r["dentro_da_janela"])
        self.assertIsNotNone(
            r["motivo"], "ausencia sem motivo: o produtor nao sabe o que fazer"
        )

    # ------------------------------------------------------------------
    # As vistas de propriedade
    # ------------------------------------------------------------------

    def test_verificar_propriedade_traz_todas_as_safras(self):
        self._safra(data_plantio=date(2026, 10, 1))
        self._safra(ano=2025, data_plantio=date(2026, 11, 15))
        r = verificar_propriedade(self.prop.id)
        self.assertEqual(len(r), 2)

    def test_fora_da_janela_so_traz_vereditos_negativos(self):
        """A lista de risco NÃO inclui safras sem veredito.

        Listar uma safra sem ZARC como "fora" seria acusar o produtor de algo
        que o sistema não sabe.
        """
        dentro = self._safra(data_plantio=date(2026, 10, 1))
        fora = self._safra(ano=2025, data_plantio=date(2026, 11, 15))
        sem_data = self._safra(ano=2024, data_plantio=None)

        riscos = safras_fora_da_janela(self.prop.id)

        ids = [r["safra_id"] for r in riscos]
        self.assertIn(fora.id, ids)
        self.assertNotIn(dentro.id, ids)
        self.assertNotIn(
            sem_data.id,
            ids,
            "safra sem veredito entrou na lista de riscos: acusar sem base",
        )
