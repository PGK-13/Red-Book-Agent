"""OCR 识别工具（PaddleOCR）。

对小红书评论中的图片执行本地 OCR 识别，支持远程图片下载。
置信度 < 0.5 时返回空字符串，触发人工审核。
"""

from __future__ import annotations

import logging
from typing import Tuple

logger = logging.getLogger(__name__)

# PaddleOCR 全局实例（惰性初始化）
_ocr_engine: "PaddleOCR | None" = None


def _get_ocr_engine() -> "PaddleOCR":
    """获取或初始化 PaddleOCR 实例（惰性加载）。"""
    global _ocr_engine
    if _ocr_engine is None:
        from paddleocr import PaddleOCR

        _ocr_engine = PaddleOCR(
            use_angle_cls=True,
            lang="ch",  # 中文
            use_gpu=False,  # CPU 执行
            show_log=False,  # 关闭日志
        )
    return _ocr_engine


async def ocr_image(image_source: str) -> Tuple[str, float]:
    """对图片执行 OCR 识别。

    Args:
        image_source: 图片源，可以是 URL 或本地文件路径。

    Returns:
        (识别文本, 置信度)。

    Notes:
        - 若为远程 URL，自动下载后识别
        - 置信度 < 0.5 时返回空字符串，触发人工审核
        - 仅支持中英文识别
    """
    import tempfile
    import urllib.request
    from pathlib import Path

    image_path = image_source

    # 如果是 URL，下载到临时文件
    if image_source.startswith(("http://", "https://")):
        try:
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                urllib.request.urlretrieve(image_source, tmp.name)
                image_path = tmp.name
        except Exception as e:
            logger.warning(f"Failed to download image {image_source}: {e}")
            return "", 0.0

    # 确保文件存在
    if not Path(image_path).exists():
        logger.warning(f"Image file not found: {image_path}")
        return "", 0.0

    # 执行 OCR
    try:
        ocr = _get_ocr_engine()
        result = ocr.ocr(image_path, cls=True)

        if not result or not result[0]:
            return "", 0.0

        # 合并所有识别结果
        texts = []
        confidences = []

        for line in result[0]:
            if line:
                text = line[1][0]  # 识别文本
                confidence = line[1][1]  # 置信度
                texts.append(text)
                confidences.append(confidence)

        combined_text = "\n".join(texts)
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

        # 置信度低于阈值时返回空字符串，触发人工审核
        if avg_confidence < 0.5:
            logger.warning(
                f"OCR confidence {avg_confidence:.2f} < 0.5, triggering human review"
            )
            return "", avg_confidence

        return combined_text, avg_confidence

    except Exception as e:
        logger.error(f"OCR failed for {image_path}: {e}")
        return "", 0.0
    finally:
        # 清理临时文件
        if image_source.startswith(("http://", "https://")):
            try:
                Path(image_path).unlink(missing_ok=True)
            except Exception:
                pass
