from flask import Flask, request
import requests
import os
import json
import unicodedata
from groq import Groq
from supabase import create_client

app = Flask(__name__)

# =========================================
# VARIABLES D'ENVIRONNEMENT
# =========================================
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

print("=================================", flush=True)
print("HAPHAK AI STARTING...", flush=True)
print("VERIFY_TOKEN:", "OK" if VERIFY_TOKEN else "MISSING", flush=True)
print("WHATSAPP_TOKEN:", "OK" if WHATSAPP_TOKEN else "MISSING", flush=True)
print("PHONE_NUMBER_ID:", PHONE_NUMBER_ID, flush=True)
print("GROQ_API_KEY:", "OK" if GROQ_API_KEY else "MISSING", flush=True)
print("=================================", flush=True)

# =========================================
# INITIALISATION DES CLIENTS
# =========================================
client = None
try:
    if GROQ_API_KEY:
        client = Groq(api_key=GROQ_API_KEY)
        print("GROQ READY", flush=True)
    else:
        print("NO GROQ API KEY FOUND", flush=True)
except Exception as e:
    print("GROQ INIT ERROR:", str(e), flush=True)

supabase = None
try:
    if SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY:
        supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
        print("SUPABASE READY", flush=True)
    else:
        print("SUPABASE CONFIG MISSING", flush=True)
except Exception as e:
    print("SUPABASE ERROR:", str(e), flush=True)

# =========================================
# FONCTIONS UTILITAIRES & PERSISTANCE
# =========================================
def save_conversation(phone, role, message):
    try:
        if not supabase: return
        supabase.table("conversations").insert({
            "telephone": phone,
            "role": role,
            "message": message
        }).execute()
    except Exception as e:
        print("SAVE CONVERSATION ERROR:", str(e), flush=True)

def save_user_initial(phone):
    """Crée l'utilisateur dès le premier contact s'il n'existe pas encore."""
    try:
        if not supabase: return
        existing = supabase.table("users").select("*").eq("telephone", phone).execute() 
        if existing.data: return 
        supabase.table("users").insert({ "telephone": phone }).execute() 
    except Exception as e: 
        print("SAVE USER INITIAL ERROR:", repr(e), flush=True) 

def get_conversation_history(phone):
    try:
        if not supabase: return []
        result = supabase.table("conversations").select("*").eq("telephone", phone).order("created_at", desc=True).limit(10).execute() 
        rows = result.data 
        rows.reverse() 
        return [{"role": row["role"], "content": row["message"]} for row in rows]
    except Exception as e: 
        print("HISTORY ERROR:", str(e), flush=True) 
        return [] 

# =========================================
# ROUTES FLASK & WEBHOOKS
# =========================================
@app.route("/")
def home():
    return "HAPHAK Smart Agent is running with DB Architecture!", 200

@app.route("/webhook", methods=["GET"])
def verify_webhook():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if mode == "subscribe" and token == VERIFY_TOKEN: 
        return challenge, 200 
    return "Verification failed", 403 

@app.route("/webhook", methods=["POST"])
def webhook():
    try: 
        data = request.get_json() 
        entry = data.get("entry", []) 
        if not entry: return "OK", 200 
        changes = entry[0].get("changes", []) 
        if not changes: return "OK", 200 
        value = changes[0].get("value", {}) 
        messages = value.get("messages") 
        if not messages: return "OK", 200 
        
        message = messages[0] 
        user_number = message.get("from") 
        user_text = message.get("text", {}).get("body", "") 
        
        # Enregistrement initial du message
        save_user_initial(user_number) 
        save_conversation(user_number, "user", user_text) 
        if not user_text: return "OK", 200 
            
        reply = "Bonjour. Le service IA n'est actuellement pas disponible." 
        try: 
            if client: 
                history = get_conversation_history(user_number) 
                
                system_prompt = """Tu es Haphak Smart Agent / Green Agro. 

Tu aides :
producteurs
acheteurs
transporteurs
entreprises
citoyens

Tu travaille dans plusieurs pays et plusieurs langues.

Tu dois toujours :
Répondre normalement au client.
Comprendre son profil.
Identifier son rôle.

Les rôles possibles :
producteur
acheteur
transporteur
entreprise
citoyen

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
Exemple acheteur :
{
"role": "acheteur",
"nom": "Jean",
"produit": "maïs",
"quantite": "10 tonnes",
"localisation": "Goma"
}

Si une information est inconnue, mets null.
Le JSON doit toujours être valide."""
                
                messages_for_ai = [{"role": "system", "content": system_prompt}] 
                messages_for_ai.extend(history) 
                messages_for_ai.append({"role": "user", "content": user_text}) 
                
                completion = client.chat.completions.create( 
                    model="llama-3.3-70b-versatile", 
                    messages=messages_for_ai, 
                    temperature=0.7, 
                    max_tokens=800 
                ) 
                reply = completion.choices[0].message.content 
                
                # Analyse de la réponse et traitement de la donnée structurée
                if "===HAPHAK_JSON===" in reply: 
                    try: 
                        text_part, json_part = reply.split("===HAPHAK_JSON===", 1) 
                        reply = text_part.strip() 
                        json_data = json.loads(json_part.strip()) 
                        
                        # EXECUTION TRANSACTIONNELLE UNIQUE VIA RPC (Supabase gère tout le matching)
                        print(f"Lancement du traitement RPC pour {user_number}...", flush=True)
                        rpc_response = supabase.rpc(
                            "process_haphak_transactional", 
                            {
                                "p_phone": user_number,
                                "p_json_data": json_data
                            }
                        ).execute()
                        
                        print(f"RPC RESULT: {rpc_response.data}", flush=True)
                        
                    except Exception as e: 
                        print("JSON PARSE OR RPC EXECUTION ERROR:", str(e), flush=True) 
                        
                save_conversation(user_number, "assistant", reply) 
        except Exception as groq_error: 
            print("GROQ ERROR:", str(groq_error), flush=True) 
            
        # Envoi de la réponse finale à l'utilisateur sur WhatsApp
        url = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages" 
        headers = { "Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json" } 
        payload = { 
            "messaging_product": "whatsapp", 
            "to": user_number, 
            "type": "text", 
            "text": { "body": reply[:4096] } 
        } 
        requests.post(url, headers=headers, json=payload, timeout=30) 
    except Exception as e: 
        print("GENERAL ERROR:", str(e), flush=True) 
    return "OK", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
