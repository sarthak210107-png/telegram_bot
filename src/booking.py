"""
Minimal appointment booking flow.

Session state (in-progress bookings) is kept in memory for speed, and mirrored
to data/sessions.json after every step so an in-progress conversation survives
a bot restart. Confirmed bookings are persisted to data/appointments.json.

Writes to both files are atomic (write to a temp file, then os.replace) and
guarded by a lock, so two near-simultaneous confirmations can't corrupt the
file or silently drop one booking.
"""
import json
import logging
import os
import tempfile
import threading
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)
APPOINTMENTS_FILE = DATA_DIR / "appointments.json"
SESSIONS_FILE = DATA_DIR / "sessions.json"

_file_lock = threading.Lock()

STEPS = ["ask_name", "ask_service", "ask_slot", "confirm"]


def _atomic_write_json(path: Path, data) -> None:
    """Write JSON to `path` atomically so a crash mid-write can't corrupt it."""
    fd, tmp_path = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp_path, path)
    except Exception:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise


def _load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.error("Failed to read %s, starting fresh: %s", path, e)
        return default


# ---- Session persistence (in-progress bookings) ----

_sessions: dict[int, dict] = {
    int(k): v for k, v in _load_json(SESSIONS_FILE, {}).items()
}


def _persist_sessions() -> None:
    with _file_lock:
        _atomic_write_json(SESSIONS_FILE, {str(k): v for k, v in _sessions.items()})


# ---- Appointments ----

def _load_appointments() -> list[dict]:
    return _load_json(APPOINTMENTS_FILE, [])


def _save_appointment(entry: dict) -> None:
    with _file_lock:
        appointments = _load_json(APPOINTMENTS_FILE, [])
        appointments.append(entry)
        _atomic_write_json(APPOINTMENTS_FILE, appointments)


def _booked_slots_today() -> set[str]:
    """Slots already taken today, so available_slots() doesn't double-book them."""
    today = datetime.now().date().isoformat()
    booked = set()
    for appt in _load_appointments():
        booked_at = appt.get("booked_at", "")
        if booked_at.startswith(today):
            booked.add(appt.get("slot", ""))
    return booked


def available_slots(config: dict) -> list[str]:
    """Generate today's remaining hourly slots based on config booking hours,
    excluding slots that are already booked."""
    booking_cfg = config["booking"]
    now = datetime.now()
    taken = _booked_slots_today()
    slots = []
    for hour in range(booking_cfg["slot_start_hour"], booking_cfg["slot_end_hour"]):
        slot_time = now.replace(hour=hour, minute=0, second=0, microsecond=0)
        if slot_time > now:
            label = slot_time.strftime("%I:%M %p")
            if label not in taken:
                slots.append(label)
    if not slots:  # if today's slots are gone or full, show tomorrow's full range
        tomorrow = now + timedelta(days=1)
        slots = [
            tomorrow.replace(hour=h, minute=0).strftime("%d %b, %I:%M %p")
            for h in range(booking_cfg["slot_start_hour"], booking_cfg["slot_end_hour"])
        ]
    return slots[: booking_cfg["slots_per_day"]]


# ---- Booking state machine ----

def start_booking(chat_id: int) -> str:
    _sessions[chat_id] = {"step": "ask_name", "data": {}}
    _persist_sessions()
    return "Sure! Let's book your appointment. What's your name?"


def is_booking_in_progress(chat_id: int) -> bool:
    return chat_id in _sessions


def _cancel_session(chat_id: int) -> None:
    _sessions.pop(chat_id, None)
    _persist_sessions()


def handle_booking_step(chat_id: int, message: str, config: dict) -> str:
    session = _sessions[chat_id]
    step = session["step"]
    text = message.strip()

    if step == "ask_name":
        if not text:
            return "That doesn't look like a name — what should we put down for you?"
        session["data"]["name"] = text
        session["step"] = "ask_service"
        _persist_sessions()
        services = ", ".join(config["business"]["services"])
        return f"Thanks {text}! Which service do you need?\nOptions: {services}"

    if step == "ask_service":
        valid_services = config["business"]["services"]
        match = next((s for s in valid_services if s.lower() == text.lower()), None)
        if match is None:
            # allow partial/substring match too, e.g. "cleaning" -> "Teeth Cleaning"
            match = next((s for s in valid_services if text.lower() in s.lower()), None)
        if match is None:
            services = ", ".join(valid_services)
            return f"Sorry, I didn't recognize that service. Please pick one of: {services}"
        session["data"]["service"] = match
        session["step"] = "ask_slot"
        _persist_sessions()
        slots = available_slots(config)
        if not slots:
            _cancel_session(chat_id)
            return "Sorry, there are no slots available right now. Please try again later or call us directly."
        return "Pick a time slot:\n" + "\n".join(f"- {s}" for s in slots)

    if step == "ask_slot":
        valid_slots = set(available_slots(config))
        if text not in valid_slots:
            slots = "\n".join(f"- {s}" for s in valid_slots)
            return f"Please pick one of the exact slots below:\n{slots}"
        session["data"]["slot"] = text
        session["step"] = "confirm"
        _persist_sessions()
        d = session["data"]
        return (f"Confirm booking?\nName: {d['name']}\nService: {d['service']}\n"
                f"Time: {d['slot']}\nReply YES to confirm or NO to cancel.")

    if step == "confirm":
        if text.lower() in ("yes", "y", "haan", "confirm"):
            # Re-check the slot hasn't been taken by someone else since we asked
            if session["data"]["slot"] in _booked_slots_today():
                _cancel_session(chat_id)
                return "Sorry, that slot was just taken by someone else. Type 'book' to pick another."
            entry = {**session["data"], "chat_id": chat_id, "booked_at": datetime.now().isoformat()}
            _save_appointment(entry)
            _cancel_session(chat_id)
            logger.info("Booking confirmed for chat_id=%s: %s", chat_id, entry)
            return "✅ Appointment booked! We'll see you then. Reply anytime if you need to reschedule."
        else:
            _cancel_session(chat_id)
            return "No problem, booking cancelled. Let me know if you'd like to try again."

    # fallback safety
    logger.warning("Unknown booking step '%s' for chat_id=%s, resetting session", step, chat_id)
    _cancel_session(chat_id)
    return "Something went wrong with the booking flow — let's start over. Type 'book' to try again."
