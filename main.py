"""
Telegram Bot：在指定群组接收 E-Hentai 画廊链接，排队执行流水线并推送到频道。
支持定时爬取画廊列表自动发现新作品。
"""
import asyncio
from loguru import logger
from telegram.ext import Application

from config.config import cfg
from handlers import register_all_handlers
from workers import pipeline_worker
from utils.db import init_db, close_db
from utils.tag_translator import load_tag_map
from scheduler import register_scheduled_jobs

logger.add("bot.log", encoding="utf-8", rotation="5 MB")


async def post_init(application: Application):
    await init_db()
    await load_tag_map()
    await application.bot.set_my_commands([])
    register_scheduled_jobs(application)
    asyncio.create_task(pipeline_worker(application))


async def post_shutdown(application: Application):
    await close_db()


def main():
    token = cfg.get("BOT_TOKEN")
    if not token:
        raise ValueError("未配置 BOT_TOKEN")
    builder = (
        Application.builder()
        .token(token)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
    )
    if cfg.get("proxy"):
        builder = builder.proxy(cfg["proxy"])
    app = builder.build()
    register_all_handlers(app)
    logger.info("Bot 启动中…")
    app.run_polling(allowed_updates=["message"])


if __name__ == "__main__":
    main()
