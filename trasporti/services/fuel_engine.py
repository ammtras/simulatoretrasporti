from decimal import Decimal
from trasporti.models import Supplemento
from trasporti.services.base import TariffValidityService


class FuelEngineXX:

    @staticmethod
    def calcola(spedizione, base_importo, supplementi_usati):
        """
        Fuel surcharge calcolato su base importo + subset supplementi
        """

        # =========================
        # 1. prendi supplementi fuel attivi
        # =========================
        fuel_rules = TariffValidityService.filtra_validita(
            Supplemento.objects.filter(
                spedizioniere=spedizione.trasportatore_scelto,
                applica_fuel=True,
                calc_type=Supplemento.PERCENTAGE
            ),
            spedizione.data
        )

        totale_fuel = Decimal("0")

        dettaglio = []

        # =========================
        # 2. base fuel (di solito base + alcuni supplementi)
        # =========================
        base_fuel = base_importo

        # =========================
        # 3. escludi supplementi NON soggetti a fuel
        # =========================
        esclusi = Decimal("0")

        for sup in supplementi_usati:

            if not sup.get("applica_fuel", True):
                esclusi += sup["costo"]

        base_fuel_effettiva = base_importo + (sum([
            Decimal(s["costo"])
            for s in supplementi_usati
            if s.get("applica_fuel", True)
        ]))

        # =========================
        # 4. applica fuel rules
        # =========================
        for fuel in fuel_rules:

            costo_fuel = base_fuel_effettiva * fuel.valore / Decimal("100")

            totale_fuel += costo_fuel

            dettaglio.append({
                "nome": fuel.nome,
                "percentuale": fuel.valore,
                "costo": costo_fuel
            })

        return {
            "totale": totale_fuel,
            "base_fuel": base_fuel_effettiva,
            "dettaglio": dettaglio
        }

from decimal import Decimal
from trasporti.models import Supplemento
from trasporti.services.base import TariffValidityService


class FuelEngine:

    @staticmethod
    def calcola(spedizione, base_importo, supplementi_usati):
        """
        Fuel surcharge calcolato su base importo + subset supplementi
        """

        # =====================================================================
        # 1. prendi supplementi fuel attivi
        # 🟢 CORREZIONE: Usiamo 'zone_tariffazione__spedizioniere' al posto di 'spedizioniere'
        # .distinct() assicura che se una regola fuel è legata a più zone, non venga duplicata
        # =====================================================================
        fuel_rules = TariffValidityService.filtra_validita(
            Supplemento.objects.filter(
                zone_tariffazione__spedizioniere=spedizione.trasportatore_scelto,
                applica_fuel=True,
                calc_type=Supplemento.PERCENTAGE
            ).distinct(),
            spedizione.data
        )

        totale_fuel = Decimal("0")
        dettaglio = []

        # =========================
        # 2. base fuel (di solito base + alcuni supplementi)
        # =========================
        base_fuel = base_importo

        # =========================
        # 3. escludi supplementi NON soggetti a fuel
        # =========================
        esclusi = Decimal("0")

        for sup in supplementi_usati:
            if not sup.get("applica_fuel", True):
                esclusi += sup["costo"]

        base_fuel_effettiva = base_importo + (sum([
            Decimal(s["costo"])
            for s in supplementi_usati
            if s.get("applica_fuel", True)
        ]))

        # =========================
        # 4. applica fuel rules
        # =========================
        for fuel in fuel_rules:
            costo_fuel = base_fuel_effettiva * fuel.valore / Decimal("100")
            totale_fuel += costo_fuel

            dettaglio.append({
                "nome": fuel.nome,
                "percentuale": fuel.valore,
                "costo": costo_fuel
            })

        return {
            "totale": totale_fuel,
            "base_fuel": base_fuel_effettiva,
            "dettaglio": dettaglio
        }