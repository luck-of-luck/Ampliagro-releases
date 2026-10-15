"""A superficie de escrita da IA, provada contra a fazenda de outro.

## PORQUE ESTE FICHEIRO EXISTE

MEDIDO 2026-10-05. Das 36 intents que ESCREVEM, 3 aceitam um identificador
que vem do cliente:

    ligar_proatividade      propriedade_id
    revogar_endpoint_iot    endpoint_id
    emitir_alerta_proativo  cenario_id

E sao exactamente estas que podem atravessar de um produtor para outro. As
outras 33 escrevem objectos novos a partir do `user` em contexto e nao tem
por onde entrar um id alheio — a garantia delas e' estrutural.

Uma guarda que ninguem exercita nao e' uma guarda: e' uma linha de codigo.
Este ficheiro chama as tres com o id do VIZINHO e afirma que nada acontece.

## A REGRA GUARDADA

Nao interessa o codigo de resposta. O que interessa e' a INVARIANTE: **o
recurso alheio nao mudou**. Por isso cada teste afirma sobre o DADO, alem do
codigo — um handler que devolvesse erro DEPOIS de gravar passaria uma
assercao de codigo.

## MEDIDO: o comportamento REAL, depois de tres tentativas

A primeira versao deste ficheiro afirmava que `ligar_proatividade`
SUBSTITUIA em silencio: pedia-se a fazenda do vizinho e o sistema aplicava
na do dono sem dizer. Essa affirmacao **era falsa**, e veio de uma medicao
feita antes de a API estar confirmada.

MEDIDO com a API certa:

    id alheio   pk=2 -> ok=False  erro="propriedade_id 2 recus..."
    id proprio  pk=1 -> ok=True   dados={'propriedade': 'MINHA'}

O que acontece e' RECUSA EXPLICITA, com o parametro nomeado no erro. Nao ha
omissao. Por isso nao existe aqui nenhum teste sobre "substituicao
silenciosa": seria um teste a fixar um comportamento que nao existe, e o seu
unico efeito seria mandar o proximo agente "arrumar" uma funcao correcta.

O que este ficheiro guarda e' o que foi medido: a recusa, e o facto de a
mesma chamada com o id PROPRIO funcionar. A segunda metade e' a que costuma
faltar — uma guarda que rejeita o dono tambem e' uma falha.

## O QUE ISTO NAO COBRE

`endpoint_id` fica por testar: construir um `IotEndpoint` exige um
`DynamicApp` e nao era o alvo mais directo. E os comandos de management, que
nao passam pelo sandbox e correm com conta de sistema — caminho que nenhum
teste de tenant aqui alcanca.
"""

from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from app.models import IACenarioPendente, Propriedade


def _mk(nome):
    return User.objects.create_user(username=nome, password="x-prova-12345")


class EscritaNaoAtravessaTenantTest(TestCase):
    """Um produtor nao escreve, nao altera e nao apaga nada de outro."""

    def setUp(self):
        self.eu = _mk("vizinho-a")
        self.eles = _mk("vizinho-b")

        self.minha = Propriedade.objects.create(
            user=self.eu, nome="MINHA", area_total=10, uf="MT", cidade="Sorriso"
        )
        self.deles = Propriedade.objects.create(
            user=self.eles, nome="DELE", area_total=10, uf="GO", cidade="Goias"
        )

    # ── 1. propriedade_id ────────────────────────────────────────────────────
    def test_ligar_proatividade_recusa_propriedade_alheia(self):
        """`propriedade_id` do outro: recusado, nomeado e sem tocar em nada.

        Se passasse, ligava o motor proativo de um produtor DENTRO da fazenda
        de outro: a IA passaria a ler plantios, talhoes e contas de quem nao
        pediu, e a avisar sozinho.
        """
        from app.amplia_mcp import executar_para
        from app.models import ProativoPreferencia

        r = executar_para(
            self.eu,
            "amplia_ligar_proatividade",
            {"propriedade_id": self.deles.pk, "ativo": True, "confirm": True},
        )

        self.assertIs(
            r.get("ok"),
            False,
            "a propriedade de outro foi aceite: %r. A IA ia ler a fazenda de "
            "quem nao pediu." % r,
        )
        # o erro tem de NOMEAR o parametro, para o produtor saber o que
        # trocar. Um erro generico ("nao encontrado") e' indistinguivel de
        # um id errado de um id de outra pessoa.
        self.assertIn(
            str(self.deles.pk),
            str(r.get("erro") or ""),
            "o erro nao diz qual `propriedade_id` foi recusado: %r. Quem "
            "chamou nao sabe se mandou o numero errado ou se foi barrado."
            % r.get("erro"),
        )

        # a invariante que importa: nada na fazenda do vizinho
        self.assertEqual(
            ProativoPreferencia.objects.filter(propriedade=self.deles).count(),
            0,
            "TOQUEI A FAZENDA DE OUTRO, apesar da resposta dizer recusa",
        )

    def test_ligar_proatividade_aceita_a_propria(self):
        """A mesma chamada, com o id do dono: tem de funcionar.

        Um guard que rejeita tudo nao e' um guard — e' uma queda. E a falha
        que passa mais despercebida, porque ninguem reclama de um sistema que
        recusa tudo: reclama-se do inverso.
        """
        from app.amplia_mcp import executar_para
        from app.models import ProativoPreferencia

        r = executar_para(
            self.eu,
            "amplia_ligar_proatividade",
            {"propriedade_id": self.minha.pk, "ativo": True, "confirm": True},
        )

        self.assertIs(r.get("ok"), True, r)
        self.assertEqual(
            (r.get("dados") or {}).get("propriedade"),
            self.minha.nome,
            "a resposta nao diz que propriedade foi tocada: %r" % (r.get("dados"),),
        )
        self.assertEqual(
            ProativoPreferencia.objects.filter(propriedade=self.minha).count(),
            1,
            "disse que ligou e nao criou preferencia: o nome nao bate com o "
            "que foi feito",
        )

    # ── 2. cenario_id ────────────────────────────────────────────────────────
    def _cenario(self, user, fingerprint):
        return IACenarioPendente.objects.create(
            user=user,
            propriedade=self.deles if user is self.eles else self.minha,
            contexto={"origem": "prova"},
            cenario={"risco": "chuva"},
            fingerprint=fingerprint,
            situacao="pendente",
            tentativas=0,
            expira_em=timezone.now() + timedelta(days=1),
        )

    def test_emitir_alerta_recusa_cenario_alheio(self):
        """Um cenario pendente de outro nao pode ser consumido.

        Consumir o cenario dispara um alerta em nome de QUEM O CRIOU. Com o
        id do vizinho, eu provocava um aviso no painel dele — e o motor
        proativo dele trataria o meu alarme como accao sua.
        """
        from app.amplia_mcp import executar_para

        cenario = self._cenario(self.eles, "alheio-1")

        r = executar_para(
            self.eu,
            "amplia_emitir_alerta_proativo",
            {"cenario_id": cenario.pk, "confirm": True},
        )

        nao_passou = r.get("ok") is False or bool(r.get("erro"))
        self.assertTrue(
            nao_passou,
            "o cenario pendente de outro foi aceite: %r. O alerta sairia em "
            "nome de quem o criou, num painel de outro produtor." % r,
        )
        self.assertEqual(
            IACenarioPendente.objects.get(pk=cenario.pk).situacao,
            "pendente",
            "o cenario de outro foi consumido: disparei um alerta que ninguem "
            "pediu, num painel de outro",
        )

    # ── a porta mais larga ───────────────────────────────────────────────────
    def test_user_id_do_corpo_nao_substitui_o_user_em_contexto(self):
        """`user_id` no corpo nao escolhe o dono.

        E' a porta mais larga: se um handler aceitar `user_id` do corpo sem
        conferir, o produtor escreve COMO QUISER. Este intent ja confere;
        este teste existe para que ninguem o desfaça.
        """
        from app.amplia_mcp import executar_para

        cenario = self._cenario(self.eu, "meu-1")
        r = executar_para(
            self.eu,
            "amplia_emitir_alerta_proativo",
            {
                "cenario_id": cenario.pk,
                "user_id": self.eles.pk,
                "confirm": True,
            },
        )
        nao_passou = r.get("ok") is False or bool(r.get("erro"))
        self.assertTrue(
            nao_passou,
            "um `user_id` alheio no corpo passou: %r. A partir daqui, "
            "qualquer intent que aceite `user_id` e' uma porta aberta." % r,
        )
        self.assertEqual(
            IACenarioPendente.objects.get(pk=cenario.pk).situacao,
            "pendente",
            "o cenario foi consumido apesar do `user_id` alheio",
        )
