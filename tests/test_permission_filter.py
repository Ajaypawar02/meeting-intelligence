"""Permission filter focused tests."""

from app.permissions.access_map import allowed_tags_for_role, is_allowed
from app.schemas.meeting_record import SensitivityTag


def test_access_map_general_excludes_hr_and_finance():
    tags = allowed_tags_for_role("general")
    assert SensitivityTag.GENERAL in tags
    assert SensitivityTag.CONFIDENTIAL_HR not in tags
    assert SensitivityTag.FINANCE not in tags


def test_is_allowed_helpers():
    assert is_allowed("exec", "confidential-hr")
    assert not is_allowed("engineering", SensitivityTag.FINANCE)
    assert is_allowed("pm", SensitivityTag.FINANCE)
