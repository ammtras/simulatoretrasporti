from decimal import Decimal
from trasporti.models import Supplemento
from trasporti.services.base import TariffValidityService


class SupplementEngine:

    @staticmethod
    def calcola(spedizione, pacchi, base_importo, zona_corrente, ids_supplementi=None):
        """
        Calcola i supplementi.
        Se ids_supplementi è fornito, calcola solo quelli selezionati (modalità simulazione).
        Altrimenti, usa la logica standard basata sulla zona.
        """

        # 🟢 LOGICA DI FILTRO: Se abbiamo IDs dalla simulazione, usiamo quelli.
        if ids_supplementi:
            queryset = Supplemento.objects.filter(id__in=ids_supplementi)
        else:
            queryset = Supplemento.objects.filter(zone_tariffazione=zona_corrente)

        supplementi = TariffValidityService.filtra_validita(
            queryset.select_related('tipo_servizio').distinct(),
            spedizione.data
        )

        totale = Decimal("0")
        dettaglio = []

        # Recupero codici servizi (usando l'attributo iniettato se presente, altrimenti il DB)
        servizi_selezionati_codici = []
        if hasattr(spedizione, '_servizi_simulati'):
            servizi_selezionati_codici = [str(c).upper() for c in spedizione._servizi_simulati if c]
        elif spedizione.pk:
            servizi_selezionati_codici = [str(c).upper() for c in
                                          spedizione.servizi_richiesti.values_list('codice', flat=True) if c]

        for sup in supplementi:
            costo = Decimal("0")
            minimo = getattr(sup, 'diritto_minimo_euro', Decimal("0"))
            codice_servizio = sup.tipo_servizio.codice.upper() if sup.tipo_servizio else None

            if not codice_servizio:
                continue

            # =================================================================
            # 🟢 LOGICA DI CALCOLO
            # =================================================================
            if codice_servizio in ["ASSIC", "CONTR"]:
                # Recuperiamo il valore base (simulato o da DB)
                attr_name = 'assicurazione_euro' if codice_servizio == "ASSIC" else 'contrassegno_euro'
                valore_base = Decimal(str(getattr(spedizione, attr_name, 0) or 0))

                if valore_base > Decimal("0"):
                    if sup.calc_type == Supplemento.PERCENTAGE:
                        costo = valore_base * sup.valore / Decimal("100")
                        if minimo > 0: costo = max(costo, minimo)
                    elif sup.calc_type == Supplemento.FIXED:
                        costo = sup.valore
                else:
                    continue

            else:
                # Se non è ASSIC/CONTR, deve essere tra i servizi selezionati
                if codice_servizio not in servizi_selezionati_codici and not ids_supplementi:
                    continue

                fattore = Decimal(len(pacchi)) if sup.applic_type == Supplemento.ACOLLO else Decimal("1")

                if sup.calc_type == Supplemento.FIXED:
                    costo = sup.valore * fattore
                elif sup.calc_type == Supplemento.PERCENTAGE:
                    costo = base_importo * sup.valore / Decimal("100")
                    if minimo > 0: costo = max(costo, minimo)

            if costo > Decimal("0"):
                totale += costo
                dettaglio.append({
                    "nome": sup.nome,
                    "valore": sup.valore,
                    "tipo": sup.calc_type,
                    "applicazione": sup.applic_type,
                    "applica_fuel": sup.applica_fuel,
                    "costo": costo,
                })

        return {
            "totale": totale,
            "dettaglio": dettaglio
        }