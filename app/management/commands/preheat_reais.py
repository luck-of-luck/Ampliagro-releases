"""
Preaquece cache IBGE para todas culturas reais (vegetal/animal/aquático) e checa alertas.
Uso: python manage.py preheat_reais
Agendado via cron 06:00 diariamente.
"""

import logging

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management.base import BaseCommand
from rest_framework.test import APIRequestFactory, force_authenticate

from app.api.views.cultures import ibge_proxy_data

logger = logging.getLogger(__name__)

# Lista curta para preheat (as 35 vegetais + 18 animal + 8 aquático validadas)
CULTURAS_PREHEAT = [
    # vegetal 29+6
    "cult-leguminosas-soja",
    "cult-graos-milho",
    "cult-graos-arroz",
    "cult-graos-trigo",
    "cult-leguminosas-feijao",
    "cult-fibras-algodao",
    "cult-graos-cafe",
    "cult-cana-cana-de-acucar",
    "cult-leguminosas-amendoim",
    "cult-oleaginosas-girassol",
    "cult-graos-sorgo",
    "cult-graos-cevada",
    "cult-graos-aveia",
    "cult-tuberculos-batata",
    "cult-tuberculos-mandioca",
    "cult-hortalicas-tomate",
    "cult-hortalicas-cebola",
    "cult-hortalicas-alho",
    "cult-hortalicas-cenoura",
    "cult-frutas-banana",
    "cult-citricos-laranja",
    "cult-frutas-manga",
    "cult-trepadeiras-uva",
    "cult-frutas-maca",
    "cult-frutas-mamao",
    "cult-frutas-melancia",
    "cult-frutas-melao",
    # animal
    "cult-bovinos-nelore",
    "cult-bovinos-angus",
    "cult-suinos-landrace",
    "cult-aves-galinha",
    "cult-aves-frango",
    "cult-ovinos-ovelha",
    # aquático
    "cult-peixes-tilapia",
    "cult-peixes-tambaqui",
    "cult-peixes-pacu",
]


class Command(BaseCommand):
    help = "Preaquece IBGE e checa alertas 06h"

    def handle(self, *args, **opts):
        User = get_user_model()
        u = User.objects.filter(is_superuser=True).first() or User.objects.first()
        if not u:
            self.stdout.write(self.style.WARNING("Sem usuário para preheat"))
            return
        factory = APIRequestFactory()
        ok, fail = 0, 0
        for cid in CULTURAS_PREHEAT:
            req = factory.get(f"/api/ibge-proxy/?cultura={cid}")
            force_authenticate(req, user=u)
            try:
                resp = ibge_proxy_data(req)
                if resp.data.get("source") in ("ibge", "fallback") and resp.data.get(
                    "metrics"
                ):
                    ok += 1
                else:
                    fail += 1
            except Exception as e:
                fail += 1
                logger.warning(f"preheat fail {cid}: {e}")
        self.stdout.write(
            self.style.SUCCESS(
                f"Preheat: {ok} ok, {fail} fail ({len(CULTURAS_PREHEAT)} culturas)"
            )
        )
        # Alertas simples: Soja -5% vs cache anterior
        try:
            from app.models import Cultura

            # Exemplo: verifica Soja valor_saca
            cid = "cult-leguminosas-soja"
            req = factory.get(f"/api/ibge-proxy/?cultura={cid}")
            force_authenticate(req, user=u)
            resp = ibge_proxy_data(req)
            metrics = {m["key"]: m for m in resp.data.get("metrics", [])}
            valor_atual = metrics.get("valor_saca", {}).get("value")
            # compara com cache anterior
            prev = cache.get("alert_prev_soja_valor")
            if prev and valor_atual and prev != valor_atual:
                # tenta parse R$ 137,00 -> 137
                def parse(v):
                    try:
                        return float(
                            str(v)
                            .replace("R$", "")
                            .replace(".", "")
                            .replace(",", ".")
                            .strip()
                        )
                    except Exception:
                        return None

                cur = parse(valor_atual)
                prv = parse(prev)
                if cur and prv and prv != 0 and abs(cur - prv) / prv >= 0.05:
                    from app.models import Notificacao

                    # cria notificação para todos superusers
                    for su in User.objects.filter(is_superuser=True):
                        Notificacao.objects.get_or_create(
                            user=su,
                            titulo="Alerta Soja -5%",
                            defaults={
                                "mensagem": f"Soja {prv} -> {cur} ({(cur - prv) / prv * 100:.1f}%)",
                                "nivel": "warning",
                            },
                        )
                    self.stdout.write(self.style.WARNING(f"Alerta Soja {prv}->{cur}"))
            if valor_atual:
                cache.set("alert_prev_soja_valor", valor_atual, 86400 * 7)
            # Chuva 80% 72h e Lotação >3.5
            try:
                from app.models import Propriedade

                for prop in Propriedade.objects.exclude(cidade="").exclude(
                    cidade__isnull=True
                )[:5]:
                    try:
                        from app.api.views.utils import _get_real_weather

                        w = _get_real_weather(prop)
                        previsoes = w.get("previsao", []) if isinstance(w, dict) else []
                        for p in previsoes[:3]:
                            prob = (
                                p.get("probabilidade")
                                or p.get("precipitacao_probabilidade")
                                or 0
                            )
                            if isinstance(prob, str):
                                prob = float(prob.replace("%", "") or 0)
                            if prob >= 80:
                                from app.models import Notificacao

                                for su in User.objects.filter(is_superuser=True):
                                    Notificacao.objects.get_or_create(
                                        user=su,
                                        titulo=f"Alerta Chuva {prop.nome}",
                                        defaults={
                                            "mensagem": f"{prob}% chuva em {prop.cidade} 72h — adie plantio",
                                            "nivel": "warning",
                                        },
                                    )
                                break
                    except Exception:
                        continue
            except Exception:
                pass
            try:
                from app.models import Talhao

                for t in Talhao.objects.filter(ativo=True).select_related(
                    "propriedade"
                )[:5]:
                    if t.area_hectare and float(t.area_hectare) > 0:
                        try:
                            from app.models import ProducaoAnimal

                            cabecas = ProducaoAnimal.objects.filter(talhao=t).count()
                            if cabecas:
                                taxa = cabecas / float(t.area_hectare)
                                if taxa > 3.5:
                                    from app.models import Notificacao

                                    for su in User.objects.filter(is_superuser=True):
                                        Notificacao.objects.get_or_create(
                                            user=su,
                                            titulo=f"Lotação alta {t.nome}",
                                            defaults={
                                                "mensagem": f"{taxa:.1f} cab/ha em {t.nome} — acima de 3.5",
                                                "nivel": "critical",
                                            },
                                        )
                        except Exception:
                            pass
            except Exception:
                pass
        except Exception as e:
            logger.warning(f"alertas fail: {e}")
        self.stdout.write(
            self.style.SUCCESS("Jobs 06h concluído — Soja, Chuva, Lotação")
        )
