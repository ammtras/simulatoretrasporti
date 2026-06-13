

from decimal import Decimal
from trasporti.models import Supplemento
from trasporti.services.base import TariffValidityService


class SupplementEngineBUG:

    @staticmethod
    def calcola(spedizione, pacchi, base_importo):
        """
        Calcola dinamicamente i supplementi basandosi sul TipoServizio associato.
        I codici attesi sono: 'assic' per Assicurazione e 'contr' per Contrassegno.
        """
        supplementi = TariffValidityService.filtra_validita(
            Supplemento.objects.filter(
                spedizioniere=spedizione.trasportatore_scelto
            ).select_related('tipo_servizio'),
            spedizione.data
        )

        totale = Decimal("0")
        dettaglio = []

        for sup in supplementi:
            fattore = Decimal("1")
            costo = Decimal("0")

            # Trasformiamo in MAIUSCOLO per evitare problemi di capitalizzazione (es. 'assic' -> 'ASSIC')
            codice_servizio = sup.tipo_servizio.codice.upper() if sup.tipo_servizio else "GENERICO"

            # =================================================================
            # 🟢 1. CONTROLLO MAPPATO: ASSICURAZIONE (Nuovo codice: 'assic')
            # =================================================================
            if codice_servizio == "ASSIC":  # 👈 Cambiato qui in 'ASSIC'
                valore_assicurato = Decimal(str(spedizione.assicurazione_euro or 0))
                if valore_assicurato > Decimal("0"):
                    if sup.calc_type == Supplemento.PERCENTAGE:
                        costo = valore_assicurato * sup.valore / Decimal("100")
                    elif sup.calc_type == Supplemento.FIXED:
                        costo = sup.valore
                else:
                    continue  # Se l'utente non ha chiesto l'assicurazione, la salta

            # =================================================================
            # 🟢 2. CONTROLLO MAPPATO: CONTRASSEGNO (Nuovo codice: 'contr')
            # =================================================================
            elif codice_servizio == "CONTR":  # 👈 Cambiato qui in 'CONTR'
                valore_contrassegno = Decimal(str(spedizione.contrassegno_euro or 0))
                if valore_contrassegno > Decimal("0"):
                    if sup.calc_type == Supplemento.PERCENTAGE:
                        costo = valore_contrassegno * sup.valore / Decimal("100")
                    elif sup.calc_type == Supplemento.FIXED:
                        costo = sup.valore
                else:
                    continue  # Se l'utente non ha chiesto il contrassegno, lo salta

            # =================================================================
            # 🟡 3. ALTRI SUPPLEMENTI (ZTL, Località Disagiate, ecc.)
            # =================================================================
            else:
                # Controlliamo i servizi accessori solo se non è un supplemento generico del corriere
                if codice_servizio != "GENERICO":
                    # Il codice nel DB (es. 'ztl') deve corrispondere a quello chiesto dalla spedizione
                    ha_servizio = spedizione.servizi_richiesti.filter(codice__iexact=codice_servizio).exists()
                    if not ha_servizio:
                        continue

                        # Calcolo standard per gli altri supplementi
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

        return {
            "totale": totale,
            "dettaglio": dettaglio
        }



class SupplementEngine:

    @staticmethod
    def calcola(spedizione, pacchi, base_importo):
        """
        Calcola i supplementi. Se un supplemento non è mappato o non è
        esplicitamente richiesto dalla spedizione, viene IGNORATO.
        """
        supplementi = TariffValidityService.filtra_validita(
            Supplemento.objects.filter(
                spedizioniere=spedizione.trasportatore_scelto
            ).select_related('tipo_servizio'),
            spedizione.data
        )

        totale = Decimal("0")
        dettaglio = []

        for sup in supplementi:
            fattore = Decimal("1")
            costo = Decimal("0")

            # Se manca la mappatura, assegniamo una stringa vuota o None
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

        return {
            "totale": totale,
            "dettaglio": dettaglio
        }