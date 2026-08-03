"""
Minimal appointment booking flow.
State is kept per chat_id in memory (fine for a single small business bot);
confirmed bookings are persisted to data/appointments.json.
"""
import json
from datetime import datetime, timedelta
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)
APPOINTMENTS_FILE = DATA_DIR / "appointments.json"

# In-memory per-user state machine: chat_id -> {"step": str, "data": {...}}
_sessions: dict[int, dict] = {}

STEPS = ["ask_name", "ask_service", "ask_slot", "confirm"]


def _load_appointments() -> list[dict]:
    if not APPOINTMENTS_FILE.exists():
        return []
    with open(APPOINTMENTS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_appointment(entry: dict) -> None:
    appointments = _load_appointments()
    appointments.append(entry)
    with open(APPOINTMENTS_FILE, "w", encoding="utf-8") as f:
        json.dump(appointments, f, indent=2)


def available_slots(config: dict) -> list[str]:
    """Generate today's remaining hourly slots based on config booking hours."""
    booking_cfg = config["booking"]
    now = datetime.now()
    slots = []
    for hour in range(booking_cfg["slot_start_hour"], booking_cfg["slot_end_hour"]):
        slot_time = now.replace(hour=hour, minute=0, second=0, microsecond=0)
        if slot_time > now:
            slots.append(slot_time.strftime("%I:%M %p"))
    if not slots:  # if today's slots are gone, show tomorrow's full range
        tomorrow = now + timedelta(days=1)
        slots = [
            tomorrow.replace(hour=h, minute=0).strftime("%d %b, %I:%M %p")
            for h in range(booking_cfg["slot_start_hour"], booking_cfg["slot_end_hour"])
        ]
    return slots[: booking_cfg["slots_per_day"]]


def start_booking(chat_id: int) -> str:
    _sessions[chat_id] = {"step": "ask_name", "data": {}}
    return "Sure! Let's book your appointment. What's your name?"


def is_booking_in_progress(chat_id: int) -> bool:
    return chat_id in _sessions


def handle_booking_step(chat_id: int, message: str, config: dict) -> str:
    session = _sessions[chat_id]
    step = session["step"]

    if step == "ask_name":
        session["data"]["name"] = message.strip()
        session["step"] = "ask_service"
        services = ", ".join(config["business"]["services"])
        return f"Thanks {message.strip()}! Which service do you need?\nOptions: {services}"

    if step == "ask_service":
        session["data"]["service"] = message.strip()
        session["step"] = "ask_slot"
        slots = available_slots(config)
        return "Pick a time slot:\n" + "\n".join(f"- {s}" for s in slots)

    if step == "ask_slot":
        session["data"]["slot"] = message.strip()
        session["step"] = "confirm"
        d = session["data"]
        return (f"Confirm booking?\nName: {d['name']}\nService: {d['service']}\n"
                f"Time: {d['slot']}\nReply YES to confirm or NO to cancel.")

    if step == "confirm":
        if message.strip().lower() in ("yes", "y", "haan", "confirm"):
            entry = {**session["data"], "chat_id": chat_id, "booked_at": datetime.now().isoformat()}
            _save_appointment(entry)
            del _sessions[chat_id]
            return "✅ Appointment booked! We'll see you then. Reply anytime if you need to reschedule."
        else:
            del _sessions[chat_id]
            return "No problem, booking cancelled. Let me know if you'd like to try again."

    # fallback safety
    del _sessions[chat_id]
    return "Something went wrong with the booking flow — let's start over. Type 'book' to try again."
