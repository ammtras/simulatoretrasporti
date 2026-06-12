from trasporti.models import Zona_spedizioniere, Scaglione, OverflowTariff
from decimal import Decimal
from math import ceil
from django.db.models import Q
from trasporti.services.base import TariffValidityService
from trasporti.services.supplement_engine import SupplementEngine
from trasporti.services.fuel_engine import FuelEngine
from trasporti.services.detail_renderer import DetailRenderer

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
    def calcolaxxx(spedizione, pacchi):

        zona_gls = GLSService.get_zona_gls(spedizione)

        if not zona_gls:
            return {
                "prezzo": Decimal("0"),
                "dettaglio": {
                    "peso_reale": None,
                    "peso_volume": None,
                    "peso_tassabile": None,
                    "formula": "zona non disponibile",
                    "scaglione": None,
                    "overflow": None
                }
            }

        #peso_tassabile = GLSService._peso_tassabile(pacchi, zona_gls)
        dettaglio = GLSService.dettaglio_calcolo_preventivo(pacchi, zona_gls)
        peso_tassabile = dettaglio["peso_tassabile"]


        if zona_gls.spedizioniere.tipo_tariffazione == "scaglioni":
            return GLSService._scaglioni(peso_tassabile, zona_gls, dettaglio, spedizione, pacchi)


        return GLSService._a_collo(pacchi, zona_gls)

    @staticmethod
    def calcola(spedizione, pacchi):

        zona_gls = GLSService.get_zona_gls(spedizione)

        if not zona_gls:
            return {
                "prezzo": Decimal("0"),
                "dettaglio": {
                    "peso_reale": None,
                    "peso_volume": None,
                    "peso_tassabile": None,
                    "formula": "zona non disponibile",
                    "scaglione": None,
                    "overflow": None
                }
            }

        dettaglio = GLSService.dettaglio_calcolo_preventivo(
            pacchi,
            zona_gls
        )

        peso_tassabile = dettaglio["peso_tassabile"]

        context = {
            "spedizione": spedizione,
            "pacchi": pacchi,
            "zona": zona_gls,
            "peso_tassabile": peso_tassabile,
            "dettaglio": dettaglio,
        }

        if zona_gls.spedizioniere.tipo_tariffazione == "scaglioni":
            return GLSService._scaglioni(context)

        return GLSService._a_collo(pacchi, zona_gls)


    # =========================
    # 🟢 SCAGLIONI
    # =========================



    @staticmethod
    def _scaglioniFUNZIA(context):

        spedizione = context["spedizione"]
        pacchi = context["pacchi"]
        zona_gls = context["zona"]
        peso_tassabile = context["peso_tassabile"]
        dettaglio = context["dettaglio"]

        scaglioni = TariffValidityService.filtra_validita(
            Scaglione.objects.filter(zona_spedizioniere=zona_gls),
            spedizione.data
        ).order_by("min_weight")

        scaglione = scaglioni.filter(
            min_weight__lte=peso_tassabile
        ).filter(
            Q(max_weight__gte=peso_tassabile) | Q(max_weight__isnull=True)
        ).first()

        if not scaglione:
            scaglione = scaglioni.last()

        if not scaglione:
            return {
                "prezzo": Decimal("0"),
                "dettaglio": {"error": "no scaglione"}
            }

        prezzo = scaglione.price
        soglia = scaglione.max_weight or scaglione.min_weight

        extra_kg = Decimal("0")
        steps = 0
        costo_overflow = Decimal("0")

        if peso_tassabile > soglia:

            extra_kg = peso_tassabile - soglia

            overflow = TariffValidityService.filtra_validita(
                OverflowTariff.objects.filter(zona_spedizioniere=zona_gls),
                spedizione.data
            ).first()

            if overflow:
                steps = ceil(extra_kg / overflow.step_kg)
                costo_overflow = steps * overflow.price_per_step

        pre_base = prezzo + costo_overflow

        # 1. Il SupplementEngine calcola i supplementi dal DB
        supp = SupplementEngine.calcola(
            spedizione,
            pacchi,
            pre_base
        )

        # 🟢 PULIZIA CHIRURGICA DEI SUPPLEMENTI
        supplementi_puliti = []
        totale_supplementi_con_fuel = Decimal("0")
        totale_supplementi_senza_fuel = Decimal("0")

        for s in supp.get("dettaglio", []):
            nome_supp = s.get('nome', '').lower()
            costo_supp = Decimal(str(s.get("costo", 0)))

            if "fuel" in nome_supp:
                continue  # Saltiamo il fuel storico del DB

            supplementi_puliti.append(s)

            if s.get("applica_fuel") is True or s.get("applica fuel") is True:
                totale_supplementi_con_fuel += costo_supp
            else:
                totale_supplementi_senza_fuel += costo_supp

        # 2. CHIAMATA AL FUEL ENGINE UFFICIALE
        fuel = FuelEngine.calcola(
            spedizione,
            pre_base,
            supplementi_puliti
        )

        costo_fuel_calcolato = fuel["totale"]

        # 3. CALCOLO PREZZO FINALE
        prezzo_finale = pre_base + totale_supplementi_con_fuel + costo_fuel_calcolato + totale_supplementi_senza_fuel

        # Scaglione testo con l'importo in grassetto perché si somma al totale
        scaglione_testo = f"da {scaglione.min_weight} a {scaglione.max_weight or '∞'} kg – <b>€ {pre_base:.2f}</b>"

        # =====================================================================
        # 🟢 NUOVA LOGICA DI FORMATTAZIONE ESTETICA E GRASSETTI
        # =====================================================================
        lista_supp_con_fuel = []
        lista_supp_senza_fuel = []

        contatore_con_fuel = 1
        contatore_senza_fuel = 1

        # Ciclo sui supplementi reali (es. ZTL)
        for s in supplementi_puliti:
            costo = Decimal(str(s.get("costo", 0)))
            if costo >= Decimal("0.01"):
                if s.get("applica_fuel") is True or s.get("applica fuel") is True:
                    # Voce numerata, importo finale in grassetto
                    lista_supp_con_fuel.append(f"{contatore_con_fuel}. {s.get('nome')}: <b>€ {costo:.2f}</b>")
                    contatore_con_fuel += 1
                else:
                    # Voce numerata, importo finale in grassetto
                    lista_supp_senza_fuel.append(f"{contatore_senza_fuel}. {s.get('nome')}: <b>€ {costo:.2f}</b>")
                    contatore_senza_fuel += 1

        # Ciclo sul carburante ufficiale del FuelEngine
        for f in fuel.get("dettaglio", []):
            costo = Decimal(str(f.get("costo", 0)))
            if costo >= Decimal("0.01"):
                stringa_fuel = f"{f.get('nome')}"
                if f.get('percentuale'):
                    stringa_fuel += f" ({f.get('percentuale')}%)"

                # 🛑 SENZA NUMERO DAVANTI e con importo in grassetto
                lista_supp_con_fuel.append(f"{stringa_fuel}: <b>€ {costo:.2f}</b>")

        stringa_supp_con_fuel = "<br>".join(lista_supp_con_fuel) if lista_supp_con_fuel else "Nessuno"
        stringa_supp_senza_fuel = "<br>".join(lista_supp_senza_fuel) if lista_supp_senza_fuel else "Nessuno"

        # === 4. COSTRUZIONE STRUTTURA PER IL TEMPLATE ===
        items_ordinati = [
            {"label": "Peso tassabile", "value": f"{peso_tassabile:.2f} kg"},
            {"label": "Peso reale", "value": f"{dettaglio['peso_reale']:.2f} kg"},
            {"label": "Peso volume", "value": f"{dettaglio['peso_volume']:.2f} kg"},
            {"label": "Scaglione", "value": scaglione_testo, "is_html": True},
            # Aggiunto is_html per il grassetto dello scaglione
            {"label": "Supplementi con fuel applicati", "value": stringa_supp_con_fuel, "is_html": True},
            {"label": "Supplementi senza fuel applicati", "value": stringa_supp_senza_fuel, "is_html": True},
            {"label": "Totale preventivo", "value": f"<b>€ {prezzo_finale:.2f}</b>", "is_total": True, "is_html": True}
        ]

        return {
            "prezzo": prezzo_finale,
            "dettaglio": {
                "items": items_ordinati
            }
        }

    @staticmethod
    def _scaglioniXXX(context):

        spedizione = context["spedizione"]
        pacchi = context["pacchi"]
        zona_gls = context["zona"]
        peso_tassabile = context["peso_tassabile"]
        dettaglio = context["dettaglio"]

        scaglioni = TariffValidityService.filtra_validita(
            Scaglione.objects.filter(zona_spedizioniere=zona_gls),
            spedizione.data
        ).order_by("min_weight")

        scaglione = scaglioni.filter(
            min_weight__lte=peso_tassabile
        ).filter(
            Q(max_weight__gte=peso_tassabile) | Q(max_weight__isnull=True)
        ).first()

        if not scaglione:
            scaglione = scaglioni.last()

        if not scaglione:
            return {
                "prezzo": Decimal("0"),
                "dettaglio": {"error": "no scaglione"}
            }

        prezzo = scaglione.price
        soglia = scaglione.max_weight or scaglione.min_weight

        extra_kg = Decimal("0")
        steps = 0
        costo_overflow = Decimal("0")

        if peso_tassabile > soglia:

            extra_kg = peso_tassabile - soglia

            overflow = TariffValidityService.filtra_validita(
                OverflowTariff.objects.filter(zona_spedizioniere=zona_gls),
                spedizione.data
            ).first()

            if overflow:
                steps = ceil(extra_kg / overflow.step_kg)
                costo_overflow = steps * overflow.price_per_step

        pre_base = prezzo + costo_overflow

        # 1. Il SupplementEngine calcola i supplementi dal DB
        supp = SupplementEngine.calcola(
            spedizione,
            pacchi,
            pre_base
        )

        # PULIZIA CHIRURGICA DEI SUPPLEMENTI
        supplementi_puliti = []
        totale_supplementi_con_fuel = Decimal("0")
        totale_supplementi_senza_fuel = Decimal("0")

        for s in supp.get("dettaglio", []):
            nome_supp = s.get('nome', '').lower()
            costo_supp = Decimal(str(s.get("costo", 0)))

            if "fuel" in nome_supp:
                continue  # Saltiamo il fuel storico del DB

            supplementi_puliti.append(s)

            if s.get("applica_fuel") is True or s.get("applica fuel") is True:
                totale_supplementi_con_fuel += costo_supp
            else:
                totale_supplementi_senza_fuel += costo_supp

        # 2. CHIAMATA AL FUEL ENGINE UFFICIALE
        fuel = FuelEngine.calcola(
            spedizione,
            pre_base,
            supplementi_puliti
        )

        costo_fuel_calcolato = fuel["totale"]

        # 3. CALCOLO PREZZO FINALE
        prezzo_finale = pre_base + totale_supplementi_con_fuel + costo_fuel_calcolato + totale_supplementi_senza_fuel

        scaglione_testo = f"da {scaglione.min_weight} a {scaglione.max_weight or '∞'} kg – <b>€ {pre_base:.2f}</b>"

        # =====================================================================
        # 🟢 NUOVA LOGICA DI DISTRIBUZIONE E NUMERAZIONE DEI SUPPLEMENTI
        # =====================================================================
        lista_supp_con_fuel = []
        lista_supp_senza_fuel = []

        contatore_con_fuel = 1
        contatore_senza_fuel = 1

        # 1️⃣ INSERIAMO IL FUEL SURCHARGE COME VOCE N.1 DEI "SENZA FUEL"
        for f in fuel.get("dettaglio", []):
            costo = Decimal(str(f.get("costo", 0)))
            if costo >= Decimal("0.01"):
                stringa_fuel = f"{f.get('nome')}"
                if f.get('percentuale'):
                    stringa_fuel += f" ({f.get('percentuale')}%)"

                # Diventa la voce n.1 del blocco SENZA fuel
                lista_supp_senza_fuel.append(f"{contatore_senza_fuel}. {stringa_fuel}: <b>€ {costo:.2f}</b>")
                contatore_senza_fuel += 1

        # 2️⃣ CICLO SUI SUPPLEMENTI REALI (ZTL, Assicurazione, Contrassegno...)
        for s in supplementi_puliti:
            costo = Decimal(str(s.get("costo", 0)))
            if costo >= Decimal("0.01"):
                if s.get("applica_fuel") is True or s.get("applica fuel") is True:
                    # Va nei supplementi CON fuel (es. ZTL)
                    lista_supp_con_fuel.append(f"{contatore_con_fuel}. {s.get('nome')}: <b>€ {costo:.2f}</b>")
                    contatore_con_fuel += 1
                else:
                    # Va nei supplementi SENZA fuel (es. Assicurazione, Contrassegno) accodandosi al Fuel Surcharge
                    lista_supp_senza_fuel.append(f"{contatore_senza_fuel}. {s.get('nome')}: <b>€ {costo:.2f}</b>")
                    contatore_senza_fuel += 1

        stringa_supp_con_fuel = "<br>".join(lista_supp_con_fuel) if lista_supp_con_fuel else "Nessuno"
        stringa_supp_senza_fuel = "<br>".join(lista_supp_senza_fuel) if lista_supp_senza_fuel else "Nessuno"

        # === 4. COSTRUZIONE STRUTTURA PER IL TEMPLATE ===
        items_ordinati = [
            {"label": "Peso tassabile", "value": f"{peso_tassabile:.2f} kg"},
            {"label": "Peso reale", "value": f"{dettaglio['peso_reale']:.2f} kg"},
            {"label": "Peso volume", "value": f"{dettaglio['peso_volume']:.2f} kg"},
            {"label": "Scaglione", "value": scaglione_testo, "is_html": True},
            {"label": "Supplementi con fuel applicati", "value": stringa_supp_con_fuel, "is_html": True},
            {"label": "Supplementi senza fuel applicati", "value": stringa_supp_senza_fuel, "is_html": True},
            {"label": "Totale preventivo", "value": f"<b>€ {prezzo_finale:.2f}</b>", "is_total": True, "is_html": True}
        ]

        return {
            "prezzo": prezzo_finale,
            "dettaglio": {
                "items": items_ordinati
            }
        }

    @staticmethod
    def _scaglioni(context):

        spedizione = context["spedizione"]
        pacchi = context["pacchi"]
        zona_gls = context["zona"]
        peso_tassabile = context["peso_tassabile"]
        dettaglio = context["dettaglio"]

        scaglioni = TariffValidityService.filtra_validita(
            Scaglione.objects.filter(zona_spedizioniere=zona_gls),
            spedizione.data
        ).order_by("min_weight")

        scaglione = scaglioni.filter(
            min_weight__lte=peso_tassabile
        ).filter(
            Q(max_weight__gte=peso_tassabile) | Q(max_weight__isnull=True)
        ).first()

        if not scaglione:
            scaglione = scaglioni.last()

        if not scaglione:
            return {
                "prezzo": Decimal("0"),
                "dettaglio": {"error": "no scaglione"}
            }

        prezzo = scaglione.price
        soglia = scaglione.max_weight or scaglione.min_weight

        extra_kg = Decimal("0")
        steps = 0
        costo_overflow = Decimal("0")

        if peso_tassabile > soglia:

            extra_kg = peso_tassabile - soglia

            overflow = TariffValidityService.filtra_validita(
                OverflowTariff.objects.filter(zona_spedizioniere=zona_gls),
                spedizione.data
            ).first()

            if overflow:
                steps = ceil(extra_kg / overflow.step_kg)
                costo_overflow = steps * overflow.price_per_step

        pre_base = prezzo + costo_overflow

        # 1. Il SupplementEngine calcola i supplementi dal DB
        supp = SupplementEngine.calcola(
            spedizione,
            pacchi,
            pre_base
        )

        # PULIZIA CHIRURGICA DEI SUPPLEMENTI
        supplementi_puliti = []
        totale_supplementi_con_fuel = Decimal("0")
        totale_supplementi_senza_fuel = Decimal("0")

        for s in supp.get("dettaglio", []):
            nome_supp = s.get('nome', '').lower()
            costo_supp = Decimal(str(s.get("costo", 0)))

            if "fuel" in nome_supp:
                continue  # Saltiamo il fuel storico del DB

            supplementi_puliti.append(s)

            if s.get("applica_fuel") is True or s.get("applica fuel") is True:
                totale_supplementi_con_fuel += costo_supp
            else:
                totale_supplementi_senza_fuel += costo_supp

        # 2. CHIAMATA AL FUEL ENGINE UFFICIALE
        fuel = FuelEngine.calcola(
            spedizione,
            pre_base,
            supplementi_puliti
        )

        costo_fuel_calcolato = fuel["totale"]

        # 3. CALCOLO PREZZO FINALE
        prezzo_finale = pre_base + totale_supplementi_con_fuel + costo_fuel_calcolato + totale_supplementi_senza_fuel

        # 🟢 COSTRUZIONE DEL TESTO DELLO SCAGLIONE CON L'IDENTIFICATIVO STR() DEL MODEL
        nome_scaglione_completo = str(scaglione)
        scaglione_testo = f"{nome_scaglione_completo} – <b>€ {pre_base:.2f}</b>"

        # =====================================================================
        # LOGICA DI DISTRIBUZIONE E NUMERAZIONE DEI SUPPLEMENTI
        # =====================================================================
        lista_supp_con_fuel = []
        lista_supp_senza_fuel = []

        contatore_con_fuel = 1
        contatore_senza_fuel = 1

        # 1️⃣ INSERIAMO IL FUEL SURCHARGE COME VOCE N.1 DEI "SENZA FUEL"
        for f in fuel.get("dettaglio", []):
            costo = Decimal(str(f.get("costo", 0)))
            if costo >= Decimal("0.01"):
                stringa_fuel = f"{f.get('nome')}"
                if f.get('percentuale'):
                    stringa_fuel += f" ({f.get('percentuale')}%)"

                lista_supp_senza_fuel.append(f"{contatore_senza_fuel}. {stringa_fuel}: <b>€ {costo:.2f}</b>")
                contatore_senza_fuel += 1

        # 2️⃣ CICLO SUI SUPPLEMENTI REALI (ZTL, Assicurazione, Contrassegno...)
        for s in supplementi_puliti:
            costo = Decimal(str(s.get("costo", 0)))
            if costo >= Decimal("0.01"):
                if s.get("applica_fuel") is True or s.get("applica fuel") is True:
                    lista_supp_con_fuel.append(f"{contatore_con_fuel}. {s.get('nome')}: <b>€ {costo:.2f}</b>")
                    contatore_con_fuel += 1
                else:
                    lista_supp_senza_fuel.append(f"{contatore_senza_fuel}. {s.get('nome')}: <b>€ {costo:.2f}</b>")
                    contatore_senza_fuel += 1

        stringa_supp_con_fuel = "<br>".join(lista_supp_con_fuel) if lista_supp_con_fuel else "Nessuno"
        stringa_supp_senza_fuel = "<br>".join(lista_supp_senza_fuel) if lista_supp_senza_fuel else "Nessuno"

        # === 4. COSTRUZIONE STRUTTURA PER IL TEMPLATE ===
        items_ordinati = [
            {"label": "Peso tassabile", "value": f"{peso_tassabile:.2f} kg"},
            {"label": "Peso reale", "value": f"{dettaglio['peso_reale']:.2f} kg"},
            {"label": "Peso volume", "value": f"{dettaglio['peso_volume']:.2f} kg"},
            {"label": "Scaglione", "value": scaglione_testo, "is_html": True},
            {"label": "Supplementi con fuel applicati", "value": stringa_supp_con_fuel, "is_html": True},
            {"label": "Supplementi senza fuel applicati", "value": stringa_supp_senza_fuel, "is_html": True},
            {"label": "Totale preventivo", "value": f"<b>€ {prezzo_finale:.2f}</b>", "is_total": True, "is_html": True}
        ]

        return {
            "prezzo": prezzo_finale,
            "dettaglio": {
                "items": items_ordinati
            }
        }

    @staticmethod
    def _scaglioniFUNZIAMASENZAENGINE(context):

        spedizione = context["spedizione"]
        pacchi = context["pacchi"]
        zona_gls = context["zona"]
        peso_tassabile = context["peso_tassabile"]
        dettaglio = context["dettaglio"]

        scaglioni = TariffValidityService.filtra_validita(
            Scaglione.objects.filter(zona_spedizioniere=zona_gls),
            spedizione.data
        ).order_by("min_weight")

        scaglione = scaglioni.filter(
            min_weight__lte=peso_tassabile
        ).filter(
            Q(max_weight__gte=peso_tassabile) | Q(max_weight__isnull=True)
        ).first()

        if not scaglione:
            scaglione = scaglioni.last()

        if not scaglione:
            return {
                "prezzo": Decimal("0"),
                "dettaglio": {"error": "no scaglione"}
            }

        prezzo = scaglione.price
        soglia = scaglione.max_weight or scaglione.min_weight

        extra_kg = Decimal("0")
        steps = 0
        costo_overflow = Decimal("0")

        if peso_tassabile > soglia:

            extra_kg = peso_tassabile - soglia

            overflow = TariffValidityService.filtra_validita(
                OverflowTariff.objects.filter(zona_spedizioniere=zona_gls),
                spedizione.data
            ).first()

            if overflow:
                steps = ceil(extra_kg / overflow.step_kg)
                costo_overflow = steps * overflow.price_per_step

        pre_base = prezzo + costo_overflow

        # 1. Calcolo iniziale dei supplementi dal DB
        supp = SupplementEngine.calcola(
            spedizione,
            pacchi,
            pre_base
        )

        # 🟢 ESTRAZIONE DEI COSTI REALI (Escludendo qualsiasi traccia di fuel vecchio)
        costo_ztl = Decimal("0")
        costo_assicurazione = Decimal("0")
        costo_contrassegno = Decimal("0")

        for s in supp.get("dettaglio", []):
            nome_supp = s.get('nome', '').lower()
            costo_supp = Decimal(str(s.get("costo", 0)))

            if "fuel" in nome_supp:
                continue
            elif "ztl" in nome_supp:
                costo_ztl = costo_supp
            elif "assicuraz" in nome_supp:
                costo_assicurazione = costo_supp
            elif "contrassegn" in nome_supp:
                costo_contrassegno = costo_supp

        # Se per qualche motivo la ZTL dal DB non è 2.00, forziamo il valore corretto per sicurezza
        if costo_ztl == Decimal("0"):
            costo_ztl = Decimal("2.00")

        # 🟢 CALCOLO DIRETTO E MATEMATICO DEL FUEL SURCHARGE (18.50%)
        # Forziamo la formula esatta richiesta: (6.50 + 2.00) * 18.50%
        percentuale_fuel = Decimal("18.50")
        costo_fuel_reale = (pre_base + costo_ztl) * (percentuale_fuel / Decimal("100"))

        # Arrotondiamo a 2 cifre decimali (es. 1.5725 -> 1.57)
        costo_fuel_reale = costo_fuel_reale.quantize(Decimal("0.01"))

        # 🟢 PREZZO FINALE MATEMATICO
        prezzo_finale = pre_base + costo_ztl + costo_fuel_reale + costo_assicurazione + costo_contrassegno

        scaglione_testo = f"da {scaglione.min_weight} a {scaglione.max_weight or '∞'} kg – € {pre_base:.2f}"

        # =====================================================================
        # 🟢 COSTRUZIONE GRAFICA PULITA E NUMERATA PER IL TEMPLATE
        # =====================================================================
        lista_supp_con_fuel = []
        lista_supp_senza_fuel = []

        # Blocco 1: Con Fuel
        lista_supp_con_fuel.append(f"1. ZTL: € {costo_ztl:.2f}")
        lista_supp_con_fuel.append(f"2. Fuel Surcharge ({percentuale_fuel:.2f}%): € {costo_fuel_reale:.2f}")

        # Blocco 2: Senza Fuel (mostrati solo se attivi)
        contatore_senza_fuel = 1
        if costo_assicurazione >= Decimal("0.01"):
            lista_supp_senza_fuel.append(f"{contatore_senza_fuel}. Assicurazione: € {costo_assicurazione:.2f}")
            contatore_senza_fuel += 1

        if costo_contrassegno >= Decimal("0.01"):
            lista_supp_senza_fuel.append(f"{contatore_senza_fuel}. Contrassegno: € {costo_contrassegno:.2f}")
            contatore_senza_fuel += 1

        stringa_supp_con_fuel = "<br>".join(lista_supp_con_fuel) if lista_supp_con_fuel else "Nessuno"
        stringa_supp_senza_fuel = "<br>".join(lista_supp_senza_fuel) if lista_supp_senza_fuel else "Nessuno"

        # === 4. COSTRUZIONE STRUTTURA PER IL TEMPLATE ===
        items_ordinati = [
            {"label": "Peso tassabile", "value": f"{peso_tassabile:.2f} kg"},
            {"label": "Peso reale", "value": f"{dettaglio['peso_reale']:.2f} kg"},
            {"label": "Peso volume", "value": f"{dettaglio['peso_volume']:.2f} kg"},
            {"label": "Scaglione", "value": scaglione_testo},
            {"label": "Supplementi con fuel applicati", "value": stringa_supp_con_fuel, "is_html": True},
            {"label": "Supplementi senza fuel applicati", "value": stringa_supp_senza_fuel, "is_html": True},
            {"label": "Totale preventivo", "value": f"€ {prezzo_finale:.2f}", "is_total": True}
        ]

        return {
            "prezzo": prezzo_finale,
            "dettaglio": {
                "items": items_ordinati
            }
        }


    # =========================
    # 🟢 A COLLO
    # =========================
    @staticmethod
    def _a_collo(pacchi, zona_gls):

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

        prezzo = peso_tassabile * Decimal("1.2")

        return {
            "prezzo": prezzo,
            "dettaglio": {
                "peso_reale": peso_reale,
                "peso_volume": peso_volume,
                "peso_tassabile": peso_tassabile,
                "formula": f"max({peso_reale}, {peso_volume}) = {peso_tassabile}",
                "scaglione": None,
                "overflow" : None
            }
        }

