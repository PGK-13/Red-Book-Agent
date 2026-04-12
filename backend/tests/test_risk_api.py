from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from httpx import AsyncClient
from jose import jwt

from app.config import settings
from app.models.account import Account
from app.schemas.risk import RiskScanResponse


def _make_auth_header(merchant_id: str) -> dict[str, str]:
    token = jwt.encode(
        {"sub": merchant_id},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    return {"Authorization": f"Bearer {token}"}


class TestRiskAPI:
    @pytest.mark.asyncio
    async def test_keyword_crud_validation_and_base_response(self, client: AsyncClient) -> None:
        merchant_id = str(uuid4())
        headers = _make_auth_header(merchant_id)

        invalid_resp = await client.post(
            "/api/v1/risk/keywords",
            json={
                "keyword": "   ",
                "category": "custom",
                "match_mode": "exact",
                "severity": "warn",
                "is_active": True,
            },
            headers=headers,
        )
        assert invalid_resp.status_code == 422

        create_resp = await client.post(
            "/api/v1/risk/keywords",
            json={
                "keyword": "promo",
                "category": "custom",
                "replacement": "intro",
                "match_mode": "exact",
                "severity": "warn",
                "is_active": True,
            },
            headers=headers,
        )
        assert create_resp.status_code == 200
        create_body = create_resp.json()
        assert create_body["code"] == 0
        assert create_body["data"]["keyword"] == "promo"
        keyword_id = create_body["data"]["id"]

        list_resp = await client.get("/api/v1/risk/keywords", headers=headers)
        assert list_resp.status_code == 200
        list_body = list_resp.json()
        assert list_body["code"] == 0
        assert isinstance(list_body["data"], list)
        assert len(list_body["data"]) == 1

        update_resp = await client.put(
            f"/api/v1/risk/keywords/{keyword_id}",
            json={"replacement": "guide", "severity": "block"},
            headers=headers,
        )
        assert update_resp.status_code == 200
        update_body = update_resp.json()
        assert update_body["code"] == 0
        assert update_body["data"]["replacement"] == "guide"
        assert update_body["data"]["severity"] == "block"

        delete_resp = await client.delete(f"/api/v1/risk/keywords/{keyword_id}", headers=headers)
        assert delete_resp.status_code == 200
        delete_body = delete_resp.json()
        assert delete_body["code"] == 0
        assert "message" in delete_body

    @pytest.mark.asyncio
    async def test_scan_rejects_invalid_scene(self, client: AsyncClient) -> None:
        merchant_id = str(uuid4())
        headers = _make_auth_header(merchant_id)

        resp = await client.post(
            "/api/v1/risk/scan",
            json={
                "account_id": str(uuid4()),
                "scene": "unknown_scene",
                "content": "hello",
            },
            headers=headers,
        )

        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_scan_returns_base_response_for_outbound_scene(self, client: AsyncClient) -> None:
        merchant_id = str(uuid4())
        headers = _make_auth_header(merchant_id)
        account_id = str(uuid4())

        expected = RiskScanResponse(
            passed=False,
            decision="rewrite_required",
            hits=[],
            retryable=True,
        )
        with patch(
            "app.api.v1.risk.risk_service.scan_output",
            new=AsyncMock(return_value=expected),
        ) as mocked_scan:
            resp = await client.post(
                "/api/v1/risk/scan",
                json={
                    "account_id": account_id,
                    "scene": "comment_reply",
                    "content": "promo copy",
                },
                headers=headers,
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0
        assert body["data"]["decision"] == "rewrite_required"
        mocked_scan.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_events_endpoint_returns_base_response(self, client: AsyncClient, db) -> None:
        merchant_id = str(uuid4())
        headers = _make_auth_header(merchant_id)
        account = Account(
            id=str(uuid4()),
            merchant_id=merchant_id,
            xhs_user_id=f"xhs_{uuid4().hex[:8]}",
            nickname="riskapi-events",
            access_type="browser",
            status="active",
        )
        db.add(account)
        await db.flush()

        with patch(
            "app.api.v1.risk.risk_service.list_account_events",
            new=AsyncMock(
                return_value=[
                    {
                        "id": str(uuid4()),
                        "merchant_id": merchant_id,
                        "account_id": account.id,
                        "module": "E",
                        "operation_type": "comment_reply",
                        "status": "failed",
                        "risk_decision": "blocked",
                        "violations": ["promo"],
                        "detail_schema": "module_e_risk_event.v1",
                        "context": {"reason": "sensitive_keywords"},
                        "created_at": datetime.now(timezone.utc),
                    }
                ]
            ),
        ):
            resp = await client.get(
                f"/api/v1/risk/accounts/{account.id}/events",
                headers=headers,
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0
        assert isinstance(body["data"], list)
        assert body["data"][0]["risk_decision"] == "blocked"
        assert body["data"][0]["module"] == "E"
