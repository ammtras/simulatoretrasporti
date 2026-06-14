# trasporti/services/pricing_engine.py

from decimal import Decimal
from trasporti.services.GLS import GLSService


class PricingEngine:

    @staticmethod
    def calcola(spedizione, pacchi):

        zona = GLSService.get_zona_gls(spedizione)

        if not zona:
            return {
                "prezzo": Decimal("0"),
                "dettaglio": {"error": "zona mancante"}
            }

        dettaglio = GLSService.dettaglio_calcolo_preventivo(pacchi, zona)
        peso_tassabile = dettaglio["peso_tassabile"]

        # 🧠 CONTEXT UNICO
        context = {
            "spedizione": spedizione,
            "pacchi": pacchi,
            "zona": zona,
            "peso_tassabile": peso_tassabile,
            "dettaglio": dettaglio,
        }

        if zona.spedizioniere.tipo_tariffazione == "scaglioni":
            return GLSService.scaglioni(context)

        return GLSService.a_collo(context)