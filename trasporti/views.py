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
from django.db.models import Q



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




def simula_preventivi(spedizione, pacchi):
    preventivi = []

    ids_supp = getattr(spedizione, '_supplementi_simulati', [])
    print(ids_supp)

    id_zona_partenza = spedizione.da_zona_id
    print(f'id zona partenza{id_zona_partenza}')
    zone_candidata_arrivo = Zona_spedizioniere.objects.filter(
        zona__id=id_zona_partenza)
    print(f'zone_candidata_arrivo{zone_candidata_arrivo}')
    id_zona_arrivo = spedizione.a_zona_id
    print(f'id zona arrivo{id_zona_arrivo}')

    # 1. Recupera la Zona geografica di arrivo dal DB
    '''from trasporti.models import Zona
    zona_arrivo = Zona.objects.get(id=id_zona_arrivo)
    zona_arrivo_candidata = Zona_spedizioniere.objects.filter(
        zona__id=zona_arrivo.id
    ).order_by('-priorita').distinct()
    print(f'zone_arrivo_candidata: {zona_arrivo_candidata}')'''
    # 2. Cerca le configurazioni (Zona_spedizioniere) che contengono questa specifica zona
    # Usiamo 'zona__in' per interrogarlo correttamente visto che è un ManyToMany

    zone_candidate = Zona_spedizioniere.objects.filter(
        Q(zona=id_zona_partenza) | Q(zona=id_zona_arrivo)
    ).distinct().select_related('spedizioniere')
    print(f'QUESTE SONO LE ZONE CANDIDATE : {zone_candidate}')

    spedizionieri_map = {}
    for z in zone_candidate:
        spedizionieri_map.setdefault(z.spedizioniere_id, []).append(z)

    for spedizioniere_id, zone_trovate in spedizionieri_map.items():

        z_spedizioniere = max(zone_trovate, key=lambda z: z.priorita)
        print(z_spedizioniere)

        # SOLO GLS (o altri reali)
        if z_spedizioniere.spedizioniere.nome.upper() == "GLS":

            dettaglio_pesi = GLSService.dettaglio_calcolo_preventivo(
                pacchi,
                z_spedizioniere
            )

            context_gls = {
                "spedizione": spedizione,
                "pacchi": pacchi,
                "zona": z_spedizioniere,
                "peso_tassabile": dettaglio_pesi["peso_tassabile"],
                "dettaglio": dettaglio_pesi,
                "ids_supplementi": ids_supp
            }
            #print(context_gls)
            #qui passano tutti i supplementi flaggati

            #  qui è il fumetto verde del preventivo
            result_reale = GLSService._scaglioni(context_gls)
            #print(result_reale)

            if result_reale:
                preventivi.append({
                    "zona_tariffazione_id": z_spedizioniere.id,
                    "trasportatore": z_spedizioniere.spedizioniere.nome,
                    "prezzo": result_reale["prezzo"],
                    "dettaglio": result_reale["dettaglio"]
                })

    if preventivi:
        min_price = min(p["prezzo"] for p in preventivi)
        for p in preventivi:
            p["best"] = (p["prezzo"] == min_price)

    return preventivi






def crea_spedizione(request):
    preventivi = None

    supplementi_disponibili = Supplemento.objects.all()

    ids_supplementi = []

    def aggiungi_assic_contr_peaks(ids_list, valore_merce, valore_contr, spedizione):
        # ASSIC
        if valore_merce > 0:
            assic_obj = Supplemento.objects.filter(tipo_servizio__codice='ASSIC').first()
            if assic_obj and assic_obj.id not in ids_list:
                ids_list.append(assic_obj.id)

        # CONTR
        if valore_contr > 0:
            contr_obj = Supplemento.objects.filter(tipo_servizio__codice='CONTR').first()
            if contr_obj and contr_obj.id not in ids_list:
                ids_list.append(contr_obj.id)

        # PEAKS
        peaks_qs = Supplemento.objects.filter(tipo_servizio__codice='PEAKS')
        for peak in peaks_qs:
            if peak.valid_from and peak.valid_to:
                if peak.valid_from <= spedizione.data <= peak.valid_to:
                    if peak.id not in ids_list:
                        ids_list.append(peak.id)



        return ids_list


        return ids_list


    if request.method == "POST":
        #print("========== POST RAW ==========")
        #print(request.POST)

        action = request.POST.get("action")
        form = SpedizioneForm(request.POST)
        formset = PaccoFormSet(request.POST)

        ids_supplementi = request.POST.getlist("supplementi_selezionati")

        if form.is_valid() and formset.is_valid():

            pacchi_data = formset.cleaned_data
            pacchi = [p for p in pacchi_data if p and not p.get("DELETE", False)]

            ids_int = [int(i) for i in ids_supplementi if i.isdigit()]

            valore_merce = form.cleaned_data.get('assicurazione_euro', Decimal('0'))
            valore_contr = form.cleaned_data.get('contrassegno_euro', Decimal('0'))

            servizi_scelti = form.cleaned_data.get("servizi_richiesti", [])

            if action == "simulate":
                spedizione_temp = form.save(commit=False)

                spedizione_temp.valore_merce = valore_merce
                spedizione_temp.valore_contrassegno = valore_contr

                ids_simulati = aggiungi_assic_contr_peaks(
                    ids_int.copy(),
                    valore_merce,
                    valore_contr,
                    spedizione_temp
                )

                spedizione_temp._servizi_simulati = list(servizi_scelti)
                spedizione_temp._supplementi_simulati = ids_simulati

                preventivi = simula_preventivi(spedizione_temp, pacchi)

            elif action == "confirm":
                spedizione = form.save(commit=False)

                peso_reale_totale = sum(Decimal(str(p["peso_kg"])) for p in pacchi)
                spedizione.peso_reale_totale_kg = peso_reale_totale

                nome_trasportatore = request.POST.get("trasportatore")

                try:
                    trasportatore_obj = Spedizioniere.objects.get(nome=nome_trasportatore)
                    spedizione.trasportatore_scelto = trasportatore_obj

                    zona_corriere_obj = Zona_spedizioniere.objects.filter(
                        spedizioniere=trasportatore_obj,
                        zona__in=[spedizione.da_zona, spedizione.a_zona]
                    ).order_by('-priorita').first()

                    spedizione.zona_tariffazione_spedizioniere = zona_corriere_obj

                except Spedizioniere.DoesNotExist:
                    spedizione.trasportatore_scelto = None

                prezzo = request.POST.get("prezzo", "0")
                spedizione.valore_preventivo = Decimal(str(prezzo).replace(",", "."))

                spedizione.save()

                ids_finali = aggiungi_assic_contr_peaks(
                    ids_int,
                    valore_merce,
                    valore_contr,
                    spedizione
                )


                spedizione.supplementi.set(ids_finali)

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
        "ids_selezionati": [i for i in ids_supplementi if i.isdigit()]
    })



class Spedizioni(ListView):
    model = Spedizione
    template_name = "spedizioni.html"
    context_object_name = "spedizioni"
    ordering = ["-data", "-id"]

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





