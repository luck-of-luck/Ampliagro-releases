"""O direito de acesso devolvia 5 campos, e o de esquecimento nao apagava nada.

OS DEFEITOS
===========
1. `/lgpd/export/` respondia 130 bytes:

       {"user": {id, username, email}, "perfil": {tipo_usuario, tema}}

   Para a fazenda que existia no banco: 18 talhoes, 12 safras, 4 lancamentos,
   2 maquinarios, 3 funcionarios, 8 dispositivos, 115 execucoes de IA, 113
   eventos, 17 artefatos, 68 widgets, 8 notificacoes — e o endereco rural
   completo. Nada disso saia.

   O Art. 18, II da LGPD da acesso "aos dados pessoais que lhe concerne,
   inclusive sobre o tratamento realizado". Quem exerce o direito recebia um
   JSON de 5 campos e tinha de voltar a pedir de novo — e o atendimento nao
   pode depender de o titular insistir.

2. `/lgpd/delete/` anunciava "Dados anonimizados" e nao anonimizava:

       perfil.nome = "Usuário Removido"
       perfil.save()

   `PerfilUsuario` nao tem campo `nome`. A atribuicao virava atributo
   avulso, o `save()` nao tinha o que gravar, e um `except Exception: pass`
   engolia o resto. O perfil continuava intacto. E o dado que mais
   identifica — CPF/CNPJ da propriedade — nunca era tocado.

A REGRA QUE FICA
================
1. Pedido de acesso devolve TUDO do titular, com contagem por bloco. A
   contagem e' o que permite verificar se veio inteiro.
2. Export e' do titular e das fazendas dele. Nunca inclui a fazenda de outro
   usuario.
3. Segredo nao e' dado pessoal e nao viaja: a chave do gateway fica de fora.
4. "Anonimizado" e' verificavel: cada campo tocado entra no retorno, e o que
   fica retido e' dito com o motivo.
5. Nenhum `except: pass` num direito que o titular exerce. Falhou, avisa.

O QUE ESTE TESTE TRAVA
======================
1. O export traz os registros da fazenda, e nao so a conta.
2. Cada bloco diz quantos registros sairam.
3. A exportacao nao vaza a fazenda de outro usuario.
4. Segredo de gateway e' barrado.
5. A anonimizacao grava em campo que existe e diz o que preservou.
"""

import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from app.models import (
    Cultura,
    Device,
    Gateway,
    LancamentoFinanceiro,
    PerfilUsuario,
    Propriedade,
    Safra,
    Talhao,
)
from app.views.lgpd import lgpd_delete_data, lgpd_export_data

User = get_user_model()


def _export(user):
    req = RequestFactory().get("/lgpd/export/")
    req.user = user
    resp = lgpd_export_data(req)
    return resp, json.loads(resp.content)


class ExportaOTudoDoTitular(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "titular", "titular@t.com", "x", first_name="Ana", last_name="Souza"
        )
        self.prop = Propriedade.objects.create(
            user=self.user,
            nome="Fazenda da Ana",
            cidade="Muzambinho",
            uf="MG",
            endereco="Estrada X, Km 2 - Zona Rural",
            cpf_cnpj="12345678900",
            caepf="CAF-123",
            area_total=Decimal("100.00"),
        )
        self.soja = Cultura.objects.create(nome="Soja")
        self.safra = Safra.objects.create(
            propriedade=self.prop,
            cultura=self.soja,
            ano=2026,
            safra_nome="Soja 26/27",
            area_plantada=Decimal("80.0"),
        )
        for i in range(4):
            Talhao.objects.create(
                propriedade=self.prop,
                nome=f"Talhão {i}",
                area_hectare=Decimal("20.0"),
                cultura_atual=self.soja,
            )
        for i in range(3):
            LancamentoFinanceiro.objects.create(
                propriedade=self.prop,
                data="2026-10-01",
                tipo="DESPESA",
                valor=Decimal("100.00"),
                descricao=f"nota {i}",
            )
        Gateway.objects.create(
            propriedade=self.prop,
            nome="GW-01",
            tipo="WIFI",
            gateway_eui="EUI-1",
            api_key="SEGREDO-QUE-NAO-PODE-VAZAR",
        )
        Device.objects.create(
            propriedade=self.prop, nome="Sensor", tipo="METEO", device_eui="D1"
        )

    def test_nao_e_mais_um_json_de_cinco_campos(self):
        """Antes: 130 bytes com a conta e mais nada."""
        _, body = _export(self.user)
        self.assertGreaterEqual(len(body), 8, msg=f"chaves={list(body)}")
        for chave in ("conta", "propriedades", "dados_operacionais", "ia", "resumo"):
            self.assertIn(chave, body, msg=f"faltou o bloco {chave!r}")

    def test_traz_os_registros_da_fazenda(self):
        _, body = _export(self.user)
        bloco = body["dados_operacionais"][str(self.prop.id)]
        self.assertEqual(bloco["talhoes"]["total"], 4)
        self.assertEqual(bloco["safras"]["total"], 1)
        self.assertEqual(bloco["lancamentos_financeiros"]["total"], 3)
        self.assertEqual(bloco["dispositivos"]["total"], 1)
        self.assertEqual(bloco["gateways"]["total"], 1)

    def test_cada_bloco_diz_quantos_registros_sairam(self):
        """Sem contagem, um export parcial e' indistinguivel de um completo."""
        _, body = _export(self.user)
        bloco = body["dados_operacionais"][str(self.prop.id)]
        for nome, v in bloco.items():
            if isinstance(v, dict):
                self.assertIn("total", v, msg=f"bloco {nome} sem contagem")
                self.assertEqual(
                    v["total"], len(v["registros"]), msg=f"bloco {nome} inconsistente"
                )
        self.assertEqual(body["resumo"]["talhoes"], 4)
        self.assertEqual(body["resumo"]["safras"], 1)
        self.assertEqual(body["resumo"]["lancamentos_financeiros"], 3)

    def test_a_conta_continua_vindo(self):
        """As duas chaves antigas sao contrato: o link de privacidade usa elas."""
        _, body = _export(self.user)
        self.assertEqual(body["user"]["username"], "titular")
        self.assertEqual(body["perfil"]["tipo_usuario"], "produtor")
        self.assertEqual(body["conta"]["first_name"], "Ana")

    def test_nao_vaza_a_fazenda_de_outro_usuario(self):
        outro = User.objects.create_user("outro", "outro@t.com", "x")
        prop_outro = Propriedade.objects.create(
            user=outro,
            nome="Fazenda do Outro",
            cidade="Ribeirão Preto",
            uf="SP",
            area_total=Decimal("50.00"),
        )
        Talhao.objects.create(
            propriedade=prop_outro,
            nome="Talhão secreto do outro",
            area_hectare=Decimal("5.0"),
        )
        resp, _ = _export(self.user)
        bruto = resp.content.decode("utf-8")
        self.assertNotIn("Fazenda do Outro", bruto)
        self.assertNotIn("Talhão secreto do outro", bruto)

    def test_segredo_do_gateway_nao_viaja(self):
        """`api_key` e' texto puro: quem receber pode publicar na fazenda."""
        resp, _ = _export(self.user)
        bruto = resp.content.decode("utf-8")
        self.assertNotIn("SEGREDO-QUE-NAO-PODE-VAZAR", bruto)
        self.assertNotIn("api_key", bruto)

    def test_pessoas_de_terceiros_nao_sao_exportadas(self):
        """Funcionario e' dado de terceiro: sai a contagem, nao o cadastro.

        O direito de acesso e' do titular. CPF, salario e endereco de quem
        trabalha na fazenda sao dados do FUNCIONARIO, e o tratamento e' da
        fazenda. Exportar a folha aqui fazia do produtor uma segunda via de
        dado pessoal de terceiro — e contradizia o que o `delete` dizia ao
        mesmo titular sobre quem responde por esse dado.
        """
        from app.models import Funcionario

        Funcionario.objects.create(
            propriedade=self.prop,
            nome="João Bitencourt",
            cargo="VAQUEIRO",
            salario=Decimal("3000.00"),
            data_admissao="2024-01-15",
        )
        resp, body = _export(self.user)
        bruto = resp.content.decode("utf-8")
        self.assertNotIn("João Bitencourt", bruto)
        self.assertNotIn("VAQUEIRO", bruto)
        bloco = body["dados_operacionais"][str(self.prop.id)]["funcionarios"]
        self.assertEqual(bloco["total"], 1, msg="a contagem tem de vir")
        self.assertEqual(bloco["registros"], [])
        self.assertIn("nota", bloco)


class AnonimizacaoGravaNoCampoCerto(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "some", "some@t.com", "x", first_name="Nome Real"
        )
        self.prop = Propriedade.objects.create(
            user=self.user,
            nome="Fazenda",
            cidade="Muzambinho",
            uf="MG",
            cpf_cnpj="12345678900",
            caepf="CAF-9",
            inscricao_estadual="ISENTO",
            area_total=Decimal("10.00"),
        )

    def _delete(self):
        req = RequestFactory().post("/lgpd/delete/")
        req.user = self.user
        resp = lgpd_delete_data(req)
        return resp, json.loads(resp.content)

    def test_nao_engole_o_erro(self):
        """Antes: `except: pass` transformava falha em 'Anonimizado'."""
        resp, body = self._delete()
        self.assertEqual(resp.status_code, 200, msg=f"corpo={body}")
        self.assertTrue(body.get("ok"))

    def test_apaga_a_conta(self):
        self._delete()
        u = User.objects.get(pk=self.user.pk)
        self.assertEqual(u.username, f"anonimizado_{self.user.pk}")
        self.assertEqual(u.email, f"deleted_{self.user.pk}@example.invalid")
        self.assertEqual(u.first_name, "")
        self.assertFalse(u.is_active)
        self.assertFalse(u.has_usable_password())

    def test_escreve_em_campo_que_existe_no_perfil(self):
        """O defeito: `perfil.nome`, campo que PerfilUsuario nao tem."""
        perfil = PerfilUsuario.objects.get(user=self.user)
        self.assertFalse(
            hasattr(perfil, "nome") and perfil._meta.get_field("nome"),
            msg="premissa do teste mudou: PerfilUsuario passou a ter 'nome'",
        )
        self._delete()
        perfil.refresh_from_db()
        self.assertEqual(perfil.tipo_usuario, "anonimizado")
        self.assertFalse(perfil.ativo_servidor)

    def test_apaga_o_documento_da_propriedade(self):
        """O dado que mais identifica e' o CPF/CNPJ — e nunca era tocado."""
        self._delete()
        p = Propriedade.objects.get(pk=self.prop.pk)
        self.assertEqual(p.cpf_cnpj, "")
        self.assertEqual(p.caepf, "")
        self.assertEqual(p.inscricao_estadual, "")

    def test_diz_o_que_ficou_e_por_que(self):
        """Apagar lancamento fiscal quebraria guarda legal. Dizer e' obrigacao."""
        _, body = self._delete()
        self.assertIn("preservado", body)
        preservado = body["preservado"]
        self.assertIn("talhoes_safras_lancamentos", preservado)
        self.assertIn("funcionarios", preservado)
        for motivo in preservado.values():
            self.assertTrue(motivo.strip(), msg="motivo vazio")

    def test_get_nao_anonimiza(self):
        req = RequestFactory().get("/lgpd/delete/")
        req.user = self.user
        resp = lgpd_delete_data(req)
        self.assertEqual(resp.status_code, 400)
        u = User.objects.get(pk=self.user.pk)
        self.assertTrue(u.is_active, msg="GET desativou a conta")
