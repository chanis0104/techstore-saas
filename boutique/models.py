import re
from django.db import models
from django.contrib.auth.models import User
from django.utils.text import slugify


class ProfilBoutique(models.Model):
    SECTEURS = [
        ('MODE', '1. Mode et Accessoires'),
        ('BEAUTE', '2. Soins, Beauté et Cosmétiques'),
        ('TELECOM', '3. Télécom, High-Tech et Électronique'),
        ('MAISON', '4. Maison, Décoration et Électroménager'),
        ('SANTE', '5. Santé et Bien-être'),
        ('BEBE', '6. Bébé, Enfant et Puériculture'),
        ('SPORT', '7. Sport et Loisirs'),
        ('ALIMENTATION', '8. Alimentation et Boissons'),
        ('AUTO_BRICO', '9. Auto, Moto et Bricolage'),
        ('IMMO_SERVICES', '10. Immobilier et Services'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    nom = models.CharField(max_length=150)
    secteur = models.CharField(max_length=50, choices=SECTEURS, default='TELECOM')
    slug = models.SlugField(unique=True, blank=True)
    whatsapp = models.CharField(max_length=30, blank=True)
    infos_livraison = models.TextField(blank=True)
    date_creation = models.DateTimeField(auto_now_add=True)

    def whatsapp_clean(self):
        """Retourne uniquement les chiffres avec l'indicatif pays pour wa.me"""
        if not self.whatsapp:
            return ""
        chiffres = re.sub(r'\D', '', self.whatsapp)
        if len(chiffres) == 9 and chiffres.startswith('6'):
            return f"237{chiffres}"
        return chiffres

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
        return f"{self.nom} ({self.get_secteur_display()})"


class Produit(models.Model):
    CATEGORIES = [
        ('1. Mode et Accessoires', (
            ('MODE_VETEMENTS', 'Vêtements'),
            ('MODE_CHAUSSURES', 'Chaussures'),
            ('MODE_MAROQUINERIE', 'Maroquinerie'),
            ('MODE_BIJOUX', 'Bijoux et Montres'),
        )),
        ('2. Soins, Beauté et Cosmétiques', (
            ('BEAUTE_VISAGE', 'Soins du visage'),
            ('BEAUTE_CORPS', 'Soins du corps'),
            ('BEAUTE_CAPILLAIRE', 'Soins capillaires'),
            ('BEAUTE_MAQUILLAGE', 'Maquillage'),
            ('BEAUTE_PARFUMERIE', 'Parfumerie'),
            ('BEAUTE_ACCESSOIRES', 'Accessoires beauté'),
        )),
        ('3. Télécom, High-Tech et Électronique', (
            ('SMART_PHONE', 'Téléphonie et Tablettes'),
            ('ACCESSOIRE', 'Accessoires télécom'),
            ('PC', 'Informatique'),
            ('TECH_AUDIO_VIDEO', 'Audio et Vidéo'),
            ('TECH_CONNECTES', 'Objets connectés'),
            ('RESEAU', 'Routeurs & Réseau'),
        )),
        ('4. Maison, Décoration et Électroménager', (
            ('MAISON_MEUBLES', 'Ameublement'),
            ('MAISON_DECO', 'Décoration'),
            ('MAISON_CUISINE', 'Cuisine et Arts de la table'),
            ('MAISON_ELECTRO', 'Électroménager'),
            ('MAISON_LINGE', 'Linge de maison'),
        )),
        ('5. Santé et Bien-être', (
            ('SANTE_COMPLEMENTS', 'Compléments alimentaires'),
            ('SANTE_BUCCO', 'Hygiène bucco-dentaire'),
            ('SANTE_MEDICAL', 'Matériel médical et paramédical'),
        )),
        ('6. Bébé, Enfant et Puériculture', (
            ('BEBE_VETEMENTS', 'Vêtements bébé et enfant'),
            ('BEBE_SORTIE', 'Équipement et Sortie'),
            ('BEBE_REPAS', 'Repas et Hygiène'),
            ('BEBE_JEUX', 'Jeux et Jouets'),
        )),
        ('7. Sport et Loisirs', (
            ('SPORT_EQUIPEMENT', 'Équipement sportif'),
            ('SPORT_VETEMENTS', 'Vêtements de sport'),
            ('SPORT_CAMPING', 'Camping et Randonnée'),
        )),
        ('8. Alimentation et Boissons', (
            ('ALIM_EPICERIE', 'Épicerie salée et sucrée'),
            ('ALIM_BOISSONS', 'Boissons'),
            ('ALIM_SPECIALISES', 'Produits spécialisés'),
        )),
        ('9. Auto, Moto et Bricolage', (
            ('AUTO_MOTO', 'Accessoires auto et moto'),
            ('BRICO_OUTILLAGE', 'Outillage et Bricolage'),
            ('JARDIN_EXTERIEUR', 'Jardin et Extérieur'),
        )),
        ('10. Immobilier et Services', (
            ('IMMOBILIER', 'Immobilier (Vente & Location)'),
            ('SERVICES_NUMERIQUES', 'Services et Produits numériques'),
        )),
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
