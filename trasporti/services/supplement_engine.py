from decimal import Decimal
from trasporti.models import Supplemento
from trasporti.services.base import TariffValidityService


class SupplementEnginexxx:

    @staticmethod
    def calcola(spedizione, pacchi, base_importo):
        """
        Calcola tutti i supplementi per una spedizione.
        Ritorna:
            {
                "totale": Decimal,
                "dettaglio": [...]
            }
        """

        supplementi = TariffValidityService.filtra_validita(
            Supplemento.objects.filter(
                spedizioniere=spedizione.trasportatore_scelto
            ),
            spedizione.data
        )

        totale = Decimal("0")

        dettaglio = []

        for sup in supplementi:

            fattore = Decimal("1")

            # =========================
            # applicazione (spedizione / collo)
            # =========================
            if sup.applic_type == Supplemento.ACOLLO:
                fattore = Decimal(len(pacchi))

            # =========================
            # calcolo base
            # =========================
            if sup.calc_type == Supplemento.FIXED:
                costo = sup.valore * fattore

            elif sup.calc_type == Supplemento.PERCENTAGE:
                costo = base_importo * sup.valore / Decimal("100")

            else:
                costo = Decimal("0")

            # =========================
            # accumulo
            # =========================
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


class SupplementEngineyyy:

    @staticmethod
    def calcola(spedizione, pacchi, base_importo):
        """
        Calcola tutti i supplementi per una spedizione.
        Ritorna:
            {
                "totale": Decimal,
                "dettaglio": [...]
            }
        """

        supplementi = TariffValidityService.filtra_validita(
            Supplemento.objects.filter(
                spedizioniere=spedizione.trasportatore_scelto
            ),
            spedizione.data
        )

        totale = Decimal("0")
        dettaglio = []

        for sup in supplementi:
            fattore = Decimal("1")

            # =========================
            # applicazione (spedizione / collo)
            # =========================
            if sup.applic_type == Supplemento.ACOLLO:
                fattore = Decimal(len(pacchi))

            # =========================
            # calcolo base
            # =========================
            if sup.calc_type == Supplemento.FIXED:
                costo = sup.valore * fattore

            elif sup.calc_type == Supplemento.PERCENTAGE:
                nome_minuscolo = sup.nome.lower()

                # 🟢 1. ASSICURAZIONE: Cerca la parola chiave nel nome del supplemento
                if "assicuraz" in nome_minuscolo:
                    # Recupera l'attributo 'valore_assicurato' dalla spedizione (default 0 se non presente o None)
                    valore_da_calcolare = Decimal(str(getattr(spedizione, "valore_assicurato", 0) or 0))
                    costo = valore_da_calcolare * sup.valore / Decimal("100")

                # 🟢 2. CONTRASSEGNO: Cerca la parola chiave nel nome del supplemento
                elif "contrassegn" in nome_minuscolo:
                    # Recupera l'attributo 'valore_contrassegno' dalla spedizione (default 0 se non presente o None)
                    valore_da_calcolare = Decimal(str(getattr(spedizione, "valore_contrassegno", 0) or 0))
                    costo = valore_da_calcolare * sup.valore / Decimal("100")

                # 🟡 3. Altri supplementi percentuali generici (tipo il fuel se calcolato qui o altro)
                else:
                    costo = base_importo * sup.valore / Decimal("100")

                # Nota: l'applicazione percentuale non usa solitamente il 'fattore' (numero colli)
                # a meno che il contratto non lo specifichi, ma se servisse puoi moltiplicare per fattore.

            else:
                costo = Decimal("0")

            # =========================
            # accumulo
            # =========================
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
        Calcola tutti i supplementi per una spedizione.
        Ritorna:
            {
                "totale": Decimal,
                "dettaglio": [...]
            }
        """

        supplementi = TariffValidityService.filtra_validita(
            Supplemento.objects.filter(
                spedizioniere=spedizione.trasportatore_scelto
            ),
            spedizione.data
        )

        totale = Decimal("0")
        dettaglio = []

        for sup in supplementi:
            fattore = Decimal("1")
            nome_minuscolo = sup.nome.lower()

            # Inizializziamo il costo a 0. Cambierà solo se soddisfa i requisiti.
            costo = Decimal("0")

            # =================================================================
            # 🟢 1. CONTROLLO SPECIALE: ASSICURAZIONE
            # =================================================================
            if "assicuraz" in nome_minuscolo:
                valore_assicurato = Decimal(str(spedizione.assicurazione_euro or 0))
                # Calcoliamo il supplemento SOLO se il cliente ha inserito un valore > 0
                if valore_assicurato > Decimal("0"):
                    if sup.calc_type == Supplemento.PERCENTAGE:
                        costo = valore_assicurato * sup.valore / Decimal("100")
                    elif sup.calc_type == Supplemento.FIXED:
                        costo = sup.valore
                else:
                    # Se il valore è 0, saltiamo l'aggiunta di questo supplemento al preventivo
                    continue

            # =================================================================
            # 🟢 2. CONTROLLO SPECIALE: CONTRASSEGNO
            # =================================================================
            elif "contrassegn" in nome_minuscolo:
                valore_contrassegno = Decimal(str(spedizione.contrassegno_euro or 0))
                # Calcoliamo il supplemento SOLO se il contrassegno è richiesto (> 0)
                if valore_contrassegno > Decimal("0"):
                    if sup.calc_type == Supplemento.PERCENTAGE:
                        costo = valore_contrassegno * sup.valore / Decimal("100")
                    elif sup.calc_type == Supplemento.FIXED:
                        costo = sup.valore
                else:
                    # Se il valore è 0, saltiamo il contrassegno
                    continue

            # =================================================================
            # 🟡 3. TUTTI GLI ALTRI SUPPLEMENTI STANDARD (Es. ZTL, Isole, Sponde...)
            # =================================================================
            else:
                if sup.applic_type == Supplemento.ACOLLO:
                    fattore = Decimal(len(pacchi))

                if sup.calc_type == Supplemento.FIXED:
                    costo = sup.valore * fattore
                elif sup.calc_type == Supplemento.PERCENTAGE:
                    costo = base_importo * sup.valore / Decimal("100")

            # =========================
            # accumulo (Solo se il costo è maggiore di 0)
            # =========================
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