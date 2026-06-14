from decimal import Decimal
from datetime import date
from trasporti.models import Supplemento


def build_supplementi_finali(request, form):
    """
    SELECTOR UNICO DI VERITÀ

    Responsabilità:
    - raccoglie checkbox utente
    - aggiunge ASSIC automatico
    - aggiunge CONTR automatico
    - aggiunge PEAK season automatico

    OUTPUT:
    lista ID supplementi coerente per engine
    """

    # =========================================================
    # 1. SUPPLEMENTI SELEZIONATI DALL’UTENTE
    # =========================================================
    ids = request.POST.getlist("supplementi_selezionati")
    ids = [int(i) for i in ids if str(i).isdigit()]

    # =========================================================
    # 2. VALORI COMMERCIALI
    # =========================================================
    valore_merce = form.cleaned_data.get("valore_merce") or Decimal("0")
    valore_contrassegno = form.cleaned_data.get("valore_contrassegno") or Decimal("0")

    # =========================================================
    # 3. DATA SPEDIZIONE
    # =========================================================
    data_spedizione = form.cleaned_data.get("data")

    # =========================================================
    # 4. ASSIC (se valore merce > 0)
    # =========================================================
    if valore_merce > 0:
        assic = Supplemento.objects.filter(
            tipo_servizio__codice="ASSIC"
        ).first()

        if assic and assic.id not in ids:
            ids.append(assic.id)

    # =========================================================
    # 5. CONTR (se contrassegno > 0)
    # =========================================================
    if valore_contrassegno > 0:
        contr = Supplemento.objects.filter(
            tipo_servizio__codice="CONTR"
        ).first()

        if contr and contr.id not in ids:
            ids.append(contr.id)

    # =========================================================
    # 6. PEAK SEASON (range date)
    # =========================================================
    if data_spedizione:
        peak_supplementi = Supplemento.objects.filter(
            tipo_servizio__codice="PEAKS"
        )

        for peak in peak_supplementi:
            if peak.valid_from and peak.valid_to:
                if peak.valid_from <= data_spedizione <= peak.valid_to:
                    if peak.id not in ids:
                        ids.append(peak.id)

    # =========================================================
    # 7. RETURN FINALE
    # =========================================================
    return ids