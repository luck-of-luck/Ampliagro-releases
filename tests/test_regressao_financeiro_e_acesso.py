"""O financeiro respondia 500, e o custo por hectare dividia por 1,0 ha inventado.

OS DEFEITOS
===========
O "Comparativo de Safras" era uma tela morta, por dois motivos empilhados:

1. `comparativo_safras_data` ordenava por `Safra.data_inicio` — campo que nao
   existe. O calendario da safra tem `data_plantio` e `data_colheita`. O
   FieldError era engolido pelo `except Exception` da propria view, que devolvia
   500 com o texto cru do Django dentro do JSON.
2. Logo depois, o rotulo usava `s.nome`. Tambem nao existe: o campo e'
   `safra_nome`. Entao, mesmo corrigindo o `order_by`, o `AttributeError`
   derrubava a tela no primeiro item da lista.

E o "custo por hectare" mentia sem avisar:

3. `calcular_custo_producao` lia `Safra.talhoes` — a M2M `app_safratalhao`,
   que esta VAZIA. A soma dava 0 e caia no fallback `or Decimal("1.0")`. O
   produtor recebia "custo por hectare" dividido por UM hectare que ele nunca
   declarou, e o numero saia plausivel. Quem tem o dado real e' a FK
   `Talhao.safra`, que estava preenchida.
4. O mesmo codigo lia `safra.producao_estimada`; o campo do modelo e'
   `producao_total`. Toda safra quebrava — mascarado pelo erro 1, que vinha
   antes. E com `producao_total = 0` a divisao por unidade levantava
   ZeroDivisionError.

A REGRA QUE FICA
===============
1. Campo que o modelo nao tem nao se escreve: o nome se le do `_meta`.
2. Nao se divide por um valor inventado para "evitar divisao por zero". Ou se
   tem a area, ou se diz que falta area.
3. Ausencia de perfil e' negacao de acesso, nunca concessao.
4. Logout e' POST: um `<a href>` para uma rota POST-only devolve 405 e nao sai.

O QUE ESTE TESTE TRAVA
=======================
1. O comparativo responde 200 e toda safra tem rotulo.
2. Nao existe mais `data_inicio` nem `s.nome` na view.
3. O custo por hectare usa a area que existe, e diz quando nao existe.
4. Producao zero nao divide.
5. Quem nao tem perfil nao entra no Kanban.
6. Os templates de logout do servidor usam form POST.
"""

import pathlib
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from app.api.views.financial import comparativo_safras_data
from app.models import Cultura, PerfilUsuario, Propriedade, Safra, Talhao
from app.services.custo_producao import calcular_custo_producao
from app.views.utils import kanban_allowed

User = get_user_model()

APP_DIR = pathlib.Path(__file__).resolve().parents[1]


class ComparativoDeSafrasNaoQuebra(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("fin_t", "fin_t@t.com", "x")
        self.user.backend = "django.contrib.auth.backends.ModelBackend"
        self.prop = Propriedade.objects.create(
            user=self.user,
            nome="Fazenda",
            cidade="Muzambinho",
            uf="MG",
            area_total=Decimal("500.00"),
        )
        self.soja = Cultura.objects.create(nome="Soja")

    def _safra(self, nome, area="100.0"):
        return Safra.objects.create(
            propriedade=self.prop,
            cultura=self.soja,
            ano=2026,
            safra_nome=nome,
            area_plantada=Decimal(area),
            data_plantio="2026-09-01",
        )

    def _get(self):
        req = RequestFactory().get("/api/financeiro/comparativo-safras/")
        req.user = self.user
        return comparativo_safras_data(req)

    def test_responde_200_e_tem_safras(self):
        """Antes: 500 com 'Cannot resolve keyword data_inicio'."""
        self._safra("Soja 26/27")
        r = self._get()
        self.assertEqual(r.status_code, 200, msg=f"corpo={r.data}")
        self.assertEqual(len(r.data["comparativo"]), 1)

    def test_toda_safra_tem_rotulo(self):
        """Antes: `s.nome` levantava AttributeError no primeiro item."""
        self._safra("Soja 26/27")
        self._safra("Milho 26/27")
        r = self._get()
        self.assertEqual(r.status_code, 200, msg=f"corpo={r.data}")
        for item in r.data["comparativo"]:
            self.assertTrue(item["nome"], msg=f"safra {item['id']} voltou sem rotulo")

    def test_a_view_nao_usa_campo_inexistente(self):
        """Trava a regressao na raiz: os nomes precisam existir no model."""
        src = (APP_DIR / "app" / "api" / "views" / "financial.py").read_text(
            encoding="utf-8"
        )
        campos = {f.name for f in Safra._meta.get_fields() if hasattr(f, "attname")}
        # `data_inicio` e' campo de outro model (Conciliacao), nao de Safra
        self.assertNotIn("data_inicio", campos)
        self.assertIn("data_plantio", campos)
        self.assertNotIn("nome", campos, msg="Safra nao tem 'nome' — use safra_nome")
        self.assertIn("safra_nome", campos)
        self.assertNotIn(
            'order_by("-data_inicio")',
            src,
            msg="view ainda ordena por campo que Safra nao tem",
        )


class CustoPorHectareNaoMente(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("custo_t2", "custo_t2@t.com", "x")
        self.prop = Propriedade.objects.create(
            user=self.user,
            nome="Fazenda",
            cidade="Muzambinho",
            uf="MG",
            area_total=Decimal("500.00"),
        )
        self.soja = Cultura.objects.create(nome="Soja")

    def test_usa_a_area_que_a_safra_declara(self):
        """A area do custo/ha e' a da SAFRA, nao a soma dos talhoes.

        O codigo antigo somava `safra.talhoes` (M2M `app_safratalhao`, vazia no
        banco) e caia no fallback `or Decimal("1.0")`: dividia por 1 hectare
        inventado. Uma safra declara 250 ha e tem 3 talhoes de 10 ha; a resposta
        honesta e' 250, porque o numerador (despesas desta safra) e' do mesmo
        periodo que o `area_plantada`.
        """
        s = Safra.objects.create(
            propriedade=self.prop,
            cultura=self.soja,
            ano=2026,
            safra_nome="Soja",
            area_plantada=Decimal("250.0"),
            producao_total=Decimal("900"),
        )
        for i in range(3):
            Talhao.objects.create(
                propriedade=self.prop,
                nome=f"T{i}",
                area_hectare=Decimal("10.0"),
            )

        r = calcular_custo_producao(s.id)
        self.assertEqual(r["area_total_ha"], 250.0)
        self.assertEqual(r["area_origem"], "area_plantada")
        self.assertNotEqual(
            r["area_total_ha"], 1.0, msg="voltou a dividir por 1 hectare inventado"
        )

    def test_area_vem_do_talhao_quando_a_safra_nao_declara(self):
        """Safra sem `area_plantada` usa o talhao ligado pelo FK `Safra.talhao`."""
        s = Safra.objects.create(
            propriedade=self.prop,
            cultura=self.soja,
            ano=2026,
            safra_nome="Soja",
            area_plantada=Decimal("0"),
            producao_total=Decimal("900"),
        )
        t = Talhao.objects.create(
            propriedade=self.prop, nome="T", area_hectare=Decimal("12.5")
        )
        s.talhao = t
        s.save(update_fields=["talhao"])

        r = calcular_custo_producao(s.id)
        self.assertEqual(r["area_total_ha"], 12.5)
        self.assertEqual(r["area_origem"], "talhoes")

    def test_safra_sem_area_diz_que_falta(self):
        """Antes: 0 silencioso, lido como preco."""
        s = Safra.objects.create(
            propriedade=self.prop,
            cultura=self.soja,
            ano=2026,
            safra_nome="Soja",
            area_plantada=Decimal("0"),
            producao_total=Decimal("10"),
        )
        r = calcular_custo_producao(s.id)
        self.assertEqual(r.get("erro"), "safra_sem_area")
        self.assertIsNone(r["custo_por_hectare"])

    def test_producao_zero_nao_divide(self):
        """Antes: ZeroDivisionError."""
        s = Safra.objects.create(
            propriedade=self.prop,
            cultura=self.soja,
            ano=2026,
            safra_nome="Soja",
            area_plantada=Decimal("50.0"),
            producao_total=Decimal("0"),
        )
        r = calcular_custo_producao(s.id)  # nao pode levantar
        self.assertIsNone(r["custo_por_unidade"])

    def test_nao_acusa_producao_estimada_que_nao_existe(self):
        """`producao_total` e' o campo; `producao_estimada` nunca existiu."""
        campos = {f.name for f in Safra._meta.get_fields() if hasattr(f, "attname")}
        self.assertIn("producao_total", campos)
        self.assertNotIn("producao_estimada", campos)
        s = Safra.objects.create(
            propriedade=self.prop,
            cultura=self.soja,
            ano=2026,
            safra_nome="Soja",
            area_plantada=Decimal("50.0"),
            producao_total=Decimal("120"),
        )
        r = calcular_custo_producao(s.id)
        self.assertEqual(r["producao_estimada"], 120.0)


class SemPerfilNaoEntraNoKanban(TestCase):
    """`kanban_allowed` fazia `except DoesNotExist: return True`.

    `app/signals.py` cria o perfil em toda conta nova, entao o caminho normal
    nunca chega aqui. O que chega e' a conta LEGADA: criada antes do sinal,
    por `bulk_create`, por SQL cru, ou por restauracao de backup. No banco real
    eram duas contas (`testuser`, `test_nav`) — e elas entravam com acesso total.
    """

    def test_conta_orfa_sem_perfil_e_negada(self):
        u = User.objects.create_user("orfa_t", "orfa@t.com", "x")
        # o sinal criou o perfil; removemos para reproduzir a conta legada.
        # Relemos o user do banco: o related object ficaria em cache na
        # instancia original e o teste mediria a cache, nao o banco.
        PerfilUsuario.objects.filter(user=u).delete()
        orfa = User.objects.get(pk=u.pk)
        self.assertFalse(
            PerfilUsuario.objects.filter(user=orfa).exists(),
            msg="pre-condicao do teste: a conta tem de ficar sem perfil",
        )
        self.assertFalse(kanban_allowed(orfa))

    def test_produtor_com_perfil_continua_entrando(self):
        """A correcao nao pode trancar o produtor legitimo."""
        u = User.objects.create_user("prod_t", "p@t.com", "x")
        perfil = PerfilUsuario.objects.get(user=u)  # criado pelo sinal
        self.assertEqual(perfil.tipo_usuario, "produtor")
        self.assertTrue(kanban_allowed(u))

    def test_cada_tipo_de_servidor_continua_entrando(self):
        for tipo in ("servidor", "operario", "agronomo", "mecanico", "administrativo"):
            u = User.objects.create_user(f"srv_{tipo}", f"{tipo}@t.com", "x")
            PerfilUsuario.objects.filter(user=u).update(tipo_usuario=tipo)
            self.assertTrue(kanban_allowed(u), msg=f"{tipo} perdeu o acesso")

    def test_anonimo_continua_negado(self):
        from django.contrib.auth.models import AnonymousUser

        self.assertFalse(kanban_allowed(AnonymousUser()))


class LogoutEhPostEmTodoLugar(TestCase):
    """`logout_view` tem @require_POST. `<a href>` faz GET e leva 405."""

    def test_templates_de_saida_nao_usam_anchor_de_get(self):
        alvos = [
            "app/templates/servidor/dashboard.html",
            "app/templates/globais/erro_hierarquia.html",
        ]
        for rel in alvos:
            txt = (
                (APP_DIR / rel)
                .read_text(encoding="utf-8")
                .replace("{% url 'logout' %}", "/logout/")
            )
            self.assertNotIn(
                '<a href="/logout/"',
                txt,
                msg=f"{rel}: link de GET para rota POST-only devolve 405",
            )
            self.assertIn(
                '<form action="/logout/" method="post"',
                txt,
                msg=f"{rel}: faltou form POST de logout",
            )
