from decimal import Decimal
from trasporti.models import Supplemento
from trasporti.services.base import TariffValidityService


class SupplementEngine:

    @staticmethod
    def calcola(spedizione, pacchi, base_importo, zona_corrente):  # 👈 Riceve la zona calcolata

        # 🟢 QUERY MANY-TO-MANY: Filtra i supplementi validi per la data
        # E che sono associati alla zona specifica della spedizione
        supplementi = TariffValidityService.filtra_validita(
            Supplemento.objects.filter(
                zone_tariffazione=zona_corrente  # 👈 Django controlla la tabella Many-to-Many in automatico!
            ).select_related('tipo_servizio').distinct(),  # .distinct() evita duplicati se ci sono incroci strani
            spedizione.data
        )

        totale = Decimal("0")
        dettaglio = []

        for sup in supplementi:
            fattore = Decimal("1")
            costo = Decimal("0")

            codice_servizio = sup.tipo_servizio.codice.upper() if sup.tipo_servizio else None

            # 🛑 SICUREZZA: Se il supplemento non è mappato a un TipoServizio, lo ignoriamo subito
            if not codice_servizio:
                continue

            # =================================================================
            # 🟢 1. CONTROLLO MAPPATO: ASSICURAZIONE ('ASSIC')
            # =================================================================
            if codice_servizio == "ASSIC":
                valore_assicurato = Decimal(str(spedizione.assicurazione_euro or 0))
                if valore_assicurato > Decimal("0"):
                    if sup.calc_type == Supplemento.PERCENTAGE:
                        costo = valore_assicurato * sup.valore / Decimal("100")
                    elif sup.calc_type == Supplemento.FIXED:
                        costo = sup.valore
                else:
                    continue

            # =================================================================
            # 🟢 2. CONTROLLO MAPPATO: CONTRASSEGNO ('CONTR')
            # =================================================================
            elif codice_servizio == "CONTR":
                valore_contrassegno = Decimal(str(spedizione.contrassegno_euro or 0))
                if valore_contrassegno > Decimal("0"):
                    if sup.calc_type == Supplemento.PERCENTAGE:
                        costo = valore_contrassegno * sup.valore / Decimal("100")
                    elif sup.calc_type == Supplemento.FIXED:
                        costo = sup.valore
                else:
                    continue

            # =================================================================
            # 🟡 3. TUTTI GLI ALTRI SUPPLEMENTI STANDARD (Es. ZTL, Isole...)
            # =================================================================
            else:
                # 🛑 CONTROLLO RESTRITTIVO: Passa SOLO se la spedizione ha richiesto questo codice
                ha_servizio = spedizione.servizi_richiesti.filter(codice__iexact=codice_servizio).exists()
                if not ha_servizio:
                    continue  # Se non è richiesto esplicitamente, viene scartato!

                # Calcolo matematico standard
                if sup.applic_type == Supplemento.ACOLLO:
                    fattore = Decimal(len(pacchi))

                if sup.calc_type == Supplemento.FIXED:
                    costo = sup.valore * fattore
                elif sup.calc_type == Supplemento.PERCENTAGE:
                    costo = base_importo * sup.valore / Decimal("100")

            # =================================================================
            # Accumulo dei costi validi
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

        # 🛑 RIGUARDA QUI: Il return ora è fuori dal ciclo 'for', allineato correttamente!
        return {
            "totale": totale,
            "dettaglio": dettaglio
        }