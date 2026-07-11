import os
import sys
import eel
import pyttsx3
import datetime
import asyncio
import ctypes
import html
import json
import logging
import math
import re
import sqlite3
import struct
import speech_recognition as sr
import wikipedia
import webbrowser
import subprocess
import pyautogui
import pywhatkit
import time
import tempfile
import requests
from logging.handlers import RotatingFileHandler
from urllib.parse import parse_qs, quote_plus, unquote, urlparse
try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None
try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None
try:
    import tkinter as tk
except ImportError:
    tk = None
try:
    import edge_tts
except ImportError:
    edge_tts = None
try:
    import psutil
except ImportError:
    psutil = None
try:
    import GPUtil
except ImportError:
    GPUtil = None
try:
    import pystray
    from PIL import Image, ImageDraw
except ImportError:
    pystray = None
    Image = None
    ImageDraw = None
try:
    import win32con
    import win32gui
except ImportError:
    win32con = None
    win32gui = None
from pathlib import Path
from queue import Empty, Queue
from threading import Event, Lock, Thread

APP_ROOT = Path(__file__).resolve().parent
LOG_DIR = APP_ROOT / "logs"
LOG_PATH = LOG_DIR / "kabir.log"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    handlers=[
        RotatingFileHandler(LOG_PATH, maxBytes=1_000_000, backupCount=5, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("kabir")

if load_dotenv is not None:
    load_dotenv(APP_ROOT / ".env")

# Allow imports from engine/auth
sys.path.insert(0, os.path.dirname(__file__))
from engine.auth        import recognize as recoganize
from engine.contact_store import (
    delete_contact as delete_saved_contact,
    get_email_address,
    get_phone_number,
    list_contacts,
    save_contact as save_saved_contact,
)
from engine.email_sender import (
    build_qsb_subject,
    get_profile_status,
    load_mail_profile,
    save_mail_profile,
    send_email,
)
from engine.message_sender import normalize_platform, normalize_whatsapp_mode, send_platform_message
from engine.settings_store import load_settings, save_settings
from engine.phone_controller import (
    answer_call,
    connect_wireless_adb,
    end_call,
    extract_phone_number,
    make_call,
    normalize_contact_name,
    pair_wireless_adb,
    setup_wireless_adb,
)
from engine.spotify_controller import (
    control_spotify,
    extract_spotify_query,
    normalize_spotify_action,
)
from skills import SkillContext, dispatch_skill, get_skill_examples

# ─── Init ──────────────────────────────────────────────────────────────────────
eel.init("www")

engine = pyttsx3.init()
voices = engine.getProperty('voices')
engine.setProperty('voice', voices[0].id)
engine.setProperty('rate', 175)

# ─── Phonebook ─────────────────────────────────────────────────────────────────
TEXT_REPLY_QUEUE = Queue()
TEXT_CAPTURE_LOCK = Lock()
CAPTURE_TEXT_REPLY = False
HISTORY_DB_LOCK = Lock()
HISTORY_DB_PATH = APP_ROOT / "kabir_history.sqlite3"
VOICE_INPUT_LOCK = Lock()
TTS_LOCK = Lock()
WAKE_WORD_STOP = Event()
WAKE_WORD_THREAD = None
WAKE_WORD_PHRASE = os.environ.get("KABIR_WAKE_WORD", "Hey Kabir").strip() or "Hey Kabir"
PORCUPINE_ACCESS_KEY = os.environ.get("KABIR_PICOVOICE_ACCESS_KEY", "").strip()
PORCUPINE_KEYWORD_PATH = os.environ.get("KABIR_PORCUPINE_KEYWORD_PATH", "").strip()
PORCUPINE_BUILTIN_KEYWORD = os.environ.get("KABIR_PORCUPINE_BUILTIN_KEYWORD", "kabir").strip().lower() or "kabir"
PORCUPINE_SENSITIVITY = os.environ.get("KABIR_PORCUPINE_SENSITIVITY", "0.65").strip()
APP_HOST = "localhost"
APP_PORT = 8000
APP_PAGE = "index.html"
APP_URL = f"http://{APP_HOST}:{APP_PORT}/{APP_PAGE}"
TRAY_ICON = None
TELEMETRY_STOP = Event()
TELEMETRY_THREAD = None
TELEMETRY_ALERT_LAST = {}
TELEMETRY_ALERT_COOLDOWN = 180
TELEMETRY_RAM_CLOSE_ACTIVE = False
LATEST_TELEMETRY = {}
LAST_ACTIVE_TASK = "STANDBY"
HUD_STOP = Event()
HUD_THREAD = None
POWER_ACTION_LOCK = Lock()
POWER_ACTION_CANCEL = Event()
POWER_ACTION_ACTIVE = False
POWER_ACTION_KIND = ""
POWER_ACTION_DEADLINE = 0.0
TTS_ENGINE_MODE = os.environ.get("KABIR_TTS_ENGINE", "neural").strip().lower()
# NEURAL_TTS_VOICE = os.environ.get("KABIR_TTS_VOICE", "en-GB-RyanNeural").strip() or "en-GB-RyanNeural"
NEURAL_TTS_VOICE = os.environ.get("KABIR_TTS_VOICE", "en-IN-PrabhatNeural").strip() or "en-IN-PrabhatNeural"
NEURAL_TTS_RATE = os.environ.get("KABIR_TTS_RATE", "+20%").strip() or "20%"
NEURAL_TTS_AVAILABLE = edge_tts is not None
OPENWEATHER_API_KEY = os.environ.get("OPENWEATHER_API_KEY", "").strip()
USER_HOME = Path.home().resolve()
DEFAULT_SAFE_FILE_ROOTS = tuple(
    root.resolve()
    for root in (
        APP_ROOT,
        USER_HOME,
        USER_HOME / "Desktop",
        USER_HOME / "Documents",
        USER_HOME / "Downloads",
        USER_HOME / "Pictures",
        USER_HOME / "Music",
        USER_HOME / "Videos",
    )
    if root.exists()
)

COMMON_EMAIL_FIXES = {
    "gmail": "gmail.com",
    "googlemail": "googlemail.com",
    "yahoo": "yahoo.com",
    "outlook": "outlook.com",
    "hotmail": "hotmail.com",
    "icloud": "icloud.com",
    "featsystems": "featsystems.com",
    "featsystems.com": "featsystems.com",
    "feat systems": "featsystems.com",
    "whichsystems": "featsystems.com",
    "whichsystems.com": "featsystems.com",
    "which systems": "featsystems.com",
    "feet systems": "featsystems.com",
}

COMMON_LOCAL_FIXES = {
    "hellodesai": "aalok.desai",
    "alokdesai": "aalok.desai",
    "aalokdesai": "aalok.desai",
}

SPOKEN_EMAIL_TOKENS = {
    " at the rate ": "@",
    " attherate ": "@",
    " at rate ": "@",
    " at ": "@",
    " dot ": ".",
    " period ": ".",
    " full stop ": ".",
    " underscore ": "_",
    " under score ": "_",
    " dash ": "-",
    " hyphen ": "-",
    " minus ": "-",
    " plus ": "+",
}

CANCEL_WORDS = {"cancel", "stop", "abort", "never mind", "nevermind"}

FILE_SEARCH_EXCLUDED_DIRS = {
    "$Recycle.Bin",
    ".git",
    "__pycache__",
    "AppData",
    "node_modules",
    "Program Files",
    "Program Files (x86)",
    "System Volume Information",
    "Windows",
}

FILE_SEARCH_INTENT_WORDS = (
    "find file",
    "find a file",
    "search file",
    "search files",
    "search for file",
    "locate file",
    "look for file",
    "show file",
    "open file",
    "where is file",
)

# ─── TTS & UI helpers ──────────────────────────────────────────────────────────
def get_history_connection():
    conn = sqlite3.connect(HISTORY_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_history_db():
    with HISTORY_DB_LOCK, get_history_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS command_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                command TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'unknown',
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS conversation_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                speaker TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS knowledge_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                body TEXT NOT NULL DEFAULT '',
                url TEXT NOT NULL DEFAULT '',
                source TEXT NOT NULL DEFAULT 'manual',
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_command_history_created ON command_history(created_at DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_conversation_history_created ON conversation_history(created_at DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_command_history_command ON command_history(command)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_conversation_history_message ON conversation_history(message)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_knowledge_entries_created ON knowledge_entries(created_at DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_knowledge_entries_title ON knowledge_entries(title)")

def history_timestamp():
    return datetime.datetime.now().isoformat(timespec="seconds")

def get_history_retention_settings():
    settings = load_settings()
    return settings["history_max_items"], settings["history_retention_days"]

def prune_history_table(conn, table_name, max_items, retention_days):
    cutoff = (datetime.datetime.now() - datetime.timedelta(days=retention_days)).isoformat(timespec="seconds")
    conn.execute(f"DELETE FROM {table_name} WHERE created_at < ?", (cutoff,))
    conn.execute(
        f"""
        DELETE FROM {table_name}
        WHERE id NOT IN (
            SELECT id FROM {table_name}
            ORDER BY created_at DESC, id DESC
            LIMIT ?
        )
        """,
        (max_items,),
    )

def apply_history_retention():
    try:
        max_items, retention_days = get_history_retention_settings()
        with HISTORY_DB_LOCK, get_history_connection() as conn:
            prune_history_table(conn, "command_history", max_items, retention_days)
            prune_history_table(conn, "conversation_history", max_items, retention_days)
    except sqlite3.Error:
        pass

def save_command_history(command, source="text"):
    command = (command or "").strip()
    if not command:
        return
    try:
        with HISTORY_DB_LOCK, get_history_connection() as conn:
            conn.execute(
                "INSERT INTO command_history (command, source, created_at) VALUES (?, ?, ?)",
                (command, source, history_timestamp()),
            )
            prune_history_table(conn, "command_history", *get_history_retention_settings())
    except sqlite3.Error:
        pass

def save_conversation_history(speaker, message):
    message = (message or "").strip()
    if not message:
        return
    try:
        with HISTORY_DB_LOCK, get_history_connection() as conn:
            conn.execute(
                "INSERT INTO conversation_history (speaker, message, created_at) VALUES (?, ?, ?)",
                (speaker, message, history_timestamp()),
            )
            prune_history_table(conn, "conversation_history", *get_history_retention_settings())
    except sqlite3.Error:
        pass


def save_knowledge_entry(title, body="", url="", source="manual"):
    title = (title or "").strip()
    body = (body or "").strip()
    url = (url or "").strip()
    if not title and not body and not url:
        return
    try:
        with HISTORY_DB_LOCK, get_history_connection() as conn:
            conn.execute(
                """
                INSERT INTO knowledge_entries (title, body, url, source, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (title or compact_agent_text(body or url, 120), body, url, source or "manual", history_timestamp()),
            )
    except sqlite3.Error:
        pass

init_history_db()
apply_history_retention()


def parse_memory_date_window(text):
    text = (text or "").lower()
    now = datetime.datetime.now()
    today = now.date()

    if "yesterday" in text:
        day = today - datetime.timedelta(days=1)
        return day.isoformat(), (day + datetime.timedelta(days=1)).isoformat(), "yesterday"
    if "today" in text:
        return today.isoformat(), (today + datetime.timedelta(days=1)).isoformat(), "today"
    if "this week" in text:
        start = today - datetime.timedelta(days=today.weekday())
        return start.isoformat(), (start + datetime.timedelta(days=7)).isoformat(), "this week"
    if "last week" in text:
        start = today - datetime.timedelta(days=today.weekday() + 7)
        return start.isoformat(), (start + datetime.timedelta(days=7)).isoformat(), "last week"

    weekdays = {
        "monday": 0,
        "tuesday": 1,
        "wednesday": 2,
        "thursday": 3,
        "friday": 4,
        "saturday": 5,
        "sunday": 6,
    }
    for name, weekday in weekdays.items():
        if f"last {name}" in text:
            days_back = (today.weekday() - weekday) % 7 or 7
            day = today - datetime.timedelta(days=days_back)
            return day.isoformat(), (day + datetime.timedelta(days=1)).isoformat(), f"last {name}"
        if name in text:
            days_back = (today.weekday() - weekday) % 7 
            day = today - datetime.timedelta(days=days_back)
            return day.isoformat(), (day + datetime.timedelta(days=1)).isoformat(), name

    match = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", text)
    if match:
        day = datetime.date.fromisoformat(match.group(1))
        return day.isoformat(), (day + datetime.timedelta(days=1)).isoformat(), match.group(1)

    return None, None, ""


def extract_memory_query(command):
    query = re.sub(
        r"\b(kabir|memory|history|knowledge base|personal knowledge base|conversation memory|search|find|look up|lookup|remember|recall|what did i|what was|show me|tell me|about|research|researched|ask|asked|say|said|open|visit|visited|read|last|this|today|yesterday|week|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
        " ",
        (command or "").lower(),
    )
    query = re.sub(r"\b\d{4}-\d{2}-\d{2}\b", " ", query)
    query = re.sub(r"[^a-z0-9 ._-]+", " ", query)
    return re.sub(r"\s+", " ", query).strip()


def is_memory_query(command):
    text = (command or "").lower().strip()
    if not text:
        return False
    triggers = (
        "knowledge base",
        "memory",
        "conversation memory",
        "command history",
        "search history",
        "what did i research",
        "what did i ask",
        "what did i read",
        "what was that article",
        "recall",
        "remember",
    )
    return any(trigger in text for trigger in triggers)


def search_memory_records(query="", start_date=None, end_date=None, limit=12, exclude_text=""):
    try:
        max_rows = max(1, min(int(limit or 12), 50))
    except (TypeError, ValueError):
        max_rows = 12

    query = (query or "").strip()
    filters = []
    params = []
    if start_date and end_date:
        filters.append("created_at >= ? AND created_at < ?")
        params.extend([start_date, end_date])
    if query:
        like = f"%{query}%"
        filters.append("searchable LIKE ?")
        params.append(like)
    if exclude_text:
        filters.append("LOWER(body) != LOWER(?)")
        params.append(exclude_text)
    where = "WHERE " + " AND ".join(filters) if filters else ""

    sql = f"""
        SELECT kind, id, title, body, url, source, created_at
        FROM (
            SELECT 'command' AS kind, id, 'Command' AS title, command AS body, '' AS url,
                   command AS searchable, source, created_at
            FROM command_history
            UNION ALL
            SELECT 'message' AS kind, id, speaker AS title, message AS body, '' AS url,
                   message AS searchable, speaker AS source, created_at
            FROM conversation_history
            UNION ALL
            SELECT 'knowledge' AS kind, id, title, body, url,
                   title || ' ' || body || ' ' || url AS searchable, source, created_at
            FROM knowledge_entries
        )
        {where}
        ORDER BY created_at DESC, id DESC
        LIMIT ?
    """
    try:
        with HISTORY_DB_LOCK, get_history_connection() as conn:
            return [dict(row) for row in conn.execute(sql, (*params, max_rows))]
    except sqlite3.Error:
        return []


def summarize_memory_results(command, records, date_label="", query=""):
    if not records:
        if date_label and query:
            return f"I found no memory entries for {query} from {date_label}."
        if date_label:
            return f"I found no memory entries from {date_label}."
        if query:
            return f"I found no memory entries matching {query}."
        return "I found no matching memory entries."

    lines = []
    for i, item in enumerate(records[:10], 1):
        lines.append(
            f"{i}. [{item.get('created_at', '')}] {item.get('title', '')}: "
            f"{compact_agent_text(item.get('body', ''), 220)}"
        )

    prompt = (
        "You are Kabir. Answer the user's memory question using only these saved local "
        "commands and conversation records. Be concise, mention dates when useful, and do not invent.\n\n"
        f"Question: {command}\n\nMemory records:\n" + "\n".join(lines)
    )
    answer = ask_ollama(prompt, max_tokens=220)
    if answer:
        return compact_agent_text(answer, 650)

    intro = "I found these memory entries"
    if date_label:
        intro += f" from {date_label}"
    if query:
        intro += f" matching {query}"
    first = "; ".join(
        f"{format_memory_time(item.get('created_at'))}: {compact_agent_text(item.get('body', ''), 90)}"
        for item in records[:4]
    )
    return f"{intro}: {first}"


def format_memory_time(value):
    try:
        return datetime.datetime.fromisoformat(str(value)).strftime("%b %d, %I:%M %p")
    except (TypeError, ValueError):
        return str(value or "")


def answer_memory_query(command):
    start_date, end_date, date_label = parse_memory_date_window(command)
    query = extract_memory_query(command)
    records = search_memory_records(query=query, start_date=start_date, end_date=end_date, limit=14, exclude_text=command)
    if not records and query:
        records = search_memory_records(query="", start_date=start_date, end_date=end_date, limit=14, exclude_text=command)
    speak(summarize_memory_results(command, records, date_label=date_label, query=query))
    set_status("Ready.")

def call_ui(function_name, *args):
    """Best-effort browser UI update; tray mode may run with no page attached."""
    try:
        getattr(eel, function_name)(*args)()
    except Exception as e:
        logger.debug("UI call failed: %s(%s): %s", function_name, len(args), e)

async def save_neural_tts(text, output_path):
    communicate = edge_tts.Communicate(text, NEURAL_TTS_VOICE, rate=NEURAL_TTS_RATE)
    await communicate.save(output_path)

def play_windows_audio(path):
    alias = f"kabir_tts_{int(time.time() * 1000)}"
    winmm = ctypes.windll.winmm
    open_cmd = f'open "{path}" type mpegvideo alias {alias}'
    if winmm.mciSendStringW(open_cmd, None, 0, None) != 0:
        return False
    try:
        winmm.mciSendStringW(f"play {alias} wait", None, 0, None)
        return True
    finally:
        winmm.mciSendStringW(f"close {alias}", None, 0, None)

def speak_with_neural_voice(text):
    if TTS_ENGINE_MODE not in {"neural", "edge"} or not NEURAL_TTS_AVAILABLE:
        return False
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(prefix="kabir_tts_", suffix=".mp3", delete=False) as temp_file:
            temp_path = temp_file.name
        asyncio.run(save_neural_tts(text, temp_path))
        return play_windows_audio(temp_path)
    except Exception:
        return False
    finally:
        if temp_path:
            try:
                os.remove(temp_path)
            except OSError:
                pass

def speak(text):
    save_conversation_history("Kabir", text)
    with TTS_LOCK:
        if not speak_with_neural_voice(text):
            engine.say(text)
            engine.runAndWait()
    call_ui("addMessage", "Kabir", text)

def set_status(text):
    call_ui("setStatus", text)

def notify_ui(type_, title, detail=""):
    call_ui("pushNotification", type_, title, detail)

def update_shutdown_ui(action="", seconds=0, active=False):
    call_ui("updateShutdownCountdown", action, int(max(0, seconds)), bool(active))

def add_user_msg(text):
    global LAST_ACTIVE_TASK
    LAST_ACTIVE_TASK = (text or "").strip()[:64].upper() or "STANDBY"
    save_conversation_history("You", text)
    call_ui("addMessage", "You", text)

def cleanup_background_services():
    TELEMETRY_STOP.set()
    HUD_STOP.set()
    stop_wake_word_detection()

def graceful_app_shutdown(exit_code=0):
    logger.info("Kabir backend shutdown requested")
    cleanup_background_services()
    try:
        if TRAY_ICON:
            TRAY_ICON.visible = False
            TRAY_ICON.stop()
    except Exception:
        logger.exception("Tray shutdown cleanup failed")
    raise SystemExit(exit_code)

def power_action_worker(action, delay_seconds):
    global POWER_ACTION_ACTIVE, POWER_ACTION_KIND, POWER_ACTION_DEADLINE
    logger.warning("Scheduled %s in %s seconds", action, delay_seconds)
    notify_ui("system", f"{action.title()} scheduled", f"Cancel within {delay_seconds} seconds.")
    try:
        for remaining in range(delay_seconds, 0, -1):
            if POWER_ACTION_CANCEL.is_set():
                logger.info("Cancelled scheduled %s", action)
                update_shutdown_ui(action, 0, False)
                notify_ui("system", f"{action.title()} cancelled", "Power action was cancelled.")
                return
            update_shutdown_ui(action, remaining, True)
            time.sleep(1)

        update_shutdown_ui(action, 0, False)
        flag = "/r" if action == "restart" else "/s"
        logger.warning("Executing Windows %s now", action)
        subprocess.Popen(["shutdown", flag, "/t", "0"])
    finally:
        with POWER_ACTION_LOCK:
            POWER_ACTION_ACTIVE = False
            POWER_ACTION_KIND = ""
            POWER_ACTION_DEADLINE = 0.0
            POWER_ACTION_CANCEL.clear()

def schedule_power_action(action, delay_seconds=30):
    global POWER_ACTION_ACTIVE, POWER_ACTION_KIND, POWER_ACTION_DEADLINE
    action = "restart" if action == "restart" else "shutdown"
    with POWER_ACTION_LOCK:
        if POWER_ACTION_ACTIVE:
            remaining = max(0, int(POWER_ACTION_DEADLINE - time.time()))
            return {
                "success": False,
                "message": f"{POWER_ACTION_KIND.title()} is already scheduled.",
                "action": POWER_ACTION_KIND,
                "seconds": remaining,
            }
        POWER_ACTION_ACTIVE = True
        POWER_ACTION_KIND = action
        POWER_ACTION_DEADLINE = time.time() + delay_seconds
        POWER_ACTION_CANCEL.clear()

    Thread(target=power_action_worker, args=(action, delay_seconds), daemon=True).start()
    update_shutdown_ui(action, delay_seconds, True)
    return {
        "success": True,
        "message": f"{action.title()} scheduled. You can cancel within {delay_seconds} seconds.",
        "action": action,
        "seconds": delay_seconds,
    }

def cancel_power_action():
    with POWER_ACTION_LOCK:
        if not POWER_ACTION_ACTIVE:
            update_shutdown_ui("", 0, False)
            return {"success": False, "message": "No shutdown or restart is scheduled."}
        action = POWER_ACTION_KIND
        POWER_ACTION_CANCEL.set()
    logger.info("Cancel requested for scheduled %s", action)
    return {"success": True, "message": f"{action.title()} cancelled."}

def clamp_percent(value):
    try:
        return max(0, min(100, round(float(value), 1)))
    except (TypeError, ValueError):
        return 0

def bytes_per_second_label(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        value = 0
    units = ("B/s", "KB/s", "MB/s", "GB/s")
    index = 0
    while value >= 1024 and index < len(units) - 1:
        value /= 1024
        index += 1
    if index == 0:
        return f"{int(value)} {units[index]}"
    return f"{value:.1f} {units[index]}"

def get_cpu_temperature():
    if psutil is None or not hasattr(psutil, "sensors_temperatures"):
        return None
    try:
        temps = psutil.sensors_temperatures(fahrenheit=False) or {}
    except Exception:
        return None
    preferred_names = ("coretemp", "k10temp", "cpu_thermal", "acpitz")
    entries = []
    for name in preferred_names:
        entries.extend(temps.get(name, []))
    if not entries:
        for sensor_entries in temps.values():
            entries.extend(sensor_entries)
    readings = [
        entry.current
        for entry in entries
        if getattr(entry, "current", None) is not None and entry.current > 0
    ]
    return round(max(readings), 1) if readings else None

def get_gpu_stats():
    if GPUtil is None:
        return {"available": False, "name": "GPU", "load": 0, "memory": 0, "temperature": None}
    try:
        gpus = GPUtil.getGPUs()
    except Exception:
        gpus = []
    if not gpus:
        return {"available": False, "name": "GPU", "load": 0, "memory": 0, "temperature": None}
    gpu = gpus[0]
    return {
        "available": True,
        "name": getattr(gpu, "name", "GPU") or "GPU",
        "load": clamp_percent((getattr(gpu, "load", 0) or 0) * 100),
        "memory": clamp_percent(getattr(gpu, "memoryUtil", 0) * 100),
        "temperature": getattr(gpu, "temperature", None),
    }

def build_telemetry_snapshot(previous_net=None, previous_time=None):
    now = time.time()
    if psutil is None:
        return {
            "available": False,
            "message": "Install psutil and GPUtil for live telemetry.",
            "updatedAt": datetime.datetime.now().strftime("%H:%M:%S"),
        }, None, now

    cpu = clamp_percent(psutil.cpu_percent(interval=None))
    ram = psutil.virtual_memory()
    disk_root = Path.home().anchor or str(Path(__file__).resolve().anchor) or os.getcwd()
    try:
        disk = psutil.disk_usage(disk_root)
        disk_percent = clamp_percent(disk.percent)
    except Exception:
        disk_percent = 0

    try:
        net = psutil.net_io_counters()
    except Exception:
        net = None
    elapsed = max(0.1, now - previous_time) if previous_time else 1
    if net and previous_net:
        up_rate = max(0, (net.bytes_sent - previous_net.bytes_sent) / elapsed)
        down_rate = max(0, (net.bytes_recv - previous_net.bytes_recv) / elapsed)
    else:
        up_rate = 0
        down_rate = 0

    gpu = get_gpu_stats()
    cpu_temp = get_cpu_temperature()
    gpu_temp = gpu.get("temperature")

    snapshot = {
        "available": True,
        "updatedAt": datetime.datetime.now().strftime("%H:%M:%S"),
        "cpu": {"label": "CPU", "value": cpu, "temperature": cpu_temp},
        "gpu": gpu,
        "ram": {"label": "RAM", "value": clamp_percent(ram.percent)},
        "disk": {"label": "DISK", "value": disk_percent},
        "network": {
            "label": "NET",
            "up": round(up_rate, 1),
            "down": round(down_rate, 1),
            "upLabel": bytes_per_second_label(up_rate),
            "downLabel": bytes_per_second_label(down_rate),
            "value": clamp_percent(min(100, ((up_rate + down_rate) / (8 * 1024 * 1024)) * 100)),
        },
    }
    return snapshot, net, now

def should_send_telemetry_alert(key):
    last_sent = TELEMETRY_ALERT_LAST.get(key, 0)
    now = time.time()
    if now - last_sent < TELEMETRY_ALERT_COOLDOWN:
        return False
    TELEMETRY_ALERT_LAST[key] = now
    return True

def wants_app_cleanup(reply):
    text = (reply or "").lower()
    if is_cancel_reply(text):
        return False
    return any(word in text for word in ("yes", "yeah", "sure", "ok", "okay", "close", "kill", "terminate"))

def extract_app_close_names(text):
    text = (text or "").lower().strip()
    text = re.sub(
        r"\b(kabir|please|yes|yeah|sure|ok|okay|can you|could you|would you|close|kill|terminate|shutdown|shut down|all|unused|apps?|applications?|programs?|processes?|for me|sir)\b",
        " ",
        text,
    )
    text = re.sub(r"\b(and|plus|also|then)\b", ",", text)
    parts = [part.strip(" .,:;\"'") for part in text.split(",")]
    return [part for part in parts if part]

def normalize_app_query(name):
    text = re.sub(r"[^a-z0-9]+", "", (name or "").lower())
    aliases = {
        "visualstudiocode": "code",
        "vscode": "code",
        "googlechrome": "chrome",
        "microsoftedge": "msedge",
        "edge": "msedge",
        "notepad": "notepad",
        "paint": "mspaint",
    }
    return aliases.get(text, text)

def process_matches_app(process, app_name):
    target = normalize_app_query(app_name)
    if not target:
        return False
    fields = []
    for getter in (process.name, process.exe):
        try:
            fields.append(getter() or "")
        except (psutil.Error, OSError):
            pass
    try:
        fields.extend(process.cmdline() or [])
    except (psutil.Error, OSError):
        pass
    for value in fields:
        normalized = re.sub(r"[^a-z0-9]+", "", str(value).lower())
        if target and target in normalized:
            return True
    return False

def close_named_apps(app_names):
    if psutil is None:
        return {"closed": [], "not_found": app_names, "failed": {"psutil": "psutil is not installed"}}

    current_pid = os.getpid()
    protected = {
        "system", "registry", "smss.exe", "csrss.exe", "wininit.exe", "winlogon.exe",
        "services.exe", "lsass.exe", "svchost.exe", "fontdrvhost.exe", "dwm.exe",
    }
    closed = []
    failed = {}
    not_found = []

    for app_name in app_names:
        matches = []
        for process in psutil.process_iter(["pid", "name"]):
            pid = process.info.get("pid")
            proc_name = (process.info.get("name") or "").lower()
            if pid == current_pid or proc_name in protected:
                continue
            try:
                if process_matches_app(process, app_name):
                    matches.append(process)
            except (psutil.Error, OSError):
                continue

        if not matches:
            not_found.append(app_name)
            continue

        for process in matches:
            label = process.info.get("name") or app_name
            try:
                process.terminate()
                closed.append(label)
            except (psutil.Error, OSError) as exc:
                failed[label] = str(exc)

        alive = []
        if matches:
            gone, alive = psutil.wait_procs(matches, timeout=3)
            for process in alive:
                label = process.info.get("name") or app_name
                try:
                    process.kill()
                    closed.append(label)
                except (psutil.Error, OSError) as exc:
                    failed[label] = str(exc)

    unique_closed = []
    for name in closed:
        if name not in unique_closed:
            unique_closed.append(name)
    return {"closed": unique_closed, "not_found": not_found, "failed": failed}

def speak_app_close_result(result):
    closed = result.get("closed", [])
    not_found = result.get("not_found", [])
    failed = result.get("failed", {})
    if closed:
        speak(f"Closed {', '.join(closed)}.")
    if not_found:
        speak(f"I could not find {', '.join(not_found)}.")
    if failed and not closed:
        speak("I found the app, but Windows would not let me close it.")
    if not closed and not not_found and not failed:
        speak("I did not find any matching apps to close.")

def handle_ram_cleanup_prompt(ram):
    global TELEMETRY_RAM_CLOSE_ACTIVE
    if TELEMETRY_RAM_CLOSE_ACTIVE:
        return
    TELEMETRY_RAM_CLOSE_ACTIVE = True
    try:
        speak(f"RAM usage is at {round(ram)} percent, sir. Would you like me to close unused apps?")
        reply = listen_for_reply("Waiting for RAM cleanup confirmation...").strip()
        if not wants_app_cleanup(reply):
            speak("Understood. I will leave your apps open.")
            return

        app_names = extract_app_close_names(reply)
        if not app_names:
            speak("Please tell me which apps you would like to close.")
            app_reply = listen_for_reply("Listening for app names to close...").strip()
            if is_cancel_reply(app_reply):
                speak("RAM cleanup cancelled.")
                return
            app_names = extract_app_close_names(app_reply)

        if not app_names:
            speak("I did not catch the app names. Please try again.")
            return

        speak_app_close_result(close_named_apps(app_names))
    finally:
        TELEMETRY_RAM_CLOSE_ACTIVE = False

def handle_telemetry_alerts(stats):
    if not stats.get("available"):
        return
    cpu_temp = stats.get("cpu", {}).get("temperature")
    gpu_temp = stats.get("gpu", {}).get("temperature")
    ram = stats.get("ram", {}).get("value", 0)

    if cpu_temp is not None and cpu_temp >= 89 and should_send_telemetry_alert("cpu_temp"):
        speak(f"Sir, CPU temperature is at {round(cpu_temp)} degrees.")
    if gpu_temp is not None and gpu_temp >= 89 and should_send_telemetry_alert("gpu_temp"):
        speak(f"Sir, GPU temperature is at {round(gpu_temp)} degrees.")
    if ram >= 90 and should_send_telemetry_alert("ram"):
        run_daemon(handle_ram_cleanup_prompt, ram)

def telemetry_loop():
    global LATEST_TELEMETRY
    previous_net = None
    previous_time = None
    if psutil is not None:
        try:
            psutil.cpu_percent(interval=None)
        except Exception:
            pass
    while not TELEMETRY_STOP.is_set():
        try:
            stats, previous_net, previous_time = build_telemetry_snapshot(previous_net, previous_time)
            LATEST_TELEMETRY = stats
            call_ui("updateStats", stats)
            handle_telemetry_alerts(stats)
        except Exception:
            pass
        TELEMETRY_STOP.wait(2)

def start_system_telemetry():
    global TELEMETRY_THREAD
    if TELEMETRY_THREAD and TELEMETRY_THREAD.is_alive():
        return
    TELEMETRY_STOP.clear()
    TELEMETRY_THREAD = run_daemon(telemetry_loop)

def telemetry_value(path, default=0):
    data = LATEST_TELEMETRY or {}
    for key in path:
        if not isinstance(data, dict):
            return default
        data = data.get(key)
    return default if data is None else data

class HolographicHUD:
    def __init__(self, stop_event):
        self.stop_event = stop_event
        self.bg = "#01070c"
        self.tick = 0
        self.root = tk.Tk()
        self.root.title("Kabir HUD")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.78)
        self.root.configure(bg=self.bg)
        try:
            self.root.wm_attributes("-transparentcolor", self.bg)
        except tk.TclError:
            pass

        width, height = 460, 280
        x = max(20, self.root.winfo_screenwidth() - width - 34)
        y = 34
        self.root.geometry(f"{width}x{height}+{x}+{y}")
        self.canvas = tk.Canvas(
            self.root,
            width=width,
            height=height,
            bg=self.bg,
            highlightthickness=0,
            bd=0,
        )
        self.canvas.pack(fill="both", expand=True)
        self.root.after(120, self.make_click_through)
        self.root.after(50, self.draw)

    def make_click_through(self):
        if win32gui is None or win32con is None:
            return
        try:
            hwnd = self.root.winfo_id()
            styles = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
            styles |= win32con.WS_EX_LAYERED | win32con.WS_EX_TRANSPARENT | win32con.WS_EX_TOOLWINDOW
            win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, styles)
        except Exception:
            pass

    def draw_arc_gauge(self, x, y, radius, value, label, color):
        value = max(0, min(100, float(value or 0)))
        self.canvas.create_oval(x-radius, y-radius, x+radius, y+radius, outline="#113044", width=2)
        self.canvas.create_arc(
            x-radius, y-radius, x+radius, y+radius,
            start=130, extent=280 * value / 100,
            style="arc", outline=color, width=5,
        )
        self.canvas.create_text(x, y-5, text=f"{round(value)}%", fill="#d7f7ff", font=("Orbitron", 13, "bold"))
        self.canvas.create_text(x, y+17, text=label, fill="#58d9ff", font=("Orbitron", 8))

    def draw(self):
        if self.stop_event.is_set():
            self.root.destroy()
            return

        self.tick += 1
        phase = self.tick / 12
        self.canvas.delete("all")
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        glow = "#00b4ff"
        amber = "#ff8a2a"

        self.canvas.create_rectangle(12, 12, w-12, h-12, outline="#155a78", width=1)
        self.canvas.create_line(28, 12, 108, 12, fill=glow, width=2)
        self.canvas.create_line(w-108, h-12, w-28, h-12, fill=glow, width=2)
        self.canvas.create_text(30, 34, anchor="w", text="KABIR HOLOGRAPHIC HUD", fill="#d7f7ff", font=("Orbitron", 12, "bold"))
        self.canvas.create_text(w-30, 34, anchor="e", text=datetime.datetime.now().strftime("%H:%M:%S"), fill=glow, font=("Orbitron", 14, "bold"))

        scan_y = 58 + (math.sin(phase) + 1) * 82
        self.canvas.create_line(24, scan_y, w-24, scan_y, fill="#0b7da8", width=1)
        for i in range(0, w, 22):
            alpha_color = "#073347" if (i + self.tick) % 44 else "#0d6688"
            self.canvas.create_line(i, 58, i + 80, h - 28, fill=alpha_color)

        cpu = telemetry_value(("cpu", "value"))
        gpu = telemetry_value(("gpu", "load"))
        ram = telemetry_value(("ram", "value"))
        disk = telemetry_value(("disk", "value"))
        net_down = telemetry_value(("network", "downLabel"), "--")
        net_up = telemetry_value(("network", "upLabel"), "--")
        cpu_temp = telemetry_value(("cpu", "temperature"), None)
        gpu_temp = telemetry_value(("gpu", "temperature"), None)

        self.draw_arc_gauge(76, 112, 38, cpu, "CPU", glow if cpu < 90 else amber)
        self.draw_arc_gauge(178, 112, 38, gpu, "GPU", glow if gpu < 90 else amber)
        self.draw_arc_gauge(280, 112, 38, ram, "RAM", glow if ram < 90 else amber)
        self.draw_arc_gauge(382, 112, 38, disk, "DSK", glow if disk < 90 else amber)

        task = LAST_ACTIVE_TASK or "STANDBY"
        self.canvas.create_rectangle(32, 178, w-32, 232, outline="#123f58", width=1)
        self.canvas.create_text(48, 194, anchor="w", text="ACTIVE TASK", fill="#58d9ff", font=("Orbitron", 8))
        self.canvas.create_text(48, 214, anchor="w", text=task[:46], fill="#d7f7ff", font=("Consolas", 13))
        self.canvas.create_text(w-48, 194, anchor="e", text=f"NET DOWN {net_down}", fill="#d7f7ff", font=("Consolas", 10))
        self.canvas.create_text(w-48, 214, anchor="e", text=f"NET UP {net_up}", fill="#d7f7ff", font=("Consolas", 10))

        cpu_temp_text = "--" if cpu_temp is None else f"{round(cpu_temp)}C"
        gpu_temp_text = "--" if gpu_temp is None else f"{round(float(gpu_temp))}C"
        self.canvas.create_text(34, 254, anchor="w", text=f"THERMAL CPU {cpu_temp_text}  GPU {gpu_temp_text}", fill="#8eeaff", font=("Consolas", 10))
        self.canvas.create_text(w-34, 254, anchor="e", text="CLICK-THROUGH ONLINE", fill="#38ffb0", font=("Orbitron", 8))
        self.root.after(90, self.draw)

    def run(self):
        self.root.mainloop()

def hud_loop():
    try:
        app = HolographicHUD(HUD_STOP)
        app.run()
    except Exception as e:
        call_ui("setStatus", f"HUD unavailable: {e}")

def show_holographic_hud():
    global HUD_THREAD
    if tk is None:
        speak("HUD overlay is unavailable because tkinter is not installed.")
        return False
    if HUD_THREAD and HUD_THREAD.is_alive():
        return True
    start_system_telemetry()
    HUD_STOP.clear()
    HUD_THREAD = Thread(target=hud_loop, daemon=True)
    HUD_THREAD.start()
    set_status("Holographic HUD online.")
    return True

def hide_holographic_hud():
    HUD_STOP.set()
    set_status("Holographic HUD hidden.")
    return True

def set_tts_engine(mode):
    global TTS_ENGINE_MODE
    mode = (mode or "").strip().lower()
    if mode in {"neural", "edge"}:
        TTS_ENGINE_MODE = "neural"
    elif mode in {"local", "offline", "pyttsx3"}:
        TTS_ENGINE_MODE = "local"
    else:
        return False
    return True

def get_tts_status():
    return {
        "mode": TTS_ENGINE_MODE,
        "neuralAvailable": NEURAL_TTS_AVAILABLE,
        "voice": NEURAL_TTS_VOICE,
        "rate": NEURAL_TTS_RATE,
    }

def set_text_capture(enabled):
    global CAPTURE_TEXT_REPLY
    with TEXT_CAPTURE_LOCK:
        CAPTURE_TEXT_REPLY = enabled

def is_text_capture_enabled():
    with TEXT_CAPTURE_LOCK:
        return CAPTURE_TEXT_REPLY

def drain_text_replies():
    while True:
        try:
            TEXT_REPLY_QUEUE.get_nowait()
        except Empty:
            return

def capture_or_process_text(text):
    text = text.strip()
    if not text:
        return
    if is_text_capture_enabled():
        add_user_msg(text)
        TEXT_REPLY_QUEUE.put(text)
        return
    process_command(text.lower(), source="text")

def listen_for_reply(status_text=None):
    """
    Accept the next reply from either the microphone or the chat box.
    Text box input is captured while a multi-step flow is active.
    """
    set_text_capture(True)
    try:
        if status_text:
            set_status(status_text)
        try:
            typed = TEXT_REPLY_QUEUE.get_nowait().strip()
            if typed:
                return typed
        except Empty:
            pass

        spoken = recognize_speech().strip()
        try:
            typed = TEXT_REPLY_QUEUE.get_nowait().strip()
            if typed:
                return typed
        except Empty:
            pass

        if spoken:
            add_user_msg(spoken)
            return spoken

        for _ in range(150):
            try:
                typed = TEXT_REPLY_QUEUE.get_nowait().strip()
                if typed:
                    return typed
            except Empty:
                eel.sleep(0.1)
        return ""
    finally:
        set_text_capture(False)

def is_cancel_reply(text):
    return text.strip().lower() in CANCEL_WORDS

def normalize_spoken_email(raw_text):
    """
    Convert typed or spoken email text into a real address.
    Handles phrases like "aalok dot desai at feat systems dot com".
    """
    text = f" {raw_text.strip().lower()} "
    if not text.strip():
        return ""

    contact_email = get_email_address(text.strip())
    if contact_email:
        return contact_email

    typed_match = re.search(r"[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}", text)
    if typed_match:
        return typed_match.group(0)

    text = re.sub(r"\s*@\s*", "@", text)
    text = re.sub(r"\s*\.\s*", ".", text)
    for spoken, symbol in SPOKEN_EMAIL_TOKENS.items():
        text = text.replace(spoken, symbol)

    text = re.sub(r"\bzero\b", "0", text)
    text = re.sub(r"\bone\b", "1", text)
    text = re.sub(r"\btwo\b", "2", text)
    text = re.sub(r"\bthree\b", "3", text)
    text = re.sub(r"\bfour\b", "4", text)
    text = re.sub(r"\bfive\b", "5", text)
    text = re.sub(r"\bsix\b", "6", text)
    text = re.sub(r"\bseven\b", "7", text)
    text = re.sub(r"\beight\b", "8", text)
    text = re.sub(r"\bnine\b", "9", text)

    text = text.replace(" ", "")
    text = re.sub(r"[^a-z0-9@._+\-]", "", text)
    text = re.sub(r"\.{2,}", ".", text).strip(".")

    if "@" in text:
        local, domain = text.split("@", 1)
        local = COMMON_LOCAL_FIXES.get(local, local)
        domain = COMMON_EMAIL_FIXES.get(domain, domain)
        text = f"{local}@{domain}"
    return text

def is_valid_email(email):
    return bool(re.fullmatch(r"[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}", email))

def extract_email_recipient(initial_command):
    text = (initial_command or "").strip().lower()
    if not text:
        return ""

    patterns = [
        r"^(?:please\s+)?(?:send|compose)\s+(?:an?\s+)?(?:email|mail)\s+to\s+(.+)$",
        r"^(?:please\s+)?(?:send|compose)\s+(?:an?\s+)?(?:email|mail)\s+(.+)$",
    ]
    for pattern in patterns:
        match = re.match(pattern, text)
        if match:
            recipient = match.group(1).strip()
            recipient = re.split(
                r"\b(?:subject|with subject|about|saying|that says|message|body)\b",
                recipient,
                maxsplit=1,
            )[0].strip(" .,:;-")
            return recipient
    return ""

# ─── Speech recognition ────────────────────────────────────────────────────────
def recognize_speech():
    recognizer = sr.Recognizer()
    try:
        with sr.Microphone() as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.5)
            set_status("Listening...")
            call_ui("setListening", True)
            audio = recognizer.listen(source, timeout=6, phrase_time_limit=8)
            set_status("Recognizing...")
            query = recognizer.recognize_google(audio).lower()
            set_status(f"You said: {query}")
            call_ui("setListening", False)
            return query
    except sr.WaitTimeoutError:
        set_status("No speech detected.")
    except sr.UnknownValueError:
        set_status("Couldn't understand. Try again.")
    except sr.RequestError:
        set_status("Speech service unavailable.")
    except Exception as e:
        set_status(f"Error: {str(e)[:30]}")
    call_ui("setListening", False)
    return ""

def run_voice_command(source="voice", wake_ack=False):
    if not VOICE_INPUT_LOCK.acquire(blocking=False):
        set_status("Voice input already active.")
        return
    try:
        if wake_ack:
            speak("Yes sir?")
        command = recognize_speech()
        if command:
            process_command(command, source=source)
        else:
            set_status("Wake word active." if source == "wake-word" else "Ready.")
    finally:
        VOICE_INPUT_LOCK.release()

def get_porcupine_sensitivity():
    try:
        return max(0.0, min(1.0, float(PORCUPINE_SENSITIVITY)))
    except ValueError:
        return 0.65

def create_porcupine_detector():
    try:
        import pvporcupine
    except ImportError:
        set_status("Install pvporcupine for wake word.")
        return None

    if not PORCUPINE_ACCESS_KEY:
        set_status("Set KABIR_PICOVOICE_ACCESS_KEY for wake word.")
        return None

    sensitivity = get_porcupine_sensitivity()
    if PORCUPINE_KEYWORD_PATH:
        keyword_path = Path(PORCUPINE_KEYWORD_PATH).expanduser()
        if not keyword_path.exists():
            set_status("Porcupine keyword file not found.")
            return None
        return pvporcupine.create(
            access_key=PORCUPINE_ACCESS_KEY,
            keyword_paths=[str(keyword_path)],
            sensitivities=[sensitivity],
        )

    return pvporcupine.create(
        access_key=PORCUPINE_ACCESS_KEY,
        keywords=[PORCUPINE_BUILTIN_KEYWORD],
        sensitivities=[sensitivity],
    )

def wake_word_loop():
    try:
        import pyaudio
    except ImportError:
        set_status("Install pyaudio for wake word.")
        return

    while not WAKE_WORD_STOP.is_set():
        porcupine = None
        audio = None
        stream = None
        try:
            porcupine = create_porcupine_detector()
            if not porcupine:
                return

            audio = pyaudio.PyAudio()
            stream = audio.open(
                rate=porcupine.sample_rate,
                channels=1,
                format=pyaudio.paInt16,
                input=True,
                frames_per_buffer=porcupine.frame_length,
            )

            set_status(f"Wake word active: {WAKE_WORD_PHRASE}")
            while not WAKE_WORD_STOP.is_set():
                pcm = stream.read(porcupine.frame_length, exception_on_overflow=False)
                pcm = struct.unpack_from("h" * porcupine.frame_length, pcm)
                if porcupine.process(pcm) >= 0:
                    set_status(f"{WAKE_WORD_PHRASE} detected.")
                    break

            if WAKE_WORD_STOP.is_set():
                break
        except Exception as e:
            set_status(f"Wake word error: {str(e)[:30]}")
            time.sleep(5)
            continue
        finally:
            if stream:
                try:
                    stream.stop_stream()
                    stream.close()
                except Exception:
                    pass
            if audio:
                try:
                    audio.terminate()
                except Exception:
                    pass
            if porcupine:
                try:
                    porcupine.delete()
                except Exception:
                    pass

        if not WAKE_WORD_STOP.is_set():
            run_voice_command(source="wake-word", wake_ack=True)

def start_wake_word_detection():
    global WAKE_WORD_THREAD
    if WAKE_WORD_THREAD and WAKE_WORD_THREAD.is_alive():
        return
    WAKE_WORD_STOP.clear()
    WAKE_WORD_THREAD = Thread(target=wake_word_loop, daemon=True)
    WAKE_WORD_THREAD.start()

def stop_wake_word_detection():
    WAKE_WORD_STOP.set()

# ─── Features ──────────────────────────────────────────────────────────────────
def get_weather(city=None):
    city = (city or load_settings().get("default_city") or "Mumbai").strip() or "Mumbai"
    if not OPENWEATHER_API_KEY:
        speak("Weather is not configured. Add OPENWEATHER_API_KEY to your .env file.")
        return
    try:
        url = f"https://api.openweathermap.org/data/2.5/weather?q={quote_plus(city)}&appid={OPENWEATHER_API_KEY}&units=metric"
        r = requests.get(url, timeout=5)
        data = r.json()
        if data.get("cod") == 200:
            desc  = data["weather"][0]["description"]
            temp  = data["main"]["temp"]
            feels = data["main"]["feels_like"]
            humidity = data["main"]["humidity"]
            speak(f"Weather in {city}: {desc}, {temp}°C, feels like {feels}°C, humidity {humidity}%.")
        else:
            speak(f"Couldn't find weather for {city}.")
    except Exception:
        speak("Couldn't fetch weather right now.")

def extract_movie_query(command):
    query = re.sub(r"\b(?:movie|imdb|film)\b", " ", command or "", flags=re.IGNORECASE)
    query = re.sub(r"\b(?:search|find|show|tell me about|details|rating|review|for|of)\b", " ", query, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", query).strip(" .,:;\"'")

def movie(initial_command=""):
    try:
        import imdb
        moviesdb = imdb.IMDb()
        text = extract_movie_query(initial_command)
        if not text:
            speak("Which movie sir?")
            text = listen_for_reply("Listening for movie name...").strip()
        if is_cancel_reply(text):
            speak("Movie search cancelled.")
            return
        if not text:
            speak("I didn't catch the movie name.")
            return
        set_status(f"Searching IMDB: {text}")
        movies = moviesdb.search_movie(text)
        if not movies:
            speak("No results found."); return
        m = moviesdb.get_movie(movies[0].getID())
        title  = m.get("title", "Unknown")
        year   = m.get("year", "Unknown")
        rating = m.get("rating", "N/A")
        plot   = m.get("plot outline", "No plot available.")
        speak(f"{title} from {year}. IMDB rating: {rating}. {plot}")
    except:
        speak("Couldn't fetch movie info.")

def news():
    try:
        from GoogleNews import GoogleNews
        import pandas as pd
        gn = GoogleNews(period="1d")
        gn.search("India")
        results = gn.result()
        speak("Here are today's headlines:")
        for i, item in enumerate(results[:5]):
            speak(item["title"])
    except:
        speak("Couldn't fetch news.")

def take_screenshot():
    folder = os.path.join(os.path.expanduser("~"), "Desktop", "kabir_screenshots")
    os.makedirs(folder, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(folder, f"screenshot_{ts}.png")
    pyautogui.screenshot().save(path)
    speak("Screenshot saved to your Desktop.")

def send_message_flow(initial_command=""):
    drain_text_replies()

    platform = normalize_platform(initial_command)
    if not platform:
        speak("Which platform should I use? WhatsApp or Slack?")
        platform_reply = listen_for_reply("Listening for message platform...").strip()
        if is_cancel_reply(platform_reply):
            speak("Message cancelled.")
            set_status("Ready.")
            return
        platform = normalize_platform(platform_reply)

    if not platform:
        speak("I can send messages on WhatsApp and Slack right now. Please try again with one of those.")
        set_status("Ready.")
        return

    whatsapp_mode = "web"
    if platform == "whatsapp":
        whatsapp_mode = normalize_whatsapp_mode(initial_command)
        if not whatsapp_mode:
            speak("Should I use WhatsApp Web or the desktop app?")
            mode_reply = listen_for_reply("Listening for WhatsApp mode...").strip()
            if is_cancel_reply(mode_reply):
                speak("Message cancelled.")
                set_status("Ready.")
                return
            whatsapp_mode = normalize_whatsapp_mode(mode_reply) or "web"

    platform_label = f"WhatsApp {whatsapp_mode}" if platform == "whatsapp" else platform
    speak(f"Who should I send the {platform_label} message to?")
    recipient = listen_for_reply("Listening for message recipient...").strip()
    if is_cancel_reply(recipient):
        speak("Message cancelled.")
        set_status("Ready.")
        return
    if not recipient:
        speak("I didn't catch the recipient. Cancelling message.")
        set_status("Ready.")
        return

    speak("What message should I send?")
    message = listen_for_reply("Listening for message text...").strip()
    if is_cancel_reply(message):
        speak("Message cancelled.")
        set_status("Ready.")
        return
    if not message:
        speak("I didn't catch the message. Cancelling.")
        set_status("Ready.")
        return

    speak(f"Ready to send on {platform_label} to {recipient}. Say send to confirm, or cancel.")
    final_reply = listen_for_reply("Waiting for message confirmation...").lower().strip()
    if is_cancel_reply(final_reply) or "send" not in final_reply:
        speak("Message cancelled.")
        set_status("Ready.")
        return

    speak(f"Sending {platform_label} message now.")
    set_status(f"Sending {platform_label} message...")
    success, result = send_platform_message(platform, recipient, message, whatsapp_mode)
    speak(result)
    set_status("Ready." if success else "Message failed.")


def make_phone_call_flow(initial_command=""):
    drain_text_replies()

    number = extract_phone_number(initial_command)
    recipient = ""
    if not number:
        contact_name = normalize_contact_name(initial_command)
        if contact_name:
            number = get_phone_number(contact_name)
            recipient = contact_name

    if not number:
        speak("Who should I call? Say a contact name or phone number.")
        reply = listen_for_reply("Listening for call recipient...").strip()
        if is_cancel_reply(reply):
            speak("Call cancelled.")
            set_status("Ready.")
            return

        number = extract_phone_number(reply)
        if not number:
            contact_name = normalize_contact_name(reply)
            number = get_phone_number(contact_name)
            recipient = contact_name

    if not number:
        speak("I couldn't find that contact or phone number.")
        set_status("Ready.")
        return

    label = recipient or number
    speak(f"Ready to call {label} from your Android phone. Say call to confirm, or cancel.")
    final_reply = listen_for_reply("Waiting for call confirmation...").lower().strip()
    if is_cancel_reply(final_reply) or "call" not in final_reply:
        speak("Call cancelled.")
        set_status("Ready.")
        return

    set_status("Calling from Android phone...")
    success, message = make_call(number)
    speak(message)
    set_status("Ready." if success else "Call failed.")


def answer_phone_call_flow():
    set_status("Answering Android call...")
    success, message = answer_call()
    speak(message)
    set_status("Ready." if success else "Call action failed.")


def end_phone_call_flow():
    set_status("Disconnecting Android call...")
    success, message = end_call()
    speak(message)
    set_status("Ready." if success else "Call action failed.")


def setup_wireless_phone_flow():
    speak("Keep the phone connected by USB for this one-time wireless setup.")
    set_status("Setting up wireless Android...")
    success, message = setup_wireless_adb()
    speak(message)
    set_status("Ready." if success else "Wireless setup failed.")


def connect_wireless_phone_flow(initial_command=""):
    address_match = re.search(r"(\d+\.\d+\.\d+\.\d+(?::\d+)?)", initial_command or "")
    address = address_match.group(1) if address_match else ""
    if not address:
        speak("Tell me the phone IP address and port, or say saved to use the saved phone.")
        reply = listen_for_reply("Listening for wireless phone address...").strip()
        if is_cancel_reply(reply):
            speak("Wireless connection cancelled.")
            set_status("Ready.")
            return
        address_match = re.search(r"(\d+\.\d+\.\d+\.\d+(?::\d+)?)", reply)
        address = address_match.group(1) if address_match else ""

    set_status("Connecting wireless Android...")
    success, message = connect_wireless_adb(address)
    speak(message)
    set_status("Ready." if success else "Wireless connection failed.")


def pair_wireless_phone_flow():
    speak("Please type the wireless debugging pairing address, including port.")
    pair_address = listen_for_reply("Waiting for pair address...").strip()
    if is_cancel_reply(pair_address):
        speak("Pairing cancelled.")
        set_status("Ready.")
        return

    speak("Please type the six digit pairing code.")
    pair_code = listen_for_reply("Waiting for pair code...").strip()
    if is_cancel_reply(pair_code):
        speak("Pairing cancelled.")
        set_status("Ready.")
        return

    speak("Now type the wireless debugging connection address and port, or say skip.")
    connect_address = listen_for_reply("Waiting for connect address...").strip()
    if is_cancel_reply(connect_address):
        speak("Pairing cancelled.")
        set_status("Ready.")
        return
    if connect_address.lower() == "skip":
        connect_address = ""

    set_status("Pairing wireless Android...")
    success, message = pair_wireless_adb(pair_address, pair_code, connect_address)
    speak(message)
    set_status("Ready." if success else "Wireless pairing failed.")


def spotify_flow(initial_command=""):
    drain_text_replies()

    action = normalize_spotify_action(initial_command)
    query = extract_spotify_query(initial_command) if action == "play" else ""

    if action == "play" and not query:
        speak("What should I play on Spotify? Say skip to just open Spotify.")
        reply = listen_for_reply("Listening for Spotify song...").strip()
        if is_cancel_reply(reply):
            speak("Spotify cancelled.")
            set_status("Ready.")
            return
        if reply.lower() == "skip":
            action = "open"
        else:
            query = reply

    if not action:
        action = "open"

    status_label = "Spotify" if not query else f"Spotify: {query}"
    set_status(f"Running {status_label}...")
    success, message = control_spotify(action, query)
    speak(message)
    set_status("Ready." if success else "Spotify failed.")


def normalize_music_platform(text):
    text = (text or "").strip().lower()
    if "spotify" in text:
        return "spotify"
    if "youtube" in text or "you tube" in text:
        return "youtube"
    return ""


def extract_youtube_song(text):
    song = text or ""
    for word in ["play", "music", "songs", "song", "on", "youtube", "you tube", "please"]:
        song = re.sub(rf"\b{re.escape(word)}\b", " ", song, flags=re.IGNORECASE)
    return " ".join(song.split())


def play_media_flow(initial_command=""):
    drain_text_replies()

    platform = normalize_music_platform(initial_command)
    if not platform:
        platform = load_settings().get("preferred_music_platform", "youtube")

    if platform not in {"spotify", "youtube"}:
        speak("I can play music on Spotify or YouTube. Please try again with one of those.")
        set_status("Ready.")
        return

    query = extract_spotify_query(initial_command) if platform == "spotify" else extract_youtube_song(initial_command)
    if not query:
        speak(f"What should I play on {platform.title()}?")
        query = listen_for_reply(f"Listening for {platform} song...").strip()
        if is_cancel_reply(query):
            speak("Music cancelled.")
            set_status("Ready.")
            return

    if not query:
        speak("I didn't catch the song name. Please try again.")
        set_status("Ready.")
        return

    if platform == "spotify":
        set_status(f"Playing on Spotify: {query}")
        success, message = control_spotify("play", query)
        speak(message)
        set_status("Ready." if success else "Spotify failed.")
        return

    speak(f"Playing {query} on YouTube.")
    set_status(f"Playing on YouTube: {query}")
    pywhatkit.playonyt(query)
def extract_maps_location(command):
    command_lower = (command or "").lower().strip()
    location = ""
    
    if "where is" in command_lower:
        location = command_lower.split("where is", 1)[1]
    elif "locate" in command_lower:
        location = command_lower.split("locate", 1)[1]
    elif "search" in command_lower and "maps" in command_lower:
        parts = re.split(r"\bsearch\s+(?:for\s+)?", command_lower, maxsplit=1)
        if len(parts) > 1:
            location = parts[1]
            
    if location:
        location = re.sub(r"\b(on|in|at)?\s*(google\s+)?maps?\b", "", location, flags=re.IGNORECASE).strip()
        location = re.sub(r"\s+", " ", location).strip(" .,:;?\"'")
        return location
    return ""


def open_app(name):
    if 'calculator' in name:
        os.startfile('C:/Windows/System32/calc.exe'); speak("Opening Calculator.")
    elif 'paint' in name:
        subprocess.Popen("mspaint"); speak("Opening Paint.")
    elif 'notepad' in name:
        subprocess.Popen("notepad.exe"); speak("Opening Notepad.")
    elif 'code' in name or 'vscode' in name or 'editor' in name:
        subprocess.Popen("code", shell=True); speak("Opening VS Code.")
    else:
        try: subprocess.Popen(name, shell=True); speak(f"Opening {name}.")
        except: speak(f"Couldn't open {name}.")

def normalize_file_search_text(text):
    text = (text or "").lower()
    text = re.sub(r"\b(dot|period|full stop)\b", ".", text)
    text = re.sub(r"\b(underscore|under score)\b", "_", text)
    return re.sub(r"[^a-z0-9]+", "", text)

def extract_file_search_query(command):
    query = (command or "").strip()
    cleanup_patterns = [
        r"^(please\s+)?(can you\s+|could you\s+)?",
        r"\b(find|search for|search|locate|look for|show|open)\b",
        r"\b(a|the)?\s*files?\b",
        r"\b(named|called|by name|with name|name is)\b",
        r"\b(on my pc|on this pc|in my computer|in computer)\b",
    ]
    for pattern in cleanup_patterns:
        query = re.sub(pattern, " ", query, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", query).strip(" .,:;\"'")

def is_file_search_command(command):
    if any(intent in command for intent in FILE_SEARCH_INTENT_WORDS):
        return True
    if re.match(r"^(find|locate|look for)\s+\S+", command):
        return not any(target in command for target in ("youtube", "google", "wikipedia", "maps"))
    if re.match(r"^search\s+\S+", command) and re.search(r"\b\w+\s+(dot|period|full stop)\s+\w+\b|[\w-]+\.[\w-]+", command):
        return not any(target in command for target in ("youtube", "google", "wikipedia"))
    return False

def push_file_results_to_ui(query, response):
    try:
        call_ui("showFileSearchResults", query, response)
    except Exception:
        pass

def handle_file_search_command(command):
    query = extract_file_search_query(command)
    if not query:
        speak("Which file should I search for?")
        query = listen_for_reply("Listening for file name...").strip()
        if is_cancel_reply(query):
            speak("File search cancelled.")
            set_status("Ready.")
            return

    response = search_files(query, None, 20)
    push_file_results_to_ui(query, response)
    results = response.get("results", [])
    if not results:
        speak(f"I couldn't find a file matching {query}.")
        set_status("No files found.")
        return

    top = results[0]
    count = len(results)
    if "open file" in command and count == 1:
        opened = open_file_path(top["path"])
        speak(f"Found {top['name']}. {opened.get('message', 'Opening file.')}")
        set_status(opened.get("message", "Opening file."))
        return

    if "open file" in command and count > 1:
        speak(f"I found {count} matches. The closest is {top['name']}. Showing the results in File Explorer.")
    else:
        speak(f"I found {count} match{'es' if count != 1 else ''}. Top result: {top['name']}.")
    set_status(response.get("message", "File search complete."))

# ─── Email flow ────────────────────────────────────────────────────────────────
def send_email_flow(initial_command=""):
    """
    Voice-driven email flow.
    Asks: recipient → subject type → body or folder path → sends.
    """
    profile_status = get_profile_status()
    if not profile_status["configured"]:
        missing = ", ".join(profile_status["missing"])
        speak(f"Mail profile is incomplete. Please open Profile and add {missing}.")
        set_status("Profile needed.")
        return

    drain_text_replies()
    to_raw = extract_email_recipient(initial_command)
    to_email = normalize_spoken_email(to_raw) if to_raw else ""

    if not is_valid_email(to_email):
        speak("Sure sir. Who should I send the email to? Please say the email address, spell it out, or type it.")
        to_email = ""
        for attempt in range(3):
            to_raw = listen_for_reply("Listening for recipient...").strip()
            if is_cancel_reply(to_raw):
                speak("Email cancelled.")
                set_status("Ready.")
                return
            to_email = normalize_spoken_email(to_raw)
            if is_valid_email(to_email):
                break
            if attempt < 2:
                speak("I didn't catch a valid email address. Please try again, or type the full address.")
        else:
            speak("I didn't catch the recipient. Cancelling email.")
            return

    # Normalise spoken email: "at" → "@", "dot" → "."
    speak(f"Sending to {to_email}. Should I use the QSB template subject, or would you like to say a custom subject?")
    subject_choice = listen_for_reply("Listening for subject type...").lower().strip()
    if is_cancel_reply(subject_choice):
        speak("Email cancelled.")
        set_status("Ready.")
        return

    if "qsb" in subject_choice or "template" in subject_choice or "default" in subject_choice:
        subject = build_qsb_subject()
        speak(f"Using subject: {subject}")
        use_template = True
    else:
        speak("Please say the subject line.")
        subject = listen_for_reply("Listening for subject...").strip()
        if is_cancel_reply(subject):
            speak("Email cancelled.")
            set_status("Ready.")
            return
        if not subject:
            subject = "Message from Kabir"
        use_template = False
        speak(f"Subject set to: {subject}")

    speak("Should I attach files from a folder? Say yes and then the folder path, or say no.")
    attach_reply = listen_for_reply("Listening for attachment choice...").strip()
    if is_cancel_reply(attach_reply):
        speak("Email cancelled.")
        set_status("Ready.")
        return

    folder_path = None
    if "yes" in attach_reply.lower() or "attach" in attach_reply.lower():
        # Extract path from reply or ask again
        # Remove trigger words to isolate path
        clean_attach_reply = attach_reply
        for w in ["yes", "attach", "files", "from", "folder", "path"]:
            clean_attach_reply = re.sub(rf"\b{re.escape(w)}\b", "", clean_attach_reply, flags=re.IGNORECASE).strip()
        folder_path = clean_attach_reply.strip() if clean_attach_reply.strip() else None

        if not folder_path:
            speak("Please type or say the folder path.")
            folder_path = listen_for_reply("Waiting for folder path...").strip() or None
            if folder_path and is_cancel_reply(folder_path):
                speak("Email cancelled.")
                set_status("Ready.")
                return
            # Fall through — folder_path stays None, no attachments
        else:
            speak(f"Attaching all files from {folder_path}.")

    speak("Please say the email body, or say skip to use the HTML template.")
    body = listen_for_reply("Listening for email body...").strip()
    if is_cancel_reply(body):
        speak("Email cancelled.")
        set_status("Ready.")
        return
    if not body or "skip" in body.lower():
        body = "Please find the attached documents. Regards, Kabir."
        use_template = True

    speak(f"Ready to send to {to_email}. Say send to confirm, or cancel.")
    final_reply = listen_for_reply("Waiting for send confirmation...").lower().strip()
    if is_cancel_reply(final_reply) or "send" not in final_reply:
        speak("Email cancelled.")
        set_status("Ready.")
        return

    speak("Sending the email now, sir. Please wait.")
    set_status("Sending email...")

    success, message = send_email(
        to_email    = to_email,
        subject     = subject,
        body_text   = body,
        folder_path = folder_path,
        use_template= use_template
    )

    speak(message)
    set_status("Ready." if success else "Email failed.")


# ─── Command processor ─────────────────────────────────────────────────────────
OLLAMA_URL = os.environ.get("KABIR_OLLAMA_URL", "http://localhost:11434/api/generate").strip()
OLLAMA_MODEL = os.environ.get("KABIR_OLLAMA_MODEL", "llama3.1").strip() or "llama3.1"
AGENT_MAX_STEPS = 6


def compact_agent_text(text, max_len=900):
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 3].rstrip() + "..."


def ask_ollama(prompt, max_tokens=700):
    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {"num_predict": max_tokens, "temperature": 0.2},
            },
            timeout=25,
        )
        response.raise_for_status()
        return (response.json().get("response") or "").strip()
    except Exception:
        return ""


def strip_agent_trigger(command):
    text = (command or "").strip()
    text = re.sub(
        r"^(kabir\s+)?(autonomous task|autonomous agent|agent mode|agent|plan and execute|do this task)\s*[:,\-]?\s*",
        "",
        text,
        flags=re.IGNORECASE,
    )
    return text.strip() or text


def is_agent_command(command):
    text = (command or "").lower().strip()
    if text.startswith(("agent:", "agent ", "kabir agent")):
        return True
    if " and email " in text and ("research" in text or "summarize" in text or "summary" in text):
        return True
    triggers = (
        "autonomous task",
        "autonomous agent",
        "agent mode",
        "plan and execute",
        "do this task",
        "research and email",
        "book me",
        "book a",
    )
    return any(trigger in text for trigger in triggers)


def extract_research_query(goal):
    text = strip_agent_trigger(goal)
    patterns = [
        r"research\s+(.*?)\s+(?:and|then)\s+(?:email|mail|send)",
        r"research\s+(.*)",
        r"summarize\s+(.*)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip(" .,:;\"'")
    return text.strip(" .,:;\"'")


def extract_agent_email_recipient(goal):
    direct = normalize_spoken_email(extract_email_recipient(goal))
    if is_valid_email(direct):
        return direct

    match = re.search(r"\b(?:email|mail|send)\s+(?:it|this|summary|the summary)?\s*(?:to)?\s+(.+)$", goal, flags=re.IGNORECASE)
    if not match:
        return ""

    candidate = match.group(1).strip(" .,:;\"'")
    for stop_word in (" after ", " with ", " about "):
        candidate = candidate.split(stop_word, 1)[0].strip()
    return normalize_spoken_email(candidate)


def duckduckgo_search(query, limit=5):
    if not query:
        return []
    try:
        url = f"https://duckduckgo.com/html/?q={quote_plus(query)}"
        response = requests.get(url, timeout=12, headers={"User-Agent": "Mozilla/5.0"})
        response.raise_for_status()
        body = response.text
    except Exception:
        return bing_search(query, limit=limit)

    results = []

    def clean_result_url(raw_url):
        raw_url = html.unescape(raw_url or "").strip()
        if not raw_url:
            return ""
        parsed = urlparse(raw_url)
        if "duckduckgo.com" in parsed.netloc and parsed.path.startswith("/l/"):
            uddg = parse_qs(parsed.query).get("uddg", [""])[0]
            return unquote(uddg) if uddg else raw_url
        if raw_url.startswith("//duckduckgo.com/l/"):
            return clean_result_url("https:" + raw_url)
        return raw_url

    if BeautifulSoup is not None:
        soup = BeautifulSoup(body, "html.parser")
        for block in soup.select(".result"):
            title_node = block.select_one(".result__a")
            if not title_node:
                continue
            title = title_node.get_text(" ", strip=True)
            result_url = clean_result_url(title_node.get("href", ""))
            snippet_node = block.select_one(".result__snippet")
            snippet = snippet_node.get_text(" ", strip=True) if snippet_node else ""
            if title and result_url:
                results.append({"title": title, "url": result_url, "snippet": compact_agent_text(snippet, 260)})
            if len(results) >= limit:
                break

    if not results:
        blocks = re.findall(r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>(.*?)</div>', body, flags=re.I | re.S)
        for raw_url, title, tail in blocks:
            clean_title = html.unescape(re.sub(r"<.*?>", "", title)).strip()
            snippet_match = re.search(r'class="result__snippet"[^>]*>(.*?)</a>|class="result__snippet"[^>]*>(.*?)</div>', tail, flags=re.I | re.S)
            snippet = ""
            if snippet_match:
                snippet = snippet_match.group(1) or snippet_match.group(2) or ""
                snippet = html.unescape(re.sub(r"<.*?>", "", snippet)).strip()
            result_url = clean_result_url(raw_url)
            if clean_title and result_url:
                results.append({"title": clean_title, "url": result_url, "snippet": compact_agent_text(snippet, 260)})
            if len(results) >= limit:
                break
    if results:
        return results
    return bing_search(query, limit=limit)


def bing_search(query, limit=5):
    if not query:
        return []
    try:
        url = f"https://www.bing.com/search?q={quote_plus(query)}"
        response = requests.get(url, timeout=12, headers={"User-Agent": "Mozilla/5.0"})
        response.raise_for_status()
        body = response.text
    except Exception as e:
        return [{"title": "Search failed", "url": "", "snippet": str(e)}]

    results = []
    if BeautifulSoup is not None:
        soup = BeautifulSoup(body, "html.parser")
        for block in soup.select("li.b_algo"):
            title_node = block.select_one("h2 a")
            if not title_node:
                continue
            title = title_node.get_text(" ", strip=True)
            result_url = html.unescape(title_node.get("href", "")).strip()
            snippet_node = block.select_one(".b_caption p, p")
            snippet = snippet_node.get_text(" ", strip=True) if snippet_node else ""
            if title and result_url:
                results.append({"title": title, "url": result_url, "snippet": compact_agent_text(snippet, 260)})
            if len(results) >= limit:
                break

    if not results:
        blocks = re.findall(r'<li[^>]+class="b_algo"[^>]*>(.*?)</li>', body, flags=re.I | re.S)
        for block in blocks:
            link_match = re.search(r'<h2[^>]*>\s*<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', block, flags=re.I | re.S)
            if not link_match:
                continue
            result_url = html.unescape(link_match.group(1)).strip()
            title = html.unescape(re.sub(r"<.*?>", "", link_match.group(2))).strip()
            snippet_match = re.search(r'<p[^>]*>(.*?)</p>', block, flags=re.I | re.S)
            snippet = ""
            if snippet_match:
                snippet = html.unescape(re.sub(r"<.*?>", "", snippet_match.group(1))).strip()
            if title and result_url:
                results.append({"title": title, "url": result_url, "snippet": compact_agent_text(snippet, 260)})
            if len(results) >= limit:
                break
    return results


LIVE_WEB_TRIGGERS = (
    "live search",
    "search the web",
    "web search",
    "look up",
    "search online",
    "latest",
    "today",
    "todays",
    "current",
    "right now",
    "recent",
    "news about",
    "stock price",
    "share price",
    "bitcoin price",
    "crypto price",
    "ipl",
    "score",
)

QUESTION_STARTERS = (
    "what",
    "who",
    "when",
    "where",
    "why",
    "how",
    "which",
    "is",
    "are",
    "can",
    "does",
    "do",
    "did",
)


def extract_live_web_query(command):
    text = (command or "").strip()
    text = re.sub(
        r"^(kabir\s+)?(live search|search the web|web search|search online|look up|answer|tell me|find out)\s*(for|about)?\s*",
        "",
        text,
        flags=re.IGNORECASE,
    )
    return text.strip(" .,:;\"'") or (command or "").strip()


def is_vague_stock_query(query):
    text = re.sub(r"\s+", " ", (query or "").lower()).strip()
    generic_words = {"stock", "stocks", "share", "shares", "price", "prices", "market", "today", "current", "latest", "right", "now"}
    tokens = re.findall(r"[a-z0-9.]+", text)
    return bool(tokens) and any(word in text for word in ("stock price", "share price")) and all(token in generic_words for token in tokens)


STOCK_SYMBOL_ALIASES = {
    "tesla": "TSLA",
    "apple": "AAPL",
    "microsoft": "MSFT",
    "google": "GOOGL",
    "alphabet": "GOOGL",
    "amazon": "AMZN",
    "meta": "META",
    "facebook": "META",
    "nvidia": "NVDA",
    "netflix": "NFLX",
    "reliance": "RELIANCE.NS",
    "tcs": "TCS.NS",
    "infosys": "INFY.NS",
    "hdfc bank": "HDFCBANK.NS",
    "icici bank": "ICICIBANK.NS",
    "sbi": "SBIN.NS",
    "tatamotors": "TMPV.NS",
    "tata motors": "TMPV.NS",
    "tata motors passenger vehicles": "TMPV.NS",
    "tata motors commercial vehicles": "TMCV.NS",
}


def extract_stock_lookup_text(query):
    text = re.sub(r"\b(stock|share|market)\s+price\b", " ", query or "", flags=re.IGNORECASE)
    text = re.sub(r"\b(current|latest|today|right now|price|quote|of|for)\b", " ", text, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", text).strip(" .,:;\"'")


def resolve_stock_symbol(query):
    lookup = extract_stock_lookup_text(query)
    if not lookup:
        return ""
    normalized = lookup.lower()
    if normalized in STOCK_SYMBOL_ALIASES:
        return STOCK_SYMBOL_ALIASES[normalized]
    if re.fullmatch(r"[A-Za-z.]{1,12}", lookup):
        return lookup.upper()

    try:
        response = requests.get(
            "https://query2.finance.yahoo.com/v1/finance/search",
            params={"q": lookup, "quotesCount": 1, "newsCount": 0},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=10,
        )
        response.raise_for_status()
        quotes = response.json().get("quotes") or []
    except Exception:
        quotes = []

    for quote in quotes:
        symbol = (quote.get("symbol") or "").strip()
        quote_type = (quote.get("quoteType") or "").upper()
        if symbol and quote_type in {"EQUITY", "ETF", "MUTUALFUND", "INDEX"}:
            return symbol
    return ""


def yahoo_stock_symbol_candidates(query):
    lookup = extract_stock_lookup_text(query)
    if not lookup:
        return []
    try:
        response = requests.get(
            "https://query2.finance.yahoo.com/v1/finance/search",
            params={"q": lookup, "quotesCount": 5, "newsCount": 0},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=10,
        )
        response.raise_for_status()
        quotes = response.json().get("quotes") or []
    except Exception:
        return []

    symbols = []
    for quote in quotes:
        symbol = (quote.get("symbol") or "").strip()
        quote_type = (quote.get("quoteType") or "").upper()
        if symbol and quote_type in {"EQUITY", "ETF", "MUTUALFUND", "INDEX"} and symbol not in symbols:
            symbols.append(symbol)
    return symbols


def fetch_stock_chart_meta(symbol):
    try:
        response = requests.get(
            f"https://query1.finance.yahoo.com/v8/finance/chart/{quote_plus(symbol)}",
            params={"range": "1d", "interval": "1m"},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=10,
        )
        response.raise_for_status()
        results = response.json().get("chart", {}).get("result") or []
    except Exception:
        results = []
    if not results:
        return {}
    return results[0].get("meta", {}) or {}


def get_stock_price_answer(query):
    if not re.search(r"\b(stock|share|quote)\b", query or "", flags=re.IGNORECASE):
        return ""
    symbol = resolve_stock_symbol(query)
    if not symbol:
        return ""

    symbols = [symbol]
    for candidate in yahoo_stock_symbol_candidates(query):
        if candidate not in symbols:
            symbols.append(candidate)

    meta = {}
    for candidate in symbols:
        meta = fetch_stock_chart_meta(candidate)
        if meta.get("regularMarketPrice") or meta.get("chartPreviousClose"):
            break

    if not meta:
        return ""
    name = meta.get("longName") or meta.get("shortName") or meta.get("symbol") or symbol
    symbol = meta.get("symbol") or symbol
    price = meta.get("regularMarketPrice") or meta.get("chartPreviousClose")
    previous_close = meta.get("previousClose") or meta.get("chartPreviousClose")
    currency = meta.get("currency") or ""
    exchange = meta.get("exchangeName") or ""
    market_state = meta.get("marketState") or ""
    if price is None:
        return ""

    change_text = ""
    if previous_close:
        change = price - previous_close
        change_percent = (change / previous_close) * 100
        direction = "up" if change >= 0 else "down"
        change_text = f", {direction} {abs(change):.2f} ({abs(change_percent):.2f}%)"
    status = f" on {exchange}" if exchange else ""
    state_text = f" Market state: {market_state}." if market_state else ""
    return f"{name} ({symbol}) is trading at {price:.2f} {currency}{change_text}{status}.{state_text}"


def clean_result_title(title):
    title = re.sub(r"\s+", " ", title or "").strip()
    title = re.sub(r"\s*[-|]\s*(Bing|Google|Yahoo|India Today|Times of India|NDTV).*$", "", title, flags=re.IGNORECASE)
    return title.strip(" .,:;\"'")


def build_search_fallback_answer(query, results):
    lower_query = (query or "").lower()
    if "news" in lower_query or "latest" in lower_query:
        headlines = []
        seen = set()
        for item in results:
            title = clean_result_title(item.get("title", ""))
            if not title or title.lower() in seen:
                continue
            seen.add(title.lower())
            headlines.append(title)
            if len(headlines) >= 3:
                break
        if headlines:
            return "Here are the top live results I found: " + "; ".join(headlines) + "."

    parts = []
    for item in results[:3]:
        title = clean_result_title(item.get("title", ""))
        snippet = compact_agent_text(item.get("snippet", ""), 130)
        if title and snippet:
            parts.append(f"{title}: {snippet}")
        elif title:
            parts.append(title)
    if parts:
        return "Here is what I found: " + " ".join(parts)
    return ""


def is_live_web_query(command):
    text = (command or "").lower().strip()
    if not text:
        return False
    if any(trigger in text for trigger in LIVE_WEB_TRIGGERS):
        return not any(target in text for target in ("youtube", "wikipedia", "file", "folder"))
    if text.endswith("?") or text.split(" ", 1)[0] in QUESTION_STARTERS:
        current_terms = ("today", "latest", "current", "right now", "recent", "news", "price", "score", "won", "yesterday", "tomorrow")
        return any(term in text for term in current_terms)
    return False


def answer_live_web_query(command):
    query = extract_live_web_query(command)
    if not query:
        speak("What should I search for, sir?")
        return
    if is_vague_stock_query(query):
        speak("Which stock or company should I check, sir?")
        set_status("Ready.")
        return

    stock_answer = get_stock_price_answer(query)
    if stock_answer:
        speak(stock_answer)
        set_status("Ready.")
        return

    set_status(f"Live search: {query}")
    results = duckduckgo_search(query, limit=6)
    useful = [item for item in results if item.get("title") and item.get("title") != "Search failed"]
    if not useful:
        reason = results[0].get("snippet") if results else "No useful search results came back."
        speak(f"I could not fetch live results right now. {compact_agent_text(reason, 160)}")
        set_status("Ready.")
        return

    for item in useful[:6]:
        save_knowledge_entry(
            item.get("title", ""),
            item.get("snippet", ""),
            item.get("url", ""),
            source=f"web search: {query}",
        )

    source_lines = []
    for i, item in enumerate(useful[:6], 1):
        source_lines.append(
            f"{i}. {item.get('title', '')}\n"
            f"Snippet: {item.get('snippet', '')}\n"
            f"URL: {item.get('url', '')}"
        )

    prompt = (
        "You are Kabir, a concise assistant with live web search snippets. "
        "Answer the user's question using only these search results. "
        "If the snippets do not contain the answer, say what the results indicate and avoid guessing. "
        "Keep the answer under 130 words and mention source titles briefly.\n\n"
        f"Question: {query}\n\nSearch results:\n" + "\n\n".join(source_lines)
    )
    answer = ask_ollama(prompt, max_tokens=260)
    if not answer:
        answer = build_search_fallback_answer(query, useful)

    if answer:
        speak(compact_agent_text(answer, 700))
    else:
        speak("I found live results, but could not turn them into a useful answer.")
    set_status("Ready.")


def summarize_agent_research(goal, query, results):
    source_lines = []
    for i, item in enumerate(results, 1):
        title = item.get("title", "")
        snippet = item.get("snippet", "")
        url = item.get("url", "")
        source_lines.append(f"{i}. {title}\n{snippet}\n{url}")

    prompt = (
        "You are Kabir, a concise desktop research assistant. Summarize these search results "
        "for the user's goal. Give 5 short bullets and a one-sentence recommendation. "
        "Do not invent details beyond the source snippets.\n\n"
        f"Goal: {goal}\nQuery: {query}\n\nSources:\n" + "\n\n".join(source_lines)
    )
    llm_summary = ask_ollama(prompt, max_tokens=500)
    if llm_summary:
        return llm_summary

    useful = [item for item in results if item.get("title") and item.get("title") != "Search failed"]
    if not useful:
        return "I could not gather enough web results to summarize this task."

    bullets = []
    for item in useful[:5]:
        detail = item.get("snippet") or item.get("url") or "No snippet was available."
        bullets.append(f"- {item['title']}: {compact_agent_text(detail, 180)}")
    return "\n".join(bullets)


def build_agent_plan(goal):
    prompt = (
        "Return only JSON for a small Kabir task plan. Allowed actions are web_search, summarize, "
        "open_browser, file_search, send_email, create_calendar_note, final. "
        "Use at most 5 steps. Example: [{\"action\":\"web_search\",\"query\":\"...\"}].\n"
        f"User goal: {goal}"
    )
    raw = ask_ollama(prompt, max_tokens=450)
    if raw:
        try:
            start = raw.find("[")
            end = raw.rfind("]") + 1
            parsed = json.loads(raw[start:end])
            if isinstance(parsed, list):
                return [step for step in parsed if isinstance(step, dict)][:AGENT_MAX_STEPS]
        except Exception:
            pass

    lower_goal = goal.lower()
    if "book" in lower_goal and ("cab" in lower_goal or "taxi" in lower_goal or "uber" in lower_goal or "ola" in lower_goal):
        return [
            {"action": "open_browser", "url": "https://m.uber.com/"},
            {"action": "open_browser", "url": "https://book.olacabs.com/"},
            {"action": "create_calendar_note", "title": "Cab booking task", "details": goal},
            {"action": "final"},
        ]

    if "research" in lower_goal or "summarize" in lower_goal or "email" in lower_goal:
        query = extract_research_query(goal)
        plan = [{"action": "web_search", "query": query}, {"action": "summarize"}]
        if "email" in lower_goal or "mail" in lower_goal:
            plan.append({"action": "send_email"})
        plan.append({"action": "final"})
        return plan

    if is_file_search_command(lower_goal):
        return [{"action": "file_search", "query": extract_file_search_query(goal)}, {"action": "final"}]

    return [{"action": "web_search", "query": goal}, {"action": "summarize"}, {"action": "final"}]


def create_calendar_note(title, details):
    folder = Path.home() / "Desktop" / "kabir_agent_notes"
    try:
        folder.mkdir(parents=True, exist_ok=True)
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        path = folder / f"agent_note_{stamp}.ics"
        now = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        body = "\n".join([
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//Kabir//Autonomous Agent//EN",
            "BEGIN:VTODO",
            f"DTSTAMP:{now}",
            f"SUMMARY:{compact_agent_text(title, 120)}",
            f"DESCRIPTION:{compact_agent_text(details, 500)}",
            "END:VTODO",
            "END:VCALENDAR",
        ])
        path.write_text(body, encoding="utf-8")
        return {"success": True, "path": str(path), "message": f"Created reminder note: {path.name}"}
    except Exception as e:
        return {"success": False, "message": f"Could not create reminder note: {str(e)}"}


def send_agent_email(goal, summary, research_results):
    profile_status = get_profile_status()
    if not profile_status["configured"]:
        missing = ", ".join(profile_status["missing"])
        return False, f"Mail profile is incomplete. Please open Profile and add {missing}."

    to_email = extract_agent_email_recipient(goal)
    if not is_valid_email(to_email):
        speak("Who should I send the summary to? Please say or type the email address.")
        reply = listen_for_reply("Listening for agent email recipient...").strip()
        if is_cancel_reply(reply):
            return False, "Agent email cancelled."
        to_email = normalize_spoken_email(reply)

    if not is_valid_email(to_email):
        return False, "I could not determine a valid email recipient."

    source_text = "\n".join(
        f"{i}. {item.get('title', 'Source')} - {item.get('url', '')}"
        for i, item in enumerate(research_results[:5], 1)
        if item.get("url")
    )
    body = f"Kabir completed the research task:\n\n{goal}\n\nSummary:\n{summary}\n\nSources:\n{source_text}".strip()
    subject = f"Kabir research summary: {compact_agent_text(extract_research_query(goal), 70)}"

    speak(f"I prepared the email to {to_email}. Say send to confirm, or cancel.")
    confirmation = listen_for_reply("Waiting for agent send confirmation...").lower().strip()
    if is_cancel_reply(confirmation) or "send" not in confirmation:
        return False, "Agent email cancelled."

    return send_email(to_email=to_email, subject=subject, body_text=body, use_template=False)


def run_autonomous_agent(goal):
    goal = strip_agent_trigger(goal)
    if not goal:
        speak("Please give me a goal for the agent.")
        return

    set_status("Agent planning...")
    speak("Agent mode engaged. I will plan the task, run the tools, and report back.")
    plan = build_agent_plan(goal)
    context = {"goal": goal, "search_results": [], "summary": ""}
    speak("Plan: " + "; ".join(step.get("action", "step") for step in plan))

    for step_number, step in enumerate(plan[:AGENT_MAX_STEPS], 1):
        action = (step.get("action") or "").lower().strip()
        set_status(f"Agent step {step_number}: {action}")

        if action == "web_search":
            query = step.get("query") or extract_research_query(goal)
            speak(f"Searching the web for {query}.")
            context["search_results"] = duckduckgo_search(query, limit=5)
            for item in context["search_results"]:
                if item.get("title") and item.get("title") != "Search failed":
                    save_knowledge_entry(
                        item.get("title", ""),
                        item.get("snippet", ""),
                        item.get("url", ""),
                        source=f"agent web search: {query}",
                    )
        elif action == "summarize":
            query = extract_research_query(goal)
            context["summary"] = summarize_agent_research(goal, query, context["search_results"])
            speak(compact_agent_text(context["summary"], 650))
        elif action == "open_browser":
            url = step.get("url") or step.get("query") or "https://www.google.com"
            webbrowser.open(url)
            speak(f"Opened {url}.")
        elif action == "file_search":
            query = step.get("query") or extract_file_search_query(goal)
            response = search_files(query, None, 20)
            push_file_results_to_ui(query, response)
            count = len(response.get("results", []))
            speak(f"File search complete. I found {count} match{'es' if count != 1 else ''}.")
        elif action == "create_calendar_note":
            note = create_calendar_note(step.get("title") or "Kabir agent task", step.get("details") or goal)
            speak(note["message"])
        elif action == "send_email":
            success, message = send_agent_email(goal, context.get("summary", ""), context.get("search_results", []))
            speak(message)
            if not success:
                break
        elif action == "final":
            break

    set_status("Ready.")
    if context.get("summary"):
        speak("Agent task complete.")
    else:
        speak("Agent task complete. I have reported the actions I could take.")


def switch_active_window():
    pyautogui.keyDown("alt")
    pyautogui.press("tab")
    pyautogui.keyUp("alt")


def build_skill_context():
    return SkillContext(
        speak=speak,
        set_status=set_status,
        open_url=webbrowser.open,
        press_key=pyautogui.press,
        hotkey=pyautogui.hotkey,
        switch_window=switch_active_window,
        get_weather=get_weather,
        spotify_flow=spotify_flow,
        play_media_flow=play_media_flow,
        extract_maps_location=extract_maps_location,
        settings=load_settings,
        is_agent_command=is_agent_command,
        run_autonomous_agent=run_autonomous_agent,
        is_memory_query=is_memory_query,
        answer_memory_query=answer_memory_query,
        is_file_search_command=is_file_search_command,
        handle_file_search_command=handle_file_search_command,
        send_email_flow=send_email_flow,
        send_message_flow=send_message_flow,
        setup_wireless_phone_flow=setup_wireless_phone_flow,
        pair_wireless_phone_flow=pair_wireless_phone_flow,
        connect_wireless_phone_flow=connect_wireless_phone_flow,
        answer_phone_call_flow=answer_phone_call_flow,
        end_phone_call_flow=end_phone_call_flow,
        make_phone_call_flow=make_phone_call_flow,
    )


def try_dispatch_command_skill(command):
    try:
        result = dispatch_skill(command, build_skill_context())
        if result is not None:
            return True
    except Exception as e:
        logger.exception("Skill dispatch failed")
        set_status(f"Skill error: {str(e)[:30]}")
        speak("That skill ran into an error. Please try again.")
        return True
    return False


def process_command(command, source="unknown"):
    logger.info("Command received from %s: %s", source, command)
    add_user_msg(command)
    save_command_history(command, source)
    if not command: return

    if try_dispatch_command_skill(command):
        return

    if is_agent_command(command):
        run_autonomous_agent(command)
    elif is_memory_query(command):
        answer_memory_query(command)
    elif is_file_search_command(command):
        handle_file_search_command(command)
    elif is_live_web_query(command):
        answer_live_web_query(command)
    elif "show hud" in command or "open hud" in command or "enable hud" in command or "holographic hud" in command:
        if show_holographic_hud():
            speak("Holographic HUD online.")
    elif "hide hud" in command or "close hud" in command or "disable hud" in command:
        hide_holographic_hud()
        speak("Holographic HUD hidden.")
    elif "neural voice" in command or "premium voice" in command:
        if "off" in command or "disable" in command or "local" in command:
            set_tts_engine("local")
            speak("Local voice engine enabled.")
        else:
            set_tts_engine("neural")
            speak("Neural voice engine enabled.")
    elif "local voice" in command or "offline voice" in command:
        set_tts_engine("local")
        speak("Local voice engine enabled.")
    elif "time" in command:
        speak(f"The time is {datetime.datetime.now().strftime('%I:%M %p')}.")
    elif "date" in command:
        speak(f"Today is {datetime.datetime.now().strftime('%A, %B %d, %Y')}.")
    elif "who are you" in command or "introduce" in command:
        speak("I am Kabir, your personal desktop assistant. Ready to serve, sir.")
    elif "who made you" in command or "who created you" in command or "who built you" in command or "who developed you" in command:
        speak("I was created by Aalok Desai. He is my creator and developer.")
    elif "how are you" in command:
        speak("All systems optimal. How can I assist you?")
    elif "wikipedia" in command:
        speak("Searching Wikipedia...")
        q = command.replace("wikipedia","").strip()
        try: speak(wikipedia.summary(q, sentences=2))
        except: speak("Couldn't find that on Wikipedia.")
    elif "open youtube" in command:
        webbrowser.open("https://www.youtube.com"); speak("Opening YouTube.")
    elif "search" in command and "youtube" in command:
        q = command[command.find("search")+6:command.find("youtube")].strip().replace("on","").strip()
        webbrowser.open(f"https://www.youtube.com/results?search_query={q}")
        speak(f"Searching YouTube for {q}.")
    elif (
        "spotify" in command
        or "next song" in command
        or "previous song" in command
        or "pause music" in command
        or "resume music" in command
    ):
        spotify_flow(command)
    elif "play" in command:
        play_media_flow(command)
    elif "where is" in command or "locate" in command or ("search" in command and "maps" in command):
        loc = extract_maps_location(command)
        if loc:
            webbrowser.open(f"https://www.google.com/maps/search/{quote_plus(loc)}")
            speak(f"Locating {loc} on Google Maps.")
        else:
            webbrowser.open("https://www.google.co.in/maps/")
            speak("Opening Maps.")
    elif "maps" in command:
        webbrowser.open("https://www.google.co.in/maps/"); speak("Opening Maps.")
    elif "open google" in command:
        webbrowser.open("https://www.google.com"); speak("Opening Google.")
    elif "google" in command:
        q = command.replace("google","").replace("search","").strip()
        if q: webbrowser.open(f"https://www.google.com/search?q={q}"); speak(f"Searching for {q}.")
    elif "stack overflow" in command:
        webbrowser.open("https://stackoverflow.com"); speak("Opening Stack Overflow.")
    elif "github" in command:
        webbrowser.open("https://github.com"); speak("Opening GitHub.")
    elif "send email" in command or "send mail" in command or "compose email" in command:
        send_email_flow(command)
    elif "open gmail" in command or "gmail" in command:
        webbrowser.open("https://mail.google.com"); speak("Opening Gmail.")
    elif "amazon" in command:
        webbrowser.open("https://www.amazon.in/"); speak("Opening Amazon.")
    elif "flipkart" in command:
        webbrowser.open("https://www.flipkart.com/"); speak("Opening Flipkart.")
    elif "weather" in command:
        city = command.replace("weather","").replace("in","").strip() or load_settings().get("default_city", "Mumbai")
        get_weather(city)
    elif "news" in command:
        news()
    elif "movie" in command or "imdb" in command:
        movie(command)
    elif (
        "send message" in command
        or "send a message" in command
        or "send whatsapp" in command
        or "whatsapp" in command
        or "slack" in command
    ):
        send_message_flow(command)
    elif "screenshot" in command:
        take_screenshot()
    elif "volume up" in command:
        pyautogui.press("volumeup"); speak("Volume increased.")
    elif "volume down" in command:
        pyautogui.press("volumedown"); speak("Volume decreased.")
    elif "mute" in command:
        pyautogui.press("volumemute"); speak("Muted.")
    elif "minimise" in command or "minimize" in command:
        pyautogui.hotkey('win','d'); speak("Windows minimised.")
    elif "switch window" in command:
        pyautogui.keyDown("alt"); pyautogui.press("tab"); pyautogui.keyUp("alt")
        speak("Switching window.")
    elif "shutdown" in command or "turn off" in command:
        response = schedule_power_action("shutdown", 30)
        speak(response["message"])
    elif "restart" in command:
        response = schedule_power_action("restart", 30)
        speak(response["message"])
    elif "empty recycle bin" in command:
        try:
            import winshell
            winshell.recycle_bin().empty(confirm=False, show_progress=False, sound=True)
            speak("Recycle bin emptied.")
        except: speak("Couldn't empty recycle bin.")
    elif (
        "wireless phone setup" in command
        or "setup wireless phone" in command
        or "setup wireless adb" in command
        or "enable wireless adb" in command
    ):
        setup_wireless_phone_flow()
    elif (
        "pair wireless phone" in command
        or "pair wireless adb" in command
        or "wireless debugging pair" in command
    ):
        pair_wireless_phone_flow()
    elif (
        "connect wireless phone" in command
        or "connect phone wirelessly" in command
        or "connect wireless adb" in command
    ):
        connect_wireless_phone_flow(command)
    elif (
        "pick up call" in command
        or "pickup call" in command
        or "answer call" in command
        or "receive call" in command
    ):
        answer_phone_call_flow()
    elif (
        "disconnect call" in command
        or "end call" in command
        or "hang up" in command
        or "cut call" in command
    ):
        end_phone_call_flow()
    elif "call" in command:
        make_phone_call_flow(command)
    elif "open" in command:
        open_app(command.replace("open","").strip())
    elif "close" in command:
        app_names = extract_app_close_names(command)
        if not app_names:
            speak("Please tell me which app you would like to close.")
        else:
            speak_app_close_result(close_named_apps(app_names))
    elif "stop" in command or "exit" in command or "quit" in command or "goodbye" in command:
        hide_holographic_hud()
        stop_wake_word_detection()
        speak("Goodbye sir. Kabir signing off."); call_ui("stopAssistant")
    else:
        speak("I'm sorry, I didn't quite catch that. Please try again.")

# ─── Eel-exposed functions ─────────────────────────────────────────────────────
@eel.expose
def init():
    """Called by script.js on page load — real face authentication flow.
    
    IMPORTANT: Uses eel.spawn() not Thread() so that eel.sleep() inside
    AuthenticateFace() correctly pumps the gevent event loop and browser
    receives live camera frames.
    """
    def _run():
        eel.hideLoader()()
        eel.sleep(0.5)
        eel.showFaceAuth()()
        speak("Ready for Face Authentication. Please look at the camera.")

        flag = recoganize.AuthenticateFace()

        eel.hideFaceAuth()()
        eel.sleep(0.3)

        if flag == 1:
            speak("Face Authentication Successful.")
            eel.showFaceAuthSuccess()()
            eel.sleep(1.8)
            eel.hideFaceAuthSuccess()()
            eel.hideStart()()
            eel.sleep(0.3)
            greet()
            start_system_telemetry()
            start_wake_word_detection()
        else:
            speak("Face Authentication Failed. Access denied.")
            eel.showAuthFailed()()

    eel.spawn(_run)

@eel.expose
def greet():
    def _run():
        hour = datetime.datetime.now().hour
        if hour < 12:   g = "Good morning"
        elif hour < 18: g = "Good afternoon"
        else:           g = "Good evening"
        speak(f"{g} sir. Kabir is online. How can I help you today?")
    eel.spawn(_run)

@eel.expose
def start_voice_input():
    def _run():
        run_voice_command(source="voice")
    eel.spawn(_run)

@eel.expose
def speak_greeting():
    """Speak Kabir's greeting when the arc reactor is clicked."""
    def _run():
        speak("Hi! I am Kabir, your personal desktop assistant.")
    eel.spawn(_run)

@eel.expose
def handle_text_input(text):
    def _run():
        capture_or_process_text(text)
    eel.spawn(_run)

@eel.expose
def show_hud():
    return show_holographic_hud()

@eel.expose
def hide_hud():
    return hide_holographic_hud()

@eel.expose
def set_voice_engine(mode):
    success = set_tts_engine(mode)
    return {"success": success, **get_tts_status()}

@eel.expose
def get_voice_engine_status():
    return get_tts_status()


@eel.expose
def get_skill_suggestions():
    return {"success": True, "suggestions": get_skill_examples()}

@eel.expose
def health_check():
    with POWER_ACTION_LOCK:
        power = {
            "active": POWER_ACTION_ACTIVE,
            "action": POWER_ACTION_KIND,
            "seconds": max(0, int(POWER_ACTION_DEADLINE - time.time())) if POWER_ACTION_ACTIVE else 0,
        }
    return {
        "success": True,
        "status": "ok",
        "time": datetime.datetime.now().isoformat(timespec="seconds"),
        "activeTask": LAST_ACTIVE_TASK,
        "wakeWordActive": bool(WAKE_WORD_THREAD and WAKE_WORD_THREAD.is_alive()),
        "telemetryActive": bool(TELEMETRY_THREAD and TELEMETRY_THREAD.is_alive()),
        "powerAction": power,
    }

@eel.expose
def request_shutdown():
    return schedule_power_action("shutdown", 30)

@eel.expose
def request_restart():
    return schedule_power_action("restart", 30)

@eel.expose
def cancel_shutdown():
    return cancel_power_action()

@eel.expose
def get_logs(limit=200):
    try:
        max_lines = max(1, min(int(limit or 200), 1000))
    except (TypeError, ValueError):
        max_lines = 200
    try:
        if not LOG_PATH.exists():
            return {"success": True, "lines": []}
        with LOG_PATH.open("r", encoding="utf-8", errors="replace") as file:
            lines = file.readlines()[-max_lines:]
        return {"success": True, "lines": [line.rstrip("\n") for line in lines]}
    except OSError as e:
        return {"success": False, "message": f"Log load failed: {str(e)}", "lines": []}

@eel.expose
def get_history(limit=80):
    try:
        max_rows = max(1, min(int(limit or 80), 200))
    except (TypeError, ValueError):
        max_rows = 80

    try:
        with HISTORY_DB_LOCK, get_history_connection() as conn:
            commands = [
                dict(row)
                for row in conn.execute(
                    """
                    SELECT id, command, source, created_at
                    FROM command_history
                    ORDER BY created_at DESC, id DESC
                    LIMIT ?
                    """,
                    (max_rows,),
                )
            ]
            messages = [
                dict(row)
                for row in conn.execute(
                    """
                    SELECT id, speaker, message, created_at
                    FROM conversation_history
                    ORDER BY created_at DESC, id DESC
                    LIMIT ?
                    """,
                    (max_rows,),
                )
            ]
            frequent = [
                dict(row)
                for row in conn.execute(
                    """
                    SELECT command, COUNT(*) AS uses, MAX(created_at) AS last_used
                    FROM command_history
                    GROUP BY LOWER(command)
                    ORDER BY uses DESC, last_used DESC
                    LIMIT 10
                    """
                )
            ]
        return {"success": True, "commands": commands, "messages": messages, "frequent": frequent}
    except sqlite3.Error as e:
        return {"success": False, "message": f"History load failed: {str(e)}", "commands": [], "messages": [], "frequent": []}


@eel.expose
def get_recent_chat(limit=40):
    try:
        max_rows = max(1, min(int(limit or 40), 200))
    except (TypeError, ValueError):
        max_rows = 40

    try:
        with HISTORY_DB_LOCK, get_history_connection() as conn:
            rows = [
                dict(row)
                for row in conn.execute(
                    """
                    SELECT id, speaker, message, created_at
                    FROM conversation_history
                    ORDER BY created_at DESC, id DESC
                    LIMIT ?
                    """,
                    (max_rows,),
                )
            ]
        rows.reverse()
        return {"success": True, "messages": rows}
    except sqlite3.Error as e:
        return {"success": False, "message": f"Chat load failed: {str(e)}", "messages": []}


@eel.expose
def clear_chat_history():
    try:
        with HISTORY_DB_LOCK, get_history_connection() as conn:
            conn.execute("DELETE FROM conversation_history")
        return {"success": True, "message": "Chat history cleared."}
    except sqlite3.Error as e:
        return {"success": False, "message": f"Clear chat failed: {str(e)}"}


@eel.expose
def clear_all_history():
    try:
        with HISTORY_DB_LOCK, get_history_connection() as conn:
            conn.execute("DELETE FROM command_history")
            conn.execute("DELETE FROM conversation_history")
        return {"success": True, "message": "Command and chat history cleared."}
    except sqlite3.Error as e:
        return {"success": False, "message": f"Clear history failed: {str(e)}"}


@eel.expose
def get_app_settings():
    return {"success": True, "settings": load_settings()}


def apply_runtime_settings(settings):
    global TTS_ENGINE_MODE, NEURAL_TTS_RATE, WAKE_WORD_PHRASE, PORCUPINE_KEYWORD_PATH
    global PORCUPINE_BUILTIN_KEYWORD, PORCUPINE_SENSITIVITY

    TTS_ENGINE_MODE = settings.get("voice_engine", TTS_ENGINE_MODE)
    NEURAL_TTS_RATE = settings.get("voice_rate", NEURAL_TTS_RATE)
    WAKE_WORD_PHRASE = settings.get("wake_word_phrase", WAKE_WORD_PHRASE)
    PORCUPINE_KEYWORD_PATH = settings.get("wake_word_keyword_path", PORCUPINE_KEYWORD_PATH)
    PORCUPINE_BUILTIN_KEYWORD = settings.get("wake_word_builtin_keyword", PORCUPINE_BUILTIN_KEYWORD)
    PORCUPINE_SENSITIVITY = str(settings.get("wake_word_sensitivity", settings.get("porcupine_sensitivity", PORCUPINE_SENSITIVITY)))


apply_runtime_settings(load_settings())


@eel.expose
def save_app_settings(settings):
    try:
        saved = save_settings(settings or {})
        apply_runtime_settings(saved)
        apply_history_retention()
        return {"success": True, "settings": saved, "message": "Settings saved."}
    except Exception as e:
        return {"success": False, "message": f"Settings save failed: {str(e)}", "settings": load_settings()}


@eel.expose
def search_memory(query="", limit=30):
    query = (query or "").strip()
    if not query:
        return {"success": True, "results": []}
    start_date, end_date, date_label = parse_memory_date_window(query)
    clean_query = extract_memory_query(query) or query
    records = search_memory_records(query=clean_query, start_date=start_date, end_date=end_date, limit=limit)
    if not records and clean_query != query:
        records = search_memory_records(query=query, start_date=start_date, end_date=end_date, limit=limit)
    if not records and start_date:
        records = search_memory_records(query="", start_date=start_date, end_date=end_date, limit=limit)
    return {
        "success": True,
        "results": records,
        "query": clean_query,
        "date_label": date_label,
    }


@eel.expose
def remember_knowledge_item(title="", body="", url="", source="manual"):
    save_knowledge_entry(title, body, url, source)
    return {"success": True, "message": "Memory saved."}

@eel.expose
def replay_history_command(command_id):
    try:
        with HISTORY_DB_LOCK, get_history_connection() as conn:
            row = conn.execute(
                "SELECT command FROM command_history WHERE id = ?",
                (command_id,),
            ).fetchone()
    except sqlite3.Error as e:
        return {"success": False, "message": f"Replay failed: {str(e)}"}

    if not row:
        return {"success": False, "message": "Command was not found."}

    def _run():
        process_command(row["command"], source="history")
    eel.spawn(_run)
    return {"success": True, "message": "Replaying command.", "command": row["command"]}

@eel.expose
def replay_history_text(command):
    command = (command or "").strip()
    if not command:
        return {"success": False, "message": "Command is empty."}

    def _run():
        process_command(command.lower(), source="history")
    eel.spawn(_run)
    return {"success": True, "message": "Replaying command.", "command": command}

@eel.expose
def get_mail_profile():
    return load_mail_profile(include_password=False)

@eel.expose
def save_profile(profile):
    try:
        saved = save_mail_profile(profile)
        return {"success": True, "profile": saved, "message": "Profile saved."}
    except Exception as e:
        return {"success": False, "message": f"Profile save failed: {str(e)}"}

@eel.expose
def get_mail_profile_status():
    return get_profile_status()

@eel.expose
def get_contacts():
    try:
        return {"success": True, "contacts": list_contacts()}
    except Exception as e:
        return {"success": False, "message": f"Contacts load failed: {str(e)}", "contacts": []}

@eel.expose
def save_contact(contact):
    try:
        saved = save_saved_contact(contact or {})
        return {"success": True, "contact": saved, "message": "Contact saved."}
    except Exception as e:
        return {"success": False, "message": f"Contact save failed: {str(e)}"}

@eel.expose
def delete_contact(contact_id):
    try:
        if delete_saved_contact(contact_id):
            return {"success": True, "message": "Contact deleted."}
        return {"success": False, "message": "Contact was not found."}
    except Exception as e:
        return {"success": False, "message": f"Contact delete failed: {str(e)}"}

@eel.expose
def search_files(query, root=None, limit=80):
    query = (query or "").strip().lower()
    normalized_query = query.replace("\\", "/")
    compact_query = normalize_file_search_text(query)
    root_text = (root or "").strip()
    try:
        max_results = max(1, min(int(limit or 80), 200))
    except (TypeError, ValueError):
        max_results = 80

    if not query:
        return {"success": False, "message": "Enter a file name to search.", "results": []}
    if root_text:
        search_roots = [Path(root_text).expanduser()]
    else:
        search_roots = [Path(__file__).resolve().parent, Path.home()]

    valid_roots = []
    seen_roots = set()
    for root_path in search_roots:
        try:
            resolved = root_path.resolve()
        except OSError:
            resolved = root_path
        root_key = str(resolved).lower()
        if root_key in seen_roots:
            continue
        seen_roots.add(root_key)
        if resolved.exists() and resolved.is_dir():
            valid_roots.append(resolved)

    if not valid_roots:
        return {"success": False, "message": "Search folder was not found.", "results": []}

    results = []
    try:
        for root_path in valid_roots:
            for current_root, dirs, files in os.walk(root_path):
                dirs[:] = [
                    d for d in dirs
                    if d not in FILE_SEARCH_EXCLUDED_DIRS and not d.startswith(".")
                ]

                for name in files:
                    file_path = Path(current_root) / name
                    path_text = str(file_path).lower()
                    compact_name = normalize_file_search_text(name)
                    compact_path = normalize_file_search_text(str(file_path))
                    name_match = query in name.lower()
                    path_match = query in path_text or normalized_query in path_text.replace("\\", "/")
                    compact_name_match = bool(compact_query and compact_query in compact_name)
                    compact_path_match = bool(compact_query and compact_query in compact_path)
                    if not name_match and not path_match and not compact_name_match and not compact_path_match:
                        continue

                    try:
                        stat = file_path.stat()
                    except OSError:
                        continue

                    results.append({
                        "name": name,
                        "path": str(file_path),
                        "folder": str(file_path.parent),
                        "size": stat.st_size,
                        "modified": datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%d %b %Y %I:%M %p"),
                        "type": file_path.suffix[1:].upper() or "FILE",
                        "match": "NAME" if name_match or compact_name_match else "PATH",
                    })

                    if len(results) >= max_results:
                        return {"success": True, "message": f"Showing first {max_results} matches.", "results": results}
    except OSError as e:
        return {"success": False, "message": f"Search failed: {str(e)}", "results": results}

    message = f"Found {len(results)} match{'es' if len(results) != 1 else ''}."
    return {"success": True, "message": message, "results": results}

def path_is_inside(path, root):
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False

def get_configured_safe_file_roots():
    roots = list(DEFAULT_SAFE_FILE_ROOTS)
    for raw_root in load_settings().get("safe_file_roots", []):
        try:
            root = Path(raw_root).expanduser().resolve(strict=True)
        except (OSError, RuntimeError):
            continue
        if root.is_dir() and not any(root == existing for existing in roots):
            roots.append(root)
    return tuple(roots)

def validate_safe_file_path(path):
    raw_path = str(path or "").strip()
    if not raw_path:
        return None, "File path is empty."
    if "\x00" in raw_path or "\n" in raw_path or "\r" in raw_path:
        return None, "File path contains invalid characters."

    lowered = raw_path.lower()
    if lowered.startswith(("\\\\.\\", "\\\\?\\")):
        return None, "Device paths are not allowed."
    parsed = urlparse(raw_path)
    if parsed.scheme and len(parsed.scheme) > 1:
        return None, "URLs and shell targets are not allowed."

    try:
        file_path = Path(raw_path).expanduser().resolve(strict=True)
    except (OSError, RuntimeError):
        return None, "File was not found."

    if not (file_path.is_file() or file_path.is_dir()):
        return None, "Only files and folders can be opened."
    if not any(path_is_inside(file_path, root) for root in get_configured_safe_file_roots()):
        return None, "Blocked unsafe path. Open files only from approved local folders."
    return file_path, ""

@eel.expose
def open_file_path(path):
    try:
        file_path, error = validate_safe_file_path(path)
        if error:
            return {"success": False, "message": error}
        os.startfile(str(file_path))
        return {"success": True, "message": "Opening file."}
    except Exception as e:
        return {"success": False, "message": f"Open failed: {str(e)}"}

@eel.expose
def reveal_file_path(path):
    try:
        file_path, error = validate_safe_file_path(path)
        if error:
            return {"success": False, "message": error}
        subprocess.Popen(["explorer", "/select,", str(file_path)])
        return {"success": True, "message": "Showing file in Explorer."}
    except Exception as e:
        return {"success": False, "message": f"Reveal failed: {str(e)}"}

# ─── Launch ──────────────────────────────────────────────────────────────────
def run_daemon(target, *args):
    thread = Thread(target=target, args=args, daemon=True)
    thread.start()
    return thread

def open_kabir_window(icon=None, item=None):
    for browser in ("msedge.exe", "chrome.exe"):
        try:
            subprocess.Popen(
                ["cmd", "/c", "start", "", browser, f"--app={APP_URL}"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return
        except Exception:
            pass
    webbrowser.open(APP_URL)

def open_kabir_settings(icon=None, item=None):
    open_kabir_window()
    set_status("Open Settings from the sidebar.")

def run_tray_command(command):
    def _run():
        process_command(command, source="tray")
    run_daemon(_run)

def tray_listen_once(icon=None, item=None):
    run_daemon(run_voice_command, "tray")

def tray_greet(icon=None, item=None):
    run_daemon(lambda: speak("Kabir is running in the system tray."))

def tray_start_wake_word(icon=None, item=None):
    start_wake_word_detection()
    set_status(f"Wake word active: {WAKE_WORD_PHRASE}")

def tray_stop_wake_word(icon=None, item=None):
    stop_wake_word_detection()
    set_status("Wake word stopped.")

def tray_toggle_wake_word(icon=None, item=None):
    if WAKE_WORD_THREAD and WAKE_WORD_THREAD.is_alive():
        tray_stop_wake_word(icon, item)
    else:
        tray_start_wake_word(icon, item)

def tray_schedule_shutdown(icon=None, item=None):
    response = schedule_power_action("shutdown", 30)
    set_status(response["message"])

def tray_schedule_restart(icon=None, item=None):
    response = schedule_power_action("restart", 30)
    set_status(response["message"])

def tray_restart_backend(icon=None, item=None):
    logger.warning("Restarting Kabir backend from tray")
    cleanup_background_services()
    if icon:
        icon.visible = False
        icon.stop()
    os.execv(sys.executable, [sys.executable] + sys.argv)

def tray_quit(icon=None, item=None):
    logger.info("Quit requested from tray")
    cleanup_background_services()
    if icon:
        icon.visible = False
        icon.stop()
    raise SystemExit(0)

def create_tray_image():
    image = Image.new("RGBA", (64, 64), (16, 20, 28, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((8, 8, 56, 56), radius=14, fill=(19, 28, 42, 255))
    draw.ellipse((18, 18, 46, 46), fill=(60, 180, 150, 255))
    draw.ellipse((26, 26, 38, 38), fill=(245, 248, 252, 255))
    return image

def create_tray_menu():
    return pystray.Menu(
        pystray.MenuItem("Open Kabir", open_kabir_window, default=True),
        pystray.MenuItem("Open Settings", open_kabir_settings),
        pystray.MenuItem("Listen once", tray_listen_once),
        pystray.MenuItem("Greet", tray_greet),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Open YouTube", lambda icon, item: run_tray_command("open youtube")),
        pystray.MenuItem("Open Google", lambda icon, item: run_tray_command("open google")),
        pystray.MenuItem("Open Gmail", lambda icon, item: run_tray_command("open gmail")),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Start wake word", tray_start_wake_word),
        pystray.MenuItem("Stop wake word", tray_stop_wake_word),
        pystray.MenuItem("Toggle wake word", tray_toggle_wake_word),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Schedule Windows shutdown", tray_schedule_shutdown),
        pystray.MenuItem("Schedule Windows restart", tray_schedule_restart),
        pystray.MenuItem("Restart Kabir backend", tray_restart_backend),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Quit Kabir", tray_quit),
    )

def start_eel_server():
    eel.start(APP_PAGE, mode=None, host=APP_HOST, port=APP_PORT, block=True)

def start_tray_app():
    global TRAY_ICON
    if pystray is None or Image is None or ImageDraw is None:
        raise RuntimeError("pystray is required for tray mode. Install it with: pip install pystray")

    run_daemon(start_eel_server)
    start_system_telemetry()
    time.sleep(1.0)
    logger.info("Kabir is online at %s", APP_URL)
    open_kabir_window()
    TRAY_ICON = pystray.Icon(
        "Kabir",
        create_tray_image(),
        "Kabir",
        create_tray_menu(),
    )
    TRAY_ICON.run()

if __name__ == "__main__":
    start_tray_app()
