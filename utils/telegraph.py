"""
Telegraph 页面生成：多图分页，每页最多 200 张。
复用 archive-at-home server/utils/preview.py 思路。
"""
import math
from config.config import cfg
from telegraph import Telegraph


def _telegraph_client():
    token = cfg.get("ph_token")
    if not token:
        raise ValueError("未配置 ph_token")
    return Telegraph(access_token=token)


def create_gallery_pages(title: str, image_urls: list, thumb_url: str) -> str:
    """
    创建一或多个 Telegraph 页，每页最多 200 张图。
    返回首页链接。
    """
    if not image_urls:
        raise ValueError("image_urls 为空")
    MAX_PER_PAGE = 200
    total = len(image_urls)
    pages = math.ceil(total / MAX_PER_PAGE)
    te = _telegraph_client()
    author = cfg.get("author_name") or "Bot"
    author_url = cfg.get("author_url") or ""

    first_path = None
    for i in range(pages):
        start = i * MAX_PER_PAGE
        end = start + MAX_PER_PAGE
        part_urls = image_urls[start:end]
        content = []
        if thumb_url:
            content.append({"tag": "img", "attrs": {"src": thumb_url}})
        content.extend([{"tag": "img", "attrs": {"src": u}} for u in part_urls])
        page_title = f"{title} ({i+1}/{pages})" if pages > 1 else title
        page = te.create_page(
            title=page_title,
            content=content,
            author_name=author,
            author_url=author_url,
        )
        path = page.get("path")
        if path and first_path is None:
            first_path = path
    if not first_path:
        raise RuntimeError("Telegraph 未返回 path")
    return f"https://telegra.ph/{first_path}"
