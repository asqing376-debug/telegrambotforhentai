"""
定时任务调度：利用 python-telegram-bot 的 JobQueue 注册周期性任务。
- 画廊列表爬取
- 标签翻译库刷新
"""
from loguru import logger
from telegram.ext import Application

from config.config import cfg
from utils.crawler import run_crawl_cycle
from utils.tag_translator import load_tag_map


async def _crawl_job(context):
    """定时爬取回调。"""
    bot = context.bot
    admin_ids = cfg.get("admin") or []
    try:
        await run_crawl_cycle(admin_ids=admin_ids, bot=bot)
    except Exception as e:
        logger.exception(f"定时爬取异常: {e}")


async def _refresh_tags_job(context):
    """定时刷新标签翻译库。"""
    try:
        await load_tag_map()
    except Exception as e:
        logger.exception(f"标签库刷新异常: {e}")


def register_scheduled_jobs(application: Application):
    """在 Bot 启动后注册所有定时任务。"""
    jq = application.job_queue
    if jq is None:
        logger.warning("JobQueue 不可用，跳过定时任务注册")
        return

    if cfg.get("crawl_enabled"):
        interval = int(cfg.get("crawl_interval") or 3600)
        jq.run_repeating(
            _crawl_job,
            interval=interval,
            first=30,
            name="crawl_galleries",
        )
        logger.info(f"已注册画廊爬取定时任务，间隔 {interval}s")
    else:
        logger.info("crawl_enabled=false，未注册爬取任务")

    jq.run_repeating(
        _refresh_tags_job,
        interval=86400,
        first=5,
        name="refresh_tag_map",
    )
    logger.info("已注册标签库刷新定时任务，间隔 24h")
