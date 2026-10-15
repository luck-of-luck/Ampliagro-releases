"""O cabeçalho da guia não escreve números. Este teste obriga-o.

POR QUE ESTE FICHEIRO SUBSTITUI O ANTERIOR
==========================================
MEDIDO 2026-10-05. O `test_guia_ferramentas_numeros.py` contava quatro
`stat-value` com classes CSS `stat-label`/`stat-value`. A guia foi
reconstruída — as classes passaram a `gf-estado-nome`/`gf-estado-num` — e o
teste antigo passou a procurar uma estrutura que já não existe.

Duas leituras possíveis, e uma está errada:

1. «A estrutura mudou, o teste adaptou-se.» — e o teste deixou de proteger.
2. «A estrutura mudou porque o modelo mudou.» — e o teste tem de proteger o
   **modelo novo**, que é mais forte do que o que protegia.

É a segunda. O modelo antigo era «4 contagens de ferramentas, uma delas
medida». O erro que o ficheiro apanhou — IoT dizia 4 com 8 dispositivos na
base — continua possível, e agora há **mais** números no cabeçalho: as
contagens de estado do catálogo (27/17/13). Um deles hardcoded seria o mesmo
defeito com mais uma ocorrência.

O que este ficheiro verifica, e porquê:

- **Nenhum número escrito à mão no cabeçalho.** Todos passam por
  `{{ ... }}`. Um número no HTML é uma promessa sem medir — o «707 culturas».
- **A IoT é o do produtor.** `Device` é por `propriedade`; contar a base
  inteira é dizer que tens 8 sensores quando 7 são do vizinho.
- **As contagens do catálogo batem com o catálogo.** A soma tem de fechar,
  classe a classe. Se o catálogo crescer e o número não, a página mente.
- **O número de IoT no HTML é o número na base.** Do produtor, confirmado
  com o terceiro produtor a existir e a não contar.
"""

from __future__ import annotations

import pathlib
import re
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

RAIZ = pathlib.Path(__file__).resolve().parents[1]
TEMPLATE = RAIZ / "app" / "templates" / "guia-ferramentas.html"


def template_bruto() -> str:
    return TEMPLATE.read_text(encoding="utf-8")


def cabecalho_bruto() -> str:
    """A parte do template antes das secções de classe.

    É onde vivem os números do topo. Depois das classes já não é cabeçalho,
    e é aí que vive o texto — que tem números de propósito (anos, leis).
    """
    t = template_bruto()
    corte = t.find('class="gf-nav"')
    assert corte != -1, (
        "não encontrei a navegação de classes. Se a página voltou ao formato "
        "antigo (abas), este ficheiro está a testar a coisa errada."
    )
    return t[:corte]


class CabecalhoNaoEscreveNumeros(TestCase):
    """1. Nenhum número escrito à mão."""

    def test_o_cabecalho_nao_tem_digitos_hardcoded(self):
        """Qualquer dígito dentro de um `gf-estado-num` é um número prometido.

        A forma correcta é `{{ variavel }}`. Um `27` à mão é o `stat-value` de
        antes com outro nome — e o ficheiro antigo provou que acontece.
        """
        cab = cabecalho_bruto()
        # As três caixas de estado.
        blocos = re.findall(r'class="gf-estado-num"[^>]*>\s*([^<]*?)\s*<', cab, re.S)
        for bruto in blocos:
            valor = bruto.strip()
            # Aceita `{{ ... }}` (o Django escreve) e vazio.
            if valor == "" or "{{" in valor:
                continue
            self.fail(
                f"número hardcoded no cabeçalho: {valor!r}\n\n"
                f"Tem de vir da vista. As contagens do catálogo passam por "
                f"`contagens_catalogo()` e `n_existe`/`n_parcial`/`n_ausente`, "
                f"e o número de IoT por `Device.objects.filter(...)`. Um "
                f"dígito à mão é um número que ninguém mediu."
            )

    def test_o_badge_do_cabecalho_tambem_nao_escreve_digitos(self):
        """O badge «N capacidades · M sensores» tem as duas coisas medidas.

        Same principle, other place. O badge é o número que o produtor lê
        primeiro e é o que se copia para uma apresentação.
        """
        cab = cabecalho_bruto()
        m = re.search(r'class="badge"[^>]*>(.*?)</span>', cab, re.S)
        assert m, "não encontrei o badge do cabeçalho"
        conteudo = m.group(1)
        # Remove o que já vem do contexto.
        sem_contexto = re.sub(r"\{\{.*?\}\}", "", conteudo, flags=re.S)
        digitos = re.findall(r"\d+", sem_contexto)
        self.assertEqual(
            digitos,
            [],
            f"o badge tem dígitos escritos à mão: {digitos}\n\n"
            f"O badge diz «{{{{ n_catalogo }}}} capacidades · {{{{ n_iot }}}} "
            f"sensores». Os dois têm de ser medidos.",
        )


class NumerosDoCabecalhoTest(TestCase):
    """2 e 3. O número de IoT é o do produtor."""

    def setUp(self):
        self.u = User.objects.create_user("guia_ferr", password="x1234567")
        self.client.force_login(self.u)

    def _html(self) -> str:
        r = self.client.get(reverse("guia-ferramentas"))
        self.assertEqual(r.status_code, 200)
        return r.content.decode("utf-8")

    def test_o_numero_de_iot_vem_dos_dispositivos_dele(self):
        """`Device` é por `propriedade`. A guia mostra o que é dele.

        Contar a base inteira é dizer que tens 8 sensores quando 7 são do
        vizinho — que é o mesmo erro do número hardcoded, mas com a base de
        dados errada em vez do HTML errado.
        """
        from app.models import Device, Propriedade

        prop = Propriedade.objects.create(
            user=self.u, nome="Fazenda dos Sensores", area_total=Decimal("10")
        )
        for i in range(3):
            Device.objects.create(
                propriedade=prop,
                nome="Sensor %d" % i,
                device_eui="eui-guia-ferr-%d" % i,
                tipo="SOLO",
            )

        html = self._html()
        m = re.search(r"{{ *n_iot *}}", template_bruto())
        self.assertIsNotNone(m, "o template deixou de usar `{{ n_iot }}`")

        # O número tem de se ler DENTRO do badge. Na página inteira há
        # dezenas de dígitos em comentários e notas, e um `search` largo
        # apanha o primeiro, não o certo. Ver a nota de
        # `test_o_numero_de_capacidades_no_badge_e_o_total`.
        badge = re.search(r'class="badge"[^>]*>(.*?)</span>', html, re.S)
        self.assertIsNotNone(badge, "não encontrei o badge do cabeçalho")
        dentro = badge.group(1)

        self.assertEqual(
            Device.objects.filter(propriedade__user=self.u).count(),
            3,
            "pré-condição: o produtor tem 3 dispositivos",
        )
        m3 = re.search(r"·\s*(\d+)\s*sensor", dentro)
        self.assertIsNotNone(
            m3, f"o badge não mostra o número de sensores:\n{dentro.strip()}"
        )
        self.assertEqual(
            int(m3.group(1)),
            3,
            "a guia mostra %s sensores e o produtor tem 3" % m3.group(1),
        )

    def test_os_dispositivos_de_outro_produtor_nao_aparecem(self):
        """O terceiro produtor existe, tem 7 sensores, e não contam.

        Este é o teste que impede a regressão mais cara: contar a base
        inteira. Com 3 + 7 = 10 na base, qualquer consulta sem filtro dá um
        número diferente dos 3 — e o produtor vê o sensor do vizinho.
        """
        from app.models import Device, Propriedade

        prop = Propriedade.objects.create(
            user=self.u, nome="Meus", area_total=Decimal("10")
        )
        Device.objects.create(
            propriedade=prop, nome="Meu sensor", device_eui="eui-meu-1", tipo="SOLO"
        )

        vizinho = User.objects.create_user("guia_vizinho", password="x1234567")
        pviz = Propriedade.objects.create(
            user=vizinho, nome="Dele", area_total=Decimal("500")
        )
        for i in range(7):
            Device.objects.create(
                propriedade=pviz,
                nome="Dele %d" % i,
                device_eui="eui-dele-%d" % i,
                tipo="SOLO",
            )

        html = self._html()
        badge = re.search(r'class="badge"[^>]*>(.*?)</span>', html, re.S)
        self.assertIsNotNone(badge, "não encontrei o badge do cabeçalho")
        m = re.search(r"·\s*(\d+)\s*sensor", badge.group(1))
        self.assertIsNotNone(m, "o badge não mostra o número de sensores")
        self.assertEqual(
            int(m.group(1)),
            1,
            "a guia mostra %s sensores. O produtor tem 1 e o vizinho tem 7. "
            "Contar a base inteira é dizer que tens 8 sensores quando tens 1."
            % m.group(1),
        )


class ContagensDoCatalogoBatem(TestCase):
    """4. As contagens de estado fecham com o catálogo."""

    def setUp(self):
        self.u = User.objects.create_user("guia_contagens", password="x1234567")
        self.client.force_login(self.u)

    def test_a_soma_das_contagens_e_o_total_do_catalogo(self):
        """27 + 17 + 13 tem de ser o número de itens.

        Se não fechar, há um item com um estado que não é um dos três — e
        esse item não tem cor nem rótulo na página. Um cartão sem estado é
        um cartão que parece funcional.
        """
        from app.guias.catalogo import CATALOGO

        total = sum(len(c["itens"]) for c in CATALOGO)
        html = self.client.get(reverse("guia-ferramentas")).content.decode("utf-8")

        numeros = re.findall(r'class="gf-estado-num"[^>]*>\s*(\d+)\s*<', html, re.S)
        self.assertEqual(
            len(numeros),
            3,
            f"esperava 3 contagens de estado, encontrei {len(numeros)}: {numeros}",
        )
        soma = sum(int(n) for n in numeros)
        self.assertEqual(
            soma,
            total,
            f"as contagens somam {soma} e o catálogo tem {total}. Ou há um "
            f"item com estado inválido, ou o cabeçalho está a mostrar "
            f"números que não são contagens de itens.",
        )


    def test_o_numero_de_capacidades_no_badge_e_o_total(self):
        """O badge diz o total. Tem de bater com o catálogo.

        Procuro o número **dentro do badge**, e não o primeiro da página.

        MEDIDO 2026-10-05: a primeira versão usava
        `re.search(r"(\\d+)\\s*capacidades", html)` sobre a página toda, e
        apanhou o `60` do comentário de CSS logo acima — «a maior parte das
        páginas põe 60 capacidades». O HTML tem dezenas de dígitos em
        comentários e notas. Um `search` na página inteira não é uma
        verificação: é uma adivinhação que às vezes dá o número certo.
        """
        from app.guias.catalogo import CATALOGO

        total = sum(len(c["itens"]) for c in CATALOGO)
        html = self.client.get(reverse("guia-ferramentas")).content.decode("utf-8")

        m = re.search(r'class="badge"[^>]*>(.*?)</span>', html, re.S)
        self.assertIsNotNone(m, "não encontrei o badge do cabeçalho")
        badge = m.group(1)

        m2 = re.search(r"(\d+)\s*capacidades", badge)
        self.assertIsNotNone(
            m2, f"o badge não tem o número de capacidades:\n{badge.strip()}"
        )
        self.assertEqual(
            int(m2.group(1)),
            total,
            "o badge diz %s capacidades e o catálogo tem %d" % (m2.group(1), total),
        )
