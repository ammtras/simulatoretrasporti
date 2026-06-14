from django.contrib import admin
from .models import *

class PaccoInline(admin.TabularInline):
    model = Pacco
    extra = 0

@admin.register(Spedizione)
class SpedizioneAdmin(admin.ModelAdmin):
    list_display = ("da_cliente_citta", "a_cliente_citta", "data")
    inlines = [PaccoInline]
    readonly_fields = ['valore_preventivo','trasportatore_scelto','zona_tariffazione_spedizioniere']


admin.site.register(Zona)
admin.site.register(Spedizioniere)
admin.site.register(Zona_spedizioniere)
admin.site.register(Scaglione)
admin.site.register(Supplemento)
admin.site.register(OverflowTariff)
admin.site.register(TipoServizio)


