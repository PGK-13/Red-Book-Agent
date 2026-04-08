"""RAG 混合检索工具（向量 + BM25，Top-5）。"""
# TODO: 实现 Qdrant 混合检索
# - 相似度 < 0.6 的结果过滤掉
# - 结果按 retrieval_weight 加权排序
# - 返回数量 ≤ 5
