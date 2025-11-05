import os
import requests
import json
import uuid
from flask import Flask, request, jsonify
# Nécessite 'furl' dans requirements.txt pour la construction de l'URL QR
from furl import furl 

# --- CONFIGURATION & JETONS ---
# REMPLACEZ CES VALEURS PAR VOS JETONS RÉELS
VERIFY_TOKEN = os.environ.get('VERIFY_TOKEN', 'tata')
PAGE_ACCESS_TOKEN = os.environ.get('PAGE_ACCESS_TOKEN', 'EAAI12hLrtqEBPZBccglgG0GuViPKTSxldQsBjMXbDf68ZCY4ZApZAuV2Wo8kwMnBoUqZCmQR0fOAGN5IZAhujkjtzbrGxQkCm5BZAnqXiZBnYsXEVZAdHi7JQSk7bUaKOTqru7K4wzl3XfUiGtgqfwx2CyvIay8PvrWL5JLAwgJ52BbZCE3q7v2SAQNZBbBPjP4ZCUHxMkD7mLimWfQsBGZCYf2dh5QZDZD')
PAGE_NAME = "Aigle Vision Mada"
EXTERNAL_API_URL = "https://rest-api-o42n.onrender.com/api/chatgpt5"
QR_API_URL = "https://api.qrserver.com/v1/create-qr-code/" 

# ID FACEBOOK DE L'ADMINISTRATEUR
ADMIN_SENDER_ID = os.environ.get('ADMIN_ID', 'VOTRE_ADMIN_ID_NUMERIQUE')
BASE_SYSTEM_PROMPT = f"Tu es le bot amical de {PAGE_NAME}. Tu proposes des formations en travail en ligne et des proxys de qualité à prix abordable."

# --- DONNÉES ET TARIFS (MIS À JOUR) ---
PROXY_PRICE_DISPLAY = "47 000 Ar (pour un proxy résidentiel, 1 mois)"
PROXY_COST_AR = 47000 
FORMATION_COST_AR = 120000 
PASSPORT_COST_AR = 40000 

# --- ÉTATS DE SESSION ---
user_session_state = {} 

app = Flask(__name__)

# --- MESSAGE DE BIENVENUE EN MALGACHE ---
WELCOME_MESSAGE_MG = (
    "Tongasoa eto amin'ny pejy **Aigle Vision Mada**! 🦅\n\n"
    "Manolotra **fiofanana feno momba ny Survey sy Microtache** izahay, hahafahanao miasa sy mahazo vola amin'ny aterineto. Vonona hanampy anao izahay.\n\n"
    "Kitiho ny bokotra **\"Offres\"** na **\"Formation\"** hijerena ny antsipiriany!"
)

# --- DÉFINITION DES ÉTAPES DU FORMULAIRE ---
FORM_PASSPORT = {
    "start_field": "nom_prenom",
    # Montant mis à jour dans la question
    "start_question": f"Pour la création de votre passeport de vérification d'identité ({PASSPORT_COST_AR:,} Ar), quel est votre **Nom et Prénom** ?",
    "steps": [
        ("numero_mobile", "Quel est votre **Numéro de mobile** ?", ),
        ("adresse", "Quelle est votre **Adresse** complète ?", ),
        # Montant mis à jour dans la confirmation
        ("confirmation", f"Merci ! Veuillez confirmer la demande de passeport ({PASSPORT_COST_AR:,} Ar) : (OUI pour valider)"),
    ],
    "end_message": "DEMANDE DE PASSEPORT"
}

FORM_STEPS = {
    "FORM_FORMATION": {
        "start_field": "nom_prenom",
        # Montant mis à jour dans la question
        "start_question": f"Parfait ! Pour l'inscription à la formation ({FORMATION_COST_AR:,} Ar), quel est votre **Nom et Prénom** ?",
        "steps": [
            ("numero_mobile", "Quel est votre **Numéro de mobile** ?", ),
            ("adresse", "Quelle est votre **Adresse** complète ?", ),
            ("competence", "Avez-vous de l'expérience concernant les **sondages en ligne** ? (Oui/Non ou précisez vos compétences)"),
            # Montant mis à jour dans la confirmation
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
        print(f"Erreur lors de l'envoi de la notification admin : {e}")
        return False

def send_message(recipient_id, message_text, current_state="AI"):
    """Envoie une réponse à l'utilisateur avec les boutons d'action (Quick Replies)."""
    
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

    url = f"https://graph.facebook.com/v18.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
    requests.post(url, json=message_data)

def upload_and_send_image(recipient_id, image_url):
    """
    Télécharge le QR code en mémoire et l'uploade sur Facebook pour contourner robots.txt.
    """
    print(f"--- Tentative d'upload du QR Code depuis {image_url} ---")
    
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
        return data.get("result", "Je suis désolé, l'IA externe n'a pas pu générer de réponse pour l'instant.")
    except requests.exceptions.RequestException as e:
        return "🤖 Je rencontre un problème technique pour la réponse complexe. Veuillez réessayer plus tard."


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
        
        if current_field == "nombre_proxy":
            try:
                num_proxy = int(message_text.strip())
                if num_proxy <= 0:
                    raise ValueError("Nombre doit être positif")
                data[current_field] = num_proxy 
            except ValueError:
                return "❌ Veuillez entrer un **nombre entier positif** valide pour le nombre de proxys."
        
        elif current_field == "confirmation":
            if message_text.lower() == "oui":
                # --- GÉNÉRATION DE LA TRANSACTION ET DU RÉSUMÉ ---
                transaction_id = str(uuid.uuid4()).replace('-', '')[:15].upper() 
                
                # Calculs et messages
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
                    cost = num_proxy * PROXY_COST_AR
                    
                    recap_message = (
                        f"🛒 NOUVELLE COMMANDE PROXY - {PAGE_NAME} 🛒\n"
                        f"Nom: **{data.get('nom_prenom', 'N/A')}**\n"
                        f"Adresse: {data.get('adresse', 'N/A')}\n"
                        f"Numéro de mobile: {data.get('numero_mobile', 'N/A')} \n"
                        f"Nombre de Proxy: {num_proxy}\n" 
                        f"Estimation de coût: {cost:,.0f} Ar\n"
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

                # --- GÉNÉRATION ET ENVOI DU QR CODE (avec furl) ---
                qr_code_url = furl(QR_API_URL).add({
                    "size": "150x150",
                    "data": qr_data
                }).url
                
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
    
    # --- GESTION DES BOUTONS D'OFFRE : FORMATION (Message très détaillé en Malgache) ---
    if "offer_formation_info" == message_text_lower: 
        
        # NOUVEAU TEXTE DE DESCRIPTION DE LA FORMATION EN MALGACHE (avec mise en forme)
        message_text = (
            "💰 **FIOFANANA SURVEYS SY MICRO-TÂCHES** 💰\n\n"
            "Raha mahazo ny teny **Frantsay na Anglisy** dia ity ny asa tena mety @nao.\n\n"
            "Ny surveys sy ny Micro-tâches dia anisan'ireo asa tsara karama ary azahoana **3$ - 10$ / jour** raha ampy information sy technique ho entina manao azy ianao.\n\n"
            "Tsy mila compétence sy diplôma, ary tsy sarotra tompoko ny surveys. Ny valiny ihany koa dia efa omeny eo fa isika no misafidy, ka ny **Paik'ady** no mila ananana.\n\n"
            "Tsy misy fetra ny fotoana iasana, fa izay tianao afaka miasa **24h/24h ary 7j/7j**.\n\n"
            "**Zavatra ilaiana raha te hanao ilay asa:**\n"
            "* 📱 Téléphone ou Ordinateur\n"
            "* 🌐 Connexion Internet (Data mobile ou Wi-Fi)\n\n"
            "**Programme de Formation Complet (de A à Z) sur Timebucks USA sy d'autres Plate-forme:**\n"
            "1. Introduction & Bases fondamentales\n"
            "2. Création Gmail sans numéro illimité\n"
            "3. Tous les outils nécessaires\n"
            "4. Bases fondamentales sy achat de Proxy\n"
            "5. Test sy installation de Proxy\n"
            "6. Procédure de création des comptes USA Timebucks sy d'autres Plate-forme\n"
            "7. Procédure de création Profil surveys optimisé\n"
            "8. Simulation des travaux avec stratégies\n"
            "9. Création Portefeuille électronique & Vérification KYC\n"
            "10. Les démarches de retrait\n"
            "11. Bonus, Compte, Proxy, ID étrangère\n"
            "**Miasa avy hatrany rehefa vita ny formation!**\n\n"
            "**Types de formation:**\n"
            "| Ligne | Date/Heure | Lieu/Note |\n"
            "|:---|:---|:---|\n"
            "| **En Ligne** | 9h-12h, 14h-18h / Spécial nuit 21h+ | Par appel vidéo, live |\n"
            "| **Présentiel** | 8 - 20 Nov. 2025 | FIANARANTSOA (Andrainjato) |\n"
            "| **Présentiel** | 22 Nov. 2025 | ANTSIRABE (Limité 10 personnes) |\n"
            "| **Présentiel** | 29 Nov. 2025 | ANTANANARIVO (Limité 20 personnes) |\n"
            "| **Présentiel** | 6 Déc. 2025 | MORONDAVA (Limité 10 personnes) |\n\n"
            "**✅ Avec suivi illimité!**\n"
            "**✅ Garantie:** Compte vérifié KYC et retrait succès.\n"
            f"**💰 Frais de formation: {FORMATION_COST_AR:,} Ar (Présentiel ou en ligne)**\n\n"
            "Aza tara misoratra anarana sy manao réservation fa sao feno ny toerana.\n"
            "**Fisoratanana anarana sy Fakana fanazavana fanampiny any amin'ny Mp, WhatsApp, Appel direct, na Manatona mivantana aty Andrainjato hoan'ny eto Fianarantsoa**\n"
            "**Contact: 038 49 115 97 (WhatsApp)**"
        )
        
        quick_replies = [
            {"content_type": "text", "title": "S'inscrire à la formation", "payload": "START_FORM_FORMATION"},
        ]
        
        # Envoi du message détaillé
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
                
                # Initialisation de la session
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
                        # Utilisez le payload pour que get_bot_response sache quelle info afficher
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
                        if response_text and response_text != "QR_SENT":
                            send_message(sender_id, response_text, current_state="AI")
                        return "OK", 200
                        
    return "OK", 200

if __name__ == '__main__':
    print(f"Démarrage du bot Messenger pour {PAGE_NAME}...")
    app.run(host='0.0.0.0', port=os.environ.get('PORT', 5000))
