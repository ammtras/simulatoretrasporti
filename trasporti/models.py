from django.db import models
from django.utils import timezone
from datetime import date



class Zona(models.Model):
    nome = models.CharField(max_length=200)
    def __str__(self):
        return self.nome

    class Meta:
        verbose_name_plural = 'Zone'


class Spedizione(models.Model):
    #data = models.DateField(default=timezone.now)
    data = models.DateField(default=date.today())
    da_cliente_citta = models.CharField(max_length=200)
    a_cliente_citta = models.CharField(max_length=200)
    da_zona = models.ForeignKey(Zona, on_delete=models.CASCADE, related_name="dazona")
    a_zona = models.ForeignKey(Zona, on_delete=models.CASCADE, related_name="a_zona")
    se_triangolazione =models.BooleanField(default=False)
    contrassegno_euro = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    assicurazione_euro = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    peso_totale_kg = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    trasportatore_scelto = models.CharField(max_length=100, null=True, blank=True)
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






