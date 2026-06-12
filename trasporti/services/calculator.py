class PricingCalculator:

    def calcola_preventivi(self, spedizione):

        results = []

        for spedizioniere in Spedizioniere.objects.all():

            engine = PricingFactory.get_engine(spedizioniere)

            prezzo = engine.calcola(spedizione, spedizioniere)

            results.append({
                "spedizioniere": spedizioniere.nome,
                "prezzo": prezzo
            })

        return sorted(results, key=lambda x: x["prezzo"])