"""Um comando de gestao vive num sitio so.

O DEFEITO
=========
`app/iot/management/commands/` continha copias byte-a-byte de dois comandos que
ja existiam em `app/management/commands/`:

    mqtt_listener.py   MD5 D3D64380A2909DC3BE9CE7AC38499100  (nos dois sitios)
    sync_inmet.py      MD5 AF5CBF4BD11FB74C8EFB1924A7CCCDDC  (nos dois sitios)

Nao eram duas versoes a reconciliar: eram o MESMO ficheiro duas vezes.

POR QUE A DUPLICACAO NAO FAZIA NADA — E MESMO ASSIM ERA PERIGO
==============================================================
`app.iot` **nao esta em INSTALLED_APPS**. O unico app do projecto e
`app.apps.AmpliagroConfig`. O Django so procura comandos em
`<app instalado>/management/commands/`, portanto a copia em `app/iot/` nunca
foi carregada. Confirmado em qualquer settings deste repositorio:

    >>> get_commands()['sync_inmet']
    'app'
    >>> get_commands()['mqtt_listener']
    'app'

Ou seja: apagar those ficheiros nao muda o que `manage.py sync_inmet` faz.
Mudar um e nao mudar o outro, esse era o problema. A proxima pessoa a precisar
de mexer no `sync_inmet` podia abri-lo em `app/iot/management/`, editar a copia
morta, e ver o comando nao mudar de comportamento nenhum — e, se a copia
morta estivesse um pouco atrasada, achava que a correcao falhou.

E ha um agravante silencioso: se `app.iot` chegasse a ser registado como app
(uma mudanca banal), as DUAS copias passariam a existir e o Django resolveria
o nome para um dos dois sem avisar. O `sync_inmet` e chamado por
`seed_telemetry.py` e `seed_mvp_demo.py`; um `call_command("sync_inmet")`
passaria a executar um ficheiro diferente conforme a ordem de INSTALLED_APPS.

O QUE ESTE TESTE FAZ
====================
Falha se o mesmo nome de comando existir em duas arvores `management/`.
Este e' um teste de ARQUITETURA, nao de comportamento: nao verifica o que o
comando faz (isso e' trabalho dos testes do proprio comando), verifica que
ha um sitio, e so um, de onde ele possa ser carregado.
"""

from __future__ import annotations

import pathlib

RAIZ = pathlib.Path(__file__).resolve().parents[1]
APP = RAIZ / "app"

#: Prefixos de directorias que contêm `management/commands/` dentro de `app/`.
#: Inclui `app/` (raiz) e qualquer sub-app como `app/iot/`.
_RAIZES_COMMANDS = [APP] + [p for p in APP.iterdir() if p.is_dir()]


def _comandos_por_raiz() -> dict[str, list[pathlib.Path]]:
    """Nome do comando -> todos os ficheiros que o definem, em qualquer raiz."""
    achados: dict[str, list[pathlib.Path]] = {}
    for raiz in _RAIZES_COMMANDS:
        pasta = raiz / "management" / "commands"
        if not pasta.is_dir():
            continue
        for ficheiro in sorted(pasta.glob("*.py")):
            if ficheiro.name == "__init__.py":
                continue
            achados.setdefault(ficheiro.stem, []).append(ficheiro)
    return achados


def test_nenhum_comando_esta_definido_em_dois_sitios():
    """Um nome de comando, um ficheiro.

    Cobre `mqtt_listener` e `sync_inmet`, que viviam duplicados em
    `app/iot/management/commands/` sem que `app.iot` estivesse em
    INSTALLED_APPS — logo, sem nenhuma utilidade.
    """
    duplicados = {
        nome: ficheiros
        for nome, ficheiros in _comandos_por_raiz().items()
        if len(ficheiros) > 1
    }

    assert not duplicados, (
        "comandos de gestao definidos em mais do que um sitio:\n"
        + "\n".join(
            f"  {nome}: {', '.join(str(f.relative_to(RAIZ)) for f in ficheiros)}"
            for nome, ficheiros in sorted(duplicados.items())
        )
        + "\n\nUm comando precisa de um unico ficheiro. Com `app.iot` fora de"
        " INSTALLED_APPS, a copia em app/iot/ nunca e' carregada — editar e'"
        " editar uma copia que nao roda. Apague a que estiver morta."
    )


def test_as_raizes_de_comandos_pertencem_a_apps_instalados():
    """O caminho inverso do mesmo defeito.

    Um `management/commands/` dentro de um pacote que NAO esta em
    INSTALLED_APPS e' um ficheiro que ninguem consegue executar. Este teste
    transformaria esse esquecimento num erro visivel em vez de uma surpresa em
    producao.
    """
    from django.apps import apps as django_apps

    instalados = {app_config.name for app_config in django_apps.get_app_configs()}

    orphans = []
    for raiz in _RAIZES_COMMANDS:
        if not (raiz / "management" / "commands").is_dir():
            continue
        if raiz == APP:
            # A raiz `app/` e' o app instalado; a unica excepcao de que
            # precisariamos seria se `app` deixasse de estar em INSTALLED_APPS,
            # e isso o `manage.py check` apanha com outra mensagem.
            continue
        nome = "app" if raiz == APP else _nome_do_pacote(raiz)
        if nome not in instalados:
            orphans.append(nome)

    assert not orphans, (
        "estas arvores management/commands/ nao pertencem a nenhum app "
        f"instalado: {', '.join(sorted(orphans))}. "
        "O Django nao as procura — os comandos la dentro nunca correm. "
        "Ou o pacote entra em INSTALLED_APPS, ou a pasta nao pertence a la."
    )


def _nome_do_pacote(pasta: pathlib.Path) -> str:
    """`app/iot` -> `app.iot`, andando no `__init__.py` mais proximo."""
    for candidato in [pasta, *pasta.parents]:
        if candidato == RAIZ:
            break
        if (candidato / "__init__.py").exists():
            return ".".join(candidato.relative_to(RAIZ).parts)
    return ".".join(pasta.relative_to(RAIZ).parts)
