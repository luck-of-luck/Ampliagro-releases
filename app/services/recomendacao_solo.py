from decimal import Decimal


class RecomendacaoSoloService:
    """
    Serviço para recomendação agronômica (Calagem, Gessagem e Adubação Básica).
    """

    @classmethod
    def calcular_necessidade_calagem(
        cls, ctc: float, v_atual: float, v_desejado: float = 70.0, prnt: float = 100.0
    ) -> float:
        """
        Calcula Necessidade de Calagem (NC) em toneladas por hectare (t/ha).
        Fórmula básica: NC = (CTC * (V_desejado - V_atual)) / PRNT
        """
        if not all([ctc, v_atual]) or ctc <= 0:
            return 0.0

        if v_atual >= v_desejado:
            return 0.0

        nc = (ctc * (v_desejado - v_atual)) / prnt
        return round(max(nc, 0.0), 2)

    @classmethod
    def calcular_necessidade_gessagem(
        cls, calcio_ca: float, aluminio_al: float
    ) -> float:
        """
        Gessagem recomendada se Ca baixo ou Al tóxico em profundidade.
        Retorna em t/ha.
        (Fórmula simplificada baseada em saturação por Alumínio)
        """
        if aluminio_al > 0.5 and calcio_ca < 0.5:
            return 1.5  # Recomendação genérica de gesso
        return 0.0

    @classmethod
    def analisar_solo(cls, analise_solo) -> dict:
        """Recebe uma AnaliseSolo e devolve a recomendação.

        ATENÇÃO — este módulo NÃO TEM ROTA. A auditoria de 2026-09-29
        confirmou: `analisar_solo` não é chamada de lado nenhum. É uma
        bomba-relógio, e o que acerta é a conclusão, não a medição.

        Três coisas que fariam este resultado errado e enganador, se
        alguém o ligar:

        1. `estado_ph` era "Bom" por omissão. Sem análise de pH, dizer que
           o solo está bom é inventar o que se deveria estar a medir — e
           é o tipo de coisa que impede o produtor de fazer uma calagem
           de que precisa. Sem pH, não há estado.

        2. `recomendacao_npk` era uma string fixa: 300 kg/ha de 04-14-08,
           com "Placeholder" dentro. Uma recomendação de fertilizante
           escrita à mão e devolvida como recomendação.

        3. Os valores por omissão (`ctc or 0`, `saturacao_bases_v or 0`)
           transformam um campo ausente num zero, e o zero alimenta a
           fórmula de calagem. Falta de dado entra como medida.

        A calagem e a gessagem calculadas a partir de uma análise real
        continuam a ser o que este módulo sabe fazer. O que não sabe é
        dizer que o solo está bom, ou que precisa de 300 kg daquele
        produto.
        """
        tem_ph = analise_solo.ph is not None
        tem_ctc = analise_solo.ctc is not None
        tem_sb = analise_solo.saturacao_bases_v is not None

        ctc = float(analise_solo.ctc) if tem_ctc else None
        v_atual = float(analise_solo.saturacao_bases_v) if tem_sb else None
        ca = (
            float(analise_solo.calcio_ca)
            if analise_solo.calcio_ca is not None
            else None
        )
        al = (
            float(analise_solo.aluminio_al)
            if analise_solo.aluminio_al is not None
            else None
        )

        nc = (
            cls.calcular_necessidade_calagem(ctc, v_atual)
            if tem_ctc and tem_sb
            else None
        )
        ng = (
            cls.calcular_necessidade_gessagem(ca, al)
            if ca is not None and al is not None
            else None
        )

        estado_ph = None
        if tem_ph:
            if analise_solo.ph < 5.5:
                estado_ph = "Ácido (Requer Calagem)"
            elif analise_solo.ph > 7.2:
                estado_ph = "Alcalino"
            else:
                estado_ph = "Bom"

        # O que faltou à análise, nomeado. Um `or 0` esconde a diferença
        # entre "o solo não tem alumínio" e "não medimos o alumínio" — e a
        # segunda é a que impede a calagem de ser recomendada.
        faltando = [
            nome
            for nome, tem in (
                ("pH", tem_ph),
                ("CTC", tem_ctc),
                ("saturação de bases", tem_sb),
                ("Cálcio", ca is not None),
                ("Alumínio", al is not None),
            )
            if not tem
        ]

        resultado = {
            "estado_ph": estado_ph,
            "necessidade_calagem_t_ha": nc,
            "necessidade_gessagem_t_ha": ng,
            "recomendacao_npk": None,
            "faltando_na_analise": faltando,
        }

        if faltando:
            resultado["motivo"] = (
                "Análise de solo incompleta: falta "
                + ", ".join(faltando)
                + ". Sem estes valores não há recomendação. A necessidade de "
                "calagem depende de CTC e saturação de bases; a de gessagem, "
                "de cálcio e alumínio."
            )

        if al is not None:
            resultado["avisos"] = (
                ["Nível de Alumínio tóxico"]
                if al > 0.5
                else ["Alumínio em níveis adequados"]
            )
        return resultado
