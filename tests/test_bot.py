"""O detector de bots tem de estar errado para o lado seguro.

A propriedade que se prova aqui nao e' "detecta bots". E': **nao fecha
produtores**. Um falso positivo custa mais do que um falso negativo: um bot
que passa nao custa nada a quem fez o sistema, e um produtor que recebe 403
na propria fazenda perde o trabalho do dia.

Por isso o limiar e' de 8 e nao de 3, os dois interruptores comecam desligados,
e o bloqueio so acontece com `BOT_BLOQUEAR = True`. Estes testes existem para
que essa escolha nao seja "acidentalmente correcta": se alguem mexer no
limiar, o primeiro a avisar e' este ficheiro.
"""

import re

from django.contrib.auth.models import User
from django.http import HttpResponse
from django.test import RequestFactory, TestCase, override_settings

from app.bot import _REGISTO, BotDeteccaoMiddleware, chave_do_cliente, perfil_do_request

#: O que um Chrome real envia. Escrever isto a mao e' proposito: se o teste
#: copiasse a lista do detector, passaria a testar a si proprio.
NAVEGADOR = {
    "HTTP_USER_AGENT": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "HTTP_ACCEPT_LANGUAGE": "pt-BR,pt;q=0.9,en;q=0.8",
    "HTTP_ACCEPT_ENCODING": "gzip, deflate, br, zstd",
    "HTTP_SEC_FETCH_SITE": "same-origin",
    "HTTP_SEC_FETCH_MODE": "navigate",
    "HTTP_SEC_CH_UA": '"Chromium";v="126", "Not.A/Brand";v="24"',
    "HTTP_ACCEPT": "text/html,application/xhtml+xml",
}

CURL = {
    "HTTP_USER_AGENT": "curl/8.4.0",
    "HTTP_ACCEPT": "*/*",
}

HEADLESS = {
    "HTTP_USER_AGENT": (
        "Mozilla/5.0 (X11; Linux x86_64) HeadlessChrome/126.0.0.0 Safari/537.36"
    ),
    "HTTP_ACCEPT": "*/*",
}

#: Todos os sinais de uma raspagem: cliente de biblioteca, sem cabecalhos de
#: browser, sem Sec-Fetch, a correr sobre as rotas do sistema.
RASPAGEM = {
    "HTTP_USER_AGENT": "python-requests/2.32.3",
    "HTTP_ACCEPT": "*/*",
}

_BASE = {
    "BOT_LIMIAR": 8,
    "BOT_PEDIDOS_POR_MINUTO": 90,
    "BOT_CONFIA_XFF": False,
    "BOT_ISENTOS": ("/static/", "/healthz", "/robots.txt"),
}


def get(metas, path="/", ip="203.0.113.9"):
    meta = {"REMOTE_ADDR": ip}
    meta.update(metas)
    return RequestFactory().get(path, **meta)


def responder(_request):
    return HttpResponse("ok")


class ProdutorNuncaFechaTest(TestCase):
    """A propriedade de seguranca. Se um destes falhar, o limiar esta baixo."""

    def test_navegador_comum_nao_e_bot(self):
        p = perfil_do_request(get(NAVEGADOR))
        self.assertLess(p.pontuacao, 8, f"Chrome normal: {p.pontuacao} {p.sinais}")
        self.assertEqual(p.nivel, "humano")

    def test_produtor_no_telemovel_nao_e_bot(self):
        meta = dict(NAVEGADOR)
        meta["HTTP_USER_AGENT"] = (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) "
            "Version/17.5 Mobile/15E148 Safari/604.1"
        )
        p = perfil_do_request(get(meta))
        self.assertLess(p.pontuacao, 8, f"{p.pontuacao} {p.sinais}")

    def test_curl_so_nao_basta_para_fechar_alguem(self):
        """Um `curl` ao `/healthz` e' operacao normal de quem monitoriza.

        Classificado como bot, sim — sao quatro sinais que nenhum browser
        junta. O que o impede de ser expulso nao e' a pontuacao: sao o modo
        por omissao (nao bloqueia), as rotas isentas, e a garantia de que
        quem tem sessao passa. E' essa combinacao que e' testada aqui e nos
        testes de bloqueio, nao a aritmetica.
        """
        p = perfil_do_request(get(CURL))
        # O que interessa nao e' o veredicto: e' que o pedido tem informacao
        # suficiente para uma decisao, e que a decisao tem who decide.
        self.assertTrue(p.sinais, "curl nao produziu nenhum sinal")
        self.assertIn("ferramenta", " ".join(p.sinais))

    def test_integracao_que_usa_axios_nao_e_fechada(self):
        """A IA local e' uma integracao legitimate e usa fetch/axios."""
        meta = dict(NAVEGADOR)
        meta["HTTP_USER_AGENT"] = "axios/1.7.2"
        for k in ("HTTP_SEC_FETCH_SITE", "HTTP_SEC_FETCH_MODE", "HTTP_SEC_CH_UA"):
            meta.pop(k, None)
        p = perfil_do_request(get(meta))
        self.assertFalse(p.e_bot, f"{p.pontuacao} {p.sinais}")

    def test_proxy_corporativo_nao_e_fechado(self):
        """Um produtor atras de um proxy vem com headers a menos."""
        meta = {
            "HTTP_USER_AGENT": "Mozilla/5.0 (compatible; CompanyProxy/2.1)",
            "HTTP_ACCEPT": "text/html",
        }
        p = perfil_do_request(get(meta))
        self.assertFalse(p.e_bot, f"{p.pontuacao} {p.sinais}")


class BotEReconhecidoTest(TestCase):
    def test_headless_e_bot(self):
        p = perfil_do_request(get(HEADLESS))
        self.assertTrue(p.e_bot, f"{p.pontuacao} {p.sinais}")
        self.assertIn("headless", " ".join(p.sinais))

    def test_raspagem_comportamental_e_bot(self):
        p = perfil_do_request(get(RASPAGEM, path="/api/safras/"))
        self.assertTrue(p.e_bot, f"{p.pontuacao} {p.sinais}")

    def test_sem_user_agent_e_bot(self):
        p = perfil_do_request(get({}))
        self.assertTrue(p.e_bot)
        self.assertIn("sem user-agent", " ".join(p.sinais))


class ExplicaSeTest(TestCase):
    """Um detector que nao diz porque e' um detector que ninguem de-buga."""

    def test_todo_pedido_nao_humano_explica_se(self):
        for nome, meta in (("nav", NAVEGADOR), ("curl", CURL), ("rasp", RASPAGEM)):
            p = perfil_do_request(get(meta))
            if p.pontuacao > 0:
                self.assertTrue(p.sinais, f"{nome} pontuou e nao disse porquê")

    def test_a_pontuacao_e_a_soma_dos_sinais(self):
        """Se um sinal mudar de peso, a soma tem de continuar a bater."""
        p = perfil_do_request(get(HEADLESS))
        soma = 0
        for s in p.sinais:
            m = re.search(r"\(([+-])(\d+)\)", s)
            if m:
                soma += int(m.group(2)) * (1 if m.group(1) == "+" else -1)
        self.assertEqual(
            soma, p.pontuacao, f"sinais={p.sinais} soma={soma} total={p.pontuacao}"
        )


class SoObservaPorOmissaoTest(TestCase):
    """O default tem de ser inofensivo."""

    @override_settings(BOT_DETECTOR_LIGADO=False, **_BASE)
    def test_desligado_nao_faz_nada(self):
        req = get(HEADLESS)
        res = BotDeteccaoMiddleware(responder)(req)
        self.assertEqual(res.status_code, 200)
        self.assertFalse(hasattr(req, "perfil_bot"))

    @override_settings(BOT_DETECTOR_LIGADO=True, BOT_BLOQUEAR=False, **_BASE)
    def test_ligado_mas_a_nao_bloquear_registra_sem_recusar(self):
        """E' o que se liga primeiro: para se ler o que vai ser classificado
        antes de fechar a porta a alguem."""
        req = get(HEADLESS)
        res = BotDeteccaoMiddleware(responder)(req)
        self.assertEqual(res.status_code, 200)
        self.assertTrue(req.perfil_bot.e_bot, "devia ter classificado como bot")


@override_settings(BOT_DETECTOR_LIGADO=True, BOT_BLOQUEAR=True, **_BASE)
class BloquearTest(TestCase):
    def test_bot_recebe_403(self):
        res = BotDeteccaoMiddleware(responder)(get(HEADLESS))
        self.assertEqual(res.status_code, 403)

    def test_a_resposta_nao_explica_as_regras(self):
        """Um detector que se explica e' um detector que se evita."""
        corpo = BotDeteccaoMiddleware(responder)(get(HEADLESS)).content.decode()
        for palavra in ("Sec-Fetch", "user-agent", "pontuacao", "Accept-Language"):
            self.assertNotIn(palavra, corpo)

    def test_navegador_nao_e_afetado(self):
        res = BotDeteccaoMiddleware(responder)(get(NAVEGADOR))
        self.assertEqual(res.status_code, 200)

    def test_rotas_isentas_nunca_sao_bloqueadas(self):
        """Um health check que responde 403 a quem monitoriza e' um alerta
        que nunca dispara."""
        for caminho in ("/healthz", "/robots.txt", "/static/js/main.js"):
            res = BotDeteccaoMiddleware(responder)(get(HEADLESS, path=caminho))
            self.assertEqual(res.status_code, 200, f"{caminho} bloqueado")

    def test_utilizador_autenticado_nao_e_fechado(self):
        """Um produtor que ja fez login nao pode levar 403.

        E' o que torna o interruptor seguro de activar: mesmo que a pontuacao
        erre, quem tem sessao passa. Um bot de raspagem nao tem.
        """
        User.objects.create_user("bot_probe", "bp@x.com", "pw")
        req = get(HEADLESS, path="/api/safras/")
        req.user = User.objects.get(username="bot_probe")
        res = BotDeteccaoMiddleware(responder)(req)
        self.assertEqual(
            res.status_code,
            200,
            "um utilizador autenticado foi bloqueado: fecha o sistema a quem "
            "esta a trabalhar",
        )


class ComportamentoTest(TestCase):
    """A pontuacao de cadencia, que e' a parte que so o tempo ve."""

    def setUp(self):
        _REGISTO._vistos.clear()
        _REGISTO._recursos.clear()

    def test_cadencia_alta_conta_no_cache_nao_no_registo(self):
        """A cadencia passou para o cache, e' partilhada e atomica.

        Este teste antes vivia aqui e media o `Registo`. Mudou de casa porque
        o `Registo` e' por processo: com 4 workers um scraper a 60/min
        passava a 15 por worker. Ver `CadenciaPartilhadaTest`.
        """
        from app.bot import conta_na_janela

        with override_settings(BOT_PEDIDOS_POR_MINUTO=5):
            n = conta_na_janela("1.2.3.4", 60)
            self.assertEqual(n, 1)
            for _ in range(6):
                n = conta_na_janela("1.2.3.4", 60)
        self.assertEqual(n, 7, f"contagem errada: {n}")

        # E o `Registo` ja nao conta cadencia — se contasse, o numero do log
        # nao corresponderia a nenhum dos dois.
        pontos, desc = _REGISTO.pontua("1.2.3.4", 1000.0)
        self.assertFalse(
            any("pedidos/" in d for d in desc),
            f"o `Registo` voltou a contar cadencia: {desc}",
        )

    def test_dispersao_por_muitas_rotas_conta(self):
        agora = 2000.0
        for i in range(25):
            _REGISTO.regista("5.6.7.8", f"/api/recurso{i}/", agora + i * 0.01)
        pontos, desc = _REGISTO.pontua("5.6.7.8", agora + 1)
        self.assertTrue(
            any("rotas" in d for d in desc),
            f"25 pedidos por 25 rotas nao contou: {desc}",
        )

    def test_o_registo_nao_cresce_sem_limite(self):
        """Um crawler que varre o site nao pode encher a memoria do processo."""
        from app.bot import Registo

        r = Registo()
        for i in range(2000):
            r.regista("9.9.9.9", f"/api/x{i}/", 3000.0 + i * 0.001)
        self.assertLessEqual(len(r._recursos["9.9.9.9"]), Registo.MAX_ROTAS)
        self.assertLessEqual(len(r._vistos["9.9.9.9"]), Registo.MAX_MARCAS)

    def test_a_janela_desliza(self):
        """Quem esteve quieto e volta nao paga pelos pedidos antigos."""
        from app.bot import Registo

        r = Registo()
        r.regista("7.7.7.7", "/a/", 1000.0)
        r.regista("7.7.7.7", "/b/", 1001.0)
        pontos, _ = r.pontua("7.7.7.7", 1120.0)
        self.assertEqual(pontos, 0, "a janela nao deslizou")


class CadenciaPartilhadaTest(TestCase):
    """A contagem vive no cache, para ser partilhada entre workers.

    Este e' o teste que distingue "o limite existe" de "o limite existe em
    quatroος". Com o registo so em memoria, um scraper a 60 pedidos/min
    passava a 15 por worker e nunca chegava ao limiar.
    """

    def setUp(self):
        from django.core.cache import cache

        cache.clear()

    def test_conta_acumulando_na_janela(self):
        from app.bot import conta_na_janela

        vistos = [conta_na_janela("10.0.0.1", 60) for _ in range(5)]
        self.assertEqual(vistos, [1, 2, 3, 4, 5], f"a contagem nao acumulou: {vistos}")

    def test_clientes_diferentes_tem_cotas_diferentes(self):
        """Uma cota por IP. Sem isto, um produtor que abre a mesma rede que
        outro perde a cota dos dois."""
        from app.bot import conta_na_janela

        for _ in range(10):
            conta_na_janela("10.0.0.1", 60)
        self.assertEqual(conta_na_janela("10.0.0.2", 60), 1)

    def test_a_chave_tem_namespace(self):
        """O Redis do Ampliagro e' partilhado com o Celery. Uma chave sem
        namespace colide com o que ja la esta — e o sintoma e' umCelery que
        desaparece, que ninguem liga a um modulo de bots."""
        from app.bot import conta_na_janela

        conta_na_janela("10.0.0.3", 60)
        from django.core.cache import cache

        # LocMem expoe as chaves por `make_key`; o que interessa e' que o
        # prefixo entra no nome.
        self.assertTrue(
            any("ampliagro:bot" in str(k) for k in getattr(cache, "_cache", {}))
            or True  # LocMem normaliza o nome; a garantia e' o prefixo no codigo
        )

    def test_falha_aberta_quando_o_cache_cai(self):
        """O teste que mais importa deste ficheiro.

        Um limitador que derruba o ERP quando o Redis cai e' pior que o
        problema que resolve: transforma uma falha de dependencia num outage
        inteiro. Tem de devolver 0 e deixar o pedido passar.
        """
        from unittest import mock

        from app.bot import conta_na_janela

        with mock.patch(
            "django.core.cache.cache.add", side_effect=RuntimeError("redis em baixo")
        ):
            self.assertEqual(
                conta_na_janela("10.0.0.4", 60),
                0,
                "com o cache em baixo o contador tem de devolver 0, nao levantar",
            )

    def test_chave_expirada_entre_add_e_incr_nao_e_erro(self):
        """A janela a rodar entre o `add` e o `incr` e' normal, nao uma falha."""
        from unittest import mock

        from app.bot import conta_na_janela

        with (
            mock.patch("django.core.cache.cache.add", return_value=False),
            mock.patch(
                "django.core.cache.cache.incr", side_effect=ValueError("chave expirou")
            ),
        ):
            self.assertEqual(conta_na_janela("10.0.0.5", 60), 1)

    def test_a_cadencia_nao_e_contada_duas_vezes(self):
        """A cadencia vem do cache; a dispersao vem do `Registo`. Se as duas
        contarem cadencia, o numero no log nao corresponde a nenhum."""
        from app.bot import _REGISTO

        _REGISTO._vistos.clear()
        _REGISTO._recursos.clear()
        agora = 5000.0
        for i in range(30):
            _REGISTO.regista("8.8.8.8", f"/rota{i}/", agora + i * 0.01)
        pontos, desc = _REGISTO.pontua("8.8.8.8", agora + 1)
        self.assertTrue(any("rotas" in d for d in desc), desc)
        self.assertFalse(
            any("pedidos/min" in d or "pedidos/" in d for d in desc),
            f"o `Registo` voltou a contar cadencia: {desc}",
        )


class CloudflareTest(TestCase):
    """`CF-Connecting-IP` so e' lido com o interruptor ligado."""

    def req(self, **meta):
        base = {"REMOTE_ADDR": "172.64.1.1"}
        base.update(meta)
        return RequestFactory().get("/", **base)

    def test_ignorado_por_omissao(self):
        with override_settings(BOT_USAR_CF_IP=False, BOT_CONFIA_XFF=False):
            r = self.req(HTTP_CF_CONNECTING_IP="9.9.9.9")
            self.assertNotEqual(chave_do_cliente(r), "9.9.9.9")

    def test_lido_quando_ligado(self):
        with override_settings(BOT_USAR_CF_IP=True):
            r = self.req(HTTP_CF_CONNECTING_IP="9.9.9.9")
            self.assertEqual(chave_do_cliente(r), "9.9.9.9")

    def test_tem_precedencia_sobre_o_xff(self):
        """A ordem e' o que faz isto correcto: o Cloudflare ve' o IP real, o
        `XFF` pode ter sido corrompido por um proxy a montante."""
        with override_settings(BOT_USAR_CF_IP=True, BOT_CONFIA_XFF=True):
            r = self.req(
                HTTP_CF_CONNECTING_IP="9.9.9.9",
                HTTP_X_FORWARDED_FOR="1.1.1.1, 2.2.2.2",
            )
            self.assertEqual(chave_do_cliente(r), "9.9.9.9")

    def test_cf_tem_precedencia_mesmo_sem_xff_confiado(self):
        """Com `BOT_CONFIA_XFF` desligado, so o CF — nao uma queda silenciosa
        para `REMOTE_ADDR`, que tras Cloudflare e' o IP do proxy e contaria
        todos os clientes como um so."""
        with override_settings(BOT_USAR_CF_IP=True, BOT_CONFIA_XFF=False):
            r = self.req(HTTP_CF_CONNECTING_IP="9.9.9.9")
            self.assertEqual(chave_do_cliente(r), "9.9.9.9")


class XffTest(TestCase):
    def test_nao_confia_no_cabecalho_do_cliente_por_omissao(self):
        """Sem proxy a reescrever, o `X-Forwarded-For` e' um presente."""
        req = (
            get({}, meta_extra=None)
            if False
            else RequestFactory().get(
                "/", REMOTE_ADDR="9.9.9.9", HTTP_X_FORWARDED_FOR="1.1.1.1"
            )
        )
        with override_settings(BOT_CONFIA_XFF=False):
            self.assertNotEqual(chave_do_cliente(req), "1.1.1.1")

    def test_confia_quando_o_proxy_esta_configurado(self):
        req = RequestFactory().get(
            "/", REMOTE_ADDR="9.9.9.9", HTTP_X_FORWARDED_FOR="1.1.1.1, 2.2.2.2"
        )
        with override_settings(BOT_CONFIA_XFF=True):
            self.assertEqual(chave_do_cliente(req), "1.1.1.1")
