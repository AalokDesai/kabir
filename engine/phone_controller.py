import os
import json
import re
import shutil
import subprocess
import time
from pathlib import Path


ADB = "adb"
PHONE_PROFILE_PATH = Path(__file__).with_name("phone_profile.json")
PHONE_NUMBER_RE = re.compile(r"\+?\d[\d\s\-()]{5,}\d")
BLOCKED_NUMBERS = {"100", "101", "102", "108", "112", "911", "999"}


def extract_phone_number(text):
    match = PHONE_NUMBER_RE.search(text or "")
    if not match:
        return ""
    return re.sub(r"[^\d+]", "", match.group(0))


def normalize_contact_name(text):
    text = (text or "").lower()
    for word in ["call", "phone", "mobile", "number", "to", "make", "a"]:
        text = re.sub(rf"\b{re.escape(word)}\b", "", text)
    return " ".join(text.split())


def _find_adb():
    env_adb = os.environ.get("ADB_PATH", "").strip()
    if env_adb and Path(env_adb).is_file():
        return env_adb

    path_adb = shutil.which(ADB)
    if path_adb:
        return path_adb

    user_home = Path.home()
    candidates = [
        user_home / "Downloads" / "platform-tools-latest-windows" / "platform-tools" / "adb.exe",
        user_home / "Downloads" / "platform-tools" / "adb.exe",
        Path("C:/platform-tools/adb.exe"),
    ]
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    return ""


def _run_adb(args, timeout=12, serial=""):
    adb_path = _find_adb()
    if not adb_path:
        return False, "ADB was not found. Add platform-tools to PATH or set ADB_PATH to adb.exe."

    command = [adb_path]
    if serial:
        command.extend(["-s", serial])
    command.extend(args)

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return False, "ADB command timed out. Check the Android phone connection."
    except Exception as e:
        return False, f"ADB error: {e}"

    output = (result.stdout or result.stderr or "").strip()
    if result.returncode != 0:
        if "no devices" in output.lower() or "device" in output.lower():
            return False, "No authorized Android device found. Connect phone and allow USB debugging."
        return False, output or "ADB command failed."
    return True, output


def _load_phone_profile():
    if not PHONE_PROFILE_PATH.exists():
        return {}
    try:
        with open(PHONE_PROFILE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def _save_phone_profile(profile):
    with open(PHONE_PROFILE_PATH, "w", encoding="utf-8") as f:
        json.dump(profile, f, indent=2)


def _parse_connected_devices(output):
    devices = []
    for line in output.splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "device":
            devices.append(parts[0])
    return devices


def _is_private_ipv4(address):
    parts = address.split(".")
    if len(parts) != 4:
        return False
    try:
        octets = [int(part) for part in parts]
    except ValueError:
        return False
    if any(octet < 0 or octet > 255 for octet in octets):
        return False
    return (
        octets[0] == 10
        or (octets[0] == 172 and 16 <= octets[1] <= 31)
        or (octets[0] == 192 and octets[1] == 168)
    )


def _first_private_ipv4(output):
    for address in re.findall(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", output or ""):
        if _is_private_ipv4(address):
            return address
    return ""


def _get_wifi_ip(serial=""):
    commands = [
        ["shell", "ip", "route", "get", "8.8.8.8"],
        ["shell", "ip", "route"],
        ["shell", "ip", "-f", "inet", "addr", "show"],
        ["shell", "ifconfig"],
        ["shell", "getprop", "dhcp.wlan0.ipaddress"],
        ["shell", "getprop", "dhcp.wifi.ipaddress"],
    ]
    for args in commands:
        success, output = _run_adb(args, timeout=8, serial=serial)
        if not success:
            continue

        match = re.search(r"\bsrc\s+(\d+\.\d+\.\d+\.\d+)", output)
        if match and _is_private_ipv4(match.group(1)):
            return True, match.group(1)

        match = re.search(r"\binet(?:\s+addr:|\s+)(\d+\.\d+\.\d+\.\d+)", output)
        if match and _is_private_ipv4(match.group(1)):
            return True, match.group(1)

        address = _first_private_ipv4(output)
        if address:
            return True, address

    return False, "Could not detect phone Wi-Fi IP. Make sure phone and laptop are on the same Wi-Fi."


def connect_wireless_adb(address=None):
    profile = _load_phone_profile()
    address = (address or profile.get("wireless_address", "")).strip()
    if not address:
        return False, "No wireless phone address saved. Run wireless phone setup once with USB connected."
    if ":" not in address:
        address = f"{address}:5555"

    success, output = _run_adb(["connect", address], timeout=15)
    if not success:
        return False, output

    if "connected" not in output.lower() and "already connected" not in output.lower():
        return False, output or f"Could not connect to {address}."

    profile["wireless_address"] = address
    _save_phone_profile(profile)
    return True, f"Wireless Android connected at {address}."


def setup_wireless_adb():
    success, output = _run_adb(["devices"])
    if not success:
        return False, output

    devices = _parse_connected_devices(output)
    usb_devices = [device for device in devices if ":" not in device]
    if not usb_devices:
        return False, "Connect your Android phone with USB once, allow debugging, then run wireless setup."

    usb_serial = usb_devices[0]
    success, ip_or_message = _get_wifi_ip(usb_serial)
    if not success:
        return False, ip_or_message

    success, output = _run_adb(["tcpip", "5555"], timeout=15, serial=usb_serial)
    if not success:
        return False, output

    time.sleep(2)
    address = f"{ip_or_message}:5555"
    success, message = connect_wireless_adb(address)
    if not success:
        return False, message
    return True, f"Wireless calling is ready. You can unplug USB. Phone connected at {address}."


def pair_wireless_adb(pair_address, pair_code, connect_address=""):
    pair_address = (pair_address or "").strip()
    pair_code = (pair_code or "").strip()
    connect_address = (connect_address or "").strip()

    if not pair_address or not pair_code:
        return False, "Pairing address and pairing code are required."

    success, output = _run_adb(["pair", pair_address, pair_code], timeout=20)
    if not success:
        return False, output

    if connect_address:
        return connect_wireless_adb(connect_address)
    return True, "Wireless debugging paired. Now run connect phone wirelessly with the connection IP and port."


def get_connected_devices():
    success, output = _run_adb(["devices"])
    if not success:
        return False, output

    devices = _parse_connected_devices(output)

    if not devices:
        connect_wireless_adb()
        success, output = _run_adb(["devices"])
        if success:
            devices = _parse_connected_devices(output)

    if not devices:
        return False, "No authorized Android device found. Connect USB, or run wireless phone setup."
    return True, f"Android device connected: {devices[0]}"


def is_blocked_number(number):
    digits = re.sub(r"\D", "", number or "")
    return digits in BLOCKED_NUMBERS


def make_call(number):
    number = extract_phone_number(number) or re.sub(r"[^\d+]", "", number or "")
    if not number:
        return False, "Phone number is missing."
    if is_blocked_number(number):
        return False, "Emergency numbers are blocked from voice automation."

    success, message = get_connected_devices()
    if not success:
        return False, message

    success, output = _run_adb(
        ["shell", "am", "start", "-a", "android.intent.action.CALL", "-d", f"tel:{number}"]
    )
    if not success:
        return False, output
    return True, f"Calling {number} from your Android phone."


def answer_call():
    success, message = get_connected_devices()
    if not success:
        return False, message
    success, output = _run_adb(["shell", "input", "keyevent", "KEYCODE_CALL"])
    if not success:
        return False, output
    return True, "Incoming call picked up on your Android phone."


def end_call():
    success, message = get_connected_devices()
    if not success:
        return False, message
    success, output = _run_adb(["shell", "input", "keyevent", "KEYCODE_ENDCALL"])
    if not success:
        return False, output
    return True, "Call disconnected on your Android phone."
