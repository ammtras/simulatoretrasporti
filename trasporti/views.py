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
from django.contrib.auth.mixins import LoginRequiredMixin
from datetime import timedelta

def check_supplemento_applicable(ids_list, spedizione):
    if sup.tipo_servizio.codice == "CONTR":
        return spedizione.da_nazione == "IT" and spedizione.a_nazione == "IT"
    return True

def simula_preventivi(spedizione, pacchi):
    preventivi = []

    ids_supp = getattr(spedizione, '_supplementi_simulati', [])
    servizi_scelti_per_check = ids_supp
    print(f'servizi_scelti_per_check {servizi_scelti_per_check}')

    id_zona_partenza = spedizione.da_zona_id
    #print(f'id zona partenza{id_zona_partenza}')
    zone_candidata_arrivo = Zona_spedizioniere.objects.filter(
        zona__id=id_zona_partenza)
    #print(f'zone_candidata_arrivo{zone_candidata_arrivo}')
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
    #print(f'QUESTE SONO LE ZONE CANDIDATE : {zone_candidate}')

    spedizionieri_map = {}
    for z in zone_candidate:
        spedizionieri_map.setdefault(z.spedizioniere_id, []).append(z)

    for spedizioniere_id, zone_trovate in spedizionieri_map.items():

        z_spedizioniere = max(zone_trovate, key=lambda z: z.priorita)
        print(f'z_spedizioniere{z_spedizioniere} (ZONA PRIORITARIA)')

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

def loggin(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request,username=username,password=password)
        print('a')
        if user is not None:
            print('b')
            login(request,user)
            return redirect('crea_spedizione')
            print('b2')
        else:
            print('c')
            messages.success(request, ('Opppsss, qualcosa è andato storto'))
            return redirect('login')
    else:
        print('url aperto')
        return render(request, 'login.html', {})

@login_required
def loggout(request):
    if request.method == "POST":
        logout(request)
        return redirect('login')

@login_required
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
                print(f'servizi_scelti:{servizi_scelti}') #qui manca il fuel

                spedizione_temp._supplementi_simulati = ids_simulati

                supp_richiesti = Supplemento.objects.filter(id__in=ids_simulati)
                print('supp_richiesti')
                for s in supp_richiesti:
                    print(f"{s.id} - {s.nome}")

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

class spedizioni(LoginRequiredMixin,ListView):
    model = Spedizione
    template_name = "spedizioni.html"
    context_object_name = "spedizioni"
    ordering = ["-data", "-id"]

    def EXget_paginate_by(self, queryset):
        per_page = self.request.GET.get("per_page", 30)

        try:
            per_page = int(per_page)
        except ValueError:
            per_page = 30

        # limite di sicurezza
        if per_page not in [10, 30, 50, 100]:
            per_page = 30

        return per_page

    def get_paginate_by(self, queryset):
        valori_validi = [4, 5, 10, 30, 50, 100]

        profilo, created = Profilo.objects.get_or_create(
            user=self.request.user
        )

        per_page = self.request.GET.get("per_page")

        if per_page:
            try:
                per_page = int(per_page)
            except ValueError:
                per_page = profilo.righe_per_pagina

            if per_page in valori_validi:
                profilo.righe_per_pagina = per_page
                profilo.save(update_fields=["righe_per_pagina"])
                return per_page

        return profilo.righe_per_pagina



    def get_queryset(self):
        # 1. Ottieni il queryset base
        queryset = super().get_queryset().prefetch_related('pacchi')

        # 2. Leggi i parametri dal form
        q = self.request.GET.get('q')
        periodo = self.request.GET.get("periodo")
        oggi = timezone.localdate()
        data_da = self.request.GET.get('data_da')
        data_a = self.request.GET.get('data_a')



        # 3. Filtra il queryset
        if q:
            # Filtra per città di partenza, arrivo o nome trasportatore
            queryset = queryset.filter(
                Q(da_cliente_citta__icontains=q) |
                Q(a_cliente_citta__icontains=q)
            )



        if periodo == "oggi":
            data_da = oggi
            data_a = oggi

        elif periodo == "ieri":
            ieri = oggi - timedelta(days=1)
            data_da = ieri
            data_a = ieri

        elif periodo == "settimana":
            data_da = oggi - timedelta(days=oggi.weekday())
            data_a = oggi

        elif periodo == "settimana_scorsa":
            inizio_settimana_corrente = oggi - timedelta(days=oggi.weekday())
            data_da = inizio_settimana_corrente - timedelta(days=7)
            data_a = inizio_settimana_corrente - timedelta(days=1)

        elif periodo == "mese":
            data_da = oggi.replace(day=1)
            data_a = oggi

        elif periodo == "mese_scorso":
            primo_giorno_mese_corrente = oggi.replace(day=1)
            ultimo_giorno_mese_scorso = primo_giorno_mese_corrente - timedelta(days=1)
            data_da = ultimo_giorno_mese_scorso.replace(day=1)
            data_a = ultimo_giorno_mese_scorso

        elif periodo == "anno":
            data_da = oggi.replace(month=1, day=1)
            data_a = oggi

        if data_da:
            queryset = queryset.filter(data__gte=data_da)

        if data_a:
            queryset = queryset.filter(data__lte=data_a)


        trasportatore = self.request.GET.get('trasportatore')
        # Filtro più robusto
        if trasportatore and trasportatore.isdigit():  # Controlla che sia un numero valido
            queryset = queryset.filter(trasportatore_scelto__id=int(trasportatore))


        return queryset

    def get_context_data(self, **kwargs):
        # Chiama il super per ottenere il queryset già filtrato!
        context = super().get_context_data(**kwargs)

        context['trasportatori'] = Spedizioniere.objects.all().order_by('nome')

        # 3. Il tuo codice per il calcolo dinamico (GLSService)
        # Ora il ciclo opererà SOLO sugli elementi filtrati
        for s in context["spedizioni"]:
            if s.trasportatore_scelto and s.trasportatore_scelto.nome.upper() == "GLS":
                # ... (il resto del tuo codice di calcolo resta invariato)
                pacchi_list = [
                    {"altezza_cm": p.altezza_cm, "larghezza_cm": p.larghezza_cm, "profondita_cm": p.profondita_cm,
                     "peso_kg": p.peso_kg}
                    for p in s.pacchi.all()
                ]
                result = GLSService.calcola(s, pacchi_list)
                if result:
                    s.dettaglio = result.get("dettaglio", {})
                    s.valore_preventivo_aggiornato = result.get("prezzo")

        return context

@login_required
def controllo_tariffe(request):
    # Carichiamo tutto in un colpo solo per efficienza

    spedizionieri = Spedizioniere.objects.prefetch_related(
        'sspedizioniere__zona_spedizioniere',
        'sspedizioniere__supplementi',
    ).all()

    return render(request, 'controllo_tariffe.html', {'spedizionieri': spedizionieri})

