"""RAG 混合检索工具（向量 + BM25，Top-5）。"""

from __future__ import annotations


async def hybrid_search(
    query: str,
    account_id: str,
    top_k: int = 3,
) -> list[dict]:
    """Qdrant 混合检索（向量 + BM25），返回 Top-K 相关文档。

    Args:
        query: 搜索查询。
        account_id: 账号 ID。
        top_k: 返回结果数量（≤5）。

    Returns:
        结果列表，每项包含 content, score, doc_id 等字段。
    """
    # TODO: 实现 Qdrant 混合检索
    # - 相似度 < 0.6 的结果过滤掉
    # - 结果按 retrieval_weight 加权排序
    # - 返回数量 ≤ 5
    # 当前返回空结果，不影响客服生成流程
    return []
