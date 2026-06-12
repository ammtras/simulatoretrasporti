
from trasporti.models import Zona_spedizioniere, Scaglione, OverflowTariff
from decimal import Decimal
from math import ceil
from django.db.models import Q




class GLSService:

    @staticmethod
    def get_zona_gls(spedizione):
        try:
            return Zona_spedizioniere.objects.get(
                spedizioniere__nome="GLS",
                zona=spedizione.a_zona
            )
        except Zona_spedizioniere.DoesNotExist:
            return None

    # =========================
    # 🟢 ENTRY POINT
    # =========================
    @staticmethod
    def calcola(spedizione, pacchi, peso_totale):

        zona_gls = GLSService.get_zona_gls(spedizione)

        if not zona_gls:
            return None

        if zona_gls.spedizioniere.tipo_tariffazione == "scaglioni":
            return GLSService._scaglioni(peso_totale, zona_gls)

        return GLSService._a_collo(spedizione, pacchi, zona_gls)

    # =========================
    # 🟢 SCAGLIONI
    # =========================
    @staticmethod
    def _scaglioni(peso_totale, zona_gls):

        scaglioni = Scaglione.objects.filter(
            zona_spedizioniere=zona_gls
        ).order_by("min_weight")

        scaglione = scaglioni.filter(
            min_weight__lte=peso_totale
        ).filter(
            Q(max_weight__gte=peso_totale) | Q(max_weight__isnull=True)
        ).first()

        if not scaglione:
            scaglione = scaglioni.last()

        if not scaglione:
            return None

        prezzo = scaglione.price

        soglia = scaglione.max_weight or scaglione.min_weight

        if peso_totale > soglia:

            extra = peso_totale - soglia

            overflow = OverflowTariff.objects.filter(
                zona_spedizioniere=zona_gls
            ).first()

            if overflow:
                steps = ceil(extra / overflow.step_kg)
                prezzo += steps * overflow.price_per_step

        return prezzo

    # =========================
    # 🟢 A COLLO
    # =========================
    @staticmethod
    def _a_collo(spedizione, pacchi, zona_gls):

        # placeholder logica futura
        peso_totale = sum(p["peso_kg"] for p in pacchi)
        return peso_totale * Decimal("1.2")