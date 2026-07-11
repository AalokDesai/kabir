"""YouTube music handler for Phoenix."""

import pywhatkit


def play_music(song: str, platform: str = "youtube") -> str:
    pywhatkit.playonyt(song)
    return f"Playing {song} on YouTube."
