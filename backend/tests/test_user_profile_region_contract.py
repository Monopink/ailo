"""Region update contract tests for user profile API helpers."""

import pytest
from pydantic import ValidationError

from app.api.v1.users import _validate_profile_update_payload_or_raise
from app.schemas.user_profile import UserProfileUpdateRequest
from app.services.profile.region import build_cn_region_snapshot


def test_build_cn_region_snapshot_for_municipality() -> None:
    """Municipalities should collapse duplicated province/city names."""
    assert build_cn_region_snapshot("上海市", "上海市") == "上海"


def test_build_cn_region_snapshot_strips_autonomous_suffixes() -> None:
    """CN region snapshot should strip province and city administrative suffixes."""
    assert build_cn_region_snapshot("内蒙古自治区", "呼伦贝尔市") == "内蒙古 呼伦贝尔"


def test_validate_profile_update_payload_rejects_client_region_snapshot() -> None:
    """Client must not submit server-generated region snapshot."""
    with pytest.raises(ValidationError):
        UserProfileUpdateRequest(
            region="上海",
            region_country_code="CN",
            region_cn_city_code="310100",
            region_province_name="上海市",
            region_city_name="上海市",
        )


def test_validate_profile_update_payload_accepts_cn_region_group() -> None:
    """CN region fields should pass when submitted as a complete group."""
    body = UserProfileUpdateRequest(
        region_country_code="CN",
        region_cn_city_code="310100",
        region_province_name="上海市",
        region_city_name="上海市",
    )

    _validate_profile_update_payload_or_raise(body)


def test_validate_profile_update_payload_accepts_region_clear_group() -> None:
    """Clearing region requires the full null field group."""
    body = UserProfileUpdateRequest(
        region_country_code=None,
        region_cn_city_code=None,
        region_province_name=None,
        region_city_name=None,
    )

    _validate_profile_update_payload_or_raise(body)
