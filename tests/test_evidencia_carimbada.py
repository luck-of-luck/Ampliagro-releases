"""A evidencia tem de dizer de onde veio cada numero — ou nao vir nada.

O QUE ESTE FICHEIRO FECHA
-------------------------
`PrescricaoVRA.contexto_recomendacao` e `MedicaoExperimental.contexto` eram
`JSONField` livres. Aceitavam `{"temp": 24}`.

Isso e' uma porta dos fundos, e nao uma pequena: o README vende

    `fonte_dado: medido | sem_dado | simulado`

como o diferencial do produto. Um campo livre onde se pode gravar um numero sem
carimbo **anula esse diferencial no sitio onde ele e' auditado**. Um investidor
ou comprador que abre a procedencia e encontra `{"temp": 24}` tira a conclusao
oposta — e a culpa e' do produto, nao do dado.

A REGRA, E POR QUE NAO E' "OBRIGATORIO"
---------------------------------------
    `{}`                      -> ACEITE. Ausencia declarada e' honestidade.
    qualquer outra coisa      -> cada folha traz o seu `fonte_dado`.

O caminho de recusar "sem sensor" como erro seria contra-producente: o produtor
nao tem sensor, o formulario nao deixa gravar, e ele escreve `sem_dado` apressado
em tudo para passar. **Um campo obrigatorio nao produz dados honestos; produz
dados conformes.** E' o mesmo motivo de `produtividade_esperada` ser NULL e nao 0.
"""

from __future__ import annotations

import pytest
from django.core.exceptions import ValidationError

from app.validators import ESTADOS_FONTE, validate_evidencia


@pytest.fixture
def user(db):
    from django.contrib.auth.models import User

    return User.objects.create_user("evid", password="x")


@pytest.fixture
def propriedade(user):
    from app.models import Propriedade

    return Propriedade.objects.create(user=user, nome="F", area_total=100)


@pytest.fixture
def talhao(propriedade):
    from app.models import Talhao

    return Talhao.objects.create(
        propriedade=propriedade, nome="T", area_hectare=10, ativo=True
    )


@pytest.fixture
def cultura():
    from app.models import Cultura

    return Cultura.objects.create(nome="Soja", grupo="graos")


@pytest.fixture
def safra(propriedade, talhao, cultura):
    from app.models import Safra

    return Safra.objects.create(
        propriedade=propriedade,
        talhao=talhao,
        cultura=cultura,
        ano=2026,
        area_plantada=10,
    )


# ============================================== o que tem de ser aceite


class TestAceita:
    def test_vazio_e_a_ausencia_declarada(self):
        """`{}` nao e' "sem informacao" — e' "nao gravei evidencia", dito."""
        for vazio in ({}, None, []):
            validate_evidencia(vazio)  # nao levanta

    def test_a_forma_que_o_cliente_produz(self):
        """O que o `experiment.js` constroi tem de passar.

        Se este teste falhar, a correcao e' no validador ou no cliente — nunca
        nos dois, e nunca afrouxando o validador.
        """
        validate_evidencia(
            {
                "fonte_dado": "medido",
                "origem": "LeituraSensor",
                "clima": {
                    "temp": {
                        "valor": 24.0,
                        "unidade": "C",
                        "fonte_dado": "medido",
                        "timestamp": "2026-10-01T12:00:00Z",
                    }
                },
                "solo": {
                    "ph": {"valor": 6.8, "unidade": "pH", "fonte_dado": "suspect"}
                },
            }
        )

    def test_ausencia_tambem_se_carimba(self):
        """`{"fonte_dado": "sem_dado"}` sem numero e' folha, e e' valida.

        E' o caso mais importante: "o sensor nao existia" precisa de ser
        registavel, ou o produtor nao tem forma de dizer a verdade.
        """
        validate_evidencia({"solo": {"ph": {"fonte_dado": "sem_dado"}}})

    def test_os_quatro_estados(self):
        for estado in ESTADOS_FONTE:
            validate_evidencia({"clima": {"temp": {"fonte_dado": estado}}})


# ============================================== o que tem de ser recusado


class TestRecusa:
    def test_numero_nu_sem_carimbo(self):
        """A porta dos fundos, exactamente como estava."""
        com = pytest.raises(ValidationError, match="temp")
        with com:
            validate_evidencia({"clima": {"temp": 24}})

    def test_um_dos_varios_sem_carimbo_e_recusado(self):
        """Nao basta os outros estarem bons — o que falta e' o que engana."""
        with pytest.raises(ValidationError, match="ph"):
            validate_evidencia(
                {
                    "clima": {"temp": {"valor": 24, "fonte_dado": "medido"}},
                    "solo": {"ph": {"valor": 6.8}},
                }
            )

    def test_fonte_dado_inventado(self):
        """`"confiavel"` nao e' um estado. Um estado inventado e' um 0 disfarçado.

        E' a mensagem que tem de ser **util**, e ela e': o caminho exacto e o
        valor. `clima.temp.fonte_dado='confiavel'` diz ao produtor onde esta o
        erro, e o validador tem de dizer tambem o que escrever em vez disso —
        senao o produtor fica a adivinhar um vocabulario.
        """
        with pytest.raises(ValidationError) as exc:
            validate_evidencia({"clima": {"temp": {"fonte_dado": "confiavel"}}})
        texto = str(exc.value)
        assert "clima.temp" in texto, texto
        assert "confiavel" in texto, texto
        for estado in sorted(ESTADOS_FONTE):
            assert estado in texto, f"a mensagem nao diz o que escrever: {estado}"

    def test_a_mensagem_diz_o_que_fazer(self):
        """Um erro que nao diz o caminho e' um beco — em qualquer sitio.

        O produtor tem de conseguir responder a pergunta sem ajuda: ponho
        `sem_dado`, ou deixo vazio?
        """
        with pytest.raises(ValidationError) as exc:
            validate_evidencia({"clima": {"temp": 24}})
        texto = str(exc.value)
        assert "sem_dado" in texto, texto
        assert "temp" in texto, texto

    def test_o_erro_diz_o_que_esta_vazio_e_significa(self):
        with pytest.raises(ValidationError) as exc:
            validate_evidencia({"clima": {"temp": 24}})
        assert "não gravei evidência" in str(exc.value), str(exc.value)

    def test_o_bloco_tem_de_ser_objecto(self):
        with pytest.raises(ValidationError):
            validate_evidencia([24, 25])


# ==================================== e a ligacao: isto esta mesmo ligado?


class TestLigadoAoModelo:
    """Um validador que ninguem chama nao protege nada."""

    def test_o_prescricao_tem_o_validador(self):
        from app.models import PrescricaoVRA

        # `get_field` e' a via correcta: `field.validators` e' onde o Django
        # guarda o que chama no `full_clean()`.
        campo = PrescricaoVRA._meta.get_field("contexto_recomendacao")
        validadores = [v.__name__ for v in campo.validators]
        assert "validate_evidencia" in validadores, validadores

    def test_a_medicao_tem_o_validador(self):
        from app.models import MedicaoExperimental

        campo = MedicaoExperimental._meta.get_field("contexto")
        validadores = [v.__name__ for v in campo.validators]
        assert "validate_evidencia" in validadores, validadores

    def test_o_full_clean_rejeita_o_numero_nu(
        self, db, user, propriedade, talhao, cultura, safra
    ):
        """O ponto que importa: o `full_clean()` tem de recusar.

        E' o que o DRF chama antes de gravar, e o que `manage.py` chama em
        `--check`. Um validador no modelo que so falha quando alguem se lembra
        de chamar nao protege nada.
        """
        from app.models import PrescricaoVRA

        p = PrescricaoVRA(
            safra=safra,
            talhao=talhao,
            cultura=cultura,
            tipo_insumo="FERTILIZANTE",
            dose_ha=100,
            unidade="kg/ha",
            grade_geojson={"type": "FeatureCollection", "features": []},
            contexto_recomendacao={"clima": {"temp": 24}},
        )
        with pytest.raises(ValidationError):
            p.full_clean()

    def test_o_full_clean_aceita_a_vazio(
        self, db, user, propriedade, talhao, cultura, safra
    ):
        """Sem evidencia continua a ser uma prescricao valida.

        Se isto falhasse, o validador estava a obrigar o produtor a ter sensor
        para semear — e a incentive a mentir.
        """
        from app.models import PrescricaoVRA

        p = PrescricaoVRA(
            safra=safra,
            talhao=talhao,
            cultura=cultura,
            tipo_insumo="FERTILIZANTE",
            dose_ha=100,
            unidade="kg/ha",
            # `grade_geojson` tem uma validacao propria que recusa vazio. Nao e'
            # do A2b e nao se mexe; e so preciso para o `full_clean` chegar ao
            # campo que este teste quer exercitar.
            grade_geojson={"type": "FeatureCollection", "features": []},
        )
        p.full_clean()
        p.save()
        assert p.pk is not None

    def test_a_api_tambem_recusa(
        self, client, user, propriedade, talhao, cultura, safra
    ):
        """A API e' por onde o dado entra a serio. Se so o modelo valida,
        um POST directo passa por cima."""
        client.force_login(user)
        r = client.post(
            "/api/prescricoes-vra/",
            {
                "safra": safra.pk,
                "talhao": talhao.pk,
                "cultura": cultura.pk,
                "tipo_insumo": "FERTILIZANTE",
                "dose_ha": "100",
                "unidade": "kg/ha",
                "contexto_recomendacao": {"clima": {"temp": 24}},
            },
            content_type="application/json",
        )
        assert r.status_code == 400, r.content[:300]
        assert "contexto_recomendacao" in r.json(), r.json()
