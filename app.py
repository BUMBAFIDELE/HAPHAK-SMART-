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

print("=== STARTUP ===")
print("VERIFY_TOKEN:", "OK" if VERIFY_TOKEN else "MISSING")
print("WHATSAPP_TOKEN:", "OK" if WHATSAPP_TOKEN else "MISSING")
print("PHONE_NUMBER_ID:", PHONE_NUMBER_ID)
print("GEMINI_API_KEY:", "OK" if GEMINI_API_KEY else "MISSING")

# =========================
# GEMINI SETUP
# =========================
genai.configure(api_key=GEMINI_API_KEY)

try:
    model = genai.GenerativeModel("gemini-1.5-flash")
    print("Gemini initialized successfully")
except Exception as e:
    print("GEMINI INIT ERROR:", str(e))

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

    print("Verification request received")

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

    print("\n==============================")
    print("WEBHOOK HIT")
    print("==============================")

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
            print("No message received")
            return "OK", 200

        message = messages[0]

        user_text = message.get("text", {}).get("body")
        user_number = message.get("from")

        print("USER NUMBER:", user_number)
        print("USER TEXT:", user_text)

        if not user_text:
            print("No text message")
            return "OK", 200

        # =========================
        # GEMINI
        # =========================

        print("Calling Gemini...")

        response = model.generate_content(user_text)

        reply = response.text

        print("Gemini response:")
        print(reply)

        # =========================
        # SEND TO WHATSAPP
        # =========================

        print("Sending reply to WhatsApp...")

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

        print("REQUEST URL:", url)
        print("REQUEST PAYLOAD:", payload)

        r = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=30
        )

        print("WHATSAPP STATUS:", r.status_code)
        print("WHATSAPP RESPONSE:")
        print(r.text)

    except Exception as e:
        print("===================================")
        print("ERROR OCCURRED")
        print(str(e))
        print("===================================")

    return "OK", 200

# =========================
# RUN
# =========================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
