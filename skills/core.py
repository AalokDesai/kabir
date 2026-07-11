from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class SkillResult:
    success: bool = True
    message: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    notification: dict[str, Any] | None = None


@dataclass
class SkillContext:
    speak: Callable[[str], None]
    set_status: Callable[[str], None]
    open_url: Callable[[str], None]
    press_key: Callable[[str], None]
    hotkey: Callable[..., None]
    switch_window: Callable[[], None]
    get_weather: Callable[[str], None]
    spotify_flow: Callable[[str], None]
    play_media_flow: Callable[[str], None]
    extract_maps_location: Callable[[str], str]
    settings: Callable[[], dict[str, Any]]
    is_agent_command: Callable[[str], bool]
    run_autonomous_agent: Callable[[str], None]
    is_memory_query: Callable[[str], bool]
    answer_memory_query: Callable[[str], None]
    is_file_search_command: Callable[[str], bool]
    handle_file_search_command: Callable[[str], None]
    send_email_flow: Callable[[str], None]
    send_message_flow: Callable[[str], None]
    setup_wireless_phone_flow: Callable[[], None]
    pair_wireless_phone_flow: Callable[[], None]
    connect_wireless_phone_flow: Callable[[str], None]
    answer_phone_call_flow: Callable[[], None]
    end_phone_call_flow: Callable[[], None]
    make_phone_call_flow: Callable[[str], None]


class BaseSkill:
    name = "base"
    description = ""
    examples: list[str] = []

    def matches(self, command: str) -> bool:
        raise NotImplementedError

    def execute(self, command: str, context: SkillContext) -> SkillResult:
        raise NotImplementedError
