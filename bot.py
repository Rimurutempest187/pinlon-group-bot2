
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Church Community Telegram Bot — Ready to run (python-telegram-bot v20+)
Features: admin/user command separation, sqlite persistence, verses, events, birthdays, prayers,
quizzes + leaderboard, broadcast, backup/restore, stats, reports.
Create by : @Enoch_777
"""

import os
import sqlite3
import logging
import tempfile
import random
from datetime import datetime
from functools import wraps
from typing import Optional, Tuple, Dict

from dotenv import load_dotenv
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    ChatAction,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ----------------- CONFIG & LOGGING -----------------
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
ADMINS = os.getenv("ADMIN_IDS", "").split(",") if os.getenv("ADMIN_IDS") else []
DB_PATH = os.getenv("DB_PATH", "church_bot.db")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ----------------- DB HELPERS -----------------

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cur = conn.cursor()
    # users: store known users
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        last_name TEXT,
        added_at TEXT
    )
    """)

    # groups: store known groups (chat_id, title)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS groups (
        chat_id INTEGER PRIMARY KEY,
        title TEXT,
        added_at TEXT
    )
    """)

    # about
    cur.execute("""
    CREATE TABLE IF NOT EXISTS about (
        id INTEGER PRIMARY KEY CHECK (id=1),
        text TEXT
    )
    """)

    # contacts
    cur.execute("""
    CREATE TABLE IF NOT EXISTS contacts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        phone TEXT
    )
    """)

    # verses
    cur.execute("""
    CREATE TABLE IF NOT EXISTS verses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        text TEXT
    )
    """)

    # events
    cur.execute("""
    CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        details TEXT,
        when_where TEXT
    )
    """)

    # birthday
    cur.execute("""
    CREATE TABLE IF NOT EXISTS birthdays (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        day INTEGER,
        month INTEGER
    )
    """)

    # prayers
    cur.execute("""
    CREATE TABLE IF NOT EXISTS prayers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        username TEXT,
        text TEXT,
        created_at TEXT
    )
    """)

    # quiz
    cur.execute("""
    CREATE TABLE IF NOT EXISTS quizzes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        question TEXT,
        option_a TEXT,
        option_b TEXT,
        option_c TEXT,
        option_d TEXT,
        answer CHAR(1)
    )
    """)

    # quiz scores
    cur.execute("""
    CREATE TABLE IF NOT EXISTS quiz_scores (
        user_id INTEGER,
        username TEXT,
        score INTEGER DEFAULT 0,
        PRIMARY KEY (user_id)
    )
    """)

    # reports
    cur.execute("""
    CREATE TABLE IF NOT EXISTS reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        username TEXT,
        text TEXT,
        created_at TEXT
    )
    """)

    conn.commit()
    conn.close()


init_db()

# ----------------- UTILITIES -----------------

def is_admin(user_id: int) -> bool:
    return str(user_id) in [x.strip() for x in ADMINS if x]


def admin_only(func):
    @wraps(func)
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user = update.effective_user
        if user is None or not is_admin(user.id):
            await update.message.reply_text("⛔ မင်းမှာ admin အခွင့်အရေး မရှိပါ။")
            return
        return await func(update, context, *args, **kwargs)

    return wrapped


async def save_user_if_not_exists(user) -> None:
    if user is None:
        return
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM users WHERE user_id=?", (user.id,))
    if not cur.fetchone():
        cur.execute(
            "INSERT INTO users (user_id, username, first_name, last_name, added_at) VALUES (?, ?, ?, ?, ?)",
            (user.id, user.username or "", user.first_name or "", user.last_name or "", datetime.utcnow().isoformat()),
        )
        conn.commit()
    conn.close()


async def save_group_if_not_exists(chat) -> None:
    if chat is None:
        return
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM groups WHERE chat_id=?", (chat.id,))
    if not cur.fetchone():
        cur.execute(
            "INSERT INTO groups (chat_id, title, added_at) VALUES (?, ?, ?)",
            (chat.id, chat.title or "", datetime.utcnow().isoformat()),
        )
        conn.commit()
    conn.close()


# ----------------- COMMAND HANDLERS -----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await save_user_if_not_exists(user)
    chat = update.effective_chat
    await save_group_if_not_exists(chat)

    text = (
        f"မင်္ဂလာပါ {user.first_name if user else ''}!\n\n"
        "Church Community Bot သို့ ရောက်ရှိလာကြသည့်အတွက် ကြိုဆိုပါတယ်။\n"
        "သင့်အသုံးပြုမှုအတွက် အောက်ပါ command များကို အသုံးပြုနိုင်ပါသည်။\n\n"
        "/help - အသုံးပြုနည်းလမ်းညွှန်\n"
        "/about - အသင်းတော်/အဖွဲ့ ရည်ရွယ်ချက်\n"
        "/verse - ယနေ့အတွက် ကောင်းသော စာတွေ (random)\n"
        "/events - လာမည့် အစီအစဉ်များ\n"
        "/birthday - ယခုလအတွင်း မွေးနေ့များ\n"
        "/pray - ဆုတောင်းပေးစေလိုသည့်အချက်များ\n"
        "/quiz - စိတ်ဝင်စားစရာမေးခွန်း (A/B/C/D)\n\n"
        "Create by : @Enoch_777"
    )
    # send
    await update.message.reply_text(text)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "/start — စတင်အသုံးပြုပြီး အချက်အလက်ယူရန်\n"
        "/help — ဒီလမ်းညွှန်ကို ပြရန်\n"
        "/about — အသင်းရဲ့ ရည်ရွယ်ချက်ကြည့်ရန်\n"
        "/verse — Random Bible verses\n"
        "/events — ကြှနျတော့်အဖွဲ့ အစီအစဉ်များ\n"
        "/birthday — ယခုလ မွေးနေ့များစာရင်း\n"
        "/pray <text> — ဆုတောင်းပို့ရန်\n"
        "/praylist — ဆုတောင်း စာရင်းကြည့်ရန်\n"
        "/quiz — Quiz ဆိုပြီး လေ့ကျင့်ရန်\n"
        "/report <text> — တင်ပြရန်\n"
        "(Admins: /edabout, /edverse, /edevents, /edbirthday, /edcontact, /edquiz, /broadcast, /stats, /backup, /restore, /allclear)"
    )
    await update.message.reply_text(text)


# About & edit
async def about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT text FROM about WHERE id=1")
    row = cur.fetchone()
    conn.close()
    if row and row[0]:
        await update.message.reply_text(row[0])
    else:
        await update.message.reply_text("သတင်းအချက်အလက် မရှိသေးပါ — admin သည် /edabout ဖြင့် သတ်မှတ်နိုင်သည်။")


@admin_only
async def edabout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # admin can run /edabout This is followed by the new about text
    args = context.args
    new_text = " ".join(args).strip() if args else None
    if not new_text and update.message.reply_to_message:
        new_text = update.message.reply_to_message.text
    if not new_text:
        await update.message.reply_text("အသုံးပြုခြင်း: /edabout <new about text> OR reply to a message and run /edabout")
        return
    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT OR REPLACE INTO about (id, text) VALUES (1, ?)", (new_text,))
    conn.commit()
    conn.close()
    await update.message.reply_text("✅ About ကို update ပြီးပါပြီ။")


# Contacts
async def contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT name, phone FROM contacts ORDER BY name")
    rows = cur.fetchall()
    conn.close()
    if not rows:
        await update.message.reply_text("Contacts မရှိသေးပါ။ Admin သည် /edcontact ဖြင့် ဖြည့်စွက်နိုင်သည်။")
        return
    lines = [f"{r[0]} — {r[1]}" for r in rows]
    await update.message.reply_text("\n".join(lines))


@admin_only
async def edcontact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # usage: /edcontact Name|Phone (multiple lines allowed by replying to message)
    text = None
    if context.args:
        text = " ".join(context.args)
    elif update.message.reply_to_message:
        text = update.message.reply_to_message.text
    if not text:
        await update.message.reply_text("Usage: /edcontact Name|Phone  OR reply to a message with lines: Name|Phone")
        return
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    conn = get_db()
    cur = conn.cursor()
    for line in lines:
        if "|" in line:
            name, phone = [p.strip() for p in line.split("|", 1)]
            cur.execute("INSERT INTO contacts (name, phone) VALUES (?, ?)", (name, phone))
    conn.commit()
    conn.close()
    await update.message.reply_text("✅ Contacts ထည့်သွင်းပြီးပါပြီ။")


# Verses
async def verse(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, text FROM verses")
    rows = cur.fetchall()
    conn.close()
    if not rows:
        await update.message.reply_text("Verses မရှိသေးပါ — admin သည် /edverse ဖြင့် ထည့်နိုင်ပါသည်။")
        return
    chosen = random.choice(rows)
    await update.message.reply_text(chosen[1])


@admin_only
async def edverse(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = None
    if update.message.reply_to_message:
        text = update.message.reply_to_message.text
    elif context.args:
        text = " ".join(context.args)
    if not text:
        await update.message.reply_text("Usage: /edverse <verse text> OR reply to a message with multiple verses (one per line)")
        return
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    conn = get_db()
    cur = conn.cursor()
    for l in lines:
        cur.execute("INSERT INTO verses (text) VALUES (?)", (l,))
    conn.commit()
    conn.close()
    await update.message.reply_text(f"✅ {len(lines)} verse(s) ထည့်သွင်းပြီးပါပြီ။")


# Events
async def events(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT title, when_where, details FROM events ORDER BY id DESC")
    rows = cur.fetchall()
    conn.close()
    if not rows:
        await update.message.reply_text("Events မရှိသေးပါ — admin သည် /edevents ဖြင့် ထည့်နိုင်သည်။")
        return
    lines = [f"{r[0]} — {r[1]}\n{r[2]}" for r in rows]
    await update.message.reply_text("\n\n".join(lines))


@admin_only
async def edevents(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # usage: /edevents Title|When & Where|Details (or reply to a message with several lines)
    text = None
    if update.message.reply_to_message:
        text = update.message.reply_to_message.text
    elif context.args:
        text = " ".join(context.args)
    if not text:
        await update.message.reply_text("Usage: /edevents Title|When & Where|Details  (multiple lines allowed)")
        return
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    conn = get_db()
    cur = conn.cursor()
    count = 0
    for l in lines:
        if "|" in l:
            title, whenwhere, details = [p.strip() for p in l.split("|", 2)]
            cur.execute("INSERT INTO events (title, when_where, details) VALUES (?, ?, ?)", (title, whenwhere, details))
            count += 1
    conn.commit()
    conn.close()
    await update.message.reply_text(f"✅ {count} event(s) ထည့်သွင်းပြီးပါပြီ။")


# Birthdays
async def birthday(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # show birthdays in current month
    now = datetime.utcnow()
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT name, day FROM birthdays WHERE month=? ORDER BY day", (now.month,))
    rows = cur.fetchall()
    conn.close()
    if not rows:
        await update.message.reply_text("ယခုလတွင် မွေးနေ့ရှိသူ မရှိသေးပါ။")
        return
    lines = [f"{r[0]} — {r[1]}" for r in rows]
    await update.message.reply_text("\n".join(lines))


@admin_only
async def edbirthday(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # usage: /edbirthday Name|DD|MM (or many lines)
    text = None
    if update.message.reply_to_message:
        text = update.message.reply_to_message.text
    elif context.args:
        text = " ".join(context.args)
    if not text:
        await update.message.reply_text("Usage: reply to message or /edbirthday Name|DD|MM (one per line)")
        return
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    conn = get_db()
    cur = conn.cursor()
    count = 0
    for l in lines:
        parts = [p.strip() for p in l.split("|")]
        if len(parts) >= 3:
            name, d, m = parts[0], int(parts[1]), int(parts[2])
            cur.execute("INSERT INTO birthdays (name, day, month) VALUES (?, ?, ?)", (name, d, m))
            count += 1
    conn.commit()
    conn.close()
    await update.message.reply_text(f"✅ {count} birthday(s) ထည့်သွင်းပြီးပါပြီ။")


# Prayers
async def pray(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = None
    if context.args:
        text = " ".join(context.args)
    elif update.message.reply_to_message:
        text = update.message.reply_to_message.text
    if not text:
        await update.message.reply_text("Usage: /pray <your prayer request text>")
        return
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO prayers (user_id, username, text, created_at) VALUES (?, ?, ?, ?)",
        (user.id, user.username or "", text, datetime.utcnow().isoformat()),
    )
    conn.commit()
    conn.close()
    await update.message.reply_text("🙏 သင့်ဆုတောင်းပေးမှုကို မှတ်တမ်းတင်ပြီးပါပြီ။")


async def praylist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT username, text, created_at FROM prayers ORDER BY id DESC")
    rows = cur.fetchall()
    conn.close()
    if not rows:
        await update.message.reply_text("ဆုတောင်းများ မရှိသေးပါ။")
        return
    lines = [f"@{r[0]} — {r[1]}" if r[0] else f"User — {r[1]}" for r in rows[:50]]
    await update.message.reply_text("\n\n".join(lines))


# Quiz
async def quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, question, option_a, option_b, option_c, option_d FROM quizzes")
    rows = cur.fetchall()
    conn.close()
    if not rows:
        await update.message.reply_text("Quiz မရှိသေးပါ — admin သည် /edquiz ဖြင့် ထည့်နိုင်သည်။")
        return
    chosen = random.choice(rows)
    qid = chosen[0]
    buttons = [
        [InlineKeyboardButton("A", callback_data=f"quiz|{qid}|A"), InlineKeyboardButton("B", callback_data=f"quiz|{qid}|B")],
        [InlineKeyboardButton("C", callback_data=f"quiz|{qid}|C"), InlineKeyboardButton("D", callback_data=f"quiz|{qid}|D")],
    ]
    kb = InlineKeyboardMarkup(buttons)
    text = f"{chosen[1]}\n\nA) {chosen[2]}\nB) {chosen[3]}\nC) {chosen[4]}\nD) {chosen[5]}"
    await update.message.reply_text(text, reply_markup=kb)


@admin_only
async def edquiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # usage: reply or /edquiz Question|A|B|C|D|AnswerLetter
    text = None
    if update.message.reply_to_message:
        text = update.message.reply_to_message.text
    elif context.args:
        text = " ".join(context.args)
    if not text:
        await update.message.reply_text("Usage: /edquiz Question|A|B|C|D|Answer")
        return
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    conn = get_db()
    cur = conn.cursor()
    count = 0
    for l in lines:
        parts = [p.strip() for p in l.split("|")]
        if len(parts) >= 6:
            question, a, b, c, d, ans = parts[0], parts[1], parts[2], parts[3], parts[4], parts[5].upper()
            if ans not in ("A", "B", "C", "D"):
                continue
            cur.execute(
                "INSERT INTO quizzes (question, option_a, option_b, option_c, option_d, answer) VALUES (?, ?, ?, ?, ?, ?)",
                (question, a, b, c, d, ans),
            )
            count += 1
    conn.commit()
    conn.close()
    await update.message.reply_text(f"✅ {count} quiz(es) ထည့်သွင်းပြီးပါပြီ။")


async def quiz_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data  # format: quiz|{id}|{choice}
    parts = data.split("|")
    if len(parts) != 3:
        await query.edit_message_text("Invalid callback data")
        return
    _, qid, choice = parts[0], int(parts[1]), parts[2]
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT answer, question FROM quizzes WHERE id=?", (qid,))
    row = cur.fetchone()
    if not row:
        await query.edit_message_text("Question not found.")
        conn.close()
        return
    correct = row[0]
    question_text = row[1]
    user = query.from_user
    username = user.username or f"{user.first_name or ''}"
    if choice == correct:
        # increment user's score
        cur.execute("INSERT OR IGNORE INTO quiz_scores (user_id, username, score) VALUES (?, ?, 0)", (user.id, username))
        cur.execute("UPDATE quiz_scores SET score = score + 1 WHERE user_id=?", (user.id,))
        conn.commit()
        await query.edit_message_text(f"✅ သင်၏ဖြေထားသည့် အဖြေ မှန်ပါသည်!\n\n{question_text}\nYour answer: {choice}")
    else:
        await query.edit_message_text(f"❌ အဖြေ မမှန်ပါ။\n\n{question_text}\nYour answer: {choice}\nCorrect: {correct}")
    conn.close()


async def tops(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT username, score FROM quiz_scores ORDER BY score DESC LIMIT 10")
    rows = cur.fetchall()
    conn.close()
    if not rows:
        await update.message.reply_text("No quiz scores yet.")
        return
    lines = [f"{i+1}. @{r[0]} — {r[1]}" for i, r in enumerate(rows)]
    await update.message.reply_text("Top Quiz Scores:\n" + "\n".join(lines))


# Broadcast
@admin_only
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Usage: /broadcast <text> (send to saved groups)
    # or reply to message and run /broadcast to send that message content
    text = None
    photo = None
    reply = update.message.reply_to_message
    if reply:
        # forward the replied message instead of creating new text
        text = reply.text
        if reply.photo:
            photo = reply.photo[-1]
    elif context.args:
        text = " ".join(context.args)
    else:
        await update.message.reply_text("Usage: reply to a message and run /broadcast OR /broadcast Your message text")
        return

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT chat_id FROM groups")
    groups = [r[0] for r in cur.fetchall()]
    conn.close()

    sent = 0
    failed = 0
    for chat_id in groups:
        try:
            if photo:
                await context.bot.send_photo(chat_id=chat_id, photo=photo.file_id, caption=text or "")
            else:
                await context.bot.send_message(chat_id=chat_id, text=text or "")
            sent += 1
        except Exception as e:
            logger.warning("Failed to send to %s: %s", chat_id, e)
            failed += 1
    await update.message.reply_text(f"Broadcast finished. sent: {sent}, failed: {failed}")


# Stats
@admin_only
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM users")
    users = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM groups")
    groups = cur.fetchone()[0]
    conn.close()
    await update.message.reply_text(f"Users: {users}\nGroups: {groups}")


# Reports
async def report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = None
    if context.args:
        text = " ".join(context.args)
    elif update.message.reply_to_message:
        text = update.message.reply_to_message.text
    if not text:
        await update.message.reply_text("Usage: /report <text> OR reply to a message and run /report")
        return
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO reports (user_id, username, text, created_at) VALUES (?, ?, ?, ?)",
        (user.id, user.username or "", text, datetime.utcnow().isoformat()),
    )
    conn.commit()
    conn.close()
    await update.message.reply_text("✅ သင့် report ကို မှတ်တမ်းတင်ပြီး admin များသို့ အကြောင်းကြားထားပါသည်။")


# Backup & Restore
@admin_only
async def backup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # send the sqlite db file to admin
    if not os.path.exists(DB_PATH):
        await update.message.reply_text("Database file not found")
        return
    await update.message.reply_document(document=open(DB_PATH, "rb"))


@admin_only
async def restore(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Admin should reply to an uploaded db file with /restore
    if not update.message.reply_to_message or not update.message.reply_to_message.document:
        await update.message.reply_text("Reply to a .db/.sqlite file and run /restore")
        return
    doc = update.message.reply_to_message.document
    tmpfd, tmpfname = tempfile.mkstemp(suffix=".db")
    await doc.get_file().download_to_drive(custom_path=tmpfname)
    # simple replace (backup old file)
    if os.path.exists(DB_PATH):
        bak = DB_PATH + ".bak"
        os.replace(DB_PATH, bak)
    os.replace(tmpfname, DB_PATH)
    await update.message.reply_text("✅ Database restored. Please /stats to verify.")


# Allclear
@admin_only
async def allclear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Danger: clear all user-facing data but keep schema
    conn = get_db()
    cur = conn.cursor()
    tables = [
        "users",
        "groups",
        "contacts",
        "verses",
        "events",
        "birthdays",
        "prayers",
        "quizzes",
        "quiz_scores",
        "reports",
    ]
    for t in tables:
        cur.execute(f"DELETE FROM {t}")
    conn.commit()
    conn.close()
    await update.message.reply_text("✅ All data cleared (schema intact).")


# Catch chat updates to save groups/users automatically
async def on_message_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # save user and group for known chats
    user = update.effective_user
    chat = update.effective_chat
    await save_user_if_not_exists(user)
    await save_group_if_not_exists(chat)
    # allow other handlers to process


# Helper to show help on unknown commands
async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Command မသိပါ — /help ကို နှိပ်ပြီး ကြည့်ပါ။")


# ----------------- MAIN -----------------

def main() -> None:
    if TOKEN is None:
        print("Error: BOT_TOKEN is not set in .env file")
        return
    app = ApplicationBuilder().token(TOKEN).concurrent_updates(True).build()

    # basic commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))

    # about
    app.add_handler(CommandHandler("about", about))
    app.add_handler(CommandHandler("edabout", edabout))

    # contacts
    app.add_handler(CommandHandler("contact", contact))
    app.add_handler(CommandHandler("edcontact", edcontact))

    # verses
    app.add_handler(CommandHandler("verse", verse))
    app.add_handler(CommandHandler("edverse", edverse))

    # events
    app.add_handler(CommandHandler("events", events))
    app.add_handler(CommandHandler("edevents", edevents))

    # birthday
    app.add_handler(CommandHandler("birthday", birthday))
    app.add_handler(CommandHandler("edbirthday", edbirthday))

    # pray
    app.add_handler(CommandHandler("pray", pray))
    app.add_handler(CommandHandler("praylist", praylist))

    # quiz & callbacks
    app.add_handler(CommandHandler("quiz", quiz))
    app.add_handler(CommandHandler("edquiz", edquiz))
    app.add_handler(CallbackQueryHandler(quiz_callback, pattern=r"^quiz\|"))
    app.add_handler(CommandHandler("tops", tops))

    # broadcast
    app.add_handler(CommandHandler("broadcast", broadcast))

    # stats
    app.add_handler(CommandHandler("stats", stats))

    # report
    app.add_handler(CommandHandler("report", report))

    # backup/restore/allclear
    app.add_handler(CommandHandler("backup", backup))
    app.add_handler(CommandHandler("restore", restore))
    app.add_handler(CommandHandler("allclear", allclear))

    # catch-all message to save user/group
    app.add_handler(MessageHandler(filters.ALL & (~filters.COMMAND), on_message_save), group=0)

    # unknown command
    app.add_handler(MessageHandler(filters.COMMAND, unknown))

    logger.info("Bot starting...")
    app.run_polling()


if __name__ == "__main__":
    main()
