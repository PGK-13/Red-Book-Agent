"""风控扫描工具（Agent 内调用 E 模块）。"""
from app.services import risk_service


async def scan_content(content: str, merchant_id: str) -> dict:
    """
    在 Agent 内调用风控扫描。
    注意：这是 Service 层的薄封装，不包含独立业务逻辑。
    """
    # TODO: 传入 db session
    raise NotImplementedError
