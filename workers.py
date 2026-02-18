"""
后台 worker：从队列取任务，限制并发，执行流水线并更新群内状态消息。
"""
import asyncio
from loguru import logger
from telegram import Bot

from config.config import cfg
from queue import get_task, max_concurrent
from utils.pipeline import run_pipeline


async def pipeline_worker(application):
    """在 post_init 中启动，循环处理队列任务。"""
    bot: Bot = application.bot
    sem = asyncio.Semaphore(max_concurrent())
    while True:
        try:
            task = await get_task()
            async with sem:
                await _process_one(bot, task)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.exception(f"worker error: {e}")


async def _process_one(bot: Bot, task):
    gid, token = task.gid, task.token
    chat_id = task.chat_id
    message_id = task.message_id
    source = getattr(task, "source", "manual")
    try:
        if chat_id and message_id:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=f"🔄 正在处理 https://e-hentai.org/g/{gid}/{token}/ …",
            )
        result = await run_pipeline(gid, token, bot, source=source)
        if chat_id and message_id:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=f"✅ 处理完成\n"
                     f"Telegraph: {result['telegraph_url']}\n"
                     f"备用下载: {result['backup_message_link']}",
            )
    except Exception as e:
        logger.exception(f"pipeline fail gid={gid} token={token}: {e}")
        if chat_id and message_id:
            try:
                await bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=f"❌ 处理失败: {str(e)[:200]}",
                )
            except Exception:
                pass
