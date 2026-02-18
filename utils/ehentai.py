"""
E-Hentai 相关：画廊元数据、GP 消耗、重采样下载链接。
复用自 archive-at-home 的 server/utils/ehentai.py 与 client/utils/ehentai.py。
"""
import re
import math
import httpx
from bs4 import BeautifulSoup
from config.config import cfg
from utils.http_client import http

EX_BASE_URL = "https://exhentai.org"
EH_BASE_URL = "https://e-hentai.org"

_headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
    "Cookie": cfg.get("eh_cookie") or "",
}


def _get_base_url():
    try:
        r = httpx.get(EX_BASE_URL, headers=_headers, proxy=cfg.get("proxy"), timeout=10)
        if r.text and "Key missing" not in r.text:
            return EX_BASE_URL
    except Exception:
        pass
    return EH_BASE_URL


_base_url = _get_base_url()


async def get_gdata(gid: str, token: str) -> dict:
    """通过 gdata API 获取画廊元数据。"""
    url = "https://e-hentai.org/api.php"
    data = {"method": "gdata", "gidlist": [[gid, token]], "namespace": 1}
    resp = await http.post(url, json=data)
    resp.raise_for_status()
    result = resp.json().get("gmetadata") or []
    if not result:
        raise ValueError("gdata 返回为空")
    return result[0]


async def get_GP_cost(gid: str, token: str) -> dict:
    """获取原图/重采样/预览 GP 消耗。"""
    def convert_to_mib(size_str):
        m = re.match(r"(\d+\.?\d*)\s*(\w+)?", (size_str or "").strip())
        if not m:
            raise ValueError(f"Invalid size: {size_str}")
        size = float(m.group(1))
        unit = (m.group(2) or "MiB").lower()
        factors = {"gib": 1024, "gb": 1024 / 1.048576, "mib": 1, "mb": 1 / 1.048576, "kib": 1 / 1024, "kb": 1 / 1024 / 1.048576}
        return size * factors.get(unit, 1) * 21

    require_GP = {"org": None, "res": None, "pre": None}
    url = f"{_base_url}/archiver.php?gid={gid}&token={token}"
    resp = await http.get(url)
    if resp.status_code != 200:
        raise RuntimeError(f"archiver 请求失败: {resp.status_code}")
    if "bounce_login" in str(resp.url):
        raise RuntimeError("Cookie 无效或已过期")
    soup = BeautifulSoup(resp.text, "html.parser")
    GPs = soup.find_all("strong")
    if not GPs:
        raise RuntimeError("无法解析 GP 信息")
    for i, x in enumerate(GPs):
        t = (x.text or "").strip()
        if t == "Free!":
            if i == 0:
                require_GP["org"] = round(float(convert_to_mib((GPs[1].text or "0 MiB"))))
            elif i == 2:
                require_GP["res"] = round(float(convert_to_mib((GPs[3].text or "0 MiB"))))
        else:
            if i == 0:
                require_GP["org"] = int("".join(c for c in (GPs[0].text or "") if c.isdigit()) or 0)
            elif i == 2:
                require_GP["res"] = int("".join(c for c in (GPs[2].text or "") if c.isdigit()) or 0)
    if require_GP.get("res"):
        require_GP["pre"] = math.ceil(int(require_GP["res"]) * 5)
    return require_GP


async def get_download_url(gid: str, token: str, image_quality: str = "res") -> str:
    """
    请求归档页面并解析重采样/原图下载链接（本地 Cookie，不依赖外部 Client）。
    复用 client/utils/ehentai.py 的 _archiver + 解析逻辑。
    """
    url = f"{_base_url}/archiver.php?gid={gid}&token={token}"
    data = {
        "dltype": image_quality,
        "dlcheck": f"Download+{'Original' if image_quality == 'org' else 'Resample'}+Archive",
    }
    resp = await http.post(url, data=data)
    resp.raise_for_status()
    text = resp.text
    m = re.search(r'document\.location\s*=\s*["\'](.*?)["\'];', text, re.DOTALL)
    if not m:
        raise RuntimeError("归档链接解析失败")
    d_url = m.group(1).rstrip("?autostart=1").rstrip("?start=1").rstrip("&")
    if not d_url.endswith("?"):
        d_url = d_url + "?"
    # 使链接可直接下载：重采样为 ...1?start=1
    suffix = "1?start=1" if image_quality == "res" else "0?start=1"
    return d_url + suffix
