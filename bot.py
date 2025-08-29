import os, json, random, tempfile, time, re, requests, threading
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import string

# ========= CONFIG =========
TOKEN = "8460021387:AAEpkr6uZZXRp-rX-bCn59lS8leVRSQOGP8"
DATA_DIR = "data"
ORDERS_FILE = "orders.json"
SALES_DIR = "ventes"
PENDING_PAYMENTS_FILE = "pending_payments.json"
SETTINGS_FILE = "settings.json"

SUPPORT_CONTACT = "@"

ADMIN_GROUP_ID = -4863989948
ADMIN_USER_ID = 7433846654

OXAPAY_API_KEY = "Y5KWYY-4P3R7Z-IZSPQZ-IATMFC"
OXAPAY_API_URL = "https://api.oxapay.com/v1/payment/invoice"
PAYMENT_TIMEOUT = 3600

# Paramètres par défaut
DEFAULT_SETTINGS = {
    "min_purchase": 1
}

PRICE = {
    "telecom": {
        "free": 0.15,
        "sfr": 0.10,
        "bouygues": 0.50
    }
}

VALID_PROMOS = {"PROMO10": 10, "PROMO20": 20, "VIP50": 50}

BANK_CHOICES = [
    ("🏦 CREDIT AGRICOLE", "AGRI"),
    ("🏦 SOCIETE GENERALE", "SOGE"),
    ("🏦 BNP PARIBAS", "BNPA"),
    ("🏦 LCL", "LCL"),
    ("🏦 CREDIT MUTUEL", "CMCIC"),
    ("🏦 LA BANQUE POSTALE", "PSST"),
    ("🏦 CIC", "CIC"),
    ("🏦 CAISSE D'EPARGNE", "CEPA"),
    ("🏦 BANQUE POPULAIRE", "CCBP"),
]

AGE_RANGES = [
    ("👶 25 ans ou moins", "0-25"),
    ("👨 26-40 ans", "26-40"),
    ("👴 40-56 ans", "40-56"),
    ("👵 57-100 ans", "57-100")
]

bot = telebot.TeleBot(TOKEN)
user_states = {}

PROCESSED_ORDERS = {}

PROMO_CODES_FILE = "promo_codes.json"

def load_promo_codes():
    """Charger les codes promo depuis le fichier"""
    try:
        if os.path.exists(PROMO_CODES_FILE):
            with open(PROMO_CODES_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    except Exception as e:
        print(f"[ERROR] Erreur lors du chargement des codes promo: {e}")
        return {}

def save_promo_codes(promo_codes):
    """Sauvegarder les codes promo dans le fichier"""
    try:
        with open(PROMO_CODES_FILE, 'w', encoding='utf-8') as f:
            json.dump(promo_codes, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[ERROR] Erreur lors de la sauvegarde des codes promo: {e}")

def load_settings():
    """Charger les paramètres depuis le fichier"""
    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return DEFAULT_SETTINGS.copy()
    except Exception as e:
        print(f"[ERROR] Erreur lors du chargement des paramètres: {e}")
        return DEFAULT_SETTINGS.copy()

def save_settings(settings):
    """Sauvegarder les paramètres dans le fichier"""
    try:
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[ERROR] Erreur lors de la sauvegarde des paramètres: {e}")

def get_min_purchase():
    """Obtenir le minimum d'achat"""
    settings = load_settings()
    return settings.get("min_purchase", 1)

def set_min_purchase(min_qty):
    """Définir le minimum d'achat"""
    settings = load_settings()
    settings["min_purchase"] = min_qty
    save_settings(settings)

def generate_promo_code():
    """Générer un code promo unique"""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

def create_promo_code(discount_percent, max_uses=1):
    """Créer un nouveau code promo"""
    promo_codes = load_promo_codes()
    
    # Générer un code unique
    while True:
        code = generate_promo_code()
        if code not in promo_codes:
            break
    
    promo_codes[code] = {
        "discount": discount_percent,
        "max_uses": max_uses,
        "used_count": 0,
        "created_at": int(time.time()),
        "used_by": []
    }
    
    save_promo_codes(promo_codes)
    return code

def is_promo_code_valid(code, user_id):
    """Vérifier si un code promo est valide et utilisable"""
    promo_codes = load_promo_codes()
    
    if code not in promo_codes:
        return False, "Code promo invalide"
    
    promo = promo_codes[code]
    
    if promo["used_count"] >= promo["max_uses"]:
        return False, "Code promo déjà utilisé"
    
    if user_id in promo["used_by"]:
        return False, "Vous avez déjà utilisé ce code"
    
    return True, promo["discount"]

def use_promo_code(code, user_id):
    """Marquer un code promo comme utilisé"""
    promo_codes = load_promo_codes()
    
    if code in promo_codes:
        promo_codes[code]["used_count"] += 1
        promo_codes[code]["used_by"].append(user_id)
        save_promo_codes(promo_codes)
        return True
    return False

# ========= UTILITY FUNCTIONS =========

def _safe_load_json(filename, default=None):
    """Charger un fichier JSON de manière sécurisée"""
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return default if default is not None else {}

def ensure_dirs():
    """Créer les dossiers nécessaires"""
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(f"{DATA_DIR}/telecom", exist_ok=True)
    os.makedirs(SALES_DIR, exist_ok=True)

def is_admin(user_id):
    """Vérifier si l'utilisateur est admin"""
    return user_id == ADMIN_USER_ID

def send_to_admin_group(message, markup=None):
    """Envoyer un message au groupe admin"""
    try:
        message_with_support = f"{message}\n\n📞 Support: {SUPPORT_CONTACT}"
        bot.send_message(ADMIN_GROUP_ID, message_with_support, parse_mode="Markdown", reply_markup=markup)
    except Exception as e:
        print(f"[ERROR] Impossible d'envoyer au groupe admin: {e}")

def count_files_in_txt(filename):
    """Compter le nombre de blocs dans un fichier txt"""
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            if not content:
                return 0
            blocks = content.split('---------------------------')
            return len([block for block in blocks if block.strip()])
    except:
        return 0

def get_stock_count(product):
    """Obtenir le stock pour un produit"""
    if product in ["free", "sfr", "bouygues"]:
        return count_files_in_txt(f"{DATA_DIR}/telecom/{product}.txt")
    return 0

def calculate_total_price(product, quantity, promo_code=None):
    """Calculer le prix total"""
    if product not in PRICE["telecom"]:
        return 0, 0, 0
    
    base_price = PRICE["telecom"][product]
    subtotal = base_price * quantity
    
    # Remise promo
    promo_discount = 0
    promo_discount_amount = 0
    
    if promo_code:
        # Vérifier d'abord les codes hardcodés
        if promo_code in VALID_PROMOS:
            promo_discount = VALID_PROMOS[promo_code]
            promo_discount_amount = subtotal * (promo_discount / 100)
        else:
            # Vérifier les codes générés dynamiquement
            promo_codes = load_promo_codes()
            if promo_code in promo_codes:
                promo_info = promo_codes[promo_code]
                if promo_info["used_count"] < promo_info["max_uses"]:
                    promo_discount = promo_info["discount"]
                    promo_discount_amount = subtotal * (promo_discount / 100)
    
    total = subtotal - promo_discount_amount
    return total, 0, promo_discount

def filter_indices_combined(cat, prod, bic_prefix=None, cp_prefix=None, age_filter=None):
    """Filtre combiné BIC + Code postal + Âge"""
    print(f"[DEBUG] Filtrage: BIC={bic_prefix}, CP={cp_prefix}, AGE={age_filter}")
    
    main_file = os.path.join(DATA_DIR, cat, f"{prod}.txt")
    if not os.path.exists(main_file):
        print(f"[ERROR] Fichier non trouvé: {main_file}")
        return []

    with open(main_file, "r", encoding="utf-8") as f:
        blocs = [b.strip() for b in f.read().split("---------------------------") if b.strip()]

    selected = []
    current_year = 2024
    
    for i, block in enumerate(blocs):
        match = True
        
        print(f"[DEBUG] Bloc {i}: {block[:100]}...")
        
        # Filtre BIC
        if bic_prefix and match:
            bic_patterns = [
                rf"(?im)^\s*BIC\s*:?\s*([A-Z0-9]+)",
                rf"(?im)\bBIC\b\s*:?\s*([A-Z0-9]+)",
                rf"(?im)Code\s*BIC\s*:?\s*([A-Z0-9]+)",
                rf"(?im)SWIFT\s*:?\s*([A-Z0-9]+)",
                rf"(?im)BIC\s*[:\-]?\s*([A-Z0-9]+)",
                rf"(?im)IBAN\s*:.*?([A-Z]{{4}}[A-Z0-9]+)"  # Extraction BIC depuis IBAN
            ]
            bic_found = False
            for pattern in bic_patterns:
                matches = re.finditer(pattern, block)
                for m in matches:
                    bic_value = m.group(1).upper().strip()
                    print(f"[DEBUG] BIC trouvé: {bic_value}, recherché: {bic_prefix}")
                    if bic_value.startswith(bic_prefix.upper()):
                        bic_found = True
                        print(f"[DEBUG] BIC match trouvé!")
                        break
                if bic_found:
                    break
            if not bic_found:
                print(f"[DEBUG] Aucun BIC correspondant trouvé pour {bic_prefix}")
                match = False
        
        # Filtre Code postal
        if cp_prefix and match:
            cp_patterns = [
                rf"(?im)^\s*Code\s*postale?\s*:?\s*(\d+)",
                rf"(?im)\bCode\s*postale?\s*:?\s*(\d+)",
                rf"(?im)\bCP\s*:?\s*(\d+)",
                rf"(?im)Postal\s*Code\s*:?\s*(\d+)",
                rf"(?im)Code\s*postale?\s*[:\-]\s*(\d+)",
                rf"(?im)CP\s*[:\-]\s*(\d+)",
                rf"(?im)Ville\s*:.*?(\d{{5}})",  # Code postal après ville
                rf"(?im)Adresse.*?(\d{{5}})",    # Code postal dans adresse
                rf"(?im)(\d{{5}})\s+[A-Za-z]",   # 5 chiffres suivis d'une lettre (ville)
                rf"(?im)\b(\d{{5}})\b"           # 5 chiffres isolés (en dernier)
            ]
            cp_found = False
            for pattern in cp_patterns:
                matches = re.finditer(pattern, block)
                for m in matches:
                    cp_value = m.group(1).strip()
                    print(f"[DEBUG] Code postal trouvé avec pattern '{pattern}': {cp_value}, recherché: {cp_prefix}")
                    if cp_value.startswith(cp_prefix):
                        cp_found = True
                        print(f"[DEBUG] Code postal match trouvé!")
                        break
                if cp_found:
                    break
            if not cp_found:
                print(f"[DEBUG] Aucun code postal correspondant trouvé pour {cp_prefix}")
                print(f"[DEBUG] Contenu du bloc pour debug: {block}")
                match = False
        
        # Filtre Âge
        if age_filter and match:
            age_patterns = [
                rf"(?im)(\d{{1,2}})[\/\-\.](\d{{1,2}})[\/\-\.](\d{{4}})",
                rf"(?im)Age\s*:?\s*(\d+)",
                rf"(?im)Born\s*:?\s*(\d{{4}})"
            ]
            age_found = False
            for pattern in age_patterns:
                birth_match = re.search(pattern, block)
                if birth_match:
                    if "Age" in pattern:
                        age = int(birth_match.group(1))
                    elif len(birth_match.groups()) >= 3:
                        birth_year = int(birth_match.group(3))
                        age = current_year - birth_year
                    else:
                        birth_year = int(birth_match.group(1))
                        age = current_year - birth_year
                    
                    if "-" in age_filter:
                        try:
                            min_age, max_age = map(int, age_filter.split("-"))
                            if min_age <= age <= max_age:
                                age_found = True
                                break
                        except ValueError:
                            continue
                    elif age_filter.endswith("+"):
                        try:
                            min_age = int(age_filter[:-1])
                            if age >= min_age:
                                age_found = True
                                break
                        except ValueError:
                            continue
                    else:
                        try:
                            target_age = int(age_filter)
                            if age == target_age:
                                age_found = True
                                break
                        except ValueError:
                            continue
            
            if not age_found:
                match = False
        
        if match:
            selected.append(i)
    
    print(f"[DEBUG] Résultat: {len(selected)} blocs sélectionnés sur {len(blocs)}")
    return selected

# ========= OXAPAY FUNCTIONS =========

def create_oxapay_invoice(amount_eur, order_id, user_email=None):
    """Créer une facture Oxapay"""
    try:
        headers = {
            'merchant_api_key': OXAPAY_API_KEY,
            'Content-Type': 'application/json'
        }
        
        data = {
            "amount": amount_eur,
            "currency": "EUR",
            "lifetime": 60,
            "fee_paid_by_payer": 1,
            "under_paid_coverage": 2.5,
            "auto_withdrawal": False,
            "mixed_payment": True,
            "order_id": order_id,
            "thanks_message": "Merci pour votre achat ! Vos fiches seront livrées automatiquement.",
            "description": f"Achat de fiches - Commande #{order_id}",
            "sandbox": False
        }
        
        if user_email:
            data["email"] = user_email
        
        response = requests.post(OXAPAY_API_URL, json=data, headers=headers, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            if result.get("status") == 200:
                return {
                    "success": True,
                    "track_id": result["data"]["track_id"],
                    "payment_url": result["data"]["payment_url"],
                    "expired_at": result["data"]["expired_at"]
                }
        
        print(f"[ERROR] Oxapay response: {response.text}")
        return {"success": False, "error": "Erreur lors de la création de la facture"}
        
    except Exception as e:
        print(f"[ERROR] Oxapay: {e}")
        return {"success": False, "error": str(e)}

def check_oxapay_payment(track_id):
    """Vérifier le statut d'un paiement Oxapay"""
    try:
        headers = {
            'merchant_api_key': OXAPAY_API_KEY,
            'Content-Type': 'application/json'
        }
        
        url = f"https://api.oxapay.com/v1/payment/{track_id}"
        
        response = requests.get(url, headers=headers, timeout=10)
        
        print(f"[DEBUG] Oxapay payment info response: {response.status_code} - {response.text}")
        
        if response.status_code == 200:
            result = response.json()
            data = result.get("data", {})
            payment_status = data.get("status")
            
            print(f"[DEBUG] Payment status: {payment_status}")
            print(f"[DEBUG] Is paid: {payment_status == 'paid'}")
            
            return {
                "success": True,
                "status": payment_status,
                "paid": payment_status == "paid",
                "amount": data.get("amount", 0),
                "currency": data.get("currency", ""),
                "tx_hash": data.get("tx_hash", "")
            }
        else:
            print(f"[ERROR] HTTP Error: {response.status_code} - {response.text}")
            return {"success": False, "error": f"HTTP {response.status_code}"}
        
    except Exception as e:
        print(f"[ERROR] Vérification Oxapay: {e}")
        return {"success": False, "error": str(e)}

def delete_message_safe(chat_id, message_id):
    """Supprime un message en toute sécurité"""
    try:
        bot.delete_message(chat_id, message_id)
    except:
        pass

def monitor_oxapay_payment(chat_id, payment_data, timeout_timestamp):
    """Surveille un paiement Oxapay en arrière-plan"""
    def check_payment():
        last_reminder_time = time.time()
        track_id = payment_data.get("track_id")
        
        if not track_id:
            print("[ERROR] track_id manquant pour la surveillance")
            return
        
        while time.time() < timeout_timestamp:
            try:
                result = check_oxapay_payment(track_id)
                print(f"[DEBUG] Surveillance - Track: {track_id}, Result: {result}")
                
                if result.get("success"):
                    if result.get("paid"):
                        print(f"[DEBUG] Paiement détecté comme payé pour {track_id}")
                        if track_id not in PROCESSED_ORDERS:
                            print(f"[DEBUG] Nouvelle commande payée détectée: {track_id}")
                            PROCESSED_ORDERS[track_id] = True
                            confirmation_msg = bot.send_message(chat_id, "🎉 **Paiement confirmé automatiquement!**\n\nVos fiches sont en cours de préparation...")
                            deliver_cards_directly(chat_id, payment_data, track_id, confirmation_msg.message_id)
                        else:
                            print(f"[DEBUG] Commande {track_id} déjà traitée, ignorée")
                        return
                    
                    # Rappel toutes les 10 minutes
                    current_time = time.time()
                    if current_time - last_reminder_time >= 600:
                        remaining_time = int((timeout_timestamp - current_time) / 60)
                        if remaining_time > 0:
                            markup = InlineKeyboardMarkup()
                            markup.add(InlineKeyboardButton("🔄 Vérifier maintenant", callback_data=f"check_payment:{track_id}"))
                            
                            bot.send_message(
                                chat_id, 
                                f"⏰ **Rappel de paiement**\n\nTemps restant: {remaining_time} minutes\n\nID de suivi: `{track_id}`",
                                reply_markup=markup,
                                parse_mode="Markdown"
                            )
                            last_reminder_time = current_time
                
                time.sleep(30)
                
            except Exception as e:
                print(f"[ERROR] Surveillance paiement: {e}")
                time.sleep(60)
        
        # Timeout atteint
        try:
            bot.send_message(chat_id, f"⏰ **Délai de paiement expiré**\n\nID de suivi: `{track_id}`\n\nVeuillez créer une nouvelle commande si nécessaire.", parse_mode="Markdown")
            remove_pending_payment(chat_id)
        except Exception as e:
            print(f"[ERROR] Erreur timeout: {e}")
    
    threading.Thread(target=check_payment, daemon=True).start()

def deliver_cards_directly(chat_id, payment_data, track_id, confirmation_msg_id=None):
    """Livrer les fiches directement après confirmation du paiement"""
    try:
        print(f"[DEBUG] deliver_cards_directly appelée - Chat: {chat_id}, Track: {track_id}")
        
        product = payment_data["product"]
        quantity = payment_data["quantity"]
        filters = payment_data.get("filters", {})
        
        print(f"[INFO] Livraison directe - Chat: {chat_id}, Produit: {product}, Quantité: {quantity}")
        print(f"[DEBUG] Filtres reçus: {filters}")
        
        # Apply promo code if user has one
        promo_code = None
        if 'user_promo_codes' in globals() and chat_id in user_promo_codes:
            promo_code = user_promo_codes[chat_id]
        
        # Calculate price with promo
        total_price, _, promo_discount = calculate_total_price(product, quantity, promo_code)
        
        # Récupérer les fiches
        if filters:
            bic_filter = filters.get("bic")
            cp_filter = filters.get("cp") or filters.get("postal")  # Support des deux noms
            age_filter = filters.get("age")
            
            print(f"[DEBUG] Filtres normalisés - BIC: {bic_filter}, CP: {cp_filter}, AGE: {age_filter}")
            
            indices = filter_indices_combined("telecom", product, bic_filter, cp_filter, age_filter)
            
            if len(indices) < quantity:
                bot.send_message(chat_id, f"❌ Pas assez de fiches correspondant aux filtres ({len(indices)} disponibles)")
                return False
            selected_indices = random.sample(indices, quantity)
        else:
            stock = get_stock_count(product)
            if stock < quantity:
                bot.send_message(chat_id, f"❌ Stock insuffisant ({stock} disponibles)")
                return False
            selected_indices = random.sample(range(stock), quantity)
        
        print(f"[DEBUG] Indices sélectionnés: {selected_indices}")
        
        # Lire et extraire les fiches
        main_file = os.path.join(DATA_DIR, "telecom", f"{product}.txt")
        if not os.path.exists(main_file):
            bot.send_message(chat_id, f"❌ Fichier {product}.txt introuvable")
            return False
            
        with open(main_file, "r", encoding="utf-8") as f:
            blocs = [b.strip() for b in f.read().split("---------------------------") if b.strip()]
        
        if not blocs:
            bot.send_message(chat_id, f"❌ Aucune donnée dans {product}.txt")
            return False
            
        selected_data = [blocs[i] for i in selected_indices if i < len(blocs)]
        
        if filters and selected_data:
            print(f"[DEBUG] Vérification des données sélectionnées:")
            for i, data in enumerate(selected_data):
                print(f"[DEBUG] Fiche {i+1}: {data[:200]}...")
        
        if len(selected_data) != quantity:
            bot.send_message(chat_id, f"❌ Erreur lors de la sélection des fiches")
            return False
        
        print(f"[DEBUG] Données sélectionnées: {len(selected_data)} fiches")
        
        timestamp = int(time.time())
        
        # Fichier 1: Fiches complètes
        filename_complete = f"{product}_{quantity}fiches_completes_{timestamp}.txt"
        filepath_complete = os.path.join(SALES_DIR, filename_complete)
        
        # Fichier 2: Numéros uniquement
        filename_phones = f"{product}_{quantity}numeros_{timestamp}.txt"
        filepath_phones = os.path.join(SALES_DIR, filename_phones)
        
        os.makedirs(SALES_DIR, exist_ok=True)
        
        # Créer le fichier des fiches complètes
        with open(filepath_complete, "w", encoding="utf-8") as f:
            f.write(f"=== FICHES COMPLÈTES ===\n")
            f.write(f"Produit: {product.upper()}\n")
            f.write(f"Quantité: {quantity} fiches\n")
            f.write(f"Track ID: {track_id}\n")
            f.write(f"Date: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"{'='*50}\n\n")
            
            for i, data in enumerate(selected_data, 1):
                f.write(f"=== FICHE {i} ===\n")
                f.write(data)
                f.write(f"\n{'='*30}\n\n")
        
        print(f"[DEBUG] Fichier complet créé: {filepath_complete}")
        
        # Extraire les numéros de téléphone
        phone_numbers = []
        for data in selected_data:
            lines = data.split('\n')
            phone_found = False
            for line in lines:
                if phone_found:
                    break
                # Chercher les numéros de téléphone avec regex plus robuste
                # Patterns pour différents formats de numéros français
                patterns = [
                    r'(\+33\s?\d\s?\d{2}\s?\d{2}\s?\d{2}\s?\d{2})',  # +33 X XX XX XX XX
                    r'(0\d\s?\d{2}\s?\d{2}\s?\d{2}\s?\d{2})',        # 0X XX XX XX XX
                    r'(\d{10})',                                      # XXXXXXXXXX
                    r'(\d{2}\s?\d{2}\s?\d{2}\s?\d{2}\s?\d{2})'       # XX XX XX XX XX
                ]
                
                for pattern in patterns:
                    phone_match = re.search(pattern, line)
                    if phone_match:
                        phone_numbers.append(phone_match.group(1))
                        phone_found = True
                        break
        
        # Si aucun numéro trouvé, utiliser un placeholder
        if not phone_numbers:
            phone_numbers = [f"Numéro_{i+1}_non_détecté" for i in range(quantity)]
        
        with open(filepath_phones, "w", encoding="utf-8") as f:
            f.write(f"=== NUMÉROS DE TÉLÉPHONE ===\n")
            f.write(f"Produit: {product.upper()}\n")
            f.write(f"Quantité: {len(phone_numbers)} numéros\n")
            f.write(f"Track ID: {track_id}\n")
            f.write(f"Date: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"{'='*50}\n\n")
            
            # Un numéro par ligne sans numérotation
            for phone in phone_numbers:
                f.write(f"{phone}\n")
        
        print(f"[DEBUG] Fichier numéros créé: {filepath_phones}")
        
        if confirmation_msg_id:
            delete_message_safe(chat_id, confirmation_msg_id)
        
        delivery_msg = bot.send_message(chat_id, f"🎉 **LIVRAISON CONFIRMÉE**\n\n📦 {quantity} fiches {product.upper()}\n🔗 Track ID: `{track_id}`\n\n📁 Vous recevez 2 fichiers:", parse_mode="Markdown")
        
        print(f"[DEBUG] Message de livraison envoyé")
        
        # Envoyer le fichier complet
        with open(filepath_complete, "rb") as f:
            complete_msg = bot.send_document(
                chat_id, 
                f, 
                caption="📋 **Fiches complètes** - Toutes les informations clients"
            )
        
        print(f"[DEBUG] Fichier complet envoyé")
        
        # Envoyer le fichier des numéros
        with open(filepath_phones, "rb") as f:
            phones_msg = bot.send_document(
                chat_id, 
                f, 
                caption="📞 **Numéros uniquement** - Liste des téléphones"
            )
        
        print(f"[DEBUG] Fichier numéros envoyé")
        
        # Sauvegarder la commande
        save_order(chat_id, payment_data, track_id, filename_complete)
        
        success_msg = bot.send_message(chat_id, "✅ **Commande livrée avec succès !**\n\nMerci pour votre achat ! 🎉", parse_mode="Markdown")
        
        def cleanup_messages():
            time.sleep(300)  # 5 minutes
            delete_message_safe(chat_id, delivery_msg.message_id)
            delete_message_safe(chat_id, success_msg.message_id)
        
        threading.Thread(target=cleanup_messages, daemon=True).start()
        
        # Clear used promo code after successful delivery
        if promo_code and 'user_promo_codes' in globals() and chat_id in user_promo_codes:
            use_promo_code(promo_code, chat_id)
            del user_promo_codes[chat_id]
        
        # Supprimer le paiement en attente
        remove_pending_payment(chat_id)
        
        print(f"[SUCCESS] Commande livrée - Chat: {chat_id}, Fichiers: {filename_complete}, {filename_phones}")
        return True
            
    except Exception as e:
        print(f"[ERROR] Erreur livraison directe: {e}")
        error_msg = str(e)
        if "'dict' object has no attribute 'append'" not in error_msg:
            bot.send_message(chat_id, f"❌ Erreur lors de la livraison: {error_msg}")
        return False

def process_paid_order(chat_id, payment_data, track_id, confirmation_msg_id=None):
    """Traiter une commande payée - utilisé pour validation manuelle"""
    try:
        print(f"[DEBUG] process_paid_order appelée - Chat: {chat_id}, Track: {track_id}")
        
        if track_id in PROCESSED_ORDERS:
            print(f"[INFO] Commande {track_id} déjà traitée, ignorée")
            bot.send_message(chat_id, "✅ Cette commande a déjà été traitée et livrée.")
            return True
        
        PROCESSED_ORDERS[track_id] = True
        return deliver_cards_directly(chat_id, payment_data, track_id, confirmation_msg_id)
        
    except Exception as e:
        print(f"[ERROR] process_paid_order: {e}")
        bot.send_message(chat_id, "❌ Erreur lors du traitement. Contactez le support.")
        return False

def save_order(chat_id, payment_data, track_id, filename):
    """Sauvegarder une commande dans l'historique"""
    orders = _safe_load_json(ORDERS_FILE, [])
    
    order = {
        "chat_id": chat_id,
        "product": payment_data["product"],
        "quantity": payment_data["quantity"],
        "amount_eur": payment_data["total_eur"],
        "track_id": track_id,
        "filename": filename,
        "timestamp": int(time.time()),
        "filters": payment_data.get("filters", {})
    }
    
    orders.append(order)
    
    with open(ORDERS_FILE, "w", encoding="utf-8") as f:
        json.dump(orders, f, ensure_ascii=False, indent=2)

# ========= PAYMENT SYSTEM =========

PENDING_PAYMENTS = {}

def load_pending_payments():
    """Charger les paiements en attente"""
    global PENDING_PAYMENTS
    PENDING_PAYMENTS = _safe_load_json(PENDING_PAYMENTS_FILE, {})
    return PENDING_PAYMENTS

def save_pending_payments(payments):
    """Sauvegarder les paiements en attente"""
    global PENDING_PAYMENTS
    PENDING_PAYMENTS = payments
    with open(PENDING_PAYMENTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(payments, f, ensure_ascii=False, indent=2)

def add_pending_payment(chat_id, payment_data):
    """Ajouter un paiement en attente"""
    global PENDING_PAYMENTS
    payments = load_pending_payments()
    payment_data["created_at"] = int(time.time())
    payment_data["expires_at"] = int(time.time()) + PAYMENT_TIMEOUT
    
    user_info = payment_data.get("user_data", {})
    order_id = f"ORDER_{chat_id}_{int(time.time())}"
    invoice_result = create_oxapay_invoice(payment_data["total_eur"], order_id, user_info.get("email"))
    
    if invoice_result.get("success"):
        payment_data["track_id"] = invoice_result["track_id"]
        payment_data["payment_url"] = invoice_result["payment_url"]
        payments[str(chat_id)] = payment_data
        save_pending_payments(payments)
        
        # Notification admin
        admin_msg = (
            f"💳 NOUVEAU PAIEMENT EN ATTENTE\n\n"
            f"👤 Client: {user_info.get('first_name', 'N/A')} (@{user_info.get('username', 'N/A')})\n"
            f"🆔 Chat ID: {chat_id}\n"
            f"💰 Montant: {payment_data['total_eur']:.2f}€\n"
            f"📱 Produit: {payment_data.get('product', 'N/A')}\n"
            f"📊 Quantité: {payment_data.get('quantity', 0)}\n"
            f"🔗 Track ID: `{invoice_result['track_id']}`\n"
            f"⏰ Expire dans 1 heure"
        )
        send_to_admin_group(admin_msg)
        
        # Démarrer le monitoring
        timeout_timestamp = time.time() + PAYMENT_TIMEOUT
        monitor_oxapay_payment(chat_id, payment_data, timeout_timestamp)
        
        return invoice_result["payment_url"]
    else:
        return None

def remove_pending_payment(chat_id):
    """Supprime un paiement en attente"""
    payments = load_pending_payments()
    payments.pop(str(chat_id), None)
    save_pending_payments(payments)

# ========= KEYBOARD MARKUPS =========

def main_menu_markup():
    """Menu principal"""
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("📱 Catégorie Telecom", callback_data="telecom"),
        InlineKeyboardButton("₿ Fiche Crypto", callback_data="crypto"),
        InlineKeyboardButton("📊 Historique", callback_data="historique"),
        InlineKeyboardButton("🎟️ Code Promo", callback_data="promo_menu")
    )
    return markup

def telecom_menu_markup():
    """Menu télécom avec stocks"""
    markup = InlineKeyboardMarkup(row_width=1)
    
    free_stock = get_stock_count("free")
    sfr_stock = get_stock_count("sfr")
    bouygues_stock = get_stock_count("bouygues")
    
    markup.add(
        InlineKeyboardButton(f"📱 Free - Stock: {free_stock} - Prix: {PRICE['telecom']['free']:.2f}€/fiche", callback_data="select_free"),
        InlineKeyboardButton(f"📶 SFR - Stock: {sfr_stock} - Prix: {PRICE['telecom']['sfr']:.2f}€/fiche", callback_data="select_sfr"),
        InlineKeyboardButton(f"📱 Bouygues - Stock: {bouygues_stock} - Prix: {PRICE['telecom']['bouygues']:.2f}€/fiche", callback_data="select_bouygues"),
        InlineKeyboardButton("🔙 Retour", callback_data="main_menu")
    )
    return markup

def filters_menu_markup(product):
    """Menu des filtres"""
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("🏦 Filtrer par BIC", callback_data=f"filter_bic:{product}"),
        InlineKeyboardButton("🏮 Filtrer par Code postal", callback_data=f"filter_postal:{product}"),
        InlineKeyboardButton("🎂 Filtrer par âge", callback_data=f"filter_age:{product}"),
        InlineKeyboardButton("🏦🎂 Filtrer BIC + âge", callback_data=f"filter_bic_age:{product}"),
        InlineKeyboardButton("🏮🎂 Filtrer Code postal + âge", callback_data=f"filter_postal_age:{product}"),
        InlineKeyboardButton("🏦🏮 Filtrer BIC + Code postal", callback_data=f"filter_bic_postal:{product}"),
        InlineKeyboardButton("🎯 Filtrer tout (BIC+CP+Âge)", callback_data=f"filter_all:{product}"),
        InlineKeyboardButton("🚫 Pas de filtre", callback_data=f"no_filter:{product}"),
        InlineKeyboardButton("🏠 Retour Menu", callback_data="main_menu")
    )
    return markup

def bic_selection_markup(product, filter_mode="single"):
    """Menu de sélection des banques BIC"""
    markup = InlineKeyboardMarkup(row_width=1)
    for label, prefix in BANK_CHOICES:
        markup.add(InlineKeyboardButton(label, callback_data=f"bic_select:{product}:{prefix}:{filter_mode}"))
    markup.add(
        InlineKeyboardButton("🔙 Retour filtres", callback_data=f"back_to_filters:{product}"),
        InlineKeyboardButton("🔙 Retour liste", callback_data="telecom")
    )
    return markup

def age_selection_markup(product, filter_mode="single"):
    """Menu de sélection des tranches d'âge"""
    markup = InlineKeyboardMarkup(row_width=2)
    for label, age_range in AGE_RANGES:
        markup.add(InlineKeyboardButton(label, callback_data=f"age_select:{product}:{age_range}:{filter_mode}"))
    markup.add(
        InlineKeyboardButton("📅 Année spécifique", callback_data=f"age_specific:{product}:{filter_mode}"),
        InlineKeyboardButton("🔙 Retour filtres", callback_data=f"back_to_filters:{product}"),
        InlineKeyboardButton("🔙 Retour liste", callback_data="telecom")
    )
    return markup

def promo_menu_markup():
    """Menu des codes promo"""
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("🎟️ Entrer un code promo", callback_data="enter_promo"),
        InlineKeyboardButton("📋 Mes codes actifs", callback_data="my_promos"),
        InlineKeyboardButton("🔙 Retour", callback_data="main_menu")
    )
    return markup

def admin_panel_markup():
    """Panel admin"""
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("💰 Prix Free", callback_data="admin_price_free"),
        InlineKeyboardButton("💰 Prix SFR", callback_data="admin_price_sfr"),
        InlineKeyboardButton("💰 Prix Bouygues", callback_data="admin_price_bouygues"),
        InlineKeyboardButton("📊 Voir Prix", callback_data="admin_view_prices"),
        InlineKeyboardButton("💳 Paiements", callback_data="admin_payments"),
        InlineKeyboardButton("🎫 Générer Code Promo", callback_data="admin_generate_promo"),
        InlineKeyboardButton("📋 Voir Codes Promo", callback_data="admin_view_promos"),
        InlineKeyboardButton("🔢 Minimum d'achat", callback_data="admin_min_purchase"),
        InlineKeyboardButton("🔙 Retour", callback_data="main_menu")
    )
    return markup

# ========= HELPER FUNCTIONS =========

def generate_welcome_text():
    """Générer le texte de bienvenue avec les prix actuels"""
    free_stock = get_stock_count("free")
    sfr_stock = get_stock_count("sfr")
    bouygues_stock = get_stock_count("bouygues")
    
    return f"""🏆 **LA RUÉE VERS L'OR** 🏆

💎 **Catégorie Telecom**

▫️ 📱 📡 **free** — Stock restant : {free_stock} — Prix : {PRICE['telecom']['free']:.2f}€/fiche
▫️ 📱 📶 **SFR** — Stock restant : {sfr_stock} — Prix : {PRICE['telecom']['sfr']:.2f}€/fiche  
▫️ 📱 📱 **bouygues** — Stock restant : {bouygues_stock} — Prix : {PRICE['telecom']['bouygues']:.2f}€/fiche

📞 Support: {SUPPORT_CONTACT}"""

def send_menu_with_image(chat_id, text, markup):
    """Envoyer un menu avec l'image"""
    try:
        # Essayer d'abord image.png, puis image.jpg
        image_paths = ["image.png", "image.jpg"]
        image_sent = False
        
        for image_path in image_paths:
            if os.path.exists(image_path):
                try:
                    with open(image_path, "rb") as photo:
                        bot.send_photo(chat_id, photo, caption=text, reply_markup=markup, parse_mode="Markdown")
                        image_sent = True
                        break
                except Exception as e:
                    print(f"[ERROR] Erreur envoi image {image_path}: {e}")
                    continue
        
        if not image_sent:
            bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")
            
    except Exception as e:
        print(f"[ERROR] Impossible d'envoyer le menu: {e}")
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")

def safe_edit_or_send(call, text, markup=None):
    """Éditer un message ou en envoyer un nouveau en cas d'erreur"""
    try:
        bot.edit_message_caption(
            caption=text,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=markup,
            parse_mode="Markdown"
        )
    except:
        try:
            bot.edit_message_text(
                text=text,
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                reply_markup=markup,
                parse_mode="Markdown"
            )
        except:
            # Si l'édition échoue, envoyer un nouveau message
            send_menu_with_image(call.message.chat.id, text, markup)

def save_prices():
    """Sauvegarder les prix dans un fichier"""
    with open("prices.json", "w", encoding="utf-8") as f:
        json.dump(PRICE, f, ensure_ascii=False, indent=2)

def load_prices():
    """Charger les prix depuis le fichier"""
    global PRICE
    try:
        with open("prices.json", "r", encoding="utf-8") as f:
            loaded_prices = json.load(f)
            PRICE.update(loaded_prices)
    except:
        pass

def auto_sort_files():
    """Tri automatique des fichiers au démarrage"""
    print("🔄 Tri automatique des fichiers en cours...")
    
    for product in ["free", "sfr", "bouygues"]:
        file_path = f"{DATA_DIR}/telecom/{product}.txt"
        if os.path.exists(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                
                if content:
                    blocks = [b.strip() for b in content.split("---------------------------") if b.strip()]
                    
                    def sort_key(block):
                        try:
                            # Extraction BIC
                            bic_patterns = [
                                r'(?im)BIC\s*:?\s*([A-Z0-9]+)',
                                r'(?im)Code\s*BIC\s*:?\s*([A-Z0-9]+)',
                                r'(?im)SWIFT\s*:?\s*([A-Z0-9]+)'
                            ]
                            bic = 'ZZZZ'
                            for pattern in bic_patterns:
                                match = re.search(pattern, block)
                                if match:
                                    bic = match.group(1).upper()
                                    break
                            
                            # Extraction Code postal
                            cp_patterns = [
                                r'(?im)Code\s*postale?\s*:?\s*(\d+)',
                                r'(?im)CP\s*:?\s*(\d+)'
                            ]
                            cp = '99999'
                            for pattern in cp_patterns:
                                match = re.search(pattern, block)
                                if match:
                                    cp = match.group(1).zfill(5)
                                    break
                            
                            age_patterns = [
                                r'(?im)(\d{1,2})[\/\-\.](\d{1,2})[\/\-\.](\d{4})',
                                r'(?im)Age\s*:?\s*(\d+)'
                            ]
                            age_sort = 9999  # Valeur par défaut pour tri (âge très élevé)
                            current_year = 2024
                            
                            for pattern in age_patterns:
                                match = re.search(pattern, block)
                                if match:
                                    if "Age" in pattern:
                                        # Si c'est déjà un âge, l'utiliser directement
                                        age_sort = int(match.group(1))
                                    elif len(match.groups()) >= 3:
                                        # Si c'est une date de naissance, calculer l'âge
                                        birth_year = int(match.group(3))
                                        age_sort = current_year - birth_year
                                    else:
                                        # Si c'est juste une année, calculer l'âge
                                        birth_year = int(match.group(1))
                                        age_sort = current_year - birth_year
                                    break
                            
                            # Convertir l'âge en string avec padding pour le tri
                            age_sort_str = str(age_sort).zfill(3)
                            
                            return (bic, cp, age_sort_str)
                        except:
                            return ('ZZZZ', '99999', '999')
                    
                    blocks.sort(key=sort_key)
                    
                    # Réécrire le fichier trié
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write("\n---------------------------\n".join(blocks))
                    
                    print(f"✅ {product}.txt trié ({len(blocks)} blocs)")
            except Exception as e:
                print(f"❌ Erreur tri {product}: {e}")
    
    print("✅ Tri automatique terminé")

def extract_phone_from_line(line):
    """Extract phone number from a line of text"""
    phone_numbers = []
    phone_found = False
    
    # Common French phone number patterns
    patterns = [
        r'0[1-9](?:[-.\s]?\d{2}){4}',                        # 0X XX XX XX XX
        r'(\+33|0033)[1-9](?:[-.\s]?\d{2}){4}',             # +33 X XX XX XX XX
        r'(\d{10})',                                         # XXXXXXXXXX
        r'(\d{2}\s?\d{2}\s?\d{2}\s?\d{2}\s?\d{2})'          # XX XX XX XX XX
    ]
    
    for pattern in patterns:
        phone_match = re.search(pattern, line)
        if phone_match:
            phone_numbers.append(phone_match.group(1))
            phone_found = True
            break
    
    return phone_numbers, phone_found

def get_filtered_stock_count(product, filters):
    """Obtenir le stock filtré pour un produit"""
    indices = filter_indices_combined("telecom", product, 
                                    filters.get("bic"), 
                                    filters.get("postal"), 
                                    filters.get("age"))
    return len(indices)

def validate_promo_code(code, user_id):
    """Valider et appliquer un code promo"""
    is_valid, result = is_promo_code_valid(code, user_id)
    
    if is_valid:
        return True, result  # result est le pourcentage de réduction
    else:
        return False, result  # result est le message d'erreur

def get_filtered_data_indices(product, filters):
    """Obtenir les indices des données filtrées"""
    bic_prefix = filters.get("bic")
    cp_prefix = filters.get("cp")
    age_filter = filters.get("age")
    
    return filter_indices_combined("telecom", product, bic_prefix, cp_prefix, age_filter)

# Initialize global variable
user_promo_codes = {}

# ========= BOT HANDLERS =========

@bot.message_handler(commands=["start"])
def cmd_start(message):
    """Commande /start"""
    user = message.from_user
    admin_msg = f"🆕 NOUVELLE INTERACTION\n👤 {user.first_name or 'N/A'} (@{user.username or 'N/A'})\n🆔 {message.chat.id}"
    send_to_admin_group(admin_msg)
    
    send_menu_with_image(message.chat.id, generate_welcome_text(), main_menu_markup())

@bot.message_handler(commands=['admin'])
def admin_command(message):
    """Commande admin"""
    user_id = message.from_user.id
    if user_id != ADMIN_USER_ID:
        bot.reply_to(message, "❌ Accès refusé")
        return
    
    bot.send_message(message.chat.id, "🔧 **Panel Administrateur**", reply_markup=admin_panel_markup(), parse_mode="Markdown")

@bot.message_handler(commands=["historique"])
def cmd_history(message):
    """Afficher l'historique des commandes"""
    orders = _safe_load_json(ORDERS_FILE, [])
    user_orders = [o for o in orders if o["chat_id"] == message.chat.id]
    
    if not user_orders:
        bot.send_message(message.chat.id, "📊 Aucune commande dans votre historique.")
        return
    
    text = "📊 **VOTRE HISTORIQUE**\n\n"
    for order in user_orders[-10:]:
        date = time.strftime('%d/%m/%Y %H:%M', time.localtime(order["timestamp"]))
        text += f"📦 {order['quantity']}x {order['product'].upper()}\n"
        text += f"💰 {order['amount_eur']:.2f}€\n"
        text += f"📅 {date}\n"
        text += f"🔗 `{order['track_id'][:16]}...`\n\n"
    
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

@bot.message_handler(func=lambda message: message.chat.type == 'private' and message.from_user.id in user_states)
def handle_user_input(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    if user_id not in user_states:
        return
    
    state = user_states[user_id]
    action = state.get("action")
    
    print(f"[DEBUG] handle_user_input - User: {user_id}, Action: {action}, Message: {message.text}")
    
    # Gestion des prix admin
    if action == "set_price":
        try:
            new_price = float(message.text)
            if new_price <= 0:
                bot.send_message(chat_id, "❌ Le prix doit être positif.")
                return
            
            product = state["product"]
            old_price = PRICE["telecom"][product]
            PRICE["telecom"][product] = new_price
            save_prices()
            
            bot.send_message(chat_id, f"✅ Prix {product.upper()} mis à jour: {old_price:.2f}€ → {new_price:.2f}€")
            
            admin_msg = f"💰 PRIX MODIFIÉ\n👤 {message.from_user.first_name}\n📱 {product.upper()}: {old_price:.2f}€ → {new_price:.2f}€"
            send_to_admin_group(admin_msg)
            
            del user_states[user_id]
            send_menu_with_image(chat_id, generate_welcome_text(), main_menu_markup())
            
        except ValueError:
            bot.send_message(chat_id, "❌ Veuillez entrer un nombre valide.")
    
    elif action == "quantity":
        try:
            quantity = int(message.text)
            if quantity <= 0:
                bot.send_message(chat_id, "❌ Quantité invalide. Entrez un nombre positif:")
                return
            
            # Vérifier le minimum d'achat
            min_purchase = get_min_purchase()
            if quantity < min_purchase:
                bot.send_message(chat_id, f"❌ Quantité insuffisante. Minimum requis: {min_purchase} fiches")
                return
            
            product = state["product"]
            filters = state.get("filters", {})
            
            # Vérifier le stock disponible
            available_stock = get_filtered_stock_count(product, filters)
            if quantity > available_stock:
                bot.send_message(chat_id, f"❌ Stock insuffisant. Stock disponible: {available_stock}")
                return
            
            # Calculer le prix final sans code promo
            total_eur, qty_discount, _ = calculate_total_price(product, quantity)
            
            # Créer les données de paiement
            payment_data = {
                "product": product,
                "quantity": quantity,
                "total_eur": total_eur,
                "qty_discount": qty_discount,
                "promo_discount": 0,
                "promo_code": None,
                "filters": filters,
                "user_data": {
                    "username": message.from_user.username,
                    "first_name": message.from_user.first_name
                }
            }
            
            # Ajouter le paiement en attente
            payment_url = add_pending_payment(chat_id, payment_data)
            
            if payment_url:
                payment_text = f"""🛒 **COMMANDE CRÉÉE**

📦 Produit: {product.upper()}
📢 Quantité: {quantity}
💵 **Total: {total_eur:.2f}€**

🔗 **Lien de paiement Oxapay:**
{payment_url}

⏰ Délai: 30 minutes
🆔 ID de suivi: `{payment_data['track_id']}`

💡 Le paiement sera vérifié automatiquement."""

                markup = InlineKeyboardMarkup()
                markup.add(
                    InlineKeyboardButton("🔄 Vérifier paiement", callback_data=f"check_payment:{payment_data['track_id']}"),
                    InlineKeyboardButton("🏠 Retour Menu", callback_data="main_menu")
                )
                
                bot.send_message(chat_id, payment_text, reply_markup=markup, parse_mode="Markdown")
                
                # Démarrer la surveillance automatique
                timeout_timestamp = time.time() + 1800  # 30 minutes
                monitor_oxapay_payment(chat_id, payment_data, timeout_timestamp)
            else:
                bot.send_message(chat_id, "❌ Erreur lors de la création du paiement. Réessayez.")
            
            # Nettoyer l'état
            if user_id in user_states:
                del user_states[user_id]
                
        except ValueError:
            bot.send_message(chat_id, "❌ Quantité invalide. Entrez un nombre:")

    # Gestion des filtres simples
    elif action in ["filter_postal", "filter_bic", "filter_age"]:
        filter_type = action.replace("filter_", "")
        product = state["product"]
        
        print(f"[DEBUG] Traitement du filtre {filter_type} pour le produit {product}")
        
        # Sauvegarder le filtre
        if "filters" not in state:
            state["filters"] = {}
        
        if filter_type == "postal":
            state["filters"]["cp"] = message.text.strip()
        elif filter_type == "bic":
            state["filters"]["bic"] = message.text.strip()
        elif filter_type == "age":
            state["filters"]["age"] = message.text.strip()
        
        # Vérifier s'il y a d'autres filtres à demander
        if state.get("multi_filter"):
            remaining_filters = state["multi_filter"]
            if filter_type in remaining_filters:
                remaining_filters.remove(filter_type)
            
            if remaining_filters:
                # Demander le prochain filtre
                next_filter = remaining_filters[0]
                state["action"] = f"filter_{next_filter}"
                user_states[user_id] = state
                
                if next_filter == "postal":
                    bot.send_message(chat_id, f"✅ Filtre {filter_type.upper()} appliqué: {message.text}\n\n🏮 **Filtrer par Code Postal**\n\nEntrez le début du code postal (ex: 75, 69, 13):")
                elif next_filter == "age":
                    bot.send_message(chat_id, f"✅ Filtre {filter_type.upper()} appliqué: {message.text}\n\n🎂 **Choisis ta tranche d'âge:**", reply_markup=age_selection_markup(product, "combined"))
                return
        
        # Tous les filtres sont appliqués, demander la quantité
        state["action"] = "quantity"
        user_states[user_id] = state
        
        # Vérifier le stock avec filtres
        available_indices = filter_indices_combined("telecom", product, 
                                                  state["filters"].get("bic"), 
                                                  state["filters"].get("cp"), 
                                                  state["filters"].get("age"))
        
        filters_text = ", ".join([f"{k.upper()}: {v}" for k, v in state["filters"].items()])
        bot.send_message(chat_id, f"✅ Filtres appliqués: {filters_text}\n📊 Stock disponible: {len(available_indices)}\n\nCombien de fiches voulez-vous acheter?")

    # Gestion spéciale pour le filtre postal+age
    elif action == "filter_postal_for_age":
        postal_prefix = message.text.strip()
        
        if not postal_prefix.isdigit():
            bot.send_message(chat_id, "❌ Veuillez entrer uniquement des chiffres pour le code postal.")
            return
        
        if len(postal_prefix) < 2:
            bot.send_message(chat_id, "❌ Veuillez entrer au moins 2 chiffres pour le code postal.")
            return
        
        print(f"[DEBUG] Code postal saisi pour postal+age: '{postal_prefix}' pour le produit: {state.get('product')}")
        
        if "filters" not in state:
            state["filters"] = {}
        state["filters"]["cp"] = postal_prefix
        
        # Passer à la sélection d'âge
        product = state["product"]
        text = f"✅ Code postal sélectionné: {postal_prefix}\n\n🎂 **Choisis ta tranche d'âge:**"
        bot.send_message(chat_id, text, reply_markup=age_selection_markup(product, "postal_age"))
        
        # Mettre à jour l'état pour attendre la sélection d'âge
        state["action"] = "waiting_age_selection"
        user_states[user_id] = state

    # Gestion de la définition du minimum d'achat admin
    elif action == "set_min_purchase":
        if not is_admin(user_id):
            bot.send_message(chat_id, "❌ Accès refusé")
            user_states.pop(user_id, None)
            return
        
        try:
            min_qty = int(message.text.strip())
            if min_qty <= 0:
                bot.send_message(chat_id, "❌ Le minimum doit être positif.")
                return
            
            old_min = get_min_purchase()
            set_min_purchase(min_qty)
            
            bot.send_message(chat_id, f"✅ Minimum d'achat mis à jour: {old_min} → {min_qty} fiches")
            
            admin_msg = f"🔢 MINIMUM MODIFIÉ\n👤 {message.from_user.first_name}\n📊 Minimum: {old_min} → {min_qty} fiches"
            send_to_admin_group(admin_msg)
            
        except ValueError:
            bot.send_message(chat_id, "❌ Veuillez entrer un nombre valide.")
        
        user_states.pop(user_id, None)
        return

    # Gestion de l'entrée de codes promo
    elif action == "enter_promo":
        promo_code = message.text.strip().upper()
        print(f"[DEBUG] Code promo entré: {promo_code}")
        
        is_valid, result = is_promo_code_valid(promo_code, user_id)
        print(f"[DEBUG] Validation code: valid={is_valid}, result={result}")
        
        if is_valid:
            user_promo_codes[user_id] = promo_code
            bot.send_message(chat_id, f"✅ Code promo **{promo_code}** appliqué!\n💰 Réduction: {result}%", parse_mode="Markdown")
        else:
            bot.send_message(chat_id, f"❌ {result}")
        
        user_states.pop(user_id, None)
        return

    # Gestion de la génération de codes promo admin
    elif action == "generate_promo":
        if not is_admin(user_id):
            bot.send_message(chat_id, "❌ Accès refusé")
            user_states.pop(user_id, None)
            return
        
        try:
            discount = int(message.text.strip())
            print(f"[DEBUG] Discount parsé: {discount}")
            
            if 1 <= discount <= 100:
                code = create_promo_code(discount, max_uses=1)
                print(f"[DEBUG] Code généré: {code}")
                
                bot.send_message(chat_id, f"✅ **Code promo généré!**\n\n🎫 Code: `{code}`\n💰 Réduction: {discount}%\n📊 Utilisations: 1 fois maximum", parse_mode="Markdown")
                
                # Notifier l'admin dans les logs
                admin_msg = f"🎫 NOUVEAU CODE PROMO GÉNÉRÉ\n👤 Admin: {message.from_user.first_name}\n🎟️ Code: `{code}`\n💰 Réduction: {discount}%"
                send_to_admin_group(admin_msg)
            else:
                bot.send_message(chat_id, "❌ La réduction doit être entre 1 et 100%")
        except ValueError as e:
            print(f"[ERROR] Erreur parsing discount: {e}")
            bot.send_message(chat_id, "❌ Veuillez entrer un nombre valide")
        except Exception as e:
            print(f"[ERROR] Erreur génération code promo: {e}")
            bot.send_message(chat_id, f"❌ Erreur lors de la génération: {str(e)}")
        
        # Nettoyer l'état utilisateur
        user_states.pop(user_id, None)

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    """Gestionnaire des callbacks - VERSION CORRIGÉE"""
    chat_id = call.message.chat.id
    user_id = call.from_user.id
    data = call.data
    
    print(f"[DEBUG] Callback reçu: {data} de l'utilisateur {user_id}")
    
    try:
        if data == "main_menu":
            safe_edit_or_send(call, generate_welcome_text(), main_menu_markup())
        
        elif data == "telecom":
            text = "📱 **CATÉGORIE TÉLÉCOM**\n\nChoisissez votre opérateur:"
            markup = telecom_menu_markup()
            markup.add(InlineKeyboardButton("🏠 Retour Menu", callback_data="main_menu"))
            safe_edit_or_send(call, text, markup)
        
        elif data == "crypto":
            try:
                text = "💰 **CATÉGORIE CRYPTO**\n\nFonctionnalité en développement..."
                safe_edit_or_send(call, text, main_menu_markup())
            except Exception as e:
                bot.send_message(chat_id, f"❌ Erreur crypto: {str(e)}")
        
        elif data.startswith("select_"):
            product = data.split("_")[1]  # Correction ici - utiliser split au lieu de split(":")
            stock = get_stock_count(product)
            
            if stock == 0:
                bot.answer_callback_query(call.id, "❌ Stock épuisé")
                return
            
            text = f"Tu as choisi *{product.upper()}*.\nSouhaites-tu appliquer un filtre ?\n\n📞 Support: {SUPPORT_CONTACT}"
            safe_edit_or_send(call, text, filters_menu_markup(product))
        
        elif data.startswith("filter_bic:"):
            product = data.split(":")[1]
            text = "🏦 **Choisis ta banque (BIC):**"
            safe_edit_or_send(call, text, bic_selection_markup(product, "single"))
        
        elif data.startswith("filter_postal:"):
            product = data.split(":")[1]
            user_states[user_id] = {"action": "filter_postal", "product": product}
            bot.send_message(chat_id, "🏮 **Filtrer par Code Postal**\n\nEntrez le début du code postal (ex: 75, 13, 69):")
        
        elif data.startswith("filter_age:"):
            product = data.split(":")[1]
            text = "🎂 **Choisis ta tranche d'âge:**"
            safe_edit_or_send(call, text, age_selection_markup(product, "single"))
        
        elif data.startswith("filter_bic_postal:"):
            product = data.split(":")[1]
            user_states[user_id] = {"action": "filter_bic_combined", "product": product, "multi_filter": ["bic", "postal"]}
            text = "🏦🏮 **Filtrer par BIC + Code Postal**\n\nÉtape 1/2: Choisis ta banque (BIC):"
            safe_edit_or_send(call, text, bic_selection_markup(product, "both"))
        
        elif data.startswith("filter_all:"):
            product = data.split(":")[1]
            user_states[user_id] = {"action": "filter_bic_combined", "product": product, "multi_filter": ["bic", "postal", "age"]}
            text = "🎯 **Filtrer par BIC + Code Postal + Âge**\n\nÉtape 1/3: Choisis ta banque (BIC):"
            safe_edit_or_send(call, text, bic_selection_markup(product, "all"))
        
        elif data.startswith("no_filter:"):
            product = data.split(":")[1]
            user_states[user_id] = {"action": "quantity", "product": product}
            bot.send_message(chat_id, f"📊 Combien de fiches {product.upper()} voulez-vous acheter?")
        
        elif data.startswith("bic_select:"):
            parts = data.split(":")
            if len(parts) >= 4:
                product = parts[1]
                bic_prefix = parts[2]
                filter_mode = parts[3]
                
                state = {
                    "product": product,
                    "filters": {"bic": bic_prefix},
                    "filter_mode": filter_mode
                }
                user_states[user_id] = state
                
                available_indices = get_filtered_data_indices(product, {"bic": bic_prefix})
                
                if filter_mode == "single":
                    state["action"] = "quantity"
                    user_states[user_id] = state
                    text = f"✅ Banque sélectionnée: {bic_prefix}\n📊 Stock disponible: {len(available_indices)}\n\nCombien de fiches voulez-vous acheter?"
                    bot.send_message(chat_id, text)
                
                elif filter_mode == "bic_age":
                    state["action"] = "filter_age_after_bic"
                    user_states[user_id] = state
                    text = f"✅ Banque sélectionnée: {bic_prefix}\n\n🎂 **Choisis ta tranche d'âge:**"
                    safe_edit_or_send(call, text, age_selection_markup(product, "bic_age"))
                
                elif filter_mode in ["both", "all"]:
                    # Filtres combinés
                    if filter_mode == "both":
                        state["action"] = "filter_postal"
                        state["multi_filter"] = ["postal"]
                        user_states[user_id] = state
                        text = f"✅ Banque sélectionnée: {bic_prefix}\n\n🏮 **Filtrer par Code Postal**\n\nEntrez le début du code postal (ex: 75, 69, 13):"
                        bot.send_message(chat_id, text)
                    else:  # all
                        state["action"] = "filter_postal"
                        state["multi_filter"] = ["postal", "age"]
                        user_states[user_id] = state
                        text = f"✅ Banque sélectionnée: {bic_prefix}\n\n🏮 **Filtrer par Code Postal**\n\nÉtape 2/3: Entrez le début du code postal (ex: 75, 69, 13):"
                        bot.send_message(chat_id, text)
        
        elif data.startswith("age_select:"):
            parts = data.split(":")
            product, age_range, filter_mode = parts[1], parts[2], parts[3]
            
            print(f"[DEBUG] age_select - Product: {product}, Age: {age_range}, Mode: {filter_mode}")
            
            if user_id not in user_states:
                user_states[user_id] = {"product": product}
            
            state = user_states[user_id]
            if "filters" not in state:
                state["filters"] = {}
            state["filters"]["age"] = age_range
            
            if filter_mode == "single":
                # Filtre âge seul
                state["action"] = "quantity"
                user_states[user_id] = state
                
                available_indices = filter_indices_combined("telecom", product, None, None, age_range)
                text = f"✅ Tranche d'âge sélectionnée: {age_range}\n📊 Stock disponible: {len(available_indices)}\n\nCombien de fiches voulez-vous acheter?"
                bot.send_message(chat_id, text)
            
            elif filter_mode == "bic_age":
                state["action"] = "quantity"
                user_states[user_id] = state
                
                available_indices = filter_indices_combined("telecom", product, 
                                                          state["filters"].get("bic"), 
                                                          None, 
                                                          age_range)
                
                text = f"✅ Filtres appliqués: BIC: {state['filters'].get('bic')}, Âge: {age_range}\n📊 Stock disponible: {len(available_indices)}\n\nCombien de fiches voulez-vous acheter?"
                bot.send_message(chat_id, text)
            
            elif filter_mode == "postal_age":
                print(f"[DEBUG] postal_age mode - Filters: {state['filters']}")
                state["action"] = "quantity"
                user_states[user_id] = state
                
                available_indices = filter_indices_combined("telecom", product, 
                                                          None,
                                                          state["filters"].get("cp"), 
                                                          age_range)
                
                text = f"✅ Filtres appliqués: Code postal: {state['filters'].get('cp')}, Âge: {age_range}\n📊 Stock disponible: {len(available_indices)}\n\nCombien de fiches voulez-vous acheter?"
                bot.send_message(chat_id, text)
            
            else:
                # Partie d'un filtre combiné - continuer vers quantité
                state["action"] = "quantity"
                user_states[user_id] = state
                
                available_indices = filter_indices_combined("telecom", product, 
                                                          state["filters"].get("bic"), 
                                                          state["filters"].get("cp"), 
                                                          state["filters"].get("age"))
                
                filters_text = ", ".join([f"{k.upper()}: {v}" for k, v in state["filters"].items()])
                text = f"✅ Filtres appliqués: {filters_text}\n📊 Stock disponible: {len(available_indices)}\n\nCombien de fiches voulez-vous acheter?"
                bot.send_message(chat_id, text)
        
        elif data.startswith("age_specific:"):
            parts = data.split(":")
            product, filter_mode = parts[1], parts[2]
            user_states[user_id] = {"action": "filter_age", "product": product}
            bot.send_message(chat_id, "🎂 **Filtrer par Âge Spécifique**\n\nEntrez l'âge souhaité (ex: 25, 18-30, 50+):")
        
        elif data.startswith("back_to_filters:"):
            product = data.split(":")[1]
            text = f"Tu as choisi *{product.upper()}*.\nSouhaites-tu appliquer un filtre ?\n\n📞 Support: {SUPPORT_CONTACT}"
            safe_edit_or_send(call, text, filters_menu_markup(product))
        
        elif data.startswith("check_payment:"):
            track_id = data.split(":")[1]
            
            # Trouver les données de paiement correspondantes
            payment_data = None
            payments = load_pending_payments()
            for chat_id_str, pdata in payments.items():
                if pdata.get('track_id') == track_id:
                    payment_data = pdata
                    break
            
            result = check_oxapay_payment(track_id)
            
            if result.get("success"):
                if result.get("paid"):
                    bot.answer_callback_query(call.id, "✅ Paiement confirmé!")
                    if track_id not in PROCESSED_ORDERS and payment_data:
                        PROCESSED_ORDERS[track_id] = True
                        confirmation_msg = bot.send_message(chat_id, "🎉 **Paiement confirmé manuellement!**\n\nVos fiches sont en cours de préparation...")
                        deliver_cards_directly(chat_id, payment_data, track_id, confirmation_msg.message_id)
                    elif track_id in PROCESSED_ORDERS:
                        bot.send_message(chat_id, "ℹ️ Cette commande a déjà été livrée.")
                else:
                    status = result.get("status", "En attente")
                    bot.answer_callback_query(call.id, f"⏳ Statut: {status}")
                    
                    # Envoyer un message détaillé
                    bot.send_message(
                        chat_id,
                        f"🔍 **Vérification du paiement**\n\n"
                        f"ID de suivi: `{track_id}`\n"
                        f"Statut: {status}\n\n"
                        f"⏰ Le paiement peut prendre quelques minutes à être confirmé.",
                        parse_mode="Markdown"
                    )
            else:
                bot.answer_callback_query(call.id, "❌ Erreur lors de la vérification")

        elif data == "historique":
            text = "📊 **HISTORIQUE**\n\nVos dernières commandes apparaîtront ici."
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("🏠 Retour Menu", callback_data="main_menu"))
            safe_edit_or_send(call, text, markup)

        elif data == "promo_menu":
            text = "🎟️ **CODES PROMO**\n\nGérez vos codes promo:"
            markup = promo_menu_markup()
            markup.add(InlineKeyboardButton("🏠 Retour Menu", callback_data="main_menu"))
            safe_edit_or_send(call, text, markup)
        
        elif data == "enter_promo":
            user_states[user_id] = {"action": "enter_promo"}
            text = "🎟️ **Entrer un code promo**\n\nVeuillez taper votre code promo:"
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("🔙 Retour", callback_data="promo_menu"))
            safe_edit_or_send(call, text, markup)
        
        elif data == "my_promos":
            promo_codes = load_promo_codes()
            if user_id == ADMIN_USER_ID:
                text = f"📋 **Codes promo secrets:**\n\n"
                for code, info in promo_codes.items():
                    text += f"🎟️ `{code}` - {info['discount']}% de réduction\n"
                text += f"\n⚠️ **Ces codes sont secrets - à donner uniquement en privé**"
                bot.send_message(chat_id, text, parse_mode="Markdown")
            else:
                # Show user's active promo code
                if 'user_promo_codes' in globals() and user_id in user_promo_codes:
                    active_code = user_promo_codes[user_id]
                    is_valid, discount = validate_promo_code(active_code, user_id)
                    if is_valid:
                        text = f"🎟️ **Votre code promo actif:**\n\n"
                        text += f"Code: `{active_code}`\n"
                        text += f"Réduction: {discount}%\n\n"
                        text += f"✅ Ce code sera automatiquement appliqué lors de votre prochain achat!"
                    else:
                        text = "❌ **Aucun code promo actif**\n\n"
                        text += "Vous n'avez pas de code promo activé actuellement."
                else:
                    text = "❌ **Aucun code promo actif**\n\n"
                    text += "Vous n'avez pas de code promo activé actuellement."
                
                markup = InlineKeyboardMarkup()
                markup.add(InlineKeyboardButton("🎟️ Entrer un code", callback_data="enter_promo"))
                markup.add(InlineKeyboardButton("🔙 Retour", callback_data="promo_menu"))
                bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=markup)

        # Admin callbacks
        elif data.startswith("admin_price_"):
            if not is_admin(user_id):
                bot.answer_callback_query(call.id, "❌ Accès refusé")
                return
            
            product = data.replace("admin_price_", "")
            user_states[user_id] = {"action": "set_price", "product": product}
            bot.send_message(chat_id, f"💰 **Modifier le prix {product.upper()}**\n\nPrix actuel: {PRICE['telecom'][product]:.2f}€\n\nEntrez le nouveau prix:")
        
        elif data == "admin_view_prices":
            if not is_admin(user_id):
                bot.answer_callback_query(call.id, "❌ Accès refusé")
                return
            
            text = "💰 **PRIX ACTUELS**\n\n"
            for product, price in PRICE["telecom"].items():
                stock = get_stock_count(product)
                text += f"📱 {product.upper()}: {price:.2f}€ (Stock: {stock})\n"
            
            bot.send_message(chat_id, text)
        
        elif data.startswith("validate_payment:"):
            if not is_admin(user_id):
                bot.answer_callback_query(call.id, "❌ Accès refusé")
                return
            
            payment_chat_id = data.split(":")[1]
            payments = load_pending_payments()
            
            if payment_chat_id in payments:
                payment_data = payments[payment_chat_id]
                track_id = payment_data.get("track_id", "manual_validation")
                process_paid_order(int(payment_chat_id), payment_data, track_id)
                bot.answer_callback_query(call.id, "✅ Paiement validé manuellement")
            else:
                bot.answer_callback_query(call.id, "❌ Paiement introuvable")
        
        elif data.startswith("reject_payment:"):
            if not is_admin(user_id):
                bot.answer_callback_query(call.id, "❌ Accès refusé")
                return
            
            payment_chat_id = data.split(":")[1]
            payments = load_pending_payments()
            
            if payment_chat_id in payments:
                # Supprimer le paiement
                remove_pending_payment(int(payment_chat_id))
                
                # Notifier l'admin
                bot.send_message(chat_id, f"❌ Paiement refusé pour {payment_chat_id}")
                
                # Notifier le client
                bot.send_message(int(payment_chat_id), "❌ **Paiement refusé par l'administrateur**\n\nContactez le support si vous pensez qu'il s'agit d'une erreur.")
            else:
                bot.send_message(chat_id, "❌ Paiement introuvable")
        
        elif data.startswith("check_oxapay:"):
            if not is_admin(user_id):
                bot.answer_callback_query(call.id, "❌ Accès refusé")
                return
            
            payment_chat_id = data.split(":")[1]
            payments = load_pending_payments()
            
            if payment_chat_id in payments:
                payment_data = payments[payment_chat_id]
                track_id = payment_data.get("track_id")
                
                if track_id:
                    result = check_oxapay_payment(track_id)
                    if result.get("success"):
                        status = result.get("status", "Unknown")
                        paid = result.get("paid", False)
                        
                        status_text = "✅ PAYÉ" if paid else f"⏳ {status}"
                        bot.send_message(chat_id, f"🔍 **Vérification Oxapay**\n\nChat ID: {payment_chat_id}\nTrack ID: `{track_id}`\nStatut: {status_text}")
                        
                        if paid:
                            process_paid_order(int(payment_chat_id), payment_data, track_id)
                    else:
                        bot.send_message(chat_id, f"❌ Erreur lors de la vérification: {result.get('error', 'Inconnue')}")
                else:
                    bot.send_message(chat_id, "❌ Track ID manquant")
            else:
                bot.send_message(chat_id, "❌ Paiement introuvable")

        elif data == "admin_payments":
            if not is_admin(user_id):
                bot.answer_callback_query(call.id, "❌ Accès refusé")
                return
            
            payments = load_pending_payments()
            if not payments:
                bot.send_message(chat_id, "💳 Aucun paiement en attente")
            else:
                for chat_id_str, payment in payments.items():
                    remaining = payment["expires_at"] - int(time.time())
                    if remaining > 0:
                        text = f"💳 **PAIEMENT EN ATTENTE**\n\n"
                        text += f"👤 Chat ID: {chat_id_str}\n"
                        text += f"💰 {payment['total_eur']:.2f}€\n"
                        text += f"📱 {payment['product'].upper()} x{payment['quantity']}\n"
                        text += f"⏰ Expire dans {remaining//60}min\n"
                        text += f"🔗 Track ID: `{payment.get('track_id', 'N/A')}`"
                        
                        markup = InlineKeyboardMarkup(row_width=2)
                        markup.add(
                            InlineKeyboardButton("✅ Valider", callback_data=f"validate_payment:{chat_id_str}"),
                            InlineKeyboardButton("❌ Refuser", callback_data=f"reject_payment:{chat_id_str}"),
                            InlineKeyboardButton("🔍 Vérifier Oxapay", callback_data=f"check_oxapay:{chat_id_str}")
                        )
                        
                        bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=markup)
        
        elif data.startswith("filter_bic_age:"):
            product = data.split(":")[1]
            user_states[user_id] = {"action": "filter_bic_age", "product": product, "multi_filter": ["bic", "age"]}
            text = "🏦🎂 **Filtrer par BIC + Âge**\n\nÉtape 1/2: Choisis ta banque (BIC):"
            safe_edit_or_send(call, text, bic_selection_markup(product, "bic_age"))
        
        elif data.startswith("filter_postal_age:"):
            product = data.split(":")[1]
            print(f"[DEBUG] filter_postal_age callback pour le produit: {product}")
            
            # Créer un état spécial pour ce filtre
            user_states[user_id] = {
                "action": "filter_postal_for_age", 
                "product": product,
                "filters": {}
            }
            
            text = "🏮🎂 **Filtrer par Code Postal + Âge**\n\nÉtape 1/2: Entrez le début du code postal (ex: 75, 69, 13):"
            bot.send_message(chat_id, text)

        elif data == "admin_generate_promo":
            if not is_admin(user_id):
                bot.answer_callback_query(call.id, "❌ Accès refusé")
                return
            
            print(f"[DEBUG] Setting generate_promo state for user {user_id}")
            user_states[user_id] = {"action": "generate_promo"}
            print(f"[DEBUG] Current user_states: {user_states}")
            
            bot.send_message(chat_id, "🎫 **Générer un Code Promo**\n\nEntrez le pourcentage de réduction (1-100):")
        
        elif data == "admin_view_promos":
            if not is_admin(user_id):
                bot.answer_callback_query(call.id, "❌ Accès refusé")
                return
            
            promo_codes = load_promo_codes()
            if not promo_codes:
                bot.send_message(chat_id, "🎫 Aucun code promo généré")
            else:
                text = "🎫 **CODES PROMO GÉNÉRÉS**\n\n"
                for code, info in promo_codes.items():
                    status = "✅ Disponible" if info["used_count"] < info["max_uses"] else "❌ Utilisé"
                    text += f"📋 `{code}` - {info['discount']}% - {status}\n"
                    text += f"   📊 {info['used_count']}/{info['max_uses']} utilisations\n\n"
                
                bot.send_message(chat_id, text, parse_mode="Markdown")
        
        elif data == "admin_min_purchase":
            if not is_admin(user_id):
                bot.answer_callback_query(call.id, "❌ Accès refusé")
                return
            
            current_min = get_min_purchase()
            user_states[user_id] = {"action": "set_min_purchase"}
            bot.send_message(chat_id, f"🔢 **Modifier le minimum d'achat**\n\nMinimum actuel: {current_min} fiches\n\nEntrez le nouveau minimum:")

        bot.answer_callback_query(call.id)
        
    except Exception as e:
        print(f"Erreur dans callback_handler: {e}")
        bot.answer_callback_query(call.id, "❌ Une erreur s'est produite")

# ========= MAIN =========

if __name__ == "__main__":
    ensure_dirs()
    load_prices()
    auto_sort_files()
    print("🤖 Bot démarré avec toutes les fonctionnalités...")
    print(f"Prix actuels: {PRICE['telecom']}")
    print(f"Codes promo: {VALID_PROMOS}")
    
    # Load pending payments at startup
    PENDING_PAYMENTS = load_pending_payments()
    
    # Load promo codes at startup
    load_promo_codes()
    
    bot.infinity_polling()
