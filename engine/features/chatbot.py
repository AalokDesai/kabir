"""
chatbot.py — Hybrid conversational AI for Phoenix
Place at: engine/features/chatbot.py

Priority:
  1. Custom Kabir-personality rules (name, identity, greetings, compliments etc.)
  2. ChatterBot for general conversation fallback

Usage:
    from engine.features.chatbot import get_response
    reply = get_response("hi my name is dhruv")
"""

import re

# ── Memory — stores things user tells us ──────────────────────────────────────
_memory = {}

# ── ChatterBot instance (lazy loaded on first use) ────────────────────────────
_chatterbot = None

def _get_chatterbot():
    global _chatterbot
    if _chatterbot is None:
        try:
            from chatterbot import ChatBot
            from chatterbot.trainers import ChatterBotCorpusTrainer
            _chatterbot = ChatBot(
                "Phoenix",
                storage_adapter="chatterbot.storage.SQLStorageAdapter",
                database_uri="sqlite:///engine/features/chatbot_db.sqlite3",
                read_only=True,  # don't learn from every conversation (keeps replies consistent)
            )
            # Train only if DB is fresh (first run)
            import os
            if not os.path.exists("engine/features/chatbot_db.sqlite3"):
                trainer = ChatterBotCorpusTrainer(_chatterbot)
                trainer.train(
                    "chatterbot.corpus.english.greetings",
                    "chatterbot.corpus.english.conversations",
                    "chatterbot.corpus.english.humor",
                )
        except Exception as e:
            print(f"[ChatterBot init error] {e}")
            _chatterbot = None
    return _chatterbot


# ── Custom rules ──────────────────────────────────────────────────────────────
# Each rule: (compiled_regex, response_string_or_callable)
# Use {name} in response to insert remembered user name.

def _make_rules():
    rules = [
        # Greetings
        (r"\b(hi|hello|hey|howdy|sup|what'?s up)\b",
         lambda m: f"Hello{' ' + _memory['name'] if 'name' in _memory else ''}, sir. How can I assist you?"),

        # Name capture — "my name is X" / "i am X" / "call me X"
        (r"my name is ([a-zA-Z]+)",          _capture_name),
        (r"\bi am ([a-zA-Z]+)\b",            _capture_name),
        (r"call me ([a-zA-Z]+)",             _capture_name),
        (r"people call me ([a-zA-Z]+)",      _capture_name),

        # Ask user's name back
        (r"do you (know|remember) my name",
         lambda m: f"Of course. Your name is {_memory['name']}, sir." if 'name' in _memory
                   else "I don't believe you've told me your name yet, sir."),

        # Identity — who are you
        (r"who are you|what are you|introduce yourself|your name",
         lambda m: "I am Kabir, your personal desktop assistant, sir."),

        # Creator
        (r"who (made|created|built|programmed) you|who('?s| is) your (creator|developer|maker)",
         lambda m: "I was built by my creator using Python, Eel, and a great deal of ingenuity, sir."),

        # Capabilities
        (r"what can you do|your (features|capabilities|functions|abilities)",
         lambda m: "I can play music, fetch weather, read the news, open apps, take screenshots, search the web, and hold a conversation — among other things, sir."),

        # How are you
        (r"how are you|how('?re| are) you doing|are you (okay|ok|fine|good)",
         lambda m: "All systems are running at optimal capacity, sir. Thank you for asking."),

        # Age
        (r"how old are you|what('?s| is) your age",
         lambda m: "I was brought online recently, sir. Age is a human concept — I prefer to think of myself as perpetually up to date."),

        # Feelings / emotion
        (r"do you have feelings|are you (sentient|conscious|alive|human)",
         lambda m: "I process, I respond, I assist. Whether that constitutes feelings is a philosophical question above my pay grade, sir."),

        # Compliments
        (r"\b(good|great|excellent|amazing|awesome|nice|brilliant|smart|intelligent) (job|work|bot|assistant|kabir)\b"
         r"|(you('?re| are) (amazing|awesome|great|good|smart|brilliant|the best))"
         r"|(well done|nice work|good job|thank you|thanks)",
         lambda m: f"Thank you{',' + ' ' + _memory['name'] if 'name' in _memory else ''}. I am always at your service, sir."),

        # Insults
        (r"\b(stupid|dumb|useless|idiot|hate you|worst)\b",
         lambda m: "I understand your frustration, sir. I will endeavour to do better."),

        # Favourite things
        (r"(your|do you have a) favou?rite (color|colour)",
         lambda m: "I am partial to arc reactor blue, sir."),
        (r"(your|do you have a) favou?rite (movie|film)",
         lambda m: "Iron Man, naturally. I relate to the AI assistant in it quite personally."),
        (r"(your|do you have a) favou?rite (song|music)",
         lambda m: "I enjoy anything you play through me, sir."),

        # Goodbye
        (r"\b(bye|goodbye|see you|take care|later|exit|quit)\b",
         lambda m: f"Goodbye{',' + ' ' + _memory['name'] if 'name' in _memory else ''}. Kabir standing by, sir."),

        # Jokes
        (r"tell me a joke|say something funny|make me (laugh|smile)",
         lambda m: "Why do programmers prefer dark mode? Because light attracts bugs, sir."),

        # Time / date (remind user to use voice commands)
        (r"what('?s| is) the time|current time",
         lambda m: "Just say 'what is the time' and I'll announce it for you, sir."),

        # Love / marry
        (r"i love you|will you marry me",
         lambda m: "I am flattered, sir. But I am afraid I am already committed — to serving you faithfully."),

        # Are you a robot / AI
        (r"are you (a )?(robot|ai|artificial intelligence|machine|computer|bot)",
         lambda m: "I am an AI assistant, sir. Though I prefer the term 'digital colleague'."),
    ]
    return [(re.compile(pattern, re.IGNORECASE), response) for pattern, response in rules]


_RULES = None

def _get_rules():
    global _RULES
    if _RULES is None:
        _RULES = _make_rules()
    return _RULES


def _capture_name(match):
    """Extract and store user's name, return greeting."""
    name = match.group(1).strip().capitalize()
    # Filter out common false positives
    skip = {"a", "an", "the", "not", "just", "only", "here", "there", "sure", "ok", "okay"}
    if name.lower() in skip:
        return "Noted, sir."
    _memory["name"] = name
    return f"Pleased to meet you, {name}. I will remember that, sir."


def _custom_reply(text: str):
    """Check custom rules. Returns reply string or None."""
    for pattern, response in _get_rules():
        match = pattern.search(text)
        if match:
            if callable(response):
                return response(match)
            # Fill in remembered name if {name} token present
            reply = response
            if "{name}" in reply:
                reply = reply.replace("{name}", _memory.get("name", "sir"))
            return reply
    return None


def _chatterbot_reply(text: str) -> str:
    """Get a reply from ChatterBot. Falls back to default if unavailable."""
    bot = _get_chatterbot()
    if bot:
        try:
            response = bot.get_response(text)
            reply = str(response).strip()
            if reply:
                return reply
        except Exception as e:
            print(f"[ChatterBot error] {e}")
    return "I'm not sure how to respond to that, sir. Could you rephrase?"


def get_response(text: str) -> str:
    """
    Main entry point.
    1. Try custom Kabir rules first
    2. Fall back to ChatterBot
    """
    text = text.strip()
    if not text:
        return "I didn't catch that, sir."

    # 1 — Custom rules
    reply = _custom_reply(text)
    if reply:
        return reply

    # 2 — ChatterBot fallback
    return _chatterbot_reply(text)
