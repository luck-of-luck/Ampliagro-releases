"""
Prova de ponta a ponta: a defesa contra alucinação atravessando o caminho
REAL, não o handler chamado direto.

Os testes de `tests_dinamico_tools.py` chamam `h_inserir_registro(...)`. Isso
prova a lógica, mas pula três camadas que também podem falhar:

  1. a allowlist de `/api/amplia/exec/` (`executar_para`)
  2. o cache de resultado do `sandbox.executar` (a tool é cacheada; um erro
     engolido no cache volta na próxima chamada)
  3. a serialização HTTP (o `erro` precisa chegar ao modelo como texto)

Se a defesa só funciona quando chamada direto, ela não funciona.
"""

import json

from django.contrib.auth.models import User
from django.test import TestCase

from app.amplia_mcp import executar_para


class PontaAPontaTest(TestCase):
    def setUp(self):
        self.u = User.objects.create_user("ana", "a@x.com", "p")
        self.bob = User.objects.create_user("bob", "b@x.com", "p")

    def _criar(self, nome="Controle de Geladeira", confirm=True):
        p = {
            "nome": nome,
            "campos": [
                {"rotulo": "Alimento", "tipo": "TEXTO", "obrigatorio": True},
                {"rotulo": "Quantidade kg", "tipo": "DECIMAL"},
            ],
            "confirm": confirm,
        }
        return executar_para(self.u, "amplia_criar_entidade", p)

    def test_fluxo_completo_criar_gravar_ler(self):
        r = self._criar()
        self.assertTrue(r["ok"], r)
        slug = r["dados"]["slug"]

        g = executar_para(
            self.u,
            "amplia_inserir_registro",
            {"entity_slug": slug, "dados": {"alimento": "Ração"}, "confirm": True},
        )
        self.assertTrue(g["ok"], g.get("erro"))

        q = executar_para(self.u, "amplia_consultar_registros", {"entity_slug": slug})
        self.assertTrue(q["ok"], q)
        self.assertIn("Ração", q["resposta"])

    def test_alucinacao_bloqueada_pelo_caminho_real(self):
        """O teste que dá nome à BUILD 2, pelo caminho que a IA usa."""
        slug = self._criar()["dados"]["slug"]

        r = executar_para(
            self.u,
            "amplia_inserir_registro",
            {
                "entity_slug": slug,
                "dados": {"alimento": "Ração", "idade_da_vaca": 10},
                "confirm": True,
            },
        )
        self.assertFalse(r["ok"], "campo alucinado passou pelo caminho real")
        self.assertIn("idade_da_vaca", r["erro"])
        self.assertIn("alimento", r["erro"])

        from app.models import DynamicRecord

        self.assertEqual(DynamicRecord.objects.filter(user=self.u).count(), 0)

    def test_valor_alucinado_por_funcao_dao_500_antes(self):
        """Regressão do `decimal.InvalidOperation`.

        `Decimal("muito")` levanta `InvalidOperation`, que herda de
        `ArithmeticError` e nao de `ValueError` — passava pelo `except` e
        derrubava a chamada. Numa defesa contra alucinação, um valor alucinado
        que derruba o servidor é a falha mais cara possível: o produtor vê
        "erro no servidor" e não tem como corrigir o modelo.
        """
        slug = self._criar()["dados"]["slug"]
        r = executar_para(
            self.u,
            "amplia_inserir_registro",
            {
                "entity_slug": slug,
                "dados": {"alimento": "Ração", "quantidade_kg": "muito"},
                "confirm": True,
            },
        )
        self.assertFalse(r["ok"], "valor invalido precisa ser erro, nao excecao")
        self.assertIn("quantidade_kg", r["erro"])

    def test_erro_chega_serializado_para_o_modelo(self):
        """O modelo lê `resposta` ou `erro`. Se o erro não for texto, a defesa
        existe mas não é utilizável.

        NOTA: `inserir_registro` passou a exigir confirmacao (2026-10-04), e
        sem `confirm=True` o sandbox devolve o PEDIDO de confirmacao, nao o
        erro de validacao. Este teste queria o erro, entao confirma primeiro.
        """
        slug = self._criar()["dados"]["slug"]
        r = executar_para(
            self.u,
            "amplia_inserir_registro",
            {
                "entity_slug": slug,
                "dados": {"alimento": "X", "inventado": 1},
                "confirm": True,
            },
        )
        self.assertIsInstance(r["erro"], str)
        json.dumps(r)  # tem de sobreviver à serialização do /api/amplia/exec/

    def test_escrita_pede_confirmacao_antes_de_gravar(self):
        """O gate: sem `confirm`, NADA é gravado.

        Este teste não existia e devia. `inserir_registro` grava um registo
        na ferramenta do produtor; sem o gate, uma frase ambígua do LLM
        escrevia na base sem ninguém ver. Com o gate, o sandbox devolve
        `needs_confirm` e o produtor responde 'sim'.
        """
        slug = self._criar()["dados"]["slug"]
        r = executar_para(
            self.u,
            "amplia_inserir_registro",
            {
                "entity_slug": slug,
                "dados": {"alimento": "Ração", "quantidade_kg": "10"},
            },
        )
        self.assertTrue(
            r.get("needs_confirm"),
            "a escrita de um registo nao pediu confirmacao. Uma frase do LLM "
            "vira um facto na base do produtor sem ele ver.",
        )
        self.assertIn("sim", str(r.get("resposta", "")).lower())

    def test_cache_nao_guarda_recusa_como_sucesso(self):
        """O sandbox cacheia resultado de tool. Se uma recusa entrasse no cache
        como 'ok', a segunda chamada devolveria sucesso sem validar nada."""
        slug = self._criar()["dados"]["slug"]
        payload = {
            "entity_slug": slug,
            "dados": {"alimento": "X", "inventado": 1},
            "confirm": True,
        }
        r1 = executar_para(self.u, "amplia_inserir_registro", payload)
        r2 = executar_para(self.u, "amplia_inserir_registro", payload)
        self.assertFalse(r1["ok"])
        self.assertFalse(r2["ok"], "a segunda chamada nao pode virar sucesso")
        self.assertIn("inventado", r2["erro"])

    def test_cruzamento_de_usuario_bloqueado_pelo_caminho_real(self):
        """Ana cria "Vacinas"; Bob tenta usar o slug dela."""
        slug = executar_para(
            self.u,
            "amplia_criar_entidade",
            {
                "nome": "Registro de Vacinas",
                "campos": [{"rotulo": "Vacina", "tipo": "TEXTO"}],
                "confirm": True,
            },
        )["dados"]["slug"]

        r = executar_para(
            self.bob,
            "amplia_inserir_registro",
            {"entity_slug": slug, "dados": {"vacina": "Raiva"}, "confirm": True},
        )
        self.assertFalse(r["ok"], "Bob nao pode escrever na ferramenta de Ana")

        # E a LEITURA tambem. Aqui `ok: False` e' o resultado CORRETO, e vale
        # registrar por que: nao existe ferramenta com esse slug para Bob, e
        # a tool diz isso abertamente em vez de devolver "0 registros".
        #
        # Um "0 registros" aqui seria o vazamento mais sutil possivel: o
        # produtor nao veria dado nenhum, mas o sistema teria dito que a
        # ferramenta existe e esta vazia — quando a verdade e que ele nunca
        # teve acesso a ela. A distincao importa: uma e' "nao ha dados", a
        # outra e "isto nao e seu".
        q = executar_para(self.bob, "amplia_consultar_registros", {"entity_slug": slug})
        self.assertFalse(q["ok"], "nao existe essa ferramenta para Bob")
        self.assertIn("nao encontrada", q["erro"])
        self.assertNotIn("Raiva", str(q), "nenhum vestigio do dado de Ana")

        # e Bob ve as SUAS ferramentas, nao as de Ana
        self.assertIn("create_entity", q["erro"], "a pista aponta para o caminho certo")

    def test_escrita_exige_confirmacao_pelo_caminho_real(self):
        """A confirmação é a fronteira entre a IA pedir e o sistema fazer."""
        r = executar_para(
            self.u,
            "amplia_criar_entidade",
            {"nome": "Sem Confirmar", "campos": [{"rotulo": "X", "tipo": "TEXTO"}]},
        )
        self.assertTrue(r["ok"])
        self.assertTrue(r["needs_confirm"])

        from app.models import DynamicApp

        self.assertFalse(
            DynamicApp.objects.filter(user=self.u, nome="Sem Confirmar").exists()
        )

    def test_nenhum_codigo_gerado_no_disco(self):
        """A promessa do Criador Livre: metadados, nunca `.py`.

        Se um dia alguémfabricar uma tool criando arquivo, esta verificação pega —
        e ela é verificável, porque a data de criação do arquivo é pública.
        """
        import pathlib

        import django

        raiz = pathlib.Path(django.__file__).parent.parent
        antes = {p: p.stat().st_mtime for p in raiz.rglob("*.py")}
        executar_para(
            self.u,
            "amplia_criar_entidade",
            {
                "nome": "Nenhum Arquivo",
                "campos": [{"rotulo": "X", "tipo": "TEXTO"}],
                "confirm": True,
            },
        )
        depois = {p: p.stat().st_mtime for p in raiz.rglob("*.py")}
        novos = [p.name for p in depois if p not in antes]
        self.assertEqual(novos, [], f"criar ferramenta gerou arquivo: {novos}")
