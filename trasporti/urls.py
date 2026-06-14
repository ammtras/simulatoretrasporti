from django.urls import path
from .views import *

urlpatterns = [
    path('', loggin, name='login'),
    path('loggin', loggin, name='login'),
    path('crea_spedizione', crea_spedizione, name='crea_spedizione'),
    path('logout', loggout, name='logout'),
    path("spedizioni/", spedizioni.as_view(), name="spedizioni"),
    path("controllo_tariffe",controllo_tariffe, name="controllo_tariffe" ),

]