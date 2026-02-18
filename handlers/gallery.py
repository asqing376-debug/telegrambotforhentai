"""
群组内接收 E-Hentai 链接，匹配后入队并回复；后台 worker 执行流水线并更新状态。
"""
import re
from loguru import logger
from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters

from config.config import cfg
from queue import put_task, can_accept_user, record_user_submit, queue_size, GalleryTask, init_queue
from utils.pipeline import run_pipeline


# 链接正则：https://e[-x]hentai.org/g/<gid>/<token>
LINK_PATTERN = re.compile(r"https://e[-x]hentai\.org/g/(\d+)/([0-9a-f]{10})", re.I)


def _allowed_chat(chat_id: int, user_id: int) -> bool:
    allowed_groups = cfg.get("allowed_group") or []
    allowed_users = cfg.get("allowed_user") or []
    return chat_id in allowed_groups or user_id in allowed_users


async def on_gallery_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    text = update.message.text.strip()
    m = LINK_PATTERN.search(text)
    if not m:
        return
    gid, token = m.group(1), m.group(2)
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id if update.effective_user else 0

    if not _allowed_chat(chat_id, user_id):
        return

    if not await can_accept_user(user_id):
        await update.message.reply_text("⏳ 您提交过于频繁，请稍后再试。")
        return

    await record_user_submit(user_id)
    status_msg = await update.message.reply_text(
        f"📥 已加入队列（当前排队约 {queue_size()} 个任务），正在处理…"
    )

    task = GalleryTask(
        gid=gid,
        token=token,
        user_id=user_id,
        chat_id=chat_id,
        message_id=status_msg.message_id,
    )
    await put_task(task)
    logger.info(f"enqueue gid={gid} token={token} user={user_id}")


def register(app):
    init_queue()
    app.add_handler(
        MessageHandler(
            (filters.ChatType.GROUPS | filters.ChatType.PRIVATE) & filters.Regex(LINK_PATTERN),
            on_gallery_link,
        )
    )
