class PricingCalculator:

    def calcola_preventiviXXX(self, spedizione):
        results = []

        # Recuperiamo i supplementi selezionati (iniettati nella view)
        # Se non esistono (spedizione reale salvata), li prendiamo dal database
        if hasattr(spedizione, '_supplementi_simulati'):
            ids_supplementi = spedizione._supplementi_simulati
        else:
            # Assicurati che spedizione abbia la relazione supplementi accessibile
            ids_supplementi = [s.id for s in spedizione.supplementi.all()]
        print(f"DEBUG: Supplementi ricevuti dal Calculator: {ids_supplementi}")  # <--- AGGIUNGI QUESTO

        for spedizioniere in Spedizioniere.objects.all():
            engine = PricingFactory.get_engine(spedizioniere)

            # 🚀 MODIFICA: Passiamo gli ID come argomento nel metodo calcola
            # Non impostiamo più engine.ids_supplementi come attributo
            prezzo = engine.calcola(spedizione, spedizioniere, ids_supplementi=ids_supplementi)

            results.append({
                "spedizioniere": spedizioniere.nome,
                "prezzo": prezzo
            })

        return sorted(results, key=lambda x: x["prezzo"])

    def calcola_preventivi(spedizione, pacchi):
        print("🚀🚀🚀 CHIAMATA FUNZIONE CALCOLA_PREVENTIVI RICEVUTA! 🚀🚀🚀")
        results = []

        # 🚨 QUESTO È IL PUNTO CRUCIALE: Recupera gli ID iniettati
        ids_supplementi = getattr(spedizione, '_supplementi_simulati', [])

        for spedizioniere in Spedizioniere.objects.all():
            engine = PricingFactory.get_engine(spedizioniere)

            # Passiamo gli ID al metodo calcola dell'engine
            prezzo = engine.calcola(spedizione, spedizioniere, ids_supplementi=ids_supplementi)

            results.append({
                "spedizioniere": spedizioniere.nome,
                "prezzo": prezzo
            })
        return sorted(results, key=lambda x: x["prezzo"])