from .core import BaseSkill, SkillContext, SkillResult


class EmailSkill(BaseSkill):
    name = "email"
    description = "Starts the email composition flow."
    examples = ["send email", "compose email to Aalok", "send mail"]

    def matches(self, command: str) -> bool:
        return "send email" in command or "send mail" in command or "compose email" in command

    def execute(self, command: str, context: SkillContext) -> SkillResult:
        context.send_email_flow(command)
        return SkillResult(message="email")


class MessagingSkill(BaseSkill):
    name = "messaging"
    description = "Sends WhatsApp, Slack, or generic platform messages."
    examples = ["send message", "send whatsapp", "send slack message"]

    def matches(self, command: str) -> bool:
        return (
            "send message" in command
            or "send a message" in command
            or "send whatsapp" in command
            or "whatsapp" in command
            or "slack" in command
        )

    def execute(self, command: str, context: SkillContext) -> SkillResult:
        context.send_message_flow(command)
        return SkillResult(message="messaging")


class PhoneSkill(BaseSkill):
    name = "phone"
    description = "Controls Android calling and wireless ADB setup flows."
    examples = ["call Aalok", "setup wireless phone", "pick up call", "disconnect call"]

    def matches(self, command: str) -> bool:
        phrases = (
            "wireless phone setup",
            "setup wireless phone",
            "setup wireless adb",
            "enable wireless adb",
            "pair wireless phone",
            "pair wireless adb",
            "wireless debugging pair",
            "connect wireless phone",
            "connect phone wirelessly",
            "connect wireless adb",
            "pick up call",
            "pickup call",
            "answer call",
            "receive call",
            "disconnect call",
            "end call",
            "hang up",
            "cut call",
            "call",
        )
        return any(phrase in command for phrase in phrases)

    def execute(self, command: str, context: SkillContext) -> SkillResult:
        if any(phrase in command for phrase in ("wireless phone setup", "setup wireless phone", "setup wireless adb", "enable wireless adb")):
            context.setup_wireless_phone_flow()
        elif any(phrase in command for phrase in ("pair wireless phone", "pair wireless adb", "wireless debugging pair")):
            context.pair_wireless_phone_flow()
        elif any(phrase in command for phrase in ("connect wireless phone", "connect phone wirelessly", "connect wireless adb")):
            context.connect_wireless_phone_flow(command)
        elif any(phrase in command for phrase in ("pick up call", "pickup call", "answer call", "receive call")):
            context.answer_phone_call_flow()
        elif any(phrase in command for phrase in ("disconnect call", "end call", "hang up", "cut call")):
            context.end_phone_call_flow()
        else:
            context.make_phone_call_flow(command)
        return SkillResult(message="phone")


class FunctionPredicateSkill(BaseSkill):
    def __init__(self, name, description, examples, predicate_name, handler_name):
        self.name = name
        self.description = description
        self.examples = examples
        self.predicate_name = predicate_name
        self.handler_name = handler_name

    def matches(self, command: str) -> bool:
        return False

    def matches_with_context(self, command: str, context: SkillContext) -> bool:
        return getattr(context, self.predicate_name)(command)

    def execute(self, command: str, context: SkillContext) -> SkillResult:
        getattr(context, self.handler_name)(command)
        return SkillResult(message=self.name)


AGENT_SKILL = FunctionPredicateSkill(
    "agent",
    "Runs autonomous multi-step assistant tasks.",
    ["agent research this topic", "kabir plan my task"],
    "is_agent_command",
    "run_autonomous_agent",
)

MEMORY_SKILL = FunctionPredicateSkill(
    "memory",
    "Answers questions from command and conversation memory.",
    ["what did I ask yesterday", "search history for email"],
    "is_memory_query",
    "answer_memory_query",
)

FILE_SEARCH_SKILL = FunctionPredicateSkill(
    "file_search",
    "Searches local files and sends results to the Files panel.",
    ["find file report", "open file invoice"],
    "is_file_search_command",
    "handle_file_search_command",
)
