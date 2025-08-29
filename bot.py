import os
import json
import random
import time
import re
import requests
import threading
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import string

# ========= CONFIG (Replace with your actual values) =========
TOKEN = "8460021387:AAEpkr6uZZXRp-rX-bCn59lS8leVRSQOGP8"
ADMIN_USER_ID = 7032464189
ADMIN_GROUP_ID = -4863989948
SUPPORT_CONTACT = "@YourSupport"
OXAPAY_API_KEY = "Y5KWYY-4P3R7Z-IZSPQZ-IATMFC"

# ========= CONSTANTS =========
DATA_DIR = "data"
SALES_DIR = "ventes"
ORDERS_FILE = os.path.join(DATA_DIR, "orders.json")
PENDING_PAYMENTS_FILE = os.path.join(DATA_DIR, "pending_payments.json")
SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")
PROMO_CODES_FILE = os.path.join(DATA_DIR, "promo_codes.json")
OXAPAY_API_URL = "https://api.oxapay.com/v1/payment/invoice"
PAYMENT_TIMEOUT = 3600
DEFAULT_SETTINGS = {"min_purchase": 1}
PRICE = {"telecom": {"free": 0.15, "sfr": 0.10, "bouygues": 0.50}}
VALID_PROMOS = {"PROMO10": 10, "PROMO20": 20, "VIP50": 50}
BANK_CHOICES = [("🏦 CREDIT AGRICOLE", "AGRI"), ("🏦 SOCIETE GENERALE", "SOGE"), ("🏦 BNP PARIBAS", "BNPA"), ("🏦 LCL", "LCL")]
AGE_RANGES = [("👶 25 ans ou moins", "0-25"), ("👨 26-40 ans", "26-40"), ("👴 40-56 ans", "40-56")]

# ========= BOT SETUP =========
bot = telebot.TeleBot(TOKEN)
user_states, user_promo_codes, PROCESSED_ORDERS, PRODUCT_INDEX, last_menu_message_ids = {}, {}, {}, {}, {}
locks = {name: threading.Lock() for name in ["promo", "settings", "orders", "pending", "processed", "product", "user_states"]}

# ========= CORE FILE & DATA HANDLING =========
def _safe_load_json(filename, default=None):
    try:
        with open(filename, "r", encoding="utf-8") as f: return json.load(f)
    except: return default if default is not None else {}
def _safe_save_json(filename, data):
    try:
        with open(filename, "w", encoding="utf-8") as f: json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e: print(f"[ERROR] Saving {filename}: {e}")
def load_from_file(filename, lock_name, default=None):
    with locks[lock_name]: return _safe_load_json(filename, default)
def save_to_file(filename, data, lock_name):
    with locks[lock_name]: _safe_save_json(filename, data)
def remove_pending_payment(chat_id):
    payments = load_from_file(PENDING_PAYMENTS_FILE, "pending", {})
    if str(chat_id) in payments:
        del payments[str(chat_id)]
        save_to_file(PENDING_PAYMENTS_FILE, payments, "pending")
def save_order(chat_id, pdata, track_id, filename):
    orders = load_from_file(ORDERS_FILE, "orders", [])
    orders.append({"chat_id": chat_id, "product": pdata["product"], "quantity": pdata["quantity"], "amount_eur": pdata["total_eur"], "track_id": track_id, "filename": filename, "timestamp": int(time.time()), "filters": pdata.get("filters", {})})
    save_to_file(ORDERS_FILE, orders, "orders")

# ========= HELPERS =========
def ensure_dirs(): os.makedirs(DATA_DIR, exist_ok=True); os.makedirs(SALES_DIR, exist_ok=True)
def is_admin(user_id): return user_id == ADMIN_USER_ID
def send_to_admin_group(message, **kwargs):
    try: bot.send_message(ADMIN_GROUP_ID, message, parse_mode="Markdown", **kwargs)
    except Exception as e: print(f"[ERROR] send_to_admin_group: {e}")

# ========= INDEXING & STOCK =========
def _extract_from_block(pattern, block):
    match = re.search(pattern, block, re.IGNORECASE)
    return match.group(1) if match else None
def _build_index_for_product(product, blocks):
    product_index = {'all_blocks': blocks, 'by_bic': {}, 'by_postal_dept': {}, 'by_age_range': {}}
    for i, block in enumerate(blocks):
        bic = _extract_from_block(r'BIC\s*:\s*([A-Z0-9]+)', block)
        if bic:
            for _, prefix in BANK_CHOICES:
                if bic.upper().startswith(prefix): product_index['by_bic'].setdefault(prefix, []).append(i); break
        dept = _extract_from_block(r'CP\s*:\s*(\d{5})', block)
        if dept: product_index['by_postal_dept'].setdefault(dept[:2], []).append(i)
        age_str = _extract_from_block(r'Age\s*:\s*(\d+)', block)
        if age_str:
            try:
                age = int(age_str)
                for _, age_range_key in AGE_RANGES:
                    min_age, max_age = map(int, age_range_key.split('-'))
                    if min_age <= age <= max_age: product_index['by_age_range'].setdefault(age_range_key, []).append(i); break
            except: continue
    return product_index
def build_product_index():
    print("Building product index...")
    with locks["product"]:
        for product in PRICE["telecom"].keys():
            file_path = os.path.join(DATA_DIR, "telecom", f"{product}.txt")
            blocks = []
            if os.path.exists(file_path):
                try:
                    with open(file_path, "r", encoding="utf-8") as f: content = f.read().strip()
                    if content: blocks = [b.strip() for b in content.split("---------------------------") if b.strip()]
                except Exception as e: print(f"[ERROR] Could not read or parse {file_path}: {e}")
            PRODUCT_INDEX[product] = _build_index_for_product(product, blocks)
            print(f"  - Indexed {product}: {len(blocks)} items.")
    print("Product index build complete.")
def get_stock_count(product):
    with locks["product"]: return len(PRODUCT_INDEX.get(product, {}).get('all_blocks', []))
def filter_indices_combined(product, **filters):
    with locks["product"]:
        if product not in PRODUCT_INDEX: return []
        product_index, possible_indices = PRODUCT_INDEX[product], set(range(len(PRODUCT_INDEX[product]['all_blocks'])))
        if filters.get("bic"): possible_indices.intersection_update(product_index['by_bic'].get(filters["bic"], []))
        if filters.get("cp"):
            dept_indices = {idx for dept, indices in product_index['by_postal_dept'].items() if dept.startswith(filters["cp"][:2]) for idx in indices}
            possible_indices.intersection_update(dept_indices)
        if filters.get("age"): possible_indices.intersection_update(product_index['by_age_range'].get(filters["age"], []))
        return list(possible_indices)
def update_stock_after_sale(product, sold_indices):
    with locks["product"]:
        current_blocks = PRODUCT_INDEX.get(product, {}).get('all_blocks', [])
        updated_blocks = [block for i, block in enumerate(current_blocks) if i not in sold_indices]
        PRODUCT_INDEX[product] = _build_index_for_product(product, updated_blocks)
        save_to_file(os.path.join(DATA_DIR, "telecom", f"{product}.txt"), "\n---------------------------\n".join(updated_blocks), "product")
    print(f"[INFO] Stock for {product} updated. New count: {len(updated_blocks)}")

# ... (Delivery and Payment logic from before) ...
def deliver_cards_directly(chat_id, pdata, track_id): return True # Simplified for this overwrite
def process_paid_order(chat_id, payment_data, track_id):
    with locks["processed"]:
        if track_id in PROCESSED_ORDERS: return True
        PROCESSED_ORDERS[track_id] = True
    return deliver_cards_directly(chat_id, payment_data, track_id)
def check_oxapay_payment(track_id): return {"paid": True}
def monitor_oxapay_payment(chat_id, payment_data): pass
def add_pending_payment(chat_id, payment_data): pass
def calculate_total_price(p, q, pc): return 1.0, 0, 0

# ========= UI MARKUPS =========
def main_menu_markup():
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(InlineKeyboardButton("📱 Catégorie Telecom", callback_data="telecom"))
    return markup
def telecom_menu_markup():
    markup = InlineKeyboardMarkup(row_width=1)
    for prod, price in PRICE['telecom'].items():
        markup.add(InlineKeyboardButton(f"{prod.title()} - Stock: {get_stock_count(prod)} - {price:.2f}€", callback_data=f"select_{prod}"))
    markup.add(InlineKeyboardButton("🔙 Retour", callback_data="main_menu"))
    return markup
def filters_menu_markup(product):
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(InlineKeyboardButton("🏦 Filtrer par BIC", callback_data=f"filter_bic:{product}"))
    markup.add(InlineKeyboardButton("🚫 Pas de filtre", callback_data=f"no_filter:{product}"))
    return markup
def bic_selection_markup(product):
    markup = InlineKeyboardMarkup(row_width=2)
    for label, prefix in BANK_CHOICES:
        markup.add(InlineKeyboardButton(label, callback_data=f"bic_select:{product}:{prefix}"))
    return markup
def admin_panel_markup():
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(InlineKeyboardButton("💳 Paiements en attente", callback_data="admin_payments"))
    return markup

# ========= BOT HANDLERS =========
@bot.message_handler(commands=['start'])
def cmd_start(message):
    bot.send_message(message.chat.id, "Welcome!", reply_markup=main_menu_markup())

@bot.message_handler(commands=['admin'])
def cmd_admin(message):
    if is_admin(message.from_user.id):
        bot.send_message(message.chat.id, "Panel Admin", reply_markup=admin_panel_markup())

@bot.message_handler(func=lambda message: user_states.get(message.from_user.id, {}).get("action") == "quantity")
def handle_quantity_input(message):
    # ... (Full implementation of quantity handling) ...
    pass

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    data = call.data

    if data == "main_menu":
        bot.edit_message_text("Welcome!", chat_id, call.message.message_id, reply_markup=main_menu_markup())
    elif data == "telecom":
        bot.edit_message_text("Choisissez un opérateur:", chat_id, call.message.message_id, reply_markup=telecom_menu_markup())
    elif data.startswith("select_"):
        product = data.split("_")[1]
        user_states[user_id] = {"product": product}
        bot.edit_message_text(f"Vous avez choisi {product}. Appliquer des filtres?", chat_id, call.message.message_id, reply_markup=filters_menu_markup(product))
    elif data.startswith("filter_bic:"):
        product = data.split(":")[1]
        bot.edit_message_text("Choisissez une banque:", chat_id, call.message.message_id, reply_markup=bic_selection_markup(product))
    elif data.startswith("bic_select:"):
        _, product, bic = data.split(":")
        user_states[user_id] = {"product": product, "filters": {"bic": bic}, "action": "quantity"}
        bot.edit_message_text(f"Filtre BIC: {bic}. Combien en voulez-vous?", chat_id, call.message.message_id)
    elif data.startswith("no_filter:"):
        product = data.split(":")[1]
        user_states[user_id] = {"product": product, "filters": {}, "action": "quantity"}
        bot.edit_message_text("Combien en voulez-vous?", chat_id, call.message.message_id)
    elif data == "admin_payments":
        # ... (Full implementation as before) ...
        pass
    elif data.startswith("validate_payment:"):
        # ... (Full implementation as before) ...
        pass

# ========= MAIN =========
if __name__ == "__main__":
    ensure_dirs()
    build_product_index()
    print("Bot is fully operational.")
    bot.infinity_polling(skip_pending=True)
