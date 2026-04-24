"""风控扫描工具（Agent 内调用 E 模块）。

对生成的回复内容执行敏感词扫描和风险检测。
返回统一 RiskScanResult。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class RiskScanResult:
    """风控扫描结果。"""

    passed: bool  # 是否通过
    hit_keywords: list[str]  # 命中的敏感词
    risk_level: str  # risk level: low / medium / high
    suggestion: str | None  # 修改建议（如不通过）


async def scan_content(
    content: str,
    merchant_id: str,
    account_id: str | None = None,
) -> RiskScanResult:
    """对内容执行风控扫描。

    Args:
        content: 待扫描内容。
        merchant_id: 商家 ID。
        account_id: 子账号 ID（可选）。

    Returns:
        RiskScanResult。
    """
    # TODO: 替换为实际 RiskService 调用
    # from app.services.risk_service import scan_text
    # result = await scan_text(content=content, merchant_id=merchant_id)
    # return RiskScanResult(
    #     passed=result.get("passed", False),
    #     hit_keywords=result.get("hit_keywords", []),
    #     risk_level=result.get("risk_level", "high"),
    #     suggestion=result.get("suggestion"),
    # )

    # 临时 mock，永远通过（实际使用时请实现真实调用）
    return RiskScanResult(
        passed=True,
        hit_keywords=[],
        risk_level="low",
        suggestion=None,
    )
