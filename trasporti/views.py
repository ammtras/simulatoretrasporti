from django.shortcuts import render, redirect
from .forms import SpedizioneForm, PaccoFormSet
from .models import *
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.generic import ListView
from trasporti.services.GLS import GLSService
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
        if z_spedizioniere.spedizioniere.codice == "GLS":
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
                # 🟢 CONFERMA PREVENTIVO
            elif action == "confirm":
                spedizione = form.save(commit=False)

                print("PACCHI DATA:")
                print(pacchi_data)

                peso_reale_totale = sum(
                    Decimal(p["peso_kg"])
                    for p in pacchi_data
                    if p and not p.get("DELETE", False)
                )

                spedizione.peso_reale_totale_kg = peso_reale_totale

                # 👇 MODIFICA QUI 👇
                nome_trasportatore = request.POST.get("trasportatore")

                try:
                    # Sostituisci 'Spedizioniere' con il nome reale del tuo modello
                    # e 'nome' con il campo che contiene il testo 'GLS'
                    trasportatore_obj = Spedizioniere.objects.get(nome=nome_trasportatore)
                    spedizione.trasportatore_scelto = trasportatore_obj
                except Spedizioniere.DoesNotExist:
                    # Gestione errore: se nel DB non esiste un trasportatore con quel nome
                    # Puoi decidere se impostarlo a None, mostrare un messaggio di errore, ecc.
                    spedizione.trasportatore_scelto = None
                    # 👆 FINE MODIFICA 👆

                prezzo = request.POST.get("prezzo", "0")
                spedizione.valore_preventivo = Decimal(str(prezzo).replace(",", "."))

                spedizione.save()

                formset.instance = spedizione
                formset.save()

                return redirect("crea_spedizione")
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
        spedizioni = super().get_queryset()

        for s in spedizioni:

            pacchi = [
                {
                    "altezza_cm": p.altezza_cm,
                    "larghezza_cm": p.larghezza_cm,
                    "profondita_cm": p.profondita_cm,
                    "peso_kg": p.peso_kg,
                }
                for p in s.pacchi.all()
            ]

            # 🔥 USA STESSA LOGICA DEL CALCOLO PREVENTIVO
            result = GLSService.calcola(s, pacchi)

            if result:
                s.dettaglio = result["dettaglio"]
                s.valore_preventivo = result["prezzo"]

        return spedizioni





