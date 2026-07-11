import os
import time
import urllib.parse
import webbrowser

import pyautogui


SPOTIFY_WEB_PLAYER = "https://open.spotify.com"
SPOTIFY_SEARCH_LOAD_SECONDS = 10


def _open_target(target):
    try:
        if os.name == "nt" and target.startswith("spotify:"):
            os.startfile(target)
        else:
            webbrowser.open(target, new=2)
        return True
    except Exception:
        if target.startswith("spotify:"):
            webbrowser.open(SPOTIFY_WEB_PLAYER, new=2)
            return True
        raise


def _activate_spotify_window():
    try:
        windows = pyautogui.getWindowsWithTitle("Spotify")
        if not windows:
            return None

        window = windows[0]
        if window.isMinimized:
            window.restore()
        window.activate()
        time.sleep(0.5)
        try:
            window.maximize()
            time.sleep(0.5)
        except Exception:
            pass
        return window
    except Exception:
        return None


def _send_media_key(action):
    key_map = {
        "playpause": "playpause",
        "next": "nexttrack",
        "previous": "prevtrack",
    }
    key = key_map.get(action)
    if not key:
        return False, "That Spotify media command is not supported yet."

    pyautogui.press(key)
    return True, f"Spotify {action} command sent."


def _play_first_search_result():
    window = _activate_spotify_window()
    time.sleep(0.5)

    if window:
        left, top = window.left, window.top
        width, height = window.width, window.height
        play_button_x = left + int(width * 0.77)
        play_button_y = top + int(height * 0.22)
    else:
        screen_width, screen_height = pyautogui.size()
        play_button_x = int(screen_width * 0.77)
        play_button_y = int(screen_height * 0.22)

    pyautogui.moveTo(play_button_x, play_button_y, duration=0.15)
    time.sleep(0.2)
    pyautogui.mouseDown(button="left")
    time.sleep(0.1)
    pyautogui.mouseUp(button="left")
    time.sleep(0.4)
    pyautogui.press("enter")


def normalize_spotify_action(text):
    text = (text or "").strip().lower()
    if text in {"spotify", "open spotify", "launch spotify"}:
        return "open"
    if "next" in text or "skip" in text:
        return "next"
    if "previous" in text or "prev" in text or "back" in text:
        return "previous"
    if "pause" in text or "resume" in text or "continue" in text:
        return "playpause"
    if "play music" in text or text in {"play spotify", "spotify play"}:
        return "playpause"
    if "stop" in text and "spotify" in text:
        return "playpause"
    if "open" in text or "launch" in text:
        return "open"
    if "play" in text or "spotify" in text:
        return "play"
    return ""


def extract_spotify_query(text):
    query = (text or "").strip().lower()
    for word in [
        "spotify",
        "play",
        "music",
        "song",
        "songs",
        "track",
        "playlist",
        "on",
        "please",
    ]:
        query = query.replace(word, " ")
    return " ".join(query.split())


def control_spotify(action, query=""):
    try:
        if action == "open":
            _open_target("spotify:")
            return True, "Opening Spotify."

        if action == "play":
            query = (query or "").strip()
            if not query:
                return _send_media_key("playpause")

            encoded_query = urllib.parse.quote(query)
            _open_target(f"spotify:search:{encoded_query}")
            time.sleep(SPOTIFY_SEARCH_LOAD_SECONDS)
            _play_first_search_result()
            return True, f"Playing {query} on Spotify."

        if action in {"playpause", "next", "previous"}:
            return _send_media_key(action)

        return False, "That Spotify command is not supported yet."
    except Exception as exc:
        return False, f"Spotify automation failed: {exc}"
