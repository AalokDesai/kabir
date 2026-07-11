import json
from pathlib import Path
from threading import Lock


SETTINGS_PATH = Path(__file__).with_name("settings.json")
SETTINGS_LOCK = Lock()

DEFAULT_SETTINGS = {
    "default_city": "Mumbai",
    "preferred_music_platform": "youtube",
    "voice_engine": "neural",
    "voice_rate": "+20%",
    "theme": "dark",
    "wake_word_enabled": False,
    "wake_word_phrase": "Hey Kabir",
    "wake_word_builtin_keyword": "kabir",
    "wake_word_keyword_path": "",
    "wake_word_sensitivity": "0.65",
    "history_max_items": 5000,
    "history_retention_days": 180,
    "safe_file_roots": [],
}


def _clean_settings(settings):
    clean = DEFAULT_SETTINGS.copy()
    if isinstance(settings, dict):
        clean.update(settings)

    clean["default_city"] = str(clean.get("default_city") or "Mumbai").strip() or "Mumbai"
    clean["preferred_music_platform"] = str(clean.get("preferred_music_platform") or "youtube").strip().lower()
    if clean["preferred_music_platform"] not in {"youtube", "spotify"}:
        clean["preferred_music_platform"] = "youtube"

    clean["voice_engine"] = str(clean.get("voice_engine") or "neural").strip().lower()
    if clean["voice_engine"] not in {"neural", "edge", "local"}:
        clean["voice_engine"] = "neural"
    clean["voice_rate"] = str(clean.get("voice_rate") or "+20%").strip() or "+20%"

    clean["theme"] = str(clean.get("theme") or "dark").strip().lower()
    if clean["theme"] not in {"dark", "light"}:
        clean["theme"] = "dark"

    clean["wake_word_enabled"] = bool(clean.get("wake_word_enabled", False))
    clean["wake_word_phrase"] = str(clean.get("wake_word_phrase") or "Hey Kabir").strip() or "Hey Kabir"
    clean["wake_word_builtin_keyword"] = str(clean.get("wake_word_builtin_keyword") or "kabir").strip().lower() or "kabir"
    clean["wake_word_keyword_path"] = str(clean.get("wake_word_keyword_path") or "").strip()
    try:
        sensitivity = max(0.0, min(1.0, float(clean.get("wake_word_sensitivity") or 0.65)))
    except (TypeError, ValueError):
        sensitivity = 0.65
    clean["wake_word_sensitivity"] = f"{sensitivity:.2f}"

    try:
        clean["history_max_items"] = max(100, min(int(clean.get("history_max_items") or 5000), 50000))
    except (TypeError, ValueError):
        clean["history_max_items"] = 5000
    try:
        clean["history_retention_days"] = max(1, min(int(clean.get("history_retention_days") or 180), 3650))
    except (TypeError, ValueError):
        clean["history_retention_days"] = 180

    roots = clean.get("safe_file_roots") or []
    if not isinstance(roots, list):
        roots = []
    clean["safe_file_roots"] = [str(root).strip() for root in roots if str(root).strip()]
    return clean


def load_settings():
    with SETTINGS_LOCK:
        if not SETTINGS_PATH.exists():
            return DEFAULT_SETTINGS.copy()
        try:
            with SETTINGS_PATH.open("r", encoding="utf-8") as file:
                return _clean_settings(json.load(file))
        except (OSError, json.JSONDecodeError):
            return DEFAULT_SETTINGS.copy()


def save_settings(settings):
    clean = _clean_settings(settings)
    with SETTINGS_LOCK:
        SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with SETTINGS_PATH.open("w", encoding="utf-8") as file:
            json.dump(clean, file, indent=2)
    return clean
