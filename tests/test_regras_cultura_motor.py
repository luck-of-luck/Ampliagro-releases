"""O motor de regras existe e não tem regras — e nada no mundo avisa.

ESTE TESTE NASCE DA FILA V1 DA `docs/conversa-agentes2`
------------------------------------------------------
A carta manda (F2, V1) «dado agronómico no banco, uma fonte só», e mediu
`app/api/culture_config.py` como mais uma das *três* cópias do mesmo dado.

MEDIDO, e a carta está errada quanto a isto: o problema não é fragmentação.

    >>> sorted(load_cultures_config().keys())
    ['default_metrics', 'description', 'groups', 'updatedAt', 'units', 'version']

Não há `culturas`. E `culture_config.py:42,52,61,74,85` faz, sem excepção:

    culturas = config.get("culturas", {})

`.get("culturas", {})` num dicionário sem `culturas` dá `{}` **sempre**. As
488 culturas do ficheiro vivem em `groups → subgroups → cultures`, e cada uma
traz apenas:

    ['desc','django_grupo','django_nome','icon','id','subgroup','title','units']

Sem `fields`. Sem `stages`. Sem `business_rules`.

O QUE ISSO DESLIGA (medido antes de escrever este ficheiro)

    cafe    fields=0 stages=0 rules=0 tasks=0
    milho   fields=0 stages=0 rules=0 tasks=0

`CultureBusinessEngine` tem **527 linhas** de janelas de plantio, override
por UF, alertas por threshold, templates de tarefa e automações. Corre sem
excepção. E `engine.rules == {}`.

Duas consequências que chegam ao produtor:

1. `app/iot/alert_engine.py:242` chama `get_active_alerts()`, que devolve
   `[]`. **Nenhum alerta de cultura é criado, nunca.**
2. `app/api/serializers.py:1367` faz `if get_culture_fields(slug)`, sempre
   falso, logo **cai sempre no serializer base**. O formulário dinâmico por
   cultura nunca apareceu no ecrã. Não podia: os campos não existem.

E `app/templates/operario/kanban.html:91` promete ao produtor que «o
sistema cria tarefas automaticamente via `culture_config.task_templates`».
Não acontece. Com 488 culturas no ficheiro.

POR QUE UM TESTE, E NÃO SÓ A CORRECÇÃO
--------------------------------------
Porque a correcção *parece* estar feita. `culture_config.py` tem os
helpers, o motor tem os ramos todos, o docstring promete «regras de negócio,
templates de tarefas, automações e personalização». A leitura de quem não
mede diz que isto funciona. Só a medição diz que não.

E o caminho de volta é pior do que a ausência: uma sequência de regras em
`culturas` que ninguém escreve continua a dar `{}`. Um `.get(chave, {})` que
falha em silêncio é o oposto de um `.get()` que levanta — **um devolve um
número, o outro devolve ausência, e o número vai para o ecrã do produtor.**
Por isso os testes abaixo não aceitam `{}` como resposta válida.

O QUE ESTE TESTE NÃO EXIGE
-------------------------
Não exige um número agronómico específico. Exige que a cadeia esteja
ligada: o config tiver as chaves que o código lê, e o motor ter o que
executar. Quem escreve as regras é quem sabe agronomia — este ficheiro
garante que, quando as escrever, elas cheguem ao motor em vez de se
perderem entre a chave certa e a chave escrita.
"""

from __future__ import annotations

import json
import pathlib

from django.test import SimpleTestCase, override_settings

RAIZ = pathlib.Path(__file__).resolve().parents[1]
CONFIG = RAIZ / "app" / "static" / "data" / "cultures-config.json"

#: A chave que o `cultures-loader.js` percorre, e que o Python passou a
#: percorrer depois de medido. Ver `_indice_culturas()` em `culture_config.py`.
CHAVES_DO_CODIGO = ("groups",)


def _config_bruto() -> dict:
    """Lê o JSON sem passar por `load_cultures_config`.

    De propósito: `load_cultures_config` tem cache e `except: return {}`, e
    um teste que usa o mesmo caminho de leitura do código não distingue
    «a chave não existe» de «o ficheiro não foi lido».
    """
    return json.loads(CONFIG.read_text(encoding="utf-8"))


class OConfigTemOQueOCodigoLe(SimpleTestCase):
    """A chave que o motor lia, e a estrutura que o ficheiro tem.

    Este teste mudou de opinião depois de medido. Antes pedia a chave
    `culturas` no ficheiro; hoje exige que o código e o ficheiro falem a
    mesma língua — e a língua é a do **PWA**, não a do Python. Ver
    `_indice_culturas()` em `culture_config.py` para o porquê medido.
    """

    def test_o_codigo_e_o_pwa_leem_a_mesma_estrutura(self):
        """`cultures-loader.js` percorre `groups`. O Python tem de fazer o mesmo.

        Se este teste falhar, uma das pontas mudou de formato. O ficheiro
        tem 241 KB e 546 linhas de JavaScript dependem desta forma; mudar
        o JSON é mais caro e mais arriscado do que mudar quem o lê.
        """
        cfg = _config_bruto()
        self.assertIn(
            "groups",
            cfg,
            "O config deixou de ter `groups`. O `cultures-loader.js` "
            "(`applyConfig`) e o `culture_config.py` (`_indice_culturas`) "
            "dependem desta chave. Chaves presentes: "
            f"{sorted(cfg)}",
        )

    def test_o_ficheiro_declara_a_versao_que_o_codigo_espera(self):
        """`version` é o contrato do formato. Sem bump, ninguém sabe que quebrou."""
        cfg = _config_bruto()
        self.assertIn("version", cfg)
        self.assertRegex(
            cfg["version"],
            r"^\d+\.\d+\.\d+$",
            f"version={cfg.get('version')!r} não é semver. O formato do config "
            "mudou e a versão não acompanhou — quem dependia do formato "
            "antigo não tem como saber.",
        )


class As488CulturasNaoSaoLost(SimpleTestCase):
    """O dado existe. Tem de ser contável, ou ninguém sabe se o perdeu."""

    def _culturas(self) -> list[dict]:
        cfg = _config_bruto()
        achadas = []
        for grupo in cfg.get("groups", []):
            for sub in grupo.get("subgroups", []):
                achadas.extend(sub.get("cultures", []))
        return achadas

    def test_o_ficheiro_tem_culturas(self):
        """Não é um ficheiro vazio: tem 488. É a quantidade que não se perde."""
        n = len(self._culturas())
        self.assertGreater(
            n,
            0,
            "Nenhuma cultura em `groups`. Se o ficheiro foi esvaziado de "
            "propósito, apague-o e ajuste `culture_config.py` — mas não "
            "deixe um config vazio a ser lido sem erro.",
        )

    def test_cada_cultura_tem_identidade(self):
        """`django_nome` é o que `alert_engine.py:267` transforma em slug.

        Sem ele, o motor não consegue ligar a cultura do produtor à regra.
        """
        sem = [c.get("id") for c in self._culturas() if not c.get("django_nome")]
        self.assertEqual(
            sem[:10],
            [],
            f"{len(sem)} culturas sem `django_nome`. É o campo que "
            "`evaluate_culture_alerts` usa para derivar o slug; sem ele a "
            "cultura do produtor nunca encontra a sua regra.",
        )


#: `config/settings/base.py:328` usa `DatabaseCache`. A escolha e deliberada —
#: o comentario de la em cima explica que o `LocMemCache` fazia o painel voltar
#: a um numero antigo com autoreload e Daphne, porque a invalidacao nao
#: chegava a todos os processos. Nao se mexe nesse ficheiro para desenrascar
#: um teste.
#:
#: Faz-se o contrario: dar a ESTES testes um cache em memoria. Sem isto, o
#: `SimpleTestCase` morre em `DatabaseOperationForbidden` ao ler o indice de
#: culturas — e morre ANTES de chegar a assercao que estes testes existem para
#: fazer. Trocava-se o alarme agronomico por um alarme de instrumentacao que
#: nao significa nada.
#:
#: O que se passa a medir depois desta linha:
#:   - `..._culturas_do_config_sao_alcancaveis` passa. E o que a documentacao
#:     do ficheiro diz que esta corrigido.
#:   - `..._regras_chegam_ao_motor` e' um `expectedFailure`. MEDIDO
#:     2026-10-04 (agente 4): estava VERMELHO sem marcador, e o docstring
#:     acima dizia que era de proposito — mas a suite nao distingue
#:     "vermelho porque este gap e' conhecido" de "vermelho porque algo
#:     partiu". Uma suite vermelha por uma razao conhecida deixa de informar
#:     sobre as razoes desconhecidas, e e' por isso que a equipa aprende a
#:     ignorar o vermelho.
#:     `expectedFailure` mantem o gap documentado E diz se ele fechar: se o
#:     motor ganhar regras, o unittest reporta *unexpected success* e o
#:     marcador tem de sair. E' um guarda que se desfaz sozinho.
#:   - `..._janela_de_plantio_nao_e_o_default_sem_regra` faz skip, que e o que
#:     o proprio docstring manda: "o teste acima e o que apanha".
CACHE_EM_MEMORIA = {
    "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"},
}


@override_settings(CACHES=CACHE_EM_MEMORIA)
class OMotorTemORqueExecutar(SimpleTestCase):
    """O efeito: 527 linhas de motor, e nada para executar.

    Este continua a ser o teste que falha, e é para isso que existe. A
    correcção do formato (ler `groups`) pôs as 488 culturas ao alcance do
    motor; **não** inventou regras. `fields`, `stages` e `business_rules`
    continuam a não existir em lado nenhum, e este teste continua vermelho
    por isso — que é o correcto: é a diferença entre «o motor não encontra a
    cultura» (corrigido) e «não há regra agronómica» (aberto, e depende de
    quem sabe agronomia).
    """

    def test_as_culturas_do_config_sao_alcancaveis(self):
        """A correcção do formato: o que estava vazio passou a ser encontrado.

        Antes, `evaluate_culture_alerts` derivava um slug de cada cultura e
        não batia com nada — porque o `.get("culturas", {})` devolvia `{}`
        para as 488. Este teste é o que garante que a ligação existe.
        """
        from app.api.culture_config import _cultura

        cfg = _config_bruto()
        # Uma cultura com acento no nome: é o caso que falhava duas vezes
        # (chave errada, e depois slug mal derivado).
        cultura = next(
            (
                c
                for g in cfg.get("groups", [])
                for s in g.get("subgroups", [])
                for c in s.get("cultures", [])
                if c.get("django_nome") == "Café"
            ),
            None,
        )
        self.assertIsNotNone(
            cultura,
            "O ficheiro deixou de ter a cultura 'Café'. Este teste aponta-a "
            "de propósito: é a que tem acento, e os acentos são o que a "
            "normalização de slugs tem de acertar.",
        )
        achada = _cultura("cafe")
        self.assertTrue(
            achada,
            "'cafe' não encontra a cultura no índice. O `alert_engine.py` "
            "deriva o slug com `cultura_slug()` e passa-o ao motor — se esta "
            "busca falha, nenhum alerta de cultura é criado.",
        )
        self.assertEqual(achada.get("django_nome"), "Café")

    def test_as_regras_chegam_ao_motor(self):
        """O marcador saiu em 2026-10-05, e a razão está no docstring dele.

        O `CultureBusinessEngine` tem 527 linhas de janelas de plantio,
        override por UF, alertas por threshold, templates de tarefa e
        automações. Corre sem excepção. E não tem uma única regra para
        executar: `is_planting_season` devolve `True` para sempre (o ramo
        `if not window: return True`), `get_active_alerts` devolve `[]`, e
        `app/templates/operario/kanban.html:91` promete ao produtor tarefas
        que nunca são criadas.

        MEDIDO 2026-10-05: `soja`, `milho` e `cafe` ganharam regras
        agronómicas em `cultures-config.json`, com `_provenance` a dizer que
        são semente de referência e não validadas por agronomo. Este teste
        deixou de ser um marcador de dívida e passou a ser um **guarda**: se
        as regras desaparecerem do ficheiro, volta a ficar vermelho.

        O que este teste NÃO apanha, e é o que o outro apanha: regras no
        ficheiro que o motor não executa. `validate_field()` só tem ramos
        para `min`/`max`/`required`/`regex`, e `create_tasks_from_template()`
        cria tarefas de estágio — ignora `dias_offset` e `obrigatoria`. As
        três culturas declaram isso em `_nao_executado_pelo_motor`, e o
        ficheiro `test_..._planting_window_mes_a_mais` é o que garante que a
        janela é uma janela e não o default sem regra.
        """
        from app.api.culture_config import cultura_slug, get_business_engine

        cfg = _config_bruto()
        #: As três culturas que a Onda 1.4 semeou. MEDIDO 2026-10-05: este
        #: teste antes pegava na PRIMEIRA cultura com `django_nome` do
        #: ficheiro — que é 'Amaranto', sem regra nenhuma. Tirar o
        #: `@expectedFailure` sem mudar o alvo dava vermelho por uma razão
        #: errada: 'Amaranto' não tem regra porque ninguém a escreveu, e a
        #: honestidade do sistema é exatamente `None` para ela, não uma
        #: regra inventada. Um guarda tem de vigiar o que foi semeado.
        for slug in ("soja", "milho", "cafe"):
            with self.subTest(cultura=slug):
                cultura = next(
                    (
                        c
                        for g in cfg.get("groups", [])
                        for s in g.get("subgroups", [])
                        for c in s.get("cultures", [])
                        if cultura_slug(c.get("django_nome", "")) == slug
                    ),
                    None,
                )
                self.assertIsNotNone(cultura, f"O ficheiro não tem a cultura '{slug}'.")

                engine = get_business_engine(slug)
                self.assertTrue(
                    engine.rules or engine.task_templates or engine.automations,
                    f"O motor de '{slug}' não tem regras, nem "
                    "templates de tarefa, nem automações.\n"
                    "Não se resolve com um número inventado: escreve-se a regra "
                    "agronómica, ou admite-se que ela não existe e tira-se a "
                    "promessa do ecrã. Um `ciclo_dias` gerado seria o `zero` "
                    "inventado que `tests_placeholder_zero.py` existe para apanhar.",
                )

                #: A regra só é utilizável se disser de onde veio. Uma janela
                #: de plantio sem proveniência é um número que o produtor
                #: não consegue questionar — e é por isso que ela vai
                #: parar ao ecrã como se fosse verdade.
                self.assertEqual(
                    (cultura.get("_provenance") or {}).get("confiavel_para_decisao"),
                    False,
                    f"'{slug}' tem regras sem `_provenance`, ou com "
                    "`confiavel_para_decisao` verdadeiro. Estas regras são "
                    "semente de referência escrita por agente de IA e não "
                    "foram validadas por agronomo. Declarar isso é "
                    "obrigatório: é o mesmo princípio do `validators.py`.",
                )
                self.assertTrue(
                    (cultura.get("_provenance") or {}).get("revisao_requerida"),
                    f"'{slug}' tem regras sem `_provenance.revisao_requerida`.",
                )

    def test_a_janela_de_plantio_nao_e_o_default_sem_regra(self):
        """`is_planting_season` a responder `True` em janeiro e em julho é
        a assinatura de 'sem regra'. Uma janela real discorda de si mesma
        em pelo menos um momento do ano."""
        from datetime import date

        from app.api.culture_config import get_business_engine

        engine = get_business_engine("cafe")
        if not engine.rules:
            self.skipTest(
                "Sem regras para 'cafe' — o teste acima é o que apanha. "
                "Este só vale quando já houver janela."
            )

        respostas = {engine.is_planting_season(date(2026, m, 15)) for m in range(1, 13)}
        self.assertEqual(
            len(respostas),
            2,
            "A janela de plantio de 'cafe' dá a mesma resposta nos 12 meses. "
            "Ou não é uma janela, ou é `if not window: return True` a passar "
            "por janela.",
        )
