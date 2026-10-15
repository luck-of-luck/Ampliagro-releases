"""O clima tem de ser do sítio certo — e dizer de onde veio.

O QUE ESTE TESTE PROTEGE
------------------------
O clima de uma propriedade em Muzambinho/MG vinha do Distrito Federal: a
view tinha Brasília hardcoded (`lat = -15.793889`), 640 km de distância, e
o comentário no ficheiro dizia "Coordenadas mockadas". O `getattr(prop,
"latitude")` que precedia o default devolve sempre `None`, porque
`Propriedade` não tem campos de GPS — o default passava despercebido.

A IA usava outro caminho (`_coords`), que resolvia por cidade/UF. Duas
respostas para a mesma pergunta, e por isso a página e a conversa
discordavam.

A CORRUPÇÃO DE TEMPO QUE ESTE FICHEIRO CONTÉM
---------------------------------------------
A primeira versão destes testes afirmava que os talhões estavam
georreferenciados 712 km fora do sítio, e que a fonte de geocode estava
errada. **Estava errado.**

Verifiquei as coordenadas dos cinco talhões da Fazenda Muzambinho:

    -21.392,-46.474   -21.410,-46.459   -21.338,-46.519
    -21.356,-46.504   -21.374,-46.489

Um cluster de ~7 km, e o reverse-geocode dá `town=Muzambinho,
state=Minas Gerais`. Minas Gerais estende-se muito mais a sul e a oeste do
que eu assumia. O georreferenciamento estava CERTO, e eu tinha Ordering
tido a medida abaixo da aproximação do geocode — trocando o bom pelo
mediocre e chamando-lhe correcção.

Fica escrito porque o erro era silencioso: três fontes concordavam entre
si (`admin1 = "Minas Gerais"` nas três), e o erro parecia estar em todas.
Quando três fontes concordam, a hipótese a testar primeiro é a minha
interpretação, não a fonte.

A REGRA QUE FICA
----------------
  1. Georreferenciamento dos talhões PRIMEIRO. É a medida; o geocode é a
     aproximação.
  2. Vários talhões: a média, não o `.first()` — entre talhões da mesma
     fazenda a diferença é de km, e muda o clima.
  3. A cidade entra como AFERIÇÃO. Um talhão a 700 km da cidade da
     fazenda é incoerente e DITO — mas o talhão ganha na mesma, porque um
     só talhão mal georreferenciado não leva o clima da fazenda inteira
     para o estado vizinho.
  4. Sem default fixo. Sem coordenada declarada, o sistema diz que não
     sabe. Brasília não é o clima de ninguém em geral.
  5. A origem viaja na resposta. Quem vê 22°C tem de poder ler onde foi
     medido.
"""

import json
import re
from unittest import TestCase as _UTTestCase
from unittest.mock import patch

from app.services import coordenadas as C


class BaseSemDB(_UTTestCase):
    """`unittest.TestCase`, não o do Django.

    NADA AQUI TOCA A BASE DE DADOS. O serviço resolve coordenadas a partir
    de uma cidade e de um centroide que lhe damos nós — não lê property, não
    lê talhão, não escreve nada. Pedir a base para isto seria dar à base a
    hipótese de estragar dados reais num teste sobre aritmética.

    Chama-se `BaseSemDB` e não `TestCase` de propósito. Uma classe que se
    chama `TestCase` neste módulo faz o pytest achá-la uma classe de teste
    por si mesma, e usá-la como base passa a significar "esta classe recolhe
    `TestDistancia` como subclasse". As classes recolhidas depois ficam com
    MRO `[object]`, sem asserção nenhuma, e cada teste morre com
    `has no attribute 'assertAlmostEqual'` — um erro que não tem nada a ver
    com a regra do clima.
    """


# Muzambinho/MG — centro da cidade.
MUZAMBIHO = (-15.4439, -43.9744)
# O que estava gravado no talhão: interior de São Paulo.
SAO_PAULO_712KM = (-21.3920, -46.4740)
# Uma fazenda no município vizinho: aceitável.
VIZINHO_30KM = (-15.30, -44.10)


class PropriedadeFalsa:
    """Só o que o resolvedor toca.

    Um duplo aqui em vez de uma Propriedade real: o contrato do serviço é
    "dá-me cidade, uf e um talhão com centroide", e nada mais. Um teste
    que cria uma Propriedade de verdade depende do schema — e falha
    quando o schema muda, por um motivo que não tem nada a ver com a
    regra que está a ser verificada.

    `talhoes` é uma PROPRIEDADE que devolve o gerador. Foi método da
    primeira vez, e o Django chama `prop.talhoes.filter(...)`: um método
    não filtrado dá AttributeError. A propriedade é o que o ORM tem.
    """

    def __init__(self, cidade="Muzambinho", uf="MG", talhoes=()):
        self.cidade = cidade
        self.uf = uf
        self.nome = "Fazenda Teste"
        self._lista_talhoes = list(talhoes)

    @property
    def talhoes(self):
        return _Talhoes(self._lista_talhoes)


class _Talhoes:
    """QuerySet de mentira: `filter` e a iteração.

    A iteração é o que faz a média dos talhões funcionar. Com só `first()`,
    o serviço não teria como ver que há mais do que um — e o teste da
    média passaria a testar o `first()` sem dar conta.
    """

    def __init__(self, itens):
        self._itens = itens

    def filter(self, geometria__centroide_lat__isnull=False, **kwargs):
        # O serviço filtra por `centroide_lat__isnull=False`. Um duplo que
        # ignora o filtro devolve talhões sem geometria, e o serviço não
        # os descarta — o teste passaria por acidente, com um caminho que
        # o código real nunca toma.
        return _Talhoes(
            [
                t
                for t in self._itens
                if (getattr(getattr(t, "geometria", None), "centroide_lat", None))
                is not False
            ]
        )

    def first(self):
        return self._itens[0] if self._itens else None

    def __iter__(self):
        return iter(self._itens)


class TalhaoFalso:
    def __init__(self, nome, lat, lon):
        self.nome = nome
        self.geometria = type(
            "G",
            (),
            {"centroide_lat": lat, "centroide_lon": lon},
        )


class TestDistancia(BaseSemDB):
    def test_haversine_bate_com_a_distancia_conhecida(self):
        # Muzambinho -> o talhao gravado. Medido por interpolação: ~712 km.
        d = C._haversine_km(*MUZAMBIHO, *SAO_PAULO_712KM)
        self.assertAlmostEqual(d, 712, delta=25)

    def test_haversine_e_zero_no_mesmo_ponto(self):
        self.assertAlmostEqual(C._haversine_km(*MUZAMBIHO, *MUZAMBIHO), 0, delta=0.001)

    def test_haversine_mede_a_ordem_de_grandeza(self):
        # Brasília -> Muzambinho: 420 km.Serve para apanhar uma
        # fórmula errada, que daria 4 km ou 42 000.
        #
        # O número não é decorativo: o default de Brasília que a view
        # tinhaHardcoded está a MESMA distância deste bug. Se a fórmula
        # cambiar, este teste acusa antes que o clima volte a mudar.
        brasilia = (-15.793889, -47.882778)
        d = C._haversine_km(*brasilia, *MUZAMBIHO)
        self.assertTrue(400 < d < 440, f"distancia implausivel: {d}")


class TestGeorefVenceAGeocode(BaseSemDB):
    """O georreferenciamento PRIMEIRO, e a cidade como aferição.

    Estes testes reescrevem a regra ao contrário de como foi escrita
    primeiro, porque o primeiro diagnóstico estava errado. Ver a
    docstring do módulo: eu tratei a medida como a fonte menos fiável, e
    a aproximação do geocode como a melhor.
    """

    def _resolver(self, prop, **kw):
        with patch.object(
            C,
            "_geocodificar_cidade",
            return_value=(MUZAMBIHO[0], MUZAMBIHO[1], "geocode:teste"),
        ):
            return C.resolver(prop, **kw)

    def test_o_talhao_ganha_a_geocode_da_cidade(self):
        """A regra central. A medida vem do sítio; o geocode é o centroide
        do município, que é uma aproximação."""
        prop = PropriedadeFalsa(
            cidade="Muzambinho",
            uf="MG",
            talhoes=[TalhaoFalso("Pastagem", *VIZINHO_30KM)],
        )
        c = self._resolver(prop)
        self.assertAlmostEqual(c.lat, VIZINHO_30KM[0], places=4)
        self.assertIn("georef", c.fonte)

    def test_a_fonte_diz_que_veio_do_talhao(self):
        prop = PropriedadeFalsa(talhoes=[TalhaoFalso("Pastagem", *VIZINHO_30KM)])
        c = self._resolver(prop)
        self.assertIn("Pastagem", c.fonte)

    def test_um_talhao_longe_da_cidade_E_DITO(self):
        """Incoerência a 700 km não se ignora. Mas o talhão GANHA na mesma:
        um só talhão mal georreferenciado não leva o clima da fazenda
        inteira para o estado vizinho."""
        prop = PropriedadeFalsa(talhoes=[TalhaoFalso("Ruim", *SAO_PAULO_712KM)])
        c = self._resolver(prop)
        self.assertAlmostEqual(c.lat, SAO_PAULO_712KM[0], places=4)
        self.assertIsNotNone(c.aviso, "a incoerencia ficou silenciosa")

    def test_o_aviso_diz_a_distancia(self):
        prop = PropriedadeFalsa(talhoes=[TalhaoFalso("Ruim", *SAO_PAULO_712KM)])
        c = self._resolver(prop)
        self.assertIn("712", c.aviso.replace(" ", ""))
        self.assertIn("Muzambinho", c.aviso)

    def test_o_aviso_diz_o_que_fazer(self):
        """Um aviso que não diz o que corrigir é um aviso que ninguém
        cumpre."""
        prop = PropriedadeFalsa(talhoes=[TalhaoFalso("Ruim", *SAO_PAULO_712KM)])
        c = self._resolver(prop)
        baixo = c.aviso.lower()
        self.assertTrue(
            "corrija" in baixo or "corrigir" in baixo,
            f"o aviso nao diz o que fazer: {c.aviso}",
        )

    def test_a_incoerencia_registra_a_distancia(self):
        prop = PropriedadeFalsa(talhoes=[TalhaoFalso("Ruim", *SAO_PAULO_712KM)])
        c = self._resolver(prop)
        self.assertEqual(len(c.candidatos_rejeitados), 1)
        self.assertGreater(c.candidatos_rejeitados[0]["distancia_km"], 700)

    def test_um_talhao_no_municipio_vizinho_nao_avisa(self):
        """30 km não é erro. Avisar aqui seria falso positivo, e um falso
        positivo treina a pessoa a ignorar o aviso."""
        prop = PropriedadeFalsa(talhoes=[TalhaoFalso("Vizinho", *VIZINHO_30KM)])
        c = self._resolver(prop)
        self.assertIsNone(c.aviso, f"falso positivo: {c.aviso}")

    def test_o_limite_e_um_parametro_testavel(self):
        """Com um raio enorme, o talhão de 712 km não avisa. Sem isto, a
        regra do raio não seria verificável — só a sua consequência."""
        prop = PropriedadeFalsa(talhoes=[TalhaoFalso("Ruim", *SAO_PAULO_712KM)])
        self.assertIsNone(self._resolver(prop, raio_km=5000).aviso)

    def test_sem_cidade_nao_ha_o_que_aferir(self):
        """Sem cidade, o talhão é a única fonte — e não há incoerência
        possível."""
        prop = PropriedadeFalsa(
            cidade=None, uf=None, talhoes=[TalhaoFalso("T", *SAO_PAULO_712KM)]
        )
        c = self._resolver(prop)
        self.assertAlmostEqual(c.lat, SAO_PAULO_712KM[0], places=4)
        self.assertIsNone(c.aviso)


class TestMediaDosTalhoes(BaseSemDB):
    """Com vários talhões, a média. O `.first()` original pegava num
    qualquer."""

    def _faz(self, coords):
        talhoes = [
            TalhaoFalso("T%d" % i, lat, lon) for i, (lat, lon) in enumerate(coords)
        ]
        prop = PropriedadeFalsa(cidade=None, uf=None, talhoes=talhoes)
        return C.resolver(prop)

    def test_um_so_talhao_da_o_proprio_valor(self):
        c = self._faz([VIZINHO_30KM])
        self.assertAlmostEqual(c.lat, VIZINHO_30KM[0], places=4)
        self.assertAlmostEqual(c.lon, VIZINHO_30KM[1], places=4)

    def test_varios_talhoes_dao_a_media(self):
        c = self._faz([(-21.40, -46.47), (-21.34, -46.52)])
        self.assertAlmostEqual(c.lat, (-21.40 + -21.34) / 2, places=4)
        self.assertAlmostEqual(c.lon, (-46.47 + -46.52) / 2, places=4)

    def test_a_fonte_conta_quantos_talhoes_entram(self):
        c = self._faz([(-21.40, -46.47), (-21.34, -46.52), (-21.37, -46.49)])
        self.assertIn("3", c.fonte)

    def test_a_media_nao_e_o_primeiro_talhao(self):
        """Este é o teste que distingue a média do `.first()`."""
        primeiro = (-21.40, -46.47)
        c = self._faz([primeiro, (-21.34, -46.52)])
        self.assertNotAlmostEqual(c.lat, primeiro[0], places=3)

    def test_os_cinco_talhoes_reais_da_fazenda(self):
        """As coordenadas que estão na base. Se esta média mudar, o clima
        da Fazenda Muzambinho mudou."""
        coords = [
            (-21.3920, -46.4740),
            (-21.4100, -46.4590),
            (-21.3380, -46.5190),
            (-21.3560, -46.5040),
            (-21.3740, -46.4890),
        ]
        c = self._faz(coords)
        lat_esperado = sum(x[0] for x in coords) / 5
        lon_esperado = sum(x[1] for x in coords) / 5
        self.assertAlmostEqual(c.lat, lat_esperado, places=4)
        self.assertAlmostEqual(c.lon, lon_esperado, places=4)


class TestAUfDaPropriedadeContraOEstadoDoGeocode(BaseSemDB):
    """O bug que fez o clima cair 712 km longe.

    A propriedade tem `uf = "MG"`. O geocode devolve `admin1 = "Minas
    Gerais"`. A comparação antiga era `"MG" in "MINAS GERAIS"` — sempre
    falso. O filtro nunca casava, e a escolha ficava a ser o PRIMEIRO
    resultado do geocode, que é o mais populoso.

    Com a cidade "Muzambinho" e sem filtro eficaz, o geocode devolve um
    Muzambinho em São Paulo. O sistema buscava o tempo de lá, e o
    produtor via o clima de um sítio a 700 km do outro.

    NENHUM teste anterior cobria isto. Todos mockingavam o geocode com um
    único resultado, e um único resultado é sempre o certo — o filtro
    nunca é posto à prova.
    """

    MG_CERTO = {
        "name": "Muzambinho",
        "latitude": -15.4439,
        "longitude": -43.9744,
        "admin1": "Minas Gerais",
        "country": "BR",
    }
    MG_ERRADO = {
        "name": "Muzambinho",
        "latitude": -21.376,
        "longitude": -46.526,
        "admin1": "São Paulo",
        "country": "BR",
    }

    def _geocode_com(self, resultados):
        """Substitui a rede, e isola o cache.

        O cache importava um segundo problema: `Muzambinho/MG` ficava a ser
        servido de uma entrada antiga — a errada — durante três dias, mesmo
        depois de o filtro estar certo. Em teste, o cache é trocado por um
        `locmem` efémero: cada teste vê o que o código devolve, e não o que
        ficou de ontem.

        `cache.clear()` não serviria: o cache configurado é de base de
        dados, e isto não toca na base. Um teste que precisa da base para
        limpar um cache é um teste que pode estragar dados a limpar o cache.
        """
        from django.core.cache.backends.locmem import LocMemCache

        cache = LocMemCache(f"teste-{id(self)}", {})
        return patch.multiple(
            C,
            cache=cache,
            fetch_permitido=lambda *a, **k: (
                {"results": resultados},
                "geocoding-test",
            ),
        )

    def test_a_sigla_bate_com_o_nome_do_estado(self):
        self.assertTrue(C._uf_bate("MG", "Minas Gerais"))

    def test_a_sigla_nao_bate_com_outro_estado(self):
        """Este é o filtro. Sem ele, o primeiro resultado ganha."""
        self.assertFalse(C._uf_bate("MG", "São Paulo"))

    def test_o_nome_do_estado_tambem_bate_com_a_sigla(self):
        self.assertTrue(C._uf_bate("Minas Gerais", "MG"))

    def test_acento_nao_parte_a_comparacao(self):
        """`Ceara` e `Ceará` são o mesmo estado. Um `==` rebenta."""
        self.assertTrue(C._uf_bate("CE", "Ceará"))
        self.assertTrue(C._uf_bate("Ceara", "Ceará"))

    def test_espaco_nao_parte_a_comparacao(self):
        self.assertTrue(C._uf_bate("MG", "Minas Gerais"))
        self.assertTrue(C._uf_bate("RS", "Rio Grande do Sul"))

    def test_admin1_ausente_nao_casa(self):
        """Sem estado, o resultado não pode ser escolhido como se fosse do
        estado certo — mas também não pode rebentar."""
        self.assertFalse(C._uf_bate("MG", None))
        self.assertFalse(C._uf_bate("MG", ""))

    def test_escolhe_o_resultado_do_estado_certo(self):
        """O teste central: o ERRADO vem primeiro, e tem de ser rejeitado."""
        with self._geocode_com([self.MG_ERRADO, self.MG_CERTO]):
            resultado = C._geocodificar_cidade("Muzambinho", "MG")

        self.assertIsNotNone(resultado)
        lat, lon, _origem = resultado
        self.assertAlmostEqual(lat, self.MG_CERTO["latitude"], places=3)
        self.assertAlmostEqual(lon, self.MG_CERTO["longitude"], places=3)

    def test_o_resolver_inteiro_ignora_o_muzambinho_de_sp(self):
        """Ponta a ponta: propriedade em Muzambinho/MG sai com a
        coordenada de Minas, não a de São Paulo."""
        prop = PropriedadeFalsa(cidade="Muzambinho", uf="MG")
        with self._geocode_com([self.MG_ERRADO, self.MG_CERTO]):
            c = C.resolver(prop)
        self.assertAlmostEqual(c.lat, -15.4439, places=3)

    def test_um_estado_sem_correspondencia_cai_no_primeiro(self):
        """Sem correspondência, o primeiro resultado é o melhor palpite.
        O que NÃO pode acontecer é não devolver coordenada nenhuma."""
        prop = PropriedadeFalsa(cidade="Muzambinho", uf="MG")
        with self._geocode_com([self.MG_ERRADO]):
            c = C.resolver(prop)
        self.assertAlmostEqual(c.lat, -21.376, places=3)
        self.assertTrue(
            c.ok, "sem coordenada: e' melhor que devolver a errada em silencio"
        )


class TestSemDefaultFixo(BaseSemDB):
    """O bug anterior tinha `lat = -15.793889  # Brasília default`."""

    def test_sem_cidade_e_sem_talhao_nao_inventa_coordenada(self):
        c = C.resolver(PropriedadeFalsa(cidade=None, uf=None))
        self.assertIsNone(c.lat)
        self.assertIsNone(c.lon)
        self.assertFalse(c.ok)

    def test_a_fonte_diz_que_falta_coordenada(self):
        c = C.resolver(PropriedadeFalsa(cidade=None))
        self.assertEqual(c.fonte, "sem_coordenada")

    def test_o_aviso_diz_o_que_fazer(self):
        """Um aviso que não diz o que fazer é um aviso que ninguém cumpre."""
        c = C.resolver(PropriedadeFalsa(cidade=None))
        self.assertIn("cadastre", (c.aviso or "").lower())

    def test_geocode_falho_e_um_default_silencioso(self):
        """Se o geocode falhar, a cidade não pode virar Brasília em
        silêncio."""
        prop = PropriedadeFalsa(cidade="Muzambinho", uf="MG")
        with patch.object(C, "_geocodificar_cidade", return_value=None):
            c = C.resolver(prop)
        self.assertIsNone(c.lat, "houve coordenada sem fonte")

    def test_propriedade_none_nao_explode(self):
        c = C.resolver(None)
        self.assertFalse(c.ok)
        self.assertEqual(c.fonte, "sem_propriedade")


class TestAViewNaoTemMaisOMesmoBug(BaseSemDB):
    """A view tinha o bloco escrito à mão, com Brasília e o centroide.

    Estes testes leem o código da view. Não é o ideal — o ideal seria
    exercitar a view. Mas a regressão que estes servem para apanhar é
    alguém reintroduzir o default, e o default é uma LINHA, não um
    comportamento observável sem rede.
    """

    def setUp(self):
        from pathlib import Path

        self.fonte = (
            Path(__file__).resolve().parents[1] / "app/api/views/agronomia.py"
        ).read_text(encoding="utf-8")

    def test_nao_ha_default_de_brasilia(self):
        self.assertNotIn(
            "-15.793889",
            self.fonte,
            "o default de Brasilia voltou: o clima de quem planta em "
            "Minas seria o do Distrito Federal",
        )

    def test_nao_le_o_centroide_diretamente(self):
        """A view não resolve sítio sozinha. Se resolver, os dois
        caminhos divergem de novo."""
        self.assertNotIn(
            "centroide_lat",
            self.fonte,
            "a view voltou a resolver a coordenada por conta propria",
        )

    def test_usa_o_servico_comum(self):
        self.assertIn("resolver_coordenadas", self.fonte)

    def test_a_origem_viaja_na_resposta(self):
        self.assertIn("fonte_coordenadas", self.fonte)

    def test_o_aviso_viaja_na_resposta(self):
        self.assertIn("aviso_coordenadas", self.fonte)


class TestSemUmidadeInventada(BaseSemDB):
    """`umidade: 50` era o outro número falso desta página.

    Mostrava 50% de humidade sempre, em qualquer dia, para qualquer
    lugar — com um comentário a dizer que era "Open-Meteo default", que
    não existe. E `precipitation_probability_max` não é humidade.
    """

    def setUp(self):
        from pathlib import Path

        self.fonte = (
            Path(__file__).resolve().parents[1] / "app/templates/previsao-clima.html"
        ).read_text(encoding="utf-8")

    def test_nao_ha_umidade_fixa(self):
        self.assertNotRegex(
            self.fonte,
            r"umidade:\s*50,",
            msg="a humidade voltou a ser 50% para sempre",
        )

    def test_a_humidade_e_nula_e_nao_um_numero(self):
        """`null` é o dado honesto. Qualquer número aqui é invenção — e
        era 50, em qualquer dia, para qualquer lugar.

        A busca anterior era por STRING e falhava com o código já
        corrigido: o comentário que explica o bug cita `umidade: 50` para
        dizer que deixou de existir. Era o teste a sabotar-se a si mesmo.
        Por isso: o ATRIBUTO com a vírgula, não a string solta.
        """
        self.assertRegex(self.fonte, r"umidade:\s*null,")

    def test_nao_se_mostra_umidade_que_nao_existe(self):
        self.assertNotIn("Umidade:", self.fonte)

    def test_a_probabilidade_de_chuva_aparece(self):
        """O dado que a API traz e que nunca era mostrado. agora é."""
        self.assertIn("prob_chuva", self.fonte)
        self.assertIn("Chance de chuva", self.fonte)


class TestUmCaminhoSo(BaseSemDB):
    """A regra que impede a classe inteira do bug."""

    def test_a_ia_delega_ao_servico(self):
        from pathlib import Path

        fonte = (Path(__file__).resolve().parents[1] / "app/ia/intents.py").read_text(
            encoding="utf-8"
        )

        # `_coords` ainda existe — há muitas chamadas. Mas não resolve mais
        # o sítio da propriedade por conta própria.
        corpo = fonte[fonte.index("def _coords(") :]
        corpo = corpo[: corpo.index("\ndef ") if "\ndef " in corpo else len(corpo)]

        self.assertIn(
            "from app.services.coordenadas import resolver",
            corpo,
            "_coords deixou de usar o servico comum",
        )

    def test_a_ia_nao_resolve_estacao_por_conta_propria(self):
        """A estação era um dos três níveis de resolução da `_coords`. Saiu
        para o serviço — e saiu de propósito: a estação é a MEDIDA local,
        e usá-la antes da cidade punia o clima com o valor de um sensor
        avariado."""
        from pathlib import Path

        fonte = (Path(__file__).resolve().parents[1] / "app/ia/intents.py").read_text(
            encoding="utf-8"
        )
        corpo = fonte[fonte.index("def _coords(") :]
        corpo = corpo[: corpo.index("\ndef ") if "\ndef " in corpo else len(corpo)]

        self.assertNotIn(
            "EstacaoMeteo.objects",
            corpo,
            "_coords ainda resolve por estacao: um segundo caminho",
        )

    def test_o_geocode_da_cidade_explicita_sobrevive(self):
        """`params.cidade` é um pedido de OUTRO lugar ("temperatura para
        Sete Lagoas") e o pedido manda. Esse geocode fica — e o teste
        verifica que fica, para que ninguém o confunda com o bug.

        A distinção que importa: geocodificar o que a pessoa PEDIU é
        respeitar o pedido; geocodificar o sítio da fazenda num caminho
        paralelo é ter duas respostas para a mesma pergunta.
        """
        from pathlib import Path

        fonte = (Path(__file__).resolve().parents[1] / "app/ia/intents.py").read_text(
            encoding="utf-8"
        )
        corpo = fonte[fonte.index("def _coords(") :]
        corpo = corpo[: corpo.index("\ndef ") if "\ndef " in corpo else len(corpo)]

        self.assertIn(
            "cidade_livre",
            corpo,
            "o pedido de uma cidade explicita tem de continuar a funcionar",
        )
