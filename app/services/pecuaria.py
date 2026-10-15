from decimal import Decimal

from app.models.pecuaria import AnimalIndividual, Pesagem, Piquete


class PecuariaService:
    @staticmethod
    def calcular_gmd(animal_id: int):
        """
        Calcula o Ganho Médio Diário (GMD) em kg/dia para um animal.
        Retorna float com GMD ou None se houver menos de 2 pesagens.
        """
        pesagens = Pesagem.objects.filter(animal_id=animal_id).order_by("data")
        if pesagens.count() < 2:
            return None

        primeira = pesagens.first()
        ultima = pesagens.last()

        dias = (ultima.data - primeira.data).days
        if dias <= 0:
            return 0.0

        ganho = float(ultima.peso - primeira.peso)
        return round(ganho / dias, 3)

    @staticmethod
    def obter_ultimo_peso(animal_id: int):
        ultima_pesagem = (
            Pesagem.objects.filter(animal_id=animal_id).order_by("-data").first()
        )
        if ultima_pesagem:
            return float(ultima_pesagem.peso)

        # Fallback para peso ao nascer ou valor padrão
        animal = AnimalIndividual.objects.get(id=animal_id)
        return float(animal.peso_nascimento) if animal.peso_nascimento else 0.0

    @staticmethod
    def calcular_lotacao_piquete(piquete_id: int):
        """
        Calcula a lotação atual de um piquete em Unidades Animais por hectare (UA/ha).
        1 UA = 450 kg de peso vivo (padrão Brasil).
        """
        piquete = Piquete.objects.get(id=piquete_id)
        animais = piquete.animais.all()

        peso_total = 0.0
        for animal in animais:
            peso_total += PecuariaService.obter_ultimo_peso(animal.id)

        unidades_animais = peso_total / 450.0
        area_ha = float(piquete.area_hectare)

        if area_ha <= 0:
            return {"ua_total": round(unidades_animais, 2), "ua_ha": 0.0}

        ua_ha = unidades_animais / area_ha

        return {
            "ua_total": round(unidades_animais, 2),
            "ua_ha": round(ua_ha, 2),
            "animais_qtd": animais.count(),
            "peso_total_kg": round(peso_total, 2),
        }

    @staticmethod
    def get_alertas_sanitarios(propriedade_id: int):
        from datetime import timedelta

        from django.utils import timezone

        from app.models.pecuaria import EventoSanitario

        hoje = timezone.now().date()
        limite_dias = hoje + timedelta(days=15)

        # Filtra eventos com proxima_dose vencida ou a vencer em até 15 dias
        eventos_alerta = (
            EventoSanitario.objects.filter(
                animal__propriedade_id=propriedade_id,
                proxima_dose__isnull=False,
                proxima_dose__lte=limite_dias,
            )
            .select_related("animal", "protocolo")
            .order_by("proxima_dose")
        )

        alertas = []
        for evt in eventos_alerta:
            status = "vencido" if evt.proxima_dose < hoje else "a_vencer"
            dias_restantes = (evt.proxima_dose - hoje).days

            alertas.append(
                {
                    "animal_brinco": evt.animal.brinco,
                    "animal_id": evt.animal.id,
                    "protocolo": evt.protocolo.nome if evt.protocolo else evt.tipo,
                    "proxima_dose": evt.proxima_dose,
                    "status": status,
                    "dias_restantes": dias_restantes,
                }
            )

        return alertas
