"""DIAGNÓSTICO: que mais está errado nos DADOS, e não no código.

Só leitura. Não escreve nada, não corrige nada, não apaga nada.

Este comando é a continuação do `checar_drift`, que aponta uma safra
impossível e pára aí. Este pergunta as perguntas que faltam:

  1. Todas as safras que não cabem no talhão (não só as que passam 2x).
  2. Soma dos talhões vs `area_total` declarada, por propriedade.
  3. Safras sem talhão, ou com talhão de área zero (sem contra-o-que conferir).
  4. Safras com `data_colheita` anterior ao plantio.
  5. Safras de anos futuros — Mistakes.
  6. Lançamentos financeiros com categoria/tipo impossível.
  7. Safras com área zero (registadas, mas por preencher).
  8. Propriedades sem nenhuma medida.

A saída é um relatório, não uma correcção. Cada linha diz o que está errado
e o que seria preciso para o decidir — porque em dado de cadastro, quem
sabe o valor certo é quem conhece a fazenda, e um comando não.
"""

from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db.models import F, Q, Sum


class Command(BaseCommand):
    help = "Diagnostico de DADOS incoerentes (so leitura). Nao altera nada."

    def handle(self, *args, **options):
        self._tornar_seguro_o_output()
        self._n_notas = 0
        self.encabezado()
        achados = 0
        achados += self.safras_vs_talhao()
        achados += self.safras_vs_propriedade()
        achados += self.talhoes_vs_area_total()
        achados += self.safras_sem_contraprova()
        achados += self.datas_impossiveis()
        achados += self.anos_futuros()
        achados += self.area_zero()
        achados += self.financeiro_impossivel()
        achados += self.propriedades_sem_medida()
        achados += self.usuarios_sem_perfil()
        self.rodape(achados)

    def _tornar_seguro_o_output(self):
        """O terminal tem uma codificação, e nem sempre dá para escrever nela.

        O separador `↳` (U+21B3) não existe em cp1252, que é a codificação por
        omissão da consola do Windows. `self.stdout.write` levantava
        `UnicodeEncodeError` — e o comando morria ali, a meio do relatório,
        depois de já ter escrito a primeira linha. Um relatório que falha a meio
        é pior do que um relatório feio: a ferramenta que existe para explicar
        dados incoerentes é a primeira a morrer quando há dados incoerentes.

        `errors="replace"` troca o que não cabe por `?` em vez de rebentar. Num
        terminal que dá para escrever, nada muda.
        """
        for stream in (self.stdout, self.stderr):
            reconfigure = getattr(stream, "reconfigure", None)
            if reconfigure is None:
                continue
            try:
                reconfigure(errors="replace")
            except (ValueError, OSError, AttributeError):
                # `StringIO` (nos testes) não aceita reconfigurar. Não é
                # motivo para o comando não correr.
                pass

    # ── apresentação ────────────────────────────────────────────────
    def encabezado(self):
        hoje = date.today()
        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("=" * 78))
        self.stdout.write(
            f" DIAGNÓSTICO DE DADOS — {hoje.isoformat()}  (leitura, não altera nada)"
        )
        self.stdout.write(self.style.MIGRATE_HEADING("=" * 78))

    def achado(self, categoria, texto):
        self.stdout.write(f"  [{categoria}] {texto}")

    def nota(self, texto):
        """Registo que NÃO conta como achado.

        Existe porque nem tudo o que está fora do lugar dói. Uma conta
        inactiva e um registo incoerente chegam ao produtor de formas
        diferentes, e dizer as duas coisas com o mesmo peso faz o relatório
        perder força: quando aparece tudo como "achado", ninguém sabe o que
        atender primeiro.

        A nota conta-se à parte. Um relatório cujo total não bate com o que a pessoa
        lê deixa de ser acreditado — e é o número grande, o primeiro em que se
        olha.
        """
        self._n_notas += 1
        self.stdout.write(f"  [NOTA] {texto}")

    def rodape(self, total):
        notas = getattr(self, "_n_notas", 0)
        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("-" * 78))
        if total == 0 and notas == 0:
            self.stdout.write(self.style.SUCCESS(" Nenhum achado."))
        elif total == 0:
            self.stdout.write(
                self.style.SUCCESS(
                    f" Nenhum achado. {notas} nota(s) para limpar quando quiser."
                )
            )
        else:
            sufixo = f" e {notas} nota(s) para limpar quando quiser" if notas else ""
            self.stdout.write(
                self.style.WARNING(
                    f" {total} achado(s){sufixo}. Nenhum é corrigido aqui: o valor "
                    "certo de um cadastro só quem conhece a fazenda sabe."
                )
            )
        self.stdout.write(self.style.MIGRATE_HEADING("-" * 78))

    # ── 1. safras que não cabem no talhão ───────────────────────────
    def safras_vs_talhao(self):
        from app.models import Safra

        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("1. SAFRA MAIOR QUE O TALHÃO"))
        linhas = []
        for s in (
            Safra.objects.filter(talhao__isnull=False)
            .exclude(talhao__area_hectare__isnull=True)
            .select_related("talhao", "cultura", "propriedade")
            .order_by("-area_plantada")
        ):
            a_talhao = float(s.talhao.area_hectare or 0)
            a_safra = float(s.area_plantada or 0)
            if a_talhao > 0 and a_safra > a_talhao * 1.10:
                linhas.append((s, a_safra, a_talhao))

        for s, a_safra, a_talhao in linhas:
            self.achado(
                "ÁREA",
                f"Safra {s.id} · {s.cultura.nome if s.cultura else '?'} · {s.ano} · "
                f"{s.propriedade.nome[:28]}: {a_safra:,.2f} ha em "
                f"'{s.talhao.nome}' ({a_talhao:,.2f} ha) = {a_safra / a_talhao:,.0f}x",
            )
            self.stdout.write(
                f"         ↳ o talhao tem {a_talhao:,.2f} ha; a safra aponta para ele. "
                "Ou a safra e' de outra propriedade, ou o talhao foi subdimensionado."
            )
        if not linhas:
            self.stdout.write(self.style.SUCCESS("  nenhuma"))
        return len(linhas)

    # ── 2. safras maiores que a propriedade ─────────────────────────
    def safras_vs_propriedade(self):
        from app.models import Safra

        self.stdout.write("")
        self.stdout.write(
            self.style.MIGRATE_HEADING("2. SAFRA MAIOR QUE A PROPRIEDADE (sem talhão)")
        )
        n = 0
        for s in (
            Safra.objects.filter(talhao__isnull=True)
            .select_related("cultura", "propriedade")
            .order_by("-area_plantada")
        ):
            a_prop = float(s.propriedade.area_total or 0)
            a_safra = float(s.area_plantada or 0)
            if a_prop > 0 and a_safra > a_prop * 3:
                n += 1
                self.achado(
                    "ÁREA",
                    f"Safra {s.id} · {s.cultura.nome if s.cultura else '?'} · {s.ano}: "
                    f"{a_safra:,.2f} ha sem talhao, propriedade tem {a_prop:,.2f} ha "
                    f"({a_safra / a_prop:,.1f}x). A area da propriedade precisa de revisao.",
                )
        if not n:
            self.stdout.write(self.style.SUCCESS("  nenhuma"))
        return n

    # ── 3. soma dos talhões vs área declarada ──────────────────────
    def talhoes_vs_area_total(self):
        from app.models import Propriedade, Talhao

        self.stdout.write("")
        self.stdout.write(
            self.style.MIGRATE_HEADING("3. TALHÕES SOMAM MAIS QUE A PROPRIEDADE")
        )
        n = 0
        for p in Propriedade.objects.all().order_by("id"):
            area_prop = float(p.area_total or 0)
            t = Talhao.objects.filter(propriedade=p)
            soma = float(t.aggregate(s=Sum("area_hectare"))["s"] or 0)
            if not area_prop or not soma:
                continue
            if soma > area_prop * 1.05:
                n += 1
                dif = soma - area_prop
                self.achado(
                    "ÁREA",
                    f"Propriedade {p.id} · {p.nome[:34]}: area_total="
                    f"{area_prop:,.2f} ha mas {t.count()} talhoes somam {soma:,.2f} ha "
                    f"(+{dif:,.2f})",
                )
                maiores = t.order_by("-area_hectare")[:3]
                for tt in maiores:
                    self.stdout.write(
                        f"         ↳ maior talhao: '{tt.nome}' {float(tt.area_hectare or 0):,.2f} ha"
                    )
        if not n:
            self.stdout.write(self.style.SUCCESS("  nenhuma"))
        return n

    # ── 4. safras sem contraprova ───────────────────────────────────
    def safras_sem_contraprova(self):
        from app.models import Safra

        self.stdout.write("")
        self.stdout.write(
            self.style.MIGRATE_HEADING("4. SAFRA SEM CONTRA-O-QUE-CONFERIR")
        )
        # `Safra.Meta.ordering` é `["-ano", "cultura"]`, e um `union()` herda
        # esse ORDER BY — que o SQLite recusa em subconsultas de um statement
        # composto ("ORDER BY not allowed in subqueries of compound
        # statements"). Por isso as contagens vão por `values_list`, e a
        # lista final é desduplicada: uma safra sem talhão e com talhão sem
        # área não pode ser contada duas vezes.
        sem_talhao_ids = list(
            Safra.objects.filter(talhao__isnull=True)
            .order_by()
            .values_list("id", flat=True)
        )
        talhao_sem_area_ids = list(
            Safra.objects.filter(talhao__isnull=False)
            .filter(Q(talhao__area_hectare__isnull=True) | Q(talhao__area_hectare=0))
            .order_by()
            .values_list("id", flat=True)
        )
        if sem_talhao_ids:
            self.achado(
                "CONFERÊNCIA",
                f"{len(sem_talhao_ids)} safra(s) sem talhao ligado — a soma do "
                "ano não pode ser confrontada com a área dos talhões. "
                f"ids: {sem_talhao_ids[:10]}",
            )
        if talhao_sem_area_ids:
            self.achado(
                "CONFERÊNCIA",
                f"{len(talhao_sem_area_ids)} safra(s) em talhao sem area medida "
                f"— mesma limitação. ids: {talhao_sem_area_ids[:10]}",
            )
        if not sem_talhao_ids and not talhao_sem_area_ids:
            self.stdout.write(self.style.SUCCESS("  nenhuma"))
        return len(set(sem_talhao_ids) | set(talhao_sem_area_ids))

    # ── 5. datas impossíveis ────────────────────────────────────────
    def datas_impossiveis(self):
        from app.models import Safra

        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("5. DATAS QUE NÃO FAZEM SENTIDO"))
        n = 0
        for s in (
            Safra.objects.filter(
                data_plantio__isnull=False, data_colheita__isnull=False
            )
            .filter(data_colheita__lt=F("data_plantio"))
            .select_related("cultura", "propriedade")
        ):
            n += 1
            self.achado(
                "DATA",
                f"Safra {s.id} · {s.cultura.nome if s.cultura else '?'} · {s.ano}: "
                f"colheita {s.data_colheita} ANTES do plantio {s.data_plantio}",
            )
        # Also: colheita muito depois do plantio (mais de 2 anos)
        for s in Safra.objects.filter(
            data_plantio__isnull=False, data_colheita__isnull=False
        ).select_related("cultura"):
            dias = (s.data_colheita - s.data_plantio).days
            if 0 <= dias > 730:
                n += 1
                self.achado(
                    "DATA",
                    f"Safra {s.id} · {s.cultura.nome if s.cultura else '?'} · {s.ano}: "
                    f"{dias} dias entre plantio e colheita ({dias / 365:.1f} anos) — "
                    "revisar as datas ou o que a safra representa.",
                )
        if not n:
            self.stdout.write(self.style.SUCCESS("  nenhuma"))
        return n

    # ── 6. anos futuros ─────────────────────────────────────────────
    def anos_futuros(self):
        from app.models import Safra

        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("6. SAFRA COM ANO NO FUTURO"))
        hoje = date.today()
        n = 0
        for s in Safra.objects.filter(ano__gt=hoje.year).select_related("cultura"):
            n += 1
            self.achado(
                "ANO",
                f"Safra {s.id} · {s.cultura.nome if s.cultura else '?'}: ano={s.ano} "
                f"(estamos em {hoje.year}) — safra planeada, ou o ano está errado.",
            )
        if not n:
            self.stdout.write(self.style.SUCCESS("  nenhuma"))
        return n

    # ── 7. safras com área zero ─────────────────────────────────────
    def area_zero(self):
        from app.models import Safra

        self.stdout.write("")
        self.stdout.write(
            self.style.MIGRATE_HEADING("7. SAFRA REGISTADA COM ÁREA ZERO")
        )
        n = 0
        for s in Safra.objects.filter(area_plantada=0).select_related(
            "cultura", "propriedade"
        ):
            n += 1
            self.achado(
                "ÁREA",
                f"Safra {s.id} · {s.cultura.nome if s.cultura else '?'} · {s.ano}: "
                f"area_plantada=0.00 (faz a media do ano descer sem aviso).",
            )
        if not n:
            self.stdout.write(self.style.SUCCESS("  nenhuma"))
        return n

    # ── 8. financeiro impossível ────────────────────────────────────
    def financeiro_impossivel(self):
        from app.models import LancamentoFinanceiro

        self.stdout.write("")
        self.stdout.write(
            self.style.MIGRATE_HEADING("8. LANÇAMENTO FINANCEIRO IMPOSSÍVEL")
        )
        n = 0

        # categoria FOLHA registada como RECEITA
        folha_Receita = LancamentoFinanceiro.objects.filter(
            tipo="RECEITA", categoria__icontains="FOLHA"
        ).select_related("propriedade")
        for l in folha_Receita:
            n += 1
            self.achado(
                "FINANCEIRO",
                f"Lançamento {l.id} · {l.propriedade.nome[:28]}: "
                f"tipo=RECEITA mas categoria=FOLHA (descricao: '{l.descricao or '—'}') "
                f"— folha é despesa. {float(l.valor or 0):,.2f}",
            )

        # valores negativos (estorno mal registado?)
        negativos = LancamentoFinanceiro.objects.filter(valor__lt=0).select_related(
            "propriedade"
        )
        for l in negativos[:10]:
            n += 1
            self.achado(
                "FINANCEIRO",
                f"Lançamento {l.id}: valor negativo {float(l.valor):,.2f} "
                f"({l.tipo}) — se é estorno, registe como tal.",
            )

        if not n:
            self.stdout.write(self.style.SUCCESS("  nenhum"))
        return n

    # ── 9. propriedades sem medida ──────────────────────────────────
    def propriedades_sem_medida(self):
        from app.models import Propriedade, Safra

        self.stdout.write("")
        self.stdout.write(
            self.style.MIGRATE_HEADING("9. PROPRIEDADE SEM ÁREA (meios de custo, ROI)")
        )
        n = 0
        for p in Propriedade.objects.filter(area_total=0).select_related("user"):
            n += 1
            safras = Safra.objects.filter(propriedade=p).count()
            self.achado(
                "MEDIDA",
                f"Propriedade {p.id} · {p.nome[:30]} ({p.user.username}): "
                f"area_total=0.00 com {safras} safra(s) — não há como calcular "
                "custo/ha nem ROI. A área precisa de ser medida.",
            )
        if not n:
            self.stdout.write(self.style.SUCCESS("  nenhuma"))
        return n

    # ── 10. utilizadores sem PerfilUsuario ───────────────────────────
    def usuarios_sem_perfil(self):
        """Todo `User` deve ter `PerfilUsuario` — o sinal cria-o no `post_save`.

        Quem ficou de fora (contas anteriores ao sinal, imports, SSO) entra com
        **nível hierárquico 0**: faz login e não vê nada, sem explicação e sem
        rasto em lugar nenhum. O `checar_drift` não apanha — compara schema, e
        aqui o schema está certo.

        Não é corrigido aqui. Dar um perfil é dar um papel, e qual papel é uma
        decisão de quem conhece a conta; este comando é de leitura.
        """
        from django.contrib.auth.models import User

        from app.models import PerfilUsuario

        self.stdout.write("")
        self.stdout.write(
            self.style.MIGRATE_HEADING("10. UTILIZADOR SEM PERFIL (nível 0)")
        )
        com_perfil = set(PerfilUsuario.objects.values_list("user_id", flat=True))
        orfaos = [
            u for u in User.objects.all().order_by("id") if u.id not in com_perfil
        ]
        for u in orfaos:
            # Uma conta desactivada não é o mesmo problema que uma activa.
            # Inactiva, ninguém entra com ela: o ruído fica na base mas não
            # chega ao produtor. Activa, alguém que KNOWS a palavra-passe
            # entra e não vê nada, sem explicação — esse é o que dói.
            if u.is_active:
                self.achado(
                    "ORFAO",
                    f"Utilizador {u.id} · {u.username} (staff={u.is_staff}) não tem "
                    "PerfilUsuario: entra com nível 0 e não vê nada. Apague a conta "
                    "ou defina o papel.",
                )
            else:
                self.nota(
                    f"Utilizador {u.id} · {u.username} sem PerfilUsuario, mas "
                    "inactivo: não entra. Limpe quando quiser."
                )
        if not orfaos:
            self.stdout.write(self.style.SUCCESS("  nenhuma"))
        # Devolve só as ACTivas. As inactivas são [NOTA] e não entram no total
        # do rodapé — se o número aqui não bater com o que a pessoa leu acima,
        # deixa de confiar no relatório inteiro. (Foi o meu próprio bug: escrevi
        # `len(orfaos)` e o rodapé passou a dizer 3 achados quando a pessoa
        # lia 1 achado e 2 notas.)
        return sum(1 for u in orfaos if u.is_active)
