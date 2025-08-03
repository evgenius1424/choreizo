# Choreizo Bot 🤖🌭

A friendly Telegram bot for managing long-term, fuzzy-scheduled household tasks like defrosting the fridge, flipping
mattresses, or deep cleaning. Perfect for tasks that need doing "every so often" but don't require rigid scheduling.

## ✨ Features

### 🎯 Smart Task Management

- **One-time tasks**: Perfect for seasonal chores or occasional maintenance
- **Recurring tasks**: Automatically reschedule after completion with randomized intervals
- **Flexible scheduling**: Set minimum and maximum day ranges (e.g., remind me every 60-100 days)

### 🔔 Intelligent Reminders

- **Daily reminders** at 11 AM Berlin time for due tasks
- **Smart task limiting**: Only shows 2 tasks per day to avoid overwhelm
- **Automatic postponing**: Extra due tasks get pushed to the next day
- **No spam**: Tasks are only reminded once per day

### 🎮 Interactive Controls

- **Quick actions**: Mark tasks as done or snooze them with inline buttons
- **Flexible snoozing**: Snooze tasks for 7-14 days (perfect for travel!)
- **Easy management**: View, add, and delete tasks with simple commands

### 📊 Progress Tracking

- Task completion statistics
- Overview of recurring vs one-time tasks
- Overdue task monitoring

## 🚀 Commands

### Adding Tasks

```
/task <task name> <min_days>-<max_days>
```

Add a one-time task that will be removed after completion.
*Example:* `/task Clean out garage 30-45`

```
/repeat <task name> <min_days>-<max_days>
```

Add a recurring task that reschedules itself after completion.
*Example:* `/repeat Flip mattress 90-120`

### Managing Tasks

```
/list
```

View all your active tasks with due dates and status

```
/delete
```

Remove a task using an interactive menu

```
/stats
```

View statistics about your tasks

```
/start
```

Get help and see all available commands

## 🛠️ Setup

### Prerequisites

- Python 3.7+
- A Telegram Bot Token (get one from [@BotFather](https://t.me/BotFather))

### Installation

1. **Clone the repository**

```bash
git clone <your-repo-url>
cd choreizo-bot
```

2. **Create virtual environment**

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**

```bash
pip install -r requirements.txt
```

4. **Configure environment**
   Create a `.env` file in the project root:

```env
BOT_TOKEN=your_telegram_bot_token_here
```

5. **Run the bot**

```bash
python bo
```

## 💾 Database

Choreizo uses SQLite for data storage. The database (`choreizo.db`) is automatically created on first run and includes:

- Task storage with due dates and recurrence settings
- User-specific task management
- Reminder tracking to prevent spam

## 🌍 Timezone

The bot operates on Berlin time (Europe/Berlin) and sends daily reminders at 11 AM. This ensures consistent scheduling
regardless of where you deploy the bot.

## 🎭 Use Cases

Perfect for managing:

- **Seasonal maintenance**: Clean gutters every 6-8 months
- **Appliance care**: Defrost freezer every 3-4 months
- **Deep cleaning**: Wash curtains every 2-3 months
- **Health reminders**: Eye exam every 12-18 months
- **Home maintenance**: Check smoke detectors every 4-6 months
- **Organization**: Declutter closets every 6-9 months

## 🤝 Contributing

Feel free to submit issues, feature requests, or pull requests. Choreizo is designed to be simple and focused on fuzzy
scheduling for household management.

---