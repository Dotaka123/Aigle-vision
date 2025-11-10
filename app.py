import os
import requests
import json
import uuid
import random
from flask import Flask, request, jsonify

# --- CONFIGURATION & JETONS (Récupération STRICTE des variables d'environnement) ---

try:
    VERIFY_TOKEN = os.environ['VERIFY_TOKEN']
    # ATTENTION : NE PAS CODER EN DUR LE PAGE_ACCESS_TOKEN.
    PAGE_ACCESS_TOKEN = os.environ['PAGE_ACCESS_TOKEN']
    # ID FACEBOOK DE L'ADMINISTRATEUR
    ADMIN_SENDER_ID = os.environ['ADMIN_ID']
except KeyError as e:
    print(f"!!! ERREUR DE CONFIGURATION CRITIQUE : La variable d'environnement {e} est manquante. !!!")
    raise SystemExit(f"Arrêt : Variable {e} non configurée.")

PAGE_NAME = "Aigle Vision Mada"
EXTERNAL_API_URL = "https://rest-api-o42n.onrender.com/api/chatgpt5"
QR_API_URL = "https://api.qrserver.com/v1/create-qr-code/"

# --- AJOUT DU CONTEXTE COMMERCIAL POUR L'IA (Nouveau Prompt) ---
FORMATION_PITCH = (
    "Raha mahazo ny teny Frantsay na Anglisy dia ity ny asa tena mety aminao🥰. "
    "Ny surveys sy ny Micro-tâches dia anisan'ireo asa tsara karama. "
    "Le bot propose la **Formation Complète (de A à Z)** pour les surveys, "
    "avec la technique et le Proxy Résidentiel. "
    "Frais de formation: 120 000ar. Aza tara manao réservation!"
)
BASE_SYSTEM_PROMPT = (
    f"Tu es le bot amical et commercial de {PAGE_NAME}. "
    "Ta mission est d'encourager l'achat de formations et de proxys. "
    "Tu dois intégrer l'argumentaire suivant dans tes réponses : "
    f"'{FORMATION_PITCH}'"
)
# ----------------------------------------------------------------------

# --- DONNÉES ET TARIFS ---
FORMATION_COST_AR = 120000 
PASSPORT_COST_AR = 40000 
PROXY_COST_AR = 47000 
PROXY_PRICE_DISPLAY = f"{PROXY_COST_AR:,} Ar (pour un proxy résidentiel, 1 mois)"

# --- MESSAGE DE BIENVENUE EN MALGACHE ---
WELCOME_MESSAGE_MG = (
    "Tongasoa eto amin'ny pejy **Aigle Vision Mada**! 🦅\n\n"
    "Manolotra **fiofanana feno momba ny Surveys sy Micro-tâches** izahay, hahafahanao miasa sy mahazo vola amin'ny aterineto. Vonona hanampy anao izahay. **Ato ianao dia afaka mahazo karama 3$ - 10$ isan'andro.**\n\n"
    "Kitiho ny bokotra **\"Offres\"** hijerena ny antsipiriany!"
)

# Réponses de repli en Malgache en cas d'échec de l'IA externe
MALAGASY_FALLBACK_RESPONSES = [
    "Aigle Vision Mada no vahaolana ho an'ny asa an-tserasera! Miantsena Proxy haingana sy azo antoka eto.",
    "Tadidio fa manome fiofanana manokana momba ny surveys sy micro-tâches izahay ao amin'ny Aigle Vision Mada. Tsy maintsy miezaka ianao!",
    "Te hahazo vola amin'ny internet? Aigle Vision Mada manome ny teknika rehetra ilainao. Afaka manomboka ianao izao.",
]

# --- ÉTATS DE SESSION (En mémoire, non persistant) ---
user_session_state = {}

app = Flask(__name__)

# --- DÉFINITION DES ÉTAPES DU FORMULAIRE (MIS À JOUR) ---

FORM_PASSPORT = {
    "start_field": "nom_prenom",
    "start_question": f"Pour la création de votre passeport de vérification d'identité ({PASSPORT_COST_AR:,} Ar), quel est votre **Nom et Prénom** ?",
    "steps": [
        ("numero_mobile", "Quel est votre **Numéro de mobile** ?", ),
        ("adresse", "Quelle est votre **Adresse** complète ?", ),
        ("confirmation", f"Merci ! Veuillez confirmer la demande de passeport ({PASSPORT_COST_AR:,} Ar) : (OUI pour valider)"),
    ],
    "end_message": "DEMANDE DE PASSEPORT"
}

FORM_STEPS = {
    "FORM_FORMATION_ONLINE": { # NOUVEAU : EN LIGNE
        "start_field": "nom_prenom",
        "start_question": f"Parfait ! Pour l'inscription à la formation EN LIGNE ({FORMATION_COST_AR:,} Ar), quel est votre **Nom et Prénom** ?",
        "steps": [
            ("numero_mobile", "Quel est votre **Numéro de mobile** ?", ),
            ("adresse", "Quelle est votre **Adresse** complète ?", ),
            ("competence", "Avez-vous de l'expérience concernant les **sondages en ligne** ? (Oui/Non ou précisez vos compétences)"),
            ("confirmation", f"Merci ! Veuillez confirmer votre inscription ({FORMATION_COST_AR:,} Ar) : (OUI pour valider)"),
        ],
        "end_message": "INSCRIPTION FORMATION EN LIGNE"
    },
    
    "FORM_FORMATION_PRESENTIEL": { # NOUVEAU : PRÉSENTIEL
        "start_field": "nom_prenom",
        "start_question": f"Parfait ! Pour l'inscription à la formation PRÉSENTIEL ({FORMATION_COST_AR:,} Ar), quel est votre **Nom et Prénom** ?",
        "steps": [
            ("lieu_presentiel", "Quel est le **Lieu** et la **Date** que vous souhaitez réserver ? (Ex: FIANARANTSOA 8-15 Nov / ANTSIRABE 22 Nov / ANTANANARIVO 29 Nov / MORONDAVA 6 Déc)"),
            ("numero_mobile", "Quel est votre **Numéro de mobile** ?", ),
            ("adresse", "Quelle est votre **Adresse** complète ?", ),
            ("competence", "Avez-vous de l'expérience concernant les **sondages en ligne** ? (Oui/Non ou précisez vos compétences)"),
            ("confirmation", f"Merci ! Veuillez confirmer votre inscription ({FORMATION_COST_AR:,} Ar) : (OUI pour valider)"),
        ],
        "end_message": "INSCRIPTION FORMATION PRÉSENTIEL"
    },
    
    "FORM_PROXY": {
        "start_field": "nom_prenom",
        "start_question": "Super ! Quel est votre **Nom et Prénom** pour cette commande de proxy ?",
        "steps": [
            ("adresse", "Quelle est votre **Adresse** de facturation/livraison ?", ),
            ("numero_mobile", "Quel est votre **Numéro de mobile** ?", ),
            ("nombre_proxy", f"Combien de **Proxys Résidentiels (1 mois)** souhaitez-vous commander ? (Prix unitaire: {PROXY_COST_AR:,} Ar)"),
            ("confirmation", "Merci ! Veuillez confirmer votre commande : (OUI pour valider)"),
        ],
        "end_message": "COMMANDE DE PROXY"
    },
    "FORM_PASSPORT": FORM_PASSPORT
}


# --- FONCTIONS MESSENGER (send, api call) ---

def send_facebook_api_request(message_data):
    """Fonction utilitaire pour gérer toutes les requêtes POST vers l'API Facebook et gérer les erreurs."""
    url = f"https://graph.facebook.com/v18.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
    try:
        response = requests.post(url, json=message_data)
        response.raise_for_status() 
        return True
    except requests.exceptions.HTTPError as e:
        print(f"!!! ÉCHEC DE L'ENVOI FACEBOOK (HTTPError) : Code {response.status_code}. Réponse : {response.text}")
        if response.status_code == 400:
             print("!!! VÉRIFIEZ LE PAGE_ACCESS_TOKEN ET/OU L'ID DE L'UTILISATEUR DESTINATAIRE (admin ou client).")
        return False
    except requests.exceptions.RequestException as e:
        print(f"!!! ÉCHEC DE L'ENVOI FACEBOOK (RequestException) : {e}")
        return False

def send_message_to_admin(admin_id, message_text):
    """Envoie un message de notification à l'administrateur."""
    print(f"--- Tentative d'envoi de la notification admin à {admin_id} ---")
    
    if not ADMIN_SENDER_ID or ADMIN_SENDER_ID == '100039040104071':
        print("\n--- ATTENTION : L'ID ADMIN est par défaut/non configuré. Le message est imprimé localement. ---\n")
        print(message_text)
        return False
        
    message_data = {
        "recipient": {"id": admin_id},
        "message": {"text": message_text}
    }
    return send_facebook_api_request(message_data)


def send_message(recipient_id, message_text, current_state="AI"):
    """Envoie une réponse à l'utilisateur avec les boutons d'action (Quick Replies)."""
    print(f"--- Tentative d'envoi du message à {recipient_id}. État: {current_state} ---")
    
    if current_state != "HUMAN":
        quick_replies = [
            {"content_type": "text", "title": "Offres", "payload": "SHOW_OFFERS_MENU"},
            {"content_type": "text", "title": "Parler à une personne", "payload": "HUMAN_AGENT"},
        ]
    else:
        quick_replies = [
            {"content_type": "text", "title": "Parler à l'IA", "payload": "AI_AGENT"},
        ]

    message_data = {
        "recipient": {"id": recipient_id},
        "message": {
            "text": message_text,
            "quick_replies": quick_replies
        }
    }
    send_facebook_api_request(message_data)


def upload_and_send_image(recipient_id, image_url):
    """Télécharge le QR code en mémoire et l'uploade sur Facebook pour envoi."""
    print(f"--- Début de l'envoi du QR Code à {recipient_id} ---")
    
    try:
        # Étape 1 : Télécharger l'image en mémoire
        img_response = requests.get(image_url)
        img_response.raise_for_status()

        # Étape 2 : Uploader l'image vers l'API de Facebook (File Upload)
        upload_url = f"https://graph.facebook.com/v18.0/me/message_attachments?access_token={PAGE_ACCESS_TOKEN}"
        
        files = {
            'message': (None, '{"attachment": {"type": "image", "payload": {"is_reusable": true}}}'),
            'filedata': ('qrcode.png', img_response.content, 'image/png')
        }

        upload_response = requests.post(upload_url, files=files)
        upload_response.raise_for_status()
        
        attachment_id = upload_response.json()['attachment_id']
        print(f"--- Image uploadée. Attachment ID: {attachment_id} ---")

        # Étape 3 : Envoyer l'image en utilisant l'ID d'attachement
        message_data = {
            "recipient": {"id": recipient_id},
            "message": {
                "attachment": {
                    "type": "image",
                    "payload": {"attachment_id": attachment_id}
                }
            }
        }
        send_facebook_api_request(message_data)

    except requests.exceptions.RequestException as e:
        print(f"!!! Échec de l'upload ou de l'envoi de l'image (QR Code) : {e}")

# --- Fonctions de Logique ---

def handle_offers_menu(sender_id):
    """Affiche le menu détaillé des offres, 'Faire une formation' est en premier."""
    print(f"--- Affichage du menu Offres à {sender_id} ---")

    message_text = "🔎 **Voici toutes nos offres de services et produits** :"

    offers_replies = [
        {"content_type": "text", "title": "Faire une formation", "payload": "OFFER_FORMATION_INFO"}, # Déplacé en premier
        {"content_type": "text", "title": "Créer un passeport", "payload": "START_FORM_PASSPORT"},
        {"content_type": "text", "title": "Acheter un proxy", "payload": "START_FORM_PROXY"},
    ]

    message_data = {
        "recipient": {"id": sender_id},
        "message": {
            "text": message_text,
            "quick_replies": offers_replies
        }
    }
    send_facebook_api_request(message_data)
    return "OK"

def call_external_api(query, sender_id):
    """Fait un appel HTTP à l'API externe pour obtenir une réponse IA."""
    print(f"--- Appel de l'API externe pour la requête : {query[:30]}... ---")
    try:
        params = {
            "query": query, "uid": sender_id, "model": "gpt-5",
            "system": BASE_SYSTEM_PROMPT,
            "imgurl": ""
        }
        response = requests.get(EXTERNAL_API_URL, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        return data.get("result", random.choice(MALAGASY_FALLBACK_RESPONSES))
    except requests.exceptions.RequestException as e:
        print(f"!!! ÉCHEC DE L'APPEL EXTERNE : {e}")
        return random.choice(MALAGASY_FALLBACK_RESPONSES)

def handle_form_input(sender_id, message_text):
    """Gère l'état et l'avancement d'un formulaire, avec vérification des entrées et QR Code."""
    state_info = user_session_state[sender_id]
    state = state_info['state']
    data = state_info['data']
    current_field = state_info.get('current_field')

    form_type_key = state.replace("FORM_", "")
    form_config = FORM_STEPS[state]
    total_steps = len(form_config['steps'])
    
    # 1. STOCKAGE ET VALIDATION DE L'INPUT
    if current_field:

        # --- Validation Spécifique : Nombre de Proxy ---
        if current_field == "nombre_proxy":
            try:
                num_proxy = int(message_text.strip())
                if num_proxy <= 0:
                    raise ValueError("Nombre doit être positif")
                data[current_field] = num_proxy
            except ValueError:
                return "❌ Veuillez entrer un **nombre entier positif** valide pour le nombre de proxys."

        # --- Gestion de la Confirmation (OUI/NON) ---
        elif current_field == "confirmation":
            if message_text.lower() == "oui":
                # --- GÉNÉRATION DE LA TRANSACTION ET DU RÉSUMÉ ---
                transaction_id = str(uuid.uuid4()).replace('-', '')[:15].upper()

                # Calculs et messages 
                cost = 0
                if form_type_key.startswith("FORMATION"):
                    cost = FORMATION_COST_AR
                    recap_message = (
                        f"🎉 NOUVELLE {form_config['end_message']} - {PAGE_NAME} (COÛT: {cost:,} Ar) 🎉\n"
                        f"Type: **{'PRÉSENTIEL' if 'PRESENTIEL' in form_type_key else 'EN LIGNE'}**\n"
                        f"{f'Lieu Réservé: {data.get("lieu_presentiel", "N/A")}\n' if 'PRESENTIEL' in form_type_key else ''}"
                        f"Nom: **{data.get('nom_prenom', 'N/A')}**\n"
                        f"Numéro de mobile: {data.get('numero_mobile', 'N/A')}\n"
                        f"Adresse: {data.get('adresse', 'N/A')}\n"
                        f"Compétence Sondage: {data.get('competence', 'N/A')}\n"
                        f"Numéro de transaction: **{transaction_id}**\n"
                        f"ACTION: INSCRIPTION CONFIRMÉE\n"
                        f"ID Utilisateur: {sender_id}"
                    )
                    qr_data = f"Type: Formation; ID: {transaction_id}; Nom: {data.get('nom_prenom')}"

                elif form_type_key == "PROXY":
                    num_proxy = data.get('nombre_proxy', 0)
                    total_cout = num_proxy * PROXY_COST_AR
                    cost = total_cout

                    recap_message = (
                        f"🛒 NOUVELLE COMMANDE PROXY - {PAGE_NAME} (COÛT ESTIMÉ: {cost:,.0f} Ar) 🛒\n"
                        f"Nom: **{data.get('nom_prenom', 'N/A')}**\n"
                        f"Adresse: {data.get('adresse', 'N/A')}\n"
                        f"Numéro de mobile: {data.get('numero_mobile', 'N/A')} \n"
                        f"Nombre de Proxy: {num_proxy}\n"
                        f"Numéro de transaction: **{transaction_id}**\n"
                        f"ACTION: COMMANDE VALIDÉE\n"
                        f"ID Utilisateur: {sender_id}"
                    )
                    qr_data = f"Type: Proxy; ID: {transaction_id}; Nom: {data.get('nom_prenom')}"

                elif form_type_key == "PASSPORT":
                    cost = PASSPORT_COST_AR
                    recap_message = (
                        f"🛂 NOUVELLE DEMANDE PASSEPORT ID - {PAGE_NAME} (COÛT: {cost:,} Ar) 🛂\n"
                        f"Nom: **{data.get('nom_prenom', 'N/A')}**\n"
                        f"Numéro de mobile: {data.get('numero_mobile', 'N/A')}\n"
                        f"Adresse: {data.get('adresse', 'N/A')}\n"
                        f"Numéro de transaction: **{transaction_id}**\n"
                        f"ACTION: DEMANDE DE PASSEPORT VALIDÉE\n"
                        f"ID Utilisateur: {sender_id}"
                    )
                    qr_data = f"Type: Passeport; ID: {transaction_id}; Nom: {data.get('nom_prenom')}"

                # --- ENVOI DU RÉCAPITULATIF À L'ADMIN ---
                send_message_to_admin(ADMIN_SENDER_ID, recap_message)

                # --- ENVOI DU RÉCAPITULATIF À L'UTILISATEUR ---
                user_recap_message = recap_message
                user_recap_message = user_recap_message.replace(f"🎉 NOUVELLE INSCRIPTION FORMATION EN LIGNE - {PAGE_NAME} (COÛT: {FORMATION_COST_AR:,} Ar) 🎉", "🎉 **Votre Inscription EN LIGNE est enregistrée !**")
                user_recap_message = user_recap_message.replace(f"🎉 NOUVELLE INSCRIPTION FORMATION PRÉSENTIEL - {PAGE_NAME} (COÛT: {FORMATION_COST_AR:,} Ar) 🎉", "🎉 **Votre Inscription PRÉSENTIEL est enregistrée !**")
                user_recap_message = user_recap_message.replace(f"🛒 NOUVELLE COMMANDE PROXY - {PAGE_NAME} (COÛT ESTIMÉ: {cost:,.0f} Ar) 🛒", "🛒 **Votre Commande est enregistrée !**")
                user_recap_message = user_recap_message.replace(f"🛂 NOUVELLE DEMANDE PASSEPORT ID - {PAGE_NAME} (COÛT: {PASSPORT_COST_AR:,} Ar) 🛂", "🛂 **Votre Demande de Passeport est enregistrée !**")
                user_recap_message = user_recap_message.replace(f"\nID Utilisateur: {sender_id}", "").replace("ACTION:", "\n*Statut :*")
                user_recap_message = user_recap_message.replace(f"Type: **{'PRÉSENTIEL' if 'PRESENTIEL' in form_type_key else 'EN LIGNE'}**\n", "")

                send_message(sender_id, user_recap_message, current_state="AI")

                # --- GÉNÉRATION ET ENVOI DU QR CODE ---
                qr_params = {
                    "size": "150x150",
                    "data": qr_data
                }
                qr_code_url = requests.Request('GET', QR_API_URL, params=qr_params).prepare().url

                upload_and_send_image(sender_id, qr_code_url)

                final_msg = (
                    f"🚀 Merci ! Votre {form_config['end_message']} est enregistrée. "
                    f"**Veuillez conserver le QR code ci-dessus** pour référence. "
                    f"Un administrateur va parler avec vous pour finaliser la procédure."
                )
                send_message(sender_id, final_msg, current_state="AI")

                # Réinitialiser l'état
                user_session_state[sender_id] = {'state': 'AI', 'step': 0, 'data': {}}
                return "QR_SENT"

            else:
                # Annulation
                user_session_state[sender_id] = {'state': 'AI', 'step': 0, 'data': {}}
                return "❌ Formulaire annulé. Vous pouvez recommencer en cliquant sur un bouton d'action ci-dessous."

        # --- Stockage Normal ---
        else:
            data[current_field] = message_text.strip()


    # 2. PASSAGE À L'ÉTAPE SUIVANTE
    user_session_state[sender_id]['step'] += 1
    next_step_index = user_session_state[sender_id]['step']

    if next_step_index < total_steps:
        next_field, next_question = form_config['steps'][next_step_index]
        user_session_state[sender_id]['current_field'] = next_field
        return next_question

    user_session_state[sender_id] = {'state': 'AI', 'step': 0, 'data': {}}
    return "Une erreur est survenue dans le formulaire. Veuillez recommencer."

def get_bot_response(message_text, sender_id):
    """Décide si la réponse est prédéfinie (tarifs/services) ou générée par l'IA."""
    message_text_lower = message_text.lower()

    # --- GESTION DES BOUTONS D'OFFRE : FORMATION (Texte long + Choix En ligne/Présentiel) ---
    if "offer_formation_info" == message_text_lower:

        message_text_long = (
            "✅Raha mahazo ny teny Frantsay🇫🇷na Anglisy🇺🇸dia ity ny asa tena mety aminao🥰\n"
            "🥰Ny surveys sy ny Micro-tâches dia anisan'ireo asa tsara karama raha ampy information🔰 sy technique ho entina manao azy ianao🥰\n"
            "❌⚠Tsy sarotra tompoko ny surveys, ny valiny ihany koa dia efa omeny eo fa isika no misafidy, ka ny Paik'ady no mila ananana✅\n"
            "⛔Tsy misy fetra ny fotoana iasana, fa izay tinao🥰 afaka miasa 24h/24h ary 7j/7\n"
            "✅**Zavatra ilaiana raha te hanao ilay asa**✅\n"
            "    👉Téléphone📱ou Ordinateur💻\n"
            "    👉Connexion Internet 📶(Data mobil ou Wi-Fi)\n"
            "✅**Formation Complète (de A à Z) sur Timebucks USA et d'autres Plate-forme** ✅\n"
            "💼 **Programme de formation complet** 📝👇\n"
            "✨Introduction, ☑Bases fondamentales\n"
            "📧Création Gmail sans numéro illimité\n"
            "✅Tous les outils nécessaires☑\n"
            "🌐Bases fondamentales et achat de Proxy☑\n"
            "🌐Test et installation de Proxy☑\n"
            "✅Procédure de création des comptes USA🇺🇸 Timebucks et d'autres Plate-forme ✅\n"
            "✅Procédure de création Profil surveys optimisé💰\n"
            "💻📱Simulation des travaux avec stratégies 🎯💼\n"
            "💰Création Portefeuille électronique💼\n"
            "✅Vérification KYC🔒☑\n"
            "✅Les démarches de retrait 💸💵\n"
            "💎🎁Bonus, Compte, Proxy, ID étrangère💎🎁\n"
            "✅🥰**Miasa avy hatrany rehefa vita ny formation** 🥰✅\n"
            "**👉🌐🔰Types de formation🔰 🌐👇**\n"
            "🌐**En ligne** ( Par appel vidéo, live)\n"
            "☑9h-12h, 14h-18h / 🌃Spécial nuit à partir 21h\n"
            "🏠**Formation Présentiel** avec connexion gratuit 📶\n"
            "📍FIANARANTSOA (Limité 10) - 8-15 nov. 2025 (Andrainjato)\n"
            "📍ANTSIRABE (Limité 10) - 22 Nov. 2025\n"
            "📍ANTANANARIVO (Limité 20) - 29 Nov. 2025\n"
            "📍MORONDAVA (Limité 10) - 6 Déc. 2025\n"
            "❤Avec suivi illimité❤ | Garantie: Compte vérifié KYC✅\n"
            f"**😍Frais de formation: {FORMATION_COST_AR:,}ar (Présentiel ou en ligne)**\n"
            "🥰Aza tara misoratra anarana sy manao réservation fa sao feno ny toerana✅\n"
            "---"
        )

        quick_replies = [
            {"content_type": "text", "title": "S'inscrire (EN LIGNE)", "payload": "START_FORM_FORMATION_ONLINE"},
            {"content_type": "text", "title": "S'inscrire (PRÉSENTIEL)", "payload": "START_FORM_FORMATION_PRESENTIEL"},
        ]
        message_data = {
            "recipient": {"id": sender_id},
            "message": {
                "text": message_text_long,
                "quick_replies": quick_replies
            }
        }
        send_facebook_api_request(message_data)
        return ""

    # --- GESTION DES BOUTONS D'OFFRE : PASSEPORT (Description détaillée) ---
    if "offer_passport_info" == message_text_lower:
        return (
            f"🛂 **CRÉATION DE PASSEPORT DE VÉRIFICATION D'IDENTITÉ** 🛂\n"
            f"**Tarif : {PASSPORT_COST_AR:,} Ar**\n"
            "Nous créons pour vous les **documents nécessaires à la vérification d'identité (ID)** lors des sondages, essentielle pour débloquer les plateformes et maximiser votre profil. Ce service inclut :\n"
            "* **Création et préparation** des documents ID (Passeport/ID fictif à usage unique).\n"
            "Cliquez sur 'Offres' puis 'Créer un passeport' pour lancer la procédure de commande et enregistrer vos informations."
        )

    # --- ANCIENS CHEMINS DE RÉPONSE RAPIDE ---
    if "tarif proxy" in message_text_lower or "prix proxy" in message_text_lower:
        return f"Le tarif pour un proxy résidentiel pour 1 mois est de **{PROXY_PRICE_DISPLAY}**. Cliquez sur 'Offres' puis 'Acheter un proxy' pour lancer la commande !"

    # Si le message n'est pas vide et ne correspond à aucun mot-clé/payload, on appelle l'IA
    if message_text.strip():
        return call_external_api(message_text, sender_id)
    return ""

# --- WEBHOOKS FLASK ---

@app.route('/webhook', methods=['GET'])
def verify_webhook():
    """Endpoint pour la vérification du webhook (GET)."""
    if request.args.get("hub.mode") == "subscribe" and request.args.get("hub.challenge"):
        if not request.args.get("hub.verify_token") == VERIFY_TOKEN:
            return "Jeton de vérification incorrect", 403
        return request.args["hub.challenge"], 200
    return "Mauvaise requête de vérification", 200

@app.route('/webhook', methods=['POST'])
def handle_messages():
    """Endpoint pour la réception des messages et événements (POST)."""
    data = request.get_json()
    print(f"\n--- REQUÊTE POST WEBHOOK REÇUE ---")
    
    if data.get("object") == "page":
        for entry in data["entry"]:
            for messaging_event in entry.get("messaging", []):
                sender_id = messaging_event["sender"]["id"]

                if sender_id not in user_session_state:
                    user_session_state[sender_id] = {'state': 'AI', 'step': 0, 'data': {}}

                message = messaging_event.get("message")
                postback = messaging_event.get("postback")

                message_text = None
                payload = None

                if message:
                    message_text = message.get("text")
                    payload = message.get("quick_reply", {}).get("payload")
                    print(f"Message de {sender_id}. Texte: '{message_text}', Payload: '{payload}'")
                elif postback:
                    payload = postback.get("payload")
                    message_text = payload # Utilise le payload comme texte dans la logique de postback
                    print(f"Postback de {sender_id}. Payload: '{payload}'")
                else:
                    print(f"Événement non traité (non-message/non-postback).")
                    continue

                if message_text is not None or payload is not None:
                    
                    if message_text is None:
                        message_text = ""

                    current_session_state = user_session_state[sender_id]['state']

                    # 0. GESTION DU MESSAGE DE BIENVENUE (POSTBACK GET_STARTED)
                    if postback and postback.get("payload") in ["GET_STARTED_PAYLOAD", "GET_STARTED"]:
                        send_message(sender_id, WELCOME_MESSAGE_MG, current_state="AI")
                        return "OK", 200

                    # 1. GESTION DES COMMANDES DE CONTRÔLE (HUMAN/AI)
                    if payload in ["HUMAN_AGENT", "AI_AGENT"]:
                        if payload == "HUMAN_AGENT":
                            user_session_state[sender_id]['state'] = "HUMAN"
                            response_text = "❌ **Transfert en cours** : J'arrête de répondre. **Un administrateur va parler avec vous dans quelques instants.**"
                            send_message(sender_id, response_text, current_state="HUMAN")
                        elif payload == "AI_AGENT":
                            user_session_state[sender_id]['state'] = "AI"
                            response_text = "✅ **Mode IA activé** : Je suis de nouveau prêt à répondre."
                            send_message(sender_id, response_text, current_state="AI")
                        return "OK", 200

                    # 2. DÉCLENCHEMENT DES FORMULAIRES ET MENUS
                    if payload == "SHOW_OFFERS_MENU":
                        handle_offers_menu(sender_id)
                        return "OK", 200
                        
                    elif payload in ["START_FORM_PROXY", "START_FORM_PASSPORT", "START_FORM_FORMATION_ONLINE", "START_FORM_FORMATION_PRESENTIEL"]:
                        form_key = payload.replace("START_", "")
                        form_config = FORM_STEPS[form_key]
                        
                        user_session_state[sender_id] = {
                            'state': form_key,
                            'step': 0,
                            'data': {},
                            'current_field': form_config['start_field']
                        }
                        response_text = form_config['start_question']
                        send_message(sender_id, response_text, current_state="AI")
                        return "OK", 200
                        
                    # 3. GESTION DE LA CONVERSATION
                    if current_session_state == "HUMAN":
                        print(f"Session {sender_id} est en mode HUMAN. Ignoré par le bot.")
                        return "OK", 200

                    # 4. RÉPONSE AUX BOUTONS D'OFFRE (OFFER_*) OU FORMULAIRE EN COURS
                    
                    if current_session_state == "AI" and payload in ["OFFER_PASSPORT_INFO", "OFFER_FORMATION_INFO"]:
                        get_bot_response(payload, sender_id)
                        return "OK", 200
                        
                    if current_session_state.startswith("FORM_"):
                        print(f"Session {sender_id} est en mode FORMULAIRE ({current_session_state}). Traitement...")
                        response_text = handle_form_input(sender_id, message_text)
                        if response_text != "QR_SENT":
                            send_message(sender_id, response_text, current_state="AI")
                        return "OK", 200

                    # 5. RÉPONSE IA GÉNÉRALE
                    if message_text.strip():
                        print(f"Session {sender_id} est en mode IA. Appel de get_bot_response...")
                        response_text = get_bot_response(message_text, sender_id)
                        if response_text and response_text not in ["QR_SENT", ""]:
                            send_message(sender_id, response_text, current_state="AI")
                        return "OK", 200
                        
    return "OK", 200

if __name__ == '__main__':
    print(f"Démarrage du bot Messenger pour {PAGE_NAME}...")
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
