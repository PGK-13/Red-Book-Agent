from sqlalchemy.ext.asyncio import AsyncSession


async def scan(content: str, merchant_id: str, db: AsyncSession) -> dict:
    """
    对内容执行风控扫描（敏感词 + 频率限制 + 去重）。
    必须在任何出站内容发布前同步调用，耗时目标 ≤1s。

    Returns:
        {"passed": bool, "violations": list[str]}
    """
    # TODO: 实现敏感词扫描、频率检查、内容去重
    return {"passed": True, "violations": []}
