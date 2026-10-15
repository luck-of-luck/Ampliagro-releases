"""Testes do medidor de posto de seguranca.

Estes testes sao deterministas e nao dependem do `.env` da maquina: cada
cenario monta um objecto com os seis campos e diz o que espera. E' o oposto do
teste que escrevi primeiro e apaguei — aquele lia `config.settings.prod` de
verdade e, por isso, dava vermelho conforme a maquina onde corria. Um teste que
da vermelho por causa do ambiente em que corre treina a ignorar o vermelho.
"""

from types import SimpleNamespace

from app.services.posto_seguranca import (
    REGRAS,
    Lacuna,
    _ligada,
    lacunas,
    relatorio,
)

#: Todos ligados. E' o cenario de uma instalacao com certificado.
COMPLETO = {
    "SECURE_SSL_REDIRECT": True,
    "SESSION_COOKIE_SECURE": True,
    "CSRF_COOKIE_SECURE": True,
    "SECURE_HSTS_SECONDS": 31536000,
    "SECURE_HSTS_INCLUDE_SUBDOMAINS": True,
    "SECURE_HSTS_PRELOAD": True,
}

#: Todos desligados. E' a instalacao sem certificado: o Caddy serve http e
#: forcar o redirect seria um 301-em-loop.
SEM_CERTIFICADO = {
    "SECURE_SSL_REDIRECT": False,
    "SESSION_COOKIE_SECURE": False,
    "CSRF_COOKIE_SECURE": False,
    "SECURE_HSTS_SECONDS": 0,
    "SECURE_HSTS_INCLUDE_SUBDOMAINS": False,
    "SECURE_HSTS_PRELOAD": False,
}


class TestLeituraDasChaves:
    def test_a_flag_aceita_o_mesmo_vocabulario_do_prod_py(self):
        """`prod.py` le com `.lower() in ("true", "1", "t")`. Aqui e' igual.

        Se este medidor usasse um vocabulario diferente, podia dizer
        'ligada' sobre um valor que o Django le como 'desligada' — que e'
        precisamente o erro que ele existe para nao cometer.
        """
        for v in ("True", "true", "TRUE", "1", "t"):
            assert _ligada(v) is True, v
        for v in ("False", "false", "0", "", "f", "sim", "on"):
            assert _ligada(v) is False, v
        assert _ligada(31536000) is True
        assert _ligada(0) is False
        assert _ligada(True) is True

    def test_o_valor_texto_do_ambiente_e_uma_string(self):
        """O `.env` chega como texto; e' por isso que existe o `_ligada`.

        `SECURE_HSTS_SECONDS=0` da linha 7 do `.env` deste repositorio entra em
        `os.environ` como a string `"0"`. Sem a traducao, `bool("0")` e'
        verdade e o medidor contaria uma protecao desligada como ligada.

        A mesma undistincao vale para a outra direccao: `prod.py` le as FLAGS
        com `.lower() in ("true","1","t")`, mas le `SECURE_HSTS_SECONDS` com
        `int(...)`, onde "31536000" e' um ano e "0" e' desligado. `_ligada` tem
        de servir as duas: a string de um numero so conta como ligada se for
        verdade que nao e' zero.
        """
        assert _ligada("0") is False
        assert _ligada("True") is True
        assert _ligada("False") is False

    def test_hsts_le_se_com_int_e_precisa_da_palavra_certa(self):
        """`SECURE_HSTS_SECONDS` e' uma contagem, nao uma flag.

        `prod.py:46` le com `int(...)`. E' por isso que `_ligada` tem o
        argumento `numerica`: com o vocabulario de flag, `"31536000"` dava
        `False` e o medidor contava um ano de HSTS como desligado.

        Este teste fixa essa distincao. Sem ele, `numerica=True` pode ser
        removido por parecer redundante e o erro volta sem ninguem dar por ela.
        """
        assert _ligada("31536000", numerica=True) is True
        assert _ligada("0", numerica=True) is False
        assert _ligada(31536000, numerica=True) is True
        assert _ligada(0, numerica=True) is False

        # Um texto nao numerico nao e' uma proteccao ligada. `int()` rebenta
        # com ValueError, e rebentar seria uma excepcao em vez de uma lacuna.
        assert _ligada("muito", numerica=True) is False
        assert _ligada(None, numerica=True) is False

        # E sem `numerica`, o numero continua a ser lido como flag — que e' o
        # comportamento de `prod.py` para as chagas que ele le com `.lower()`.
        assert _ligada("31536000", numerica=False) is False


class TestLacunas:
    def test_uma_instalacao_completa_nao_tem_lacunas(self):
        assert lacunas(SimpleNamespace(**COMPLETO)) == []

    def test_a_instalacao_sem_certificado_reporta_as_seis(self):
        """E' o cenario que `docker-compose.prod.yml:37` descreve.

        Seis lacunas nao e' um alarme: e' o estado correcto daquele caso. O
        texto tem de dizer isso, ou o operador desiste de o ler.
        """
        achadas = lacunas(SimpleNamespace(**SEM_CERTIFICADO))

        assert len(achadas) == len(REGRAS)
        assert {a.chave for a in achadas} == set(REGRAS)

    def test_o_hsts_desligado_sozinho_aparece_so_ele(self):
        """O caso que este modulo persegue: so o HSTS em falta.

        `SECURE_SSL_REDIRECT=True`, cookies secure, e `SECURE_HSTS_SECONDS=0`.
        E' a instalacao com certificado e com o `.env` copiado de outro sitio.
        Os settings parecem correctos e o browser nunca recebe o cabecalho.
        """
        cenario = dict(COMPLETO, SECURE_HSTS_SECONDS=0)

        achadas = lacunas(SimpleNamespace(**cenario))

        assert [a.chave for a in achadas] == ["SECURE_HSTS_SECONDS"]
        assert achadas[0].valor == 0

    def test_a_chave_que_nao_existe_no_schema_nao_e_lacuna(self):
        """Falta de protecao e' diferente de campo inexistente.

        Os settings de teste podem nao ter `SECURE_HSTS_PRELOAD`. Dizer 'falta
        protecao' ali seria inventar um buraco num schema que nao o pediu.
        """
        parcial = {k: v for k, v in COMPLETO.items() if k != "SECURE_HSTS_PRELOAD"}

        achadas = lacunas(SimpleNamespace(**parcial))

        assert [a.chave for a in achadas] == []
        assert "completo" in relatorio(SimpleNamespace(**parcial))

    def test_a_lacuna_diz_de_onde_veio_o_valor(self):
        """`definida_no_ambiente` separa 'o .env mandou' de 'o default mandou'.

        Sao problemas diferentes com conselhos diferentes: um `.env` a dizer
        False e' corrigir uma linha; um default a ser False e' uma decisao do
        codigo. O texto tem de distinguir.
        """
        cenario = SimpleNamespace(**dict(COMPLETO, SECURE_HSTS_SECONDS=0))

        achada = lacunas(cenario)[0]

        assert achada.definida_no_ambiente == (
            "SECURE_HSTS_SECONDS" in __import__("os").environ
        )
        assert "definida no ambiente" in achada.em_texto() or (
            "NAO esta no ambiente" in achada.em_texto()
        )


class TestRelatorio:
    def test_o_relatorio_completo_nao_inventa_problemas(self):
        texto = relatorio(SimpleNamespace(**COMPLETO))

        assert "completo" in texto
        assert "desligadas" not in texto

    def test_cada_lacuna_diz_o_que_observar_para_confirmar(self):
        """O texto tem de ser accionavel: o que ligar, e como se ve.

        Um relatorio que so diz 'HSTS desligado' obriga o operador a saber o
        que procurar. Um que diz 'confirme o cabecalho na resposta' diz-lhe
        onde olhar.

        A busca e' por `strict-transport-security` em minusculas e NAO por
        `Strict-Transport-Security`. O suggestivo nao e' que o relatorio tenha
        o cabecalho mal escrito — e' que a suggestao de confirmar que ele trae
        usa `grep -i`, que nao distingue maiusculas. Um teste que exigisse a
        grafia exacta passava por erro, quando o texto esta certo.
        """
        cenario = SimpleNamespace(**dict(COMPLETO, SECURE_HSTS_SECONDS=0))

        texto = relatorio(cenario)

        assert "strict-transport-security" in texto.lower()
        assert "grep -i" in texto, (
            "a forma de confirmar tem de ser insensivel a maiusculas: o "
            f"cabecalho que se procura e' Strict-Transport-Security.\n{texto}"
        )
        assert "Para confirmar" in texto
        assert "1 de 6" in texto

    def test_o_relatorio_diz_que_nao_e_falha_de_codigo(self):
        """Sem esta frase, o operador corrige o `prod.py` e nao ganha nada.

        E' a armadilha medida: `base.py:9` faz `load_dotenv('.env')` antes de
        `prod.py` ler `os.environ`, e mudar o `prod.py` nao muda o resultado.
        Dizer isso no texto e' o que poupa a proxima sessao uma correccao
        inutil.
        """
        texto = relatorio(SimpleNamespace(**SEM_CERTIFICADO))

        assert "NAO e' uma falha do codigo" in texto
        assert "decisao de quem instala" in texto

    def test_o_relatorio_lembra_o_por_do_redirect_desligado(self):
        """Sao as duas linhas de `docker-compose.prod.yml:30-37`.

        Sem esta lembranca, 'redirect desligado' le-se como erro. Com ela, le-se
        como a unica saida de uma instalacao sem certificado.
        """
        texto = relatorio(SimpleNamespace(**SEM_CERTIFICADO))

        assert "docker-compose.prod.yml" in texto
        assert "301-em-loop" in texto


class TestContrato:
    def test_a_lacuna_e_imutavel(self):
        """E' um registo de leitura. Nao ha quem o altere a meio de um relatorio.

        Sem `frozen`, um `relatorio` que corresse enquanto outra coisa muda os
        settings imprimiria um numero diferente do que mediu.
        """
        lacuna = Lacuna("X", False, "significa", "observar", False)

        try:
            lacuna.valor = True
        except Exception:
            return  # congelado, como deve ser
        raise AssertionError("a Lacuna aceitou escrever: e' um registo de leitura")

    def test_toda_a_chave_de_regras_tem_uma_observacao(self):
        """Uma regra sem `observar` obriga o operador a saber o que procurar.

        `REGRAS` e' o dicionario de glossario do modulo. Uma entrada com a
        segunda posicao vazia estraga o relatorio inteiro em silencio.
        """
        for chave, (significa, observar) in REGRAS.items():
            assert significa.strip(), chave
            assert observar.strip(), chave

    def test_as_chaves_de_regras_sao_as_de_prod_py(self):
        """Se o `prod.py` endurecer outra chave, este modulo tem de a cobrir.

        Estas seis sao as de `config/settings/prod.py:31-54`. Um dia haver uma
        setima e este teste tem de falhar — e' o aviso.
        """
        assert set(REGRAS) == {
            "SECURE_SSL_REDIRECT",
            "SESSION_COOKIE_SECURE",
            "CSRF_COOKIE_SECURE",
            "SECURE_HSTS_SECONDS",
            "SECURE_HSTS_INCLUDE_SUBDOMAINS",
            "SECURE_HSTS_PRELOAD",
        }
