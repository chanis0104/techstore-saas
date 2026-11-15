from django.contrib import admin
from django.urls import path
from boutique import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.accueil, name='accueil'),
    path('inscription/', views.inscription_vendeur, name='inscription'),
    path('connexion/', views.connexion_vendeur, name='connexion'),
    path('deconnexion/', views.deconnexion_vendeur, name='deconnexion'),
    path('vendeur/', views.tableau_bord_vendeur, name='vendeur'),
    path('b/<slug:boutique_slug>/', views.catalogue_boutique, name='catalogue'),
    path('assistant-ia/', views.assistant_ia_vue, name='assistant_ia'),
]