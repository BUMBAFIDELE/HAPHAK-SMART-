from flask import Flask, request

app = Flask(__name__)

@app.route("/")
def home():
    return "HAPHAK AI is running!"

@app.route("/webhook", methods=["GET"])
def verify():
    verify_token = "haphak2026"

    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == verify_token:
        return challenge, 200

    return "Verification failed", 403

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
