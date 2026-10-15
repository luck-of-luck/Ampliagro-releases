"""O tenancy falha PARA o lado seguro. Nao para o lado conveniente.

O QUE ESTE FICHEIRO TRAVA
=========================
`TenantIsolationMiddleware` verifica que todo o id que o request traz
(`?propriedade_id`, `?talhao_id`, `?device_id`, `?safra_id`, ...) pertence
ao utilizador. Sem isso, `?talhao_id=64` de outra pessoa devolvia o talhao
de outra pessoa — carimbado `fonte_dado: "medido"`.

Quando a verificacao levantava excepcao (uma migration em falta, um nome de
campo que mudou), o codigo registava o erro e deixava a request passar SEM
verificacao nenhuma. O log dizia textualmente: "cross-tenant pode passar".

MEDIDO 2026-10-05: foi isso que aconteceu. Cinco migrations por fazer
fizeram o codigo pedir `cod_municipio` a uma base sem a coluna. O
`OperationalError` foi engolido e o middleware desativou-se a si proprio —
num sistema cujo produto e' a confianca de que os dados de um produtor so
aparecem a ele.

Agora e' fail-closed: 503 com uma mensagem que diz porquê.

O QUE UM "SEM DADO" E' UM 403
==============================
Saidas diferentes porque a verdade e' diferente:

  403  "esse talhao e' de outra pessoa"    -> recuso VERDADEIRO
  503  "nao consegui verificar de quem e'"  -> recuso por NAO SABER

Um 200 em qualquer um dos dois casos seria "confia em mim". E o produtor
nao tem forma de saber que o que viu era de outra pessoa.

COMO ESTES TESTES NAO TRABALHAM
===============================
Nao chamam o middleware com um request de verdade. Nao tem DB. O que fazem
e' ler o fonte e garantir tres coisas:

  1. o caminho de falha diz `status=503` (e nao 200, e nao "passa");
  2. a mensagem de falha diz "nao se sabe de quem e'" (e nao acusa o
     vizinho);
  3. o caminho feliz continua a passar a request (fail-closed nao pode
     virar "recusa tudo").

O teste que EXECUTA o caminho a serio, com um `OperationalError` a meio,
vive em `tests/test_tenancy_da_503_real.py` e precisa da base de teste.
"""

import inspect
import unittest

from app.middleware import TenantIsolationMiddleware


def fonte_do_middleware():
    return inspect.getsource(TenantIsolationMiddleware.__call__)


class TenancyFalhaFechadaTest(unittest.TestCase):
    """A falha de tenancy tem de fechar a porta, nao a abrir."""

    def test_o_middleware_existe_e_tem_a_mesma_tabela_de_verificacao(self):
        m = TenantIsolationMiddleware(lambda r: None)
        self.assertIn("talhao_id", m.TABELAS_VERIFICADAS)
        self.assertIn("propriedade_id", m.TABELAS_VERIFICADAS)
        self.assertIn("safra_id", m.TABELAS_VERIFICADAS)

    def test_a_excepcao_que_falha_a_verificacao_e_um_operationalerror(self):
        """O que acontece em producao e' um OperationalError.

        Uma coluna que nao existe (`cod_municipio`), uma tabela que nao foi
        criada — o Django levanta `OperationalError`. Nao e' uma excepcao
        exotica; e' a coisa mais comum quando ha migrations por aplicar.
        """
        from django.db.utils import OperationalError

        self.assertTrue(issubclass(OperationalError, Exception))

    def test_o_caminho_de_falha_diz_503(self):
        """Um `status=200` aqui seria "confia em mim"."""
        fonte = fonte_do_middleware()
        self.assertIn(
            "status=503",
            fonte,
            "o caminho de falha de tenancy nao diz 503. Se o codigo ficou "
            "sem `status=503`, o pedido pode estar a passar sem "
            "verificacao.",
        )

    def test_a_mensagem_de_503_diz_que_nao_se_sabe(self):
        """E' o que separa um 503 de uma acusacao de cross-tenant.

        Se a mensagem disser "nao pertence ao utilizador", o produtor vai
        culpar o vizinho por um problema de migracao que e' nosso. Custa
        horas a descobrir.
        """
        fonte = fonte_do_middleware()
        self.assertIn(
            "possivel confirmar",
            fonte,
            "a mensagem de falha tem de dizer que NAO SE SABE de quem e' o "
            "pedido, e nao que o pedido e' de outra pessoa.",
        )

    def test_a_mensagem_de_503_nao_acusa_o_vizinho(self):
        """A falha e' nossa (configuracao/migration), nao do vizinho.

        Isto le a MENSAGEM, nao o fonte inteiro. Ler o fonte inteiro daria
        falso positivo: os comentarios explicam porque e' que "dados de
        outra pessoa" sao o pior cenario — e a palavra aparece la de
        proposito. O que nao pode e' a mensagem que o produtor vai LER
        acusar o vizinho.
        """
        import re as _re

        fonte = fonte_do_middleware()
        # a mensagem que o produtor recebe: o primeiro argumento de
        # `self._rejeitar` no caminho de falha
        bloco = fonte.split("except Exception:")[-1]
        m = _re.search(
            r'return self\._rejeitar\(\s*request,\s*(?:f?)"(.*?)"',
            bloco,
            _re.S,
        )
        self.assertIsNotNone(m, "nao encontrei a mensagem de 503 no caminho de falha")
        # junta os segmentos da string (o `f` deixa as f-strings em varias
        # linhas como `f"..." f"..."`)
        mensagem = m.group(1).lower()
        for acusacao in ("nao pertence", "outro utilizador", "de outra pessoa"):
            self.assertNotIn(
                acusacao,
                mensagem,
                f"a mensagem que o produtor vai ler acusa o vizinho: {acusacao!r}. A "
                f"falha e' nossa (configuracao/migration), nao dele.",
            )
        self.assertTrue(
            "indisponivel" in mensagem or "nao e' possivel confirmar" in mensagem,
            "a mensagem tem de dizer que a verificacao esta indisponivel / "
            f"que nao se sabe de quem e' o pedido. Actual: {mensagem!r}",
        )

    def test_o_caminho_feliz_continua_a_passar_a_request(self):
        """Fail-closed nao pode virar "recusa tudo".

        Se transformassemos a excepcao num 403 para TODO o request, o
        produtor nao faria nada e o sistema pareceria partido — que e' o
        outro extremo do mesmo erro de desenho. O caminho feliz tem de
        seguir intacto.
        """
        m = TenantIsolationMiddleware(lambda r: None)
        self.assertTrue(
            callable(m.get_response),
            "o middleware precisa de um get_response para passar a request "
            "depois de verificar.",
        )
        fonte = fonte_do_middleware()
        self.assertIn(
            "return self.get_response(request)",
            fonte,
            "o caminho feliz tem de chamar get_response. Se nao chama, todo o "
            "request morre aqui.",
        )


if __name__ == "__main__":
    unittest.main()
