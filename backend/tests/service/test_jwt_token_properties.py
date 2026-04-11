"""属性测试 — _create_jwt_token() 正确性属性。

Property 4: JWT 签发往返一致性 (需求 3.1)
    签发的 JWT 解码后 sub、nickname、avatar 与输入一致。

Property 5: JWT 过期时间正确性 (需求 3.3)
    JWT exp 字段等于签发时间 + JWT_EXPIRE_MINUTES。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from hypothesis import given, settings, strategies as st
from jose import jwt

from app.config import settings as app_settings
from app.services.account_service import _create_jwt_token


# ── 辅助 strategies ──

nonempty_str = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P", "S")),
    min_size=1,
    max_size=200,
)

avatar_st = st.one_of(st.none(), nonempty_str)


# ── Property 4: JWT 签发往返一致性 ──


class TestJwtRoundtripConsistency:
    """验证签发的 JWT 解码后 sub、nickname、avatar 与输入一致（需求 3.1）。"""

    @given(xhs_user_id=nonempty_str, nickname=nonempty_str, avatar=avatar_st)
    @settings(max_examples=200)
    def test_jwt_decode_matches_input(
        self,
        xhs_user_id: str,
        nickname: str,
        avatar: str | None,
    ) -> None:
        """JWT 解码后的 sub、nickname、avatar 应与签发时的输入完全一致。"""
        token = _create_jwt_token(xhs_user_id, nickname, avatar)
        payload = jwt.decode(
            token,
            app_settings.jwt_secret_key,
            algorithms=[app_settings.jwt_algorithm],
        )
        assert payload["sub"] == xhs_user_id, (
            f"sub 不一致: {payload['sub']!r} != {xhs_user_id!r}"
        )
        assert payload["nickname"] == nickname, (
            f"nickname 不一致: {payload['nickname']!r} != {nickname!r}"
        )
        assert payload["avatar"] == avatar, (
            f"avatar 不一致: {payload['avatar']!r} != {avatar!r}"
        )


# ── Property 5: JWT 过期时间正确性 ──


class TestJwtExpirationCorrectness:
    """验证 JWT exp 字段等于签发时间 + JWT_EXPIRE_MINUTES（需求 3.3）。"""

    @given(xhs_user_id=nonempty_str, nickname=nonempty_str, avatar=avatar_st)
    @settings(max_examples=200)
    def test_jwt_exp_equals_now_plus_expire_minutes(
        self,
        xhs_user_id: str,
        nickname: str,
        avatar: str | None,
    ) -> None:
        """JWT exp 应在 [now + expire_minutes - 1s, now + expire_minutes + 1s] 范围内。

        JWT exp 是整数时间戳（秒精度），因此需要容忍 ±1 秒的误差。
        """
        before = datetime.now(timezone.utc)
        token = _create_jwt_token(xhs_user_id, nickname, avatar)
        after = datetime.now(timezone.utc)

        payload = jwt.decode(
            token,
            app_settings.jwt_secret_key,
            algorithms=[app_settings.jwt_algorithm],
        )
        exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)

        # JWT exp 为整数秒，截断微秒后可能比 before 早最多 1 秒
        expected_min = (
            before.replace(microsecond=0)
            + timedelta(minutes=app_settings.jwt_expire_minutes)
            - timedelta(seconds=1)
        )
        expected_max = (
            after + timedelta(minutes=app_settings.jwt_expire_minutes)
            + timedelta(seconds=1)
        )

        assert expected_min <= exp <= expected_max, (
            f"exp {exp.isoformat()} 不在预期范围 "
            f"[{expected_min.isoformat()}, {expected_max.isoformat()}]"
        )
