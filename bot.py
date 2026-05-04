"""
bot.py — all Telegram interaction.

Handles:
  - Sending the morning outfit summary
  - Sending the evening feedback prompt
  - Listening for 👍 / 👎 replies and logging them to feedback_log.csv

This module is imported by scheduler.py. You can also run it directly
to send a test message and verify your credentials before starting the scheduler.
"""

import csv
import datetime
import os

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters

import advisor
import weather

# ---------------------------------------------------------------------------
# TELEGRAM CREDENTIALS — loaded from the .env file in this folder.
# Never put real tokens directly in Python files; .env is listed in .gitignore
# so it won't be accidentally committed to git.
#
# Your .env file should look like this:
#   BOT_TOKEN=123456789:ABCdefGhIJKlmNoPQRsTUVwXyz
#   CHAT_ID=987654321
# ---------------------------------------------------------------------------

load_dotenv()  # reads .env and adds its contents to the environment

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
CHAT_ID   = os.getenv("CHAT_ID", "")

# ---------------------------------------------------------------------------
# FILE PATH
# ---------------------------------------------------------------------------

FEEDBACK_LOG = "feedback_log.csv"

# ---------------------------------------------------------------------------
# MODULE-LEVEL STATE
# These variables track the conversation between the morning send and evening reply.
# They reset each time the bot process restarts.
# ---------------------------------------------------------------------------

_last_morning_suggestion: str = ""  # Stores the morning message so it can be logged later
_waiting_for_feedback: bool = False  # True after the evening prompt is sent


# ---------------------------------------------------------------------------
# CSV SETUP
# ---------------------------------------------------------------------------

def ensure_feedback_log_exists() -> None:
    """
    Create feedback_log.csv with a header row if it doesn't exist yet.
    Safe to call on every startup — it won't overwrite an existing file.
    """
    if not os.path.exists(FEEDBACK_LOG):
        with open(FEEDBACK_LOG, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["date", "period", "suggestion", "feedback"])
        print(f"Created {FEEDBACK_LOG}")


# ---------------------------------------------------------------------------
# MESSAGE FORMATTING
# ---------------------------------------------------------------------------

def format_morning_message(periods: dict) -> str:
    """
    Build the full Telegram message string for the morning send.

    Calls advisor.get_recommendation() for each of the three periods and
    joins them into a single readable message.
    """
    today = datetime.date.today().strftime("%A, %d %B %Y")  # e.g. "Monday, 05 May 2026"

    sections = [
        f"👗 Weather Outfit Advisor",
        f"📅 {today}",
        "",  # blank line for visual spacing
    ]

    for period_key in ("morning", "afternoon", "evening"):
        recommendation = advisor.get_recommendation(periods[period_key])
        sections.append(recommendation)
        sections.append("")  # blank line between periods

    return "\n".join(sections).rstrip()  # strip trailing blank line


# ---------------------------------------------------------------------------
# JOB CALLBACKS (called by the scheduler's job_queue)
# ---------------------------------------------------------------------------

async def send_morning_message(context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Fetch today's weather, build the outfit advice, and send it via Telegram.
    Called automatically by the job queue at 8:00am.
    """
    global _last_morning_suggestion

    try:
        periods = weather.get_weather_periods()
        message = format_morning_message(periods)
    except Exception as e:
        # If the weather fetch fails, send an error message rather than silently doing nothing
        message = f"Could not fetch weather today. Error: {e}"

    await context.bot.send_message(chat_id=CHAT_ID, text=message)

    # Store the message so the evening job can log it alongside the feedback
    _last_morning_suggestion = message
    print(f"Morning message sent at {datetime.datetime.now().strftime('%H:%M')}")


async def send_feedback_prompt(context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Send a feedback request at 8:00pm.
    Sets _waiting_for_feedback so the message handler knows to log the next reply.
    """
    global _waiting_for_feedback

    await context.bot.send_message(
        chat_id=CHAT_ID,
        text="How was today's outfit advice? Reply with 👍 or 👎"
    )
    _waiting_for_feedback = True
    print(f"Feedback prompt sent at {datetime.datetime.now().strftime('%H:%M')}")


# ---------------------------------------------------------------------------
# MESSAGE HANDLER (listens for incoming messages)
# ---------------------------------------------------------------------------

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle all incoming text messages from Telegram.

    Security note: we only process messages from CHAT_ID — anyone else is ignored.
    This prevents strangers from spamming the feedback log if they somehow message your bot.
    """
    global _waiting_for_feedback

    # Ignore messages from anyone other than the configured chat
    if str(update.effective_chat.id) != str(CHAT_ID):
        return

    text = update.message.text.strip()

    if _waiting_for_feedback:
        if text in ("👍", "👎"):
            # Log the feedback to CSV
            with open(FEEDBACK_LOG, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    datetime.date.today().isoformat(),  # e.g. "2026-05-04"
                    "morning",
                    _last_morning_suggestion[:200],  # truncate long suggestions for CSV readability
                    text,
                ])
            _waiting_for_feedback = False
            await update.message.reply_text("Thanks for the feedback!")
            print(f"Feedback logged: {text}")
        else:
            await update.message.reply_text(
                "Send 👍 or 👎 after the evening prompt to log feedback."
            )
    else:
        await update.message.reply_text(
            "I'll send outfit advice at 8am and ask for feedback at 8pm. "
            "Nothing to do right now!"
        )


# ---------------------------------------------------------------------------
# CONVENIENCE FUNCTION — builds the MessageHandler for use in scheduler.py
# ---------------------------------------------------------------------------

def build_message_handler() -> MessageHandler:
    """Return a configured MessageHandler that routes all text messages to handle_message."""
    return MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)


# ---------------------------------------------------------------------------
# STANDALONE TEST — run `python bot.py` to send a single test message
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import asyncio
    import telegram

    async def _test():
        bot = telegram.Bot(BOT_TOKEN)
        await bot.send_message(
            chat_id=CHAT_ID,
            text="Test message from your weather outfit advisor bot! Setup is working."
        )
        print("Test message sent successfully.")

    # Sanity check before attempting to connect
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE" or CHAT_ID == "YOUR_CHAT_ID_HERE":
        print("ERROR: Please set BOT_TOKEN and CHAT_ID in bot.py before testing.")
    else:
        asyncio.run(_test())
