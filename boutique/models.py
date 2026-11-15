import re
from django.db import models
from django.contrib.auth.models import User
from django.utils.text import slugify


class ProfilBoutique(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    nom = models.CharField(max_length=150)
    slug = models.SlugField(unique=True, blank=True)
    whatsapp = models.CharField(max_length=30, blank=True)
    infos_livraison = models.TextField(blank=True)
    date_creation = models.DateTimeField(auto_now_add=True)

    def whatsapp_clean(self):
        """Retourne uniquement les chiffres du numéro WhatsApp pour wa.me"""
        if not self.whatsapp:
            return ""
        return re.sub(r'\D', '', self.whatsapp)

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.nom)
            slug = base_slug
            counter = 1
            while ProfilBoutique.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nom


class Produit(models.Model):
    CATEGORIES = [
        ('SMART_PHONE', 'Téléphones & Tablettes'),
        ('PC', 'Ordinateurs & Laptops'),
        ('ACCESSOIRE', 'Accessoires & Chargeurs'),
        ('RESEAU', 'Routeurs & Réseau'),
    ]
    boutique = models.ForeignKey(ProfilBoutique, on_delete=models.CASCADE, related_name='produits')
    nom = models.CharField(max_length=200)
    categorie = models.CharField(max_length=50, choices=CATEGORIES, default='SMART_PHONE')
    prix = models.CharField(max_length=100)  # Ex: "220 000 FCFA"
    stock = models.PositiveIntegerField(default=1)
    caracteristiques = models.TextField()
    image_base64 = models.TextField(blank=True, null=True)
    date_ajout = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.nom} ({self.boutique.nom})"


class Reservation(models.Model):
    produit = models.ForeignKey(Produit, on_delete=models.CASCADE, related_name='reservations')
    date_reservation = models.DateTimeField(auto_now_add=True)
    traitee = models.BooleanField(default=False)

    def __str__(self):
        return f"Réservation #{self.id} - {self.produit.nom}"