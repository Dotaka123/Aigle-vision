import os
import requests
import json
import uuid
import random 
from flask import Flask, request, jsonify

# --- CONFIGURATION & JETONS ---
# REMPLACEZ CES VALEURS PAR VOS JETONS RÉELS
VERIFY_TOKEN = os.environ.get('VERIFY_TOKEN', 'tata')
PAGE_ACCESS_TOKEN = os.environ.get('PAGE_ACCESS_TOKEN', 'EAAI12hLrtqEBPxaOXb7oL7mx8rR1fwNgD2mtNVQ6rKZCo7wGZACWyWwpCZAP9F9xUiz6Q96Xg3ZB9Upo8zSkmjUGfa2R2dE5k75ZBN5PdTpH85qhPOnELBYoVAtcHxmZC3XMH5FlRBooNk4BCx7SavRgmFpi8vQ470Tt6IHl9QviaXPCLRk7ZBbuh2trAO4LQzRblZAssAZDZD')
PAGE_NAME = "Aigle Vision Mada"
EXTERNAL_API_URL = "https://rest-api-o42n.onrender.com/api/chatgpt5"
QR_API_URL = "https://api.qrserver.com/v1/create-qr-code/" 

# ID FACEBOOK DE L'ADMINISTRATEUR (VÉRIFIEZ ABSOLUMENT CET ID POUR CORRIGER L'ERREUR 400)
ADMIN_SENDER_ID = os.environ.get('ADMIN_ID', '100039040104071')
BASE_SYSTEM_PROMPT = f"Tu es le bot amical de {PAGE_NAME}. Tu proposes des formations en travail en ligne et des proxys de qualité à prix abordable."

# --- DONNÉES ET TARIFS (VALEURS MISES À JOUR) ---
FORMATION_COST_AR = 120000 # Nouveau prix: 120 000 Ar
PASSPORT_COST_AR = 40000  # Nouveau prix: 40 000 Ar
PROXY_COST_AR = 47000     # Nouveau prix: 47 000 Ar
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

# --- ÉTATS DE SESSION ---
user_session_state = {} 

app = Flask(__name__)

# --- DÉFINITION DES ÉTAPES DU FORMULAIRE (TEXTES MIS À JOUR) ---
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
    "FORM_FORMATION": {
        "start_field": "nom_prenom",
        "start_question": f"Parfait ! Pour l'inscription à la formation ({FORMATION_COST_AR:,} Ar), quel est votre **Nom et Prénom** ?",
        "steps": [
            ("numero_mobile", "Quel est votre **Numéro de mobile** ?", ),
            ("adresse", "Quelle est votre **Adresse** complète ?", ),
            ("competence", "Avez-vous de l'expérience concernant les **sondages en ligne** ? (Oui/Non ou précisez vos compétences)"),
            ("confirmation", f"Merci ! Veuillez confirmer votre inscription ({FORMATION_COST_AR:,} Ar) : (OUI pour valider)"),
        ],
        "end_message": "INSCRIPTION FORMATION"
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

def send_message_to_admin(admin_id, message_text):
    """Envoie un message de notification à l'administrateur."""
    if admin_id == 'VOTRE_ADMIN_ID_NUMERIQUE':
        print("\n--- ATTENTION : L'ID ADMIN n'est pas configuré. Le message est imprimé localement. ---\n")
        print(message_text)
        return False
        
    message_data = {
        "recipient": {"id": admin_id},
        "message": {"text": message_text}
    }

    url = f"https://graph.facebook.com/v18.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
    
    try:
        response = requests.post(url, json=message_data)
        response.raise_for_status()
        return True
    except requests.exceptions.RequestException as e:
        print(f"!!! Échec de l'envoi de la notification admin (Erreur 400 ou autre) : {e}")
        print("!!! VÉRIFIEZ L'ADMIN_SENDER_ID : IL DOIT ÊTRE L'ID NUMÉRIQUE FACEBOOK D'UN DÉVELOPPEUR/TESTEUR AYANT EU UNE CONVERSATION AVEC LE BOT.")
        return False

def send_message(recipient_id, message_text, current_state="AI"):
    """Envoie une réponse à l'utilisateur avec les boutons d'action (Quick Replies)."""
    
    if current_state != "HUMAN":
        quick_replies = [
            # Bouton "Faire une formation" retiré d'ici pour n'apparaître que dans les Offres
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

    url = f"https://graph.facebook.com/v18.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
    requests.post(url, json=message_data)

def upload_and_send_image(recipient_id, image_url):
    """
    Télécharge le QR code en mémoire et l'uploade sur Facebook pour contourner robots.txt.
    """
    print(f"--- Téléchargement du QR Code depuis {image_url} ---")
    
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
        print(f"--- Image uploadée avec succès. Attachment ID: {attachment_id} ---")

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
        send_url = f"https://graph.facebook.com/v18.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
        requests.post(send_url, json=message_data)
        
    except requests.exceptions.RequestException as e:
        print(f"!!! Échec de l'upload ou de l'envoi de l'image : {e}")

def handle_offers_menu(sender_id):
    """Affiche le menu détaillé des offres."""
    
    message_text = "🔎 **Voici toutes nos offres de services et produits** :"
    
    offers_replies = [
        {"content_type": "text", "title": "Créer un passeport", "payload": "START_FORM_PASSPORT"},
        {"content_type": "text", "title": "Acheter un proxy", "payload": "START_FORM_PROXY"},
        {"content_type": "text", "title": "Faire une formation", "payload": "OFFER_FORMATION_INFO"}, 
    ]
    
    message_data = {
        "recipient": {"id": sender_id},
        "message": {
            "text": message_text,
            "quick_replies": offers_replies
        }
    }

    url = f"https://graph.facebook.com/v18.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
    requests.post(url, json=message_data)
    
    return "OK"


def call_external_api(query, sender_id):
    """Fait un appel HTTP à l'API externe pour obtenir une réponse IA."""
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
        return random.choice(MALAGASY_FALLBACK_RESPONSES)


# --- LOGIQUE DU FORMULAIRE ---

def handle_form_input(sender_id, message_text):
    """Gère l'état et l'avancement d'un formulaire, avec vérification des entrées et QR Code."""
    state_info = user_session_state[sender_id]
    state = state_info['state']
    data = state_info['data']
    current_field = state_info.get('current_field')
    
    form_type = state.split('_')[1]
    form_config = FORM_STEPS[f"FORM_{form_type}"]
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
                
                # Calculs et messages (UTILISE LES NOUVEAUX PRIX)
                if form_type == "FORMATION":
                    cost = FORMATION_COST_AR
                    recap_message = (
                        f"🎉 NOUVELLE INSCRIPTION FORMATION - {PAGE_NAME} (COÛT: {cost:,} Ar) 🎉\n"
                        f"Nom: **{data.get('nom_prenom', 'N/A')}**\n"
                        f"Numéro de mobile: {data.get('numero_mobile', 'N/A')}\n"
                        f"Adresse: {data.get('adresse', 'N/A')}\n"
                        f"Compétence Sondage: {data.get('competence', 'N/A')}\n"
                        f"Numéro de transaction: **{transaction_id}**\n"
                        f"ACTION: INSCRIPTION CONFIRMÉE\n"
                        f"ID Utilisateur: {sender_id}"
                    )
                    qr_data = f"Type: Formation; ID: {transaction_id}; Nom: {data.get('nom_prenom')}"
                
                elif form_type == "PROXY":
                    num_proxy = data.get('nombre_proxy', 0)
                    total_cout = num_proxy * PROXY_COST_AR
                    
                    recap_message = (
                        f"🛒 NOUVELLE COMMANDE PROXY - {PAGE_NAME} 🛒\n"
                        f"Nom: **{data.get('nom_prenom', 'N/A')}**\n"
                        f"Adresse: {data.get('adresse', 'N/A')}\n"
                        f"Numéro de mobile: {data.get('numero_mobile', 'N/A')} \n"
                        f"Nombre de Proxy: {num_proxy}\n"
                        f"Estimation de coût: {total_cout:,.0f} Ar\n"
                        f"Numéro de transaction: **{transaction_id}**\n"
                        f"ACTION: COMMANDE VALIDÉE\n"
                        f"ID Utilisateur: {sender_id}"
                    )
                    qr_data = f"Type: Proxy; ID: {transaction_id}; Nom: {data.get('nom_prenom')}"
                
                elif form_type == "PASSPORT":
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
                user_recap_message = user_recap_message.replace(f"🎉 NOUVELLE INSCRIPTION FORMATION - {PAGE_NAME} (COÛT: {FORMATION_COST_AR:,} Ar) 🎉", "🎉 **Votre Inscription est enregistrée !**")
                user_recap_message = user_recap_message.replace(f"🛒 NOUVELLE COMMANDE PROXY - {PAGE_NAME} 🛒", "🛒 **Votre Commande est enregistrée !**")
                user_recap_message = user_recap_message.replace(f"🛂 NOUVELLE DEMANDE PASSEPORT ID - {PAGE_NAME} (COÛT: {PASSPORT_COST_AR:,} Ar) 🛂", "🛂 **Votre Demande de Passeport est enregistrée !**")
                user_recap_message = user_recap_message.replace(f"\nID Utilisateur: {sender_id}", "").replace("ACTION:", "\n*Statut :*")
                
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


# --- LOGIQUE DE RÉPONSE GÉNÉRALE ---

def get_bot_response(message_text, sender_id):
    """Décide si la réponse est prédéfinie (tarifs/services) ou générée par l'IA."""
    message_text_lower = message_text.lower()
    
    # --- GESTION DES BOUTONS D'OFFRE : FORMATION (Description détaillée + Bouton d'inscription) ---
    if "offer_formation_info" == message_text_lower:
        
        message_text = (
            f"🎓 **FORMATION SONDAGES RÉMUNÉRÉS : Le Guide Complet** 🎓\n"
            f"**Tarif : {FORMATION_COST_AR:,} Ar (Formation en ligne)**\n"
            "Notre formation complète vous offre la méthode et les outils pour **générer un revenu stable via les sondages rémunérés**.\n"
            "* **Concept central** : Nous vous apprenons à utiliser les Proxys Résidentiels pour accéder de manière fiable aux sondages internationaux, qui sont souvent les mieux payés.\n"
            "* **Objectifs** : Maîtriser les plateformes, optimiser vos profils et garantir la fiabilité de vos réponses pour maximiser vos gains.\n"
        )
        
        quick_replies = [
            {"content_type": "text", "title": "S'inscrire à la formation", "payload": "START_FORM_FORMATION"},
        ]
        message_data = {
            "recipient": {"id": sender_id},
            "message": {
                "text": message_text,
                "quick_replies": quick_replies
            }
        }
        url = f"https://graph.facebook.com/v18.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
        requests.post(url, json=message_data)
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
                elif postback:
                    payload = postback.get("payload")
                    message_text = payload

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
                        
                    elif payload in ["START_FORM_PROXY", "START_FORM_FORMATION", "START_FORM_PASSPORT"]:
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
                        return "OK", 200

                    # 4. RÉPONSE AUX BOUTONS D'OFFRE (OFFER_*) OU FORMULAIRE EN COURS
                    
                    if current_session_state == "AI" and payload in ["OFFER_PASSPORT_INFO", "OFFER_FORMATION_INFO"]:
                        get_bot_response(payload, sender_id)
                        return "OK", 200
                        
                    if current_session_state.startswith("FORM_"):
                        response_text = handle_form_input(sender_id, message_text)
                        if response_text != "QR_SENT":
                            send_message(sender_id, response_text, current_state="AI")
                        return "OK", 200

                    # 5. RÉPONSE IA GÉNÉRALE
                    if message_text.strip():
                        response_text = get_bot_response(message_text, sender_id)
                        if response_text and response_text not in ["QR_SENT", ""]:
                            send_message(sender_id, response_text, current_state="AI")
                        return "OK", 200
                        
    return "OK", 200

if __name__ == '__main__':
    print(f"Démarrage du bot Messenger pour {PAGE_NAME}...")
    app.run(host='0.0.0.0', port=os.environ.get('PORT', 5000))
