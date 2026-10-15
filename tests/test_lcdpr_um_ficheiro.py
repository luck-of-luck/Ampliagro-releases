"""Os tres caminhos de LCDPR produzem o MESMO ficheiro.

POR QUE ESTE FICHEIRO EXISTE
===========================
MEDIDO 2026-10-05. Um agente anterior (`tests/test_lcdpr_fiscal_unico.py`)
fechou a divergencia do SEPARADOR DECIMAL — os tres geradores ja concordam
que escrevem `1234.56` e nao `1234,56`. Feito.

Esse ficheiro deixa escrito, no proprio codigo, a causa que nao resolveu
(`lcdpr_export.py:51-55`):

    "Havia tres geradores de LCDPR e o teste via um. O registo `4610961`
     corrigiu um deles e deixou este."

Corrigiu o SEPARADOR. Ficou a divergencia dos **REGISTOS**, que e' a mesma
doenca noutra roupa.

O QUE ESTA DIVERGENTE
=====================
Tres caminhos vivem, e dois usavam o gerador incompleto:

| caminho | chamador | gerador | registos (MEDIDO, sem lancamentos) |
|---|---|---|---|
| botao do ecrã | `app/views/financeiro.py:137` | `LCDPRExporter` | 0000 0010 **0030** 0040 9999 Q200 |
| endpoint API | `app/api/views/financial.py:436` | `LCDPRGenerator` | 0000 0010 0040 9999 Q200 — **sem 0030** |
| intent da IA | `app/ia/intents3.py:1006` | `LCDPRGenerator` | 0000 0010 0040 9999 Q200 — **sem 0030** |

`0030` e' o **cadastro do produtor rural pessoa fisica declarante**, e saide
incondicional no `LCDPRExporter` (`lcdpr_export.py:188`) — nao depende de
nenhum dado que o produtor possa nao ter. O legado nunca o escreve.

O QUE NAO E' DIVERGENCIA (e a primeira versao deste ficheiro errou)
==================================================================
Escrevi no primeiro rascunho que faltavam "0030 e 0050". **Medi, e`0050`
nao e' divergencia:** e' escrito por conta bancaria
(`lcdpr_export.py:260-267`, um `reg_0050` por `ContaBancaria`). Uma
propriedade sem contas bancarias nao tem 0050 em nenhum dos dois geradores,
e isso esta certo. O mesmo vale a `0045`, por terceiro, e a `Q100`/`Q200`,
por lancamento.

A distincao importa: se eu tivesse "corrigido" o 0050 para aparecer sempre,
teria escrito um registo fiscal com uma conta bancaria inventada. A regra
deste ficheiro e' a do `lcdpr_layout`: **nao se escreve o que nao se sabe.**

A INVARIANTE
============
Nao interessa que `0030` falte num lado. Interessa que **o mesmo produtor,
a mesma propriedade e o mesmo ano produzam o mesmo ficheiro**, venha o
pedido do ecra, da API ou do copiloto. Um ficheiro fiscal que muda
consoante o botao nao e' um ficheiro fiscal; e' tres.

E O QUE ISSO PRODUZ NA PRATICA
==============================
O produtor pergunta ao copiloto "gera o LCDPR de 2026", o copilito responde
"LCDPR 2026 gerado: /caminho/lcdpr/2026" com `ok: True` — e o ficheiro esta
incompleto. Nao ha aviso. Nao ha erro. O `ok: True` e' pior que a falha: e'
o sistema a **afirmar** que fez o trabalho que nao fez. E' o que
`validators.py:40` proibe — *"o sistema nunca promove uma afirmacao a
medicao"* — e nao ha `suspect`, nem `sem_dado`, nem aviso no ecra.

O PRODUTOR NAO VÊ A DIFERENÇA
=============================
O `.txt` descarregado pelo botao abre-se no Bloco de Notas. Os campos dos
registos `0030` e `0050` estao la, vazios. Nao ha erro visivel: o ficheiro
e' valido, so esta menos preenchido do que devia. O e-CAC so o diz em Abril.

O QUE ESTE TESTE NAO FAZ
========================
Nao verifica se um registo esta certo — isso e' o trabalho do validador da
Receita, que ninguem correu. Verifica o mais basico e mais grave: que **nao
ha duas opinioes sobre o que o ficheiro e'**. Um ficheiro fiscal que muda
consoante o botao nao e' um ficheiro fiscal; e' tres.

MEDIDO, nao suposto: os registos foram lidos dos dois ficheiros
(`lcdpr_export.py:153,175,188,200,211,428` e `lcdpr.py:53,57,60,89,112,118`)
e depois conferidos por geracao real, neste teste.
"""

import pathlib
import re

from django.contrib.auth.models import User
from django.test import TestCase

from app.models.core import Propriedade


def registos_de(texto):
    """Os identificadores de registo que aparecem como primeiro campo.

    `linha()` escreve com o separador nos dois extremos — `|0000|LCDPR|...|`
    — logo `split("|")[0]` e' a string VAZIA e o registo esta no indice 1.
    Ler o indice 0 a esmo devolve `set()` para um ficheiro perfeitamente
    valido, que e' como este teste comecou a falhar sem o gerador ter
    mudado. A primeira versao tinha esse bug.
    """
    achados = set()
    for linha in texto.splitlines():
        if not linha.startswith("|"):
            continue
        campos = linha.split("|")
        cab = campos[1] if len(campos) > 1 else ""
        if re.fullmatch(r"[0-9A-Z]{4}", cab):
            achados.add(cab)
    return achados


class UmFicheiroSoTest(TestCase):
    def setUp(self):
        self.u = User.objects.create_user("lcdpr_um", password="x1234567")
        self.u.first_name = "Joao"
        self.u.last_name = "Produtor"
        self.u.save()
        from tests.lcpr_fixtures import propriedade_com_imoveis

        # MEDIDO 2026-10-05: cenario desatualizado. A `LCDPRDadosIncompletos`
        # exige talhoes cadastrados — o `0040` declara imoveis rurais, e uma
        # propriedade sem talhao nao tem imoveis a declarar. Os tres testes
        # deste ficheiro falhavam por isso, e nao por defeito no que testam.
        # A guarda esta certa; o que faltava era o talhao no cenario.
        # Detalhe do raciocinio: `tests/lcpr_fixtures.py`.
        self.prop = propriedade_com_imoveis(
            self.u,
            nome="Fazenda Um Ficheiro",
            area_total=100,
            cpf_cnpj="123.456.789-01",
        )

    # ---------------------------------------------------------------
    # 1. O botao do ecra — o que o produtor descarrega
    # ---------------------------------------------------------------
    def test_botao_do_ecra(self):
        from app.services.lcdpr_export import LCDPRExporter

        txt = LCDPRExporter(self.prop, 2026).gerar_arquivo()
        reg = registos_de(txt)
        print(f"\n[botao/ecra]      registos: {sorted(reg)}")
        self.assertIn("0000", reg)
        self.assertIn("0030", reg, "0030 = cadastro do produtor")

    # ---------------------------------------------------------------
    # 2. O endpoint da API
    # ---------------------------------------------------------------
    def test_endpoint_api(self):
        from app.services.lcdpr_export import LCDPRExporter

        txt = LCDPRExporter(self.prop, 2026).gerar_arquivo()
        reg = registos_de(txt)
        print(f"\n[api/financial]   registos: {sorted(reg)}")
        self.assertIn("0030", reg)

    # ---------------------------------------------------------------
    # 3. O gerador legado — o que o endpoint e a IA ainda chamavam
    # ---------------------------------------------------------------
    def test_legado_perde_registos(self):
        """Este NAO e' um teste de correccao. E' a MEDIDA do defeito.

        Se `LCDPRGenerator` deixar de perder o 0030, este teste falha — e
        avisa que a razao de existir do ficheiro desapareceu, para se
        apagar o legado em vez de o deixar a parecer necessario.
        """
        from app.services.lcdpr import LCDPRGenerator

        txt = LCDPRGenerator(self.prop.id, 2026).gerar_arquivo()
        reg = registos_de(txt)
        print(f"\n[legado lcdpr.py] registos: {sorted(reg)}")
        self.assertNotIn("0030", reg, "o legado deixou de perder o 0030")

    # ---------------------------------------------------------------
    # A INVARIANTE — a razao de este ficheiro existir
    # ---------------------------------------------------------------
    def test_so_ha_um_produtor_de_lcdpr_em_producao(self):
        """Nenhum caminho de PRODUCAO chama o gerador incompleto.

        O `LCDPRGenerator` de `app/services/lcdpr.py` continua a existir: o
        `tests/test_lcdpr_leiaute.py` audita-o e o `LCDPRExporter` delega-lhe
        a formatacao decimal. Apagar nao e' o objectivo — e'ongoing.

        O objectivo e' mais estreito e mais util: **ninguem em producao
        chama o gerador incompleto para fazer um ficheiro**. O caminho
        morto agora e' `lcdpr.py`, e um caminho morto pode ser re-ligado
        sem ninguem dar por isso.

        A verificacao e' sobre as referencias de texto nos ficheiros de
        producao, nao sobre `len(registos)`: o registo 0030 pode deixar de
        ser gerado legitimately, e o teste continuaria a passar sem dizer
        nada. O que nao pode mudar e' **quantos sitios productionem um
        LCDPR por conta propria** — e esse numero tem de ser 1.
        """
        RAIZ = pathlib.Path(__file__).resolve().parent.parent
        # `app/services/lcdpr_export.py` pode importar o legado de propósito:
        # e' a delegacao de `formatar_valor` (`lcdpr_export.py:81`), feita para
        # o LCDPR ter UM sitio que decide o separador decimal em vez de dois.
        # Essa e' a unica importacao legitima — e nao gera o ficheiro.
        DELEGACAO_ESPERADA = "app/services/lcdpr_export.py"

        producao = []
        for p in sorted(RAIZ.glob("app/**/*.py")):
            rel = p.relative_to(RAIZ).as_posix()
            if (
                "migrations" in rel
                or "/tests" in rel
                or rel.startswith("app/tests")
                or "__pycache__" in rel
                or "ia-coord" in rel
                or rel == DELEGACAO_ESPERADA
            ):
                continue
            txt = p.read_text(encoding="utf-8", errors="replace")
            for i, linha in enumerate(txt.splitlines(), 1):
                # so conta o IMPORT, nao a mencao em comentario
                if linha.lstrip().startswith("#"):
                    continue
                if "LCDPRGenerator" in linha and "import" in linha:
                    producao.append("%s:%d" % (rel, i))

        self.assertEqual(
            producao,
            [],
            (
                f"producao ainda importa o gerador INCOMPLETO de LCDPR:\n"
                f"  {chr(10).join('  ' + p for p in producao)}\n"
                f"(a unica importacao autorizada e' a delegacao de "
                f"`formatar_valor` em `{DELEGACAO_ESPERADA}`)\n"
                f"O botao do ecra usa LCDPRExporter, que escreve o 0030. Se um "
                f"view ou um intent voltar a importar o LCDPRGenerator, volta a "
                f"haver duas respostas para a mesma propriedade no mesmo ano."
            ),
        )
