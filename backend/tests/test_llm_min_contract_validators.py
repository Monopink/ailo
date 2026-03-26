import sys
import types

if "chinese_calendar" not in sys.modules:
    chinese_calendar_stub = types.ModuleType("chinese_calendar")
    chinese_calendar_stub.get_holiday_detail = lambda _target_date: (False, None)
    sys.modules["chinese_calendar"] = chinese_calendar_stub

if "lunar_python" not in sys.modules:
    lunar_python_stub = types.ModuleType("lunar_python")

    class _SolarStub:
        @staticmethod
        def fromYmdHms(*_args, **_kwargs):  # noqa: N802
            raise RuntimeError("not used in this test")

        @staticmethod
        def fromYmd(*_args, **_kwargs):  # noqa: N802
            raise RuntimeError("not used in this test")

    lunar_python_stub.Solar = _SolarStub
    sys.modules["lunar_python"] = lunar_python_stub

from app.services.ai.utils.min_contract import prune_l1_fields, validate_l0_contract


def test_l0_requires_booleans() -> None:
    result = validate_l0_contract({"should_reply": True, "should_block": False})
    assert not result.ok


def test_l0_rejects_non_array_messages() -> None:
    result = validate_l0_contract(
        {
            "attack_detected": False,
            "should_block": False,
            "should_reply": True,
            "outgoing_messages": "hi",
            "followup_messages": [],
        }
    )
    assert not result.ok


def test_l0_rejects_empty_string_message() -> None:
    result = validate_l0_contract(
        {
            "attack_detected": False,
            "should_block": False,
            "should_reply": True,
            "outgoing_messages": ["   "],
            "followup_messages": [],
        }
    )
    assert not result.ok


def test_l0_requires_non_empty_messages_when_should_reply_true() -> None:
    result = validate_l0_contract(
        {
            "attack_detected": False,
            "should_block": False,
            "should_reply": True,
            "outgoing_messages": [],
            "followup_messages": [],
        }
    )
    assert not result.ok


def test_l0_allows_missing_messages_when_should_reply_false() -> None:
    result = validate_l0_contract(
        {
            "attack_detected": False,
            "should_block": False,
            "should_reply": False,
        }
    )
    assert result.ok
    assert result.outgoing_messages == []
    assert result.followup_messages == []


def test_l0_ignores_valid_messages_when_should_reply_false() -> None:
    result = validate_l0_contract(
        {
            "attack_detected": False,
            "should_block": False,
            "should_reply": False,
            "outgoing_messages": ["hi"],
            "followup_messages": ["later"],
        }
    )
    assert result.ok
    assert result.reply_messages_ignored is True
    assert result.outgoing_messages == []
    assert result.followup_messages == []


def test_l1_prunes_invalid_score_and_memory() -> None:
    style_dimension_names = ["d1", "d2"]
    personality_schema = {
        "properties": {
            "score": {
                "properties": {
                    "d1": {"minimum": 0, "maximum": 10},
                    "d2": {"minimum": 0, "maximum": 10},
                }
            }
        }
    }

    result = prune_l1_fields(
        ai_response={
            "score": {"d1": 99, "d2": 1},
            "should_update_memory": "yes",
            "memory_operations": [],
        },
        style_dimension_names=style_dimension_names,
        personality_schema=personality_schema,
    )
    assert "score" not in result.pruned_response
    assert "should_update_memory" not in result.pruned_response
    assert "memory_operations" not in result.pruned_response
    assert result.score_kept is False
    assert result.memory_kept is False


def test_l1_keeps_valid_score() -> None:
    style_dimension_names = ["d1", "d2"]
    personality_schema = {
        "properties": {
            "score": {
                "properties": {
                    "d1": {"minimum": 0, "maximum": 10},
                    "d2": {"minimum": 0, "maximum": 10},
                }
            }
        }
    }

    result = prune_l1_fields(
        ai_response={"score": {"d1": 0, "d2": 10}},
        style_dimension_names=style_dimension_names,
        personality_schema=personality_schema,
    )
    assert result.score_kept is True
    assert result.pruned_response.get("score") == {"d1": 0, "d2": 10}


def test_l1_keeps_memory_when_actionable() -> None:
    style_dimension_names = ["d1"]
    personality_schema = {
        "properties": {"score": {"properties": {"d1": {"minimum": 0, "maximum": 1}}}}
    }

    result = prune_l1_fields(
        ai_response={
            "should_update_memory": True,
            "memory_operations": {
                "add": [
                    {
                        "memory_type": "core",
                        "content": "Remember user prefers hot americano",
                        "importance": 2,
                    }
                ]
            },
        },
        style_dimension_names=style_dimension_names,
        personality_schema=personality_schema,
    )
    assert result.memory_kept is True


def test_l1_marks_memory_not_kept_when_no_actionable_operations() -> None:
    style_dimension_names = ["d1"]
    personality_schema = {
        "properties": {"score": {"properties": {"d1": {"minimum": 0, "maximum": 1}}}}
    }

    result = prune_l1_fields(
        ai_response={"should_update_memory": True, "memory_operations": {"add": []}},
        style_dimension_names=style_dimension_names,
        personality_schema=personality_schema,
    )
    assert result.memory_kept is False
    assert result.pruned_response.get("should_update_memory") is True
    assert result.pruned_response.get("memory_operations") == {
        "remove": [],
        "update": [],
        "refresh": [],
        "add": [],
    }
