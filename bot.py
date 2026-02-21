import os
import asyncio
import sqlite3
import random
import logging
from datetime import datetime
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, FSInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.exceptions import TelegramForbiddenError

# Logger Setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
# Admin ID ကို integer အဖြစ်သေချာပြောင်းလဲခြင်း
try:
    ADMIN_ID = int(os.getenv("ADMIN_ID", 0))
except ValueError:
    logger.error("ADMIN_ID must be a valid number in .env file")
    ADMIN_ID = 0

bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- Database Core ---
def query_db(query, params=(), fetchone=False, commit=False):
    """Database connection ကို ပိုမိုလုံခြုံစိတ်ချရအောင် handling လုပ်ပေးထားသော function"""
    res = None
    conn = sqlite3.connect('church_plus.db')
    try:
        c = conn.cursor()
        c.execute(query, params)
        if commit:
            conn.commit()
        res = c.fetchone() if fetchone else c.fetchall()
    except Exception as e:
        logger.error(f"Database error: {e}")
    finally:
        conn.close()
    return res

def init_db():
    conn = sqlite3.connect('church_plus.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS verses (id INTEGER PRIMARY KEY AUTOINCREMENT, content TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS quizzes (id INTEGER PRIMARY KEY AUTOINCREMENT, question TEXT, a TEXT, b TEXT, c TEXT, d TEXT, correct TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS prayers (id INTEGER PRIMARY KEY AUTOINCREMENT, user_name TEXT, user_id INTEGER, content TEXT, date TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS members (user_id INTEGER PRIMARY KEY, username TEXT, joined_date TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS scores (user_id INTEGER PRIMARY KEY, name TEXT, points INTEGER DEFAULT 0)''')
    
    defaults = [
        ('about', '💒 *အသင်းတော်အကြောင်း*\n\nအချက်အလက်များ မထည့်သွင်းရသေးပါ။'),
        ('contact', '📞 *ဆက်သွယ်ရန်*\n\nဖုန်းနံပါတ်များ မရှိသေးပါ။'),
        ('events', '📅 *လာမည့်အစီအစဉ်များ*\n\nလက်ရှိတွင် အစီအစဉ်သစ် မရှိသေးပါ။'),
        ('birthday', '🎂 *ယခုလမွေးနေ့ရှင်များ*\n\nစာရင်းမရှိသေးပါ။')
    ]
    c.executemany("INSERT OR IGNORE INTO settings VALUES (?, ?)", defaults)
    conn.commit()
    conn.close()

# --- Keyboards ---
def main_menu():
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="⛪ About", callback_data="about"), InlineKeyboardButton(text="📞 Contact", callback_data="contact"))
    builder.row(InlineKeyboardButton(text="📖 Verse", callback_data="verse"), InlineKeyboardButton(text="📅 Events", callback_data="events"))
    builder.row(InlineKeyboardButton(text="🎮 Quiz", callback_data="quiz"), InlineKeyboardButton(text="🎂 Birthday", callback_data="birthday"))
    builder.row(InlineKeyboardButton(text="🙏 Pray", callback_data="pray_request_info"), InlineKeyboardButton(text="🏆 Leaderboard", callback_data="tops"))
    return builder.as_markup()

# --- Handlers ---
@dp.message(Command("start"))
async def cmd_start(message: Message):
    query_db("INSERT OR IGNORE INTO members VALUES (?, ?, ?)", 
             (message.from_user.id, message.from_user.username, datetime.now().strftime("%Y-%m-%d")), commit=True)
    
    welcome_text = (
        f"🙏 **မင်္ဂလာပါ {message.from_user.first_name}!**\n\n"
        "Church Community Bot မှ နွေးထွေးစွာ ကြိုဆိုပါသည်။ "
        "အောက်ပါ Menu များကို အသုံးပြု၍ အချက်အလက်များကို ရယူနိုင်ပါသည်။\n\n"
        "✨ *Created by : @Enoch_777*"
    )
    await message.answer(welcome_text, reply_markup=main_menu(), parse_mode="Markdown")

@dp.callback_query(F.data == "about")
async def show_about(callback: CallbackQuery):
    res = query_db("SELECT value FROM settings WHERE key='about'", fetchone=True)
    await callback.message.edit_text(res[0], reply_markup=main_menu(), parse_mode="Markdown")

@dp.callback_query(F.data == "contact")
async def show_contact(callback: CallbackQuery):
    res = query_db("SELECT value FROM settings WHERE key='contact'", fetchone=True)
    await callback.message.edit_text(res[0], reply_markup=main_menu(), parse_mode="Markdown")

@dp.callback_query(F.data == "verse")
async def show_verse(callback: CallbackQuery):
    verses = query_db("SELECT content FROM verses")
    text = f"📖 *ယနေ့အတွက် နှုတ်ကပတ်တော်*\n\n{random.choice(verses)[0]}" if verses else "⚠️ ကျမ်းချက်များ မရှိသေးပါ။"
    await callback.message.edit_text(text, reply_markup=main_menu(), parse_mode="Markdown")

@dp.callback_query(F.data == "events")
async def show_events(callback: CallbackQuery):
    res = query_db("SELECT value FROM settings WHERE key='events'", fetchone=True)
    await callback.message.edit_text(res[0], reply_markup=main_menu(), parse_mode="Markdown")

@dp.callback_query(F.data == "birthday")
async def show_birthday(callback: CallbackQuery):
    res = query_db("SELECT value FROM settings WHERE key='birthday'", fetchone=True)
    await callback.message.edit_text(res[0], reply_markup=main_menu(), parse_mode="Markdown")

@dp.callback_query(F.data == "pray_request_info")
async def pray_info(callback: CallbackQuery):
    await callback.answer("ဆုတောင်းစာပို့ရန် /pray <စာ> ဟု ရိုက်ပို့ပေးပါ။", show_alert=True)

# --- Quiz System ---
@dp.callback_query(F.data == "quiz")
async def start_quiz(callback: CallbackQuery):
    quizzes = query_db("SELECT * FROM quizzes")
    if not quizzes:
        return await callback.answer("မေးခွန်းများ မရှိသေးပါ။", show_alert=True)
    
    q = random.choice(quizzes)
    builder = InlineKeyboardBuilder()
    # Data Format: q_ans:UserChoice:CorrectChoice
    for choice in ['A', 'B', 'C', 'D']:
        builder.add(InlineKeyboardButton(text=choice, callback_data=f"q_ans:{choice}:{q[6]}"))
    
    text = f"❓ *Bible Quiz*\n\n{q[1]}\n\nA) {q[2]}\nB) {q[3]}\nC) {q[4]}\nD) {q[5]}"
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")

@dp.callback_query(F.data.startswith("q_ans:"))
async def check_quiz(callback: CallbackQuery):
    _, user_choice, correct_ans = callback.data.split(":")
    if user_choice == correct_ans:
        query_db("INSERT OR IGNORE INTO scores (user_id, name, points) VALUES (?, ?, 0)", 
                 (callback.from_user.id, callback.from_user.first_name), commit=True)
        query_db("UPDATE scores SET points = points + 10 WHERE user_id = ?", (callback.from_user.id,), commit=True)
        await callback.answer("🎯 မှန်ကန်ပါတယ်။ (+၁၀ မှတ်)", show_alert=True)
    else:
        await callback.answer(f"❌ မှားယွင်းပါတယ်။ အဖြေမှန်မှာ {correct_ans} ဖြစ်ပါတယ်။", show_alert=True)
    
    # ဖြေပြီးရင် Main Menu ပြန်ပို့ပေးမယ်
    res = query_db("SELECT value FROM settings WHERE key='about'", fetchone=True)
    await callback.message.edit_text(res[0], reply_markup=main_menu(), parse_mode="Markdown")

@dp.callback_query(F.data == "tops")
async def show_tops(callback: CallbackQuery):
    tops = query_db("SELECT name, points FROM scores ORDER BY points DESC LIMIT 10")
    text = "🏆 *Quiz Leaderboard*\n\n"
    if not tops: 
        text += "မှတ်တမ်း မရှိသေးပါ။"
    else:
        for i, row in enumerate(tops, 1):
            text += f"{i}. {row[0]} — {row[1]} Pts\n"
    await callback.message.edit_text(text, reply_markup=main_menu(), parse_mode="Markdown")

# --- Admin Section ---
def is_admin(user_id):
    return user_id == ADMIN_ID

@dp.message(Command("edabout"))
async def ed_about(message: Message):
    if not is_admin(message.from_user.id): return
    content = message.text.replace("/edabout", "").strip()
    if content:
        query_db("UPDATE settings SET value=? WHERE key='about'", (content,), commit=True)
        await message.reply("✅ About content updated!")

@dp.message(Command("edcontact"))
async def ed_contact(message: Message):
    if not is_admin(message.from_user.id): return
    content = message.text.replace("/edcontact", "").strip()
    if content:
        query_db("UPDATE settings SET value=? WHERE key='contact'", (content,), commit=True)
        await message.reply("✅ Contact content updated!")

@dp.message(Command("edverse"))
async def ed_verse(message: Message):
    if not is_admin(message.from_user.id): return
    lines = message.text.split("\n")[1:]
    added = 0
    for line in lines:
        if line.strip():
            query_db("INSERT INTO verses (content) VALUES (?)", (line.strip(),), commit=True)
            added += 1
    await message.reply(f"✅ {added} verses added!")

@dp.message(Command("edquiz"))
async def ed_quiz(message: Message):
    if not is_admin(message.from_user.id): return
    try:
        data = message.text.replace("/edquiz", "").strip().split("|")
        # Format: Question | A | B | C | D | CorrectLetter
        query_db("INSERT INTO quizzes (question, a, b, c, d, correct) VALUES (?, ?, ?, ?, ?, ?)", 
                 (data[0].strip(), data[1].strip(), data[2].strip(), data[3].strip(), data[4].strip(), data[5].strip().upper()), commit=True)
        await message.reply("✅ Quiz added!")
    except:
        await message.reply("❌ Format: `/edquiz Question | A | B | C | D | A`", parse_mode="Markdown")

@dp.message(Command("pray"))
async def pray_user(message: Message):
    content = message.text.replace("/pray", "").strip()
    if not content: 
        return await message.reply("အသုံးပြုပုံ- `/pray [စာ]`", parse_mode="Markdown")
    query_db("INSERT INTO prayers (user_name, user_id, content, date) VALUES (?, ?, ?, ?)",
             (message.from_user.full_name, message.from_user.id, content, datetime.now().strftime("%d/%m/%Y")), commit=True)
    await message.answer("🙏 ဆုတောင်းစာ ပေးပို့ပြီးပါပြီ။")

@dp.message(Command("praylist"))
async def pray_list(message: Message):
    if not is_admin(message.from_user.id): return
    prayers = query_db("SELECT user_name, content, date FROM prayers ORDER BY id DESC LIMIT 10")
    text = "📝 *Recent Prayer Requests*\n\n"
    for p in prayers:
        text += f"👤 *{p[0]}* ({p[2]}): {p[1]}\n\n"
    await message.answer(text if prayers else "စာရင်းမရှိပါ။", parse_mode="Markdown")

@dp.message(Command("broadcast"))
async def broadcast(message: Message):
    if not is_admin(message.from_user.id): return
    if not message.reply_to_message:
        return await message.reply("Broadcast လုပ်မည့်စာ/ပုံကို Reply ပြန်ပါ။")
    
    users = query_db("SELECT user_id FROM members")
    count = 0
    for u in users:
        try:
            await bot.copy_message(u[0], message.chat.id, message.reply_to_message.message_id)
            count += 1
            await asyncio.sleep(0.05) # Flood limit ရှောင်ရန်
        except TelegramForbiddenError:
            continue # Bot ကို block ထားသူများကိုကျော်သွားမည်
        except Exception:
            continue
    await message.answer(f"📢 ပို့ပြီးသည့်လူဦးရေ: {count}")

@dp.message(Command("stats"))
async def show_stats(message: Message):
    if not is_admin(message.from_user.id): return
    u_count = query_db("SELECT COUNT(*) FROM members", fetchone=True)[0]
    p_count = query_db("SELECT COUNT(*) FROM prayers", fetchone=True)[0]
    await message.answer(f"📊 *Statistics*\nTotal Users: {u_count}\nPrayers: {p_count}", parse_mode="Markdown")

@dp.message(Command("backup"))
async def db_backup(message: Message):
    if not is_admin(message.from_user.id): return
    if os.path.exists('church_plus.db'):
        db_file = FSInputFile("church_plus.db")
        await message.answer_document(db_file, caption="Database Backup")
    else:
        await message.answer("Database file not found!")

@dp.message(Command("allclear"))
async def clear_data(message: Message):
    if not is_admin(message.from_user.id): return
    query_db("DELETE FROM prayers", commit=True)
    query_db("DELETE FROM verses", commit=True)
    query_db("DELETE FROM quizzes", commit=True)
    await message.answer("🗑 ဒေတာများအားလုံး ရှင်းလင်းပြီးပါပြီ။")

async def main():
    init_db()
    logger.info("Bot is starting...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped!")
