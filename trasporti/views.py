from django.shortcuts import render, redirect
from .forms import SpedizioneForm, PaccoFormSet
from .models import *
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.generic import ListView
from trasporti.services.GLS import GLSService
from django.utils import timezone
from decimal import Decimal


def loggin(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request,username=username,password=password)
        if user is not None:
            login(request,user)
            return redirect('contatti')
        else:
            messages.success(request, ('Opppsss, qualcosa è andato storto'))
            return redirect('login')
    else:
        return render(request, 'login.html', {})


@login_required
def loggout(request):
    logout(request)
    return redirect('login')


from trasporti.models import Zona_spedizioniere

from decimal import Decimal
from django.db.models import Q

def calcola_preventivi(spedizione, pacchi):
    preventivi = []

    # 1. Recuperiamo gli ID di ENTRAMBE le zone selezionate nel form
    id_zona_partenza = spedizione.da_zona_id
    id_zona_arrivo = spedizione.a_zona_id

    # 2. 🔍 QUERY CON LOGICA "OR" (L'essenza della tua regola)
    # Chiediamo al database: "Dammi tutte le tariffe dei corrieri dove il ManyToMany 'zona'
    # contiene la zona di partenza OPPURE la zona di arrivo".
    #
    # Esempio: Se da_zona = Milano e a_zona = Calabria:
    # - Lo Spedizioniere A (Tariffa Unica) viene preso perché ha sia Milano che Calabria nel DB.
    # - Lo Spedizioniere B (Tariffa Calabria) viene preso perché la query trova il match su a_zona (Calabria).
    zone_spedizionieri_disponibili = Zona_spedizioniere.objects.filter(
        Q(zona=id_zona_partenza) | Q(zona=id_zona_arrivo)
    ).distinct().select_related('spedizioniere')

    # 3. Ciclo dinamico sui corrieri trovati nel DB
    for z_spedizioniere in zone_spedizionieri_disponibili:

        # 🟢 CORRIERE REALE: GLS
        if z_spedizioniere.spedizioniere.nome.upper() == "GLS":
            dettaglio_pesi = GLSService.dettaglio_calcolo_preventivo(pacchi, z_spedizioniere)

            context_gls = {
                "spedizione": spedizione,
                "pacchi": pacchi,
                "zona": z_spedizioniere,  # Passiamo l'oggetto completo
                "peso_tassabile": dettaglio_pesi["peso_tassabile"],
                "dettaglio": dettaglio_pesi
            }

            result_reale = GLSService._scaglioni(context_gls)

            if result_reale:
                preventivi.append({
                    "zona_tariffazione_id": z_spedizioniere.id,  # ID per il Radio Button del form
                    "trasportatore": z_spedizioniere.spedizioniere.nome,
                    "prezzo": result_reale["prezzo"],
                    "dettaglio": result_reale["dettaglio"]
                })

        # 🟡 MOCK CARRIERS: Per gli altri spedizionieri non ancora integrati
        else:
            peso_reale_totale = sum(Decimal(p.get("peso_kg", 0)) for p in pacchi if p and not p.get("DELETE", False))
            prezzo_mock = peso_reale_totale * Decimal("1.5")

            if prezzo_mock < z_spedizioniere.peso_minimo_fatturabile:
                prezzo_mock = z_spedizioniere.peso_minimo_fatturabile * Decimal("1.5")

            preventivi.append({
                "zona_tariffazione_id": z_spedizioniere.id,
                "trasportatore": z_spedizioniere.spedizioniere.nome,
                "prezzo": prezzo_mock,
                "dettaglio": {"items": [{"label": "Tariffa Base Simulata", "value": f"€ {prezzo_mock:.2f}"}]}
            })

    # ⭐ CALCOLO BEST PRICE
    if preventivi:
        min_price = min(p["prezzo"] for p in preventivi)
        for p in preventivi:
            p["best"] = (p["prezzo"] == min_price)

    return preventivi




#in crea_spedizione chiedere conferma se si vuole creare una spezione con data antecedente ad oggi






def crea_spedizione(request):
    preventivi = None
    # Recuperiamo i supplementi filtrando quelli che non hanno codice ASSIC o CONTR
    supplementi_disponibili = Supplemento.objects.exclude(tipo_servizio__codice__in=['ASSIC', 'CONTR', 'FUELS'])

    # Inizializziamo la lista dei selezionati per evitare errori se non c'è il POST
    ids_supplementi = []

    if request.method == "POST":
        print("DEBUG: Entrato nel POST della View!")
        action = request.POST.get("action")
        form = SpedizioneForm(request.POST)
        formset = PaccoFormSet(request.POST)

        # Recuperiamo gli ID dei supplementi dal form
        ids_supplementi = request.POST.getlist("supplementi_selezionati")

        # --- INCOLLA QUI IL BLOCCO DI DEBUG ---
        if form.is_valid() and formset.is_valid():
            print("DEBUG: Form valido!")
        else:
            print(f"DEBUG: Form NON valido! Errori form: {form.errors}")
            print(f"DEBUG: Errori formset: {formset.errors}")
        # --------------------------------------

        if form.is_valid() and formset.is_valid():
            pacchi_data = formset.cleaned_data
            pacchi = [p for p in pacchi_data if p and not p.get("DELETE", False)]

            # 🔵 SIMULA PREVENTIVI
            if action == "simulate":
                spedizione_temp = form.save(commit=False)

                # Inietto servizi e supplementi per il motore di calcolo
                servizi_scelti = form.cleaned_data.get("servizi_richiesti", [])
                spedizione_temp._servizi_simulati = list(servizi_scelti)
                # Passiamo gli ID dei supplementi al motore di calcolo
                spedizione_temp._supplementi_simulati = ids_supplementi

                preventivi = calcola_preventivi(spedizione_temp, pacchi)

            # 🟢 CONFERMA PREVENTIVO
            elif action == "confirm":
                spedizione = form.save(commit=False)

                # Calcolo peso
                peso_reale_totale = sum(Decimal(p["peso_kg"]) for p in pacchi)
                spedizione.peso_reale_totale_kg = peso_reale_totale

                nome_trasportatore = request.POST.get("trasportatore")
                try:
                    trasportatore_obj = Spedizioniere.objects.get(nome=nome_trasportatore)
                    spedizione.trasportatore_scelto = trasportatore_obj

                    # Logica zona
                    zona_corriere_obj = Zona_spedizioniere.objects.filter(
                        spedizioniere=trasportatore_obj,
                        zona=spedizione.a_zona
                    ).first()
                    spedizione.zona_tariffazione_spedizioniere = zona_corriere_obj
                except Spedizioniere.DoesNotExist:
                    spedizione.trasportatore_scelto = None
                    spedizione.zona_tariffazione_spedizioniere = None

                prezzo = request.POST.get("prezzo", "0")
                spedizione.valore_preventivo = Decimal(str(prezzo).replace(",", "."))

                # Salvataggio
                spedizione.save()

                # 🚀 SALVATAGGIO RELAZIONE MANY-TO-MANY
                if ids_supplementi:
                    spedizione.supplementi.set(ids_supplementi)

                form.save_m2m()
                formset.instance = spedizione
                formset.save()

                return redirect("spedizioni")

    else:
        form = SpedizioneForm(instance=Spedizione(data=timezone.now().date()))
        formset = PaccoFormSet()

    return render(request, "crea_spedizione.html", {
        "form": form,
        "formset": formset,
        "preventivi": preventivi,
        "supplementi_disponibili": supplementi_disponibili,
        "ids_selezionati": ids_supplementi  # <--- AGGIUNTA FONDAMENTALE
    })





class Spedizioni(ListView):
    model = Spedizione
    template_name = "spedizioni.html"
    context_object_name = "spedizioni"
    ordering = ["-data"]

    def get_queryset(self):
        # 🟢 OTTIMIZZAZIONE: prefetch_related carica tutti i pacchi in un'unica query velocizzando la pagina
        return super().get_queryset().prefetch_related('pacchi')

    def get_context_data(self, **kwargs):
        # Prende il contesto standard di Django (che contiene già la lista "spedizioni")
        context = super().get_context_data(**kwargs)

        # 🟢 RICALCOLO DINAMICO: Cicliamo sulle spedizioni destinate al template
        for s in context["spedizioni"]:
            if s.trasportatore_scelto and s.trasportatore_scelto.nome.upper() == "GLS":

                # Prepariamo la lista dei pacchi come dizionari per il service
                pacchi_list = [
                    {
                        "altezza_cm": p.altezza_cm,
                        "larghezza_cm": p.larghezza_cm,
                        "profondita_cm": p.profondita_cm,
                        "peso_kg": p.peso_kg,
                    }
                    for p in s.pacchi.all()
                ]

                # Eseguiamo il calcolo ufficiale tramite il GLSService
                result = GLSService.calcola(s, pacchi_list)

                if result:
                    # Iniettiamo il dizionario 'dettaglio' nell'oggetto in memoria
                    s.dettaglio = result.get("dettaglio", {})
                    # Se vuoi mostrare il prezzo aggiornato al volo nel template
                    s.valore_preventivo_aggiornato = result.get("prezzo")

        return context





