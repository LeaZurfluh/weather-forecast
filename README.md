# Weather Outfit Advisor

A Python bot that fetches London's weather each morning, tells you what to wear, and asks for your feedback in the evening.

Every day at **8am** you get a Telegram message like:

```
Weather Outfit Advisor — Monday, 05 May 2026

Morning (avg 12.1°C, feels like 9.8°C) — cloudy, rain 45%
  Base layer:  warm jumper or fleece
  Outer layer: jacket or warm coat
  Rain gear:   umbrella just in case
  Extras:      scarf (optional)

Afternoon (avg 15.3°C, feels like 14.1°C) — cloudy
  Base layer:  light-to-mid jumper or thick cardigan
  Outer layer: jacket or warm coat

Evening (avg 11.0°C, feels like 8.5°C) — rain, rain 72%
  Base layer:  warm jumper or fleece
  Outer layer: jacket or warm coat
  Rain gear:   bring umbrella — rain expected
```

At **8pm** it asks you to rate the advice with 👍 or 👎. Replies are saved to `feedback_log.csv`.

---

## What you need before starting

- **Python 3.9 or newer** — check with `python3 --version` in your terminal
- **A Telegram account** — the app on your phone is fine

---

## Step 1 — Create a Telegram bot (takes about 2 minutes)

1. Open Telegram on your phone or desktop.
2. Search for **@BotFather** (it has a blue checkmark — it's the official one).
3. Tap **Start** or send `/start`.
4. Send `/newbot`.
5. BotFather will ask for a name (e.g. `My Weather Advisor`) and a username (must end in `bot`, e.g. `myweatheradvisor_bot`).
6. BotFather replies with a **token** that looks like: `123456789:ABCdefGhIJKlmNoPQRsTUVwXyz`
7. **Copy that token** — you'll need it in a moment.

---

## Step 2 — Find your Chat ID

Your Chat ID tells the bot who to message. The easiest way:

1. On Telegram, search for **@userinfobot**.
2. Send it any message (e.g. `/start`).
3. It replies with your **Id** — a number like `987654321`.
4. Copy that number.

Alternatively, after setting up the bot token in the next step, you can:
1. Send your new bot any message on Telegram (this opens the chat).
2. Visit this URL in your browser (replace `TOKEN` with your actual token):
   `https://api.telegram.org/botTOKEN/getUpdates`
3. Look for `"chat": {"id": 987654321, ...}` in the JSON.

---

## Step 3 — Add your credentials to the code

Open [bot.py](bot.py) and replace the two placeholder values near the top:

```python
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"   # ← paste your token here
CHAT_ID   = "YOUR_CHAT_ID_HERE"     # ← paste your chat ID here (as a string, keep the quotes)
```

Save the file.

---

## Step 4 — Install dependencies

In your terminal, navigate to this folder and run:

```bash
pip install -r requirements.txt
```

This installs three packages:
- `requests` — for fetching weather data
- `python-telegram-bot` — for sending Telegram messages
- `schedule` — included for reference (the bot uses the built-in scheduler instead)

If you have both Python 2 and 3 installed, use `pip3` instead of `pip`.

---

## Step 5 — Test your credentials (optional but recommended)

Before running the full scheduler, send a quick test message to confirm everything is wired up:

```bash
python bot.py
```

If it prints `Test message sent successfully.` and your phone buzzes, you're ready.
If you get an error, re-check your token and chat ID — a single wrong character is enough to break it.

---

## Step 6 — Test the weather fetch

```bash
python -c "from weather import get_weather_periods; import pprint; pprint.pprint(get_weather_periods())"
```

You should see a dict with `morning`, `afternoon`, and `evening` keys, each containing London temperature data.

---

## Step 7 — Run the bot

```bash
python scheduler.py
```

Leave this terminal window open. The bot runs in the foreground — you'll see a startup message:

```
Bot is running.
  Morning outfit advice: 08:00 daily
  Evening feedback prompt: 20:00 daily
Press Ctrl+C to stop.
```

Press **Ctrl+C** to stop it.

---

## Testing without waiting for 8am

To send yourself the morning message immediately (useful when first setting up), open [scheduler.py](scheduler.py), find this commented-out block near the bottom, and uncomment it:

```python
# import asyncio
# application.job_queue.run_once(morning_job, when=5)  # fires after 5 seconds
```

Run `python scheduler.py`, wait about 5 seconds, and the message will arrive. Re-comment those lines before leaving the bot running overnight.

---

## Customising the outfit thresholds

All the clothing logic lives in [advisor.py](advisor.py). At the top of the file you'll find:

```python
COLD_OFFSET = 2  # ← change this first
```

This number (in °C) is added to every standard temperature threshold. Changing it shifts all recommendations at once:

| COLD_OFFSET | Who it suits |
|-------------|--------------|
| 0 | Average person — standard thresholds |
| 2 | Slightly cold-sensitive (default) |
| 4 | Noticeably cold-sensitive |
| -2 | Runs warm / prefers lighter clothing |

You can also override the individual thresholds (`COLD_THRESHOLD`, `COOL_THRESHOLD`, etc.) in the same file for finer control.

The rain thresholds (`RAIN_LIKELY`, `RAIN_POSSIBLE`) are separate constants just below the temperature ones.

---

## Feedback log

Every time you reply 👍 or 👎 after the evening prompt, a row is appended to `feedback_log.csv` in this folder. It's created automatically on first run. Format:

```
date,period,suggestion,feedback
2026-05-04,morning,"Morning (avg 12.1°C...",👍
```

---

## Troubleshooting

**`Error: Unauthorized` or `Invalid token`**
Your `BOT_TOKEN` in `bot.py` is wrong. Double-check it — no spaces, no missing characters.

**Bot starts but no message arrives**
- Did you send your bot at least one message on Telegram first? Bots can't message you unless you've opened the conversation with them.
- Check that `CHAT_ID` is correct — get it from @userinfobot.
- Make sure the bot is running (terminal should show the startup message).

**`ModuleNotFoundError: No module named 'telegram'`**
Run `pip install -r requirements.txt` again. If that doesn't help, you may have multiple Python versions — try `pip3 install -r requirements.txt`.

**`job_queue` is `None`**
The `[job-queue]` extra wasn't installed. Run:
```bash
pip install "python-telegram-bot[job-queue]==21.3"
```

**Weather fetch fails**
Open-Meteo is free and needs no API key. Check your internet connection. The error message printed to the terminal will say what went wrong.

**Messages arrive at the wrong time**
The schedule runs on your machine's local clock. If the machine is not set to London time (Europe/London), the 8am job fires at 8am *your* machine's time, not London's. You can adjust the times in `scheduler.py`:
```python
application.job_queue.run_daily(morning_job, time=datetime.time(8, 0))
```

---

## Project structure

```
weather-forecast/
├── weather.py          # Fetches and parses Open-Meteo data
├── advisor.py          # Rule-based outfit recommendation logic
├── bot.py              # Telegram sending, feedback handling, CSV logging
├── scheduler.py        # Entry point — orchestrates the daily jobs
├── requirements.txt    # Python dependencies
├── feedback_log.csv    # Auto-created; stores your 👍/👎 responses
└── README.md           # This file
```
