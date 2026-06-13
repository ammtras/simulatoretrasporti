from decimal import Decimal
from trasporti.models import Supplemento
from trasporti.services.base import TariffValidityService


class SupplementEngine:

    @staticmethod
    def calcola(spedizione, pacchi, base_importo, zona_corrente):
        """
        Calcola i supplementi basandosi sulla zona corrente.
        🟢 LOGICA AGGIORNATA: Inclusione del diritto_minimo_euro per supplementi percentuali.
        """

        supplementi = TariffValidityService.filtra_validita(
            Supplemento.objects.filter(
                zone_tariffazione=zona_corrente
            ).select_related('tipo_servizio').distinct(),
            spedizione.data
        )

        totale = Decimal("0")
        dettaglio = []

        servizi_selezionati_codici = []
        if spedizione.pk:
            servizi_selezionati_codici = list(spedizione.servizi_richiesti.values_list('codice', flat=True))
        else:
            try:
                servizi_selezionati_codici = [s.codice for s in spedizione.servizi_richiesti.all()]
            except (ValueError, AttributeError):
                servizi_selezionati_codici = []

        servizi_selezionati_codici = [str(c).upper() for c in servizi_selezionati_codici if c]

        for sup in supplementi:
            costo = Decimal("0")
            minimo = getattr(sup, 'diritto_minimo_euro', Decimal("0"))
            codice_servizio = sup.tipo_servizio.codice.upper() if sup.tipo_servizio else None

            if not codice_servizio:
                continue

            # =================================================================
            # 🟢 LOGICA DI CALCOLO (PERCENTAGE o FIXED)
            # =================================================================
            if codice_servizio in ["ASSIC", "CONTR"]:
                valore_base = Decimal(
                    str(getattr(spedizione, 'assicurazione_euro' if codice_servizio == "ASSIC" else 'contrassegno_euro',
                                0) or 0))

                if valore_base > Decimal("0"):
                    if sup.calc_type == Supplemento.PERCENTAGE:
                        costo = valore_base * sup.valore / Decimal("100")
                        if minimo > 0: costo = max(costo, minimo)
                    elif sup.calc_type == Supplemento.FIXED:
                        costo = sup.valore
                else:
                    continue

            else:
                if codice_servizio not in servizi_selezionati_codici:
                    continue

                fattore = Decimal(len(pacchi)) if sup.applic_type == Supplemento.ACOLLO else Decimal("1")

                if sup.calc_type == Supplemento.FIXED:
                    costo = sup.valore * fattore
                elif sup.calc_type == Supplemento.PERCENTAGE:
                    costo = base_importo * sup.valore / Decimal("100")
                    if minimo > 0: costo = max(costo, minimo)

            # =================================================================
            # ACCUMULO RISULTATI
            # =================================================================
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