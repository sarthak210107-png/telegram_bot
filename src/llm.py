"""
Thin wrapper around Groq's OpenAI-compatible chat API.
Groq has a generous free tier and is fast enough for real-time chat replies.
Swap BASE_URL/MODEL if you'd rather use Gemini or another free-tier provider.
"""
import os
import requests

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
BASE_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "llama-3.1-8b-instant"

SYSTEM_PROMPT_TEMPLATE = """You are a helpful WhatsApp/Telegram assistant for a local business.
Answer ONLY using the business information below. If the answer isn't in the
information, say you'll have someone from the business follow up — never make
up hours, prices, or services.

Keep replies short (2-4 sentences), friendly, and in the same language the
customer used (English or Hindi/Hinglish).

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
            json={"model": MODEL, "messages": messages, "temperature": 0.4, "max_tokens": 300},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()
    except requests.exceptions.RequestException as e:
        return f"Sorry, I'm having trouble replying right now. Please try again in a bit. ({e})"
