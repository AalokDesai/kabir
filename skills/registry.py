from .core import SkillContext, SkillResult
from .advanced import (
    AGENT_SKILL,
    FILE_SEARCH_SKILL,
    MEMORY_SKILL,
    EmailSkill,
    MessagingSkill,
    PhoneSkill,
)
from .desktop import (
    MediaSkill,
    SystemControlSkill,
    TimeDateSkill,
    WeatherSkill,
    WebsiteSkill,
)


REGISTERED_SKILLS = [
    AGENT_SKILL,
    MEMORY_SKILL,
    FILE_SEARCH_SKILL,
    EmailSkill(),
    MessagingSkill(),
    PhoneSkill(),
    TimeDateSkill(),
    WeatherSkill(),
    WebsiteSkill(),
    MediaSkill(),
    SystemControlSkill(),
]


def get_registered_skills():
    return REGISTERED_SKILLS


def get_skill_examples():
    examples = []
    for skill in REGISTERED_SKILLS:
        examples.extend(skill.examples)
    return examples


def dispatch_skill(command: str, context: SkillContext) -> SkillResult | None:
    command = (command or "").strip().lower()
    if not command:
        return None
    for skill in REGISTERED_SKILLS:
        if hasattr(skill, "matches_with_context"):
            matched = skill.matches_with_context(command, context)
        else:
            matched = skill.matches(command)
        if matched:
            return skill.execute(command, context)
    return None
