from django.urls import path
from .views import *

urlpatterns = [
    path('', crea_spedizione, name='crea_spedizione'),
    path('login', loggin, name='login'),
    path('logout', loggout, name='logout'),
]