"""Role → allowed sensitivity tags. Restricted content is filtered pre-LLM."""

from __future__ import annotations

from app.schemas.meeting_record import SensitivityTag

# What each audience role is allowed to see.
ACCESS_MAP: dict[str, set[SensitivityTag]] = {
    "general": {SensitivityTag.GENERAL},
    "engineering": {SensitivityTag.GENERAL},
    "pm": {SensitivityTag.GENERAL, SensitivityTag.FINANCE},
    "finance": {SensitivityTag.GENERAL, SensitivityTag.FINANCE},
    "hr": {SensitivityTag.GENERAL, SensitivityTag.CONFIDENTIAL_HR},
    "exec": {
        SensitivityTag.GENERAL,
        SensitivityTag.FINANCE,
        SensitivityTag.CONFIDENTIAL_HR,
    },
}


def allowed_tags_for_role(role: str) -> set[SensitivityTag]:
    return ACCESS_MAP.get(role.lower(), ACCESS_MAP["general"])


def is_allowed(role: str, tag: SensitivityTag | str) -> bool:
    if isinstance(tag, str):
        tag = SensitivityTag(tag)
    return tag in allowed_tags_for_role(role)
