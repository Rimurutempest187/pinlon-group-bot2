import logging
import asyncio
import sqlite3
import os
import shutil
from datetime import datetime
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile

# Load environment variables
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

# Initialize Bot and Dispatcher
bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- Database Setup ---
def init_db():
    conn = sqlite3.connect("church_bot.db")
    cursor = conn.cursor()
    # General Settings
    cursor.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
    # Verses
    cursor.execute("CREATE TABLE IF NOT EXISTS verses (id INTEGER PRIMARY KEY, content TEXT)")
    # Birthdays
    cursor.execute("CREATE TABLE IF NOT EXISTS birthdays (id INTEGER PRIMARY KEY, name TEXT, month INTEGER)")
    # Prayers
    cursor.execute("CREATE TABLE IF NOT EXISTS prayers (id INTEGER PRIMARY KEY, username TEXT, request TEXT, date TEXT)")
    # Quizzes
    cursor.execute("CREATE TABLE IF NOT EXISTS quizzes (id INTEGER PRIMARY KEY, question TEXT, a TEXT, b TEXT, c TEXT, d TEXT, answer TEXT)")
    # Scores
    cursor.execute("CREATE TABLE IF NOT EXISTS scores (user_id INTEGER PRIMARY KEY, name TEXT, points INTEGER DEFAULT 0)")
    # Stats
    cursor.execute("CREATE TABLE IF NOT EXISTS stats (chat_id INTEGER PRIMARY KEY, type TEXT)")
    
    # Default values
    defaults = [('about', 'History not set.'), ('contact', 'Contacts not set.'), ('events', 'No upcoming events.')]
    cursor.executemany("INSERT OR IGNORE INTO settings VALUES (?, ?)", defaults)
    
    conn.commit()
    conn.close()

def get_setting(key):
    conn = sqlite3.connect("church_bot.db")
    val = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()[0]
    conn.close()
    return val

def log_chat(chat_id, chat_type):
    conn = sqlite3.connect("church_bot.db")
    conn.execute("INSERT OR IGNORE INTO stats (chat_id, type) VALUES (?, ?)", (chat_id, chat_type))
    conn.commit()
    conn.close()

# --- User Commands ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    log_chat(message.chat.id, message.chat.type)
    welcome = (
        "🙏 မင်္ဂလာပါ! Church Community Bot မှ ကြိုဆိုပါတယ်။\n\n"
        "ဝိညာဉ်ရေးရာခွန်အားနှင့် အသင်းတော်သတင်းအချက်အလက်များအတွက် အသုံးပြုနိုင်ပါသည်။\n\n"
        "ဖန်တီးသူ : @Enoch_777"
    )
    await message.answer(welcome)

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    help_text = (
        "📖 **အသုံးပြုပုံ လမ်းညွှန်**\n\n"
        "/about - အသင်းတော်အကြောင်း\n"
        "/contact - ဆက်သွယ်ရန်\n"
        "/verse - နှုတ်ကပတ်တော်များ\n"
        "/events - အစီအစဉ်များ\n"
        "/birthday - ယခုလမွေးနေ့ရှင်များ\n"
        "/pray - ဆုတောင်းချက်ပေးပို့ရန်\n"
        "/quiz - ကျမ်းစာဉာဏ်စမ်း\n"
        "/tops - ရမှတ်အများဆုံးစာရင်း\n"
        "/report - သတင်းပေးပို့ရန်"
    )
    await message.answer(help_text, parse_mode="Markdown")

@dp.message(Command("about"))
async def cmd_about(message: types.Message):
    await message.answer(f"ℹ️ **About Us**\n\n{get_setting('about')}", parse_mode="Markdown")

@dp.message(Command("contact"))
async def cmd_contact(message: types.Message):
    await message.answer(f"📞 **Contact Leaders**\n\n{get_setting('contact')}", parse_mode="Markdown")

@dp.message(Command("events"))
async def cmd_events(message: types.Message):
    await message.answer(f"📅 **Upcoming Events**\n\n{get_setting('events')}", parse_mode="Markdown")

@dp.message(Command("verse"))
async def cmd_verse(message: types.Message):
    conn = sqlite3.connect("church_bot.db")
    verse = conn.execute("SELECT content FROM verses ORDER BY RANDOM() LIMIT 1").fetchone()
    conn.close()
    if verse:
        await message.answer(f"📖 **Today's Verse**\n\n{verse[0]}", parse_mode="Markdown")
    else:
        await message.answer("ကျမ်းချက်များ မရှိသေးပါ။")

@dp.message(Command("birthday"))
async def cmd_birthday(message: types.Message):
    this_month = datetime.now().month
    conn = sqlite3.connect("church_bot.db")
    members = conn.execute("SELECT name FROM birthdays WHERE month=?", (this_month,)).fetchall()
    conn.close()
    if members:
        list_str = "\n".join([f"🎂 {m[0]}" for m in members])
        await message.answer(f"🎉 **ယခုလ မွေးနေ့ရှင်များ**\n\n{list_str}")
    else:
        await message.answer("ယခုလတွင် မွေးနေ့ရှိသူ မရှိပါ။")

@dp.message(Command("pray"))
async def cmd_pray(message: types.Message):
    text = message.text.replace("/pray", "").strip()
    if not text:
        return await message.answer("ကျေးဇူးပြု၍ `/pray <ဆုတောင်းချက်>` ဟု ရေးပေးပါ။")
    
    conn = sqlite3.connect("church_bot.db")
    conn.execute("INSERT INTO prayers (username, request, date) VALUES (?, ?, ?)", 
                 (f"@{message.from_user.username}", text, datetime.now().strftime("%Y-%m-%d")))
    conn.commit()
    conn.close()
    await message.answer("🙏 သင်၏ ဆုတောင်းချက်ကို မှတ်တမ်းတင်ပြီးပါပြီ။")

@dp.message(Command("quiz"))
async def cmd_quiz(message: types.Message):
    conn = sqlite3.connect("church_bot.db")
    q = conn.execute("SELECT id, question, a, b, c, d FROM quizzes ORDER BY RANDOM() LIMIT 1").fetchone()
    conn.close()
    if not q:
        return await message.answer("ဉာဏ်စမ်းများ မရှိသေးပါ။")
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"A: {q[2]}", callback_data=f"q_{q[0]}_a")],
        [InlineKeyboardButton(text=f"B: {q[3]}", callback_data=f"q_{q[0]}_b")],
        [InlineKeyboardButton(text=f"C: {q[4]}", callback_data=f"q_{q[0]}_c")],
        [InlineKeyboardButton(text=f"D: {q[5]}", callback_data=f"q_{q[0]}_d")]
    ])
    await message.answer(f"❓ {q[1]}", reply_markup=kb)

@dp.callback_query(F.data.startswith("q_"))
async def handle_quiz_answer(callback: types.CallbackQuery):
    _, q_id, user_ans = callback.data.split("_")
    conn = sqlite3.connect("church_bot.db")
    correct_ans = conn.execute("SELECT answer FROM quizzes WHERE id=?", (q_id,)).fetchone()[0]
    
    if user_ans.upper() == correct_ans.upper():
        conn.execute("INSERT INTO scores (user_id, name, points) VALUES (?, ?, 1) ON CONFLICT(user_id) DO UPDATE SET points=points+1", 
                     (callback.from_user.id, callback.from_user.full_name))
        conn.commit()
        await callback.answer("✅ မှန်ကန်ပါတယ်! +1 မှတ်", show_alert=True)
    else:
        await callback.answer(f"❌ မှားယွင်းပါတယ်။ အဖြေမှန်မှာ {correct_ans.upper()} ဖြစ်ပါတယ်။", show_alert=True)
    conn.close()
    await callback.message.delete()

@dp.message(Command("tops"))
async def cmd_tops(message: types.Message):
    conn = sqlite3.connect("church_bot.db")
    ranks = conn.execute("SELECT name, points FROM scores ORDER BY points DESC LIMIT 10").fetchall()
    conn.close()
    if ranks:
        res = "\n".join([f"{i+1}. {r[0]} - {r[1]} pts" for i, r in enumerate(ranks)])
        await message.answer(f"🏆 **Quiz Ranking**\n\n{res}")
    else:
        await message.answer("ရမှတ်စာရင်း မရှိသေးပါ။")

# --- Admin Commands ---

def is_admin(user_id):
    return user_id == ADMIN_ID

@dp.message(Command("edabout"))
async def ed_about(message: types.Message):
    if not is_admin(message.from_user.id): return
    text = message.text.replace("/edabout", "").strip()
    if text:
        conn = sqlite3.connect("church_bot.db")
        conn.execute("UPDATE settings SET value=? WHERE key='about'", (text,))
        conn.commit() ; conn.close()
        await message.answer("✅ About update အောင်မြင်သည်။")

@dp.message(Command("edcontact"))
async def ed_contact(message: types.Message):
    if not is_admin(message.from_user.id): return
    text = message.text.replace("/edcontact", "").strip()
    if text:
        conn = sqlite3.connect("church_bot.db")
        conn.execute("UPDATE settings SET value=? WHERE key='contact'", (text,))
        conn.commit() ; conn.close()
        await message.answer("✅ Contact update အောင်မြင်သည်။")

@dp.message(Command("edevents"))
async def ed_events(message: types.Message):
    if not is_admin(message.from_user.id): return
    text = message.text.replace("/edevents", "").strip()
    if text:
        conn = sqlite3.connect("church_bot.db")
        conn.execute("UPDATE settings SET value=? WHERE key='events'", (text,))
        conn.commit() ; conn.close()
        await message.answer("✅ Events update အောင်မြင်သည်။")

@dp.message(Command("edverse"))
async def ed_verse(message: types.Message):
    if not is_admin(message.from_user.id): return
    # Usage: /edverse Verse text here (One per line for multiple)
    lines = message.text.replace("/edverse", "").strip().split("\n")
    if lines:
        conn = sqlite3.connect("church_bot.db")
        for line in lines:
            if line.strip(): conn.execute("INSERT INTO verses (content) VALUES (?)", (line.strip(),))
        conn.commit() ; conn.close()
        await message.answer(f"✅ Verses {len(lines)} ခု ထည့်ပြီးပါပြီ။")

@dp.message(Command("edbirthday"))
async def ed_birthday(message: types.Message):
    if not is_admin(message.from_user.id): return
    # Usage: /edbirthday Name|Month_Number
    data = message.text.replace("/edbirthday", "").strip().split("|")
    if len(data) == 2:
        conn = sqlite3.connect("church_bot.db")
        conn.execute("INSERT INTO birthdays (name, month) VALUES (?, ?)", (data[0].strip(), int(data[1].strip())))
        conn.commit() ; conn.close()
        await message.answer("✅ Birthday list ထည့်ပြီးပါပြီ။")

@dp.message(Command("edquiz"))
async def ed_quiz(message: types.Message):
    if not is_admin(message.from_user.id): return
    # Usage: /edquiz Question|A|B|C|D|CorrectLetter
    data = message.text.replace("/edquiz", "").strip().split("|")
    if len(data) == 6:
        conn = sqlite3.connect("church_bot.db")
        conn.execute("INSERT INTO quizzes (question, a, b, c, d, answer) VALUES (?,?,?,?,?,?)", 
                     (data[0], data[1], data[2], data[3], data[4], data[5]))
        conn.commit() ; conn.close()
        await message.answer("✅ Quiz ထည့်ပြီးပါပြီ။")

@dp.message(Command("praylist"))
async def cmd_praylist(message: types.Message):
    if not is_admin(message.from_user.id): return
    conn = sqlite3.connect("church_bot.db")
    prays = conn.execute("SELECT username, request, date FROM prayers ORDER BY id DESC LIMIT 20").fetchall()
    conn.close()
    if prays:
        res = "\n---\n".join([f"👤 {p[0]} ({p[2]}):\n{p[1]}" for p in prays])
        await message.answer(f"🙏 **Recent Prayer Requests**\n\n{res}")
    else:
        await message.answer("ဆုတောင်းချက် မရှိသေးပါ။")

@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    if not is_admin(message.from_user.id): return
    conn = sqlite3.connect("church_bot.db")
    users = conn.execute("SELECT COUNT(*) FROM stats WHERE type='private'").fetchone()[0]
    groups = conn.execute("SELECT COUNT(*) FROM stats WHERE type IN ('group', 'supergroup')").fetchone()[0]
    conn.close()
    await message.answer(f"📊 **Bot Statistics**\n\nUsers: {users}\nGroups: {groups}")

@dp.message(Command("broadcast"))
async def cmd_broadcast(message: types.Message):
    if not is_admin(message.from_user.id): return
    
    conn = sqlite3.connect("church_bot.db")
    chats = conn.execute("SELECT chat_id FROM stats WHERE type IN ('group', 'supergroup')").fetchall()
    conn.close()
    
    count = 0
    msg_text = message.caption if message.photo else message.text.replace("/broadcast", "").strip()
    
    for chat in chats:
        try:
            if message.photo:
                await bot.send_photo(chat[0], message.photo[-1].file_id, caption=msg_text)
            else:
                await bot.send_message(chat[0], msg_text)
            count += 1
            await asyncio.sleep(0.1) # Prevent flooding
        except:
            continue
    await message.answer(f"📢 Broadcast ပို့လွှတ်မှုပြီးဆုံး (Groups: {count})")

@dp.message(Command("backup"))
async def cmd_backup(message: types.Message):
    if not is_admin(message.from_user.id): return
    shutil.copyfile("church_bot.db", "backup_church.db")
    file = FSInputFile("backup_church.db")
    await message.answer_document(file, caption="Database Backup Success.")

@dp.message(Command("restore"))
async def cmd_restore(message: types.Message, bot: Bot):
    if not is_admin(message.from_user.id): return
    if not message.document:
        return await message.answer("Database ဖိုင်ကို upload တင်ပြီး /restore ဟု caption ရေးပေးပါ။")
    
    await bot.download(message.document, destination="church_bot.db")
    await message.answer("✅ Data restored successfully.")

@dp.message(Command("allclear"))
async def cmd_clear(message: types.Message):
    if not is_admin(message.from_user.id): return
    conn = sqlite3.connect("church_bot.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM verses")
    cursor.execute("DELETE FROM prayers")
    cursor.execute("DELETE FROM quizzes")
    cursor.execute("DELETE FROM scores")
    conn.commit() ; conn.close()
    await message.answer("⚠️ All Data Cleared (except settings and stats).")

@dp.message(Command("report"))
async def cmd_report(message: types.Message):
    text = message.text.replace("/report", "").strip()
    if text:
        await bot.send_message(ADMIN_ID, f"🚩 **New Report from {message.from_user.full_name}**:\n\n{text}")
        await message.answer("ကျေးဇူးတင်ပါတယ်။ သတင်းပို့ချက်ကို Admin ထံ ပေးပို့လိုက်ပါပြီ။")

# --- Startup ---
async def main():
    init_db()
    logging.basicConfig(level=logging.INFO)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
