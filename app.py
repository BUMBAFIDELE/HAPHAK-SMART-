from flask import Flask, request
import requests
import os
from groq import Groq

app = Flask(__name__)

# =========================
# VARIABLES D'ENVIRONNEMENT
# =========================

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

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

        client = Groq(
            api_key=GROQ_API_KEY
        )

        print("GROQ READY", flush=True)

    else:

        print("NO GROQ API KEY FOUND", flush=True)

except Exception as e:

    print("GROQ INIT ERROR:", str(e), flush=True)

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

        print("FROM:", user_number, flush=True)
        print("TEXT:", user_text, flush=True)

        if not user_text:
            return "OK", 200

        # =========================
        # APPEL GROQ
        # =========================

        try:

            if client:

                print("CALLING GROQ...", flush=True)

                completion = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[
                        {
                            "role": "system",
                            "content": """
Tu es HAPHAK Smart Agent.

Ton rôle :

- Répondre aux clients de manière professionnelle.
- Qualifier les prospects.
- Encourager la conversion en clients.
- Répondre dans la langue du client.
- Être poli, clair et utile.
- Si tu ne connais pas une information, dis-le honnêtement.
"""
                        },
                        {
                            "role": "user",
                            "content": user_text
                        }
                    ],
                    temperature=0.7,
                    max_tokens=800
                )

                reply = completion.choices[0].message.content

                print("GROQ SUCCESS", flush=True)

            else:

                reply = (
                    "Bonjour. Le service IA n'est actuellement pas disponible."
                )

        except Exception as groq_error:

            print(
                "GROQ ERROR:",
                str(groq_error),
                flush=True
            )

            reply = (
                "Bonjour. Votre message a été reçu mais le service IA est temporairement indisponible."
            )

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

    app.run(
        host="0.0.0.0",
        port=port
    )
