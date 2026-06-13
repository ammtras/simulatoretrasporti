from django.db import models
from django.utils import timezone



class Zona(models.Model):
    nome = models.CharField(max_length=200)
    def __str__(self):
        return self.nome

    class Meta:
        verbose_name_plural = 'Zone'


class Spedizioniere(models.Model):

    A_SCAGLIONI = "scaglioni"
    A_COLLO = "collo"

    TARIFFAZIONI = [
        (A_SCAGLIONI, "Scaglioni"),
        (A_COLLO, "A collo"),
    ]

    nome = models.CharField(max_length=100)
    tipo_tariffazione = models.CharField(max_length=20, choices=TARIFFAZIONI, default=A_SCAGLIONI)

    def __str__(self):
        return self.nome

    class Meta:
        verbose_name_plural = "Spedizionieri"


#zona tariffazione spedizioniere
class Zona_spedizioniere(models.Model):
    nome = models.CharField(max_length=200, null=True, blank=True)
    spedizioniere = models.ForeignKey(Spedizioniere, on_delete=models.CASCADE)
    # 🟢 UN UNICO CAMPO PER TUTTE LE ZONE ABILITATE (Sia partenza che arrivo)
    zona = models.ManyToManyField(
        Zona,
        related_name="zone_tariffazione_spedizionieri",
        help_text="Seleziona le zone che sono servite questa tariffa"
    )
    divisore_volumetrico = models.IntegerField(default=5000)
    peso_minimo_fatturabile = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    contrassegno_allowed = models.BooleanField(default=False)

    def __str__(self):
        # Uniamo i nomi di tutte le zone associate (es: "Italia, Spagna")
        nomi_zone = ", ".join([z.nome for z in self.zona.all()])
        return f"{self.spedizioniere} | TARIFFA {self.nome} (ID {self.id})| ZONE: [{nomi_zone}]"

    class Meta:
        verbose_name_plural = "Zone Tariffazione Spedizionieri"

class TipoServizio(models.Model):
    # Un codice univoco che userai nel codice Python
    codice = models.CharField(max_length=50, unique=True) # es: 'ASSICURAZIONE', 'CONTRASSEGNO', 'ZTL'
    nome = models.CharField(max_length=100) # es: "Assicurazione Merce", "Contrassegno"

    def __str__(self):
        return self.nome


class MappaturaZonaTariffaria(models.Model):
    stato_partenza = models.CharField(max_length=100, help_text="Es: Italia")
    stato_destinazione = models.CharField(max_length=100, help_text="Es: Spagna, Svizzera, Italia")
    # La zona geografica astratta a cui corrisponde questa combinazione di Stati
    zona_corrispondente = models.ForeignKey(Zona, on_delete=models.CASCADE,related_name="mappature_tariffarie")

    class Meta:
        verbose_name = "Mappatura Zona Tariffaria"
        verbose_name_plural = "Mappature Zone Tariffarie"

    def __str__(self):
        return f"{self.stato_partenza} ➡️ {self.stato_destinazione} = {self.zona_corrispondente.nome}"
class Spedizione(models.Model):
    #data = models.DateField(default=timezone.now)
    data = models.DateField(default=timezone.now)
    da_cliente_citta = models.CharField(max_length=200)
    a_cliente_citta = models.CharField(max_length=200)
    da_zona = models.ForeignKey(Zona, on_delete=models.CASCADE, related_name="dazona")
    a_zona = models.ForeignKey(Zona, on_delete=models.CASCADE, related_name="a_zona")
    zona_tariffazione_spedizioniere = models.ForeignKey(
        Zona_spedizioniere,
        on_delete=models.SET_NULL,  # Evita cancellazioni a cascata delle spedizioni
        null=True,  # Permette al record di non avere una tariffa durante la simulazione
        blank=True,  # Permette di salvare il form senza questo campo inizialmente
        related_name="spedizioni"  # Un related_name più pulito e leggibile
    )
    servizi_richiesti = models.ManyToManyField(TipoServizio, blank=True)
    contrassegno_euro = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    assicurazione_euro = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    trasportatore_scelto = models.ForeignKey(Spedizioniere,on_delete=models.CASCADE,null=True, blank=True)
    valore_preventivo = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    def __str__(self):
        return f" {self.data} da cliente città {self.da_cliente_citta} a {self.a_cliente_citta}"

    class Meta:
        verbose_name_plural = 'Spedizioni'

class Pacco(models.Model):
    altezza_cm = models.DecimalField(max_digits=6, decimal_places=2)
    larghezza_cm = models.DecimalField(max_digits=6, decimal_places=2)
    profondita_cm = models.DecimalField(max_digits=6, decimal_places=2)
    peso_kg = models.DecimalField(max_digits=6, decimal_places=2)
    spedizione = models.ForeignKey(Spedizione, on_delete=models.CASCADE, related_name="pacchi")
    def __str__(self):
        return f"Pacco {self.altezza_cm}x{self.larghezza_cm}x{self.profondita_cm} Kg {self.peso_kg}"

    class Meta:
        verbose_name_plural = 'Pacchi'

class Scaglione(models.Model):
    spedizioniere = models.ForeignKey(Spedizioniere, on_delete=models.CASCADE,null=True)
    zona = models.ForeignKey(Zona, on_delete=models.CASCADE,null=True)
    zona_spedizioniere = models.ForeignKey(Zona_spedizioniere, on_delete=models.CASCADE)
    min_weight = models.DecimalField(max_digits=8,decimal_places=2)
    max_weight = models.DecimalField(max_digits=8,decimal_places=2)
    price = models.DecimalField(max_digits=10,decimal_places=2)
    valid_from = models.DateField(default=timezone.now)
    valid_to = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"{self.spedizioniere} | da {self.min_weight} a {self.max_weight} | {self.zona_spedizioniere} | dal {self.valid_from} a {self.valid_to} |  € {self.price}  "

    class Meta:
        verbose_name_plural = "Scaglioni"

class OverflowTariff(models.Model):
    zona_spedizioniere = models.ForeignKey(Zona_spedizioniere, on_delete=models.CASCADE)
    step_kg = models.DecimalField(max_digits=8,decimal_places=2)
    price_per_step = models.DecimalField(max_digits=8,decimal_places=2)
    valid_from = models.DateField(default=timezone.now)
    valid_to = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"{self.zona_spedizioniere} | ogni {self.step_kg} Kg € {self.price_per_step}"

    class Meta:
        verbose_name_plural = "Tariffe extra soglia (non in scaglioni)"


class Supplemento(models.Model):

    tipo_servizio = models.ForeignKey(
        TipoServizio,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='supplementi_corrieri'
    )

    FIXED = "fisso"
    PERCENTAGE = "percentuale"
    ACOLLO = "a collo"
    ASPEDIZIONE = "a spedizione"

    TYPES = [
        (FIXED, "fisso"),
        (PERCENTAGE, "percentuale"),
    ]

    APPLICAZIONE = [
        (ACOLLO, "a collo"),
        (ASPEDIZIONE, "a spedizione"),
    ]

    # 🟢 RELAZIONE MANY-TO-MANY: Lega il supplemento a una o più zone
    zone_tariffazione = models.ManyToManyField(
        Zona_spedizioniere,
        related_name='supplementi',
        blank=True,
        help_text="Seleziona le zone in cui questo supplemento è applicabile. Se vuoto, non verrà applicato."
    )

    nome = models.CharField(max_length=200)
    calc_type = models.CharField(max_length=28,choices=TYPES)
    applic_type = models.CharField(max_length=28,choices=APPLICAZIONE)
    valore = models.DecimalField(max_digits=10,decimal_places=2)
    applica_fuel = models.BooleanField(default=True)
    valid_from = models.DateField(default=timezone.now)
    valid_to = models.DateField(null=True, blank=True)

    def __str__(self):
        return f" {self.nome} | dal {self.valid_from} a {self.valid_to} | {self.applic_type} | {self.calc_type} | {self.valore}  "


    class Meta:
        verbose_name_plural = "Supplementi"



