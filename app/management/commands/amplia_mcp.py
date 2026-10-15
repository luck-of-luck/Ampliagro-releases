"""
`manage.py amplia_mcp` — o servidor MCP da AmplIA explicado ao operador.

POR QUE ISTO EXISTE
-------------------
O servidor MCP (`app/amplia_mcp/servidor.py`) é a porta para os agentes de
fora. Até aqui, configurar essa porta significava três coisas que ninguém
descobria sozinho: qualInterpreter, que `--usuario` existe no banco, e que
o `DJANGO_SETTINGS_MODULE` certo. Quem erra recebe um `exit 2` com uma linha
em stderr e nenhuma pista sobre o próximo passo.

Este comando transforma "não arranca" em "diz-me o que falta":

    manage.py amplia_mcp doctor        # o que está e o que falta
    manage.py amplia_mcp config        # o JSON pronto a colar no cliente
    manage.py amplia_mcp usuarios      # quem pode ser --usuario
    manage.py amplia_mcp resource URI  # imprime um recurso pela URI

O `doctor` não é um health check genérico do Django. Cada linha responde a
uma falha que já aconteceu de facto, e cada uma diz o comando que a resolve.

O QUE ESTE COMANDO NÃO FAZ
--------------------------
Não arranca o servidor. Um `stdio` MCP é um processo que vive enquanto o
cliente o segura; arrancá-lo a partir de um comando de gestão produziria um
processo que sai logo a seguir e um cliente que recebe EOF sem erro. Este
comando diz o que fazer; o cliente faz.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import connection

#: A raiz do repositório, deduzida do ficheiro — a mesma regra do servidor.
#: (`app/management/commands/amplia_mcp.py` -> ../../../ = raiz)
RAIZ_REPO = Path(__file__).resolve().parents[3]


def _interpreter() -> str:
    """O Python que tem o Django. Um cliente MCP tem de usar ESTE, não o `python`."""
    return sys.executable


def _script_servidor() -> str:
    return str(RAIZ_REPO / "app" / "amplia_mcp" / "servidor.py")


class Command(BaseCommand):
    help = "Diagnóstico e configuração do servidor MCP (stdio) da AmplIA."

    def add_arguments(self, parser):
        sub = parser.add_subparsers(dest="sub", required=True)

        sub.add_parser(
            "doctor", help="o que está instalado, o que falta e como resolver"
        )
        sub.add_parser("config", help="JSON pronto a colar no cliente MCP")
        sub.add_parser("usuarios", help=" usernames que podem ser --usuario")

        p_res = sub.add_parser("resource", help="imprime um recurso pela URI")
        p_res.add_argument("uri", help="ex.: amplia://capacidades")

    # ------------------------------------------------------------------
    def handle(self, *args, **opts):
        sub = opts["sub"]
        if sub == "doctor":
            return self._doctor()
        if sub == "config":
            return self._config()
        if sub == "usuarios":
            return self._usuarios()
        if sub == "resource":
            return self._resource(opts["uri"])
        raise CommandError(f"subcomando desconhecido: {sub}")

    # ------------------------------------------------------------------
    # doctor
    # ------------------------------------------------------------------
    def _doctor(self) -> None:
        from app.ia.sandbox import INTENTS, somente_leitura

        REGISTO = INTENTS
        falhas: list[str] = []
        avisos: list[str] = []
        p = lambda ok, txt: self.stdout.write(  # noqa: E731
            f"  {'[ok] ' if ok else '[!!] '} {txt}"
        )

        self.stdout.write(self.style.MIGRATE_HEADING("AmplIA — servidor MCP"))
        self.stdout.write("")

        # 1. Python e Django -------------------------------------------------
        self.stdout.write(self.style.MIGRATE_HEADING("1. Interpretador"))
        p(True, f"Python: {_interpreter()}")
        try:
            import django

            p(True, f"Django: {django.get_version()}")
        except ImportError as e:
            p(False, f"Django nao encontrado ({e})")
            falhas.append("Django ausente neste interprete")

        # 2. O SDK ------------------------------------------------------------
        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("2. SDK 'mcp' (so para stdio)"))
        try:
            import mcp  # noqa: F401

            p(True, f"SDK 'mcp' instalado ({getattr(mcp, '__file__', '?')})")
        except ImportError:
            p(False, "SDK 'mcp' NAO instalado — o servidor stdio nao arranca")
            self.stdout.write(
                "       resolver: "
                f"{_interpreter()} -m pip install -r requirements-mcp.txt"
            )
            falhas.append("SDK 'mcp' ausente (opcional; HTTP funciona sem ele)")

        # 3. Caminhos ---------------------------------------------------------
        # A falha que custou mais tempo a arranjar: o `.env` tem
        # `DATABASE_URL=sqlite:///db.sqlite3`, relativo, e o Django resolve
        # `NAME` contra o CWD do processo. `manage.py` nunca notou porque
        # corre da raiz; um cliente MCP é lançado do directório do utilizador.
        # Verificado, não especulado: antes da correcção, correr o servidor de
        # outro directório criava um banco NOVO e VAZIO nesse directório
        # (4096 bytes — SQLite sem uma tabela) e respondia
        # `no such table: auth_user`.
        #
        # O que interessa verificar NÃO é se o caminho é absoluto — a equipa
        # resolveu isto com `os.chdir(RAIZ_REPO)` no arranque do servidor, e
        # um caminho relativo deixa de ser um problema quando ninguém depende
        # do CWD. O que interessa é a RESOLUÇÃO: onde é que este banco
        # está, afinal? É essa a pergunta que um operador faz, e a resposta
        # errada é a que abre a base vazia.
        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("3. Caminhos"))
        cfg = connection.settings_dict
        nome = str(cfg.get("NAME") or "")
        em_memoria = nome.startswith(":") or nome.startswith("file:")
        resolvido = (
            Path.cwd() / nome
            if nome and not em_memoria and not Path(nome).is_absolute()
            else None
        )
        if em_memoria:
            p(True, f"Banco: {nome} (em memoria)")
        else:
            alvo = Path(nome) if Path(nome).is_absolute() else resolvido
            existe = bool(alvo and alvo.is_file())
            p(existe, f"Banco: {alvo}")
            if not existe:
                falhas.append(f"o banco nao existe no caminho resolvido: {alvo}")
            elif alvo.stat().st_size == 0:
                p(False, "o banco esta VAZIO (0 bytes) — e' o caminho antigo")
                falhas.append(
                    f"banco vazio em {alvo}: o .env aponta para um caminho "
                    "que nao e' a base viva"
                )
        srv = Path(_script_servidor())
        p(srv.is_file(), f"Servidor: {srv}")
        p(
            (RAIZ_REPO / "config" / "settings").is_dir(),
            f"Raiz do repo (deduzida pelo servidor): {RAIZ_REPO}",
        )

        # 4. Banco e utilizadores --------------------------------------------
        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("4. Banco e utilizadores"))
        try:
            with connection.cursor() as c:
                c.execute("select count(*) from auth_user")
                n_users = c.fetchone()[0]
            p(True, f"Banco liga. {n_users} utilizador(es)")
            if n_users == 0:
                avisos.append(
                    "zero utilizadores: nenhum --usuario pode funcionar. "
                    "Crie com `manage.py cria_conta_demo` ou `createsuperuser`."
                )
        except Exception as e:  # noqa: BLE001 — o diagnostico E' a excepcao
            p(False, f"Banco NAO liga: {e}")
            falhas.append(f"banco inacessivel: {e}")

        # 5. O catalogo que a IA vai receber ----------------------------------
        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("5. Catalogo publicado"))
        from app.amplia_mcp import TOOLS_CATALOGO, catalogo_tools

        tools = catalogo_tools()
        leitura = [t for t in tools if t.get("x-read-only")]
        escrita = [t for t in tools if not t.get("x-read-only")]
        p(
            bool(REGISTO) and len(tools) == len(REGISTO),
            f"intents no registo: {len(REGISTO)}  |  tools publicadas: {len(tools)}",
        )
        if len(tools) != len(REGISTO):
            falhas.append(
                "o catalogo publica um numero diferente do registo — "
                "uma intent existe mas nao chega a IA"
            )
        p(True, f"  leitura: {len(leitura)}   escrita: {len(escrita)}")
        p(bool(TOOLS_CATALOGO), f"tools de catalogo: {len(TOOLS_CATALOGO)}")

        # 6. Como ligar -------------------------------------------------------
        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("6. Como ligar um cliente"))
        self.stdout.write(
            f"  comando: {_interpreter()} {_script_servidor()} --usuario <NOME>"
        )
        self.stdout.write("  leitura por omissao; --permitir-escrita abre as escritas")
        self.stdout.write(
            "  `manage.py amplia_mcp config` imprime o JSON pronto a colar"
        )

        # Veredito -------------------------------------------------------------
        self.stdout.write("")
        if falhas:
            self.stdout.write(self.style.ERROR(f"FALHA ({len(falhas)}):"))
            for f in falhas:
                self.stdout.write(f"  - {f}")
            raise CommandError("o servidor MCP nao esta pronto")
        for a in avisos:
            self.stdout.write(self.style.WARNING(f"AVISO: {a}"))
        if not avisos:
            self.stdout.write(self.style.SUCCESS("OK — pronto para ligar um cliente."))

    # ------------------------------------------------------------------
    # config
    # ------------------------------------------------------------------
    def _config(self) -> None:
        """O JSON que o cliente MCP consome. Pronto a colar, sem editar."""
        usuario = os.environ.get("AMPLIA_MCP_USUARIO") or self._primeiro_usuario()
        if not usuario:
            raise CommandError(
                "nao ha utilizadores no banco. Crie um e volte: "
                "`manage.py cria_conta_demo` (ou `createsuperuser`)"
            )

        interpreter = _interpreter()
        cmd = [interpreter, _script_servidor(), "--usuario", usuario]
        env = {}
        if os.environ.get("AMPLIA_PROD"):
            env["AMPLIA_PROD"] = "1"

        bloco = {
            "mcp": {
                "amplia": {
                    "type": "local",
                    "command": [cmd[0]],
                    "args": cmd[1:],
                    "enabled": True,
                    **({"environment": env} if env else {}),
                }
            }
        }

        self.stdout.write(
            "Abra o ficheiro de configuracao do seu cliente MCP e cole isto.\n"
            "O caminho e' ABSOLUTO de proposito: um cliente MCP nao tem directório\n"
            "de trabalho do projecto, e e' por isso que o servidor o descobre sozinho.\n"
        )
        self.stdout.write(json.dumps(bloco, indent=2, ensure_ascii=False))

        self.stdout.write("")
        self.stdout.write(
            "Para LIGAR AS ESCRITAS (irrigacao, lancamentos, registos), junte\n"
            '"--permitir-escrita" aos args. Por omissao o servidor e\' so leitura,\n'
            "e diz quantas tools de escrita ficam bloqueadas ao arrancar."
        )
        self.stdout.write("")
        origem = (
            "AMPLIA_MCP_USUARIO do ambiente"
            if os.environ.get("AMPLIA_MCP_USUARIO")
            else "o primeiro utilizador activo do banco"
        )
        self.stdout.write(f"Utilizador escolhido: {usuario}  ({origem})")
        self.stdout.write(
            "Para escolher outro: $env:AMPLIA_MCP_USUARIO='<nome>'; "
            "ou veja todos com `manage.py amplia_mcp usuarios`."
        )

    # ------------------------------------------------------------------
    def _primeiro_usuario(self) -> str:
        try:
            return (
                User.objects.filter(is_active=True)
                .order_by("id")
                .values_list("username", flat=True)
                .first()
                or ""
            )
        except Exception:  # noqa: BLE001
            return ""

    def _usuarios(self) -> None:
        try:
            nomes = list(
                User.objects.filter(is_active=True)
                .order_by("id")
                .values_list("username", flat=True)
            )
        except Exception as e:  # noqa: BLE001
            raise CommandError(f"banco inacessivel: {e}") from e
        if not nomes:
            self.stdout.write(self.style.WARNING("nenhum utilizador activo"))
            return
        self.stdout.write("Pode usar qualquer um destes como --usuario:")
        for n in nomes:
            self.stdout.write(f"  {n}")

    # ------------------------------------------------------------------
    def _resource(self, uri: str) -> None:
        """Lê um recurso pela mesma porta do servidor MCP.

        Serve para confirmar que um `resources/read` responde, sem ter de
        montar um cliente. E — porque `read_resource` deixou de devolver o
        contexto para URI desconhecidas — também mostra que uma URI errada
        ERRA em vez de devolver outra coisa.
        """
        from app.amplia_mcp import contexto
        from app.amplia_mcp.capacidades import catalogo_de_capacidades
        from app.amplia_mcp.skills import catalogo_skis
        from app.ia.paginas import MODELOS, referencia_widgets, summarise_catalogo

        usuario = os.environ.get("AMPLIA_MCP_USUARIO") or self._primeiro_usuario()
        if not usuario:
            raise CommandError(
                "nenhum utilizador para contexto. Use --usuario via env AMPLIA_MCP_USUARIO"
            )

        user = User.objects.filter(username=usuario).first()
        if user is None:
            raise CommandError(f"utilizador {usuario!r} nao existe")

        u = uri.strip()
        if u == "amplia://modelos":
            out: Any = {
                "modelos": [
                    {k: m[k] for k in ("titulo", "para_quem", "widgets", "depende")}
                    for m in MODELOS.values()
                ],
                "resumo": summarise_catalogo(),
            }
        elif u == "amplia://widgets":
            out = referencia_widgets()
        elif u == "amplia://skills":
            out = catalogo_skis()
        elif u == "amplia://capacidades":
            out = catalogo_de_capacidades()
        elif u.startswith("amplia://contexto"):
            out = contexto(user)
        else:
            raise CommandError(
                f"recurso MCP desconhecido: {u!r}. Disponiveis: "
                "amplia://contexto/<usuario>, amplia://modelos, amplia://widgets, "
                "amplia://skills, amplia://capacidades"
            )

        self.stdout.write(json.dumps(out, ensure_ascii=False, indent=2, default=str))
