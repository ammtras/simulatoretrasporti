from django.db import models

class Zona(models.Model):
    nome = models.CharField(max_length=200)
    class Meta:
        verbose_name_plural = 'Zone'


class Spedizione(models.Model):
    da_cliente_citta = models.CharField(max_length=200)
    a_cliente_citta = models.CharField(max_length=200)
    da_zona = models.ForeignKey(Zona, on_delete=models.CASCADE, related_name="dazona")
    a_zona = models.ForeignKey(Zona, on_delete=models.CASCADE, related_name="a_zona")
    se_triangolazione =models.BooleanField(default=False)

    def __str__(self):
        return f"da cliente città {self.da_cliente_citta} a {self.a_cliente_citta}"

class Pacco(models.Model):
    altezza_cm = models.DecimalField(max_digits=6, decimal_places=2)
    larghezza_cm = models.DecimalField(max_digits=6, decimal_places=2)
    profondita_cm = models.DecimalField(max_digits=6, decimal_places=2)
    peso_kg = models.DecimalField(max_digits=6, decimal_places=2)
    spedizione = models.ForeignKey(Spedizione, on_delete=models.CASCADE, related_name="pacchi")
    def __str__(self):
        return f"Pacco {self.altezza_cm}x{self.larghezza_cm}x{self.profondita_cm} Kg {self.peso_kg}"






