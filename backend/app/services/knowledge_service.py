from sqlalchemy.ext.asyncio import AsyncSession


# TODO: 实现知识库业务逻辑
# - 文档解析分块（≤512 token，50 token 重叠）
# - Qdrant 向量索引
# - 混合检索（向量 + BM25，Top-5）
# - 爆款文案权重动态调整
# - 行业爆款采集与趋势分析
