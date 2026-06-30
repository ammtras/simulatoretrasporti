from django.shortcuts import render

# Create your views here.
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST
from django.db.models import Case, When, Value, IntegerField, Q
from openpyxl import Workbook
from datetime import datetime
from .models import OrdineImportazione, Acconto
from decimal import Decimal, InvalidOperation
from django.db import models
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST
from django.core.paginator import Paginator
from django.db.models import Sum
from django.contrib.auth.decorators import login_required




COLONNE = [
    ("id", "ID"),
    ("ordine_data", "Ordine Data"),
    ("ordine_fornitore_sigla", "Forn."),
    ("ordine_nome_fornitore", "Nome fornitore"),
    ("ordine_descrizione", "Ordine Descrizione"),
    ("ordine_num_pezzi", "N. pezzi"),
    ("ordine_preventivo_dollari", "Prev. USD"),
    ("ordine_proforma_arrivata_dollari", "Proforma USD"),
    ("ordine_preventivi_nolo_import", "Preventivi nolo"),
    ("ordine_confermata_spedizione_con_spedizioniere", "Spedizioniere Scelto"),

    ("arrivo_anno", "Arrivo anno"),
    ("arrivo_data", "Data arrivo"),
    ("arrivo_num", "Arrivo N."),

    ("ft_dazi_iva_ragione_sociale", "Ft Dazi/IVA Ragione Sociale"),
    ("ft_dazi_iva_iva_euro", "Ft Dazi/IVA IVA €"),
    ("ft_dazi_iva_dazio_euro", " FtDazi/IVA Dazio €"),
    ("ft_dazi_iva_costi_accessori_euro", "Ft Dazi/IVA Costi accessori €"),
    ("ft_dazi_iva_totale", "Ft Dazi/IVA Totale €"),
    ("ft_dazi_iva_totale_nostro_prot_numero", "Ft Dazi/IVA PROT.N."),

    ("ft_merce_fornit_sigla", "Ft Merce Sigla fornitore"),
    ("ft_merce_fornit_ragione_sociale", "Ft Merce Ragione sociale"),
    ("ft_merce_num", "Fattura Merce N. "),
    ("ft_merce_data", "Fattura Merce data"),
    ("ft_merce_tot_pz", "Fattura Merce Tot. pezzi"),
    ("ft_valore_usd", "Fattura Merce Valore USD"),

    ("nolo_se_prepagato_in_ft_usd", "Nolo prepagato USD"),
    ("nolo_vettore_nome", "Vettore"),
    ("nolo_ft_totale", "Tot. nolo Fattura"),
    ("nolo_ft_nostro_prot_numero", "Ft.Nolo PROT.N."),

    ("ader_bolla_doganale_classica", "Bolla doganale classica"),
    ("ader_MRN_codice", "MRN"),
    ("ader_stampato_mrn_da_ader", "MRN stampato"),
    ("ader_nostro_prot_num", "nostro PROT.N."),

    ("note", "Note"),
]

CAMPI_TABELLA = [
    "id",
    "ordine_fornitore_sigla",
    "ordine_nome_fornitore",
    "ordine_descrizione",
    "ordine_num_pezzi",
    "ordine_preventivo_dollari",
    "ordine_proforma_arrivata_dollari",
    "ordine_preventivi_nolo_import",
    "ordine_confermata_spedizione_con_spedizioniere",
    "arrivo_anno",
    "arrivo_data",
    "arrivo_num",
    "ft_dazi_iva_ragione_sociale",
    "ft_dazi_iva_iva_euro",
    "ft_dazi_iva_dazio_euro",
    "ft_dazi_iva_costi_accessori_euro",
    "ft_dazi_iva_totale",
    "ft_dazi_iva_totale_nostro_prot_numero",
    "ft_merce_fornit_sigla",
    "ft_merce_fornit_ragione_sociale",
    "ft_merce_num",
    "ft_merce_data",
    "ft_merce_tot_pz",
    "ft_valore_usd",
    "nolo_se_prepagato_in_ft_usd",
    "nolo_vettore_nome",
    "nolo_ft_totale",
    "nolo_ft_nostro_prot_numero",
    "ader_bolla_doganale_classica",
    "ader_MRN_codice",
    "ader_stampato_mrn_da_ader",
    "ader_nostro_prot_num",
    "note",
]

def get_queryset_importazioni(request):
    righe = (
        OrdineImportazione.objects
        .prefetch_related("acconti")
        .annotate(
            stato_ordinamento=Case(
                When(
                    Q(arrivo_anno__isnull=True) &
                    Q(ordine_confermata_spedizione_con_spedizioniere__isnull=False) &
                    ~Q(ordine_confermata_spedizione_con_spedizioniere=""),
                    then=Value(0)
                ),
                When(arrivo_anno__isnull=True, then=Value(1)),
                default=Value(2),
                output_field=IntegerField(),
            ),
            mrn_vuoto=Case(
                When(ader_MRN_codice__isnull=True, then=Value(0)),
                When(ader_MRN_codice="", then=Value(0)),
                default=Value(1),
                output_field=IntegerField(),
            ),
            id_non_arrivati=Case(
                When(arrivo_anno__isnull=True, then="id"),
                default=Value(None),
                output_field=IntegerField(),
            ),
        )
    )

    anno_ordine = request.GET.get("anno_ordine")
    anno_arrivo = request.GET.get("anno_arrivo")
    stato = request.GET.get("stato")
    fornitore = request.GET.get("fornitore")

    if anno_ordine:
        righe = righe.filter(ordine_anno=anno_ordine)

    if anno_arrivo:
        righe = righe.filter(arrivo_anno=anno_arrivo)

    if stato == "non_arrivati":
        righe = righe.filter(arrivo_anno__isnull=True)

    if stato == "arrivati":
        righe = righe.filter(arrivo_anno__isnull=False)

    if fornitore:
        righe = righe.filter(ordine_nome_fornitore__icontains=fornitore)

    return righe.order_by(
        "stato_ordinamento",
        "id_non_arrivati",
        "mrn_vuoto",
        "-arrivo_anno",
        "-arrivo_data",
        "-arrivo_num",
        "ader_nostro_prot_num",
        "id",
    )


def tabella_importazioni(request):
    righe = get_queryset_importazioni(request)

    # TOTALI DEL QUERYSET FILTRATO, NON DELLA SOLA PAGINA
    totali = righe.aggregate(
        ordine_totale_pezzi=Sum("ordine_num_pezzi"),
        ordine_preventivi_totale_dollari=Sum("ordine_preventivo_dollari"),
        ordine_proforme_totale_dollari=Sum("ordine_proforma_arrivata_dollari"),
    )

    totali["ordine_totale_pezzi"] = totali["ordine_totale_pezzi"] or 0
    totali["ordine_preventivi_totale_dollari"] = totali["ordine_preventivi_totale_dollari"] or Decimal("0")
    totali["ordine_proforme_totale_dollari"] = totali["ordine_proforme_totale_dollari"] or Decimal("0")

    totale_acconti_pagati = sum(
        riga.totale_acconti_usd
        for riga in righe
    )

    totali["totale_acconti_pagati"] = totale_acconti_pagati
    totali["totale_da_pagare"] = (
        totali["ordine_proforme_totale_dollari"] - totale_acconti_pagati
    )

    # PAGINAZIONE
    per_page = request.GET.get("per_page", "100")
    page_number = request.GET.get("page", 1)

    if per_page == "all":
        page_obj = None
        righe_pagina = righe
    else:
        try:
            per_page_int = int(per_page)
        except ValueError:
            per_page_int = 100

        paginator = Paginator(righe, per_page_int)
        page_obj = paginator.get_page(page_number)
        righe_pagina = page_obj.object_list

    return render(request, "importPRC/tabella_importazioni.html", {
        "righe": righe_pagina,
        "page_obj": page_obj,
        "per_page": per_page,
        "campi": CAMPI_TABELLA,
        "colonne": COLONNE,
        "totali": totali,
    })

@require_POST
def crea_riga_importazione(request):
    riga = OrdineImportazione.objects.create()
    return JsonResponse({
        "ok": True,
        "id": riga.id,
    })


def parse_data(valore):
    formati = [
        "%Y-%m-%d",

        "%d-%m-%Y",
        "%d-%m-%y",

        "%d/%m/%Y",
        "%d/%m/%y",

        "%d.%m.%Y",
        "%d.%m.%y",
    ]

    for formato in formati:
        try:
            return datetime.strptime(valore, formato).date()
        except ValueError:
            pass

    raise ValueError(f"Data non valida: {valore}")

@require_POST
def aggiorna_cella_importazione(request):
    riga_id = request.POST.get("id")
    campo = request.POST.get("campo")
    valore = request.POST.get("valore", "").strip()

    if campo not in CAMPI_TABELLA or campo == "id":
        return JsonResponse(
            {"ok": False, "errore": "Campo non valido"},
            status=400
        )

    riga = get_object_or_404(OrdineImportazione, id=riga_id)

    try:
        field = OrdineImportazione._meta.get_field(campo)

        if valore == "":
            valore_convertito = None

        elif isinstance(field, models.DecimalField):
            valore_convertito = Decimal(valore.replace(",", "."))

        elif isinstance(field, models.DateField):
            valore_convertito = parse_data(valore)

        elif isinstance(field, models.IntegerField):
            valore_convertito = int(valore)

        elif isinstance(field, models.BooleanField):
            valore_convertito = valore.lower() in [
                "true", "1", "si", "sì", "yes"
            ]

        else:
            valore_convertito = valore

        setattr(riga, campo, valore_convertito)
        riga.save(update_fields=[campo])

        return JsonResponse({"ok": True})


    except Exception as e:

        print("=" * 80)

        print("ERRORE AGGIORNAMENTO CELLA")

        print("campo =", campo)

        print("valore =", repr(valore))

        print("errore =", str(e))

        print("=" * 80)

        return JsonResponse(

            {

                "ok": False,

                "errore": str(e)

            },

            status=400

        )

def esporta_importazioni_excel(request):
    wb = Workbook()
    ws = wb.active
    ws.title = "Importazioni"

    ws.append(CAMPI_TABELLA)

    righe = OrdineImportazione.objects.all().order_by("id")

    for riga in righe:
        ws.append([
            getattr(riga, campo) for campo in CAMPI_TABELLA
        ])

    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = 'attachment; filename="importazioni.xlsx"'

    wb.save(response)
    return response

def esporta_importazioni_excel_filtrato(request):
    righe = get_queryset_importazioni(request)

    wb = Workbook()
    ws = wb.active
    ws.title = "Importazioni filtrate"

    ws.append([titolo for campo, titolo in COLONNE])

    for riga in righe:
        ws.append([
            getattr(riga, campo, "")
            for campo, titolo in COLONNE
        ])

    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = 'attachment; filename="importazioni_filtrate.xlsx"'

    wb.save(response)
    return response

@require_POST
def crea_acconto(request):
    ordine_id = request.POST.get("ordine_id")

    ordine = get_object_or_404(OrdineImportazione, id=ordine_id)

    acconto = Acconto.objects.create(
        ordine_importazione=ordine,
        valore_usd=0
    )

    return JsonResponse({
        "ok": True,
        "id": acconto.id,
    })


@require_POST
def aggiorna_acconto(request):
    acconto_id = request.POST.get("id")
    campo = request.POST.get("campo")
    valore = request.POST.get("valore", "").strip()

    if campo not in ["data", "banca", "valore_usd"]:
        return JsonResponse({"ok": False, "errore": "Campo acconto non valido"}, status=400)

    acconto = get_object_or_404(Acconto, id=acconto_id)

    try:
        if valore == "":
            valore_convertito = None
        elif campo == "valore_usd":
            valore_convertito = Decimal(valore.replace(",", "."))
        elif campo == "data":
            valore_convertito = parse_data(valore)
        else:
            valore_convertito = valore

        setattr(acconto, campo, valore_convertito)
        acconto.save(update_fields=[campo])

        return JsonResponse({"ok": True})

    except Exception as e:
        return JsonResponse({"ok": False, "errore": str(e)}, status=400)


@require_POST
def elimina_acconto(request):
    acconto_id = request.POST.get("id")

    acconto = get_object_or_404(Acconto, id=acconto_id)
    acconto.delete()

    return JsonResponse({"ok": True})


from django.http import HttpResponse
from django.shortcuts import get_object_or_404

from .models import OrdineImportazione


def valore(v):
    if v is None:
        return ""
    return str(v)


def stampa_dettaglio(request, ordine_id):
    ordine = get_object_or_404(
        OrdineImportazione.objects.prefetch_related("acconti"),
        id=ordine_id
    )

    testo = f"""
    DETTAGLIO IMPORTAZIONE 
    
    ====================
    MRN
    ====================
    {valore(ordine.ader_MRN_codice)}
    
    
    ====================
    ARRIVO
    ====================
    Anno arrivo: {valore(ordine.arrivo_anno)}
    Data arrivo: {valore(ordine.arrivo_data)}
    
    
    ====================
    FATTURA MERCE
    ====================
    Ragione sociale: {valore(ordine.ft_merce_fornit_ragione_sociale)}
    Numero fattura: {valore(ordine.ft_merce_num)}
    Data fattura: {valore(ordine.ft_merce_data)}
    Totale pezzi: {valore(ordine.ft_merce_tot_pz)}
    Valore USD: {valore(ordine.ft_valore_usd)}
    
    
    ====================
    FATTURA DAZI / IVA
    ====================
    Ragione sociale: {valore(ordine.ft_dazi_iva_ragione_sociale)}
    IVA euro: {valore(ordine.ft_dazi_iva_iva_euro)}
    Dazio euro: {valore(ordine.ft_dazi_iva_dazio_euro)}
    Costi accessori euro: {valore(ordine.ft_dazi_iva_costi_accessori_euro)}
    Totale euro: {valore(ordine.ft_dazi_iva_totale)}
    Nostro prot. N.: {valore(ordine.ft_dazi_iva_totale_nostro_prot_numero)}
    """

    if (ordine.nolo_se_prepagato_in_ft_usd or Decimal("0")) > Decimal("0.00"):
        testo += f"""
        
    ====================
    NOLO IMPORT SE PREPAGATO IN FATTURA
    ====================
    Nolo prepagato in fattura USD: {valore(ordine.nolo_se_prepagato_in_ft_usd)}
    """

    if (ordine.nolo_ft_totale or Decimal("0")) > Decimal("0.00"):
        testo += f"""
        
    ====================
    FATTURA NOLO IMPORT (NON PREPAGATO)
    ====================
    Vettore: {valore(ordine.nolo_vettore_nome)}
    Totale fattura nolo: {valore(ordine.nolo_ft_totale)}
    Nostro prot. N.: {valore(ordine.nolo_ft_nostro_prot_numero)}
    """

    testo += f"""
    
    ====================
    NOTE
    ====================
    {valore(ordine.note)}
    """

    response = HttpResponse(testo, content_type="text/plain; charset=utf-8")
    response["Content-Disposition"] = f'inline; filename="ordine_importazione_{ordine.id}.txt"'
    return response