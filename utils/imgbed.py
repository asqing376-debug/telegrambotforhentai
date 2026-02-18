"""
图床上传：CloudFlare ImgBed 风格 API。
POST /upload，multipart/form-data，Authorization: Bearer <token>。
参考：https://cfbed.sanyue.de/api/
"""
import os
from loguru import logger
from config.config import cfg
from utils.http_client import http

# 脱敏：日志中不打印完整 Token
def _mask_token(t: str) -> str:
    if not t or len(t) < 8:
        return "***"
    return t[:4] + "***" + t[-2:]


async def upload_image(file_path: str) -> str:
    """
    上传单张图片到图床，返回可访问的图片 URL。
    失败抛出异常。
    """
    base = (cfg.get("imgbed_base_url") or "").rstrip("/")
    token = cfg.get("imgbed_api_token")
    if not base or not token:
        raise ValueError("未配置 imgbed_base_url 或 imgbed_api_token")
    url = f"{base}/upload"
    headers = {"Authorization": f"Bearer {token}"}
    if not os.path.isfile(file_path):
        raise FileNotFoundError(file_path)
    with open(file_path, "rb") as f:
        resp = await http.post(
            url,
            headers=headers,
            files={"file": (os.path.basename(file_path), f, "image/jpeg")},
        )
    # 避免在日志中记录完整 URL/Token
    logger.debug(f"imgbed upload status={getattr(resp, 'status_code', None)} file={os.path.basename(file_path)}")
    if resp.status_code != 200:
        logger.warning(f"imgbed upload failed status={resp.status_code} token={_mask_token(token)}")
        resp.raise_for_status()
    raw = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
    data = raw if isinstance(raw, dict) else {}
    # 常见返回格式：{"url": "..."} | {"data": {"url": "..."}} | [{ "src": "/file/xxx" }]（Cfbed 风格，需拼接域名）
    out_url = data.get("url") or (data.get("data") or {}).get("url")
    if not out_url and isinstance(raw, list) and len(raw) > 0 and isinstance(raw[0], dict):
        src = raw[0].get("src")
        if src:
            out_url = f"{base.rstrip('/')}{src}" if src.startswith("/") else f"{base}/{src}"
    if not out_url:
        raise ValueError(f"图床返回中无法解析 URL，结构: {type(raw).__name__} {list(raw)[:3] if isinstance(raw, (dict, list)) else ''}")
    return out_url
