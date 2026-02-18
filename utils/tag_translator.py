"""
EhTagTranslation 标签中文翻译模块。
从 GitHub 下载 db.text.json，构建 namespace:tag → 中文名 映射表。
"""
from collections import defaultdict

from loguru import logger

from utils.http_client import http

_tag_map: dict = None

TAG_DB_URL = (
    "https://github.com/EhTagTranslation/Database/releases/latest/download/db.text.json"
)


async def load_tag_map():
    """下载并解析 EhTagTranslation 数据库，写入全局 _tag_map。"""
    global _tag_map
    try:
        resp = await http.get(TAG_DB_URL, follow_redirects=True, timeout=30)
        resp.raise_for_status()
        db = resp.json()
    except Exception as e:
        logger.error(f"下载 EhTagTranslation 失败: {e}")
        if _tag_map is None:
            _tag_map = defaultdict(lambda: {"name": "", "data": {}})
        return

    new_map = defaultdict(lambda: {"name": "", "data": {}})
    for entry in db.get("data", [])[2:]:
        namespace = entry.get("namespace", "")
        if not namespace:
            continue
        new_map[namespace]["name"] = entry.get("frontMatters", {}).get("name", namespace)
        new_map[namespace]["data"].update(
            {key: value["name"] for key, value in entry.get("data", {}).items()}
        )
    _tag_map = new_map
    logger.info(f"EhTagTranslation 加载完成，共 {len(_tag_map)} 个 namespace")


def translate_tags(raw_tags: list[str]) -> dict[str, list[str]]:
    """
    将 gdata API 返回的 tags 列表翻译为中文。

    参数:
        raw_tags: ["language:japanese", "artist:xxx", ...]
    返回:
        {namespace: [中文标签1, 中文标签2, ...]}
        namespace 使用原始英文键（language / parody / artist / ...）
    """
    global _tag_map
    if _tag_map is None:
        return {}

    result: dict[str, list[str]] = {}
    for item in raw_tags:
        ns, sep, tag = item.partition(":")
        if not sep:
            continue
        ns_info = _tag_map.get(ns)
        if ns_info:
            cn_name = ns_info["data"].get(tag)
            if cn_name:
                result.setdefault(ns, []).append(cn_name)
            else:
                result.setdefault(ns, []).append(tag)
        else:
            result.setdefault(ns, []).append(tag)
    return result
