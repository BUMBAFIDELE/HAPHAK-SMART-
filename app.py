from flask import Flask, request
import requests
import os
import google.generativeai as genai

app = Flask(__name__)

# =========================
# ENV VARIABLES
# =========================
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

print("=================================")
print("APPLICATION STARTING")
print("VERIFY_TOKEN:", "OK" if VERIFY_TOKEN else "MISSING")
print("WHATSAPP_TOKEN:", "OK" if WHATSAPP_TOKEN else "MISSING")
print("PHONE_NUMBER_ID:", PHONE_NUMBER_ID)
print("GEMINI_API_KEY:", "OK" if GEMINI_API_KEY else "MISSING")
print("=================================")

# =========================
# GEMINI SETUP
# =========================
try:
    genai.configure(api_key=GEMINI_API_KEY)

    model = genai.GenerativeModel("gemini-2.0-flash")

    print("Gemini initialized successfully")

except Exception as e:
    print("GEMINI INIT ERROR:", str(e))
    model = None

# =========================
# HOME ROUTE
# =========================
@app.route("/")
def home():
    return "HAPHAK AI is running!"

# =========================
# WEBHOOK VERIFICATION
# =========================
@app.route("/webhook", methods=["GET"])
def verify_webhook():

    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    print("Webhook verification request received")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        print("Webhook verified successfully")
        return challenge, 200

    print("Webhook verification failed")
    return "Verification failed", 403

# =========================
# RECEIVE WHATSAPP MESSAGES
# =========================
@app.route("/webhook", methods=["POST"])
def webhook():

    print("\n=================================", flush=True)
    print("WEBHOOK HIT", flush=True)
    print("=================================", flush=True)

    data = request.get_json()

    print("RAW DATA:", flush=True)
    print(data, flush=True)

    try:

        entry = data.get("entry", [])

        if not entry:
            print("No entry found", flush=True)
            return "OK", 200

        changes = entry[0].get("changes", [])

        if not changes:
            print("No changes found", flush=True)
            return "OK", 200

        value = changes[0].get("value", {})

        messages = value.get("messages")

        if not messages:
            print("No messages in webhook", flush=True)
            return "OK", 200

        message = messages[0]

        user_number = message.get("from")
        user_text = message.get("text", {}).get("body")

        print("USER NUMBER:", user_number, flush=True)
        print("USER TEXT:", user_text, flush=True)

        if not user_text:
            return "OK", 200

        if model is None:
            print("Gemini model unavailable", flush=True)
            return "OK", 200

        # =========================
        # GEMINI
        # =========================

        print("CALLING GEMINI...", flush=True)

        response = model.generate_content(user_text)

        print("GEMINI RESPONSE RECEIVED", flush=True)

        reply = response.text

        print("AI REPLY:", flush=True)
        print(reply, flush=True)

        # =========================
        # SEND TO WHATSAPP
        # =========================

        url = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"

        headers = {
            "Authorization": f"Bearer {WHATSAPP_TOKEN}",
            "Content-Type": "application/json"
        }

        payload = {
            "messaging_product": "whatsapp",
            "to": user_number,
            "text": {
                "body": reply
            }
        }

        print("SENDING TO WHATSAPP...", flush=True)

        r = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=30
        )

        print("WHATSAPP STATUS CODE:", r.status_code, flush=True)
        print("WHATSAPP RESPONSE:", flush=True)
        print(r.text, flush=True)

    except Exception as e:

        print("=================================", flush=True)
        print("ERROR OCCURRED", flush=True)
        print(str(e), flush=True)
        print("=================================", flush=True)

    return "OK", 200

# =========================
# RUN APP
# =========================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
