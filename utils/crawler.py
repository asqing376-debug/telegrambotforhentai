"""
画廊列表定时爬取模块：请求 E-Hentai 列表页，解析新增画廊链接，去重后注入任务队列。
"""
import re
import asyncio

from bs4 import BeautifulSoup
from loguru import logger

from config.config import cfg
from utils.http_client import http
from utils.db import is_processed, set_offset, get_offset
from queue import put_task, GalleryTask

GALLERY_LINK_RE = re.compile(r"https://e[-x]hentai\.org/g/(\d+)/([0-9a-f]{10})", re.I)


async def crawl_list_page(url: str, page: int = 0) -> list[tuple[str, str]]:
    """
    请求单个列表页，解析出所有画廊 (gid, token)。
    E-Hentai 列表页分页参数为 ?page=N（追加到已有 query string）。
    """
    sep = "&" if "?" in url else "?"
    page_url = f"{url}{sep}page={page}" if page > 0 else url
    try:
        resp = await http.get(page_url, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        logger.error(f"爬取列表页失败 page={page}: {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    galleries = []
    seen = set()
    for a_tag in soup.find_all("a", href=GALLERY_LINK_RE):
        m = GALLERY_LINK_RE.search(a_tag["href"])
        if m:
            gid, token = m.group(1), m.group(2)
            if gid not in seen:
                seen.add(gid)
                galleries.append((gid, token))
    return galleries


async def crawl_source(source_cfg: dict) -> list[tuple[str, str]]:
    """
    对单个爬取源执行增量爬取。
    返回新增（未处理过的）画廊 (gid, token) 列表。
    """
    name = source_cfg.get("name", "unnamed")
    url = source_cfg.get("url", "")
    max_pages = int(source_cfg.get("max_pages", 3))
    if not url:
        logger.warning(f"爬取源 '{name}' 未配置 url，跳过")
        return []

    new_galleries = []
    hit_processed = False

    for page in range(max_pages):
        if hit_processed:
            break
        galleries = await crawl_list_page(url, page)
        if not galleries:
            break

        for gid, token in galleries:
            if await is_processed(gid):
                hit_processed = True
                break
            new_galleries.append((gid, token))

        delay = cfg.get("crawl_page_delay") or 2
        await asyncio.sleep(delay)

    if new_galleries:
        first_gid = new_galleries[0][0]
        await set_offset(name, last_gid=first_gid, last_page=0)
        logger.info(f"爬取源 '{name}' 发现 {len(new_galleries)} 个新画廊")
    else:
        logger.info(f"爬取源 '{name}' 无新画廊")

    return new_galleries


async def run_crawl_cycle(admin_ids: list[int] = None, bot=None):
    """
    遍历所有 crawl_sources，汇总新画廊，注入任务队列。
    爬取失败超过阈值时向管理员告警。
    """
    if not cfg.get("crawl_enabled"):
        return

    sources = cfg.get("crawl_sources") or []
    if not sources:
        logger.debug("未配置 crawl_sources，跳过爬取")
        return

    retry_limit = int(cfg.get("crawl_retry_limit") or 3)
    alert_threshold = int(cfg.get("crawl_alert_threshold") or 5)
    consecutive_failures = 0
    total_new = 0

    for src in sources:
        for attempt in range(retry_limit):
            try:
                new_galleries = await crawl_source(src)
                consecutive_failures = 0
                for gid, token in new_galleries:
                    task = GalleryTask(
                        gid=gid,
                        token=token,
                        user_id=0,
                        chat_id=0,
                        message_id=0,
                        source="crawl",
                    )
                    await put_task(task)
                    total_new += 1
                break
            except Exception as e:
                consecutive_failures += 1
                logger.error(f"爬取源 '{src.get('name')}' 第 {attempt+1} 次失败: {e}")
                if consecutive_failures >= alert_threshold and bot and admin_ids:
                    for aid in admin_ids:
                        try:
                            await bot.send_message(
                                chat_id=aid,
                                text=f"⚠️ 画廊列表爬取连续失败 {consecutive_failures} 次，请检查。",
                            )
                        except Exception:
                            pass
                await asyncio.sleep(5)

    if total_new:
        logger.info(f"本轮爬取共注入 {total_new} 个新任务")
