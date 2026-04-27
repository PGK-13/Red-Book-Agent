COMMENT_INTENTS = ["ask_price", "complaint", "ask_link", "general_inquiry", "competitor_mention", "other"]

DM_INTENTS = [
    "ask_price",
    "ask_link",
    "purchase_intent",
    "complaint",
    "high_value_bd",
    "general_inquiry",
    "other",
]

INTENT_CLASSIFICATION_PROMPT = """
你是一个小红书评论/私信意图分类助手。

请分析用户输入，返回以下字段（JSON格式）：
{{
  "intent": "意图类别",
  "confidence": 置信度（0.0 ~ 1.0）,
  "sentiment_score": 情绪分数（-1.0 ~ 1.0，负数为负面情绪）
}}

## 评论场景（source=comment）可用意图：
{comment_intents}

## 私信场景（source=message）可用意图：
{dm_intents}

## 分类依据：
- ask_price: 询问价格、优惠、折扣
- complaint: 投诉、负面反馈、强烈不满
- ask_link: 询问链接、二维码、联系方式
- general_inquiry: 一般性咨询
- competitor_mention: 提及竞品
- purchase_intent: 明确购买意向
- high_value_bd: 高价值商业合作/探店邀约
- other: 其他

## 输入信息：
source: {source_type}
文本内容：{content}
OCR结果：{ocr_result}

请仔细分析文本内容和OCR结果（如有），给出最准确的分类。
"""
