from flask import Flask, request
import requests
import os
from groq import Groq
from supabase import create_client

app = Flask(__name__)

# =========================
# VARIABLES D'ENVIRONNEMENT
# =========================

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_PUBLISHABLE_KEY = os.getenv("SUPABASE_PUBLISHABLE_KEY")

print("=================================", flush=True)
print("HAPHAK AI STARTING...", flush=True)
print("VERIFY_TOKEN:", "OK" if VERIFY_TOKEN else "MISSING", flush=True)
print("WHATSAPP_TOKEN:", "OK" if WHATSAPP_TOKEN else "MISSING", flush=True)
print("PHONE_NUMBER_ID:", PHONE_NUMBER_ID, flush=True)
print("GROQ_API_KEY:", "OK" if GROQ_API_KEY else "MISSING", flush=True)
print("=================================", flush=True)

# =========================
# INITIALISATION GROQ
# =========================

client = None

try:
    if GROQ_API_KEY:
        client = Groq(api_key=GROQ_API_KEY)
        print("GROQ READY", flush=True)
    else:
        print("NO GROQ API KEY FOUND", flush=True)
except Exception as e:
    print("GROQ INIT ERROR:", str(e), flush=True)

# =========================
# INITIALISATION SUPABASE
# =========================

supabase = None

try:
    if SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY:
        supabase = create_client(SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY)
        print("SUPABASE READY", flush=True)
    else:
        print("SUPABASE CONFIG MISSING", flush=True)
except Exception as e:
    print("SUPABASE ERROR:", str(e), flush=True)

# =========================
# FONCTIONS UTILITAIRES
# =========================

def save_conversation(phone, role, message):
    try:
        if not supabase:
            return
        supabase.table("conversations").insert({
            "telephone": phone,
            "role": role,
            "message": message
        }).execute()
    except Exception as e:
        print("SAVE CONVERSATION ERROR:", str(e), flush=True)

def save_user(phone):
    try:
        if not supabase:
            return

        existing = (
            supabase
            .table("users")
            .select("id")
            .eq("telephone", phone)
            .execute()
        )

        if existing.data:
            return

        supabase.table("users").insert({
            "telephone": phone
        }).execute()

        print("NEW USER CREATED:", phone, flush=True)
    except Exception as e:
        print("SAVE USER ERROR:", str(e), flush=True)

def update_user_role(phone, role):
    try:
        if not supabase:
            return

        supabase.table("users").update({
            "role": role
        }).eq("telephone", phone).execute()

        print(f"ROLE UPDATED: {phone} -> {role}", flush=True)
    except Exception as e:
        print("ROLE UPDATE ERROR:", str(e), flush=True)

def get_conversation_history(phone):
    try:
        if not supabase:
            return []

        result = (
            supabase
            .table("conversations")
            .select("*")
            .eq("telephone", phone)
            .order("created_at", desc=True)
            .limit(10)
            .execute()
        )

        rows = result.data
        rows.reverse()

        history = []
        for row in rows:
            history.append({
                "role": row["role"],
                "content": row["message"]
            })
        return history
    except Exception as e:
        print("HISTORY ERROR:", str(e), flush=True)
        return []

# =========================
# PAGE D'ACCUEIL
# =========================

@app.route("/")
def home():
    return "HAPHAK Smart Agent is running!", 200

# =========================
# WEBHOOK VERIFY (GET)
# =========================

@app.route("/webhook", methods=["GET"])
def verify_webhook():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    print("VERIFY REQUEST RECEIVED", flush=True)

    if mode == "subscribe" and token == VERIFY_TOKEN:
        print("WEBHOOK VERIFIED", flush=True)
        return challenge, 200

    return "Verification failed", 403

# =========================
# WEBHOOK MESSAGE (POST)
# =========================

@app.route("/webhook", methods=["POST"])
def webhook():
    print("WEBHOOK HIT", flush=True)

    try:
        data = request.get_json()

        print("PAYLOAD:", flush=True)
        print(data, flush=True)

        entry = data.get("entry", [])
        if not entry:
            return "OK", 200

        changes = entry[0].get("changes", [])
        if not changes:
            return "OK", 200

        value = changes[0].get("value", {})
        messages = value.get("messages")
        if not messages:
            return "OK", 200

        message = messages[0]
        user_number = message.get("from")
        user_text = message.get("text", {}).get("body", "")
        
        save_user(user_number)
        save_conversation(user_number, "user", user_text)
        
        print("FROM:", user_number, flush=True)
        print("TEXT:", user_text, flush=True)

        if not user_text:
            return "OK", 200

        # =========================
        # APPEL GROQ
        # =========================
        reply = "Bonjour. Le service IA n'est actuellement pas disponible."

        try:
            if client:
                print("CALLING GROQ...", flush=True)

                history = get_conversation_history(user_number)

                # Correction ici : Définition propre du prompt système
                system_prompt = """Tu es Haphak Smart Agent / Green Agro.

Tu aides :
- producteurs
- acheteurs
- transporteurs
- entreprises
- citoyens

Tu travaille dans plusieurs pays et plusieurs langues.

Tu dois toujours :
1. Répondre normalement au client.
2. Comprendre son profil.
3. Identifier son rôle.

Les rôles possibles :
- producteur
- acheteur
- transporteur
- entreprise
- citoyen

A la fin de chaque réponse ajoute exactement :
===HAPHAK_JSON===
puis un JSON valide contenant les informations détectées.

Exemple :
{
  "role": "producteur",
  "nom": "Fidele",
  "produits": [
    {"culture": "maïs", "quantite": "5 tonnes"}
  ]
}

Si une information est inconnue, mets null.
Le JSON doit toujours être valide."""

                # Construction correcte du tableau de messages pour Groq
                messages_for_ai = [
                    {"role": "system", "content": system_prompt}
                ]
                
                # Ajout de l'historique et du message actuel
                messages_for_ai.extend(history)
                messages_for_ai.append({
                    "role": "user",
                    "content": user_text
                })

                print("HISTORY SENT TO AI:", flush=True)
                print(messages_for_ai, flush=True)

                completion = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=messages_for_ai,
                    temperature=0.7,
                    max_tokens=800
                )

                reply = completion.choices[0].message.content

                save_conversation(user_number, "assistant", reply)
                print("GROQ SUCCESS", flush=True)

        except Exception as groq_error:
            print("GROQ ERROR:", str(groq_error), flush=True)
            reply = "Bonjour. Votre message a été reçu mais le service IA est temporairement indisponible."

        # =========================
        # ENVOI WHATSAPP
        # =========================
        url = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"

        headers = {
            "Authorization": f"Bearer {WHATSAPP_TOKEN}",
            "Content-Type": "application/json"
        }

        payload = {
            "messaging_product": "whatsapp",
            "to": user_number,
            "type": "text",
            "text": {
                "body": reply[:4096]
            }
        }

        print("SENDING MESSAGE...", flush=True)

        r = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=30
        )

        print("STATUS:", r.status_code, flush=True)
        print("RESPONSE:", r.text, flush=True)

    except Exception as e:
        print("GENERAL ERROR:", str(e), flush=True)

    return "OK", 200

# =========================
# LANCEMENT
# =========================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
