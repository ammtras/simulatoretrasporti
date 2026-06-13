from django.db.models import Q
from trasporti.models import Supplemento

class TariffValidityService:

    @staticmethod
    def filtra_validita(queryset, data):
        return queryset.filter(
            valid_from__lte=data
        ).filter(
            Q(valid_to__gte=data) | Q(valid_to__isnull=True)
        )




class BaseEngineXXX:

    def calcola(self, spedizione, spedizioniere, ids_supplementi=None):
        # 1. IL TUO CALCOLO ORIGINALE (che già avevi)
        # Sostituisci la riga sotto con la logica reale che hai nel tuo codice
        prezzo_totale = self.calcola_base(spedizione, spedizioniere)

        # 2. GESTIONE SUPPLEMENTI (La parte nuova che integra i tuoi checkbox)
        if ids_supplementi:
            # Filtriamo i supplementi validi presenti nel DB
            supplementi = Supplemento.objects.filter(id__in=ids_supplementi)

            for s in supplementi:
                # Verifichiamo se il supplemento è applicabile a questo specifico spedizioniere/zona
                if s.zone_tariffazione.filter(spedizioniere=spedizioniere).exists():

                    # Applichiamo il calcolo in base al tipo (fisso o percentuale)
                    if s.calc_type == 'fisso':
                        prezzo_totale += s.valore
                    elif s.calc_type == 'percentuale':
                        # Supponendo che 'valore' sia la percentuale (es: 5 per 5%)
                        prezzo_totale += (prezzo_totale * (s.valore / 100))

        return prezzo_totale


class BaseEngine:
    def calcola(self, spedizione, spedizioniere, ids_supplementi=None):
        prezzo_totale = self.calcola_base(spedizione, spedizioniere)

        # Stampa per debug: verifica se arrivano gli ID
        print(f"DEBUG Engine: Ricevuti IDS {ids_supplementi}")

        if ids_supplementi:
            supplementi = Supplemento.objects.filter(id__in=ids_supplementi)
            for s in supplementi:
                # Logica calcolo
                if s.calc_type == 'fisso':
                    prezzo_totale += s.valore
                # ...
        return prezzo_totale