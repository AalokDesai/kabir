import base64
import json
import re
import uuid
from datetime import datetime
from pathlib import Path
from threading import Lock

import win32crypt


CONTACT_STORE_PATH = Path(__file__).with_name("contacts.json.enc")
CONTACT_STORE_LOCK = Lock()


def _now():
    return datetime.now().isoformat(timespec="seconds")


def normalize_contact_key(value):
    value = (value or "").strip().lower()
    value = re.sub(r"[^a-z0-9@._+\-\s]", " ", value)
    return " ".join(value.split())


def _empty_store():
    return {"version": 1, "contacts": []}


def _protect(data):
    protected = win32crypt.CryptProtectData(data, None, None, None, None, 0)
    return base64.b64encode(protected).decode("ascii")


def _unprotect(value):
    protected = base64.b64decode(value.encode("ascii"))
    _, data = win32crypt.CryptUnprotectData(protected, None, None, None, 0)
    return data


def _load_store_unlocked():
    if not CONTACT_STORE_PATH.exists():
        return _empty_store()

    with open(CONTACT_STORE_PATH, "r", encoding="utf-8") as file:
        wrapper = json.load(file)

    payload = _unprotect(wrapper.get("protected_data", ""))
    data = json.loads(payload.decode("utf-8"))
    if not isinstance(data, dict):
        return _empty_store()

    contacts = data.get("contacts")
    if not isinstance(contacts, list):
        data["contacts"] = []
    data["version"] = 1
    return data


def _save_store_unlocked(data):
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    wrapper = {"version": 1, "protected_data": _protect(payload)}
    with open(CONTACT_STORE_PATH, "w", encoding="utf-8") as file:
        json.dump(wrapper, file, indent=2)


def _clean_contact(contact):
    name = str(contact.get("name", "")).strip()
    phone = str(contact.get("phone", "")).strip()
    email = str(contact.get("email", "")).strip().lower()
    aliases = contact.get("aliases", [])
    if isinstance(aliases, str):
        aliases = re.split(r"[,;\n]", aliases)

    clean_aliases = []
    for alias in aliases if isinstance(aliases, list) else []:
        clean = normalize_contact_key(alias)
        if clean and clean not in clean_aliases:
            clean_aliases.append(clean)

    normalized_name = normalize_contact_key(name)
    if normalized_name and normalized_name not in clean_aliases:
        clean_aliases.insert(0, normalized_name)

    return {
        "id": str(contact.get("id") or uuid.uuid4()),
        "name": name,
        "phone": phone,
        "email": email,
        "aliases": clean_aliases,
        "created_at": str(contact.get("created_at") or _now()),
        "updated_at": _now(),
    }


def list_contacts():
    with CONTACT_STORE_LOCK:
        data = _load_store_unlocked()
        return sorted(data["contacts"], key=lambda item: item.get("name", "").lower())


def save_contact(contact):
    clean = _clean_contact(contact or {})
    if not clean["name"]:
        raise ValueError("Contact name is required.")
    if not clean["phone"] and not clean["email"]:
        raise ValueError("Add a phone number, an email address, or both.")

    with CONTACT_STORE_LOCK:
        data = _load_store_unlocked()
        contacts = []
        replaced = False
        for existing in data["contacts"]:
            if existing.get("id") == clean["id"]:
                clean["created_at"] = existing.get("created_at") or clean["created_at"]
                contacts.append(clean)
                replaced = True
            else:
                contacts.append(existing)
        if not replaced:
            contacts.append(clean)
        data["contacts"] = contacts
        _save_store_unlocked(data)
    return clean


def delete_contact(contact_id):
    contact_id = str(contact_id or "").strip()
    if not contact_id:
        return False

    with CONTACT_STORE_LOCK:
        data = _load_store_unlocked()
        original_count = len(data["contacts"])
        data["contacts"] = [item for item in data["contacts"] if item.get("id") != contact_id]
        changed = len(data["contacts"]) != original_count
        if changed:
            _save_store_unlocked(data)
        return changed


def find_contact(value):
    key = normalize_contact_key(value)
    if not key:
        return None

    for contact in list_contacts():
        aliases = contact.get("aliases") or []
        if key == normalize_contact_key(contact.get("name")) or key in aliases:
            return contact
    return None


def get_phone_number(value):
    contact = find_contact(value)
    return (contact or {}).get("phone", "")


def get_email_address(value):
    contact = find_contact(value)
    return (contact or {}).get("email", "")
