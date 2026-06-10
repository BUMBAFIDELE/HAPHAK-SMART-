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

# =========================
# GEMINI SETUP
# =========================
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.5-flash")

# =========================
# HOME ROUTE
# =========================
@app.route("/")
def home():
    return "HAPHAK AI is running!"


# =========================
# WEBHOOK VERIFICATION (META)
# =========================
@app.route("/webhook", methods=["GET"])
def verify_webhook():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200

    return "Verification failed", 403


# =========================
# RECEIVE WHATSAPP MESSAGES
# =========================
@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()
    print("DATA RECEIVED:", data)

    try:
        # Lire message WhatsApp
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
        user_text = message.get("text", {}).get("body")
        user_number = message.get("from")

        if not user_text:
            return "OK", 200

        # =========================
        # GEMINI RESPONSE
        # =========================
        response = model.generate_content(user_text)
        reply = response.text

        # =========================
        # SEND BACK TO WHATSAPP
        # =========================
        url = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"

        headers = {
            "Authorization": f"Bearer {WHATSAPP_TOKEN}",
            "Content-Type": "application/json"
        }

        payload = {
            "messaging_product": "whatsapp",
            "to": user_number,
            "text": {"body": reply}
        }

        requests.post(url, headers=headers, json=payload)

    except Exception as e:
        print("ERROR:", e)

    return "OK", 200


# =========================
# RUN APP
# =========================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
