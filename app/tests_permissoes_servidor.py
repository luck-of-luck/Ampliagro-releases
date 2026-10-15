"""Invariante do modelo de 2 camadas de permissao do servidor.

Por que este arquivo existe
---------------------------
As paginas ``/servidor/*`` sao alcancaveis por TODAS as areas (camada 1, em
``hierarquia.PERMISSAO_POR_VIEW``). O QUE o servidor ve e filtrado dentro da
propria view (camada 2), pelo ``area_servidor``:

  estoque    -> so MECANICA/ESTOQUE/ADMIN/GERAL; MECANICA so ve PECA/FERRAMENTA
  agenda     -> fora de GERAL, filtra por cargo_alvo/setor da area
  alertas    -> MECANICA ve metricas de motor, CAMPO ve metricas de solo
  dashboard  -> as cards por area (MECANICA/CAMPO/PECUARIA)

Apertar a lista da camada 1 NAO aumenta a seguranca: troca o 403 da camada 1
por um 403 da camada 2 (mesma tela de erro, mesmos dados ausentes) e quebra o
contrato em que o produtor libera acesso via ``permissoes["paginas_extra"]``,
verificado em ``pode_acessar()`` ANTES da lista.

Estes testes existem para essa lista nao ser "apertada" por alguem que ache
que esta aumentando a seguranca.
"""

from django.contrib.auth.models import User
from django.test import Client, TestCase

from app.hierarquia import (
    PERMISSAO_POR_VIEW,
    PRODUTOR_SOMENTE,
    TODAS_AS_AREAS,
    pode_acessar,
)
from app.models import PerfilUsuario, Propriedade

PAGINAS_SERVIDOR = (
    "servidor-dashboard",
    "servidor-config",
    "servidor-estoque",
    "servidor-agenda",
    "servidor-alertas",
    "servidor-kanban",
    "operario-kanban",
)


def _mkuser(name):
    return User.objects.create_user(username=name, password="x")


def _servidor(name, area, prop):
    """Cria servidor com area.

    Usa update_or_create porque o sinal post_save `garantir_perfil_usuario`
    (app/signals.py) ja cria o PerfilUsuario de todo User novo. Um `create`
    aqui colidiria com o sinal (UNIQUE em perfilusuario.user_id).
    """
    u = _mkuser(name)
    PerfilUsuario.objects.update_or_create(
        user=u,
        defaults={
            "tipo_usuario": "servidor",
            "area_servidor": area,
            "propriedade_vinculada": prop,
        },
    )
    # o sinal populou o cache de `u.perfil`; descarta para o resto do teste
    # enxergar o perfil atualizado
    if hasattr(u, "_state"):
        u._state.fields_cache.pop("perfil", None)
    return u


class ServidorPermissaoPorAreaTest(TestCase):
    def setUp(self):
        self.produtor = _mkuser("prod_permteste")
        self.prop = Propriedade.objects.create(
            user=self.produtor, nome="Faz Perm", area_total=10, uf="MT", cidade="X"
        )

    def test_todas_as_areas_estao_no_mapa_das_paginas_do_servidor(self):
        for pagina in PAGINAS_SERVIDOR:
            with self.subTest(pagina=pagina):
                self.assertIn(pagina, PERMISSAO_POR_VIEW, f"{pagina} sumiu do mapa")
                self.assertEqual(
                    PERMISSAO_POR_VIEW[pagina],
                    TODAS_AS_AREAS,
                    f"{pagina} foi restringido por area — a restricao real e na view",
                )

    def test_toda_area_alcanca_as_paginas_do_servidor(self):
        for pagina in PAGINAS_SERVIDOR:
            for area in TODAS_AS_AREAS:
                with self.subTest(pagina=pagina, area=area):
                    u = _servidor(f"srv_{pagina}_{area}", area, self.prop)
                    self.assertTrue(
                        pode_acessar(u, pagina),
                        f"{area} perdeu acesso a {pagina} na camada 1",
                    )

    def test_restricao_real_continua_sendo_da_view(self):
        """A camada 2 precisa existir: CAMPO nao entra no estoque, mas entra
        no proprio painel."""
        c = Client()
        c.force_login(_servidor("srv_campo_estq", "CAMPO", self.prop))
        self.assertEqual(c.get("/servidor/estoque/").status_code, 403)
        self.assertEqual(c.get("/servidor/").status_code, 200)

    def test_paginas_extra_do_produtor_continuam_valendo(self):
        u = _servidor("srv_extra_perm", "GERAL", self.prop)
        perfil = u.perfil
        perfil.permissoes = {"paginas_extra": ["perfil"]}
        perfil.save()
        self.assertTrue(pode_acessar(u, "perfil"))
        # ...e PRODUTOR_SOMENTE continua acima de paginas_extra
        self.assertFalse(pode_acessar(u, next(iter(PRODUTOR_SOMENTE))))
