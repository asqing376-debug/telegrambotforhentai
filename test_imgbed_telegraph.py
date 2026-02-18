"""
测试图床与 Telegraph 的实际请求/响应，便于确认解析逻辑。
运行前请确保 config/config.yaml 已配置 imgbed_base_url、imgbed_api_token、ph_token 等。
"""
import asyncio
import json
import os
import sys

# 最小有效 1x1 透明 PNG（约 68 字节）
MINI_PNG = bytes([
    0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,
    0x00, 0x00, 0x00, 0x0D, 0x49, 0x48, 0x44, 0x52,
    0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,
    0x08, 0x06, 0x00, 0x00, 0x00, 0x1F, 0x15, 0xC4,
    0x89, 0x00, 0x00, 0x00, 0x0A, 0x49, 0x44, 0x41,
    0x54, 0x78, 0x9C, 0x63, 0x00, 0x01, 0x00, 0x00,
    0x05, 0x00, 0x01, 0x0D, 0x0A, 0x2D, 0xB4, 0x00,
    0x00, 0x00, 0x00, 0x49, 0x45, 0x4E, 0x44, 0xAE,
    0x42, 0x60, 0x82,
])


async def test_imgbed():
    """上传一张最小 PNG 到图床，打印原始响应。"""
    try:
        from config.config import cfg
    except FileNotFoundError as e:
        print("图床测试跳过：未找到 config（需 config/config.yaml）", e)
        return
    base = (cfg.get("imgbed_base_url") or "").rstrip("/")
    token = cfg.get("imgbed_api_token")
    if not base or not token:
        print("图床测试跳过：未配置 imgbed_base_url 或 imgbed_api_token")
        return

    import httpx
    url = f"{base}/upload"
    headers = {"Authorization": f"Bearer {token}"}
    # 部分图床接受 Authorization: <token> 无 Bearer 前缀
    headers_alt = {"Authorization": token}

    print("--- 图床请求 ---")
    print(f"POST {url}")
    print(f"Authorization: Bearer {token[:8]}...{token[-4:] if len(token) > 12 else '***'}")
    print("body: multipart/form-data, file=test_mini.png (1x1 PNG)")
    print()

    for name, h in [("Bearer", headers), ("Raw", headers_alt)]:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    url,
                    headers=h,
                    files={"file": ("test_mini.png", MINI_PNG, "image/png")},
                )
            print(f"--- 图床响应 ({name}) ---")
            print(f"status_code: {resp.status_code}")
            print(f"Content-Type: {resp.headers.get('content-type', '')}")
            try:
                body = resp.json()
                print("body (JSON):", json.dumps(body, ensure_ascii=False, indent=2))
                # 当前解析逻辑（含 Cfbed 风格 data[0].src）
                base = (cfg.get("imgbed_base_url") or "").rstrip("/")
                data = body if isinstance(body, dict) else {}
                out_url = data.get("url") or (data.get("data") or {}).get("url")
                if not out_url and isinstance(body, list) and len(body) > 0 and isinstance(body[0], dict):
                    src = body[0].get("src")
                    if src:
                        out_url = f"{base}{src}" if src.startswith("/") else f"{base}/{src}"
                if out_url:
                    print(f"解析出的图片 URL: {out_url}")
                else:
                    print("解析出的 URL: 无（需根据上面 body 调整 utils/imgbed.py）")
            except Exception:
                print("body (raw):", resp.text[:500])
            print()
            if resp.status_code == 200:
                break
        except Exception as e:
            print(f"图床请求异常 ({name}): {e}\n")


def test_telegraph():
    """创建一篇最小 Telegraph 页，打印 create_page 返回结构。"""
    try:
        from config.config import cfg
    except FileNotFoundError:
        print("Telegraph 测试跳过：未找到 config")
        return
    token = cfg.get("ph_token")
    if not token:
        print("Telegraph 测试跳过：未配置 ph_token")
        return

    from telegraph import Telegraph
    te = Telegraph(access_token=token)
    author = cfg.get("author_name") or "Test"
    author_url = cfg.get("author_url") or ""

    print("--- Telegraph 请求 ---")
    print("create_page(title='Test Page', content=[img], author_name=..., author_url=...)")
    print()

    try:
        page = te.create_page(
            title="Test Page",
            content=[{"tag": "img", "attrs": {"src": "https://telegra.ph/file/1.jpg"}}],
            author_name=author,
            author_url=author_url,
        )
        print("--- Telegraph 响应 ---")
        print("create_page 返回:", json.dumps(page, ensure_ascii=False, indent=2))
        path = page.get("path")
        if path:
            print(f"解析出的首页链接: https://telegra.ph/{path}")
        else:
            print("解析出的 path: 无（需根据上面返回调整 utils/telegraph.py）")
    except Exception as e:
        print("Telegraph 请求异常:", e)


def main():
    print("========== 图床实际解析测试 ==========\n")
    asyncio.run(test_imgbed())
    print("========== Telegraph 实际解析测试 ==========\n")
    test_telegraph()


if __name__ == "__main__":
    main()
