import base64
import json
import re
from google import genai
from google.genai import types
from django.conf import settings
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from .models import ProfilBoutique, Produit, Reservation


def alleger_image_b64(image_file):
    """Convertit un fichier image uploadé en chaîne Base64."""
    try:
        encoded = base64.b64encode(image_file.read()).decode('utf-8')
        return f"data:{image_file.content_type};base64,{encoded}"
    except Exception:
        return ""

def accueil(request):
    """Gère l'arrivée sur la racine du site (/) en excluant la boutique admin."""
    if request.user.is_authenticated and not request.user.is_superuser:
        return redirect("vendeur")
        
    # On récupère uniquement les boutiques des marchands (en excluant l'admin/superuser)
    boutiques = ProfilBoutique.objects.exclude(user__is_superuser=True).order_by("-id")
    
    # Si aucune boutique marchande n'existe encore
    if not boutiques.exists():
        return render(request, "boutique/annuaire_boutiques.html")
        
    # S'il n'y a qu'une seule boutique marchande -> Redirection directe vers son catalogue
    if boutiques.count() == 1:
        return redirect("catalogue", boutique_slug=boutiques.first().slug)
        
    # S'il y a plusieurs boutiques marchandes -> Annuaire
    return render(request, "boutique/annuaire_boutiques.html", {"boutiques": boutiques})

def inscription_vendeur(request):
    """Gère l'inscription d'un nouveau marchand et crée sa boutique associée."""
    if request.user.is_authenticated:
        return redirect('vendeur')
        
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        nom_boutique = request.POST.get('nom_boutique')
        whatsapp = request.POST.get('whatsapp')
        
        if form.is_valid():
            user = form.save()
            ProfilBoutique.objects.create(
                user=user,
                nom=nom_boutique or f"Boutique de {user.username}",
                whatsapp=whatsapp or ""
            )
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            return redirect('vendeur')
    else:
        form = UserCreationForm()
        
    return render(request, 'boutique/inscription.html', {'form': form})


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
                categorie=request.POST.get("categorie", "SMARTPHONE"),
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
        "reservations": reservations
    })


def catalogue_boutique(request, boutique_slug):
    """Affiche la vitrine publique d'une boutique spécifique (Multi-tenant)."""
    profil = get_object_or_404(ProfilBoutique, slug=boutique_slug)
    produits = profil.produits.all().order_by("-date_ajout")
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
    """Endpoint AJAX pour l'assistant IA connecté au stock, avec mémoire, debug et priorité au stock réel."""
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

    API_KEY = getattr(settings, "GEMINI_API_KEY", "").strip()
    if not API_KEY:
        return JsonResponse({"reponse": "Clé API Gemini non configurée."})

    # 1. Si le slug n'est pas dans le JSON, on le récupère automatiquement depuis le HTTP_REFERER
    if not boutique_slug:
        referer = request.META.get('HTTP_REFERER', '')
        match = re.search(r'/b/([^/]+)/', referer)
        if match:
            boutique_slug = match.group(1)

    # 2. Recherche robuste de la boutique
    profil = None
    if boutique_slug:
        profil = ProfilBoutique.objects.filter(slug=boutique_slug).first()
    if not profil:
        profil = ProfilBoutique.objects.first()

    # 3. Récupération des produits avec affichage de debug dans le terminal
    infos_produits = "Aucun produit actuellement en stock."
    if profil:
        produits = profil.produits.all()
        print(f"\n[DEBUG CHAT] Boutique détectée : {profil.nom} (Slug: {profil.slug})")
        print(f"[DEBUG CHAT] Nombre de produits trouvés : {produits.count()}")
        if produits.exists():
            liste = []
            for p in produits:
                print(f" -> Produit : {p.nom} | Prix : {p.prix} | Stock : {p.stock}")
                liste.append(f"- {p.nom} : {p.prix} FCFA (Stock : {p.stock}) | Caractéristiques : {p.caracteristiques}")
            infos_produits = "\n".join(liste)
    else:
        print("\n[DEBUG CHAT] ERREUR : Aucune boutique trouvée en base de données !")

    # 4. Gestion de la mémoire de conversation
    if 'chat_history' not in request.session:
        request.session['chat_history'] = []
    
    historique = request.session['chat_history'][-6:]
    historique_texte = ""
    for h in historique:
        role = "Client" if h['role'] == 'user' else "Assistant"
        historique_texte += f"{role}: {h['content']}\n"

    # 5. Instructions système prioritaires orientées stock réel
    nom_boutique_actuelle = profil.nom if profil else "la boutique"
    instructions_systeme = (
        f"INSTRUCTION CRITIQUE ET PRIORITAIRE : Tu es le vendeur officiel de la boutique '{nom_boutique_actuelle}'. "
        f"Voici la liste exacte et actuelle des articles EN STOCK dans ta boutique :\n{infos_produits}\n\n"
        "Règles strictes :\n"
        "- IGNORE complètement si l'historique de discussion ci-dessous disait le contraire : le stock ci-dessus est la seule et unique vérité.\n"
        "- Si le client cherche un article présent dans la liste (comme l'iPhone 13), propose-le immédiatement avec son vrai prix.\n"
        "- Fais des réponses courtes, chaleureuses et naturelles (2 phrases maximum).\n"
        "- Ne répète JAMAIS 'Bonjour' si la conversation a déjà commencé.\n"
        "- INTERDICTION absolue d'utiliser des listes numérotées (1, 2, 3). Parle comme un vrai vendeur sur WhatsApp."
    )

    prompt_complet = f"Historique de la conversation :\n{historique_texte}\nNouveau message du Client: {message_client}\nAssistant:"

    succes, resultat = appeler_gemini(instructions_systeme, prompt_complet, API_KEY)
    
    if succes:
        request.session['chat_history'].append({"role": "user", "content": message_client})
        request.session['chat_history'].append({"role": "assistant", "content": resultat})
        request.session.modified = True
        return JsonResponse({"reponse": resultat})

    return JsonResponse({"reponse": "Désolé, petit souci de connexion. Tu peux répéter ?"})