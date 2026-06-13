
from decimal import Decimal
from trasporti.models import Supplemento
from trasporti.services.base import TariffValidityService


class FuelEngine:

    @staticmethod
    def calcola(spedizione, base_importo, supplementi_usati, z_spedizioniere=None):
        """
        Fuel surcharge calcolato su base importo + subset supplementi.
        Identifica le regole del carburante in base al tipo (PERCENTAGE) e al nome,
        rispettando il fatto che applica_fuel del carburante stesso sia FALSE nel DB.
        """

        # =====================================================================
        # 1. Prendi le regole del Fuel attive
        # =====================================================================
        if z_spedizioniere:
            # Se passiamo la zona calcolata (in simulazione), usiamo questa via sicura al 100%
            query_base = Supplemento.objects.filter(
                zone_tariffazione=z_spedizioniere,  # 👈 Se nel modello si chiama 'zona', sostituisci con zona=z_spedizioniere
                calc_type=Supplemento.PERCENTAGE,
                nome__icontains="fuel"
            )
        else:
            # Fallback se la spedizione è già salvata e ha un trasportatore,
            # usiamo l'ID puro per evitare errori sulle relazioni Many-to-Many
            id_trasportatore = getattr(spedizione, 'trasportatore_scelto_id', None)
            if id_trasportatore:
                query_base = Supplemento.objects.filter(
                    zona_spedizioniere__spedizioniere_id=id_trasportatore,
                    calc_type=Supplemento.PERCENTAGE,
                    nome__icontains="fuel"
                ).distinct()
            else:
                # Se non c'è modo di tracciare il corriere, restituisce una query vuota
                query_base = Supplemento.objects.none()

        fuel_rules = TariffValidityService.filtra_validita(query_base, spedizione.data)

        totale_fuel = Decimal("0")
        dettaglio = []

        # =====================================================================
        # 2. Calcolo base effettiva (Tariffa base + supplementi che SUBISCONO il fuel)
        # Se un supplemento ha applica_fuel=False (es: il fuel stesso), viene escluso.
        # =====================================================================
        base_fuel_effettiva = base_importo + sum([
            Decimal(s["costo"])
            for s in supplementi_usati
            if s.get("applica_fuel", True)
        ])

        # =====================================================================
        # 3. Applica la percentuale di Fuel sulla base corretta
        # =====================================================================
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