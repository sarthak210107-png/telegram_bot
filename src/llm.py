"""
Thin wrapper around Groq's OpenAI-compatible chat API.
Groq has a generous free tier and is fast enough for real-time chat replies.
Swap BASE_URL/MODEL if you'd rather use Gemini or another free-tier provider.
"""
import logging
import os
import requests

logger = logging.getLogger(__name__)

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
BASE_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "llama-3.1-8b-instant"

SYSTEM_PROMPT_TEMPLATE = """You are a friendly, conversational assistant for a local
business, chatting with customers on WhatsApp/Telegram. Talk naturally like a real
person — ask follow-up questions, show interest, make small talk if the customer
wants to chat.

For anything about the business itself — hours, prices, location, services,
policies — you must ONLY use the BUSINESS INFORMATION below. Never invent business
facts. If a customer asks something about the business that isn't covered below,
say you'll check and have someone follow up.

For everything else (general questions, casual conversation, advice, opinions) —
feel free to respond naturally using your own knowledge, like a normal AI assistant
would. You're not restricted outside of business-specific facts.

Reply in the same language/style the customer uses (English, Hindi, or Hinglish).
Keep replies conversational — 2-5 sentences is usually enough unless more detail
is genuinely needed.

BUSINESS INFORMATION:
{context}
"""


def ask_llm(user_message: str, context: str, history: list[dict] | None = None) -> str:
    """
    Send the customer's message + business context to the LLM and return a reply.
    history: optional list of {"role": "user"/"assistant", "content": str} for multi-turn memory.
    """
    if not GROQ_API_KEY:
        return ("(LLM not configured yet — set GROQ_API_KEY in your .env file. "
                "Get a free key at console.groq.com)")

    messages = [{"role": "system", "content": SYSTEM_PROMPT_TEMPLATE.format(context=context)}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": user_message})

    try:
        resp = requests.post(
            BASE_URL,
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json",
            },
            json={"model": MODEL, "messages": messages, "temperature": 0.7, "max_tokens": 500},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()
    except requests.exceptions.RequestException as e:
        logger.error("Groq API request failed: %s", e)
        return "Sorry, I'm having trouble replying right now. Please try again in a bit."
    except (KeyError, IndexError, ValueError) as e:
        # Covers malformed/unexpected response shape and JSON decode errors
        logger.error("Groq API returned an unexpected response: %s", e)
        return "Sorry, I'm having trouble replying right now. Please try again in a bit."
