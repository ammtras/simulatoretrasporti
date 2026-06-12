from django import forms
from django.forms import inlineformset_factory
from .models import Spedizione, Pacco
from django.utils import timezone


class SpedizioneForm(forms.ModelForm):
    class Meta:
        model = Spedizione
        fields = [
            "data",
            "da_cliente_citta",
            "a_cliente_citta",
            "da_zona",
            "a_zona",
            "zona_tariffazione_spedizioniere",
            "contrassegno_euro",
            "assicurazione_euro",
            "se_triangolazione",
        ]

        widgets = {
            "data": forms.DateInput(attrs={"type": "date"})
        }



PaccoFormSet = inlineformset_factory(
    Spedizione,
    Pacco,
    fields=[
        "altezza_cm",
        "larghezza_cm",
        "profondita_cm",
        "peso_kg"
    ],
    extra=10,   # 👈 10 righe vuote
    can_delete=True
)