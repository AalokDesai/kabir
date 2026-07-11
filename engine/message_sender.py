import json
import os
import shutil
import subprocess
import time
import webbrowser

import pyautogui


NODE_BRIDGE = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "integrations",
    "messaging",
    "send_message.js",
)

SUPPORTED_PLATFORMS = {"whatsapp", "slack"}
SLACK_DESKTOP_URI = "slack:"


def normalize_platform(text):
    text = (text or "").strip().lower()
    if "whatsapp" in text or "what's app" in text or "what app" in text:
        return "whatsapp"
    if "slack" in text:
        return "slack"
    return ""


def normalize_whatsapp_mode(text):
    text = (text or "").strip().lower()
    if "desktop" in text or "app" in text or "application" in text:
        return "desktop"
    if "web" in text or "browser" in text:
        return "web"
    return ""


def send_platform_message(platform, recipient, message, whatsapp_mode="web"):
    platform = normalize_platform(platform)
    if platform == "whatsapp":
        return send_whatsapp_message(recipient, message, whatsapp_mode)
    if platform == "slack":
        return send_slack_desktop_message(recipient, message)
    return False, "That messaging platform is not supported yet."


def _paste_text(text):
    try:
        import pyperclip

        pyperclip.copy(text)
        pyautogui.hotkey("ctrl", "v")
    except Exception:
        pyautogui.typewrite(text)


def send_whatsapp_message(recipient, message, mode="web"):
    if not recipient or not message:
        return False, "WhatsApp recipient and message are required."

    mode = normalize_whatsapp_mode(mode) or "web"
    if mode == "desktop":
        return send_whatsapp_desktop_message(recipient, message)
    return send_whatsapp_web_message(recipient, message)


def send_whatsapp_web_message(recipient, message):
    webbrowser.open("https://web.whatsapp.com/", new=2)
    time.sleep(25)

    pyautogui.click(250, 218)
    pyautogui.hotkey("ctrl", "a")
    pyautogui.press("backspace")
    time.sleep(0.5)
    _paste_text(recipient)
    time.sleep(1.5)
    pyautogui.press("enter")
    time.sleep(1)

    pyautogui.click(835, 956)
    _paste_text(message)
    pyautogui.press("enter")
    return True, f"WhatsApp Web message sent to {recipient}."


def send_whatsapp_desktop_message(recipient, message):
    try:
        os.startfile("whatsapp:")
    except Exception:
        webbrowser.open("whatsapp://")

    time.sleep(10)
    pyautogui.hotkey("ctrl", "f")
    time.sleep(0.5)
    pyautogui.hotkey("ctrl", "a")
    pyautogui.press("backspace")
    _paste_text(recipient)
    time.sleep(2.5)
    pyautogui.press("enter")
    time.sleep(2)
    _paste_text(message)
    pyautogui.press("enter")
    return True, f"WhatsApp Desktop message sent to {recipient}."


def _activate_window(title, timeout=10):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            windows = pyautogui.getWindowsWithTitle(title)
            if windows:
                window = windows[0]
                if window.isMinimized:
                    window.restore()
                window.activate()
                time.sleep(0.8)
                return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


def _open_slack_desktop():
    try:
        os.startfile(SLACK_DESKTOP_URI)
    except Exception:
        slack_exe = os.path.join(
            os.environ.get("LOCALAPPDATA", ""),
            "slack",
            "slack.exe",
        )
        if os.path.exists(slack_exe):
            subprocess.Popen([slack_exe])
        else:
            return False

    return _activate_window("Slack", timeout=15)


def send_slack_desktop_message(recipient, message):
    if not recipient or not message:
        return False, "Slack recipient and message are required."

    if not _open_slack_desktop():
        return (
            False,
            "I couldn't open the Slack desktop app. Please make sure Slack is installed and signed in.",
        )

    # Slack desktop quick switcher accepts channels, people, and DMs.
    pyautogui.hotkey("ctrl", "k")
    time.sleep(0.7)
    pyautogui.hotkey("ctrl", "a")
    pyautogui.press("backspace")
    _paste_text(recipient)
    time.sleep(1.2)
    pyautogui.press("enter")
    time.sleep(1.2)
    _paste_text(message)
    pyautogui.press("enter")
    return True, f"Slack desktop message sent to {recipient}."


def send_with_node_bridge(platform, recipient, message):
    if not os.path.exists(NODE_BRIDGE):
        return False, "Node messaging bridge is missing."
    if shutil.which("node") is None:
        return False, "Node.js is not installed, so Slack messaging cannot run yet."

    payload = json.dumps(
        {"platform": platform, "recipient": recipient, "message": message},
        ensure_ascii=True,
    )

    result = subprocess.run(
        ["node", NODE_BRIDGE, payload],
        capture_output=True,
        text=True,
        timeout=30,
    )

    output = (result.stdout or result.stderr or "").strip()
    if result.returncode == 0:
        return True, output or f"{platform.title()} message sent."
    return False, output or f"{platform.title()} message failed."
