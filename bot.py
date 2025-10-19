# obmen_bot_full.py
# -*- coding: utf-8 -*-
import os, json, time, logging
from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.dispatcher import FSMContext

# --------------------
# Sozlamalar
# --------------------
os.environ["TZ"] = "Asia/Tashkent"
API_TOKEN = "8468598297:AAFOjfJNz356TcTgOegnYNdIdbGZh3yqjTE"
ADMIN_ID = 7973934849
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
        with open(path,"w",encoding="utf-8") as f:
            json.dump(default,f,ensure_ascii=False,indent=2)
        return default
    with open(path,"r",encoding="utf-8") as f:
        try: return json.load(f)
        except: return default

def save_json(path, data):
    with open(path,"w",encoding="utf-8") as f:
        json.dump(data,f,ensure_ascii=False,indent=2)

# --------------------
# Data stores
# --------------------
currencies = load_json(CURRENCIES_FILE, {})
users = load_json(USERS_FILE, {})
orders = load_json(ORDERS_FILE, {})
sessions = {}

# --------------------
# FSM
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
    edit_rate = State()
    delete_choose = State()

# --------------------
# Utilities
# --------------------
def is_admin(uid):
    return int(uid)==int(ADMIN_ID)

def ensure_user(uid,tg_user=None):
    key = str(uid)
    if key not in users:
        users[key]={"id":uid,"name":tg_user.full_name if tg_user else "",
                    "username":tg_user.username if tg_user else "",
                    "orders":[]}
        save_json(USERS_FILE,users)
    return users[key]

def main_menu_kb(uid=None):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(types.KeyboardButton("📲 Sotib olish"))
    if uid and is_admin(uid):
        kb.add(types.KeyboardButton("⚙️ Admin Panel"))
    return kb

def back_kb():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True,one_time_keyboard=True)
    kb.add(types.KeyboardButton("◀️ Bekor qilish"))
    return kb

def new_order_id():
    return str(int(time.time()*1000))

# --------------------
# Start
# --------------------
@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    uid = message.from_user.id
    ensure_user(uid,message.from_user)
    await message.answer("Assalomu alaykum! Menyu orqali davom eting.", reply_markup=main_menu_kb(uid))

# --------------------
# Sotib olish
# --------------------
@dp.message_handler(lambda message: message.text=="📲 Sotib olish")
async def buy_start(message: types.Message):
    uid = message.from_user.id
    if not currencies:
        await message.answer("Hozircha valyuta mavjud emas. Iltimos admin bilan bog'laning.")
        return
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True,one_time_keyboard=True)
    for cur in currencies.keys():
        kb.add(types.KeyboardButton(cur))
    kb.add(types.KeyboardButton("◀️ Bekor qilish"))
    await message.answer("Qaysi valyutani sotib olmoqchisiz?", reply_markup=kb)
    await BuyFSM.choose_currency.set()

@dp.message_handler(state=BuyFSM.choose_currency)
async def choose_currency(message: types.Message, state: FSMContext):
    if message.text=="◀️ Bekor qilish":
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
        amt = float(message.text.replace(",","."))
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
    rate = currencies[currency]["buy_rate"]
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(types.KeyboardButton("Chek yuborish"))
    kb.add(types.KeyboardButton("◀️ Bekor qilish"))
    await message.answer(f"{amt} {currency} uchun to‘lovni quyidagi karta raqamiga qiling:\n5614 6818 7267 2690", reply_markup=kb)
    await BuyFSM.next()

@dp.message_handler(state=BuyFSM.confirm)
async def confirm_handler(message: types.Message, state: FSMContext):
    if message.text=="◀️ Bekor qilish":
        await state.finish()
        await message.answer("Bekor qilindi.", reply_markup=main_menu_kb(message.from_user.id))
        return
    if message.text!="Chek yuborish":
        await message.answer("Iltimos faqat 'Chek yuborish' tugmasini bosing.")
        return
    data = await state.get_data()
    order_id = new_order_id()
    order = {"id":order_id,"user_id":message.from_user.id,"currency":data["currency"],
             "amount":data["amount"],"wallet":data["wallet"],"type":"buy","status":"waiting_admin",
             "created_at":int(time.time()),"rate":currencies[data["currency"]]["buy_rate"]}
    orders[order_id] = order
    users.setdefault(str(message.from_user.id), {"id": message.from_user.id}).setdefault("orders", []).append(order_id)
    save_json(ORDERS_FILE, orders)
    save_json(USERS_FILE, users)
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"admin_order|confirm|{order_id}"))
    kb.add(types.InlineKeyboardButton("❌ Bekor qilish", callback_data=f"admin_order|reject|{order_id}"))
    await bot.send_message(ADMIN_ID,f"Yangi buyurtma!\nFoydalanuvchi: {message.from_user.full_name}\nID: {message.from_user.id}\nValyuta: {data['currency']}\nMiqdor: {data['amount']}\nHamyon: {data['wallet']}\nBuyurtma ID: {order_id}", reply_markup=kb)
    await message.answer("✅ Buyurtma adminga yuborildi.", reply_markup=main_menu_kb(message.from_user.id))
    await state.finish()

# --------------------
# Admin buyurtma tasdiqlash / bekor qilish
# --------------------
@dp.callback_query_handler(lambda c: c.data.startswith("admin_order"))
async def admin_order_cb(call: types.CallbackQuery):
    parts = call.data.split("|")
    if len(parts)!=3: return await call.answer("Xato callback")
    action, order_id = parts[1], parts[2]
    order = orders.get(order_id)
    if not order: return await call.answer("Buyurtma topilmadi")
    if action=="confirm":
        order["status"]="confirmed"
        save_json(ORDERS_FILE, orders)
        await bot.send_message(order["user_id"], f"Sizning buyurtmangiz tasdiqlandi ✅")
        await call.answer("Tasdiqlandi")
    elif action=="reject":
        order["status"]="rejected"
        save_json(ORDERS_FILE, orders)
        await bot.send_message(order["user_id"], f"Sizning buyurtmangiz bekor qilindi ❌")
        await call.answer("Bekor qilindi")

# --------------------
# Admin Panel Start
# --------------------
@dp.message_handler(lambda message: message.text=="⚙️ Admin Panel")
async def admin_panel_start(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("Siz admin emassiz.")
        return
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("➕ Valyuta qo‘shish", "✏️ Valyuta nomini o‘zgartirish")
    kb.add("💰 Valyuta kursini o‘zgartirish", "🗑️ Valyuta o‘chirish")
    kb.add("◀️ Orqaga")
    await message.answer("Admin panel:", reply_markup=kb)
    await AdminFSM.main.set()

# Admin panel FSM
@dp.message_handler(state=AdminFSM.main)
async def admin_main(message: types.Message, state: FSMContext):
    if message.text=="➕ Valyuta qo‘shish":
        await message.answer("Valyuta nomini kiriting:", reply_markup=back_kb())
        await AdminFSM.add_name.set()
    elif message.text=="✏️ Valyuta nomini o‘zgartirish":
        if not currencies:
            await message.answer("Hozircha valyuta mavjud emas.", reply_markup=back_kb())
            return
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        for cur in currencies.keys():
            kb.add(types.KeyboardButton(cur))
        kb.add("◀️ Bekor qilish")
        await message.answer("Qaysi valyuta nomini o‘zgartirmoqchisiz?", reply_markup=kb)
        await AdminFSM.edit_choose.set()
    elif message.text=="💰 Valyuta kursini o‘zgartirish":
        if not currencies:
            await message.answer("Hozircha valyuta mavjud emas.", reply_markup=back_kb())
            return
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        for cur in currencies.keys():
            kb.add(types.KeyboardButton(cur))
        kb.add("◀️ Bekor qilish")
        await message.answer("Qaysi valyuta kursini o‘zgartirmoqchisiz?", reply_markup=kb)
        await AdminFSM.edit_rate.set()
    elif message.text=="🗑️ Valyuta o‘chirish":
        if not currencies:
            await message.answer("Hozircha valyuta mavjud emas.", reply_markup=back_kb())
            return
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        for cur in currencies.keys():
            kb.add(types.KeyboardButton(cur))
        kb.add("◀️ Bekor qilish")
        await message.answer("Qaysi valyutani o‘chirmoqchisiz?", reply_markup=kb)
        await AdminFSM.delete_choose.set()
    elif message.text=="◀️ Orqaga":
        await state.finish()
        await message.answer("Bosh menyu:", reply_markup=main_menu_kb(message.from_user.id))
    else:
        await message.answer("Noto‘g‘ri tugma. Qaytadan tanlang.")

# Valyuta qo‘shish
@dp.message_handler(state=AdminFSM.add_name)
async def add_currency_name(message: types.Message, state: FSMContext):
    if message.text=="◀️ Bekor qilish":
        await state.finish()
        await admin_panel_start(message)
        return
    await state.update_data(new_name=message.text)
    await message.answer("Valyuta kursini kiriting (raqam):", reply_markup=back_kb())
    await AdminFSM.add_rate.set()

@dp.message_handler(state=AdminFSM.add_rate)
async def add_currency_rate(message: types.Message, state: FSMContext):
    if message.text=="◀️ Bekor qilish":
        await state.finish()
        await admin_panel_start(message)
        return
    try:
        rate = float(message.text.replace(",",".")) 
    except:
        await message.answer("Iltimos to‘g‘ri raqam kiriting.")
        return
    data = await state.get_data()
    currencies[data["new_name"]] = {"buy_rate":rate,"sell_rate":rate}
    save_json(CURRENCIES_FILE, currencies)
    await message.answer(f"{data['new_name']} qo‘shildi! Buy/Sell: {rate}", reply_markup=back_kb())
    await state.finish()
    await admin_panel_start(message)

# Valyuta nomini o‘zgartirish
@dp.message_handler(state=AdminFSM.edit_choose)
async def edit_currency_choose(message: types.Message, state: FSMContext):
    if message.text=="◀️ Bekor qilish":
        await state.finish()
        await admin_panel_start(message)
        return
    if message.text not in currencies:
        await message.answer("Valyuta topilmadi.")
        return
    await state.update_data(edit_name_old=message.text)
    await message.answer("Yangi nom kiriting:", reply_markup=back_kb())
    await AdminFSM.edit_name.set()

@dp.message_handler(state=AdminFSM.edit_name)
async def edit_currency_name(message: types.Message, state: FSMContext):
    if message.text=="◀️ Bekor qilish":
        await state.finish()
        await admin_panel_start(message)
        return
    data = await state.get_data()
    currencies[message.text] = currencies.pop(data["edit_name_old"])
    save_json(CURRENCIES_FILE, currencies)
    await message.answer(f"{data['edit_name_old']} nomi {message.text} ga o‘zgartirildi.", reply_markup=back_kb())
    await state.finish()
    await admin_panel_start(message)

# Valyuta kursini o‘zgartirish
@dp.message_handler(state=AdminFSM.edit_rate)
async def edit_currency_rate_choose(message: types.Message, state: FSMContext):
    if message.text=="◀️ Bekor qilish":
        await state.finish()
        await admin_panel_start(message)
        return
    if message.text not in currencies:
        await message.answer("Valyuta topilmadi.")
        return
    await state.update_data(rate_name=message.text)
    await message.answer(f"{message.text} uchun yangi kursni kiriting:", reply_markup=back_kb())
    await AdminFSM.next()

@dp.message_handler(state=AdminFSM.next)
async def edit_currency_rate_set(message: types.Message, state: FSMContext):
    if message.text=="◀️ Bekor qilish":
        await state.finish()
        await admin_panel_start(message)
        return
    try:
        rate = float(message.text.replace(",",".")) 
    except:
        await message.answer("Iltimos raqam kiriting.")
        return
    data = await state.get_data()
    currencies[data["rate_name"]]["buy_rate"] = rate
    currencies[data["rate_name"]]["sell_rate"] = rate
    save_json(CURRENCIES_FILE, currencies)
    await message.answer(f"{data['rate_name']} kursi yangilandi: {rate}", reply_markup=back_kb())
    await state.finish()
    await admin_panel_start(message)

# Valyuta o‘chirish
@dp.message_handler(state=AdminFSM.delete_choose)
async def delete_currency(message: types.Message, state: FSMContext):
    if message.text=="◀️ Bekor qilish":
        await state.finish()
        await admin_panel_start(message)
        return
    if message.text not in currencies:
        await message.answer("Valyuta topilmadi.")
        return
    removed = currencies.pop(message.text)
    save_json(CURRENCIES_FILE, currencies)
    await message.answer(f"{message.text} o‘chirildi.", reply_markup=back_kb())
    await state.finish()
    await admin_panel_start(message)
# --------------------
# Run bot
# --------------------
if __name__=="__main__":
    print("Bot ishga tushmoqda...")
    executor.start_polling(dp, skip_updates=True)
