# import_prc/urls.py

from django.urls import path
from importPRC.views import *

app_name = "importPRC"

urlpatterns = [
    path("", tabella_importazioni, name="tabella_importazioni"),
    path("crea-riga/", crea_riga_importazione, name="crea_riga_importazione"),
    path("aggiorna-cella/", aggiorna_cella_importazione, name="aggiorna_cella_importazione"),
    path("export-excel/", esporta_importazioni_excel, name="esporta_importazioni_excel"),
    path("export-excel-filtrato/", esporta_importazioni_excel_filtrato, name="esporta_importazioni_excel_filtrato"),
    path("crea-acconto/", crea_acconto, name="crea_acconto"),
    path("aggiorna-acconto/", aggiorna_acconto, name="aggiorna_acconto"),
    path("elimina-acconto/", elimina_acconto, name="elimina_acconto"),
    path("stampa-dettaglio/<int:ordine_id>/", stampa_dettaglio, name="stampa_dettaglio"),

    ]