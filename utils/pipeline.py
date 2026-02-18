"""
画廊流水线：下载 zip → 解压 → 自然排序重命名 → 副标题命名+非法字符清理 → 加密打包
→ 图床上传 → Telegraph → 频道推送（文件名+文件+密码；缩略图+描述+Telegraph+备用链接）→ 本地清理
"""
import re
import os
import html
import asyncio
import zipfile
import shutil

import httpx
import pyzipper
from loguru import logger

from config.config import cfg
from utils.ehentai import get_gdata, get_download_url
from utils.imgbed import upload_image
from utils.telegraph import create_gallery_pages
from utils.tag_translator import translate_tags
from utils.db import mark_processed
from utils.http_client import http

TAG_FIELD_ORDER = [
    ("language", "语言"),
    ("parody", "原作"),
    ("group", "团队"),
    ("artist", "艺术家"),
    ("male", "男性"),
]


def _natural_sort_key(s: str):
    return [int(x) if x.isdigit() else x.lower() for x in re.split(r"(\d+)", s)]


def _sanitize_filename(name: str) -> str:
    """清理文件名非法字符。"""
    if not name:
        return "gallery"
    # 保留日文、英文、数字、常见标点
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", name)
    name = name.strip().strip(".") or "gallery"
    return name[:200]


async def _download_zip(url: str, dest_path: str) -> None:
    """流式下载 zip 到本地。"""
    async with httpx.AsyncClient(proxy=cfg.get("proxy"), timeout=120, follow_redirects=True) as client:
        async with client.stream("GET", url) as resp:
            resp.raise_for_status()
            with open(dest_path, "wb") as f:
                async for chunk in resp.aiter_bytes(1024 * 1024):
                    f.write(chunk)


def _unzip_and_rename_natural(zip_path: str, extract_dir: str) -> list[str]:
    """解压并按自然排序重命名为 0001.jpg, 0002.jpg... 返回排序后的文件名列表。"""
    os.makedirs(extract_dir, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(extract_dir)
    files = [f for f in os.listdir(extract_dir) if os.path.isfile(os.path.join(extract_dir, f))]
    files.sort(key=_natural_sort_key)
    renamed = []
    for idx, fn in enumerate(files, start=1):
        ext = os.path.splitext(fn)[1] or ".jpg"
        new_name = f"{idx:04d}{ext}"
        old_path = os.path.join(extract_dir, fn)
        new_path = os.path.join(extract_dir, new_name)
        if old_path != new_path:
            os.rename(old_path, new_path)
        renamed.append(new_name)
    return renamed


def _make_encrypted_zip(source_dir: str, zip_path: str, password: str) -> None:
    """将 source_dir 下文件打成加密 zip。"""
    with pyzipper.AESZipFile(
        zip_path, "w", compression=pyzipper.ZIP_DEFLATED, encryption=pyzipper.WZ_AES
    ) as zf:
        zf.setpassword(password.encode("utf-8"))
        for fn in sorted(os.listdir(source_dir), key=_natural_sort_key):
            fp = os.path.join(source_dir, fn)
            if os.path.isfile(fp):
                zf.write(fp, fn)


def _build_channel_caption(
    title: str,
    title_jpn: str,
    translated_tags: dict[str, list[str]],
    telegraph_url: str,
    gid: str,
    token: str,
) -> str:
    """按固定顺序组装频道消息正文，缺失的标签行跳过。"""
    safe_title = html.escape(title)
    safe_title_jpn = html.escape(title_jpn)
    lines = [safe_title, safe_title_jpn]
    for ns, label in TAG_FIELD_ORDER:
        tags = translated_tags.get(ns)
        if tags:
            lines.append(f"{label}: {' '.join(f'#{t}' for t in tags)}")
    lines.append(f"原始地址: https://e-hentai.org/g/{gid}/{token}/")
    lines.append(f'在线预览: <a href="{telegraph_url}">{safe_title_jpn}</a>')
    lines.append("备注: 近期网络不稳定，如不显示图片刷新两次即可")
    return "\n".join(lines)


async def run_pipeline(gid: str, token: str, bot, source: str = "manual") -> dict:
    """
    执行完整流水线，返回用于频道推送的数据。
    失败抛出异常；成功后本函数内自动清理本地临时文件。
    """
    download_folder = cfg.get("download_folder") or "./download"
    temp_folder = cfg.get("temp_folder") or "./temp"
    password = cfg.get("archive_password") or "gallery"
    channel_backup_id = cfg.get("channel_backup_id")
    channel_main_id = cfg.get("channel_main_id")
    if not channel_backup_id or not channel_main_id:
        raise ValueError("未配置 channel_backup_id 或 channel_main_id")

    os.makedirs(download_folder, exist_ok=True)
    os.makedirs(temp_folder, exist_ok=True)
    zip_path = os.path.join(download_folder, f"{gid}.zip")
    extract_dir = os.path.join(temp_folder, gid)
    archive_name = None
    archive_path = None

    try:
        # 1) 画廊元数据
        meta = await get_gdata(gid, token)
        title = (meta.get("title") or "").strip()
        title_jpn = (meta.get("title_jpn") or "").strip() or title
        thumb_url = (meta.get("thumb") or "").replace("s.exhentai", "ehgt")
        filecount = int(meta.get("filecount") or 0)
        raw_tags = meta.get("tags") or []

        # 1.1) 标签翻译
        translated_tags = translate_tags(raw_tags)

        # 2) 重采样下载链接
        d_url = await get_download_url(gid, token, "res")
        await _download_zip(d_url, zip_path)

        # 3) 解压 + 自然排序重命名
        image_names = _unzip_and_rename_natural(zip_path, extract_dir)
        if filecount and len(image_names) != filecount:
            logger.warning(f"gid={gid} 页数不一致: 预期={filecount} 实际={len(image_names)}")

        # 4) 以副标题命名并清理非法字符，打包加密 zip
        safe_name = _sanitize_filename(title_jpn)
        archive_name = f"{safe_name}.zip"
        archive_path = os.path.join(temp_folder, archive_name)
        _make_encrypted_zip(extract_dir, archive_path, password)

        # 5) 上传图片到图床（逐张），收集 URL
        image_urls = []
        for fn in image_names:
            fp = os.path.join(extract_dir, fn)
            if not os.path.isfile(fp):
                continue
            try:
                url = await upload_image(fp)
                image_urls.append(url)
                await asyncio.sleep(2)
            except Exception as e:
                logger.error(f"imgbed upload fail {fn}: {e}")
                raise
        if not image_urls:
            raise RuntimeError("没有可用的图片 URL")

        # 6) Telegraph
        telegraph_url = create_gallery_pages(title or title_jpn, image_urls, thumb_url)

        # 7) 备用频道：文件名 + 文件 + 密码，并获取消息链接
        with open(archive_path, "rb") as f:
            msg = await bot.send_document(
                chat_id=channel_backup_id,
                document=f,
                caption=f"文件名：{archive_name}\n密码：{password}",
                filename=archive_name,
            )
        chat_id_str = str(msg.chat_id).replace("-100", "")
        backup_message_link = f"https://t.me/c/{chat_id_str}/{msg.message_id}"

        # 8) 主频道：缩略图 + 标签格式消息
        description = _build_channel_caption(
            title, title_jpn, translated_tags, telegraph_url, gid, token
        )
        await bot.send_photo(
            chat_id=channel_main_id,
            photo=thumb_url,
            caption=description,
            parse_mode="HTML",
        )

        # 9) 标记已处理
        await mark_processed(gid, token, source)

        return {
            "title": title,
            "title_jpn": title_jpn,
            "thumb_url": thumb_url,
            "telegraph_url": telegraph_url,
            "backup_message_link": backup_message_link,
            "archive_path": archive_path,
            "archive_name": archive_name,
            "archive_password": password,
            "description": description,
        }
    finally:
        for p in [zip_path, extract_dir, archive_path]:
            if p and os.path.exists(p):
                try:
                    if os.path.isfile(p):
                        os.remove(p)
                    else:
                        shutil.rmtree(p, ignore_errors=True)
                except Exception as e:
                    logger.warning(f"清理失败 {p}: {e}")
        if os.path.isdir(download_folder) and not os.listdir(download_folder):
            try:
                os.rmdir(download_folder)
            except Exception:
                pass



