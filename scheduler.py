"""
scheduler.py — entry point. Run this file to start the bot.

    python scheduler.py

What this does:
  - Registers a daily 8:00am job that fetches weather and sends outfit advice
  - Registers a daily 8:00pm job that asks for feedback
  - Starts the Telegram bot's polling loop (keeps running until you press Ctrl+C)

SCHEDULING APPROACH — why not the `schedule` library?
  `python-telegram-bot` v20+ runs its own asyncio event loop inside `run_polling()`.
  The `schedule` library needs its own `while True` loop, and mixing the two requires
  threading — awkward for a beginner. Instead, we use the `job_queue` that's built into
  python-telegram-bot (it's powered by APScheduler under the hood). Same outcome, no
  threading needed. The `schedule` package is still installed (see requirements.txt) if
  you want to explore it separately.
"""

import datetime

from telegram.ext import ApplicationBuilder

import bot

# ---------------------------------------------------------------------------
# JOB FUNCTIONS
# These are called by the job queue at the scheduled times.
# They must be async and accept a single `context` argument.
# ---------------------------------------------------------------------------

async def morning_job(context) -> None:
    """Run at 8:00am — fetch weather and send the outfit summary."""
    await bot.send_morning_message(context)


async def evening_job(context) -> None:
    """Run at 8:00pm — send the feedback prompt."""
    await bot.send_feedback_prompt(context)


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main() -> None:
    # Sanity check — catch the most common setup mistake before starting
    if bot.BOT_TOKEN == "YOUR_BOT_TOKEN_HERE" or bot.CHAT_ID == "YOUR_CHAT_ID_HERE":
        print(
            "ERROR: BOT_TOKEN and CHAT_ID are not set.\n"
            "Open bot.py and replace the placeholder values.\n"
            "See README.md for step-by-step instructions."
        )
        return

    # Make sure the feedback CSV exists before anything else runs
    bot.ensure_feedback_log_exists()

    # Build the Telegram Application
    # `[job-queue]` extra must be installed (it's in requirements.txt) for job_queue to work
    application = ApplicationBuilder().token(bot.BOT_TOKEN).build()

    # Register the message handler so the bot can receive replies
    application.add_handler(bot.build_message_handler())

    # Schedule the two daily jobs
    # `datetime.time(8, 0)` means 08:00 local time of the machine running this script.
    # If your machine is not set to London time, adjust accordingly or use a UTC offset.
    application.job_queue.run_daily(
        morning_job,
        time=datetime.time(8, 0),
        name="morning_outfit_advice",
    )
    application.job_queue.run_daily(
        evening_job,
        time=datetime.time(20, 0),
        name="evening_feedback_prompt",
    )

    print("Bot is running.")
    print("  Morning outfit advice: 08:00 daily")
    print("  Evening feedback prompt: 20:00 daily")
    print("Press Ctrl+C to stop.\n")

    # ---------------------------------------------------------------------------
    # TESTING TIP — send a message right now without waiting for 8am:
    #
    # Uncomment the block below, run `python scheduler.py`, wait ~5 seconds,
    # then re-comment it and restart normally.
    #
    import asyncio
    application.job_queue.run_once(morning_job, when=5)  # fires after 5 seconds
    # ---------------------------------------------------------------------------

    # This call blocks — it keeps the bot alive, polling Telegram for new messages
    application.run_polling()


if __name__ == "__main__":
    main()
