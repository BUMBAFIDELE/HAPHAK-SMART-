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
print("=================================", flush=True)

# =========================================
# INITIALISATION DES CLIENTS
# =========================================
client = None
try:
    if GROQ_API_KEY:
        client = Groq(api_key=GROQ_API_KEY)
        print("GROQ READY", flush=True)
except Exception as e:
    print("GROQ INIT ERROR:", str(e), flush=True)

supabase = None
try:
    if SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY:
        supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
        print("SUPABASE READY", flush=True)
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
    return "HAPHAK Smart Agent is running with Native JSON Mode!", 200

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
        
        save_user_initial(user_number) 
        save_conversation(user_number, "user", user_text) 
        if not user_text: return "OK", 200 
            
        reply = "Bonjour. Le service IA n'est actuellement pas disponible." 
        try: 
            if client: 
                history = get_conversation_history(user_number) 
                
                # --- PREMIER APPEL : LA RÉPONSE TEXTE NATURELLE POUR L'UTILISATEUR ---
                system_prompt_text = "Tu es Haphak Smart Agent / Green Agro. Tu dialogues avec des producteurs, acheteurs, transporteurs, entreprises et citoyens en Afrique. Réponds chaleureusement, clairement et brièvement à l'utilisateur."
                messages_text = [{"role": "system", "content": system_prompt_text}]
                messages_text.extend(history)
                messages_text.append({"role": "user", "content": user_text})
                
                completion_text = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=messages_text,
                    temperature=0.7,
                    max_tokens=400
                )
                reply = completion_text.choices[0].message.content

                # --- DEUXIÈME APPEL : EXTRACTION STRUCTURÉE SÉCURISÉE (MODE JSON) ---
                system_prompt_json = """Tu es un extracteur de données strict. Analyse le message de l'utilisateur et génère UNIQUEMENT un objet JSON valide.
Les rôles possibles : producteur, acheteur, transporteur, entreprise, citoyen.

Structure attendue :
{
  "role": "producteur" ou "acheteur" ou "transporteur" ou "citoyen" ou null,
  "nom": "nom détecté ou null",
  "localisation": "ville ou territoire détecté ou null",
  "produit": "nom du produit (uniquement pour acheteur) ou null",
  "quantite": "quantité détectée ou null",
  "produits": [ {"culture": "maïs", "quantite": "5 tonnes"} ] (uniquement pour producteur)
}
Si une information est absente, mets null. Ne rajoute aucun texte explicatif en dehors du JSON."""

                messages_json = [{"role": "system", "content": system_prompt_json}, {"role": "user", "content": user_text}]
                
                completion_json = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=messages_json,
                    temperature=0.0, # Déterminisme maximal
                    response_format={"type": "json_object"}, # FORCE LE MODE JSON NATIVELEMENT
                    max_tokens=400
                )
                
                clean_json_str = completion_json.choices[0].message.content.strip()
                print(f"--- NATIVE JSON EXTRAIT --- : {clean_json_str}", flush=True)
                
                if clean_json_str:
                    try:
                        json_data = json.loads(clean_json_str)
                        
                        # Exécution de notre fonction RPC transactionnelle blindée
                        print(f"Lancement du traitement RPC pour {user_number}...", flush=True)
                        rpc_response = supabase.rpc(
                            "process_haphak_transactional", 
                            {"p_phone": user_number, "p_json_data": json_data}
                        ).execute()
                        print(f"RPC RESULT: {rpc_response.data}", flush=True)
                    except Exception as rpc_err:
                        print(f"RPC ERROR: {str(rpc_err)}", flush=True)
                        
                save_conversation(user_number, "assistant", reply) 
        except Exception as groq_error: 
            print("GROQ ERROR:", str(groq_error), flush=True) 
            
        # Envoi WhatsApp
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

# ==========================================================
# ÉTAPE 9 : ROUTE DE NOTIFICATION PUSH AUTOMATIQUE (WEBHOOK INTERNE)
# ==========================================================
@app.route("/send-matching-notification", methods=["POST"])
def send_matching_notification():
    try:
        data = request.get_json()
        print(f"WEBHOOK ALERTE REÇU DE SUPABASE : {data}", flush=True)
        
        record = data.get("record", {})
        if not record:
            return "No record found", 400
            
        acheteur_tel = record.get("acheteur_tel")
        producteur_tel = record.get("producteur_tel")
        produit = record.get("produit", "un produit")
        
        url = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages" 
        headers = { "Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json" } 
        
        if producteur_tel:
            msg_prod = f"Notification Haphak : Un acheteur recherche votre produit ({produit}). Nous initions la mise en relation !"
            payload_prod = { "messaging_product": "whatsapp", "to": producteur_tel, "type": "text", "text": { "body": msg_prod } }
            requests.post(url, headers=headers, json=payload_prod, timeout=30)
            
        if acheteur_tel:
            msg_ach = f"Notification Haphak : Nous avons trouvé un producteur correspondant à votre demande de ({produit}) !"
            payload_ach = { "messaging_product": "whatsapp", "to": acheteur_tel, "type": "text", "text": { "body": msg_ach } }
            requests.post(url, headers=headers, json=payload_ach, timeout=30)
            
        return "Notifications envoyées automatiquement", 200
    except Exception as e:
        print(f"ERROR IN SEND MATCHING NOTIFICATION: {str(e)}", flush=True)
        return "Internal Error", 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
