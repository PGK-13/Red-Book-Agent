from sqlalchemy.ext.asyncio import AsyncSession


class LongTermMemory:
    """PostgreSQL 长期记忆：存储用户偏好标签、历史意向等。"""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_user_memory(self, conversation_id: str) -> dict:
        """获取用户长期记忆（从 conversations.user_long_term_memory）。"""
        # TODO: 实现长期记忆读取
        return {}

    async def update_user_memory(self, conversation_id: str, memory: dict) -> None:
        """更新用户长期记忆。"""
        # TODO: 实现长期记忆更新
        raise NotImplementedError
