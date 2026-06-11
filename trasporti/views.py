from decimal import Decimal
from django.shortcuts import render, redirect
from .forms import SpedizioneForm, PaccoFormSet
from .models import *
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages



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


def calcola_preventivi(peso_totale):
    preventivi = [
        {"trasportatore": "GLS", "prezzo": peso_totale * Decimal("1.2")},
        {"trasportatore": "DHL", "prezzo": peso_totale * Decimal("1.5")},
        {"trasportatore": "UPS", "prezzo": peso_totale * Decimal("1.8")},
    ]

    # 👉 trova il prezzo più basso
    min_price = min(p["prezzo"] for p in preventivi)

    # 👉 aggiunge flag
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
                peso_totale = sum(
                    Decimal(p["peso_kg"])
                    for p in pacchi_data
                    if p and not p.get("DELETE", False)
                )

                preventivi = calcola_preventivi(peso_totale)

            # 🟢 CONFERMA PREVENTIVO
            elif action == "confirm":
                spedizione = form.save(commit=False)


                peso_totale = sum(
                    Decimal(p["peso_kg"])
                    for p in pacchi_data
                    if p and not p.get("DELETE", False)
                )

                spedizione.peso_totale_kg = peso_totale

                # 👉 dati selezionati dal bottone
                spedizione.trasportatore_scelto = request.POST.get("trasportatore")
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
