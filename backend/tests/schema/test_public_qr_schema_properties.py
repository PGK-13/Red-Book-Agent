"""属性测试 — 公开扫码登录 Schema 正确性属性。

Property 1: PublicQrLoginStatusResponse 状态字段约束 (需求 6.1)
Property 2: success 状态必须携带 token 和 user (需求 2.3)
Property 3: waiting/expired 状态 token 和 user 为 null (需求 2.4)
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings, strategies as st
from pydantic import ValidationError

from app.schemas.account import PublicQrLoginStatusResponse, UserInfo


# ── 辅助 strategies ──

valid_statuses = st.sampled_from(["waiting", "success", "expired"])

nonempty_str = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P", "S")),
    min_size=1,
    max_size=100,
)

user_info_st = st.builds(
    UserInfo,
    nickname=nonempty_str,
    avatar=st.one_of(st.none(), nonempty_str),
    xhs_user_id=nonempty_str,
)


# ── Property 1: 状态字段约束 ──


class TestStatusFieldConstraint:
    """验证 status 只能为 "waiting"、"success"、"expired" 之一（需求 6.1）。"""

    @given(status=valid_statuses)
    @settings(max_examples=50)
    def test_valid_status_accepted(self, status: str) -> None:
        """合法状态值应被接受。"""
        resp = PublicQrLoginStatusResponse(status=status)
        assert resp.status == status

    @given(
        status=st.text(min_size=1, max_size=50).filter(
            lambda s: s not in ("waiting", "success", "expired")
        )
    )
    @settings(max_examples=100)
    def test_invalid_status_rejected(self, status: str) -> None:
        """非法状态值应触发 ValidationError。"""
        with pytest.raises(ValidationError):
            PublicQrLoginStatusResponse(status=status)


# ── Property 2: success 状态必须携带 token 和 user ──


class TestSuccessCarriesTokenAndUser:
    """验证 status 为 success 时 token 和 user 不为 None（需求 2.3）。

    注意：Pydantic 模型本身不强制此业务约束，此属性测试验证
    当正确构造 success 响应时，token 和 user 字段确实存在且非空。
    """

    @given(token=nonempty_str, user=user_info_st)
    @settings(max_examples=100)
    def test_success_with_token_and_user(self, token: str, user: UserInfo) -> None:
        """success 状态携带 token 和 user 时，两者均不为 None。"""
        resp = PublicQrLoginStatusResponse(
            status="success", token=token, user=user
        )
        assert resp.status == "success"
        assert resp.token is not None, "success 状态的 token 不应为 None"
        assert resp.user is not None, "success 状态的 user 不应为 None"
        assert resp.token == token
        assert resp.user.nickname == user.nickname
        assert resp.user.xhs_user_id == user.xhs_user_id


# ── Property 3: waiting/expired 状态 token 和 user 为 null ──


class TestNonSuccessNullTokenAndUser:
    """验证 status 为 waiting 或 expired 时 token 和 user 为 None（需求 2.4）。"""

    @given(status=st.sampled_from(["waiting", "expired"]))
    @settings(max_examples=50)
    def test_non_success_defaults_null(self, status: str) -> None:
        """waiting/expired 状态默认 token 和 user 为 None。"""
        resp = PublicQrLoginStatusResponse(status=status)
        assert resp.status == status
        assert resp.token is None, f"{status} 状态的 token 应为 None"
        assert resp.user is None, f"{status} 状态的 user 应为 None"

    @given(status=st.sampled_from(["waiting", "expired"]))
    @settings(max_examples=50)
    def test_non_success_explicit_null(self, status: str) -> None:
        """显式传入 None 时 token 和 user 仍为 None。"""
        resp = PublicQrLoginStatusResponse(
            status=status, token=None, user=None
        )
        assert resp.token is None
        assert resp.user is None
