import asyncio
import csv
import os
from datetime import datetime
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, BufferedInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("Не задан BOT_TOKEN в .env файле")

# Список администраторов (добавьте сюда все ID, кому нужен доступ)
ADMIN_IDS = [5573362, 298826270]

storage = MemoryStorage()
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=storage)

CSV_FILE = "data.csv"

EXPECTED_HEADERS = [
    "Дата/время",
    "ФИО",
    "Номер квартиры",
    "Номер телефона",
    "ХВС",
    "ГВС",
    "Тепло",
    "Подъезд",
    "Этаж",
    "Email"
]

class SurveyStates(StatesGroup):
    waiting_fullname = State()
    waiting_apartment = State()
    waiting_entrance = State()
    waiting_floor = State()
    waiting_phone = State()
    waiting_email = State()
    waiting_meters = State()
    confirm = State()

def migrate_csv():
    if not os.path.exists(CSV_FILE):
        return
    with open(CSV_FILE, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        rows = list(reader)
    if not rows:
        return
    headers = rows[0]
    if len(headers) >= len(EXPECTED_HEADERS):
        return
    new_rows = []
    new_rows.append(EXPECTED_HEADERS)
    for row in rows[1:]:
        while len(row) < len(EXPECTED_HEADERS):
            row.append("")
        new_rows.append(row)
    with open(CSV_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerows(new_rows)

def init_csv():
    if not os.path.exists(CSV_FILE):
        with open(CSV_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(EXPECTED_HEADERS)
    else:
        migrate_csv()

def save_to_csv(data):
    with open(CSV_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            data["fullname"],
            data["apartment"],
            data["phone"],
            "Да" if data["hvs"] else "Нет",
            "Да" if data["gvs"] else "Нет",
            "Да" if data["heat"] else "Нет",
            data.get("entrance", ""),
            data.get("floor", ""),
            data.get("email", "")
        ])

def read_all_records():
    if not os.path.exists(CSV_FILE):
        return []
    with open(CSV_FILE, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        rows = list(reader)
    return rows

def get_stats():
    rows = read_all_records()
    if len(rows) <= 1:
        return 0, 0, 0, 0
    data_rows = rows[1:]
    total = len(data_rows)
    hvs = sum(1 for r in data_rows if len(r) > 4 and r[4] == "Да")
    gvs = sum(1 for r in data_rows if len(r) > 5 and r[5] == "Да")
    heat = sum(1 for r in data_rows if len(r) > 6 and r[6] == "Да")
    return total, hvs, gvs, heat

@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "🏠 Добро пожаловать! Мы помогаем жителям нашего дома организовать поверку счётчиков ХВС, ГВС и Тепла.\n"
        "Адрес: Измайловский проезд, 5А\n\n"
        "Чтобы мы могли подготовить коллективную заявку, пожалуйста, ответьте на несколько вопросов.\n\n"
        "Введите ваше ФИО (полностью):",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.set_state(SurveyStates.waiting_fullname)

@dp.message(SurveyStates.waiting_fullname)
async def process_fullname(message: Message, state: FSMContext):
    fullname = message.text.strip()
    if not fullname:
        await message.answer("Пожалуйста, введите ФИО (не оставляйте пустым):")
        return
    await state.update_data(fullname=fullname)
    await message.answer("Введите номер вашей квартиры (цифрами):")
    await state.set_state(SurveyStates.waiting_apartment)

@dp.message(SurveyStates.waiting_apartment)
async def process_apartment(message: Message, state: FSMContext):
    apartment = message.text.strip()
    if not apartment.isdigit():
        await message.answer("Номер квартиры должен состоять только из цифр. Попробуйте ещё раз:")
        return
    await state.update_data(apartment=apartment)
    await message.answer("Введите номер вашего подъезда (цифрами):")
    await state.set_state(SurveyStates.waiting_entrance)

@dp.message(SurveyStates.waiting_entrance)
async def process_entrance(message: Message, state: FSMContext):
    entrance = message.text.strip()
    if not entrance.isdigit():
        await message.answer("Номер подъезда должен состоять только из цифр. Попробуйте ещё раз:")
        return
    await state.update_data(entrance=entrance)
    await message.answer("Введите номер вашего этажа (цифрами):")
    await state.set_state(SurveyStates.waiting_floor)

@dp.message(SurveyStates.waiting_floor)
async def process_floor(message: Message, state: FSMContext):
    floor = message.text.strip()
    if not floor.isdigit():
        await message.answer("Номер этажа должен состоять только из цифр. Попробуйте ещё раз:")
        return
    await state.update_data(floor=floor)
    await message.answer("Введите ваш номер телефона (в формате +7XXXXXXXXXX):")
    await state.set_state(SurveyStates.waiting_phone)

@dp.message(SurveyStates.waiting_phone)
async def process_phone(message: Message, state: FSMContext):
    phone = message.text.strip()
    if not phone.startswith('+') or not phone[1:].isdigit():
        await message.answer("Пожалуйста, введите номер в международном формате, например +79001234567:")
        return
    await state.update_data(phone=phone)
    await message.answer("Введите ваш адрес электронной почты (для отправки чека и документов):")
    await state.set_state(SurveyStates.waiting_email)

@dp.message(SurveyStates.waiting_email)
async def process_email(message: Message, state: FSMContext):
    email = message.text.strip()
    if not email or '@' not in email:
        await message.answer("Пожалуйста, введите корректный email (например, example@mail.ru):")
        return
    await state.update_data(email=email)
    builder = InlineKeyboardBuilder()
    builder.button(text="❄️ ХВС", callback_data="meter_hvs")
    builder.button(text="🔥 ГВС", callback_data="meter_gvs")
    builder.button(text="🌡️ Тепло", callback_data="meter_heat")
    builder.button(text="✅ Готово", callback_data="meter_done")
    builder.adjust(2, 2)
    await message.answer(
        "Выберите счётчики, которые нужно поверить.\n"
        "Нажмите на кнопку с нужным типом, чтобы отметить/снять отметку.\n"
        "Когда закончите, нажмите «Готово».",
        reply_markup=builder.as_markup()
    )
    await state.set_state(SurveyStates.waiting_meters)
    await state.update_data(hvs=False, gvs=False, heat=False)

@dp.callback_query(SurveyStates.waiting_meters, F.data.startswith("meter_"))
async def process_meter_selection(callback: CallbackQuery, state: FSMContext):
    action = callback.data.split("_")[1]
    data = await state.get_data()
    if action == "done":
        if not (data.get("hvs") or data.get("gvs") or data.get("heat")):
            await callback.answer("Выберите хотя бы один счётчик!", show_alert=True)
            return
        await callback.message.delete_reply_markup()
        summary = (
            f"📋 Проверьте введённые данные:\n"
            f"ФИО: {data['fullname']}\n"
            f"Квартира: {data['apartment']}\n"
            f"Подъезд: {data['entrance']}\n"
            f"Этаж: {data['floor']}\n"
            f"Телефон: {data['phone']}\n"
            f"Email: {data['email']}\n"
            f"ХВС: {'Да' if data['hvs'] else 'Нет'}\n"
            f"ГВС: {'Да' if data['gvs'] else 'Нет'}\n"
            f"Тепло: {'Да' if data['heat'] else 'Нет'}\n\n"
            "Всё верно? Нажмите «Да» для сохранения или «Нет» для начала заново."
        )
        kb = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="✅ Да"), KeyboardButton(text="❌ Нет")]],
            resize_keyboard=True,
            one_time_keyboard=True
        )
        await callback.message.answer(summary, reply_markup=kb)
        await state.set_state(SurveyStates.confirm)
        await callback.answer()
        return
    key = action
    current = data.get(key, False)
    data[key] = not current
    await state.update_data(**{key: data[key]})
    builder = InlineKeyboardBuilder()
    builder.button(
        text=f"{'✅' if data['hvs'] else '❄️'} ХВС",
        callback_data="meter_hvs"
    )
    builder.button(
        text=f"{'✅' if data['gvs'] else '🔥'} ГВС",
        callback_data="meter_gvs"
    )
    builder.button(
        text=f"{'✅' if data['heat'] else '🌡️'} Тепло",
        callback_data="meter_heat"
    )
    builder.button(text="✅ Готово", callback_data="meter_done")
    builder.adjust(2, 2)
    await callback.message.edit_text(
        "Выберите счётчики, которые нужно поверить.\n"
        "Нажмите на кнопку с нужным типом, чтобы отметить/снять отметку.\n"
        "Когда закончите, нажмите «Готово».",
        reply_markup=builder.as_markup()
    )
    await callback.answer()

@dp.message(SurveyStates.confirm)
async def process_confirm(message: Message, state: FSMContext):
    if message.text == "✅ Да":
        data = await state.get_data()
        save_to_csv(data)
        await message.answer(
            "✅ Спасибо! Ваши данные сохранены.\n"
            "Мы свяжемся с вами для уточнения даты поверки.",
            reply_markup=ReplyKeyboardRemove()
        )
        await state.clear()
    elif message.text == "❌ Нет":
        await message.answer(
            "Хорошо, начнём заново. Введите ваше ФИО:",
            reply_markup=ReplyKeyboardRemove()
        )
        await state.clear()
        await state.set_state(SurveyStates.waiting_fullname)
    else:
        await message.answer("Пожалуйста, нажмите кнопку «Да» или «Нет».")

@dp.message(StateFilter(
    SurveyStates.waiting_fullname,
    SurveyStates.waiting_apartment,
    SurveyStates.waiting_entrance,
    SurveyStates.waiting_floor,
    SurveyStates.waiting_phone,
    SurveyStates.waiting_email
))
async def handle_incorrect_input(message: Message, state: FSMContext):
    await message.answer("Пожалуйста, следуйте инструкциям и введите запрашиваемые данные.")

# ============ АДМИН-ФУНКЦИОНАЛ ============

@dp.message(Command("admin"))
async def admin_cmd(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⛔ У вас нет доступа к этой команде.")
        return

    builder = InlineKeyboardBuilder()
    builder.button(text="📋 Последние 20 записей", callback_data="admin_show")
    builder.button(text="📥 Скачать все данные (CSV)", callback_data="admin_download")
    builder.button(text="📊 Статистика", callback_data="admin_stats")
    builder.button(text="❌ Закрыть меню", callback_data="admin_close")
    builder.adjust(1)

    await message.answer(
        "🔐 Админ-панель\n\nВыберите действие:",
        reply_markup=builder.as_markup()
    )

@dp.callback_query(F.data.startswith("admin_"))
async def admin_actions(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Доступ запрещён.", show_alert=True)
        await callback.message.delete_reply_markup()
        return

    action = callback.data.split("_")[1]

    if action == "close":
        await callback.message.delete_reply_markup()
        await callback.message.answer("Меню закрыто.")
        await callback.answer()
        return

    if action == "show":
        try:
            rows = read_all_records()
            if len(rows) <= 1:
                await callback.message.answer("📭 Нет сохранённых записей.")
                await callback.answer()
                return
            data_rows = rows[1:]
            last_20 = data_rows[-20:]
            if not last_20:
                await callback.message.answer("Нет записей.")
                await callback.answer()
                return

            output = "📋 Последние 20 записей:\n\n"
            for row in reversed(last_20):
                date = row[0] if len(row) > 0 else ""
                name = row[1] if len(row) > 1 else ""
                apt = row[2] if len(row) > 2 else ""
                phone = row[3] if len(row) > 3 else ""
                hvs = row[4] if len(row) > 4 else ""
                gvs = row[5] if len(row) > 5 else ""
                heat = row[6] if len(row) > 6 else ""
                entrance = row[7] if len(row) > 7 else ""
                floor = row[8] if len(row) > 8 else ""
                email = row[9] if len(row) > 9 else ""

                line = f"{date} | {name} | кв.{apt}"
                if entrance:
                    line += f" (п.{entrance})"
                if floor:
                    line += f" эт.{floor}"
                line += f"\n   Тел.: {phone} | Email: {email if email else '—'}"
                line += f"\n   ХВС:{hvs} ГВС:{gvs} Тепло:{heat}\n\n"
                output += line

                if len(output) > 3900:
                    output += "\n... (показаны не все записи, скачайте CSV)"
                    break

            await callback.message.delete_reply_markup()
            await callback.message.answer(output)
            await callback.answer()

        except Exception as e:
            await callback.message.answer(f"❌ Ошибка при формировании списка:\n{str(e)}")
            await callback.answer()
        return

    if action == "download":
        if not os.path.exists(CSV_FILE):
            await callback.message.answer("Файл с данными ещё не создан.")
            await callback.answer()
            return
        with open(CSV_FILE, "rb") as f:
            file_data = f.read()
        await callback.message.delete_reply_markup()
        await callback.message.answer_document(
            BufferedInputFile(file_data, filename="data.csv"),
            caption="📎 Все данные в формате CSV."
        )
        await callback.answer()
        return

    if action == "stats":
        total, hvs, gvs, heat = get_stats()
        stats_text = (
            f"📊 Статистика\n\n"
            f"👥 Всего заявок: {total}\n"
            f"❄️ ХВС: {hvs}\n"
            f"🔥 ГВС: {gvs}\n"
            f"🌡️ Тепло: {heat}"
        )
        await callback.message.delete_reply_markup()
        await callback.message.answer(stats_text)
        await callback.answer()
        return

# ============ ЗАПУСК ============
async def main():
    init_csv()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())