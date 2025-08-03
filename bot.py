import logging
import os
import random
import sqlite3
from datetime import datetime, timedelta

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
logging.basicConfig(level=logging.INFO)

conn = sqlite3.connect("choreizo.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("""
    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        task TEXT,
        due_date TEXT
    )
""")
conn.commit()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Hello! I'm Choreizo. Use /add_task to start scheduling fun chores!")


async def add_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        task_name = context.args[0]
        min_days = int(context.args[1])
        max_days = int(context.args[2])
        days_until_due = random.randint(min_days, max_days)
        due_date = (datetime.now() + timedelta(days=days_until_due)).isoformat()

        cursor.execute("INSERT INTO tasks (user_id, task, due_date) VALUES (?, ?, ?)",
                       (update.effective_user.id, task_name, due_date))
        conn.commit()

        await update.message.reply_text(f"✅ Task '{task_name}' added! I'll remind you around {days_until_due} days.")
    except Exception as e:
        await update.message.reply_text("❌ Usage: /add_task task_name min_days max_days")


def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("add_task", add_task))

    print("🤖 Bot running...")
    app.run_polling()


if __name__ == "__main__":
    main()
