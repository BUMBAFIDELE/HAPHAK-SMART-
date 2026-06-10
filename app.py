from flask import Flask, request
import os

app = Flask(__name__)

@app.route("/")
def home():
    return "HAPHAK AI is running!"


@app.route("/webhook", methods=["GET"])
def verify():
    verify_token = os.getenv("VERIFY_TOKEN")

    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == verify_token:
        return challenge, 200

    return "Verification failed", 403


@app.route("/webhook", methods=["POST"])
def webhook():
    print("MESSAGE RECEIVED:", request.get_json())
    return "OK", 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
