"""O Caderno de Campo tem de responder ao que o `sync.js` envia.

O QUE ESTE TESTE PROVA
======================
`app/static/js/pwa/sync.js` tem très métodos que fazem POST:

    :105  /api/caderno/notas/   JSON  {talhao_id, cultura_id, conteudo, tipo,
                                     latitude, longitude, offline_id}
    :144  /api/caderno/fotos/   FormData {note_id, image, caption}
    :252  /api/caderno/voice/   FormData {note_id, audio, transcription, duration}

MEDIDO 2026-10-04: **nenhuma das três rotas existia.** O produtor escrevia a
nota no meio do talhão, o `OfflineDB` guardava em `field_notes`, o sync levava
404, e o `.catch` fazia `console.error`. Sem erro no ecrã. O produtor tinha um
caderno no telemóvel que não existia em lado nenhum — e nunca soube.

O que havia era o outro lado: `app/models/caderno.py` (`NotaCampo`), a migration
`0065_nota_campo.py` e `app/api/views/caderno.py` (serializer + view). Ou seja,
**o furo estava numa linha: as rotas não estavam registadas em `urls.py`.** E um
furo numa linha é o mais difícil de ver, porque cada peça parece certa.

Este teste é o contrato. Ele envia **o payload exacto do `sync.js`**, não um
payload inventado por mim — porque um teste com um payload inventado passa
quando o cliente real e o servidor divergem, que é precisamente o defeito.

O QUE ESTE TESTE NÃO AFIRMA
===========================
Não afirma que `fotos/` e `voice/` estejam implementadas. Ambas devolvem **501**
com a lista do que falta, e isso é uma decisão, não uma falha: um 404 punha o
produtor a tentar outra vez; um 501 diz "isto não existe ainda, e aqui está o
que falta". O teste fixa o 501 para que a rota não possa desaparecer em
silêncio — cair para 404 seria voltar ao buraco.
"""

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from app.models import NotaCampo, Propriedade, Talhao


class CadernoDeCampoTest(TestCase):
    def setUp(self):
        self.dono = User.objects.create_user(
            username="dono_caderno", password="x1234567"
        )
        self.prop = Propriedade.objects.create(
            user=self.dono, nome="Fazenda Caderno", area_total=10, uf="MT", cidade="X"
        )
        self.talhao = Talhao.objects.create(
            propriedade=self.prop, nome="Talhao 1", area_hectare="5.00"
        )
        # Um segundo produtor, para o teste de tenancy ter contra quem falhar.
        self.outro = User.objects.create_user(
            username="outro_caderno", password="x1234567"
        )
        self.prop_outro = Propriedade.objects.create(
            user=self.outro, nome="Fazenda Alheia", area_total=10, uf="MT", cidade="X"
        )
        self.talhao_outro = Talhao.objects.create(
            propriedade=self.prop_outro, nome="Talhao Alheio", area_hectare="5.00"
        )

        self.client = Client()
        self.client.force_login(self.dono)

    def _payload_do_sync_js(self, **extra):
        """O corpo de `sync.js:105-120`, com os campos que ele manda."""
        payload = {
            "talhao_id": self.talhao.pk,
            "cultura_id": None,
            "conteudo": "pulgao no canto norte, folha com furos",
            "tipo": "praga",
            "latitude": -19.123456,
            "longitude": -57.654321,
            "offline_id": 1737000000000,
        }
        payload.update(extra)
        return payload

    def _post(self, **extra):
        return self.client.post(
            reverse("api-caderno-notas"),
            data=self._payload_do_sync_js(**extra),
            content_type="application/json",
        )

    # ── as três rotas existem ─────────────────────────────────────────────

    def test_as_tres_rotas_respondem(self):
        """A regressao que fecha o buraco: 404 = feature fantasma.

        MEDIDO 2026-10-05 (actualizacao). Este teste vivia com as tres rotas
        em 501. `nota_fotos` foi **implementada** entretanto, e continua a
        ser verdade que nenhuma das tres pode dar 404 — que e' o que este
        teste existe para travar. O que muda e' o codigo esperado de cada
        uma, e ele tem de mudar com a realidade, nao com a minha memoria.

        - `notas/`: 201 (grava).
        - `fotos/`: 400 sem ficheiro (a rota existe e valida a entrada; um
          501 aqui significaria que voltou a nao existir).
        - `voice/`: 501 (decisao de produto pendente: guardar audio ou so o
          texto).
        """
        r_notas = self._post()
        self.assertNotEqual(
            r_notas.status_code,
            404,
            "`/api/caderno/notas/` voltou a dar 404. E' a feature fantasma: o "
            "modelo e a view existem, e sem a rota em `urls.py` o produtor "
            "perde a nota sem ver erro.",
        )
        self.assertEqual(r_notas.status_code, 201, r_notas.content[:300])

        r_fotos = self.client.post(reverse("api-caderno-fotos"), data={})
        self.assertNotEqual(
            r_fotos.status_code,
            404,
            "`api-caderno-fotos` deu 404. 404 e' o buraco; qualquer outro "
            "codigo e' a rota a responder.",
        )
        self.assertEqual(
            r_fotos.status_code,
            400,
            "`fotos/` sem ficheiro devolve 400 com o motivo — a rota existe e "
            "esta a validar a entrada. Um 501 aqui diria que a rota voltou a "
            f"nao existir. Corpo: {r_fotos.content[:200]!r}",
        )

        r_voice = self.client.post(reverse("api-caderno-voice"), data={})
        self.assertNotEqual(
            r_voice.status_code,
            404,
            "`api-caderno-voice` deu 404. 404 e' o buraco; 501 com a lista do "
            "que falta e' a honestidade.",
        )
        self.assertEqual(r_voice.status_code, 501, r_voice.content[:200])

    def test_a_nota_do_produtor_chega_ao_servidor(self):
        """O que o produtor escreveu passa a existir onde ele pode ler."""
        antes = NotaCampo.objects.count()

        r = self._post()

        self.assertEqual(r.status_code, 201, r.content[:300])
        self.assertEqual(NotaCampo.objects.count(), antes + 1)

        nota = NotaCampo.objects.latest("id")
        self.assertEqual(nota.user, self.dono)
        self.assertEqual(nota.talhao, self.talhao)
        self.assertEqual(nota.tipo, "praga")
        self.assertEqual(nota.offline_id, 1737000000000)
        self.assertIn("pulgao", nota.conteudo)
        self.assertEqual(
            nota.propriedade,
            self.prop,
            "a propriedade nao foi deduzida do talhao. `sync.js` nao manda "
            "`propriedade_id`, e sem esta deducao a nota fica orfa do "
            "agregamento do painel.",
        )

    # ── a proveniência: uma nota e' DECLARADO, nunca medido ───────────────

    def test_a_nota_e_declarado_e_nao_medido(self):
        """
        A doutrina do projecto, aplicada ao que NASCE no caderno.

        `app/validators.py:40-41`: *"o sistema nunca promove uma afirmacao a
        medicao."* Uma nota de campo foi escrita por uma pessoa — nao ha sensor
        nenhum em `-19.123456, -57.654321`. Marca-la como `medido` e' a mesma
        mentira que o manifesto Agro 5.0 promete nao contar, e `fonte_dado` e'
        NOT NULL para que nao haja omissao silenciosa.
        """
        self._post()

        nota = NotaCampo.objects.latest("id")
        self.assertEqual(
            nota.fonte_dado,
            "declarado",
            "a nota de campo ficou marcada como "
            f"'{nota.fonte_dado}'. Ninguem mediu o que esta "
            "escrito; quem escreveu foi a pessoa.",
        )

    def test_o_cliente_nao_escolhe_a_proveniencia(self):
        """
        `fonte_dado` e' READ ONLY no serializer. Nao e' defensiveness: e' a
        fronteira. Um payload com `"fonte_dado": "medido"` tem de ser ignorado,
        porque um cliente nao decide a proveniencia de um dado — e o unico que
        poderia escrever "medido" aqui seria um navegador comprometido ou um
        bug de sync.
        """
        self._post(fonte_dado="medido")

        self.assertEqual(
            NotaCampo.objects.latest("id").fonte_dado,
            "declarado",
            "o cliente escolheu a proveniencia da nota. `fonte_dado` tem de ser "
            "read-only no serializer.",
        )

    # ── idempotencia: o offline reenvia ───────────────────────────────────

    def test_o_retry_nao_duplica_a_nota(self):
        """
        A razao de o `offline_id` existir.

        A `markNoteSynced` do `sync.js` so corre DEPOIS de um 2xx. Uma nota
        escrita offline repete em cada sync enquanto o servidor estiver em
        baixo — e uma nota repetida vinte vezes e' pior que uma nota perdida:
        o produtor ve "pulgao" cinco vezes e deixa de confiar no caderno.
        """
        primeiro = self._post()
        segundo = self._post()
        terceiro = self._post()

        self.assertEqual(primeiro.status_code, 201)
        self.assertEqual(
            segundo.status_code,
            200,
            "o reenvio tem de ser 2xx — e' o que faz o `sync.js` marcar a nota "
            "como sincronizada e parar de reenviar. Um 4xx aqui prende a nota "
            "na fila para sempre.",
        )
        self.assertEqual(terceiro.status_code, 200)
        self.assertEqual(
            NotaCampo.objects.filter(offline_id=1737000000000).count(),
            1,
            "a mesma nota foi gravada mais do que uma vez. `offline_id` tem de "
            "ser a chave de idempotencia.",
        )

    def test_offline_id_de_outro_utilizador_nao_colide(self):
        """
        A idempotencia e' por `(user, offline_id)`, nao so por `offline_id`.

        Dois produtores a escrever offline no mesmo relogio geram ids que podem
        coincidir. Se a chave fosse global, o segundo perderia a sua nota em
        silencio — e nunca a veria.
        """
        client_outro = Client()
        client_outro.force_login(self.outro)

        primeiro = self._post()
        segundo = client_outro.post(
            reverse("api-caderno-notas"),
            data={
                "conteudo": "nota do outro produtor",
                "tipo": "observacao",
                "offline_id": 1737000000000,
            },
            content_type="application/json",
        )

        self.assertEqual(primeiro.status_code, 201)
        self.assertEqual(segundo.status_code, 201, segundo.content[:300])
        self.assertEqual(NotaCampo.objects.filter(offline_id=1737000000000).count(), 2)

    # ── tenancy: a validacao que este caminho tem de fazer sozinho ─────────

    def test_um_talhao_alheio_e_recusado(self):
        """
        `talhao_id` vem do browser e e' verificado no serializer.

        Este caminho tambem passa pelo `TenantIsolationMiddleware` (`agente 9,
        2026-10-05`), que le o corpo JSON e recusa ids que nao pertencem ao
        utilizador: `403` para recurso de outra pessoa (404 = inexistente). O
        serializer e' a segunda barreira. A validacao no serializer NAO e' a
        defesa unica deste caminho, e o codigo esperado tem de acompanhar:
        `403` da middleware, nao `400`.
        """
        r = self._post(talhao_id=self.talhao_outro.pk)

        self.assertEqual(
            r.status_code,
            403,
            "o talhao de outra fazenda foi aceite. Uma nota gravada no talhao "
            "alheio escreve no GeoJSON e no custo/ha de alguem que nao e' o "
            "dono.",
        )
        self.assertEqual(NotaCampo.objects.count(), 0)

    def test_uma_propriedade_alheia_e_recusada(self):
        r = self._post(propriedade_id=self.prop_outro.pk)

        # A middleware agora rejeita ids fora do tenant do produtor por 403
        # (recurso de outra pessoa), o serializer tambem.
        self.assertEqual(r.status_code, 403, r.content[:200])
        self.assertEqual(NotaCampo.objects.count(), 0)

    def test_uma_nota_vazia_e_recusada(self):
        """`conteudo` em branco nao e' uma nota, e' um clique perdido."""
        r = self._post(conteudo="   ")

        self.assertEqual(r.status_code, 400, r.content[:200])
        self.assertEqual(NotaCampo.objects.count(), 0)

    # ── autenticacao ──────────────────────────────────────────────────────

    def test_anonimo_nao_escreve(self):
        anonimo = Client()

        r = anonimo.post(
            reverse("api-caderno-notas"),
            data=self._payload_do_sync_js(),
            content_type="application/json",
        )

        self.assertIn(r.status_code, (401, 403))
        self.assertEqual(NotaCampo.objects.count(), 0)

    # ── a hora do produtor, nao a da sincronizacao ────────────────────────

    def test_a_nota_aceita_a_hora_do_produtor(self):
        """
        MEDIDO no `sync.js`: a nota e' escrita as 9h e sincronizada as 17h. Se
        o `registada_em` for `agora`, a nota passa a dizer que foi escrita ao
        fim da tarde — e e' essa diferenca que decide se choveu durante a
        aplicacao.
        """
        quando = timezone.now() - timezone.timedelta(hours=8)

        r = self._post(registada_em=quando.isoformat())

        self.assertEqual(r.status_code, 201, r.content[:300])
        nota = NotaCampo.objects.latest("id")
        self.assertAlmostEqual(
            nota.registada_em.timestamp(),
            quando.timestamp(),
            delta=5,
            msg="o `registada_em` guardado nao e' a hora que o produtor escreveu",
        )

    # ── anti-falso-verde ──────────────────────────────────────────────────

    def test_as_rotas_estao_no_urlresolver(self):
        """
        Se `reverse()` funcionar, o nome existe; se o `path` desaparecer do
        `urls.py`, os testes acima comecam a dar `NoReverseMatch` — que e' uma
        falha ruidosa, e e' o que se quer de uma guarda de rota.
        """
        self.assertEqual(reverse("api-caderno-notas"), "/api/caderno/notas/")
        self.assertEqual(reverse("api-caderno-fotos"), "/api/caderno/fotos/")
        self.assertEqual(reverse("api-caderno-voice"), "/api/caderno/voice/")
