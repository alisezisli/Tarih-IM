import logging
import json
import re
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackContext

# Enable logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Global variables
TOKEN = ""
EVENTS_FILE = "events.json"
# Welcome & Help Message
HELP_TEXT = """*Tarih IM 👋🤖🏴‍☠️*

Bu bot, ilgili günde - kendince - önemli olay/olayları gösterir.

👉 /dun     ->  Dünün olaylarını gösterir
👉 /bugun   ->  Bugünün olaylarını gösterir
👉 /yarin   ->  Yarının olaylarını gösterir

👉 /tarih GG:AA     ->  Belirtilen tarihe ait olayları gösterir
👉 /otomatik SS:DD  ->  Belirtilen saatte, o günün olayını otomatik gösterir

❓ Bu mesajı tekrar görmek için: /help, /yardim, /hakkinda

https://gnuadm.in
https://alisezisli.com.tr

Bu bot, bir özgür yazılımdır ve GNU GPL v3 ile lisanslanmıştır.
https://github.com/alisezisli/Tarih-IM
"""

# Load events from JSON
def load_events():
    try:
        with open(EVENTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Error loading {EVENTS_FILE}: {e}")
        return []

# Get events for a specific day, ignoring the year
def get_events_for_date(date_obj):
    target_date = date_obj.strftime("%m-%d")  # Get MM-DD format
    events = load_events()
    return [event for event in events if event["date"][5:] == target_date]  # Compare MM-DD only

# Format event messages
def format_events(events):
    if not events:
        return "🤐 Bu tarih için kayıtlı bir olay yok."

    return "\n\n".join([
        f"*{e['header']}*\n_{datetime.strptime(e['date'], '%Y-%m-%d').strftime('%d-%m-%Y')}_\n\n{e['description']}"
        for e in events
    ])

# Send welcome message on start
async def start(update: Update, context: CallbackContext):
    await update.message.reply_text(HELP_TEXT, parse_mode="Markdown")

# Command: /bugun
async def bugun(update: Update, context: CallbackContext):
    today = datetime.now()
    events = get_events_for_date(today)
    await update.message.reply_text(format_events(events), parse_mode="Markdown")

# Command: /dun
async def dun(update: Update, context: CallbackContext):
    yesterday = datetime.now() - timedelta(days=1)
    events = get_events_for_date(yesterday)
    await update.message.reply_text(format_events(events), parse_mode="Markdown")

# Command: /yarin
async def yarin(update: Update, context: CallbackContext):
    tomorrow = datetime.now() + timedelta(days=1)
    events = get_events_for_date(tomorrow)
    await update.message.reply_text(format_events(events), parse_mode="Markdown")

# Command: /tarih DD:MM
async def tarih(update: Update, context: CallbackContext):
    if not context.args:
        await update.message.reply_text("🤦‍♂️ Gün ve ay şeklinde bir tarih belirtilmeli. Mesela şöyle: /tarih 22-01 veya 22:01", parse_mode="Markdown")
        return

    raw_date = context.args[0].replace(":", "-")  # DD:MM → DD-MM
    try:
        day, month = map(int, raw_date.split("-"))
    except ValueError:
        await update.message.reply_text("🤦‍♂️ Tarihi anlamadım. Şöyle bir şeyler olmalıydı: GG-AA veya GG:AA", parse_mode="Markdown")
        return

    # Check if the date is, well, a date
    try:
        date_obj = datetime(datetime.now().year, month, day)
    except ValueError:
        await update.message.reply_text("🤦‍♂️ Böyle bir tarih, pek mümkün değil gibi. GG:AA şeklinde olmalı. Mesela: /tarih 22-01", parse_mode="Markdown")
        return

    # Date is valid. Check for event:
    events = get_events_for_date(date_obj)
    if not events:
        await update.message.reply_text("🤐 Bu tarih için kayıtlı bir olay yok.", parse_mode="Markdown")
        return

    message = format_events(events)
    await update.message.reply_text(message, parse_mode="Markdown")

# Command: /otomatik HH:MM
async def otomatik(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id

    if len(context.args) != 1:
        await update.message.reply_text("🤦‍♂️ Saat belirtilmeli. Örneğin: /otomatik 19:28", parse_mode="Markdown")
        return

    time_arg = context.args[0]
    match = re.match(r'^([01]?\d|2[0-3]):([0-5]\d)$', time_arg)
    if not match:
        await update.message.reply_text("🤦‍♂️ Saati anlamadım. Şöyle bir şeyler olmalıydı: HH:MM (24 saat)", parse_mode="Markdown")
        return

    # Clock is correct. Set the cron:
    hour, minute = int(match.group(1)), int(match.group(2))
    job_id = f"daily_{chat_id}"

    # Remove existing one:
    existing_jobs = context.job_queue.get_jobs_by_name(job_id)
    if existing_jobs:
        existing_jobs[0].remove()
        logging.info(f"Removed existing job: {job_id}")

    # Hızlı test için run_once (10 saniye sonra)
    #context.job_queue.run_once(
    #    lambda context: send_daily_event(context.bot, chat_id),
    #    when=10,
    #    name=f"test_{job_id}"
    #)

    # Covert to UTC. Otherwise, it's not working as expected:
    from datetime import timezone
    local_time = datetime.strptime(f"{hour:02d}:{minute:02d}", "%H:%M").time()
    now = datetime.now(timezone.utc)  # UTC time
    local_datetime = datetime.combine(now.date(), local_time, tzinfo=timezone.utc)
    utc_time = local_datetime - timedelta(hours=3)  # UTC TR fix

    context.job_queue.run_daily(
        lambda context: send_daily_event(context.bot, chat_id),
        time=utc_time.time(),  # UTC converted
        days=(0, 1, 2, 3, 4, 5, 6),  # Every day
        name=job_id
    )

    logging.info(f"Scheduled job {job_id} for {hour:02d}:{minute:02d} daily (UTC: {utc_time.time()})")
    await update.message.reply_text(f"💪🤖👍 Her gün şu saatte günün olayını göndereceğim  {hour:02d}:{minute:02d}", parse_mode="Markdown")

# Send automated messages:
async def send_daily_event(bot, chat_id):
    today = datetime.now()
    events = get_events_for_date(today)
    message = format_events(events)
    logging.info(f"send_daily_event triggered for chat {chat_id} with message: {message}")
    try:
        await bot.send_message(chat_id=chat_id, text=message, parse_mode="Markdown")
        logging.info(f"Message successfully sent to {chat_id}")
    except Exception as e:
        logging.error(f"Failed to send message to {chat_id}: {e}")

# Main function
def main():
    logging.info("Starting bot...")
    app = Application.builder().token(TOKEN).build()

    # Start & Help Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", start))
    app.add_handler(CommandHandler("yardim", start))
    app.add_handler(CommandHandler("hakkinda", start))

    # Date Commands
    app.add_handler(CommandHandler("bugun", bugun))
    app.add_handler(CommandHandler("dun", dun))
    app.add_handler(CommandHandler("yarin", yarin))
    app.add_handler(CommandHandler("tarih", tarih))
    app.add_handler(CommandHandler("otomatik", otomatik))

    logging.info("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
