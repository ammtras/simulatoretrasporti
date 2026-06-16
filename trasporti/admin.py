from django.contrib import admin
from trasporti.models import *

class PaccoInline(admin.TabularInline):
    model = Pacco
    extra = 0

@admin.register(Spedizione)
class SpedizioneAdmin(admin.ModelAdmin):
    list_display = ("da_cliente_citta", "a_cliente_citta", "data")
    inlines = [PaccoInline]
    readonly_fields = ['valore_preventivo','trasportatore_scelto','zona_tariffazione_spedizioniere']

def spedizioniere_display(self, obj):
    prima_zona = obj.zone_tariffazione.first()
    return prima_zona.spedizioniere.nome if prima_zona else "-"

class SpedizioniereFilter(admin.SimpleListFilter):
    title = "Spedizioniere"
    parameter_name = "spedizioniere"

    def lookups(self, request, model_admin):
        return [
            (s.id, s.nome)
            for s in Spedizioniere.objects.all().order_by("nome")
        ]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(
                zone_tariffazione__spedizioniere_id=self.value()
            ).distinct()

        return queryset

@admin.register(Supplemento)
class SupplementoAdmin(admin.ModelAdmin):
    list_display = (
        "spedizioniere_nome",
        "nome",
        "tipo_servizio_codice",
        "applic_type",
        "calc_type",
        "valore",
        "diritto_minimo_euro",
        "applica_fuel",
        "valid_from",
        "valid_to",
    )

    list_filter = (
        SpedizioniereFilter,
        "zone_tariffazione",
        "tipo_servizio",
        "applic_type",
        "calc_type",
        "applica_fuel",
    )

    def spedizioniere_nome(self, obj):
        spedizionieri = (
            obj.zone_tariffazione
            .values_list("spedizioniere__nome", flat=True)
            .distinct()
        )

        return ", ".join(spedizionieri)

    def tipo_servizio_codice(self, obj):
        return obj.tipo_servizio.codice if obj.tipo_servizio else "-"

    tipo_servizio_codice.short_description = "Tipo servizio"

    spedizioniere_display.short_description = "Spedizioniere"





admin.site.register(Tariffa_colli)
admin.site.register(Zona)
admin.site.register(Zona_spedizioniere)
admin.site.register(Spedizioniere)
admin.site.register(Scaglione)
admin.site.register(OverflowTariff)
admin.site.register(TipoServizio)


