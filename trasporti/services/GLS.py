from trasporti.models import Zona_spedizioniere, Scaglione, OverflowTariff
from decimal import Decimal
from math import ceil
from django.db.models import Q


class GLSService:

    # =========================
    # 🟢 ZONA
    # =========================
    @staticmethod
    def get_zona_gls(spedizione):
        return getattr(spedizione, "zona_tariffazione_spedizioniere", None)

    # =========================
    # 🟢 PESO TASSABILE
    # =========================
    @staticmethod
    def _peso_tassabile(pacchi, zona_gls):
        print(pacchi)
        divisore = zona_gls.divisore_volumetrico

        peso_reale = sum(
            Decimal(p["peso_kg"])
            for p in pacchi
            if p and p.get("peso_kg") is not None
        )

        peso_volume = sum(
            (Decimal(p["profondita_cm"]) *
             Decimal(p["larghezza_cm"]) *
             Decimal(p["altezza_cm"])) / Decimal(divisore)
            for p in pacchi
            if p and all(k in p for k in ["profondita_cm", "larghezza_cm", "altezza_cm"])
        )
        print(f'peso reale :{peso_reale}')
        print(f'peso volume :{peso_volume}')
        return max(peso_reale, peso_volume)
        print(f'max: {max}')

    # =========================
    # 🟢 ENTRY POINT
    # =========================
    @staticmethod
    def dettaglio_calcolo_preventivo(pacchi, zona_gls):

        divisore = zona_gls.divisore_volumetrico

        peso_reale = sum(
            Decimal(p["peso_kg"])
            for p in pacchi
            if p and p.get("peso_kg") is not None
        )

        peso_volume = sum(
            (
                    Decimal(p.get("altezza_cm") or 0) *
                    Decimal(p.get("larghezza_cm") or 0) *
                    Decimal(p.get("profondita_cm") or 0)
            ) / Decimal(divisore)
            for p in pacchi
        )

        peso_tassabile = max(peso_reale, peso_volume)

        return {
            "peso_reale": peso_reale,
            "peso_volume": peso_volume,
            "peso_tassabile": peso_tassabile,
            "formula": f"max({peso_reale}, {peso_volume}) = {peso_tassabile}"
        }

    @staticmethod
    def calcola(spedizione, pacchi):

        zona_gls = GLSService.get_zona_gls(spedizione)

        if not zona_gls:
            return None

        #peso_tassabile = GLSService._peso_tassabile(pacchi, zona_gls)
        dettaglio = GLSService.dettaglio_calcolo_preventivo(pacchi, zona_gls)
        peso_tassabile = dettaglio["peso_tassabile"]

        print(f'peso tassabile :{peso_tassabile}')

        if zona_gls.spedizioniere.tipo_tariffazione == "scaglioni":
            return GLSService._scaglioni(peso_tassabile, zona_gls, dettaglio)


        return GLSService._a_collo(pacchi, zona_gls)


    # =========================
    # 🟢 SCAGLIONI
    # =========================
    @staticmethod
    def _scaglioni(peso_tassabile, zona_gls, dettaglio):

        scaglioni = Scaglione.objects.filter(
            zona_spedizioniere=zona_gls
        ).order_by("min_weight")

        scaglione = scaglioni.filter(
            min_weight__lte=peso_tassabile
        ).filter(
            Q(max_weight__gte=peso_tassabile) | Q(max_weight__isnull=True)
        ).first()

        if not scaglione:
            scaglione = scaglioni.last()

        if not scaglione:
            return None

        prezzo = scaglione.price

        soglia = scaglione.max_weight or scaglione.min_weight

        if peso_tassabile > soglia:

            extra = peso_tassabile - soglia

            overflow = OverflowTariff.objects.filter(
                zona_spedizioniere=zona_gls
            ).first()

            if overflow:
                steps = ceil(extra / overflow.step_kg)
                prezzo += steps * overflow.price_per_step

        return {
            "prezzo": prezzo,
            "dettaglio": dettaglio
        }

    # =========================
    # 🟢 A COLLO
    # =========================
    @staticmethod
    def _a_collo(pacchi, zona_gls):

        peso_tassabile = GLSService._peso_tassabile(pacchi, zona_gls)

        return peso_tassabile * Decimal("1.2")

