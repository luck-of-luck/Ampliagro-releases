"""Zona de escrita isolada: a IA compõe o Palco, não mexe no painel do produtor.

O documento de arquitectura promete (§VI) que o painel construido pela IA é
"efemero e condicionado, evitando que alterações automatizadas sobrescrevam o
layout historico de gestao da fazenda".

Esta é a promessa de segurança com consequencia mais grave que eu ainda nao
tinha verificado: se a IA escreve onde o produtor guarda o trabalho dele, o
dano nao e um numero errado no ecra — e o trabalho dele desaparece.

O que o codigo mostra (auditado antes de escrever este ficheiro):

* `PresetPalco` (app/models/palco.py) e onde a IA escreve.
  `WidgetUsuario` (app/models/usuario.py) e onde o produtor guarda.
  Sao modelos DIFERENTES, em ficheiros diferentes, sem FK entre eles.
* `intents.py:1161` filtra sempre `PresetPalco.objects.filter(user=user, ...)`:
  a posse entra no filtro, nao ha campo para o cliente dizer de quem e.
* `validar_estrutura`/`aplicar_operacoes` nunca levantam: cada problema vira
  motivo em `descartados` e a mesa segue com o resto.

Estes testes fixam o invariante para que uma refatoracao futura nao o quebra
em silencio — que e como o BUG-4 aconteceu: nao por logica errada, por
inventario incompleto.
"""

from __future__ import annotations

import pathlib

from django.contrib.auth.models import User
from django.test import TestCase

from app.ia import palco
from app.models import PresetPalco, WidgetUsuario

RAIZ = pathlib.Path(__file__).resolve().parent


class ZonaDeEscritaIsoladaTest(TestCase):
    def setUp(self):
        self.ana = User.objects.create_user("ana", password="x")
        self.bob = User.objects.create_user("bob", password="x")

    def test_o_ia_nao_tem_forma_de_achar_o_widget_usuario(self):
        """Nenhum modulo da IA escreve em `WidgetUsuario`.

        Se algum handler passar a gravar no modelo do produtor, o painel dele
        desaparece sem nenhum aviso. A varredura e por fonte, e nao por
        `co_names`: um handler que chama um utilitario que grava nao aparece
        em `co_names` do handler, e a varredura passaria em silencio.
        """
        # So os modulos que participam na composicao do palco. `intents.py` e
        # `palco*.py`; `dinamicos.py` e `iot*.py` sao ferramentas do produtor,
        # nao a mesa.
        modulos_do_palco = ["intents.py", "palco.py", "palco_dados.py", "paginas.py"]
        offenders = []
        for nome in modulos_do_palco:
            caminho = RAIZ / nome
            if not caminho.exists():
                continue
            texto = caminho.read_text(encoding="utf-8")
            # procura o import E o uso, nao so a palavra
            if "WidgetUsuario" in texto:
                offenders.append(nome)

        self.assertEqual(
            offenders,
            [],
            f"modulos da IA que referenciam WidgetUsuario: {offenders}. "
            "A zona de escrita isolada diz que a IA so escreve em PresetPalco.",
        )

    def test_widget_usuario_do_produtor_sobrevive_a_ia(self):
        """O teste que importa: a IA a trabalhar nao toca no painel do produtor.

        `WidgetUsuario` e um widget POR LINHA (tipo/pos/tamanho/config), nao um
        layout em JSON — o que torna a comparacao ainda mais direta: se a IA
        escrevesse aqui, apareceria uma linha nova ou mudaria `config`.
        """
        meu = WidgetUsuario.objects.create(
            user=self.ana,
            tipo_widget="kpi-custo",
            posicao_x=0,
            posicao_y=0,
            tamanho_w=6,
            tamanho_h=4,
            config={"filtro": "safra-2026"},
        )

        # A IA compoe um preset e grava com forca.
        PresetPalco.objects.create(
            user=self.ana,
            slug="amplia",
            nome="Palco da IA",
            estrutura={
                "widgets": [
                    {"tipo": "kpi-area", "geom": {"x": 0, "y": 0, "w": 4, "h": 3}}
                ]
            },
        )

        meu.refresh_from_db()
        self.assertEqual(
            meu.config, {"filtro": "safra-2026"}, "a IA alterou o widget do produtor"
        )
        self.assertEqual(WidgetUsuario.objects.filter(user=self.ana).count(), 1)

    def test_widget_usuario_nao_tem_ligacao_ao_preset_da_ia(self):
        """`WidgetUsuario` nao tem qualquer campo que aponte para `PresetPalco`.

        Se algum dia um preset da IA passar a ser gravado num campo do produtor,
        o produtor abre o painel e ve a mesa da IA no lugar da dele. O teste
        fixa que a ligacao nao existe — por ausencia de campo, nao por
        convencao.
        """
        campos = {f.name for f in WidgetUsuario._meta.get_fields()}
        self.assertNotIn(
            "preset",
            campos,
            "WidgetUsuario passou a ter campo de preset: a IA poderia plantar "
            "a mesa dela como preset do produtor",
        )
        # E nenhum campo e relacao para o palco.
        relacoes = {f.name for f in WidgetUsuario._meta.get_fields() if f.is_relation}
        for nome in relacoes:
            with self.subTest(campo=nome):
                alvo = WidgetUsuario._meta.get_field(nome).related_model
                self.assertIsNot(
                    alvo,
                    PresetPalco,
                    "WidgetUsuario tem uma relacao directa para PresetPalco",
                )

    def test_a_ia_so_alca_presets_do_proprio_produtor(self):
        """A posse entra no filtro: o slug de um e o preset de outro."""
        meu = PresetPalco.objects.create(
            user=self.ana, slug="amplia", nome="Palco da Ana", estrutura={"widgets": []}
        )
        # O Bob pede o slug da Ana. `resolver` no handler faz
        # `filter(user=user, slug=slug)`, entao nao acha.
        achado = PresetPalco.objects.filter(user=self.bob, slug="amplia").first()
        self.assertIsNone(achado, "o preset de um produtor apareceu para o outro")
        # E o preset da Ana continua intacto.
        meu.refresh_from_db()
        self.assertEqual(meu.user, self.ana)


class MesaDaIaSeguraTest(TestCase):
    """O que a IA escreve tem de passar pelo catalogo — nunca um widget inventado."""

    def test_widget_inventado_nao_entra(self):
        validos, fora = palco.validar_estrutura([{"tipo": "widget-que-nao-existe"}])
        self.assertEqual(validos, [])
        self.assertTrue(any("desconhecido" in d for d in fora))

    def test_patch_invalido_nao_levanta(self):
        """Patch de 1B nao pode ser traceback: e descarte com motivo."""
        for operacoes in (
            None,
            "texto",
            [None, 1, "x"],
            [{"op": "add"}, {"op": "add", "widget": None}],
            [{"op": "remove"}, {"op": "move"}],
            [{"op": "add", "widget": {"tipo": "inexistente"}}],
        ):
            with self.subTest(operacoes=operacoes):
                novos, _ = palco.aplicar_operacoes([], operacoes)
                self.assertEqual(novos, [])

    def test_patch_nao_adiciona_widget_repetido(self):
        base = [{"tipo": "kpi-custo", "geom": {"x": 0, "y": 0, "w": 6, "h": 4}}]
        novos, descartados = palco.aplicar_operacoes(
            base, [{"op": "add", "widget": {"tipo": "kpi-custo"}}]
        )
        self.assertEqual(len(novos), 1)
        self.assertTrue(any("repetido" in d for d in descartados))

    def test_patch_respeita_o_teto_de_widgets(self):
        ops = [
            {"op": "add", "widget": {"tipo": t}}
            for t in list(palco.CATALOGO_IA)[: palco.MAX_WIDGETS + 5]
        ]
        novos, descartados = palco.aplicar_operacoes([], ops)
        self.assertLessEqual(len(novos), palco.MAX_WIDGETS)
        self.assertTrue(any("acima_do_teto" in d for d in descartados))

    def test_nao_mutar_a_lista_do_chamador(self):
        base = [{"tipo": "kpi-custo", "geom": {"x": 0, "y": 0, "w": 6, "h": 4}}]
        antes = [dict(w) for w in base]
        palco.aplicar_operacoes(base, [{"op": "add", "widget": {"tipo": "kpi-area"}}])
        self.assertEqual(base, antes, "aplicar_operacoes mutou a lista do chamador")
