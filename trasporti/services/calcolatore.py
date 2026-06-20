from trasporti.models import Zona_spedizioniere, Scaglione, OverflowTariff
from decimal import Decimal
from math import ceil
from django.db.models import Q
from trasporti.services.base import TariffValidityService
from trasporti.services.supplement_engine import SupplementEngine
from trasporti.services.fuel_engine import FuelEngine
from trasporti.models import Tariffa_colli, Supplemento
from trasporti.services.detail_renderer import DetailRendererService

class CalcolatriceService:


    @staticmethod
    def get_zona(spedizione):
        return getattr(spedizione, "zona_tariffazione_spedizioniere", None)


    @staticmethod
    def dettaglio_calcolo_preventivo(pacchi, zona_get):
        peso_reale = sum(Decimal(p.get("peso_kg") or 0) for p in pacchi if p)

        # Calcolo volumetrico esplicito
        volume_totale_cm3 = sum(
            Decimal(p.get("altezza_cm") or 0) * Decimal(p.get("larghezza_cm") or 0) * Decimal(
                p.get("profondita_cm") or 0)
            for p in pacchi if p
        )

        # 2. Otteniamo il divisore basandoci sul peso reale (o come da tua logica)
        divisore_finale = zona_get.get_divisore_effettivo(peso_reale, volume_totale_cm3)

        # 3. Calcolo peso volume
        peso_volume = volume_totale_cm3 / Decimal(divisore_finale)
        peso_tassabile = max(peso_reale, peso_volume)

        print(f"DEBUG_CALCOLO: Vol={volume_totale_cm3}, Div={divisore_finale}, PV={peso_volume}")

        return {
            "peso_reale": peso_reale,
            "peso_volume": peso_volume,
            "peso_tassabile": peso_tassabile,
            "volume_cm3": volume_totale_cm3,
            "divisore": divisore_finale,
            "formula": f"max({peso_reale}, {peso_volume}) = {peso_tassabile}"
        }

    @staticmethod
    def calcola(spedizione, pacchi):

        zona_get = CalcolatriceService.get_zona(spedizione)

        if not zona_get:
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

        dettaglio = CalcolatriceService.dettaglio_calcolo_preventivo(
            pacchi,
            zona_get
        )

        peso_tassabile = dettaglio["peso_tassabile"]

        # 🟢 LOGICA: Recupero ID supplementi (DB se esiste, Simulazione se nuova)
        if spedizione.pk:
            # Se la spedizione è già salvata, prendiamo i supplementi dal DB
            ids_supplementi = list(spedizione.supplementi.values_list('id', flat=True))
        else:
            # Se è in fase di simulazione (non ha ancora PK), prendiamo quelli iniettati
            ids_supplementi = getattr(spedizione, '_supplementi_simulati', [])

        context = {
            "spedizione": spedizione,
            "pacchi": pacchi,
            "zona": zona_get,
            "peso_tassabile": peso_tassabile,
            "dettaglio": dettaglio,
            "ids_supplementi": ids_supplementi
        }

        if zona_get.spedizioniere.tipo_tariffazione == "scaglioni":
            return CalcolatriceService._scaglioni(context)

        return CalcolatriceService._a_collo(context)


    @staticmethod
    def _scaglioni(context):

        print("=== INIZIO _SCAGLIONI ===")
        print("context peso_tassabile:", context["peso_tassabile"])

        peso_tassabile = context["peso_tassabile"]

        print("peso_tassabile locale:", peso_tassabile)

        spedizione = context["spedizione"]
        pacchi = context["pacchi"]
        zona_get = context["zona"]
        peso_tassabile = context["peso_tassabile"]
        dettaglio = context["dettaglio"]
        ids_supplementi = context.get("ids_supplementi", [])




        # 1. Calcolo tariffa base
        scaglioni = TariffValidityService.filtra_validita(
            Scaglione.objects.filter(zona_spedizioniere=zona_get),
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

        print(f'peso tassabile: {peso_tassabile}')


        if peso_tassabile > soglia:
            extra_kg = peso_tassabile - soglia
            overflow = TariffValidityService.filtra_validita(
                OverflowTariff.objects.filter(zona_spedizioniere=zona_get),
                spedizione.data
            ).first()
            if overflow:
                costo_overflow = ceil(extra_kg / overflow.step_kg) * overflow.price_per_step

        pre_base = prezzo + costo_overflow
        print(f'DDEEBBUUGG prezzo: {prezzo}')
        print(f'DDEEBBUUGG costo_overflow: {costo_overflow}')
        print(f'DDEEBBUUGG prebase: {pre_base}')

        # 2. CHIAMATA AL SUPPLEMENT ENGINE
        supp = SupplementEngine.calcola_supplementi(
            spedizione,
            pacchi,
            pre_base,
            zona_get,
            ids_supplementi=ids_supplementi,
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

        fuel = FuelEngine.calcola(spedizione, pre_base, supplementi_puliti, zona_get)
        costo_fuel_calcolato = fuel["totale"]
        subtotale_euro_imponibile = pre_base + totale_supplementi_con_fuel + costo_fuel_calcolato + totale_supplementi_senza_fuel
        imponibile_senza_fuel = pre_base + totale_supplementi_con_fuel + totale_supplementi_senza_fuel
        totale_imponibile_con_fuel = pre_base + totale_supplementi_con_fuel + totale_supplementi_senza_fuel + costo_fuel_calcolato
        totale_imponibile_senza_fuel = pre_base + totale_supplementi_con_fuel + totale_supplementi_senza_fuel


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

            # Verifica i nomi delle chiavi esatte che arrivano dal form
            # Spesso arrivano come 'altezza', 'larghezza' o 'profondita' senza '_cm'
        # 🟢 AGGIUNTA DEL DIVISORE NELLA STRINGA
        # Costruiamo la stringa formattata come hai chiesto: cm3 / divisore
        volume_cm3 = dettaglio.get('volume_cm3', 0)
        divisore = dettaglio.get('divisore', 1)
        formula_volume = f"{volume_cm3:.0f} cm³ / {divisore}"
        #subtotale_euro_imponibile
        iva_euro = Decimal(subtotale_euro_imponibile * Decimal(0.22))
        totale_con_iva_euro = Decimal(subtotale_euro_imponibile * Decimal(1.22))

        items_ordinati = [
            {"label": "Peso tassabile", "value": f"{peso_tassabile:.2f} kg"},
            {"label": "Peso reale", "value": f"{dettaglio['peso_reale']:.2f} kg"},
            {"label": "Peso volume", "value": f"{dettaglio['peso_volume']:.2f} kg ({formula_volume})"},
            {"label": "Scaglione", "value": scaglione_testo, "is_html": True},
            {"label": "Supplementi con fuel applicati", "value": stringa_supp_con_fuel, "is_html": True},
            {"label": "Supplementi senza fuel applicati", "value": stringa_supp_senza_fuel, "is_html": True},
            {"label": "Subtotale Euro imponibile", "value": f"<b>€ {subtotale_euro_imponibile:.2f}</b>", "is_html": True},
            {"label": "di cui imponibile senza fuel", "value": f"<b>€ {imponibile_senza_fuel:.2f}</b>",  "is_html": True},
            {"label": "IVA", "value": f"<b>€ {iva_euro:.2f}</b>", "is_html": True},
            {"label": "TOTALE IVA INCLUSA", "value": f"<b>€ {totale_con_iva_euro:.2f}</b>", "is_total": True,
             "is_html": True},
        ]

        print(totale_imponibile_con_fuel)
        print(totale_imponibile_senza_fuel)
        return {
            "totale_con_iva_euro": totale_con_iva_euro,
            "dettaglio": {"items": items_ordinati},
            "totale_imponibile_con_fuel": totale_imponibile_con_fuel,
            "totale_imponibile_senza_fuel": totale_imponibile_senza_fuel,
        }




    def _a_collo(context):
        spedizione = context["spedizione"]
        pacchi = context["pacchi"]
        zona_get = context["zona"]
        peso_tassabile = context["peso_tassabile"]
        dettaglio = context["dettaglio"]
        ids_supplementi = context.get("ids_supplementi", [])

        numero_colli = len(pacchi)

        print(
            f"sono entrata nella funzione A COLLO : "
            f"il totale colli della spedizione è {numero_colli}"
        )

        '''print(f"zona_get = {zona_get}")
        print(f"zona_get.id = {zona_get.id}")

        print("\n=== TUTTE LE TARIFFE COLLI DEL DB ===")
        for t in Tariffa_colli.objects.all():
            print(
                f"id={t.id} | "
                f"zona_spedizioniere_id={t.zona_spedizioniere_id} | "
                f"zona={t.zona_spedizioniere} | "
                f"da={t.colli_quantità_da} | "
                f"a={t.colli_quantità_a} | "
                f"costo={t.costo_euro}"
            )'''

        tariffe_colli = Tariffa_colli.objects.filter(
            zona_spedizioniere=zona_get
        )

        print("\n=== TARIFFE COLLI TROVATE PER LA ZONA ===")
        print(tariffe_colli)
        print(f"count = {tariffe_colli.count()}")

        for t in tariffe_colli:
            print(
                f"id={t.id} | "
                f"da={t.colli_quantità_da} | "
                f"a={t.colli_quantità_a} | "
                f"costo={t.costo_euro}"
            )

        tariffe_colli = TariffValidityService.filtra_validita(
            tariffe_colli,
            spedizione.data
        ).order_by("colli_quantità_da")

        print("\n=== DOPO FILTRO VALIDITÀ ===")
        print(tariffe_colli)
        print(f"count = {tariffe_colli.count()}")

        tariffa_collo = tariffe_colli.filter(
            colli_quantità_da__lte=numero_colli,
            colli_quantità_a__gte=numero_colli
        ).first()

        print(f"\n2 tariffa_collo trovata = {tariffa_collo}")

        if not tariffa_collo:
            print(f"NESSUNA tariffa trovata per {numero_colli} colli")

            return {
                "prezzo": Decimal("0"),
                "dettaglio": {
                    "error": "no tariffa colli"
                }
            }

        print(
            f"Tariffa selezionata: "
            f"{tariffa_collo.colli_quantità_da} - "
            f"{tariffa_collo.colli_quantità_a} "
            f"=> € {tariffa_collo.costo_euro}"
        )

        # 1. Prezzo base della tariffa a colli
        tariffa_a_collo = Decimal(str(tariffa_collo.costo_euro))
        pre_base_tariffa = Decimal(str(tariffa_collo.costo_euro))
        nolo = pre_base_tariffa * Decimal(numero_colli)



        pre_base = nolo

        # 2. Supplemento peso volume per collo > 45 kg
        divisore = Decimal(str(dettaglio.get("divisore", 1)))


        # supplemento cod SAHAN (Supplementi Additional Handling)
        supplemento_additional_handling = Decimal("0")
        dettaglio_supp_peso_volume = []
        dettaglio_supplemento_additional_handling = []


        for index, pacco in enumerate(pacchi, start=1):
            altezza = Decimal(str(pacco.get("altezza_cm", 0) or 0))
            larghezza = Decimal(str(pacco.get("larghezza_cm", 0) or 0))
            profondita = Decimal(str(pacco.get("profondita_cm", 0) or 0))

            volume_cm3_collo = altezza * larghezza * profondita
            peso_volume_collo = volume_cm3_collo / divisore
            circonferenza = ((altezza * 2) + (larghezza * 2)  + profondita)
            print(circonferenza)

            print(
                f"Collo {index}: "
                f"{altezza}x{larghezza}x{profondita} = "
                f"{volume_cm3_collo} cm³ / {divisore} = "
                f"{peso_volume_collo:.2f} kg volume"
            )

            if volume_cm3_collo > Decimal("169901"):
                supplemento_additional_handling += Decimal("10")

                dettaglio_supplemento_additional_handling.append({
                    "nome": f"Supplemento additional handling: il volume del pacco  {volume_cm3_collo} {index} > 169901 cm3",
                    "costo": Decimal("10.00"),
                    "peso_volume_collo": peso_volume_collo,
                    "applica_fuel": True,
                })

                print(f" A Supplemento peso volume applicato al collo {index}: € 10.00")

            elif circonferenza > 266:
                supplemento_additional_handling += Decimal("10")

                dettaglio_supplemento_additional_handling.append({
                    "nome": f"Supplemento additional handling: la circonferenza del pacco  {circonferenza} {index} > 266 cm",
                    "costo": Decimal("10.00"),
                    "peso_volume_collo": peso_volume_collo,
                    "applica_fuel": True,
                })

                print(f" B Supplemento peso volume applicato al collo circonferenza{index}: € 10.00")

            elif max(larghezza, altezza, profondita) > 121:
                supplemento_additional_handling += Decimal("10")

                dettaglio_supplemento_additional_handling.append({
                    "nome": f"Supplemento additional handling: lato max   {index} > 121 cm",
                    "costo": Decimal("10.00"),
                    "peso_volume_collo": peso_volume_collo,
                    "applica_fuel": True,
                })

                print(f" B Supplemento peso volume applicato al collo lato max >121cm {index}: € 10.00")

            #se il secondo lato piu lungo è maggiore di 76
            dimensioni = sorted([larghezza, altezza, profondita], reverse=True)
            #lato_max = dimensioni[0]
            secondo_lato = dimensioni[1]
            if secondo_lato > 76:
                supplemento_additional_handling += Decimal("10")

                dettaglio_supplemento_additional_handling.append({
                    "nome": f"Supplemento additional handling: secondo lato {secondo_lato} cm collo {index} > 76 cm",
                    "costo": Decimal("10.00"),
                    "peso_volume_collo": peso_volume_collo,
                    "applica_fuel": True,
                })

                print(f"B Supplemento additional handling applicato al collo " f"{index}: secondo lato {secondo_lato} cm > 76 cm : € 10.00")

        nolo = pre_base_tariffa * Decimal(numero_colli)
        pre_base = nolo

        print("DEBUG A_COLLO ids_supplementi:", ids_supplementi)
        print("DEBUG A_COLLO assicurazione_euro:", spedizione.assicurazione_euro)
        print("DEBUG A_COLLO zona_get:", zona_get)

        print("DEBUG zone ASSIC:")
        for s in Supplemento.objects.filter(tipo_servizio__codice="ASSIC"):
            print(
                s.id,
                s.nome,
                list(s.zone_tariffazione.values_list("id", "nome"))
            )
        print("ids_supplementi =", ids_supplementi)

        for s in Supplemento.objects.filter(id__in=ids_supplementi):
            print(
                f"aaaa id={s.id} | "
                f"bbbb nome={s.nome} | "
                f"cccc codice={s.tipo_servizio.codice if s.tipo_servizio else 'None'}"
            )

        # 3. Supplementi standard
        supp = SupplementEngine.calcola_supplementi(
            spedizione,
            pacchi,
            pre_base,
            zona_get,
            ids_supplementi=ids_supplementi,
        )

        supplementi_puliti = []
        totale_supplementi_con_fuel = Decimal("0")
        totale_supplementi_senza_fuel = Decimal("0")

        for s in supp.get("dettaglio", []):
            nome_supp = s.get("nome", "").lower()
            costo_supp = Decimal(str(s.get("costo", 0)))

            if "fuel" in nome_supp:
                continue

            supplementi_puliti.append(s)

            if s.get("applica_fuel") is True or s.get("applica fuel") is True:
                totale_supplementi_con_fuel += costo_supp
            else:
                totale_supplementi_senza_fuel += costo_supp

        # 4. Supplemento peso volume manuale, con fuel
        for s in dettaglio_supplemento_additional_handling:
            supplementi_puliti.append(s)

            if s.get("applica_fuel") is True:
                totale_supplementi_con_fuel += Decimal(str(s["costo"]))
            else:
                totale_supplementi_senza_fuel += Decimal(str(s["costo"]))

        # 5. Fuel
        fuel = FuelEngine.calcola(
            spedizione,
            pre_base,
            supplementi_puliti,
            zona_get
        )

        costo_fuel_calcolato = Decimal(str(fuel["totale"]))

        prezzo = (
                pre_base
                + totale_supplementi_con_fuel
                + totale_supplementi_senza_fuel
                + costo_fuel_calcolato
        )
        #subtotale euro imponibile
        print(f'DEBUG FEDEX subtotale_euro_imponibile {prezzo}')

        imponibile_senza_fuel = (
                pre_base
                + totale_supplementi_con_fuel
                + totale_supplementi_senza_fuel
        )

        totale_imponibile_con_fuel = imponibile_senza_fuel + costo_fuel_calcolato
        totale_imponibile_senza_fuel = imponibile_senza_fuel

        # 6. Output dettagliato
        tariffa_collo_testo = (f"{tariffa_collo} {numero_colli} colli: € {tariffa_a_collo:.2f} a collo")
        #nolo = numero_colli * pre_base_tariffa

        lista_supp_con_fuel = []
        lista_supp_senza_fuel = []
        contatore_con_fuel = 1
        contatore_senza_fuel = 1

        for f in fuel.get("dettaglio", []):
            costo = Decimal(str(f.get("costo", 0)))

            if costo >= Decimal("0.01"):
                stringa_fuel = f"{f.get('nome')}"

                if f.get("percentuale"):
                    stringa_fuel += f" ({f.get('percentuale')}%)"

                lista_supp_senza_fuel.append(
                    f"{contatore_senza_fuel}. {stringa_fuel}: <b>€ {costo:.2f}</b>"
                )
                contatore_senza_fuel += 1

        for s in supplementi_puliti:
            costo = Decimal(str(s.get("costo", 0)))

            if costo >= Decimal("0.01"):
                if s.get("applica_fuel") is True or s.get("applica fuel") is True:
                    lista_supp_con_fuel.append(
                        f"{contatore_con_fuel}. {s.get('nome')}: <b>€ {costo:.2f}</b>"
                    )
                    contatore_con_fuel += 1
                else:
                    extra = ""

                    if s.get("peso_volume_collo"):
                        extra = (
                            f" ({Decimal(str(s.get('peso_volume_collo'))):.2f} kg volume)"
                        )

                    lista_supp_senza_fuel.append(
                        f"{contatore_senza_fuel}. {s.get('nome')}{extra}: <b>€ {costo:.2f}</b>"
                    )
                    contatore_senza_fuel += 1

        stringa_supp_con_fuel = (
            "<br>".join(lista_supp_con_fuel)
            if lista_supp_con_fuel
            else "Nessuno"
        )

        stringa_supp_senza_fuel = (
            "<br>".join(lista_supp_senza_fuel)
            if lista_supp_senza_fuel
            else "Nessuno"
        )

        volume_cm3 = dettaglio.get("volume_cm3", 0)
        divisore_output = dettaglio.get("divisore", 1)
        formula_volume = f"{volume_cm3:.0f} cm³ / {divisore_output}"
        #prezzo è il totale imponinile
        iva_euro = Decimal(prezzo * Decimal(0.22))
        totale_con_iva_euro = Decimal(prezzo * Decimal(1.22))


        items_ordinati = [
            {"label": "Numero colli", "value": f"{numero_colli}"},
            {"label": "Peso tassabile", "value": f"{peso_tassabile:.2f} kg"},
            {"label": "Peso reale", "value": f"{dettaglio['peso_reale']:.2f} kg"},
            {"label": "Peso volume", "value": f"{dettaglio['peso_volume']:.2f} kg ({formula_volume})"},
            {"label": "Tariffa a colli", "value": tariffa_collo_testo, "is_html": True},
            {"label": "Nolo", "value": f"<b>€ {nolo:.2f}</b>", "is_html": True},
            {"label": "Supplementi con fuel applicati", "value": stringa_supp_con_fuel, "is_html": True},
            {"label": "Supplementi senza fuel applicati", "value": stringa_supp_senza_fuel, "is_html": True},
            {"label": "Subtotale euro imponibile", "value": f"<b>€ {prezzo:.2f}</b>", "is_total": True, "is_html": True},
            {"label": "di cui imponibile senza fuel", "value": f"<b>€ {imponibile_senza_fuel:.2f}</b>", "is_html": True},
            {"label": "IVA", "value": f"<b>€ {iva_euro:.2f}</b>", "is_html": True},
            {"label": "TOTALE IVA INCLUSA", "value": f"<b>€ {totale_con_iva_euro:.2f}</b>", "is_total": True, "is_html": True},
        ]

        print(f"DEBUG FEDEX imponibile_senza_fuel  = {imponibile_senza_fuel}")
        #print(f"supplemento_peso_volume = {supplemento_peso_volume}")
        #print(f"supplemento_additional_handling = {supplemento_additional_handling}")
        #print(f"costo_fuel_calcolato = {costo_fuel_calcolato}")




        return {
            "totale_con_iva_euro": totale_con_iva_euro,
            "dettaglio": {
                "items": items_ordinati
            },
            "totale_imponibile_con_fuel": totale_imponibile_con_fuel,
            "totale_imponibile_senza_fuel": totale_imponibile_senza_fuel,
        }






