import datetime
import re
from urllib.parse import quote_plus

from .core import BaseSkill, SkillContext, SkillResult


class TimeDateSkill(BaseSkill):
    name = "time_date"
    description = "Answers current time and date questions."
    examples = ["what is the time", "what is the date", "today's date"]

    def matches(self, command: str) -> bool:
        return "time" in command or "date" in command

    def execute(self, command: str, context: SkillContext) -> SkillResult:
        if "time" in command:
            context.speak(f"The time is {datetime.datetime.now().strftime('%I:%M %p')}.")
            return SkillResult(message="time")
        context.speak(f"Today is {datetime.datetime.now().strftime('%A, %B %d, %Y')}.")
        return SkillResult(message="date")


class WeatherSkill(BaseSkill):
    name = "weather"
    description = "Fetches weather using the configured default city or a city from the command."
    examples = ["weather", "weather in Mumbai", "temperature in Delhi"]

    def matches(self, command: str) -> bool:
        return "weather" in command or "temperature" in command or "forecast" in command

    def execute(self, command: str, context: SkillContext) -> SkillResult:
        city = re.sub(r"\b(weather|temperature|forecast|today|now|please)\b", " ", command, flags=re.IGNORECASE)
        city = re.sub(r"^\s*(in|for|of)\s+", "", city.strip(), flags=re.IGNORECASE)
        city = re.sub(r"\s+", " ", city).strip(" .,:;?")
        if not city:
            city = context.settings().get("default_city", "Mumbai")
        context.get_weather(city)
        return SkillResult(message=f"weather:{city}")


class WebsiteSkill(BaseSkill):
    name = "websites"
    description = "Opens common websites and web searches."
    examples = [
        "open youtube",
        "search lo-fi music on youtube",
        "open google",
        "google python sqlite",
        "where is Ahmedabad",
        "open github",
    ]

    def matches(self, command: str) -> bool:
        if "search" in command and ("youtube" in command or "you tube" in command):
            return True
        if "open youtube" in command or command.strip() in {"youtube", "you tube"}:
            return True
        if "where is" in command or "locate" in command or ("search" in command and "maps" in command) or "maps" in command:
            return True
        if "open google" in command or "google" in command:
            return True
        return any(phrase in command for phrase in ("stack overflow", "github", "open gmail", "amazon", "flipkart"))

    def execute(self, command: str, context: SkillContext) -> SkillResult:
        if "search" in command and ("youtube" in command or "you tube" in command):
            query = self._youtube_query(command)
            context.open_url(f"https://www.youtube.com/results?search_query={quote_plus(query)}")
            context.speak(f"Searching YouTube for {query}.")
            return SkillResult(message="youtube_search")

        if "open youtube" in command or command.strip() in {"youtube", "you tube"}:
            context.open_url("https://www.youtube.com")
            context.speak("Opening YouTube.")
            return SkillResult(message="youtube")

        if "where is" in command or "locate" in command or ("search" in command and "maps" in command):
            location = context.extract_maps_location(command)
            if location:
                context.open_url(f"https://www.google.com/maps/search/{quote_plus(location)}")
                context.speak(f"Locating {location} on Google Maps.")
            else:
                context.open_url("https://www.google.co.in/maps/")
                context.speak("Opening Maps.")
            return SkillResult(message="maps")

        if "maps" in command:
            context.open_url("https://www.google.co.in/maps/")
            context.speak("Opening Maps.")
            return SkillResult(message="maps")

        if "open google" in command:
            context.open_url("https://www.google.com")
            context.speak("Opening Google.")
            return SkillResult(message="google")

        if "google" in command:
            query = command.replace("google", "").replace("search", "").strip()
            if query:
                context.open_url(f"https://www.google.com/search?q={quote_plus(query)}")
                context.speak(f"Searching for {query}.")
                return SkillResult(message="google_search")

        simple_sites = {
            "stack overflow": ("https://stackoverflow.com", "Opening Stack Overflow."),
            "github": ("https://github.com", "Opening GitHub."),
            "open gmail": ("https://mail.google.com", "Opening Gmail."),
            "amazon": ("https://www.amazon.in/", "Opening Amazon."),
            "flipkart": ("https://www.flipkart.com/", "Opening Flipkart."),
        }
        for phrase, (url, spoken) in simple_sites.items():
            if phrase in command:
                context.open_url(url)
                context.speak(spoken)
                return SkillResult(message=phrase.replace(" ", "_"))

        return SkillResult(success=False, message="No website action matched.")

    def _youtube_query(self, command: str) -> str:
        match = re.search(r"\bsearch\s+(?:for\s+)?(.+?)\s+(?:on\s+)?(?:youtube|you tube)\b", command)
        if match:
            return match.group(1).strip()
        query = re.sub(r"\b(search|for|on|youtube|you tube)\b", " ", command, flags=re.IGNORECASE)
        return re.sub(r"\s+", " ", query).strip(" .,:;?") or "YouTube"


class MediaSkill(BaseSkill):
    name = "media"
    description = "Routes Spotify and YouTube playback commands."
    examples = ["play music", "play Believer on Spotify", "next song", "pause music"]

    def matches(self, command: str) -> bool:
        return (
            "spotify" in command
            or "next song" in command
            or "previous song" in command
            or "pause music" in command
            or "resume music" in command
            or "play" in command
        )

    def execute(self, command: str, context: SkillContext) -> SkillResult:
        if (
            "spotify" in command
            or "next song" in command
            or "previous song" in command
            or "pause music" in command
            or "resume music" in command
        ):
            context.spotify_flow(command)
            return SkillResult(message="spotify")
        context.play_media_flow(command)
        return SkillResult(message="play_media")


class SystemControlSkill(BaseSkill):
    name = "system_controls"
    description = "Handles volume and simple window controls."
    examples = ["volume up", "volume down", "mute", "minimize", "switch window"]

    def matches(self, command: str) -> bool:
        return any(
            phrase in command
            for phrase in ("volume up", "volume down", "mute", "minimise", "minimize", "switch window")
        )

    def execute(self, command: str, context: SkillContext) -> SkillResult:
        if "volume up" in command:
            context.press_key("volumeup")
            context.speak("Volume increased.")
            return SkillResult(message="volume_up")
        if "volume down" in command:
            context.press_key("volumedown")
            context.speak("Volume decreased.")
            return SkillResult(message="volume_down")
        if "mute" in command:
            context.press_key("volumemute")
            context.speak("Muted.")
            return SkillResult(message="mute")
        if "minimise" in command or "minimize" in command:
            context.hotkey("win", "d")
            context.speak("Windows minimised.")
            return SkillResult(message="minimize")
        if "switch window" in command:
            context.switch_window()
            context.speak("Switching window.")
            return SkillResult(message="switch_window")
        return SkillResult(success=False, message="No system action matched.")
