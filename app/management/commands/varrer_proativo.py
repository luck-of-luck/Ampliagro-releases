"""Roda a varredura proativa do AmplIA.

    python manage.py varrer_proativo

POR QUE ESTE COMANDO EXISTE
===========================
A varredura ja nasceu como `app.ia.proativo_tasks.varrer()` — uma funcao
comum, sem broker. O envelope Celery (`varrer_task`) e' so um embrulho por
cima. Este comando e' o outro embrulho: o mesmo nucleo, sem Celery.

A ESCOLHA, E POR QUE
====================
Para rodar uma varredura 2x ao dia, um broker e' infraestrutura a mais. Redis
nao tem build oficial no Windows; WSL e' um sistema operacional inteiro;
Docker e' um daemon para um job que leva alguns segundos. E o preco nao e' a
instalacao — e' o SUPORTE: cada "o alerta nao veio" vira "o Redis caiu", e o
tecnico que resolve isso nao e' o produtor, nao e' a IA, e' o cara do
computador da fazenda. A adocao morre ali, nao no codigo.

O Agendador de Tarefas do Windows e' o que ja estava na maquina, e' nativo,
sobrevive a reinicio, nao tem daemon para dar crash, e mostra o ultimo
resultado em `schtasks /query`. Para um job diario, ele e' a resposta certa —
e a resposta que continua certa quando o job passa a rodar 12x ao dia, e
continua errada se um dia a fila de cenarios precisar de concorrencia real. A
hora de trocar por broker e' quando o volume justificar, e nao antes.

UM ARGUMENTO QUE PARECE DETALHE E E' O MOTIVO DESTE COMANDO NAO CRASHAR
======================================================================
`DATABASE_URL=sqlite:///db.sqlite3` e' RELATIVO. Rodar `manage.py` de outra
pasta aponta para outro banco — ou para nenhum, com "no such table". Um
agendador roda com um diretorio de trabalho que ninguem escolhe, e o sintoma
de errar isso e' um job que falha as 7h12 e 17h12, todo dia, para sempre, sem
nenhum erro visivel. Por isso o comando sobe ate a raiz do projeto sozinho e
avisa se o banco encontrado nao for o esperado.

O QUE ESTE COMANDO NAO FAZ
==========================
Nao agenda nada. Agendar e' `tools/bat/setup_tarefa_proativa.bat`, separado de
propósito: quem instala o agendamento e' o operador, uma vez, na maquina dele.
Um comando de management que cria tarefa do sistema seria um comando que muda
a maquina de quem apenas pediu um relatorio.
"""

import os
import sys
from pathlib import Path

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Roda uma varredura do motor proativo (o mesmo nucleo do Celery, sem broker)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--teto-usuarios",
            type=int,
            default=None,
            help="Maximo de produtores nesta passada (protege o banco em horario de pico)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="So relata o que faria; nao grava alerta nem enfileira cenario",
        )
        parser.add_argument(
            "--json",
            action="store_true",
            help="Imprime o resumo como JSON (para o agendador ou um log)",
        )

    def handle(self, *args, **options):
        self._garantir_raiz()
        self._conferir_banco()

        from app.ia import proativo_tasks

        if options["dry_run"]:
            # Um "--dry-run" que grava e' pior do que nao ter dry-run: quem
            # confia nele perde o mesmo alerta duas vezes, e a segunda perde por
            # dedup — e o produtor nunca recebe nenhum dos dois.
            self.stdout.write(
                self.style.WARNING(
                    "--dry-run: nenhuma varredura sera feita. "
                    "Use este comando sem a flag para realmente varrer."
                )
            )
            self._mostrar_ambiente(proativo_tasks)
            return

        resumo = proativo_tasks.varrer(teto_usuarios=options["teto_usuarios"])

        if options["json"]:
            import json as _json

            self.stdout.write(_json.dumps(resumo, ensure_ascii=False, default=str))
        else:
            self._relatorio(resumo, proativo_tasks)

        # Codigo de saida NAO zero quando alguem falhou. E' isto que o Windows
        # grava em "Ultimo resultado" no Agendador de Tarefas, e e' a unica coisa
        # que o operador vai olhar se o alerta nao chegou. Devolver 0 com falha
        # dentro transforma uma pane de rede numa pane invisivel — e o produtor
        # perde o aviso sem ninguem descobrir por que.
        if resumo.get("usuarios_com_erro", 0):
            sys.exit(1)

    # -- a raiz do projeto, porque o banco e' relativo -----------------------

    def _garantir_raiz(self) -> Path:
        r"""Sobe ate a raiz antes de o Django tocar no banco.

        `settings.base` le `DATABASE_URL` do `.env`, e ele aponta `db.sqlite3`
        por caminho RELATIVO. Num Agendador de Tarefas o diretorio de trabalho e'
        C:\Windows\System32, e o job falha com "no such table" — todas as
        manhas, sem ninguem ver.
        """
        raiz = Path(__file__).resolve().parents[3]
        if Path.cwd().resolve() != raiz:
            os.chdir(raiz)
        return raiz

    def _conferir_banco(self) -> None:
        """Falha alto e cedo se o banco que o Django vai abrir nao existe.

        Sem esta checagem, o erro do caminho relativo chega como `no such table:
        app_proativopreferencia` — no meio da varredura, embrulhado num traceback
        que nao diz nada sobre a causa real. O `chdir` acima ja' resolve o caso
        comum; isto cobre o caso que sobra: o `.env` aponta para um banco que nao
        esta' la, e' a copia de outro projeto, ou o arquivo foi movido. Nesses
        casos, dizer "o banco nao esta' em <caminho>" vale mais que um traceback.
        """
        from django.conf import settings
        from django.core.management.base import CommandError

        nome = settings.DATABASES.get("default", {}).get("NAME")
        if not nome:
            return
        # Nao todo NAME e' um caminho em disco. O SQLite aceita URI
        # (`file:memdb1?mode=memory&cache=shared`) e `:memory:`, e e' assim que
        # o banco de teste do Django se apresenta — e como qualquer instalacao
        # em memoria se apresenta. Abrir "file:memdb1?mode=memory" como arquivo
        # daria sempre "banco nao encontrado", num banco que existe e funciona.
        nome_str = str(nome)
        if nome_str == ":memory:" or "file:" in nome_str or "://" in nome_str:
            return
        alvo = Path(nome_str)
        if not alvo.is_absolute():
            alvo = Path.cwd() / alvo
        if not alvo.exists():
            raise CommandError(
                f"banco nao encontrado em {alvo}\n"
                f"  o projeto esta' em {Path.cwd()}\n"
                "  se o caminho no .env (DATABASE_URL) aponta para outro lugar, "
                "a varredura rodaria contra o banco errado — por isso ela para aqui."
            )

    def _ambiente(self, tasks) -> dict:
        return {
            "raiz": str(Path.cwd()),
            "celery": bool(getattr(tasks, "CELERY_DISPONIVEL", False)),
        }

    def _mostrar_ambiente(self, tasks) -> None:
        a = self._ambiente(tasks)
        self.stdout.write(f"  raiz:    {a['raiz']}")
        self.stdout.write(
            f"  celery:  {'instalado' if a['celery'] else 'ausente (e irrelevante aqui)'}"
        )

    def _relatorio(self, resumo: dict, tasks) -> None:
        """O relatorio tem que responder: o produtor foi avisado, ou nao?

        Uma saida que so diz "ok" deixa o operador sem como distinguir "rodei e
        nao havia nada" de "rodei e quebrei antes de comecar" — e sao exatamente
        esses dois casos que ele precisa diferenciar as 7h12.
        """
        a = self._ambiente(tasks)

        self.stdout.write("")
        self.stdout.write("== varredura proativa ==")
        self.stdout.write(f"  raiz:        {a['raiz']}")
        self.stdout.write(
            f"  celular:     {resumo.get('usuarios_avaliados', 0)} produtor(es) avaliado(s)"
        )
        if resumo.get("usuarios_pulado"):
            self.stdout.write(
                self.style.WARNING(f"  pulados:     {resumo['usuarios_pulado']} (teto)")
            )
        self.stdout.write(f"  alertas:     {resumo.get('alertas', 0)} emitido(s)")
        self.stdout.write(
            f"  suprimidos:  {resumo.get('suprimidos', 0)} (dedup / teto)"
        )
        self.stdout.write(f"  cenarios:    {resumo.get('cenarios', 0)} enfileirado(s)")
        self.stdout.write(
            f"  expirados:   {resumo.get('cenarios_purgados', 0)} cenario(s) vencido(s) limpo(s)"
        )
        self.stdout.write(
            f"  comandos:    {resumo.get('comandos_expirados', 0)} comando(s) IoT "
            "sem ACK expirado(s)"
        )
        if resumo.get("comandos_com_erro"):
            # Sem esta linha, um "0 comando(s)" aqui seria mentira: o numero
            # seria o de uma expiratacao que NAO correu. A fila continuaria a
            # encher e o operador leria "fila limpa".
            self.stdout.write(
                self.style.ERROR(
                    "  FALHAS:     nao deu para expirar comandos IoT. O 0 acima "
                    "NAO significa 'nada vencido' — significa 'nao perguntou'."
                )
            )

        if resumo.get("parou_por_teto"):
            self.stdout.write(
                self.style.WARNING(
                    f"  PARADA: {resumo.get('motivo_parada')} — "
                    "a varredura nao cobriu todo mundo. Aumente --teto-usuarios "
                    "ou a frequencia no agendador."
                )
            )

        # A distinguish "pulei por teto" de "tentei e deu errado" e' o que separa
        # um alerta de um operators comforting. Sem isto, uma API de tempo fora
        # do ar aparece como "pulados: 5 (teto)" — e quem le sobe para mexer no
        # teto, que nao era o problema, enquanto o produtor nao recebe nada.
        erros = resumo.get("usuarios_com_erro", 0)
        if erros:
            self.stdout.write(
                self.style.ERROR(
                    f"  FALHAS:     {erros} produtor(es) nao puderam ser avaliados. "
                    "O motor seguiu para os demais, mas estes NAO receberam alerta."
                )
            )

        novos = resumo.get("alertas", 0)
        if novos:
            self.stdout.write(self.style.SUCCESS(f"  {novos} alerta(s) entregue(s)."))
        elif erros:
            # O conforto falso e' o pior resultado possivel aqui. "A regra olhou
            # e nao achou risco" seria mentira: a regra NAO olhou — falhou antes.
            # O produtor que nao foi avaliado acredita que ninguem viu risco na
            # chuva que viria, e sai para o campo.
            self.stdout.write(
                self.style.ERROR(
                    "  IMPOSSIVEL AFIRMAR QUE NAO HA RISCO: "
                    "parte dos produtores nao foi avaliada."
                )
            )
        else:
            # "Nenhum alerta" e' uma NOTA BOA — a regra olhou e nao achou risco.
            # Dizer isso evita que o operador recompute se o job rodou, e evita
            # que ele suba, meia-noite, para "conferir se a IA esta viva".
            self.stdout.write(
                "  nenhum alerta novo: a regra olhou e nao achou risco hoje."
            )
        self.stdout.write("")
