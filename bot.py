import logging
import os
import random
import re
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


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Hello! I'm Choreizo, your friendly task reminder bot.\n\n"
        "Here's what I can do:\n"
        "- /task <task name> <min_days>-<max_days>: Add a one-time task that will remind you within the specified day range.\n"
        "  Example: `/task Clean up the room 5-10`\n\n"
        "- /every <task name> <min_days>-<max_days>: Add a recurring task that will remind you repeatedly within the specified day range after each completion.\n"
        "  Example: `/every Buy groceries 7-14`\n\n"
        "- /list: See all your currently active tasks and their next due dates."
    )


async def _parse_task_input(args):
    """
    Helper function to parse task input in the format:
    "<task name> <min_days>-<max_days>"
    """
    full_text = " ".join(args)
    match = re.search(r'(\d+)-(\d+)$', full_text.strip())
    if match:
        min_days = int(match.group(1))
        max_days = int(match.group(2))
        task_name = full_text[:match.start()].strip()
        if not task_name:
            return None, None, None
        return task_name, min_days, max_days
    return None, None, None


async def add_one_time_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    task_name, min_days, max_days = await _parse_task_input(context.args)

    if task_name is None or min_days is None or max_days is None:
        await update.message.reply_text(
            "❌ Usage: `/task <task name> <min_days>-<max_days>`\nExample: `/task Clean up the room 5-10`")
        return

    try:
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
    except Exception as e:
        logging.error(f"Error adding task: {e}")
        await update.message.reply_text("An error occurred while adding the task. Please try again.")


async def add_recurring_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    task_name, min_days, max_days = await _parse_task_input(context.args)

    if task_name is None or min_days is None or max_days is None:
        await update.message.reply_text(
            "❌ Usage: `/every <task name> <min_days>-<max_days>`\nExample: `/every Buy groceries 7-14`")
        return

    try:
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
    except Exception as e:
        logging.error(f"Error adding recurring task: {e}")
        await update.message.reply_text("An error occurred while adding the recurring task. Please try again.")


async def list_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    cursor.execute("""
        SELECT task, due_date, recurrence_min
        FROM tasks
        WHERE user_id = ?
        ORDER BY due_date ASC
        LIMIT 10
    """, (user_id,))
    rows = cursor.fetchall()
    if not rows:
        await update.message.reply_text("📭 No tasks found.")
        return

    lines = ["📝 Your closest tasks:"]
    for task, due_date, recurrence in rows:
        due = datetime.fromisoformat(due_date).strftime("%Y-%m-%d")
        lines.append(f"• {task} — due: {due}{' (recurring)' if recurrence else ''}")
    await update.message.reply_text("\n".join(lines))


async def reminder_loop(app: Application):
    while True:
        now = datetime.now()
        start_hour = 7
        end_hour = 21  # 9 PM

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

        await asyncio.sleep(60 * 60)


async def handle_snooze(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    task_id = int(query.data.split(":")[1])
    new_days = random.randint(7, 14)
    new_due = datetime.now() + timedelta(days=new_days)
    cursor.execute("UPDATE tasks SET due_date = ? WHERE id = ?", (new_due.isoformat(), task_id))
    conn.commit()
    await query.edit_message_text(f"😴 Snoozed for {new_days} days.")


def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("task", add_one_time_task))
    app.add_handler(CommandHandler("every", add_recurring_task))
    app.add_handler(CommandHandler("list", list_tasks))
    app.add_handler(CallbackQueryHandler(handle_snooze, pattern="^snooze:"))

    app.job_queue.run_once(lambda *_: asyncio.create_task(reminder_loop(app)), 1)

    print("🤖 Choreizo is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
