"""原始扫描件分组清单生成工具。

按分隔标记将连续扫描件切分成多笔凭证，生成 CSV 清单供后续重命名。
"""

import csv
from pathlib import Path

from audit_tools.common.logging import get_logger

logger = get_logger(__name__)

SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".heic", ".pdf"}


def is_supported(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in SUPPORTED_EXTS and not path.name.startswith(".")


def detect_separators(files: list, keyword: str = "finger", mode: str = "keyword") -> set:
    """检测分隔文件。

    Args:
        files: 文件列表
        keyword: 模式为 keyword 时的关键字
        mode: "keyword" | "size" | "none"
    """
    separators = set()
    if mode == "keyword":
        for index, path in enumerate(files):
            if keyword.lower() in path.name.lower():
                separators.add(index)
                logger.info("  标记为分隔：%s", path.name)
    elif mode == "size":
        threshold = 50 * 1024
        for index, path in enumerate(files):
            if path.stat().st_size < threshold:
                separators.add(index)
                logger.info("  标记为分隔：%s", path.name)
    return separators


def split_groups(files: list, separator_indices: set) -> list:
    """按分隔索引切分成组。"""
    groups = []
    current = []
    for index, path in enumerate(files):
        if index in separator_indices:
            if current:
                groups.append(current)
                current = []
            continue
        current.append(path)

    if current:
        groups.append(current)
    return groups


def process(folder: str, keyword: str = "finger", mode: str = "keyword") -> str:
    """生成分组清单 CSV。

    Args:
        folder: 扫描件文件夹路径
        keyword: 分隔文件关键字
        mode: 分隔识别模式

    Returns:
        生成的 CSV 路径
    """
    folder = Path(folder)
    if not folder.is_dir():
        raise FileNotFoundError(f"找不到文件夹：{folder}")

    files = sorted(path for path in folder.iterdir() if is_supported(path))
    if not files:
        raise SystemExit("该文件夹内没有图片或 PDF 文件。")

    logger.info("找到 %d 个文件。", len(files))
    separators = detect_separators(files, keyword, mode)
    groups = split_groups(files, separators)

    logger.info("识别出 %d 笔凭证：", len(groups))
    for index, group in enumerate(groups, 1):
        logger.info("  第 %02d 笔：%d 个文件，首张 %s", index, len(group), group[0].name)

    csv_path = folder / "凭证分组清单.csv"
    with csv_path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.writer(file)
        writer.writerow(["分组序号", "文件数量", "首张文件", "凭证字", "凭证号", "日期(日)", "科目/摘要", "备注"])
        for index, group in enumerate(groups, 1):
            writer.writerow([index, len(group), group[0].name, "记", "", "", "", ""])

    logger.info("分组清单已生成：%s", csv_path)
    logger.info("请在 Excel 中打开清单，填好凭证字、凭证号、日期和摘要后，再运行 scan-rename。")
    return str(csv_path)
