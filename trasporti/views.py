from django.shortcuts import render, redirect
from .forms import SpedizioneForm, PaccoFormSet
from .models import *
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.generic import ListView
from trasporti.services.GLS import GLSService

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
def crea_spedizioneXX(request):
    preventivi = None

    if request.method == "POST":
        action = request.POST.get("action")

        form = SpedizioneForm(request.POST)

        formset = PaccoFormSet(request.POST)

        if form.is_valid() and formset.is_valid():

            pacchi_data = formset.cleaned_data

            # 🔵 SIMULA PREVENTIVI
            if action == "simulate":

                spedizione_temp = form.save(commit=False)  # 👈 FIX

                peso_reale_totale = sum(
                    Decimal(p["peso_kg"])
                    for p in pacchi_data
                    if p and not p.get("DELETE", False)
                )

                pacchi = [
                    p for p in formset.cleaned_data
                    if p and not p.get("DELETE", False)
                ]

                preventivi = calcola_preventivi(spedizione_temp, pacchi)


            # 🟢 CONFERMA PREVENTIVO
            elif action == "confirm":
                spedizione = form.save(commit=False)

                peso_reale_totale = sum(
                    Decimal(p["peso_kg"])
                    for p in pacchi_data
                    if p and not p.get("DELETE", False)
                )
                spedizione.peso_reale_totale_kg = peso_reale_totale

                nome_trasportatore = request.POST.get("trasportatore")

                try:
                    trasportatore_obj = Spedizioniere.objects.get(nome=nome_trasportatore)
                    spedizione.trasportatore_scelto = trasportatore_obj

                    # 🟢 NUOVO FIX: Recuperiamo e salviamo la zona del trasportatore!
                    # Cerchiamo la Zona_spedizioniere che incrocia il corriere scelto con la tratta del form
                    from trasporti.models import Zona_spedizioniere  # Assicurati che l'import sia corretto

                    zona_corriere_obj = Zona_spedizioniere.objects.filter(
                        spedizioniere=trasportatore_obj,
                        da_zona=spedizione.da_zona,  # Le località inserite nel form
                        a_zona=spedizione.a_zona
                    ).first()

                    # Salviamo la relazione sul DB (così la lista /spedizioni la troverà compilata!)
                    spedizione.zona_tariffazione_spedizioniere = zona_corriere_obj

                except Spedizioniere.DoesNotExist:
                    spedizione.trasportatore_scelto = None
                    spedizione.zona_tariffazione_spedizioniere = None

                prezzo = request.POST.get("prezzo", "0")
                spedizione.valore_preventivo = Decimal(str(prezzo).replace(",", "."))

                # Salva tutto nel Database
                spedizione.save()
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
        "preventivi": preventivi
    })



def crea_spedizione(request):
    preventivi = None

    if request.method == "POST":
        action = request.POST.get("action")
        form = SpedizioneForm(request.POST)
        formset = PaccoFormSet(request.POST)

        if form.is_valid() and formset.is_valid():
            pacchi_data = formset.cleaned_data

            # 🔵 SIMULA PREVENTIVI
            if action == "simulate":
                spedizione_temp = form.save(commit=False)

                # Iniettiamo i servizi in memoria per il motore dei supplementi
                servizi_scelti = form.cleaned_data.get("servizi_richiesti", [])
                spedizione_temp._servizi_simulati = list(servizi_scelti)

                peso_reale_totale = sum(
                    Decimal(p["peso_kg"])
                    for p in pacchi_data
                    if p and not p.get("DELETE", False)
                )

                pacchi = [
                    p for p in formset.cleaned_data
                    if p and not p.get("DELETE", False)
                ]
                preventivi = calcola_preventivi(spedizione_temp, pacchi)

            # 🟢 CONFERMA PREVENTIVO
            elif action == "confirm":
                spedizione = form.save(commit=False)

                peso_reale_totale = sum(
                    Decimal(p["peso_kg"])
                    for p in pacchi_data
                    if p and not p.get("DELETE", False)
                )
                spedizione.peso_reale_totale_kg = peso_reale_totale

                nome_trasportatore = request.POST.get("trasportatore")

                try:
                    trasportatore_obj = Spedizioniere.objects.get(nome=nome_trasportatore)
                    spedizione.trasportatore_scelto = trasportatore_obj

                    # 🟢 FIX CHIRURGICO: Cerchiamo la zona usando il campo reale del modello ('zona')
                    # Agganciamo la zona del corriere basandoci sulla destinazione della spedizione (a_zona)
                    from trasporti.models import Zona_spedizioniere

                    zona_corriere_obj = Zona_spedizioniere.objects.filter(
                        spedizioniere=trasportatore_obj,
                        zona=spedizione.a_zona  # 👈 'zona' è il campo nel DB, 'spedizione.a_zona' è il dato del form
                    ).first()

                    # Salviamo la relazione corretta sul DB
                    spedizione.zona_tariffazione_spedizioniere = zona_corriere_obj

                except Spedizioniere.DoesNotExist:
                    spedizione.trasportatore_scelto = None
                    spedizione.zona_tariffazione_spedizioniere = None

                prezzo = request.POST.get("prezzo", "0")
                spedizione.valore_preventivo = Decimal(str(prezzo).replace(",", "."))

                # Salva definitivamente la spedizione e le relazioni Many-to-Many
                spedizione.save()
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
        "preventivi": preventivi
    })

#in crea_spedizione chiedere conferma se si vuole creare una spezione con data antecedente ad oggi




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





