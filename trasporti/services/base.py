from django.db.models import Q
from trasporti.models import Supplemento

class TariffValidityService:

    @staticmethod
    def filtra_validita(queryset, data):
        return queryset.filter(
            valid_from__lte=data
        ).filter(
            Q(valid_to__gte=data) | Q(valid_to__isnull=True)
        )






