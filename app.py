from flask import Flask, request
import requests
import os
import json
from groq import Groq
from supabase import create_client

# Utilisation correcte de __name__
app = Flask(__name__)

# =========================================
# VARIABLES D'ENVIRONNEMENT
# =========================================
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_PUBLISHABLE_KEY = os.getenv("SUPABASE_PUBLISHABLE_KEY")

print("=================================", flush=True)
print("HAPHAK AI STARTING...", flush=True)
print("VERIFY_TOKEN:", "OK" if VERIFY_TOKEN else "MISSING", flush=True)
print("WHATSAPP_TOKEN:", "OK" if WHATSAPP_TOKEN else "MISSING", flush=True)
print("PHONE_NUMBER_ID:", PHONE_NUMBER_ID, flush=True)
print("GROQ_API_KEY:", "OK" if GROQ_API_KEY else "MISSING", flush=True)
print("=================================", flush=True)

# =========================================
# INITIALISATION GROQ
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

# =========================================
# INITIALISATION SUPABASE
# =========================================
supabase = None

try:
    if SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY:
        supabase = create_client(SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY)
        print("SUPABASE READY", flush=True)
    else:
        print("SUPABASE CONFIG MISSING", flush=True)
except Exception as e:
    print("SUPABASE ERROR:", str(e), flush=True)

# =========================================
# FONCTIONS UTILITAIRES
# =========================================
def save_conversation(phone, role, message):
    try:
        if not supabase:
            return
        supabase.table("conversations").insert({
            "telephone": phone,
            "role": role,
            "message": message
        }).execute()
    except Exception as e:
        print("SAVE CONVERSATION ERROR:", str(e), flush=True)

def save_user(phone):
    try:
        print("SAVE USER CALLED:", phone, flush=True)
        if not supabase: 
            print("SUPABASE NOT AVAILABLE", flush=True) 
            return
            
        existing = (
            supabase
            .table("users")
            .select("*")
            .eq("telephone", phone)
            .execute()
        ) 
        print("EXISTING USER:", existing.data, flush=True) 
        
        if existing.data: 
            print("USER ALREADY EXISTS", flush=True) 
            return 
            
        result = ( 
            supabase 
            .table("users") 
            .insert({ "telephone": phone }) 
            .execute() 
        ) 
        print("USER INSERT RESULT:", result.data, flush=True) 
    except Exception as e: 
        print("SAVE USER ERROR:", repr(e), flush=True) 

def update_user_role(phone, role):
    try:
        if not supabase:
            return
        supabase.table("users").update({ "role": role }).eq("telephone", phone).execute() 
        print(f"ROLE UPDATED: {phone} -> {role}", flush=True) 
    except Exception as e: 
        print("ROLE UPDATE ERROR:", str(e), flush=True) 

def update_user_profile(phone, json_data):
    try:
        if not supabase:
            return
        supabase.table("users").update({ 
            "nom": json_data.get("nom"), 
            "role": json_data.get("role"), 
            "territoire": json_data.get("localisation") 
        }).eq("telephone", phone).execute() 
        print("USER PROFILE UPDATED", flush=True) 
    except Exception as e: 
        print("USER PROFILE ERROR:", str(e), flush=True) 

def save_profile(phone, json_data):
    try:
        if not supabase:
            return

        role = json_data.get("role") 
        print("SAVE PROFILE JSON:", json_data, flush=True) 
        print("ROLE DETECTED:", role, flush=True) 
        
        # PRODUCTEUR 
        if role == "producteur": 
            produits = json_data.get("produits", []) 
            for produit in produits: 
                culture = culture

                if not culture:
                    continue
                existing = (
                    supabase
                    .table("producteurs")
                    .select("*")
                    .eq("telephone", phone)
                    .eq("cultures", culture)
                    .execute()
                )

                if existing.data:
                    supabase.table("producteurs").update({
                        "nom": json_data.get("nom"),
                        "quantite": produit.get("quantite"),
                        "territoire": json_data.get("localisation")
                    }).eq(
                        "id",
                        existing.data[0]["id"]
                    ).execute()
                    print("PRODUCTEUR UPDATED", flush=True)
                else:
                    supabase.table("producteurs").insert({
                        "telephone": phone,
                        "nom": json_data.get("nom"),
                        "cultures": produit.get("culture"),
                        "quantite": produit.get("quantite"),
                        "territoire": json_data.get("localisation")
                    }).execute()
                    print("PRODUCTEUR CREATED", flush=True)
                    
        # ACHETEUR 
        elif role == "acheteur": 
            print("ACHETEUR DETECTED", flush=True)
            print(json_data, flush=True)
            existing = (
                supabase
                .table("acheteurs")
                .select("*")
                .eq("telephone", phone)
                .eq("produit", json_data.get("produit"))
                .execute()
            )

            if existing.data:
                supabase.table("acheteurs").update({
                    "quantite": json_data.get("quantite"),
                    "region": json_data.get("localisation")
                }).eq(
                    "id",
                    existing.data[0]["id"]
                ).execute()
                print("ACHETEUR UPDATED", flush=True)
            else:
                supabase.table("acheteurs").insert({
                    "telephone": phone,
                    "nom": json_data.get("nom"),
                    "produit": json_data.get("produit"),
                    "quantite": json_data.get("quantite"),
                    "region": json_data.get("localisation")
                }).execute()
                print("ACHETEUR CREATED", flush=True)
                
        # TRANSPORTEUR 
        elif role == "transporteur": 
            supabase.table("transporteurs").insert({ 
                "telephone": phone, 
                "nom": json_data.get("nom"), 
                "vehicule": json_data.get("vehicule"), 
                "capacite": json_data.get("capacite"), 
                "region": json_data.get("localisation") 
            }).execute() 
            
        # DECHETS 
        elif role == "citoyen": 
            if json_data.get("type_dechet"): 
                supabase.table("dechets").insert({ 
                    "telephone": phone, 
                    "nom": json_data.get("nom"), 
                    "type_dechet": json_data.get("type_dechet"), 
                    "quantite": json_data.get("quantite"), 
                    "localisation": json_data.get("localisation") 
                }).execute() 
        print("PROFILE SAVED", flush=True) 
    except Exception as e: 
        print("PROFILE SAVE ERROR:", str(e), flush=True) 

def check_matching(phone, json_data):
    try:
        if not supabase:
            return

        role = json_data.get("role")

        # Quand un PRODUCTEUR arrive
        if role == "producteur":
            produits = json_data.get("produits", [])
            for produit in produits:
                culture = produit.get("culture")
                acheteurs = (
                    supabase
                    .table("acheteurs")
                    .select("*")
                    .eq("produit", culture)
                    .execute()
                )

                for acheteur in acheteurs.data:
                    supabase.table("alertes").insert({
                        "type_alerte": "matching_produit",
                        "produit": culture,
                        "producteur_tel": phone,
                        "acheteur_tel": acheteur["telephone"],
                        "message": f"Correspondance trouvée pour {culture}",
                        "statut": "nouvelle"
                    }).execute()

        # Quand un ACHETEUR arrive
        elif role == "acheteur":
            produit = json_data.get("produit")
            producteurs = (
                supabase
                .table("producteurs")
                .select("*")
                .eq("cultures", produit)
                .execute()
            )

            for producteur in producteurs.data:
                supabase.table("alertes").insert({
                    "type_alerte": "matching_produit",
                    "produit": produit,
                    "producteur_tel": producteur["telephone"],
                    "acheteur_tel": phone,
                    "message": f"Correspondance trouvée pour {produit}",
                    "statut": "nouvelle"
                }).execute()

        print("MATCHING DONE
