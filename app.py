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
    model = genai.GenerativeModel("gemini-1.5-flash")
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

    print("\n=================================")
    print("WEBHOOK HIT")
    print("=================================")

    data = request.get_json()

    print("RAW DATA:")
    print(data)

    try:

        entry = data.get("entry", [])
        print("ENTRY:", entry)

        if not entry:
            print("No entry found")
            return "OK", 200

        changes = entry[0].get("changes", [])
        print("CHANGES:", changes)

        if not changes:
            print("No changes found")
            return "OK", 200

        value = changes[0].get("value", {})
        print("VALUE:", value)

        messages = value.get("messages")
        print("MESSAGES:", messages)

        if not messages:
            print("No messages in webhook")
            return "OK", 200

        message = messages[0]

        user_number = message.get("from")
        user_text = message.get("text", {}).get("body")

        print("USER NUMBER:", user_number)
        print("USER TEXT:", user_text)

        if not user_text:
            print("No text content")
            return "OK", 200

        if model is None:
            print("Gemini model unavailable")
            return "OK", 200

        # =========================
        # GEMINI
        # =========================

        print("CALLING GEMINI...")

        response = model.generate_content(user_text)

        print("GEMINI RESPONSE RECEIVED")

        reply = response.text

        print("AI REPLY:")
        print(reply)

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

        print("SENDING TO WHATSAPP...")
        print("URL:", url)

        r = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=30
        )

        print("WHATSAPP STATUS CODE:", r.status_code)
        print("WHATSAPP RESPONSE:")
        print(r.text)

    except Exception as e:
        print("=================================")
        print("ERROR OCCURRED")
        print(str(e))
        print("=================================")

    return "OK", 200

# =========================
# RUN APP
# =========================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
