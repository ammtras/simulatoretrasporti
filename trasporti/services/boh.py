from decimal import Decimal

def calcola_peso_tassabile_collo(pacco, zona_spedizioniere):

    peso_reale = pacco.peso_kg

    volume = (
        pacco.altezza_cm *
        pacco.larghezza_cm *
        pacco.profondita_cm
    )

    peso_volumetrico = volume / Decimal(zona_spedizioniere.divisore_volumetrico)

    valori = [peso_reale, peso_volumetrico]

    if zona_spedizioniere.peso_minimo_fatturabile:
        valori.append(zona_spedizioniere.peso_minimo_fatturabile)

    return max(valori)