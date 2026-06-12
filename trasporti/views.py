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




def calcola_preventivi(spedizione, pacchi):

    preventivi = []

    # 🔵 peso totale
    peso_reale_totale = sum(
        Decimal(p.get("peso_kg", 0))
        for p in pacchi
        if p and not p.get("DELETE", False)
    )

    # =========================
    # 🟢 GLS (DELEGATO AL SERVICE)
    # =========================
    result_gls = GLSService.calcola(spedizione, pacchi)

    if result_gls:
        preventivi.append({
            "trasportatore": "GLS",
            "prezzo": result_gls["prezzo"],
            "dettaglio": result_gls["dettaglio"]
        })

    # =========================
    # 🟡 MOCK CARRIER
    # =========================
    preventivi += [
        {
            "trasportatore": "DHL",
            "prezzo": peso_reale_totale * Decimal("1.5")
        },
        {
            "trasportatore": "UPS",
            "prezzo": peso_reale_totale * Decimal("1.8")
        }
    ]

    # =========================
    # ⭐ BEST PRICE
    # =========================
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

#in crea_spedizione chiedere conferma se si vuole creare una spezione con data antecedente ad oggi

class Spedizionixx(ListView):
    model = Spedizione
    template_name = "spedizioni.html"
    context_object_name = "spedizioni"
    ordering = ["-data"]  # più recenti prima

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        for spedizione in context["spedizioni"]:
            pacchi = [
                {
                    "altezza_cm": p.altezza_cm,
                    "larghezza_cm": p.larghezza_cm,
                    "profondita_cm": p.profondita_cm,
                    "peso_kg": p.peso_kg,
                }
                for p in spedizione.pacco_set.all()
            ]

            spedizione.dettaglio = GLSService.dettaglio_calcolo_preventivo(
                pacchi,
                spedizione.zona_tariffazione_spedizioniere
            )

        return context

from trasporti.services.GLS import GLSService

class Spedizioni(ListView):
    model = Spedizione
    template_name = "spedizioni.html"
    context_object_name = "spedizioni"
    ordering = ["-data"]

    def get_queryset(self):
        spedizioni = super().get_queryset()

        for spedizione in spedizioni:

            pacchi = [
                {
                    "altezza_cm": p.altezza_cm,
                    "larghezza_cm": p.larghezza_cm,
                    "profondita_cm": p.profondita_cm,
                    "peso_kg": p.peso_kg,
                }
                for p in spedizione.pacchi.all()
            ]

            spedizione.dettaglio = GLSService.dettaglio_calcolo_preventivo(
                pacchi,
                spedizione.zona_tariffazione_spedizioniere
            )

        return spedizioni

