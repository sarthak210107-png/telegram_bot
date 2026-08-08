# Business Auto-Reply Bot

An AI-powered chatbot for local businesses (clinics, salons, small shops) that:
- Answers customer FAQs automatically, grounded in the business's real info (no hallucinated hours/prices)
- Runs a full appointment-booking conversation and saves bookings
- Costs **₹0/month** to run — free LLM API tier + free bot hosting

Built as a config-driven template: swap `config.yaml` and you have a new bot for a new business in 5 minutes.

## Why this exists

Most small businesses in India lose customers to unanswered WhatsApp/Telegram messages
after hours. This bot handles the first response instantly, and only escalates to a
human when it genuinely doesn't know the answer.

## Architecture

```
customer message
      │
      ▼
 is a booking in progress? ──yes──▶ booking.py (step-by-step state machine)
      │no
      ▼
 did they type "book"? ──yes──▶ start booking flow
      │no
      ▼
 llm.py: send message + business context (from config.yaml) to Groq's free API
      │
      ▼
 grounded reply sent back to customer
```

- `config.yaml` — all business-specific info (name, hours, services, FAQs, booking rules). Editing this is all you need to reuse the bot for a different client.
- `src/knowledge.py` — turns the config into a plain-text context block for the LLM.
- `src/llm.py` — calls Groq's free-tier LLM API, grounded strictly on the business context so it won't invent prices or hours.
- `src/booking.py` — a simple 4-step state machine (name → service → slot → confirm) that persists confirmed bookings to `data/appointments.json`.
- `src/bot.py` — Telegram bot entrypoint that wires the above together.

## Setup (takes ~5 minutes)

1. **Clone and install:**
   ```bash
   git clone <this-repo>
   cd whatsapp-business-bot
   pip install -r requirements.txt
   ```

2. **Get a free Telegram bot token:**
   - Message [@BotFather](https://t.me/BotFather) on Telegram
   - Send `/newbot`, follow the prompts, copy the token it gives you

3. **Get a free Groq API key:**
   - Sign up at [console.groq.com](https://console.groq.com) (free tier, no card needed)
   - Create an API key

4. **Configure:**
   ```bash
   cp .env.example .env
   # edit .env and paste in your tokens
   ```

5. **Customize for your business:**
   - Edit `config.yaml` — name, hours, services, FAQs

6. **Run:**
   ```bash
   cd src
   python bot.py
   ```

   Message your bot on Telegram and try it — ask a question, or type "book".

## Deploying for free (24/7 uptime)

Run it for free on [Railway](https://railway.app) or [Render](https://render.com):
1. Push this repo to GitHub
2. Connect the repo on Railway/Render, add your `.env` variables in their dashboard
3. Set the start command to `python src/bot.py`

Both have free tiers sufficient for a single small-business bot.

## Porting to WhatsApp

This ships with Telegram because it's instantly free and needs no business
verification — perfect for demos and MVPs. To move to WhatsApp:
- Use the [Twilio WhatsApp API](https://www.twilio.com/whatsapp) (has a free sandbox for testing)
- Replace `src/bot.py`'s Telegram polling loop with a Flask/FastAPI webhook that Twilio calls on incoming messages
- `knowledge.py`, `llm.py`, and `booking.py` need **zero changes** — that's the whole point of separating business logic from the messaging platform


## Tech stack

Python · python-telegram-bot · Groq API (Llama 3.1) · PyYAML

## License

MIT — use freely, customize per client.
