"""Publica comandos de IoT autorizados no broker.

    python manage.py publicar_comandos                 # dry-run: só relata
    python manage.py publicar_comandos --executar      # publica mesmo
    python manage.py publicar_comandos --executar --limite 200

O DRY-RUN É O OMISSÍVEL
=======================
Um publisher com a publication como omissível é um publisher que alguém vai
accidentalmente rodar contra a água de uma propriedade. `--executar` tem de
ser escrito à mão, e o relatório em modo de relato diz exactamente o que
SARIA publicado — que é a única forma de o operador ver o que o motor
pretende antes de o deixar mexer em alguma coisa.

A autorização é feita em `app/iot/publicar.py`, e é feita na publicação, não
na semeada: a regra pode ter sido desligada, ou a leitura normalizado, desde
que o comando foi enfileirado.
"""

from __future__ import annotations

import json

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        "Publica comandos de IoT pendentes no broker, revalidando a regra de "
        "cada um. Sem --executar, só relata."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--executar",
            action="store_true",
            help="Publica mesmo. Sem esta flag, nada sai do servidor.",
        )
        parser.add_argument(
            "--limite",
            type=int,
            default=None,
            help="Máximo de comandos por passagem.",
        )
        parser.add_argument(
            "--json",
            action="store_true",
            help="Imprime o relatório como JSON.",
        )

    def handle(self, *args, **options):
        from app.iot import publicar as pub

        limite = options["limite"] or pub.LIMITE_PADRAO
        executar = options["executar"]

        if not executar:
            # O dry-run TEM de dizer o que faria. Um dry-run mudo obriga o
            # operador a uma segunda invocação para saber o que está na fila,
            # e essa segunda é a que costuma ser corrida apressada.
            fila = pub.pendentes(limite)
            podiam, recusados = [], []
            for cmd in fila:
                try:
                    pub.autorizar(cmd)
                except pub.Recusado as r:
                    recusados.append((cmd, r.motivo))
                else:
                    podiam.append(cmd)

            self.stdout.write("== publicar_comandos (dry-run) ==")
            self.stdout.write(
                f"  pendentes considerados: {len(fila)}   publicaveis: "
                f"{len(podiam)}   recusados: {len(recusados)}"
            )
            for cmd in podiam:
                self.stdout.write(
                    f"    [SARIA PUBLICADO] {cmd.comando} -> "
                    f"{pub.topico_de(cmd)}  (cmd {cmd.id}, "
                    f"{cmd.tentativas or 0} tentativa(s) anterior(es))"
                )
            for cmd, motivo in recusados:
                self.stdout.write(
                    f"    [recusado] {cmd.comando} (cmd {cmd.id}): {motivo}"
                )
            if not fila:
                self.stdout.write("  fila vazia.")
            self.stdout.write("\n  Nada foi publicado. Para publicar mesmo: --executar")
            return

        relatorio = pub.publicar(limite=limite)
        if options["json"]:
            self.stdout.write(json.dumps(relatorio, ensure_ascii=False, default=str))
            return

        self.stdout.write("== publicar_comandos ==")
        self.stdout.write(f"  considerados: {relatorio['vistos']}")
        self.stdout.write(
            self.style.SUCCESS(f"  publicados:  {relatorio['publicados']}")
        )
        self.stdout.write(f"  recusados:   {relatorio['recusados']}")
        if relatorio["erros"]:
            self.stdout.write(
                self.style.ERROR(
                    f"  ERROS:       {relatorio['erros']} — continuam na fila "
                    "para nova tentativa."
                )
            )
        for motivo, n in sorted(relatorio["motivos"].items(), key=lambda kv: -kv[1]):
            self.stdout.write(f"    {n}x {motivo}")
