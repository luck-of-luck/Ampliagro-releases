"""A conta de teste principal. Criada uma vez, e nunca mais tocada.

    python manage.py criar_conta_demo

O QUE ESTE COMANDO É, E O QUE ELE PROMETE
==========================================
A conta de teste principal do Ampliagro: uma exploração cafeeira e de corte
em Muzambinho, MG. É a conta onde os dados são reais e inseridos à mão — e é
por isso que este comando tem uma regra absoluta:

    **NUNCA alterar a palavra-passe, o nome de utilizador, ou os dados
    desta conta depois de a criar.**

Não é uma preferência. É a razão de o comando ser idempotente e de não ter
onde escrever um update: correr outra vez não muda nada, e a pessoa que o
executa não tem como estragar o trabalho de quem popula a base.

O QUE ELE NÃO FAZ
==================
Não inventa safras, lançamentos, inventário ou produção. Estes são DADOS, e dados
falsos numa conta de teste são piores do que uma conta vazia: quando um número
não bate, não se sabe se o cálculo errou ou se a preenchimento foi inventado.
Quem preenche a base é quem sabe o que é real.

Por isso o comando cria a IDENTIDADE — utilizador e propriedade — e mais nada.
A área total é o único número que exige e pode ser passada em `--area`;
o resto da propriedade fica por preencher, porque quem preenche a base
decide os hectares.
"""

from __future__ import annotations

import secrets
import string
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction

from app.models import Propriedade

USUARIO = "demo.muzambinho"
NOME_PESSOA = "Produtora Muzambinho"
NOME_FAZENDA = "Fazenda Muzambinho"
CIDADE = "Muzambinho"
UF = "MG"
BIOMA = "Mata Atlântica"
ATIVIDADE = "Café e gado de corte"


def senha_forte(n=20) -> str:
    """Senha gerada, mostrada UMA vez na criação.

    O alfabeto exclui o que se confunde à primeira vista: `0`/`O`, `1`/`l`/`I`.
    Uma palavra-passe que alguém tem de reler três vezes não é uma palavra-passe,
    é um-disable do logout.
    """
    alfabeto = string.ascii_letters + string.digits
    digitos = "23456789"
    # Garante pelo menos um digito inequivoco
    base = "".join(secrets.choice(alfabeto) for _ in range(n - 1))
    return base + secrets.choice(digitos)


class Command(BaseCommand):
    help = "Cria a conta de teste principal (café e corte, Muzambinho/MG). Nunca altera uma conta existente."

    def add_arguments(self, parser):
        parser.add_argument(
            "--area",
            type=str,
            default=None,
            help="Área total em hectares. Sem este valor a propriedade fica por preencher, "
            "que é o honesto: quem conhece a fazenda é quem a mede.",
        )
        parser.add_argument(
            "--senha",
            type=str,
            default=None,
            help="Palavra-passe a definir NA CRIAÇÃO. Depois de criada, esta opção é "
            "ignorada de propósito — a palavra-passe é do dono da conta.",
        )

    def handle(self, *args, **options):
        existente = User.objects.filter(username=USUARIO).first()
        if existente:
            # A RAMA MAIS IMPORTANTE DESTE COMANDO.
            # Correr outra vez NÃO toca em nada. Nem na palavra-passe, nem no
            # nome, nem na propriedade. Só relata o que existe.
            self._relata(existente)
            return

        senha = options.get("senha") or senha_forte()
        area = options.get("area")

        with transaction.atomic():
            user = User.objects.create_user(
                username=USUARIO,
                password=senha,
                first_name=NOME_PESSOA,
                email="demo.muzambinho@exemplo.local",
                is_staff=True,
            )
            prop = Propriedade.objects.create(
                user=user,
                nome=NOME_FAZENDA,
                cidade=CIDADE,
                uf=UF,
                pais="Brasil",
                bioma=BIOMA,
                tipo_exploracao="1",
                # `area_total` é NOT NULL no esquema. Sem o valor real entra
                # ZERO — que neste campo significa "por preencher", e não "a
                # fazenda tem-area". O relatório diz isso com todas as letras,
                # porque um 0 lido como área é um número que engana em silêncio.
                area_total=Decimal(area) if area else Decimal("0"),
            )

        self.stdout.write(self.style.SUCCESS("Conta de teste principal criada."))
        self.stdout.write("")
        self.stdout.write(f"  utilizador : {USUARIO}")
        self.stdout.write(f"  palavra-passe : {senha}")
        self.stdout.write("")
        self.stdout.write(
            self.style.WARNING(
                "  A PALAVRA-PASSE É MOSTRADA UMA VEZ E SÓ ESTA. Não há recuperação: "
                "este comando não a volta a mostrar, porque alterá-la é proibido."
            )
        )
        self.stdout.write(
            self.style.WARNING(
                "  Daqui para a frente, esta conta é sua. Nem a palavra-passe, nem o "
                "nome, nem os dados são tocados por mim ou por este comando."
            )
        )
        self._relata(user, propriedade=prop)

    def _relata(self, user, propriedade=None):
        props = list(Propriedade.objects.filter(user=user))
        alvo = propriedade or (props[0] if props else None)
        self.stdout.write("")
        self.stdout.write(f"  {user.username} ({user.first_name or 'sem nome'})")
        if alvo:
            area = getattr(alvo, "area_total", None)
            self.stdout.write(
                f"    fazenda : {alvo.nome} — {alvo.cidade}/{alvo.uf}"
                + (f" — {area} ha" if area else " — área por preencher")
            )
            self.stdout.write(f"    perfil  : {ATIVIDADE} (vem dos dados que inserir)")
        if not props:
            self.stdout.write(
                "    propriedade : nenhuma — a app vai levar ao onboarding"
            )
        elif len(props) > 1:
            self.stdout.write(f"    propriedades : {len(props)}")
