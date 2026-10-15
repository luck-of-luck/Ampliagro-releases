"""Fonte única da verdade sobre presets de widget do dashboard.

Presets "fantasma" são presets que existiram em versões antigas do painel e
continuam gravados no estado do usuário (DashboardUserState) e no localStorage.
Eles reaparecem no menu mesmo depois de o usuário tê-los excluído, porque o
frontend bloqueia a leitura mas o servidor continuava reenviando-os.

A blocklist abaixo é lida tanto pelo backend (ao salvar/limpar o estado) quanto
pelo template (ao montar PRESETS/getPresetOrder). Alterar um nome aqui muda os
dois lados de uma vez — não duplique a lista no JS.
"""

PRESET_BLOCK = frozenset(
    {
        # visões antigas (pré-2025)
        "visao-geral",
        "visao-base",
        "visao-executivo",
        "visao-campo",
        "visao-financeira",
        "wexecutivo",
        "executivo",
        "financeiro",
        "base",
        "Agua",
        # presets de demonstracao que uma conta nova recebia (medido
        # 2026-10-14). `custom-agua` era preset hard-coded do frontend:
        # nascia em TODA a conta, com series de arroz e milho que ninguem
        # registou. `custom-tempo` e `custom-logistica` chegaram por fuga de
        # `localStorage` entre contas no mesmo browser (palco-amplia.js
        # escrevia a chave sem escopo de utilizador). Os tres ficaram
        # gravados no DashboardUserState de contas que nunca os pediram.
        "custom-agua",
        "custom-tempo",
        "custom-logistica",
        # presets custom-* de demonstração/teste que ficaram na base
        "custom-plantio",
        "custom-caixa",
        "custom-hjh",
        "custom-lua",
        "custom-vegetal-real",
        "custom-animal-real",
        "custom-aquatico-real",
        "custom-aaa",
        "custom-bbb",
        "custom-arroz",
        "custom-oi",
        "custom--gua",
        "custom-sol",
        "custom-internet",
        "custom-frio",
        "custom-muitacaxa",
        "custom-def",
        "custom-testenovo",
    }
)

PREFIXO_PERMITIDO = "custom-"

#: Chave do preset-base de entrada. E' o preset que um produtor novo recebe ao
#: criar a conta: leva o SVG com as letras "IA" e traz contexto, orientacao e
#: o chat da IA pronto. Nao passa pelo `custom-` de proposito — e' a lista de
#: sistema abaixo que o garante contra a limpeza de fantasmas.
PRESET_BASE_IA = "base-ia"

#: Presets de SISTEMA: pertencem ao produto, não ao produtor, e por isso não
#: passam pelo `custom-`.
#:
#: O palco "Amplia" é o primeiro. Sem esta lista ele nunca apareceria no menu:
#: `preset_permitido('amplia')` devolvia False, e a validação que existe para
#: apanhar presets fantasma estava a apagar o preset principal da BUILD 5.
#:
#: O "chamado-amplia" é o segundo, e é o preset onde a IA pode escrever. A
#: mesma razão o traz para aqui: um preset de sistema que não esteja nesta lista
#: é apagado pela limpeza de presets fantasma no momento em que o produtor grava
#: o estado — e a peça que a IA acabou de escrever desaparece. É a mesma classe
#: de falha que `amplia_palco.py` descreve: "a mesa é criada e nunca mais
#: aparece no menu — um botão que parece funcionar e não faz nada".
#:
#: `base-ia` é o terceiro, e é o que o produtor comum vê primeiro. Sem ele a
#: conta nova acordava em `custom-agua`: um preset de DEMONSTACAO, com dois
#: widgets genericos, e com `active_preset` a None — ou seja, um painel vazio
#: na primeira vez que alguém entra. Este é o preset-base.
#:
#: A distinção é deliberada: um preset de sistema é criado pelo produto e não
#: pode ser apagado pelo produtor; um `custom-*` é dele. Um `custom-` que se
#: chame "amplia" não ganha nada com isto — a blocklist continua a mandar.
PRESETS_SISTEMA = frozenset({"amplia", "chamado-amplia", PRESET_BASE_IA})


def preset_imutavel(nome: str) -> bool:
    """True se o produtor não pode apagar nem alterar este preset.

    Só `base-ia` é verdadeiramente imutável. `amplia` e `chamado-amplia` entram
    em `PRESETS_SISTEMA` para não serem apagados pela limpeza de fantasmas, mas
    são palcos de trabalho — tratá-los como intocáveis deixaria o produtor sem
    forma de os ajustar. Daí a lista ser separada: `PRESETS_SISTEMA` protege da
    limpeza automática, `preset_imutavel` protege da mão do produtor.
    """
    return nome == PRESET_BASE_IA


def preset_permitido(nome: str) -> bool:
    """True se o preset pode existir no dashboard.

    Duas portas: um preset de sistema, pela lista acima; ou um preset do
    produtor, pelo prefixo `custom-` e fora da blocklist.
    """
    if not nome:
        return False
    if nome in PRESETS_SISTEMA:
        return True
    return nome.startswith(PREFIXO_PERMITIDO) and nome not in PRESET_BLOCK


def limpar_presets_bloqueados(state: dict) -> tuple[dict, list[str]]:
    """Remove do estado do dashboard todo preset bloqueado.

    Devolve (estado, removidos). Presets do usuário (custom-* válidos) e o
    layout/active_preset são preservados; active_preset só é trocado se apontar
    para um preset bloqueado, caindo para o primeiro permitido disponível.
    """
    if not isinstance(state, dict):
        return state, []

    removidos: list[str] = []

    presets = state.get("presets")
    if isinstance(presets, dict):
        for nome in list(presets):
            if not preset_permitido(nome):
                presets.pop(nome, None)
                removidos.append(nome)
        meta = state.get("presets_meta")
        if isinstance(meta, dict):
            for nome in list(meta):
                if not preset_permitido(nome):
                    meta.pop(nome, None)

    ordem = state.get("presets_order")
    if isinstance(ordem, list):
        filtrada = [k for k in ordem if preset_permitido(k)]
        if len(filtrada) != len(ordem):
            removidos.extend(k for k in ordem if k not in filtrada)
        state["presets_order"] = filtrada

    ativo = state.get("active_preset")
    if ativo and not preset_permitido(ativo):
        candidatos = state.get("presets_order") or []
        valido = next((k for k in candidatos if preset_permitido(k)), None)
        if valido is None and isinstance(presets, dict):
            valido = next((k for k in presets if preset_permitido(k)), None)
        state["active_preset"] = valido
        removidos.append(ativo)

    return state, sorted(set(removidos))
