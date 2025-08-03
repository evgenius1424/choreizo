import logging
import os
import random
import sqlite3
from datetime import datetime, timedelta
import asyncio

from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes
)

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
logging.basicConfig(level=logging.INFO)

# --- Database Setup ---
conn = sqlite3.connect("choreizo.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    task TEXT,
    due_date TEXT,
    recurrence_min INTEGER,
    recurrence_max INTEGER
)
""")
conn.commit()


# --- Command Handlers ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Hello! I'm Choreizo. You can:\n"
        "- Add a one-time task: /add_task <task_name> <min_days> <max_days>\n"
        "- Add a recurring task: /add_recurring_task <task_name> <min_days> <max_days>\n"
        "- List tasks: /list_tasks"
    )


async def add_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        task_name = context.args[0]
        min_days = int(context.args[1])
        max_days = int(context.args[2])
        days_until_due = random.randint(min_days, max_days)
        due_date = (datetime.now() + timedelta(days=days_until_due)).isoformat()

        cursor.execute("""
            INSERT INTO tasks (user_id, task, due_date, recurrence_min, recurrence_max)
            VALUES (?, ?, ?, NULL, NULL)
        """, (update.effective_user.id, task_name, due_date))
        conn.commit()

        await update.message.reply_text(
            f"✅ Task '{task_name}' added! I'll remind you in ~{days_until_due} days."
        )
    except Exception:
        await update.message.reply_text("❌ Usage: /add_task <task_name> <min_days> <max_days>")


async def add_recurring_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        task_name = context.args[0]
        min_days = int(context.args[1])
        max_days = int(context.args[2])
        days_until_due = random.randint(min_days, max_days)
        due_date = (datetime.now() + timedelta(days=days_until_due)).isoformat()

        cursor.execute("""
            INSERT INTO tasks (user_id, task, due_date, recurrence_min, recurrence_max)
            VALUES (?, ?, ?, ?, ?)
        """, (update.effective_user.id, task_name, due_date, min_days, max_days))
        conn.commit()

        await update.message.reply_text(
            f"🔁 Recurring task '{task_name}' added! First reminder in ~{days_until_due} days."
        )
    except Exception:
        await update.message.reply_text("❌ Usage: /add_recurring_task <task_name> <min_days> <max_days>")


async def list_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    cursor.execute("SELECT task, due_date, recurrence_min FROM tasks WHERE user_id = ?", (user_id,))
    rows = cursor.fetchall()
    if not rows:
        await update.message.reply_text("📭 No tasks found.")
        return

    lines = []
    for task, due_date, recurrence in rows:
        due = datetime.fromisoformat(due_date).strftime("%Y-%m-%d")
        lines.append(f"📝 {task} — due: {due}{' (recurring)' if recurrence else ''}")
    await update.message.reply_text("\n".join(lines))


# --- Background Reminder Job ---

async def reminder_loop(app: Application):
    while True:
        now = datetime.now()
        start_hour = 11
        end_hour = 20

        if not (start_hour <= now.hour < end_hour):
            logging.info(f"Skipping notifications during off-hours ({now.hour}:00)")
            await asyncio.sleep(60 * 60)  # Still wait an hour before checking again
            continue

        cursor.execute("SELECT id, user_id, task, due_date, recurrence_min, recurrence_max FROM tasks")
        for row in cursor.fetchall():
            task_id, user_id, task, due_date, rmin, rmax = row
            due = datetime.fromisoformat(due_date)
            if due <= now:
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("🕐 Snooze", callback_data=f"snooze:{task_id}")]
                ])
                try:
                    await app.bot.send_message(
                        chat_id=user_id,
                        text=f"🔔 Reminder: *{task}* is due!",
                        reply_markup=keyboard,
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    logging.warning(f"Failed to notify user {user_id}: {e}")

                if rmin is not None and rmax is not None:
                    new_days = random.randint(rmin, rmax)
                    new_due = datetime.now() + timedelta(days=new_days)
                    cursor.execute(
                        "UPDATE tasks SET due_date = ? WHERE id = ?",
                        (new_due.isoformat(), task_id)
                    )
                else:
                    cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
                conn.commit()

        await asyncio.sleep(60 * 60)  # Run every hour


# --- Button Handler ---

async def handle_snooze(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    task_id = int(query.data.split(":")[1])
    new_days = random.randint(7, 14)
    new_due = datetime.now() + timedelta(days=new_days)
    cursor.execute("UPDATE tasks SET due_date = ? WHERE id = ?", (new_due.isoformat(), task_id))
    conn.commit()
    await query.edit_message_text(f"😴 Snoozed for {new_days} days.")


# --- Entry Point ---

def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("add_task", add_task))
    app.add_handler(CommandHandler("add_recurring_task", add_recurring_task))
    app.add_handler(CommandHandler("list_tasks", list_tasks))
    app.add_handler(CallbackQueryHandler(handle_snooze, pattern="^snooze:"))

    # Launch reminder loop
    app.job_queue.run_once(lambda *_: asyncio.create_task(reminder_loop(app)), 1)

    print("🤖 Choreizo is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
