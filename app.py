from flask import Flask, request
import requests
import os
import google.generativeai as genai

app = Flask(__name__)

# =========================
# VARIABLES D'ENVIRONNEMENT
# =========================

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

print("=================================", flush=True)
print("HAPHAK AI STARTING...", flush=True)
print("VERIFY_TOKEN:", "OK" if VERIFY_TOKEN else "MISSING", flush=True)
print("WHATSAPP_TOKEN:", "OK" if WHATSAPP_TOKEN else "MISSING", flush=True)
print("PHONE_NUMBER_ID:", PHONE_NUMBER_ID, flush=True)
print("GEMINI_API_KEY:", "OK" if GEMINI_API_KEY else "MISSING", flush=True)
print("=================================", flush=True)

# =========================
# INITIALISATION GEMINI
# =========================

model = None

try:
    if GEMINI_API_KEY:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-1.5-flash")
        print("GEMINI READY", flush=True)
    else:
        print("NO GEMINI API KEY FOUND", flush=True)

except Exception as e:
    print("GEMINI INIT ERROR:", str(e), flush=True)

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
        # APPEL GEMINI
        # =========================

        try:

            if model:

                print("CALLING GEMINI...", flush=True)

                response = model.generate_content(user_text)

                reply = response.text

                print("GEMINI SUCCESS", flush=True)

            else:

                reply = (
                    "Bonjour. Le service IA n'est actuellement pas disponible."
                )

        except Exception as gemini_error:

            print(
                "GEMINI ERROR:",
                str(gemini_error),
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
                "body": reply
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
