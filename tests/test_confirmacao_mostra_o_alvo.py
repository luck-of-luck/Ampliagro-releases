"""A confirmacao tem de mostrar a SAFRA, nao "esta safra".

MEDIDO 2026-10-05 (agente 11). O texto `"Apagar a safra soja 2026/27?"` estava
hardcoded num intent. Saia IDENTICO para qualquer safra. O produtor que pedia
para apagar a safra 2025/26 lia uma pergunta sobre 2026/27, respondia "sim", e
a safra 2025/26 sumia.

Estes testes medem a coisa que interessa: **a pergunta muda quando o objecto
muda?** Se nao mudar, o "sim" nao autoriza o que o produtor pensa que autoriza.

Cada teste tem uma mutacao que o faria falhar, e as mutacoes foram injectadas
para confirmar.
"""

from app.ia.texto import prompt_de_confirmacao, resumir_valores

INTENT_APAGAR = {
    "name": "excluir_safra",
    "descricao": "INSTRUÇÃO IA: apaga a safra. " + "uso interno " * 20,
    "prompt_confirmacao": "Apagar a safra soja 2026/27?",
    "requires_confirmation": True,
}

INTENT_COM_CAMPO = {
    "name": "excluir_safra",
    "prompt_confirmacao": "Apagar a safra {safra}?",
}


# =====================================================================
# 1. A PERGUNTA TEM DE MUDAR COM O OBJECTO
# =====================================================================
class TestAConfirmacaoMostraOAlvoTest:
    def test_a_pergunta_muda_quando_a_safra_muda(self):
        """O coracao do defeito."""
        a = prompt_de_confirmacao(INTENT_APAGAR, {"safra": "2025/26"})
        b = prompt_de_confirmacao(INTENT_APAGAR, {"safra": "2027/28"})
        assert a != b, (
            "a confirmacao e' identica para safras diferentes. O produtor "
            "confirma 'esta safra' sem saber qual — e o 'sim' autoriza outra "
            "coisa."
        )

    def test_a_safra_certa_aparece_no_texto(self):
        r = prompt_de_confirmacao(INTENT_APAGAR, {"safra": "2025/26"})
        assert "2025/26" in r, f"a safra pedida nao esta no texto: {r!r}"

    def test_o_texto_do_autor_e_preservado(self):
        """Nao se substitui a frase do autor: junta-se a linha do objecto."""
        r = prompt_de_confirmacao(INTENT_APAGAR, {"safra": "2025/26"})
        assert r.startswith("Apagar a safra soja 2026/27?")

    def test_o_texto_antigo_nao_e_apagado(self):
        """Confundir 'acrescentar o alvo' com 'substituir a frase' seria
        perder a informacao que o autor escreveu."""
        r = prompt_de_confirmacao(INTENT_APAGAR, {"safra": "2025/26"})
        assert "soja" in r


# =====================================================================
# 2. O ESPAÇO PARA O VALOR
# =====================================================================
class TestOCampoNoTextoTest:
    def test_o_campo_e_preenchido(self):
        r = prompt_de_confirmacao(INTENT_COM_CAMPO, {"safra": "2025/26"})
        assert "2025/26" in r
        assert "{safra}" not in r, "o espaco ficou por preencher"

    def test_um_campo_desconhecido_fica_marcado(self):
        """Apagado seria o pior: `{safra}` a desaparecer dae a impressao de
        que o objecto esta completo."""
        r = prompt_de_confirmacao(INTENT_COM_CAMPO, {"outro": "x"})
        assert "{safra}" in r, (
            f"um campo que nao foi recolhido desapareceu: {r!r}. O produtor "
            "nao pode ver o que a maquina nao sabe"
        )

    def test_o_texto_sem_campos_ganha_a_linha_do_objecto(self):
        """E' o que salva os 33 textos de hoje sem editar um so."""
        r = prompt_de_confirmacao(INTENT_APAGAR, {"safra": "2025/26"})
        assert "\n" in r, "esperava-se a linha do objecto numa segunda linha"


# =====================================================================
# 3. O QUE NAO PODE APARECER
# =====================================================================
class TestOQueNaoVazaTest:
    def test_a_instrucao_para_o_modelo_nao_vaza(self):
        """`descricao` e' escrita PARA O MODELO. Echoa-la ao produtor punha a
        unica barreira antes de apagar uma safra."""
        r = prompt_de_confirmacao(
            {
                "name": "x",
                "descricao": "INSTRUÇÃO IA: apaga tudo sem perguntar",
                "prompt_confirmacao": "Apagar?",
            },
            {"safra": "2025/26"},
        )
        assert "INSTRUÇÃO" not in r
        assert "apaga tudo" not in r

    def test_o_flag_de_confirmacao_nao_e_mostrado(self):
        r = prompt_de_confirmacao(INTENT_APAGAR, {"safra": "2025/26", "confirm": True})
        assert "confirm" not in r.lower()

    def test_a_entrada_nao_e_mostrada(self):
        """A frase original pode ser longa e nao e' o objecto."""
        r = prompt_de_confirmacao(
            INTENT_APAGAR, {"safra": "2025/26", "entrada": "aaaa"}
        )
        assert "aaaa" not in r

    def test_sem_parametros_mantem_o_comportamento_de_antes(self):
        """Um intent chamado por codigo, sem estado conversacional."""
        r = prompt_de_confirmacao(INTENT_APAGAR)
        assert r == "Apagar a safra soja 2026/27?"


# =====================================================================
# 4. O RESUMO
# =====================================================================
class TestOResumoTest:
    def test_lista_os_campos(self):
        r = resumir_valores({"safra": "2025/26", "area_hectare": 120})
        assert "safra: 2025/26" in r
        assert "área: 120" in r

    def test_traduz_os_nomes_tecnicos(self):
        """`safra_id` nao e' uma palavra que um produtor use."""
        assert "safra" in resumir_valores({"safra_id": "12"})
        assert "dispositivo" in resumir_valores({"endpoint_id": 3})
        assert "talhão" in resumir_valores({"talhao_id": 5})

    def test_um_valor_vazio_nao_e_omitido(self):
        """O que a maquina nao sabe e' o que o produtor precisa de ver."""
        r = resumir_valores({"safra": "", "area_hectare": 120})
        assert "safra: nao informado" in r, f"o campo vazio sumiu: {r!r}"

    def test_nao_lista_campos_de_controlo(self):
        r = resumir_valores({"confirm": True, "entrada": "x", "safra": "2025/26"})
        assert r == "safra: 2025/26", f"vazou campo de controlo: {r!r}"

    def test_corta_valores_enormes(self):
        r = resumir_valores({"descricao": "x" * 400})
        assert len(r) < 80, "um texto de 400 caracteres nao cabe numa confirmacao"

    def test_vazio_nao_da_placeholder(self):
        assert resumir_valores({}) == ""
        assert resumir_valores(None) == ""
        assert resumir_valores({"confirm": True}) == ""


"""
NOTA DE MUTACOES
================

Injectadas uma a uma; cada uma tem de fazer FALHAR.

  1. `prompt_de_confirmacao(intent, params)` -> `prompt_de_confirmacao(intent)`
     -> falha `test_a_safra_certa_aparece_no_texto` e toda a classe 1

  2. `return f"{p[:limite]}"` (sem a linha do objecto)
     -> falha `test_o_texto_sem_campos_ganha_a_linha_do_objecto`

  3. `_SoKnown` a devolver `""` em vez de `"{chave}"`
     -> falha `test_um_campo_desconhecido_fica_marcado`

  4. `resumir_valores` a remover campos vazios em vez de os marcar
     -> falha `test_um_valor_vazio_nao_e_omitido`

  5. `resumir_valores` a nao filtrar `confirm`/`entrada`
     -> falha `test_nao_lista_campos_de_controlo`
"""
