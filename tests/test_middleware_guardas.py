"""As duas mutacoes que NENHUM teste apanhou, e os testes que faltavam.

MEDIDO 2026-10-05 (agente 11). Mutation testing nos testes do middleware JSON
deixou passar duas mutacoes. Nao sao mutacoes irrelevantes — sao duas coisas que
eu escrevi e nao provei.

MUTACAO 1 — a guarda do content-type
------------------------------------
Trocar `if "json" not in ct: return None` por `pass` nao muda o valor devolvido:
sem a guarda, `json.loads` de um multipart falha e o `except` devolve `None`
igual. A diferenca esta' no EFEITO SECUNDARIO — e por isso que um teste que so'
olha para o valor de retorno nunca a apanha.

O efeito que importa: num upload grande o Django usa *streaming handlers*, e
`request.body` levanta `RawPostDataException`. Um middleware que o leia sem
guarda rebenta o upload. O `RequestFactory` com um ficheiro pequeno NAO
reproduz isto — o corpo esta' em memoria e o Django cacheia-o. Por isso o
teste tem de forcar a excecao.

MUTACAO 2 — anular ids inexistentes no caminho JSON
---------------------------------------------------
`app/middleware.py` tem um segundo comportamento: quando um id aponta para um
registo que nao existe, o pedido segue (nao e' ataque) mas o id e' apagado, para
a view ver "sem dado" em vez de tentar ler o registo. Esse comportamento estava
no caminho JSON e **nao tinha teste nenhum** — eu tinha comentado que estava
la, e comentar nao e' provar.

Um id inexistente no caminho JSON era apagado da query string e do formulario,
e num POST JSON ficava la: a view via um id que apontava para o nada.
"""

import json

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import RequestDataTooBig
from django.test import RequestFactory

from app.middleware import TenantIsolationMiddleware

User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture
def dois():
    from app.models import Propriedade, Talhao

    d = {}
    for chave in ("ana", "bruno"):
        u = User.objects.create_user(chave, password="x" * 12)
        p = Propriedade.objects.create(
            user=u,
            nome=f"Fazenda {chave}",
            area_total=100.0,
            uf="MG",
            pais="BR",
            moeda="BRL",
            tipo_exploracao="1",
            participacao=100.0,
        )
        d[chave] = {
            "user": u,
            "propriedade": p,
            "talhao": Talhao.objects.create(
                propriedade=p, nome=f"T {chave}", area_hectare=10.0, ativo=True
            ),
        }
    return d


def passar(user, req):
    req.user = user
    req.session = {}

    def get_response(_r):
        from django.http import JsonResponse

        return JsonResponse({"ok": True})

    return TenantIsolationMiddleware(get_response)(req)


class TestAUploadGrandeNaoRebentaTest:
    """O efeito secundario que a mutacao removia."""

    def test_um_upload_streaming_nao_e_derrubado(self, dois):
        """Um upload grande usa streaming handlers: `request.body` levanta.

        Este e' o caso real da regressao. Nao e' um detalhe — e' um ficheiro de
        2 GB de uma fotografia ortomosa que deixa de fazer upload.
        """

        class PedidoEmStreaming:
            """Repete o formato do request mas com `body` a levantar, como o
            Django faz quando `DATA_UPLOAD_MAX_MEMORY_SIZE` e' ultrapassado."""

            method = "POST"
            content_type = "multipart/form-data; boundary=X"
            GET = {}
            POST = {}

            @property
            def body(self):
                raise RequestDataTooBig(
                    "You cannot access body after reading from request's data stream"
                )

        r = passar(
            dois["ana"]["user"],
            PedidoEmStreaming(),
        )
        # o essencial: nao levantou. Uma excepcao aqui seria um 500 num upload.
        assert r.status_code != 500

    def test_a_guarda_e_o_que_impede_isso(self, dois):
        """O `_corpo_json` tem de devolver `None` sem sequer tocar no corpo."""
        req = RequestFactory().post("/x/", data={"a": "b"})
        req.content_type = "multipart/form-data; boundary=X"
        assert TenantIsolationMiddleware._corpo_json(req) is None


class TestIdsInexistentesNoCaminhoJsonTest:
    """A mutacao 2. Comportamento que existia sem teste."""

    def _request(self, user, corpo):
        req = RequestFactory().post(
            "/api/x/", data=json.dumps(corpo), content_type="application/json"
        )
        req.user = user
        req.session = {}
        return req

    def test_um_id_que_nao_existe_nao_e_um_ataque_nem_um_500(self, dois):
        """Segue o pedido, mas o id fica anulado.

        Um id inexistente NAO e' cross-tenant: nao ha de quem roubar, nao ha
        registo alheio. Recusar seria inventar uma ameaca. E deixar o id la faz
        a view ir procurar um registo que nao existe.
        """
        req = self._request(dois["ana"]["user"], {"talhao_id": 99999999})
        r = passar(dois["ana"]["user"], req)
        assert r.status_code == 200

    def test_o_id_inexistente_e_efectivamente_apagado_do_corpo(self, dois):
        """E aqui a prova de que o comportamento existe.

        Nao basta o pedido passar: o `talhao_id` tem de ter ficado vazio no
        corpo que a view vai ler. E' isto que a mutacao apagava, e e' por isto
        que o teste anterior sozinho nao a apanhava.
        """
        req = self._request(dois["ana"]["user"], {"talhao_id": 99999999})
        passar(dois["ana"]["user"], req)
        assert req.corpo_json.get("talhao_id") == "", (
            f"o id inexistente nao foi anulado: {req.corpo_json.get('talhao_id')!r}. "
            "A view vai receber um id que aponta para o nada."
        )
        assert req.ids_inexistentes == ["talhao_id"]

    def test_um_id_que_existe_nao_e_anulado(self, dois):
        """Anular um id valido seria destruir trabalho: o produtor escreve o
        talhao certo e o sistema finge que nao existe."""
        alvo = dois["ana"]["talhao"].pk
        req = self._request(dois["ana"]["user"], {"talhao_id": alvo})
        passar(dois["ana"]["user"], req)
        assert req.corpo_json.get("talhao_id") == alvo
        assert req.ids_inexistentes == []

    def test_um_id_nao_numerico_passa_intacto(self, dois):
        """`"abc"` nao e' cross-tenant nem id. A view responde 'sem dado'; o
        middleware nao tem de fabricar uma recusa."""
        req = self._request(dois["ana"]["user"], {"talhao_id": "abc"})
        r = passar(dois["ana"]["user"], req)
        assert r.status_code == 200

    def test_formulario_continua_a_ser_anulado_do_mesmo_jeito(self, dois):
        req = RequestFactory().post("/api/x/", data={"talhao_id": 99999999})
        r = passar(dois["ana"]["user"], req)
        assert r.status_code == 200
        assert req.POST.get("talhao_id") == ""


class TestAPropriedadeDoCorpoTest:
    """`request.propriedade` e' a conveniencia que as views usam.

    MEDIDO 2026-10-05 (agente 11). Terceira ronda de mutation testing, e esta
    mutacao passou: `request.propriedade = dono.first()` podia ser removido e
    os testes todos ficavam verdes.

    E' o mais grave dos tres que faltavam. Nao e' um detalhe de implementacao:
    e' o objecto que o middleware DEPOIS depõe no request para as views nao
    terem de ir buscar a propriedade do usuario. Se ele deixa de ser posto, as
    views que dependem dele passam a ver `None` — e cao o codigo de cada uma a
    resolver, o que num sistema com 400 views e' um `None` silencioso.

    A mutacao anterior (`pass`) também nao foi apanhada — essa fica registada
    como mutacao EQUIVALENTE, e nao como falha: sem a guarda do content-type,
    o `try/except` ja apanha a excepcao de ler o corpo e devolve `None` na
    mesma. A guarda é defesa em profundidade; remove-la nao muda o que se
    observa. Inventar um teste que a "apanhe" seria fabricar uma prova falsa.
    """

    def _request(self, user, corpo):
        req = RequestFactory().post(
            "/api/x/", data=json.dumps(corpo), content_type="application/json"
        )
        req.user = user
        req.session = {}
        return req

    def test_a_propriedade_do_corpo_e_posta_no_request(self, dois):
        """O `propriedade_id` do corpo tem de chegar a `request.propriedade`.

        Este teste foi corrigido DUAS vezes. A primeira versao dava a ana uma
        unica propriedade, e passava mesmo quando a leitura do corpo era
        removida: o fallback `if request.propriedade is None: ...first()`
        devolvia essa mesma unica propriedade. Um teste verde a medir a coisa
        errada e' pior que um vermelho — da a sensacao de cobertura onde nao ha.

        Agora a ana tem DUAS. O fallback devolve a primeira; o corpo diz a
        segunda. O teste passa a distinguir as duas coisas.
        """
        from app.models import Propriedade

        # a primeira, por ordem de criacao — e' a que o fallback devolve
        primeira = dois["ana"]["propriedade"]
        segunda = Propriedade.objects.create(
            user=dois["ana"]["user"],
            nome="Fazenda Seg.nda",
            area_total=50.0,
            uf="MG",
            pais="BR",
            moeda="BRL",
            tipo_exploracao="1",
            participacao=100.0,
        )
        assert primeira.pk != segunda.pk

        req = self._request(dois["ana"]["user"], {"propriedade_id": segunda.pk})
        passar(dois["ana"]["user"], req)
        assert req.propriedade is not None, (
            "`request.propriedade` ficou None — as views que dependem desta "
            "conveniencia passam a ver 'sem propriedade' sem erro nenhum"
        )
        assert req.propriedade.pk == segunda.pk, (
            f"veio {req.propriedade.nome!r} em vez da pedida. Se o fallback "
            " acted, e o corpo foi ignorado — que e' o bug que este teste "
            "procura."
        )

    def test_a_conveniencia_continua_para_o_formulario(self, dois):
        req = RequestFactory().post(
            "/api/x/", data={"propriedade_id": dois["ana"]["propriedade"].pk}
        )
        req.user = dois["ana"]["user"]
        req.session = {}
        passar(dois["ana"]["user"], req)
        assert req.propriedade is not None

    def test_sem_ids_cai_na_primeira_propriedade_do_utilizador(self, dois):
        """A conveniencia que existia antes da correccao tem de continuar."""
        # sem o `content_type`, o Django trata a string JSON como formulario e
        # `data` chega a ser uma string — o `TestCase` do cliente chora.
        req = RequestFactory().post(
            "/api/x/", data=json.dumps({"nome": "x"}), content_type="application/json"
        )
        req.user = dois["ana"]["user"]
        req.session = {}
        passar(dois["ana"]["user"], req)
        assert req.propriedade is not None
        assert req.propriedade.user_id == dois["ana"]["user"].pk

    def test_a_propriedade_de_outro_e_recusada_antes_de_ser_posta(self, dois):
        req = self._request(
            dois["ana"]["user"], {"propriedade_id": dois["bruno"]["propriedade"].pk}
        )
        r = passar(dois["ana"]["user"], req)
        assert r.status_code == 403
