from django.db import models
from django.utils import timezone
from decimal import Decimal

class OrdineImportazione(models.Model):
    # ordine
    ordine_data = models.DateField(default=timezone.now, null=True, blank=True)
    ordine_fornitore_sigla = models.CharField(max_length=2, null=True, blank=True)
    ordine_nome_fornitore = models.CharField(max_length=50, null=True, blank=True)
    ordine_descrizione = models.CharField(max_length=50, null=True,blank=True)
    ordine_num_pezzi = models.PositiveIntegerField(default=0, null=True, blank=True)
    ordine_preventivo_dollari = models.DecimalField(max_digits=10, decimal_places=2, default=0, null=True, blank=True)
    ordine_proforma_arrivata_dollari = models.DecimalField(max_digits=10, decimal_places=2, default=0, null=True, blank=True)
    ordine_preventivi_nolo_import = models.TextField(null=True, blank=True)
    ordine_confermata_spedizione_con_spedizioniere = models.CharField(max_length=30, null=True, blank=True)

    # arrivo
    arrivo_anno = models.PositiveIntegerField(null=True, blank=True)
    arrivo_data = models.DateField(null=True, blank=True)
    arrivo_num = models.PositiveIntegerField(null=True, blank=True)

    # fattura dazi iva
    ft_dazi_iva_ragione_sociale = models.CharField(max_length=30, null=True, blank=True)
    ft_dazi_iva_iva_euro = models.DecimalField(max_digits=10, decimal_places=2, default=0, null=True, blank=True)
    ft_dazi_iva_dazio_euro = models.DecimalField(max_digits=10, decimal_places=2, default=0, null=True, blank=True)
    ft_dazi_iva_costi_accessori_euro = models.DecimalField(max_digits=10, decimal_places=2, default=0, null=True, blank=True)
    ft_dazi_iva_totale = models.DecimalField(max_digits=10, decimal_places=2, default=0, null=True, blank=True)
    ft_dazi_iva_totale_nostro_prot_numero = models.CharField(max_length=10, null=True, blank=True)

    # fattura fornitore
    ft_merce_fornit_sigla = models.CharField(max_length=2, null=True, blank=True)
    ft_merce_fornit_ragione_sociale = models.CharField(max_length=50, null=True, blank=True)
    ft_merce_num = models.CharField(max_length=30, null=True, blank=True)
    ft_merce_data = models.DateField(null=True, blank=True)
    ft_merce_tot_pz = models.PositiveIntegerField(default=0, null=True, blank=True)
    ft_valore_usd = models.DecimalField(max_digits=10, decimal_places=2, default=0, null=True, blank=True)

    # nolo import
    nolo_se_prepagato_in_ft_usd = models.DecimalField(max_digits=10, decimal_places=2, default=0, null=True, blank=True)
    nolo_vettore_nome = models.CharField(max_length=30, null=True, blank=True)
    nolo_ft_totale = models.DecimalField(max_digits=10, decimal_places=2, default=0, null=True, blank=True)
    nolo_ft_nostro_prot_numero = models.CharField(max_length=10, null=True, blank=True)


    # ader
    ader_bolla_doganale_classica = models.BooleanField(default=False)
    ader_MRN_codice = models.CharField(max_length=30, null=True, blank=True)
    ader_stampato_mrn_da_ader = models.BooleanField(default=False)
    ader_nostro_prot_num = models.CharField(max_length=6, null=True, blank=True)

    # note
    note = models.TextField(null=True, blank=True)

    @property
    def totale_acconti_usd(self):
        return sum(
            (a.valore_usd or Decimal("0"))
            for a in self.acconti.all()
        )

    @property
    def stato_acconti(self):

        proforma = self.ordine_proforma_arrivata_dollari or Decimal("0")
        pagato = self.totale_acconti_usd

        differenza = pagato - proforma

        if differenza == 0:
            return "Saldo completo"

        if differenza < 0:
            return f"Residuo da saldare $ {abs(differenza):.2f}"

        return f"Pagato $ {differenza:.2f} in eccedenza"

    def __str__(self):
        return f"Ordine importazione {self.id} - {self.ordine_nome_fornitore or ''}"

    class Meta:
        verbose_name_plural = "Righe Ordini Importazioni"


class Acconto(models.Model):
    ordine_importazione = models.ForeignKey(
        OrdineImportazione,
        on_delete=models.CASCADE,
        related_name="acconti"
    )

    valore_usd = models.DecimalField(max_digits=10, decimal_places=2, default=0, null=True, blank=True)
    data = models.DateField(default=timezone.now, null=True, blank=True)
    banca = models.CharField(max_length=3, blank=True, null=True)

    def __str__(self):
        return f"Acconto {self.valore_usd} USD - {self.banca or ''}"

    class Meta:
        verbose_name_plural = "Acconti"



