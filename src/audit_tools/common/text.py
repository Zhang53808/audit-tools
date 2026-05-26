"""文本处理工具函数。"""

import re
from pathlib import Path


def sanitize_filename(value: str) -> str:
    """移除文件名中的非法字符，压缩空白。"""
    value = re.sub(r'[\\/:*?"<>|]', "_", value)
    return re.sub(r"\s+", " ", value).strip()


def unique_path(path: Path) -> Path:
    """如果路径已存在，追加 _2, _3 ... 直到找到空闲名称。"""
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    index = 2
    while True:
        candidate = path.with_name(f"{stem}_{index}{suffix}")
        if not candidate.exists():
            return candidate
        index += 1
