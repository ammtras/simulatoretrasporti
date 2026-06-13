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
    def _scaglioni(context):
        spedizione = context["spedizione"]
        pacchi = context["pacchi"]
        zona_gls = context["zona"]
        peso_tassabile = context["peso_tassabile"]
        dettaglio = context["dettaglio"]

        # 1. Calcolo tariffa base
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
            return {"prezzo": Decimal("0"), "dettaglio": {"error": "no scaglione"}}

        prezzo = scaglione.price
        soglia = scaglione.max_weight or scaglione.min_weight

        extra_kg = Decimal("0")
        costo_overflow = Decimal("0")

        if peso_tassabile > soglia:
            extra_kg = peso_tassabile - soglia
            overflow = TariffValidityService.filtra_validita(
                OverflowTariff.objects.filter(zona_spedizioniere=zona_gls),
                spedizione.data
            ).first()
            if overflow:
                costo_overflow = ceil(extra_kg / overflow.step_kg) * overflow.price_per_step

        pre_base = prezzo + costo_overflow

        # 2. CHIAMATA AL SUPPLEMENT ENGINE (con gestione simulazione)
        ids_supplementi = getattr(spedizione, '_supplementi_simulati', [])

        supp = SupplementEngine.calcola(
            spedizione,
            pacchi,
            pre_base,
            zona_gls,
            ids_supplementi=ids_supplementi
        )

        # 3. Logica Fuel e Totali
        supplementi_puliti = []
        totale_supplementi_con_fuel = Decimal("0")
        totale_supplementi_senza_fuel = Decimal("0")

        for s in supp.get("dettaglio", []):
            nome_supp = s.get('nome', '').lower()
            costo_supp = Decimal(str(s.get("costo", 0)))
            if "fuel" in nome_supp:
                continue
            supplementi_puliti.append(s)
            if s.get("applica_fuel") is True or s.get("applica fuel") is True:
                totale_supplementi_con_fuel += costo_supp
            else:
                totale_supplementi_senza_fuel += costo_supp

        fuel = FuelEngine.calcola(spedizione, pre_base, supplementi_puliti, zona_gls)
        costo_fuel_calcolato = fuel["totale"]
        prezzo_finale = pre_base + totale_supplementi_con_fuel + costo_fuel_calcolato + totale_supplementi_senza_fuel

        # 4. Preparazione output
        nome_scaglione_completo = str(scaglione)
        scaglione_testo = f"{nome_scaglione_completo} – <b>€ {pre_base:.2f}</b>"

        lista_supp_con_fuel = []
        lista_supp_senza_fuel = []
        contatore_con_fuel = 1
        contatore_senza_fuel = 1

        for f in fuel.get("dettaglio", []):
            costo = Decimal(str(f.get("costo", 0)))
            if costo >= Decimal("0.01"):
                stringa_fuel = f"{f.get('nome')}"
                if f.get('percentuale'):
                    stringa_fuel += f" ({f.get('percentuale')}%)"
                lista_supp_senza_fuel.append(f"{contatore_senza_fuel}. {stringa_fuel}: <b>€ {costo:.2f}</b>")
                contatore_senza_fuel += 1

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
            "dettaglio": {"items": items_ordinati}
        }

    @staticmethod
    def _a_collo(pacchi, zona_gls):
        # ... (tutto il calcolo del peso rimane uguale) ...
        peso_reale = ...
        peso_tassabile = max(peso_reale, peso_volume)
        prezzo = peso_tassabile * Decimal("1.2")

        # 🟢 NUOVO: Costruiamo gli items come nello scaglione
        items_ordinati = [
            {"label": "Peso tassabile", "value": f"{peso_tassabile:.2f} kg"},
            {"label": "Prezzo base a collo", "value": f"<b>€ {prezzo:.2f}</b>", "is_total": True, "is_html": True}
        ]

        return {
            "prezzo": prezzo,
            "dettaglio": {
                "items": items_ordinati  # Ora è identico allo scaglione!
            }
        }

