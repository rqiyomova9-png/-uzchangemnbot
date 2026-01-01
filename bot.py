# -*- coding: utf-8 -*-
import os, json, time, logging
from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.dispatcher import FSMContext
from dotenv import load_dotenv

# --------------------
# Sozlamalar
# --------------------
os.environ["TZ"] = "Asia/Tashkent"
load_dotenv()

API_TOKEN = os.getenv("API_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

DATA_DIR = "bot_data"
CURRENCIES_FILE = os.path.join(DATA_DIR, "currencies.json")
USERS_FILE = os.path.join(DATA_DIR, "users.json")
ORDERS_FILE = os.path.join(DATA_DIR, "orders.json")
os.makedirs(DATA_DIR, exist_ok=True)

# --------------------
# Logging & bot init
# --------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
storage = MemoryStorage()
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot, storage=storage)

# --------------------
# JSON helpers
# --------------------
def load_json(path, default):
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(default, f, ensure_ascii=False, indent=2)
        return default
    with open(path, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except:
            return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# --------------------
# Data stores
# --------------------
currencies = load_json(CURRENCIES_FILE, {})
users = load_json(USERS_FILE, {})
orders = load_json(ORDERS_FILE, {})
sessions = {}

# --------------------
# FSM States
# --------------------
class BuyFSM(StatesGroup):
    choose_currency = State()
    amount = State()
    wallet = State()
    confirm = State()

class AdminFSM(StatesGroup):
    main = State()
    add_name = State()
    add_rate = State()
    edit_choose = State()
    edit_name = State()
    edit_rate_choose = State()
    edit_rate_set = State()
    delete_choose = State()

# --------------------
# Utilities
# --------------------
def is_admin(uid):
    return int(uid) == int(ADMIN_ID)

def ensure_user(uid, tg_user=None):
    key = str(uid)
    if key not in users:
        users[key] = {
            "id": uid,
            "name": tg_user.full_name if tg_user else "",
            "username": tg_user.username if tg_user else "",
            "orders": []
        }
        save_json(USERS_FILE, users)
    return users[key]

def main_menu_kb(uid=None):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(types.KeyboardButton("📲 Sotib olish"))
    if uid and is_admin(uid):
        kb.add(types.KeyboardButton("⚙️ Admin Panel"))
    return kb

def back_kb():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    kb.add(types.KeyboardButton("◀️ Bekor qilish"))
    return kb

def new_order_id():
    return str(int(time.time() * 1000))

# --------------------
# Start
# --------------------
@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    uid = message.from_user.id
    ensure_user(uid, message.from_user)
    await message.answer("Assalomu alaykum! Menyu orqali davom eting.", reply_markup=main_menu_kb(uid))

# --------------------
# Sotib olish logikasi
# --------------------
@dp.message_handler(lambda message: message.text == "📲 Sotib olish")
async def buy_start(message: types.Message):
    uid = message.from_user.id
    if not currencies:
        await message.answer("Hozircha valyuta mavjud emas. Iltimos admin bilan bog'laning.")
        return
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    for cur in currencies.keys():
        kb.add(types.KeyboardButton(cur))
    kb.add(types.KeyboardButton("◀️ Bekor qilish"))
    await message.answer("Qaysi valyutani sotib olmoqchisiz?", reply_markup=kb)
    await BuyFSM.choose_currency.set()

@dp.message_handler(state=BuyFSM.choose_currency)
async def choose_currency(message: types.Message, state: FSMContext):
    if message.text == "◀️ Bekor qilish":
        await state.finish()
        await message.answer("Bekor qilindi.", reply_markup=main_menu_kb(message.from_user.id))
        return
    if message.text not in currencies:
        await message.answer("Valyuta topilmadi. Qaytadan tanlang.")
        return
    await state.update_data(currency=message.text)
    await message.answer(f"{message.text} bo‘yicha qancha miqdorda olmoqchisiz?")
    await BuyFSM.next()

@dp.message_handler(state=BuyFSM.amount)
async def amount_handler(message: types.Message, state: FSMContext):
    try:
        amt = float(message.text.replace(",", "."))
    except:
        await message.answer("Iltimos raqam kiriting.")
        return
    await state.update_data(amount=amt)
    await message.answer("Hamyon raqamingizni kiriting:")
    await BuyFSM.next()

@dp.message_handler(state=BuyFSM.wallet)
async def wallet_handler(message: types.Message, state: FSMContext):
    await state.update_data(wallet=message.text)
    data = await state.get_data()
    currency = data["currency"]
    amt = data["amount"]
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(types.KeyboardButton("Chek yuborish"))
    kb.add(types.KeyboardButton("◀️ Bekor qilish"))
    await message.answer(f"{amt} {currency} uchun to‘lovni quyidagi karta raqamiga qiling:\n5614 6818 7267 2690", reply_markup=kb)
    await BuyFSM.next()

@dp.message_handler(state=BuyFSM.confirm)
async def confirm_handler(message: types.Message, state: FSMContext):
    if message.text == "◀️ Bekor qilish":
        await state.finish()
        await message.answer("Bekor qilindi.", reply_markup=main_menu_kb(message.from_user.id))
        return
    if message.text != "Chek yuborish":
        await message.answer("Iltimos faqat 'Chek yuborish' tugmasini bosing.")
        return
    data = await state.get_data()
    order_id = new_order_id()
    order = {
        "id": order_id,
        "user_id": message.from_user.id,
        "currency": data["currency"],
        "amount": data["amount"],
        "wallet": data["wallet"],
        "type": "buy",
        "status": "waiting_admin",
        "created_at": int(time.time()),
        "rate": currencies[data["currency"]]["buy_rate"]
    }
    orders[order_id] = order
    users.setdefault(str(message.from_user.id), {"id": message.from_user.id}).setdefault("orders", []).append(order_id)
    save_json(ORDERS_FILE, orders)
    save_json(USERS_FILE, users)
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"admin_order|confirm|{order_id}"))
    kb.add(types.InlineKeyboardButton("❌ Bekor qilish", callback_data=f"admin_order|reject|{order_id}"))
    await bot.send_message(ADMIN_ID, f"Yangi buyurtma!\nFoydalanuvchi: {message.from_user.full_name}\nID: {message.from_user.id}\nValyuta: {data['currency']}\nMiqdor: {data['amount']}\nHamyon: {data['wallet']}\nBuyurtma ID: {order_id}", reply_markup=kb)
    await message.answer("✅ Buyurtma adminga yuborildi.", reply_markup=main_menu_kb(message.from_user.id))
    await state.finish()

# --------------------
# Run bot
# --------------------
if __name__ == "__main__":
    print("Bot ishga tushmoqda...")
    executor.start_polling(dp, skip_updates=True)
