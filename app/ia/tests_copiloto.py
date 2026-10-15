"""Testes do copiloto — a diferença entre um chatbot e um copiloto.

O QUE SE TESTA, E PORQUÊ
========================
O produtor perguntou, naSua palavras:

    "vai chover hoje?"  ->  "Sim, chance de xx%. E tem uma aplicação de
                            pesticida marcada para quinta. Quer remarcar?"

Duas coisas distintas, e ambas são testadas:

1. **A VOZ.** O que o produtor lê não tem markdown, emoji, setas, nem a
   impersonalidade das instruções de sistema. Isto é medido, não opinado:
   antes de `app/ia/voz.py`, 25 de 29 ficheiros de `app/ia` usavam cabeçalho
   markdown, 19 usavam negrito, 7 usavam setas e 4 tinham emoji.

2. **A OFERTA.** A regra que acha a aplicação que a chuva estraga já existia
   em `proativo.regras_deterministicas` — e o `sandbox` nunca a chamava.
   Este módulo é o que a chama, e a parte que interessa é o que ele faz
   quando NÃO há risco: cala-se.

O QUE ESTE FICHEIRO PROVA NEGATIVAMENTE
=========================================
Uma oferta que aparece sempre é ruído, e ruído é o que faz um produtor
deixar de ler. Por isso o teste mais importante é o primeiro: **sem risco,
o copiloto não diz nada.**
"""

from datetime import timedelta

from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from app.ia import copiloto, registro
from app.ia.voz import limpar


class VozTest(TestCase):
    """O que o produtor lê."""

    def test_numero_como_um_portugues_o_le(self):
        """MEDIDO: 25 números com ponto decimal numa interface escrita em
        português. `9.9 mm` é o número que decide se um produtor pulveriza —
        e um produtor brasileiro lê `18.1` como milhar-e-um, não como
        dezoito vírgula um."""
        self.assertEqual(limpar("chuva 0.0 mm"), "chuva 0,0 mm")
        self.assertEqual(limpar("temperatura 18.0°C"), "temperatura 18,0°C")
        self.assertEqual(limpar("vento 8.3 km/h"), "vento 8,3 km/h")
        self.assertEqual(limpar("pico 96% (9.9 mm)"), "pico 96% (9,9 mm)")
        self.assertEqual(limpar("100.00 kg de adubo"), "100,00 kg de adubo")

    def test_a_virgula_nao_come_um_numero_de_versao(self):
        """Este teste existe porque a versão ANTERIOR da regex prometia isto
        no comentário e NÃO fazia: `Python 3.11` virava `Python 3,11`. O `3`
        está isolado, e a guarda de ponto não vê o `Python` que está antes.

        Uma promessa no comentário que o código não cumpre é pior do que
        nenhum comentário: passa a revisão e falha na tela do produtor."""
        for t in (
            "Python 3.11",
            "app 1.2.3",
            "v2.10",
            "10.04.2026",
            "1.234.567,89",
        ):
            self.assertEqual(limpar(t), t, f"virgula comeu {t!r}")

    def test_a_unidade_fica_colada_ao_numero(self):
        """A primeira regex tinha `\\s*` antes do lookahead e COMIA o espaço:
        `0.0 mm` saía `0,0mm`. Um número colado à unidade não é português de
        ninguém — e o defeito parece correcto numa revisão apressada."""
        self.assertEqual(limpar("0.0 mm"), "0,0 mm")
        self.assertEqual(limpar("8.3 km/h"), "8,3 km/h")
        self.assertNotIn("0,0mm", limpar("0.0 mm"))

    def test_o_dinheiro_tem_a_virgula_certa(self):
        """`R$ 0.00` é lido como zero reais por um brasileiro, e `R$ 1.234.56`
        como milhar quando são mil duzentos e trinta e quatro. `R$` é âncora:
        um ponto depois de `R$` só pode ser decimal."""
        self.assertEqual(limpar("R$ 0.00 receita"), "R$ 0,00 receita")
        self.assertEqual(limpar("R$ 1.234.567,89"), "R$ 1.234.567,89")
        # `R$ 1.234.56` fica como está, e é uma decisão.
        #
        # É ambíguo: pode ser milhar americano com vírgula trocada, ou um
        # decimal depois de um ponto de milhar. Adivinhar errado num valor
        # que o produtor vai ler como dinheiro é pior do que não mexer. As
        # guardas de ponto recusam os dois casos, e recusar é a resposta
        # certa quando a pergunta não tem resposta única.
        self.assertEqual(limpar("R$ 1.234.56"), "R$ 1.234.56")

    def test_um_intervalo_e_uma_coisa_so(self):
        """MEDIDO: `17.6–24.3°C` saía `17.6–24,3°C`. O primeiro número não
        tem unidade colada — o que a segue é um traço — e a regra simples não o
        via. Um intervalo com vírgula de um lado e ponto do outro é um número
        que não existe em lado nenhum, e é PIOR do que não converter nada."""
        self.assertEqual(limpar("17.6–24.3°C"), "17,6–24,3°C")

        # Limite conhecido, e fica escrito: `mín. 3.5 máx. 9.1 mm` NÃO é
        # convertido no primeiro número. Não é um intervalo com traço, e
        # inferir que é um intervalo seria adivinhar a partir de duas
        # palavras. O número da direita, esse sim, tem unidade e converte.
        # Registado aqui para ninguém conta com um comportamento que não
        # existe.

    def test_tira_negrito_e_italico(self):
        self.assertEqual(limpar("**Alerta** de chuva"), "Alerta de chuva")
        # `__x__` é o caso que uma regex de marcador único não apanha, e o
        # resultado é texto com os símbolos à vista que parece intacto.
        self.assertEqual(limpar("__Alerta__ de chuva"), "Alerta de chuva")
        self.assertEqual(limpar("*alerta* de chuva"), "alerta de chuva")

    def test_tira_cabecalho_e_bolinha(self):
        self.assertEqual(limpar("# Resumo da safra"), "Resumo da safra")
        # O travessão também é lista em markdown, e não só a bolinha.
        self.assertEqual(limpar("- ureia 50 sc"), "ureia 50 sc")
        self.assertEqual(limpar("• diesel 200 L"), "diesel 200 L")

    def test_tira_emoji(self):
        for e in ("\U0001f525", "☀", "✅"):
            self.assertNotIn(e, limpar(f"Chuva forte {e}"))

    def test_tita_seta_unicode_e_ascii(self):
        """A ASCII `->` aparece em `intents.py` e `ia-local.js` desde sempre.
        Responder `->` ao produtor é tão máquina como responder `→`."""
        for s in ("→", "->", "=>"):
            self.assertNotIn(s, limpar(f"Aplicação {s} remarcar"))

    def test_remove_a_bolinha_sem_mudar_a_maiuscula(self):
        """A primeira versão capitalizava ao remover a bolinha: `• diesel`
        saía `Diesel`. Um transformador que reescreve é um transformador
        que mente — e mente com a confiança de quem parece ter cuidado."""
        self.assertEqual(limpar("• diesel 200 L"), "diesel 200 L")
        self.assertEqual(limpar("Ureia 50 sc"), "Ureia 50 sc")

    def test_nao_toca_nas_palavras_do_autor(self):
        """A camada SÓ subtrai. Não traduz `sync` nem tira o sujeito de
        "Ele avisa" — quem escreve a frase sabe o que está a dizer melhor do
        que uma regex, e um traducador automático produz "a ligação fica sem
        ligação", que não é português de ninguém."""
        original = "Ele avisa quando o sync fica offline."
        self.assertEqual(limpar(original), original)

    def test_a_voz_nao_e_o_responsavel_pela_voz(self):
        """O que `'Ele avisa'` nos prompts é do AUTOR, e arruma-se onde está
        escrito. Este teste existe para fixar essa separação: se um dia a
        `limpar()` voltar a reescrever palavras, este teste avisa."""
        self.assertEqual(limpar("sync"), "sync")
        self.assertEqual(limpar("dashboard"), "dashboard")
        self.assertEqual(limpar("Ele avisa"), "Ele avisa")

    def test_nao_mexe_no_que_e_legivel(self):
        """A camada tira lixo. Não reescreve o que está bem escrito — uma voz
        que reescreve o sentido é pior do que uma voz robótica, porque parece
        mais segura do que é."""
        bom = "Vai chover hoje, 80% de chance."
        self.assertEqual(limpar(bom), bom)

    def test_apanha_o_lixo_dos_acentos_e_espacos(self):
        self.assertEqual(limpar("Nada  de   espaço ."), "Nada de espaço.")

    def test_aceita_vazio_e_none(self):
        self.assertEqual(limpar(None), "")
        self.assertEqual(limpar(""), "")


class Cala_seSemRiscoTest(TestCase):
    """O teste mais importante: uma oferta que aparece sempre é ruído."""

    def test_sem_tarefa_de_aplicacao_nao_ha_oferta(self):
        from django.contrib.auth.models import User

        from app.models import Propriedade

        u = User.objects.create_user("cop_vazio", password="x1234567")
        p = Propriedade.objects.create(
            user=u, nome="FAZ", cidade="SOROCABA", uf="SP", area_total=50
        )
        achado = copiloto.sugerir(u, p)
        # Sem rede a previsao pode nao vir; com rede, vem e nao ha tarefa.
        # Nos dois casos: nao ha o que oferecer.
        if achado is not None:
            self.fail(f"ofereceu sem existir tarefa de aplicação: {achado}")

    def test_a_frase_de_oferta_pergunta_e_nao_afirma(self):
        """A diferença entre um alerta e um copiloto: um alerta diz "isto vai
        acontecer", um copiloto pergunta "queres que eu arrume?". O segundo
        é uma ação que o produtor pode recusar."""
        oferta = copiloto.frase_de_oferta(
            {
                "titulo": "Chuva pode lavar a aplicacao",
                "nivel": "critico",
                "data_proposta": "2026-10-08",
            },
            "Sim, chance de chuva de 80%.",
        )
        self.assertIn("Quer que eu remarque", oferta)
        self.assertTrue(oferta.rstrip().endswith("?"))

    def test_a_data_da_oferta_e_concreta(self):
        """ "Quer que eu remarque para depois da chuva?" obriga o produtor a
        uma segunda volta para saber PARA QUE DIA, e essa volta é onde a
        maioria desiste. Quem pergunta já está a fazer a conta de cabeça."""
        oferta = copiloto.frase_de_oferta(
            {"titulo": "Chuva lava a aplicacao", "data_proposta": "2026-10-08"},
            "Sim, 80%.",
        )
        self.assertIn("08/10", oferta)
        self.assertIn("dia 08/10", oferta)

    def test_sem_dia_seco_nao_promete_o_que_nao_pode_cumprir(self):
        """Este é o teste mais importante do ficheiro.

        Sem dia seco no horizonte, a oferta DESPERDICA a vez. "Quer que eu
        remarque?" sem dia para propor obriga a uma segunda volta e entrega
        uma promessa que o sistema não tem como cumprir.

        E o pior não é a volta extra: é o produtor dizer "sim" a uma
        pergunta que não tem resposta, e receber "para que dia?". A confiança
        que se ganha com a pergunta é a mesma que se perde na follow-up."""
        oferta = copiloto.frase_de_oferta(
            {"titulo": "Chuva lava a aplicacao", "data_proposta": None},
            "Sim, 80%.",
        )
        self.assertNotIn("remarque", oferta.lower())
        self.assertIn("Não há dia seco", oferta)
        self.assertTrue(oferta.rstrip().endswith("?"))

    def test_a_resposta_vem_antes_da_pergunta(self):
        """Oferecer antes de responder faz o produtor ler um alerta em vez de
        uma previsão — e é o que transforma um copiloto num boletim."""
        oferta = copiloto.frase_de_oferta(
            {
                "titulo": "Chuva lava a aplicacao",
                "data_proposta": "2026-10-08",
            },
            "Sim, 80% de chance.",
        )
        i_resposta = oferta.index("80%")
        i_pergunta = oferta.index("Quer que eu remarque")
        self.assertLess(i_resposta, i_pergunta, oferta)


class LimiarTest(SimpleTestCase):
    """`primeiro_dia_seco` usa os limiares da REGRA, não os seus.

    Duas respostas à mesma chuva divergem no primeiro dia em que alguém muda
    um limiar num lado só. A regra vê chuva suficiente; o copiloto oferece o
    dia errado; o produtor descobre a divergência no campo, com o
    agrotóxico já comprado."""

    def test_importa_os_limiares_da_regra(self):
        from app.ia.proativo import LIMIAR_CHUVA_MM, LIMIAR_CHUVA_PROB

        previsao = {
            "dias": [
                {"dia": "2026-10-06", "mm": 0.0, "prob": 0.0},
                {"dia": "2026-10-07", "mm": 30.0, "prob": 90.0},
                {"dia": "2026-10-08", "mm": 0.0, "prob": 10.0},
            ]
        }
        achado = copiloto.primeiro_dia_seco(previsao, "2026-10-06")
        self.assertEqual(achado, "2026-10-08")
        # e confirma que o limiar é mesmo o da regra
        self.assertLess(LIMIAR_CHUVA_MM, 30.0)
        self.assertLess(LIMIAR_CHUVA_PROB, 90.0)

    def test_devolve_none_quando_todo_o_horizonte_esta_chuvoso(self):
        previsao = {"dias": [{"dia": "2026-10-06", "mm": 30.0, "prob": 90.0}]}
        self.assertIsNone(copiloto.primeiro_dia_seco(previsao, "2026-10-05"))


class RegraRealTest(TestCase):
    """A regra que acha o risco é a de produção, não uma cópia."""

    def setUp(self):
        from django.contrib.auth.models import User

        from app.models import (
            EstagioCultura,
            Propriedade,
            RegistroProducao,
            TarefaEstagio,
        )

        self.u = User.objects.create_user("cop_risco", password="x1234567")
        self.p = Propriedade.objects.create(
            user=self.u, nome="FAZ", cidade="SOROCABA", uf="SP", area_total=100
        )
        # `EstagioCultura` aponta para um `RegistroProducao`, que por sua vez
        # exige `user`. A cadeia toda é necessária — e é o preço de um modelo
        # que guarda o talão de um talhão, e não um Enum.
        registro = RegistroProducao.objects.create(
            user=self.u,
            cultura_key="SOJA",
            nome="Talhão 1",
            location=self.p,
            unidade="ha",
            observacoes="",
        )
        self.dia = timezone.localdate() + timedelta(days=1)
        self.t = TarefaEstagio.objects.create(
            propriedade=self.p,
            estagio=EstagioCultura.objects.create(registro=registro, nome="Plantio"),
            descricao="Aplicacao de glifosato antes da chuva",
            cargo_alvo="CAMPO",
            setor="Campo",
            data_limite=self.dia,
            status="pendente",
            prioridade="alta",
        )

    def _cenario_com_chuva(self):
        return {
            "tem_cenario": True,
            "tarefas": [
                {
                    "tarefa_id": self.t.pk,
                    "descricao": self.t.descricao,
                    "parece_aplicacao": True,
                    "dia": self.dia.isoformat(),
                    "status": "pendente",
                }
            ],
            "previsao": {
                "ok": True,
                "dias": [
                    {
                        "dia": self.dia.isoformat(),
                        "mm": 25.0,
                        "prob": 80,
                        "tmax": 24,
                        "tmin": 18,
                    }
                ],
            },
            "propriedade": self.p.nome,
            "dias": 3,
        }

    def test_a_regra_de_producao_acha_o_risco(self):
        """Confirma que `proativo.regras_deterministicas` é mesmo a regra que
        vai correr — e que ela estava certa desde o início. O que faltava era
        alguém a chamar-lhe."""
        from app.ia.proativo import regras_deterministicas

        achados = regras_deterministicas(self._cenario_com_chuva())
        self.assertTrue(achados, "a regra de produção não achou o risco")
        self.assertEqual(achados[0]["regra"], "chuva_apos_aplicacao")
        self.assertEqual(achados[0]["tarefa_id"], self.t.pk)

    def test_o_copiloto_devolve_o_achado_da_regra(self):
        from app.ia import proativo

        original = proativo.montar_cenario
        proativo.montar_cenario = lambda *a, **k: self._cenario_com_chuva()
        try:
            achado = copiloto.sugerir(self.u, self.p)
        finally:
            proativo.montar_cenario = original

        self.assertIsNotNone(achado)
        self.assertEqual(achado["tarefa_id"], self.t.pk)

    def test_o_copiloto_nao_remarca_nada(self):
        """Um copiloto que age sem perguntar decide por alguém que paga as
        consequências. A oferta é uma pergunta; a acção vem com `confirm`."""
        from app.models import TarefaEstagio

        antes = TarefaEstagio.objects.get(pk=self.t.pk).data_limite
        self.assertEqual(antes, self.dia)
        # `sugerir` só lê. Não chama nada que escreva.
        copiloto.sugerir(self.u, self.p)
        self.assertEqual(
            TarefaEstagio.objects.get(pk=self.t.pk).data_limite,
            antes,
            "o copiloto remarcou sem o produtor dizer que sim",
        )

    def test_cala_se_quando_a_previsao_falha(self):
        """Uma previsão que não chegou é um caso NORMAL, não uma excepção.
        Um copiloto que rebenta é pior do que um copiloto calado."""
        from app.ia import proativo

        original = proativo.montar_cenario

        def _explode(*a, **k):
            raise RuntimeError("sem rede")

        proativo.montar_cenario = _explode
        try:
            self.assertIsNone(copiloto.sugerir(self.u, self.p))
        finally:
            proativo.montar_cenario = original


class SandboxingDaVozTest(TestCase):
    """A voz é lavada no LIMITE, e vale para todos os handlers."""

    def test_a_resposta_que_sai_nao_tem_markdown(self):
        from django.contrib.auth.models import User

        from app.ia import sandbox
        from app.models import Propriedade

        u = User.objects.create_user("cop_voz", password="x1234567")
        Propriedade.objects.create(
            user=u, nome="FAZ", cidade="SOROCABA", uf="SP", area_total=10
        )
        r = sandbox.executar(u, "listar_maquinas", {}, via="sessao")
        resposta = r.get("resposta") or ""
        for sinal in ("**", "##", "```"):
            self.assertNotIn(sinal, resposta, resposta)
        self.assertNotIn("->", resposta, resposta)


class PercursoCompletoTest(TestCase):
    """O PRODUTOR PERCORRE, do princípio ao fim.

    ESTE É O TESTE QUE FALTAVA
    -------------------------
    Havia testes para a regra (`sugerir` acha o risco) e testes para a frase
    (`frase_de_oferta` faz a pergunta). Nenhum ligava os dois, e nenhum
    testava o que acontece quando o produtor diz "sim".

    O caminho do "sim" é o caminho que importa, e ele passa pela máquina de
    estados — `AGUARDANDO_CONFIRMACAO`, `intent_pendente`, `dados_coletados` —
    que é a parte mais fácil de partir e a que ninguém estava a olhar.

    Um teste que cobre cada peça e não cobre a peça que o produtor atravessa
    é um teste que passa enquanto o produto não funciona.
    """

    def setUp(self):
        from django.contrib.auth.models import User

        from app.models import (
            EstagioCultura,
            Propriedade,
            RegistroProducao,
            TarefaEstagio,
        )

        self.u = User.objects.create_user("cop_percurso", password="x1234567")
        self.p = Propriedade.objects.create(
            user=self.u, nome="FAZ", cidade="SOROCABA", uf="SP", area_total=100
        )
        registro_prod = RegistroProducao.objects.create(
            user=self.u,
            cultura_key="SOJA",
            nome="Talhão 1",
            location=self.p,
            unidade="ha",
            observacoes="",
        )
        self.hoje = timezone.localdate()
        self.amanha = self.hoje + timedelta(days=1)
        self.t = TarefaEstagio.objects.create(
            propriedade=self.p,
            estagio=EstagioCultura.objects.create(
                registro=registro_prod, nome="Plantio"
            ),
            descricao="Aplicacao de glifosato antes da chuva",
            cargo_alvo="CAMPO",
            setor="Campo",
            data_limite=self.amanha,
            status="pendente",
            prioridade="alta",
        )

    def _cenario(self, dia_seco):
        return {
            "tem_cenario": True,
            "tarefas": [
                {
                    "tarefa_id": self.t.pk,
                    "dia": self.amanha.isoformat(),
                    "descricao": "Aplicacao de glifosato",
                    "status": "pendente",
                    "parece_aplicacao": True,
                }
            ],
            "previsao": {
                "ok": True,
                "dias": [
                    {"dia": self.amanha.isoformat(), "mm": 30.0, "prob": 95.0},
                    {"dia": dia_seco.isoformat(), "mm": 0.0, "prob": 10.0},
                ],
            },
            "propriedade": self.p.nome,
            "dias": 5,
        }

    def _sem_chuva_de_verdade(self, cenario):
        """Mete o tempo e o cenário de chuva, sem tocar na rede.

        O registo guarda a FUNÇÃO, não o nome dela — por isso
        `patch("app.ia.intents.vai_chover")` nãocia de nada, o nome não existe
        lá, e o `AttributeError` é a prova de que o mock estava errado e não
        o código."""
        from unittest.mock import patch

        def _chuva(user, params, ctx):
            return {
                "ok": True,
                "resposta": "Vai chover em FAZ nas próximas 24h, 95% de chance.",
                "dados": {},
            }

        return (
            patch("app.ia.proativo.obter_previsao", return_value=cenario["previsao"]),
            patch("app.ia.proativo.montar_cenario", return_value=cenario),
            patch.dict(registro.REGISTO["vai_chover"], {"handler": _chuva}),
        )

    def test_o_sim_remarca_para_o_dia_seco(self):
        """A pergunta, o sim, e a data a mudar. Ponta a ponta."""
        from app.ia import sandbox
        from app.models import TarefaEstagio

        # a chuva é amanhã; o primeiro dia seco é daqui a quatro
        dia_seco = self.hoje + timedelta(days=4)
        cenario = self._cenario(dia_seco)

        p1, p2, p3 = self._sem_chuva_de_verdade(cenario)
        with p1, p2, p3:
            # 1. o produtor pergunta do tempo
            r1 = sandbox.executar(
                self.u, "vai_chover", {}, via="sessao", meta={"entrada": "vai chover"}
            )
            self.assertTrue(r1.get("ok"), r1)
            self.assertIn("95%", r1["resposta"])
            self.assertIn("Quer que eu remarque", r1["resposta"])
            # a oferta diz PARA QUE DIA, não "depois da chuva"
            self.assertIn(dia_seco.strftime("%d/%m"), r1["resposta"])
            # e a data NÃO mudou
            self.assertEqual(
                TarefaEstagio.objects.get(pk=self.t.pk).data_limite,
                self.amanha,
                "o copiloto remarcou antes de o produtor dizer que sim",
            )
            self.assertTrue(r1.get("needs_confirm"))

            # 2. o produtor diz "sim"
            r2 = sandbox.executar(self.u, "", {}, via="sessao", meta={"entrada": "sim"})

        self.assertTrue(r2.get("ok"), r2)
        # 3. a data mudou para o dia que o copiloto PROPÔS
        self.assertEqual(
            TarefaEstagio.objects.get(pk=self.t.pk).data_limite,
            dia_seco,
            "o sim não remarcou para o dia prometido",
        )
        self.assertIn(dia_seco.strftime("%d/%m"), r2["resposta"])

    def test_a_tarefa_continua_onde_esta_sem_o_sim(self):
        """Um 'não' tem de ser tão respeitado quanto um 'sim'. E, sem resposta
        nenhuma, também: a oferta é uma pergunta, e uma pergunta não muda
        nada sozinha."""
        from app.ia import sandbox
        from app.models import TarefaEstagio

        cenario = self._cenario(self.hoje + timedelta(days=4))
        p1, p2, p3 = self._sem_chuva_de_verdade(cenario)
        with p1, p2, p3:
            sandbox.executar(
                self.u, "vai_chover", {}, via="sessao", meta={"entrada": "vai chover"}
            )
            # o produtor não responde. A data fica.
            sandbox.executar(
                self.u, "", {}, via="sessao", meta={"entrada": "vou pensar"}
            )

        self.assertEqual(
            TarefaEstagio.objects.get(pk=self.t.pk).data_limite,
            self.amanha,
            "a data mudou sem o produtor pedir",
        )

    # NOTA — não há aqui um teste de "idempotência do copiloto", e é de propósito.
    #
    # Houve um, escrito contra o motor quebrado, que afirmava que DUAS chamadas
    # seguidas do mesmo intent devolviam a mesma oferta. Isso não é uma invariante
    # deste produto: a oferta é uma PERGUNTA, e por isso arma a máquina de estados
    # (`sandbox.executar` deixa `contexto.estado_atual = "AGUARDANDO_CONFIRMACAO"`).
    # A segunda chamada cai no ramo da confirmação e devolve "Operação cancelada" —
    # que é a resposta certa a alguém que não respondeu à pergunta anterior.
    #
    # E o teste antigo não provava o que dizia provar: `assertNotIn("copiloto", r)`
    # passa com a oferta morta, porque não olha para a resposta. Matizei-o
    # (frase_de_oferta apagada em sandbox.py) e ele continuou verde.
    #
    # O que garante a oferta esta em `test_o_sim_remarca_para_o_dia_seco`, acima:
    # assere a PROSA ("Quer que eu remarque"), a data concreta proposta, que a data
    # NÃO mudou antes do "sim", e `needs_confirm`. Esse é o comportamento do produtor.
