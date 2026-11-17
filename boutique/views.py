import base64
import json
import re
import io
import time
from PIL import Image
from google import genai
from google.genai import types
from django.conf import settings
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.core.paginator import Paginator
from django.core.cache import cache
from django.db.models import F
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from .models import ProfilBoutique, Produit, Reservation


def alleger_image_b64(image_file):
    """Compresse et redimensionne automatiquement l'image en JPEG léger pour économiser la RAM."""
    try:
        img = Image.open(image_file)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        img.thumbnail((800, 800))
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=75, optimize=True)
        encoded = base64.b64encode(buffer.getvalue()).decode('utf-8')
        return f"data:image/jpeg;base64,{encoded}"
    except Exception:
        try:
            image_file.seek(0)
            encoded = base64.b64encode(image_file.read()).decode('utf-8')
            return f"data:{image_file.content_type};base64,{encoded}"
        except Exception:
            return ""


def accueil(request):
    """Gère l'arrivée sur la racine du site (/) en excluant la boutique admin."""
    if request.user.is_authenticated and not request.user.is_superuser:
        return redirect("vendeur")
        
    boutiques = ProfilBoutique.objects.exclude(user__is_superuser=True).order_by("-id")
    
    if not boutiques.exists():
        return render(request, "boutique/annuaire_boutiques.html", {
            "secteurs": ProfilBoutique.SECTEURS
        })
        
    if boutiques.count() == 1:
        return redirect("catalogue", boutique_slug=boutiques.first().slug)
        
    return render(request, "boutique/annuaire_boutiques.html", {
        "boutiques": boutiques,
        "secteurs": ProfilBoutique.SECTEURS
    })


def annuaire_boutiques(request):
    """Affiche toujours la liste complète de toutes les boutiques marchandes."""
    boutiques = ProfilBoutique.objects.exclude(user__is_superuser=True).order_by("-id")
    return render(request, "boutique/annuaire_boutiques.html", {
        "boutiques": boutiques,
        "secteurs": ProfilBoutique.SECTEURS
    })


def inscription_vendeur(request):
    """Gère l'inscription d'un nouveau marchand et crée sa boutique associée."""
    if request.user.is_authenticated:
        return redirect('vendeur')
        
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        nom_boutique = request.POST.get('nom_boutique')
        secteur = request.POST.get('secteur', 'TELECOM')
        whatsapp = request.POST.get('whatsapp')
        
        if form.is_valid():
            user = form.save()
            ProfilBoutique.objects.create(
                user=user,
                nom=nom_boutique or f"Boutique de {user.username}",
                secteur=secteur,
                whatsapp=whatsapp or ""
            )
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            return redirect('vendeur')
    else:
        form = UserCreationForm()
        
    return render(request, 'boutique/inscription.html', {
        'form': form,
        'secteurs': ProfilBoutique.SECTEURS
    })


def connexion_vendeur(request):
    """Gère la connexion des marchands existants avec affichage des erreurs dans le terminal."""
    if request.user.is_authenticated:
        return redirect('vendeur')
        
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('vendeur')
        else:
            print(f"[DEBUG CONNEXION] Échec de connexion. Erreurs : {form.errors}")
    else:
        form = AuthenticationForm()
        
    return render(request, 'boutique/connexion.html', {"form": form})


def deconnexion_vendeur(request):
    """Déconnecte le marchand et redirige vers l'accueil."""
    logout(request)
    return redirect("accueil")


@login_required(login_url="connexion")
def tableau_bord_vendeur(request):
    """Tableau de bord sécurisé du marchand pour gérer sa boutique, ses produits et ses commandes."""
    profil, _ = ProfilBoutique.objects.get_or_create(
        user=request.user,
        defaults={"nom": f"Boutique de {request.user.username}", "whatsapp": ""}
    )

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "maj_profil":
            profil.nom = request.POST.get("nom", profil.nom)
            profil.secteur = request.POST.get("secteur", profil.secteur)
            profil.whatsapp = request.POST.get("whatsapp", profil.whatsapp)
            profil.infos_livraison = request.POST.get("infos_livraison", profil.infos_livraison)
            profil.save()
            return redirect("vendeur")

        elif action == "ajouter_produit":
            img_b64 = ""
            if request.FILES.get("image"):
                img_b64 = alleger_image_b64(request.FILES["image"])

            Produit.objects.create(
                boutique=profil,
                nom=request.POST.get("nom"),
                categorie=request.POST.get("categorie", "SMART_PHONE"),
                prix=request.POST.get("prix"),
                stock=int(request.POST.get("stock", 1)),
                caracteristiques=request.POST.get("caracteristiques", ""),
                image_base64=img_b64
            )
            return redirect("vendeur")

        elif action == "maj_stock":
            prod = get_object_or_404(Produit, id=request.POST.get("produit_id"), boutique=profil)
            prod.stock = max(0, int(request.POST.get("nouveau_stock", 0)))
            prod.save()
            return redirect("vendeur")

        elif action == "supprimer_produit":
            prod = get_object_or_404(Produit, id=request.POST.get("produit_id"), boutique=profil)
            prod.delete()
            return redirect("vendeur")

        elif action == "marquer_traitee":
            res = get_object_or_404(Reservation, id=request.POST.get("reservation_id"), produit__boutique=profil)
            res.traitee = not res.traitee
            res.save()
            return redirect("vendeur")

    produits = profil.produits.all().order_by("-date_ajout")
    reservations = Reservation.objects.filter(produit__boutique=profil).order_by("-date_reservation")

    return render(request, "boutique/vendeur.html", {
        "profil": profil,
        "produits": produits,
        "reservations": reservations,
        "secteurs": ProfilBoutique.SECTEURS,
        "categories": Produit.CATEGORIES
    })


def catalogue_boutique(request, boutique_slug):
    """Affiche la vitrine publique d'une boutique avec compteur de vues et pagination anti-saturation RAM."""
    profil = get_object_or_404(ProfilBoutique, slug=boutique_slug)
    
    # Incrémente les vues de +1 directement en base de données
    ProfilBoutique.objects.filter(pk=profil.pk).update(vues=F('vues') + 1)
    profil.refresh_from_db()
    
    # Récupération des produits
    produits_list = profil.produits.all().order_by("-date_ajout")
    
    # Pagination : maximum 12 produits par page pour éviter le crash 502 / Out of Memory
    paginator = Paginator(produits_list, 12)
    page_number = request.GET.get('page')
    produits = paginator.get_page(page_number)
    
    return render(request, "boutique/catalogue.html", {
        "profil": profil,
        "produits": produits
    })


def appeler_gemini(instruction, prompt_complet, api_key):
    """Interroge l'API Google Gemini avec gestion de l'historique et des instructions."""
    modeles = [
        "gemini-3.5-flash-lite",
        "gemini-3.8-flash",
        "gemini-3.6-flash",
        "gemini-3.1-flash-lite",
    ]
    
    client = genai.Client(api_key=api_key)
    derniere_erreur = ""

    for modele in modeles:
        try:
            response = client.models.generate_content(
                model=modele,
                contents=prompt_complet,
                config=types.GenerateContentConfig(
                    system_instruction=instruction,
                    max_output_tokens=250,
                    temperature=0.6,
                )
            )
            if response and response.text:
                return True, response.text.strip()
        except Exception as e:
            derniere_erreur = f"[{modele}] {str(e)}"
            continue

    print(f"Erreur Gemini : {derniere_erreur}")
    return False, derniere_erreur


def assistant_ia_vue(request):
    """Endpoint AJAX pour l'assistant IA connecté au stock, avec protections anti-spam."""
    if request.method != "POST":
        return JsonResponse({"erreur": "Méthode non autorisée"}, status=405)
        
    try:
        data = json.loads(request.body)
        message_client = data.get("message", "").strip()
        boutique_slug = data.get("boutique_slug", "").strip()
    except Exception:
        message_client = request.POST.get("message", "").strip()
        boutique_slug = request.POST.get("boutique_slug", "").strip()

    if not message_client:
        return JsonResponse({"reponse": "Écris-moi un petit message !"})

    # --- BLOC DE LIMITATION DEMANDÉ ---
    if len(message_client) > 500:
        return JsonResponse({"reponse": "Ton message est un peu trop long (500 caractères maximum)."})

    client_ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR'))
    if client_ip:
        client_ip = client_ip.split(',')[0].strip()
    else:
        client_ip = "unknown"

    cache_key = f"rate_limit_ai_{client_ip}"
    requetes_recentes = cache.get(cache_key, 0)

    # Maximum 12 messages par minute par visiteur
    if requetes_recentes >= 12:
        return JsonResponse({
            "reponse": "Oups ! Tu envoies des messages trop rapidement. Attends une petite minute."
        }, status=429)

    cache.set(cache_key, requetes_recentes + 1, timeout=60)
    # ----------------------------------

    API_KEY = getattr(settings, "GEMINI_API_KEY", "").strip()
    if not API_KEY:
        return JsonResponse({"reponse": "Clé API Gemini non configurée dans settings.py."})

    profil = ProfilBoutique.objects.filter(slug=boutique_slug).first() or ProfilBoutique.objects.first()
    nom_boutique = profil.nom if profil else "notre boutique"
    secteur_boutique = profil.get_secteur_display() if profil else "Commerce général"
    slug_actuel = profil.slug if profil else "default"

    liste_produits = ""
    if profil:
        produits_dispo = profil.produits.filter(stock__gt=0)
        if produits_dispo.exists():
            lignes = [f"- {p.nom} ({p.get_categorie_display()}) : {p.prix} FCFA | {p.caracteristiques}" for p in produits_dispo]
            liste_produits = "\n".join(lignes)
        else:
            liste_produits = "Aucun produit en stock pour le moment."

    cle_session = f"chat_historique_{slug_actuel}"
    historique = request.session.get(cle_session, [])
    historique.append(f"Client : {message_client}")
    historique = historique[-8:]

    prompt_complet = "\n".join(historique)

    instructions_systeme = (
        f"Tu es un conseiller de vente humain, calme et naturel de la boutique '{nom_boutique}' "
        f"(Secteur : {secteur_boutique}).\n"
        f"RÈGLES STRICTES :\n"
        f"- Adapte ton vocabulaire au secteur d'activité de la boutique.\n"
        f"- Ne dis JAMAIS 'Bonjour' ou 'Bienvenue' si la conversation a déjà commencé.\n"
        f"- Fais des réponses courtes et naturelles (2 à 3 phrases maximum), comme sur WhatsApp.\n"
        f"- Propose UNIQUEMENT les articles en stock ci-dessous :\n\n"
        f"STOCK RÉEL DISPONIBLE :\n{liste_produits}"
    )

    succes, resultat = appeler_gemini(instructions_systeme, prompt_complet, API_KEY)
    
    if succes:
        historique.append(f"Vendeur : {resultat}")
        request.session[cle_session] = historique
        return JsonResponse({"reponse": resultat})
        
    return JsonResponse({"reponse": "Désolé, je rencontre un petit souci de connexion. Pouvez-vous répéter ?"})