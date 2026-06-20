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
            "contrassegno_euro",
            "assicurazione_euro",
        ]

        widgets = {
            "data": forms.DateInput(attrs={"type": "date"})
        }



'''PaccoFormSet = inlineformset_factory(
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
)'''




class PaccoForm(forms.ModelForm):
    class Meta:
        model = Pacco
        fields = [
            "altezza_cm",
            "larghezza_cm",
            "profondita_cm",
            "peso_kg",
        ]

        '''widgets = {
            "altezza_cm": forms.NumberInput(attrs={
                "class": "form-control form-control-sm d-inline-block",
                "style": "width: 5ch;",
            }),
            "larghezza_cm": forms.NumberInput(attrs={
                "class": "form-control form-control-sm d-inline-block",
                "style": "width: 5ch;",
            }),
            "profondita_cm": forms.NumberInput(attrs={
                "class": "form-control form-control-sm d-inline-block",
                "style": "width: 5ch;",
            }),
            "peso_kg": forms.NumberInput(attrs={
                "class": "form-control form-control-sm d-inline-block",
                "style": "width: 5ch;",
            }),
        }'''

PaccoFormSet = inlineformset_factory(
    Spedizione,
    Pacco,
    form=PaccoForm,
    extra=10,
    can_delete=False
)
