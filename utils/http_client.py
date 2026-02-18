import httpx
from config.config import cfg

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36"
}
cookie_str = cfg.get("eh_cookie") or ""
cookie_jar = httpx.Cookies()
for item in (cookie_str or "").split(";"):
    if "=" in item:
        k, v = item.strip().split("=", 1)
        cookie_jar.set(k, v, domain=".e-hentai.org")
        cookie_jar.set(k, v, domain=".exhentai.org")

http = httpx.AsyncClient(
    proxy=cfg.get("proxy"),
    headers=headers,
    cookies=cookie_jar,
    timeout=30,
    follow_redirects=True,
)
