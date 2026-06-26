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

def save_user(phone):
    try:
        if not supabase: return
        existing = supabase.table("users").select("*").eq("telephone", phone).execute() 
        if existing.data: return 
        supabase.table("users").insert({ "telephone": phone }).execute() 
    except Exception as e: 
        print("SAVE USER ERROR:", repr(e), flush=True) 

def update_user_role(phone, role):
    try:
        if not supabase: return
        supabase.table("users").update({ "role": role }).eq("telephone", phone).execute() 
    except Exception as e: 
        print("ROLE UPDATE ERROR:", str(e), flush=True) 

def update_user_profile(phone, json_data):
    try:
        if not supabase: return
        
        # Amélioration n°3 : Construction dynamique pour éviter d'écraser par du null
        updates = {}
        if json_data.get("nom"): updates["nom"] = json_data.get("nom")
        if json_data.get("role"): updates["role"] = json_data.get("role")
        if json_data.get("localisation"): updates["territoire"] = json_data.get("localisation")
        
        if updates:
            supabase.table("users").update(updates).eq("telephone", phone).execute() 
            print("USER PROFILE UPDATED SANS ECRASEMENT NULL", flush=True) 
    except Exception as e: 
        print("USER PROFILE ERROR:", str(e), flush=True) 

def save_profile(phone, json_data):
    try:
        if not supabase: return
        role = json_data.get("role") 
        
        if role == "producteur": 
            produits = json_data.get("produits", []) 
            for produit in produits: 
                culture = produit.get("culture")
                if not culture: continue
                existing = supabase.table("producteurs").select("*").eq("telephone", phone).eq("cultures", culture).execute()

                if existing.data:
                    supabase.table("producteurs").update({
                        "nom": json_data.get("nom"),
                        "quantite": produit.get("quantite"),
                        "territoire": json_data.get("localisation")
                    }).eq("id", existing.data[0]["id"]).execute()
                else:
                    supabase.table("producteurs").insert({
                        "telephone": phone,
                        "nom": json_data.get("nom"),
                        "cultures": normalize(culture),
                        "quantite": produit.get("quantite"),
                        "territoire": json_data.get("localisation")
                    }).execute()
                
        elif role == "acheteur": 
            produit = json_data.get("produit")
            if not produit: return
            existing = supabase.table("acheteurs").select("*").eq("telephone", phone).eq("produit", produit).execute()

            if existing.data:
                supabase.table("acheteurs").update({
                    "nom": json_data.get("nom"),
                    "quantite": json_data.get("quantite"),
                    "region": json_data.get("localisation")
                }).eq("id", existing.data[0]["id"]).execute()
            else:
                supabase.table("acheteurs").insert({
                    "telephone": phone,
                    "nom": json_data.get("nom"),
                    "produit": normalize(produit),
                    "quantite": json_data.get("quantite"),
                    "region": json_data.get("localisation")
                }).execute()
                
        elif role == "transporteur": 
            supabase.table("transporteurs").insert({ 
                "telephone": phone, "nom": json_data.get("nom"), 
                "vehicule": json_data.get("vehicule"), "capacite": json_data.get("capacite"), 
                "region": json_data.get("localisation") 
            }).execute() 
            
        elif role == "citoyen": 
            if json_data.get("type_dechet"): 
                supabase.table("dechets").insert({ 
                    "telephone": phone, "nom": json_data.get("nom"), 
                    "type_dechet": json_data.get("type_dechet"), "quantite": json_data.get("quantite"), 
                    "localisation": json_data.get("localisation") 
                }).execute() 
        print("PROFILE SAVED", flush=True) 
    except Exception as e: 
        print("PROFILE SAVE ERROR:", str(e), flush=True) 

# =========================================
# MOTEUR DE MATCHING AUTOMATIQUE
# =========================================
def check_matching(phone, json_data):
    try:
        if not supabase: return
        role = json_data.get("role")

        # Amélioration n°1 : Utilisation de ilike() à la place de eq()
        if role == "producteur":
            produits = json_data.get("produits", [])
            for produit in produits:
                culture = normalize(produit.get("culture"))
                if not culture: continue
                
                acheteurs = supabase.table("acheteurs").select("*").ilike("produit", f"%{culture}%").execute()

                for acheteur in acheteurs.data:
                    # Amélioration n°2 : Déduplication avant création de l'alerte
                    existing_alert = (
                        supabase.table("alertes")
                        .select("*")
                        .eq("producteur_tel", phone)
                        .eq("acheteur_tel", acheteur["telephone"])
                        .eq("produit", culture)
                        .execute()
                    )
                    if not existing_alert.data:
                        supabase.table("alertes").insert({
                            "type_alerte": "matching_produit",
                            "produit": culture,
                            "producteur_tel": phone,
                            "acheteur_tel": acheteur["telephone"],
                            "message": f"Correspondance trouvée pour {culture}",
                            "statut": "nouvelle"
                        }).execute()

                    existing_transaction = (
                        supabase.table("transactions")
                        .select("*")
                        .eq("producteur_tel", phone)
                        .eq("acheteur_tel", acheteur["telephone"])
                        .eq("produit", normalize(culture))
                        .execute()
                    )
                    print("TRANSACTION CREATED", flush=True)

                    if not existing_transaction.data:
                        supabase.table("transactions").insert({
                            "produit": culture,
                            "producteur_tel": phone,
                            "acheteur_tel": acheteur["telephone"],
                            "statut": "matching"
                        }).execute()

        elif role == "acheteur":
            produit = normalize(json_data.get("produit"))
            if not produit: return
            
            producteurs = supabase.table("producteurs").select("*").ilike("cultures", f"%{produit}%").execute()

            for producteur in producteurs.data:
                # Amélioration n°2 : Déduplication avant création de l'alerte
                existing_alert = (
                    supabase.table("alertes")
                    .select("*")
                    .eq("producteur_tel", producteur["telephone"])
                    .eq("acheteur_tel", phone)
                    .eq("produit", normalize(produit))
                    .execute()
                )

                print("ALERTE CREATED", flush=True)
                
                if not existing_alert.data:
                    supabase.table("alertes").insert({
                        "type_alerte": "matching_produit",
                        "produit": produit,
                        "producteur_tel": producteur["telephone"],
                        "acheteur_tel": phone,
                        "message": f"Correspondance trouvée pour {produit}",
                        "statut": "nouvelle"
                    }).execute()

                existing_transaction = (
                    supabase.table("transactions")
                    .select("*")
                    .eq("producteur_tel", producteur["telephone"])
                    .eq("acheteur_tel", phone)
                    .eq("produit", produit)
                    .execute()
                )

                if not existing_transaction.data:
                    supabase.table("transactions").insert({
                        "produit": produit,
                        "producteur_tel": producteur["telephone"],
                        "acheteur_tel": phone,
                        "statut": "matching"
                    }).execute()
                    
        print("MATCHING DONE", flush=True)
    except Exception as e:
        print("MATCHING ERROR:", str(e), flush=True)

def normalize(text):
    if not text:
        return ""

    text = text.lower().strip()

    text = ''.join(
        c for c in unicodedata.normalize('NFD', text)
        if unicodedata.category(c) != 'Mn'
    )

    return text

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
    return "HAPHAK Smart Agent is running!", 200

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
        
        save_user(user_number) 
        save_conversation(user_number, "user", user_text) 
        if not user_text: return "OK", 200 
            
        reply = "Bonjour. Le service IA n'est actuellement pas disponible." 
        try: 
            if client: 
                history = get_conversation_history(user_number) 
                
                # Rétablissement du prompt complet d'origine
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
                
                if "===HAPHAK_JSON===" in reply: 
                    try: 
                        text_part, json_part = reply.split("===HAPHAK_JSON===", 1) 
                        reply = text_part.strip() 
                        json_data = json.loads(json_part.strip()) 
                        detected_role = json_data.get("role") 
                        if detected_role: 
                            update_user_role(user_number, detected_role) 
                            update_user_profile(user_number, json_data) 
                            save_profile(user_number, json_data)
                            check_matching(user_number, json_data)
                    except Exception as e: 
                        print("JSON PARSE ERROR:", str(e), flush=True) 
                        
                save_conversation(user_number, "assistant", reply) 
        except Exception as groq_error: 
            print("GROQ ERROR:", str(groq_error), flush=True) 
            
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
