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
    spedizioniere = models.ForeignKey(Spedizioniere, on_delete=models.CASCADE)
    zona = models.ForeignKey(Zona, on_delete=models.CASCADE)
    divisore_volumetrico = models.IntegerField(default=5000)
    peso_minimo_fatturabile = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    contrassegno_allowed = models.BooleanField(default=False)


    def __str__(self):
        return f"ZONA TARIFFAZIONE {self.spedizioniere} {self.zona} "

    class Meta:
        verbose_name_plural = "Zone Tariffazione Spedizionieri"
        unique_together = ("spedizioniere", "zona")

class Spedizione(models.Model):
    #data = models.DateField(default=timezone.now)
    data = models.DateField(default=timezone.now)
    da_cliente_citta = models.CharField(max_length=200)
    a_cliente_citta = models.CharField(max_length=200)
    da_zona = models.ForeignKey(Zona, on_delete=models.CASCADE, related_name="dazona")
    a_zona = models.ForeignKey(Zona, on_delete=models.CASCADE, related_name="a_zona")
    zona_tariffazione_spedizioniere = models.ForeignKey(Zona_spedizioniere,on_delete=models.CASCADE,related_name="zona_tariffazione_spedizioniere")
    se_triangolazione =models.BooleanField(default=False)
    contrassegno_euro = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    assicurazione_euro = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    peso_totale_kg = models.DecimalField(max_digits=10, decimal_places=2, default=0)
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

    spedizioniere = models.ForeignKey(Spedizioniere, on_delete=models.CASCADE)
    nome = models.CharField(max_length=200)
    calc_type = models.CharField(max_length=28,choices=TYPES)
    applic_type = models.CharField(max_length=28,choices=APPLICAZIONE)
    valore = models.DecimalField(max_digits=10,decimal_places=2)
    applica_fuel = models.BooleanField(default=True)
    valid_from = models.DateField(default=timezone.now)
    valid_to = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"{self.spedizioniere} | {self.nome} | dal {self.valid_from} a {self.valid_to} | {self.applic_type} | {self.calc_type} | {self.valore}  "


    class Meta:
        verbose_name_plural = "Supplementi"



