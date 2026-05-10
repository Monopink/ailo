"""Tests for invitation bindability policy and public intake safety guard."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1 import public_invitations as public_invitations_module
from app.services.invitation import bindability
from app.utils.client_ip import ClientIPResolutionError


@pytest.mark.asyncio
async def test_bindability_returns_false_when_invitee_already_bound(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Bindability should reject when invitee already has a binding."""

    async def _mock_get_by_invitee_user_id(
        _db: AsyncSession,
        *,
        invitee_user_id: int,
    ) -> object:
        assert invitee_user_id == 1001
        return object()

    monkeypatch.setattr(
        bindability.invite_binding_crud,
        "get_by_invitee_user_id",
        _mock_get_by_invitee_user_id,
    )

    result = await bindability.is_invite_code_bindable(
        db_session,
        invitee_user_id=1001,
        inviter_user_id=2001,
    )
    assert result is False


@pytest.mark.asyncio
async def test_bindability_returns_false_for_self_bind(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Bindability should reject self bind."""

    async def _mock_get_by_invitee_user_id(
        _db: AsyncSession,
        *,
        invitee_user_id: int,
    ) -> None:
        assert invitee_user_id == 1001

    monkeypatch.setattr(
        bindability.invite_binding_crud,
        "get_by_invitee_user_id",
        _mock_get_by_invitee_user_id,
    )

    result = await bindability.is_invite_code_bindable(
        db_session,
        invitee_user_id=1001,
        inviter_user_id=1001,
    )
    assert result is False


@pytest.mark.asyncio
async def test_bindability_returns_true_for_valid_relation(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Bindability should pass when no reverse invite relation exists."""

    async def _mock_get_by_invitee_user_id(
        _db: AsyncSession,
        *,
        invitee_user_id: int,
    ) -> None:
        assert invitee_user_id == 1001

    async def _mock_is_inviter_of(
        _db: AsyncSession,
        *,
        inviter_user_id: int,
        invitee_user_id: int,
    ) -> bool:
        assert inviter_user_id == 1001
        assert invitee_user_id == 2001
        return False

    monkeypatch.setattr(
        bindability.invite_binding_crud,
        "get_by_invitee_user_id",
        _mock_get_by_invitee_user_id,
    )
    monkeypatch.setattr(bindability.invite_binding_crud, "is_inviter_of", _mock_is_inviter_of)

    result = await bindability.is_invite_code_bindable(
        db_session,
        invitee_user_id=1001,
        inviter_user_id=2001,
    )
    assert result is True


@pytest.mark.asyncio
async def test_public_intake_denies_when_client_ip_unresolvable(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Public intake should fail-closed when client IP cannot be resolved."""

    def _raise_client_ip_resolution_error(_request: object) -> str:
        raise ClientIPResolutionError("missing_client_ip_header", "missing header")

    monkeypatch.setattr(
        public_invitations_module, "get_client_ip", _raise_client_ip_resolution_error
    )

    response = await client.post(
        "/api/v1/public/invitations/intake",
        json={
            "source": "link",
            "trigger": "manual_input",
            "raw_text": "ABCD12",
        },
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload.get("message") == "请求来源受限"
    assert payload.get("reason") == "CLIENT_IP_RESOLUTION_FAILED"
