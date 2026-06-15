from decimal import Decimal
from trasporti.models import Supplemento
from trasporti.services.base import TariffValidityService



class SupplementEngine:

    @staticmethod
    def calcola(spedizione, pacchi, base_importo, zona_corrente, ids_supplementi=None):
        # 1. Recupera solo ciò che è SELEZIONATO
        # Se non hai selezionato nulla (ids_supplementi vuoto), la lista deve essere vuota!
        if not ids_supplementi:
            # Aggiungi qui solo i supplementi obbligatori (es. ASSIC/CONTR se presenti nel form)
            # Ma evita di caricare "tutti" i supplementi della zona
            ids_supplementi = []

        queryset = Supplemento.objects.filter(
            zone_tariffazione=zona_corrente,
            id__in=ids_supplementi  # <--- FORZA IL FILTRO A VUOTO SE NON SELEZIONATO
        )


        if ids_supplementi:
            queryset = queryset.filter(id__in=ids_supplementi)


        supplementi = TariffValidityService.filtra_validita(
            queryset.select_related('tipo_servizio').distinct(),
            spedizione.data
        )
        print(f'supplementi validi nella zona?? {supplementi}')


        totale = Decimal("0")
        dettaglio = []


        servizi_selezionati_codici = []

        if hasattr(spedizione, "_servizi_simulati"):
            servizi_selezionati_codici = [
                str(c).upper() for c in spedizione._servizi_simulati if c
            ]

        elif spedizione.pk:
            servizi_selezionati_codici = list(
                spedizione.servizi_richiesti.values_list("codice", flat=True)
            )
            servizi_selezionati_codici = [
                str(c).upper() for c in servizi_selezionati_codici if c
            ]

        # 🟢 LOOP SUPPLEMENTI
        for sup in supplementi:

            costo = Decimal("0")
            minimo = getattr(sup, "diritto_minimo_euro", Decimal("0"))
            codice_servizio = (
                sup.tipo_servizio.codice.strip()
                if sup.tipo_servizio else None
            )

            if not codice_servizio:
                continue

            # =========================================================
            # 🔥 ASSIC / CONTR (FIX DEFINITIVO)
            # =========================================================
            if codice_servizio in ["ASSIC", "CONTR"]:

                attr_name = (
                    "assicurazione_euro"
                    if codice_servizio == "ASSIC"
                    else "contrassegno_euro"
                )

                # 🟢 Fallback robusto (SIMULAZIONE + POST + DB SAFE)
                valore_base = (
                    getattr(spedizione, attr_name, None)
                    or getattr(spedizione, "_valori_simulati", {}).get(attr_name)
                    or 0
                )

                valore_base = Decimal(str(valore_base))

                if valore_base <= 0:
                    continue

                if sup.calc_type == Supplemento.PERCENTAGE:
                    costo = valore_base * sup.valore / Decimal("100")
                    if minimo > 0:
                        costo = max(costo, minimo)

                elif sup.calc_type == Supplemento.FIXED:
                    costo = sup.valore

            # =========================================================
            # 🔵 ALTRI SUPPLEMENTI
            # =========================================================
            else:

                # se non selezionato e non simulazione → skip
                if (
                    ids_supplementi is None
                    and codice_servizio not in servizi_selezionati_codici
                ):
                    continue

                fattore = Decimal(len(pacchi)) if sup.applic_type == Supplemento.ACOLLO else Decimal("1")

                if sup.calc_type == Supplemento.FIXED:
                    costo = sup.valore * fattore

                elif sup.calc_type == Supplemento.PERCENTAGE:
                    costo = base_importo * sup.valore / Decimal("100")
                    if minimo > 0:
                        costo = max(costo, minimo)

            # =========================================================
            # 🟢 ACCUMULO
            # =========================================================
            if costo > 0:
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