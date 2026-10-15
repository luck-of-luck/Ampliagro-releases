"""O worker proativo tem de respeitar a revogacao — e NAO passa por HTTP.

O QUE ESTE TESTE PROVA
=====================
`perfil.ativo_servidor = False` significa "o produtor desligou este servidor".
A primeira correcao foi o `ServidorRevogadoMiddleware`, que e' um ponto unico e
bom — mas e' um ponto **HTTP**.

`app/ia/proativo_tasks.py::varrer()` e' o worker que avalia cada produtor e
grava alertas proativos. Ele:

  - nao tem `request`, logo nao entra no middleware;
  - chama `avaliar_usuario()` dentro de um `try/except`, que transformava uma
    eventual recusa em `usuarios_com_erro` e seguia para o proximo.

MEDIDO 2026-10-04: um servidor com `ativo_servidor=False` continuava a ser
avaliado e a receber alertas, com a fazenda dele como origem, e sem qualquer
erro visivel. O produtor tinha desligado o servidor na tela — e o sistema
continuava a falar-lhe em nome dele.

PORQUE ISTO E' UM TESTE E NAO UM AJUSTE NO MIDDLEWARE
=====================================================
Porque e' o mesmo modo de falha duas vezes. O `MERGED.md` regista-o: uma regra
que tem de valer em N sitios nao pode ser lembrada em N sitios. A fonte da regra
e' `app/services/revogacao.py`, e o que este teste garante e' que o worker
**descobre** essa fonte — em vez de ter a sua propria copia da condicao, que
seria correcta hoje e divergente amanha.

O QUE ESTE TESTE NAO AFIRMA
===========================
Nao afirma que o middleware pode sair. Ele continua a ser o primeiro filtro
(recusa antes de gastar uma query); este e' o segundo, e cobre quem nao passou
pelo primeiro.
"""

from django.contrib.auth.models import User
from django.test import TestCase

from app.ia.proativo_tasks import varrer
from app.models import PerfilUsuario, ProativoPreferencia, Propriedade


class WorkerProativoRespeitaRevogacaoTest(TestCase):
    def setUp(self):
        # A propriedade "debulk" so existe para o `setUp` ficar valido; cada
        # `_servidor` cria a sua (ver o docstring do helper).
        User.objects.create_user(username="dono", password="x1234567")
        Propriedade.objects.create(
            user=User.objects.get(username="dono"),
            nome="Fazenda Worker",
            area_total=10,
            uf="MT",
            cidade="X",
        )

    def _servidor(self, username, ativo):
        """Um servidor com a sua propriedade.

        `ProativoPreferencia.propriedade` é UNIQUE — uma preferência por
        propriedade — então dois servidores não podem partilhar a mesma. Não
        é um detalhe do teste: é a razão pela qual o worker avalia por
        utilizador e não por propriedade.
        """
        dono = User.objects.create_user(
            username=username + "_dono", password="x1234567"
        )
        prop = Propriedade.objects.create(
            user=dono, nome="Fazenda " + username, area_total=10, uf="MT", cidade="X"
        )
        u = User.objects.create_user(username=username, password="x1234567")
        PerfilUsuario.objects.update_or_create(
            user=u,
            defaults={
                "tipo_usuario": "servidor",
                "area_servidor": "CAMPO",
                "propriedade_vinculada": prop,
                "ativo_servidor": ativo,
            },
        )
        ProativoPreferencia.objects.update_or_create(
            user=u, defaults={"ativo": True, "propriedade": prop}
        )
        return u

    def test_um_servidor_revogado_nao_e_avaliado(self):
        """O caso que motivou o achado: desligado é não ser avaliado."""
        self._servidor("srv_revogado_worker", False)

        resumo = varrer()

        self.assertEqual(
            resumo["usuarios_avaliados"],
            0,
            "um servidor com ativo_servidor=False foi avaliado pelo worker. "
            "Ele nao passa pelo middleware, e a unica coisa que o parava era o "
            "`try/except` — que engolia a recusa e seguia para o proximo.",
        )
        self.assertEqual(
            resumo["usuarios_revogados"],
            1,
            "a revogacao tem de ser CONTADA, e nao somada ao `usuarios_pulado`. "
            "Um relatorio que diz 'pulados: 1 (teto)' quando o que houve foi "
            "revogacao e' um relatorio que nao serve para diagnosticar.",
        )

    def test_a_conta_de_revogados_esta_separada_das_outras(self):
        """
        As três causas de não-avaliar têm de ser distinguíveis. Somar a
        revogação ao `pulados` seria o mesmo erro que o `usuarios_com_erro`
        já foi, e que este ficheiro de testes documenta.
        """
        self._servidor("srv_revogado_1", False)
        self._servidor("srv_revogado_2", False)

        resumo = varrer()

        self.assertEqual(resumo["usuarios_revogados"], 2)
        self.assertEqual(
            resumo["usuarios_pulado"],
            0,
            "revogação contaminationou `usuarios_pulado`",
        )
        self.assertEqual(
            resumo["usuarios_com_erro"],
            0,
            "revogação entrou como `usuarios_com_erro` — ou seja, por dentro do "
            "`try/except`, que e' exactamente o caminho que a esconderia.",
        )

    def test_um_servidor_ativo_continua_a_ser_avaliado(self):
        """
        O outro lado do interruptor. Sem isto, um guarda que bloqueia sempre
        também passa os testes: `usuarios_avaliados == 0` e `revogados == 1`
        seriam verdadeiros nos dois casos.
        """
        self._servidor("srv_ativo_worker", True)

        resumo = varrer()

        self.assertEqual(
            resumo["usuarios_revogados"],
            0,
            "um servidor ACTIVO foi contado como revogado",
        )
        self.assertEqual(
            resumo["usuarios_avaliados"],
            1,
            "um servidor com ativo_servidor=True deixou de ser avaliado. "
            "`ativo_servidor` tem default=True: isto só pode acontecer se o "
            "guarda leu o flag ao contrário.",
        )

    def test_a_varredura_continua_para_os_outros(self):
        """
        Revogar um servidor não pode derrubar a varredura dos restantes — que
        é o que um `raise` dentro do loop faria.
        """
        self._servidor("srv_revogado_among", False)
        self._servidor("srv_ativo_among", True)

        resumo = varrer()

        self.assertEqual(resumo["usuarios_revogados"], 1)
        self.assertEqual(resumo["usuarios_avaliados"], 1)

    def test_regra_tem_fonte_unica(self):
        """
        O teste de arquitetura. Se o worker ganha a sua própria cópia da
        condição, passa a ter duas regras para o mesmo facto — e a segunda
        diverge sem que nada diga.

        É a mesma exigência que `app/services/revogacao.py` faz nos outros
        callers, e a que o `MERGED.md` traduz: *"tem de ser um sítio, e o resto
        descobre."*

        MEDE O CÓDIGO, NÃO A PROSA. Uma versão anterior deste teste lia o
        `getsource` e falhava porque o comentário que explica o defeito
        menciona `ativo_servidor` — o mesmo erro de
        `tests_pergunta_nao_e_resposta.cjs::_corpo_sem_docstring`, que documenta
        o caso de um teste que acusa o código por causa da frase que o
        documenta. Por isso vai por `ast`: interessa o acesso ao atributo, não
        a sua menção.
        """
        import ast
        import inspect

        from app.ia import proativo_tasks

        arvore = ast.parse(inspect.getsource(proativo_tasks))

        # Acesso ao atributo: `perfil.ativo_servidor`, `x["ativo_servidor"]`
        # excluído de propósito — subscript é chave de dicionário, não o flag.
        atributos = {
            node.attr
            for node in ast.walk(arvore)
            if isinstance(node, ast.Attribute) and node.attr == "ativo_servidor"
        }
        self.assertEqual(
            atributos,
            set(),
            "`proativo_tasks.py` lê `ativo_servidor` diretamente "
            f"({atributos}). A regra tem uma fonte, e é "
            "`app/services/revogacao.py`. Uma segunda leitura do flag aqui é "
            "uma segunda regra — correcta hoje, divergente amanhã, e sem nada "
            "que as compare.",
        )

        chamadas = {
            node.func.id
            for node in ast.walk(arvore)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        self.assertIn(
            "servidor_ativo",
            chamadas,
            "o worker tem de chamar `servidor_ativo()` de `app/services/revogacao.py`",
        )
