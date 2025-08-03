import logging
import os
import random
import re
import sqlite3
from datetime import datetime, timedelta
import asyncio
from contextlib import asynccontextmanager
import pytz

from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes
)

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
logging.basicConfig(level=logging.INFO)

BERLIN_TZ = pytz.timezone('Europe/Berlin')
REMINDER_HOUR = 11

DB_PATH = "choreizo.db"


def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            task TEXT,
            due_date TEXT,
            recurrence_min INTEGER,
            recurrence_max INTEGER,
            last_reminded TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """)
        try:
            cursor.execute("ALTER TABLE tasks ADD COLUMN last_reminded TEXT")
        except sqlite3.OperationalError:
            pass
        try:
            cursor.execute("ALTER TABLE tasks ADD COLUMN created_at TEXT DEFAULT CURRENT_TIMESTAMP")
        except sqlite3.OperationalError:
            pass
        conn.commit()


async def get_berlin_time():
    return datetime.now(BERLIN_TZ)


async def is_reminder_time():
    berlin_now = await get_berlin_time()
    return berlin_now.hour == REMINDER_HOUR


async def get_today_berlin():
    berlin_now = await get_berlin_time()
    return berlin_now.date()


@asynccontextmanager
async def get_db():
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
    finally:
        conn.close()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Hello! I'm Choreizo, your friendly task reminder bot.\n\n"
        "Here's what I can do:\n"
        "• /task <task name> <min_days>-<max_days>: Add a one-time task\n"
        "  Example: `/task Clean up the room 5-10`\n\n"
        "• /repeat <task name> <min_days>-<max_days>: Add a recurring task\n"
        "  Example: `/repeat Buy groceries 7-14`\n\n"
        "• /list: See all your currently active tasks\n"
        "• /delete: Remove a task\n"
        "• /stats: View your task completion stats"
    )


async def _parse_task_input(args):
    if not args:
        return None, None, None

    full_text = " ".join(args)
    match = re.search(r'(\d+)-(\d+)$', full_text.strip())
    if match:
        min_days = int(match.group(1))
        max_days = int(match.group(2))
        task_name = full_text[:match.start()].strip()
        if not task_name or min_days <= 0 or max_days < min_days:
            return None, None, None
        return task_name, min_days, max_days
    return None, None, None


async def add_one_time_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    task_name, min_days, max_days = await _parse_task_input(context.args)

    if task_name is None:
        await update.message.reply_text(
            "❌ Usage: `/task <task name> <min_days>-<max_days>`\n"
            "Example: `/task Clean bathroom 7-10`\n"
            "Min days must be > 0 and max days >= min days")
        return

    try:
        days_until_due = random.randint(min_days, max_days)
        due_date = (datetime.now() + timedelta(days=days_until_due)).isoformat()

        async with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO tasks (user_id, task, due_date, recurrence_min, recurrence_max)
                VALUES (?, ?, ?, NULL, NULL)
            """, (update.effective_user.id, task_name, due_date))
            conn.commit()

        await update.message.reply_text(
            f"✅ Task '{task_name}' added! I'll remind you in {days_until_due} day{'s' if days_until_due != 1 else ''}."
        )
    except Exception as e:
        logging.error(f"Error adding task: {e}")
        await update.message.reply_text("❌ An error occurred while adding the task. Please try again.")


async def add_repeating_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    task_name, min_days, max_days = await _parse_task_input(context.args)

    if task_name is None:
        await update.message.reply_text(
            "❌ Usage: `/repeat <task name> <min_days>-<max_days>`\n"
            "Example: `/repeat Flip mattress 60-100`\n"
            "Min days must be > 0 and max days >= min days")
        return

    try:
        days_until_due = random.randint(min_days, max_days)
        due_date = (datetime.now() + timedelta(days=days_until_due)).isoformat()

        async with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO tasks (user_id, task, due_date, recurrence_min, recurrence_max)
                VALUES (?, ?, ?, ?, ?)
            """, (update.effective_user.id, task_name, due_date, min_days, max_days))
            conn.commit()

        await update.message.reply_text(
            f"🔁 Recurring task '{task_name}' added! First reminder in {days_until_due} day{'s' if days_until_due != 1 else ''}."
        )
    except Exception as e:
        logging.error(f"Error adding recurring task: {e}")
        await update.message.reply_text("❌ An error occurred while adding the recurring task. Please try again.")


async def list_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    async with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, task, due_date, recurrence_min, recurrence_max
            FROM tasks
            WHERE user_id = ?
            ORDER BY due_date ASC
        """, (user_id,))
        rows = cursor.fetchall()

    if not rows:
        await update.message.reply_text("You have no tasks at the moment.")
        return

    lines = ["*Your Tasks:*"]
    now = datetime.now()

    for task_id, task, due_date, rmin, rmax in rows:
        due = datetime.fromisoformat(due_date)
        days_left = (due - now).days

        if days_left < 0:
            status = f"Overdue by {abs(days_left)} day{'s' if abs(days_left) != 1 else ''}"
        elif days_left == 0:
            status = "Due *today*"
        elif days_left == 1:
            status = "Due *tomorrow*"
        else:
            status = f"Due in *{days_left}* day{'s' if days_left != 1 else ''}"

        recurring_chip = " 🔁" if rmin is not None else ""
        lines.append(f"• *{task}* — {status}{recurring_chip}")

    message = "\n".join(lines)
    if len(message) > 4000:
        messages = [message[i:i + 4000] for i in range(0, len(message), 4000)]
        for msg in messages:
            await update.message.reply_text(msg, parse_mode="Markdown")
    else:
        await update.message.reply_text(message, parse_mode="Markdown")


async def delete_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    async with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, task FROM tasks WHERE user_id = ? ORDER BY due_date ASC
        """, (user_id,))
        tasks = cursor.fetchall()

    if not tasks:
        await update.message.reply_text("📭 No tasks to delete.")
        return

    keyboard = []
    for task_id, task_name in tasks[:10]:
        keyboard.append([InlineKeyboardButton(f"🗑️ {task_name[:30]}...", callback_data=f"delete:{task_id}")])

    keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="delete:cancel")])

    await update.message.reply_text(
        "Select a task to delete:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def get_tasks_due_today(user_id):
    today = datetime.now().date()

    async with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, task, due_date, recurrence_min, recurrence_max, last_reminded
            FROM tasks
            WHERE user_id = ? AND date(due_date) <= date('now')
            ORDER BY due_date ASC
        """, (user_id,))
        return cursor.fetchall()


async def postpone_task_by_one_day(task_id):
    async with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE tasks 
            SET due_date = datetime(due_date, '+1 day')
            WHERE id = ?
        """, (task_id,))
        conn.commit()


async def reminder_loop(app: Application):
    while True:
        try:
            if not await is_reminder_time():
                await asyncio.sleep(30 * 60)
                continue

            logging.info("Sending daily reminders at 11 AM Berlin time")
            current_date = await get_today_berlin()

            async with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT DISTINCT user_id FROM tasks 
                    WHERE date(due_date) <= date('now')
                    AND (last_reminded IS NULL OR date(last_reminded) != date('now'))
                """)
                users = cursor.fetchall()

            for (user_id,) in users:
                tasks_due = await get_tasks_due_today(user_id)

                if not tasks_due:
                    continue

                tasks_to_remind = []
                for task in tasks_due:
                    task_id, task_name, due_date, rmin, rmax, last_reminded = task

                    if last_reminded is None or datetime.fromisoformat(last_reminded).date() != current_date:
                        tasks_to_remind.append(task)

                if not tasks_to_remind:
                    continue

                if len(tasks_to_remind) > 2:
                    tasks_for_today = tasks_to_remind[:2]
                    tasks_to_postpone = tasks_to_remind[2:]

                    for task in tasks_to_postpone:
                        task_id = task[0]
                        await postpone_task_by_one_day(task_id)
                        logging.info(f"Postponed task {task_id} due to overlap")
                else:
                    tasks_for_today = tasks_to_remind

                for task in tasks_for_today:
                    task_id, task_name, due_date, rmin, rmax, last_reminded = task

                    keyboard = InlineKeyboardMarkup([
                        [
                            InlineKeyboardButton("✅ Done", callback_data=f"done:{task_id}"),
                            InlineKeyboardButton("😴 Snooze 7-14d", callback_data=f"snooze:{task_id}")
                        ]
                    ])

                    try:
                        berlin_time = await get_berlin_time()
                        await app.bot.send_message(
                            chat_id=user_id,
                            text=f"🔔 Good morning! Reminder: *{task_name}* is due!",
                            reply_markup=keyboard,
                            parse_mode="Markdown"
                        )

                        async with get_db() as conn:
                            cursor = conn.cursor()
                            cursor.execute("""
                                UPDATE tasks 
                                SET last_reminded = ? 
                                WHERE id = ?
                            """, (berlin_time.isoformat(), task_id))
                            conn.commit()

                    except Exception as e:
                        logging.warning(f"Failed to notify user {user_id}: {e}")

            await asyncio.sleep(23 * 60 * 60)

        except Exception as e:
            logging.error(f"Error in reminder loop: {e}")
            await asyncio.sleep(60 * 60)


async def handle_task_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    action, task_id = query.data.split(":", 1)

    if action == "delete":
        if task_id == "cancel":
            await query.edit_message_text("❌ Deletion cancelled.")
            return

        task_id = int(task_id)
        async with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT task FROM tasks WHERE id = ?", (task_id,))
            task_info = cursor.fetchone()

            if task_info:
                cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
                conn.commit()
                await query.edit_message_text(f"🗑️ Deleted task: {task_info[0]}")
            else:
                await query.edit_message_text("❌ Task not found.")
        return

    task_id = int(task_id)

    async with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT task, recurrence_min, recurrence_max 
            FROM tasks WHERE id = ?
        """, (task_id,))
        task_info = cursor.fetchone()

        if not task_info:
            await query.edit_message_text("❌ Task not found.")
            return

        task_name, rmin, rmax = task_info

        if action == "done":
            if rmin is not None and rmax is not None:
                new_days = random.randint(rmin, rmax)
                new_due = datetime.now() + timedelta(days=new_days)
                cursor.execute("""
                    UPDATE tasks 
                    SET due_date = ?, last_reminded = NULL 
                    WHERE id = ?
                """, (new_due.isoformat(), task_id))
                await query.edit_message_text(
                    f"✅ Great job! '{task_name}' completed.\n"
                    f"Next reminder in {new_days} day{'s' if new_days != 1 else ''}."
                )
            else:
                cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
                await query.edit_message_text(f"✅ Task '{task_name}' completed and removed!")

        elif action == "snooze":
            snooze_days = random.randint(7, 14)

            new_due = datetime.now() + timedelta(days=snooze_days)
            cursor.execute("""
                UPDATE tasks 
                SET due_date = ?, last_reminded = NULL 
                WHERE id = ?
            """, (new_due.isoformat(), task_id))
            await query.edit_message_text(
                f"😴 '{task_name}' snoozed for {snooze_days} days (perfect for travel!)."
            )

        conn.commit()


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    async with get_db() as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM tasks WHERE user_id = ?", (user_id,))
        total_tasks = cursor.fetchone()[0]

        cursor.execute("""
            SELECT COUNT(*) FROM tasks 
            WHERE user_id = ? AND date(due_date) < date('now')
        """, (user_id,))
        overdue_tasks = cursor.fetchone()[0]

        cursor.execute("""
            SELECT COUNT(*) FROM tasks 
            WHERE user_id = ? AND recurrence_min IS NOT NULL
        """, (user_id,))
        recurring_tasks = cursor.fetchone()[0]

        one_time_tasks = total_tasks - recurring_tasks

    await update.message.reply_text(
        f"📊 *Your Task Stats:*\n\n"
        f"📋 Total tasks: {total_tasks}\n"
        f"🔁 Recurring: {recurring_tasks}\n"
        f"📝 One-time: {one_time_tasks}\n"
        f"⚠️ Overdue: {overdue_tasks}",
        parse_mode="Markdown"
    )


def main():
    init_db()
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("task", add_one_time_task))
    app.add_handler(CommandHandler("repeat", add_repeating_task))
    app.add_handler(CommandHandler("list", list_tasks))
    app.add_handler(CommandHandler("delete", delete_task))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CallbackQueryHandler(handle_task_action))

    app.job_queue.run_once(lambda *_: asyncio.create_task(reminder_loop(app)), 1)

    print("🤖 Choreizo is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
