import asyncio
import logging
from datetime import datetime, date
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv
import os
import re

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
DRIVER_GROUP = int(os.getenv("DRIVER_GROUP_ID"))

bot = Bot(token=TOKEN, parse_mode="HTML")
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
logging.basicConfig(level=logging.INFO)

orders = []
unique_users = set()
today_users = set()
today_repeat = 0
banned_users = []

class Order(StatesGroup):
    waiting_info = State()

class AdminStates(StatesGroup):
    broadcast = State()
    ban = State()

def main_menu():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="Termiz → Toshkent")],
        [KeyboardButton(text="Toshkent → Termiz")],
        [KeyboardButton(text="Pochta hizmati")],
        [KeyboardButton(text="Sozlamalar")]
    ], resize_keyboard=True)

def admin_panel():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="Statistika")],
        [KeyboardButton(text="Guruhga xabar")],
        [KeyboardButton(text="Foydalanuvchi banlash")],
        [KeyboardButton(text="Orqaga")]
    ], resize_keyboard=True)

def count_people(text: str) -> int:
    text = text.lower()
    numbers = re.findall(r'\d+', text)
    for n in numbers:
        num = int(n)
        if 1 <= num <= 20:
            if any(w in text for w in ["kishi", "odam", "joy", "o'", "kish", "adam"]):
                return num
    return 1

@dp.message(Command("start"))
async def start(message: Message):
    uid = message.from_user.id
    if uid in banned_users:
        return await message.answer("Siz banlangansiz!")
    if uid == ADMIN_ID:
        return await message.answer("Admin panel", reply_markup=admin_panel())
    await message.answer(
        "<b>Termiz – Toshkent Taxi Bot</b>\n\n"
        "Assalomu alaykum! Yo‘nalishni tanlang",
        reply_markup=main_menu()
    )

@dp.message(F.text.in_(["Termiz → Toshkent", "Toshkent → Termiz", "Pochta hizmati"]))
async def direction(message: Message, state: FSMContext):
    if message.from_user.id in banned_users: return
    await state.update_data(dir=message.text)
    await message.answer(
        f"Yo‘nalish: <b>{message.text}</b>\n\n"
        "Ism, telefon va qo‘shimcha ma’lumot yozing:\n"
        "(masalan: Akbar +99899... 3 kishi)",
        reply_markup=types.ReplyKeyboardRemove()
    )
    await state.set_state(Order.waiting_info)

@dp.message(Order.waiting_info)
async def info(message: Message, state: FSMContext):
    user = message.from_user
    data = await state.get_data()
    direction = data.get("dir", "Noma’lum")
    people = count_people(message.text)
    now = datetime.now()
    today = date.today()

    is_new_today = all(o["user_id"] != user.id or o["date"] != today for o in orders)

    orders.append({"user_id": user.id, "full_name": user.full_name, "info": message.text, "people": people, "time": now, "date": today})
    unique_users.add(user.id)
    if is_new_today:
        today_users.add(user.id)
    else:
        global today_repeat
        today_repeat += 1

    await message.answer("Buyurtmangiz qabul qilindi! Tez orada bog‘lanamiz", reply_markup=main_menu())

    text = (
        "<b>YANGI BUYURTMA</b>\n\n"
        f"<b>Mijoz:</b> <a href='tg://user?id={user.id}'>{user.full_name}</a>\n"
        f"<b>Yo‘nalish:</b> {direction}\n"
        f"<b>Odamlar:</b> {people} kishi\n"
        f"<b>Info:</b> {message.text}\n"
        f"<b>Vaqti:</b> {now.strftime('%H:%M')}"
    )
    await bot.send_message(DRIVER_GROUP, text)
    if message.chat.id == DRIVER_GROUP:
        await message.delete()
    await state.clear()

@dp.message(F.chat.type.in_({"group", "supergroup"}))
async def clean_group(message: Message):
    if message.chat.id != DRIVER_GROUP: return
    admins = [a.user.id for a in await bot.get_chat_administrators(DRIVER_GROUP)]
    if message.from_user.id not in admins:
        await message.delete()

@dp.message(F.text == "Statistika")
async def stats(message: Message):
    if message.from_user.id != ADMIN_ID: return
    today = date.today()
    today_list = [o for o in orders if o["date"] == today]
    today_people = sum(o["people"] for o in today_list)
    total_people = sum(o["people"] for o in orders)

    last5 = "\n".join(
        f"• {o['time'].strftime('%H:%M')} – {o['full_name']} ({o['info'][:30]}...)"
        for o in orders[-5:]
    ) or "Hali buyurtma yo‘q"

    text = (
        "<b>FOYDALANUVCHILAR STATISTIKASI</b>\n\n"
        f"Bugun mijozlar: <b>{len(today_list)} kishi</b>\n"
        f"Bugun odamlar: <b>{today_people} kishi</b>\n\n"
        f"Jami odamlar: <b>{total_people} kishi</b>\n"
        f"Jami noyob mijozlar: <b>{len(unique_users)} ta</b>\n\n"
        f"Bugun yangi: <b>{len(today_users)} ta</b>\n"
        f"Bugun takroriy: <b>{today_repeat} ta</b>\n\n"
        f"<b>Oxirgi 5 ta:</b>\n{last5}"
    )
    await message.answer(text, reply_markup=admin_panel())

@dp.message(F.text == "Guruhga xabar")
async def bc_start(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    await message.answer("Xabar yozing:")
    await state.set_state(AdminStates.broadcast)

@dp.message(AdminStates.broadcast)
async def bc_send(message: Message, state: FSMContext):
    await bot.send_message(DRIVER_GROUP, f"<b>Admin xabar:</b>\n\n{message.text}")
    await message.answer("Yuborildi!", reply_markup=admin_panel())
    await state.clear()

@dp.message(F.text == "Foydalanuvchi banlash")
async def ban_start(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    await message.answer("User ID yoki @username yozing:")
    await state.set_state(AdminStates.ban)

@dp.message(AdminStates.ban)
async def ban_do(message: Message, state: FSMContext):
    txt = message.text.strip().replace("@", "")
    try:
        uid = int(txt) if txt.isdigit() else (await bot.get_chat(txt)).id
        banned_users.append(uid)
        await message.answer(f"{uid} banlandi!", reply_markup=admin_panel())
    except:
        await message.answer("Topilmadi")
    await state.clear()

@dp.message(F.text == "Orqaga")
async def back(message: Message):
    if message.from_user.id == ADMIN_ID:
        await message.answer("Admin panel", reply_markup=admin_panel())

async def main():
    print("Bot ishga tushdi! Statistika – faqat odamlar va mijozlar")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
