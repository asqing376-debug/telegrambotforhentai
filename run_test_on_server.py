#!/usr/bin/env python3
"""
在测试服务器上一键运行：图床 + Telegraph 实际解析测试。
用法：上传到服务器后执行  python3 run_test_on_server.py
依赖：pip install httpx telegraph pyyaml（脚本内会尝试安装）
"""
import json
import subprocess
import sys

# 测试用配置（与 config.yaml.example 一致，仅用于本脚本）
IMGBED_BASE = "https://yaoianime.cc"
IMGBED_TOKEN = "imgbed_65hMJDuMJjk0GNJPsFlDObl5DpXhEuK5"
PH_TOKEN = "fe538f89c77089abaed746e266eff64881aeb80be84ae74f4e9d8cc9d384"
AUTHOR_NAME = "筋肉控"
AUTHOR_URL = "https://t.me/jinroukong"

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


def ensure_deps():
    try:
        import httpx
        import telegraph
    except ImportError:
        print("安装依赖: httpx telegraph pyyaml ...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "httpx", "telegraph", "pyyaml", "-q"])
        print("依赖已安装。\n")


def test_imgbed():
    import httpx
    base = IMGBED_BASE.rstrip("/")
    url = f"{base}/upload"
    headers = {"Authorization": f"Bearer {IMGBED_TOKEN}"}
    print("--- 图床请求 ---")
    print(f"POST {url}")
    print(f"Authorization: Bearer {IMGBED_TOKEN[:12]}...")
    print("body: multipart file=test_mini.png\n")
    try:
        with httpx.Client(timeout=30) as client:
            resp = client.post(
                url,
                headers=headers,
                files={"file": ("test_mini.png", MINI_PNG, "image/png")},
            )
    except Exception as e:
        print(f"图床请求异常: {e}\n")
        return
    print("--- 图床响应 ---")
    print(f"status_code: {resp.status_code}")
    print(f"Content-Type: {resp.headers.get('content-type', '')}")
    try:
        body = resp.json()
        print("body (JSON):", json.dumps(body, ensure_ascii=False, indent=2))
        data = body if isinstance(body, dict) else {}
        out_url = data.get("url") or (data.get("data") or {}).get("url")
        if not out_url and isinstance(body, list) and len(body) > 0 and isinstance(body[0], dict):
            src = body[0].get("src")
            if src:
                out_url = f"{base}{src}" if src.startswith("/") else f"{base}/{src}"
        print(f"解析出的图片 URL: {out_url or '(无)'}")
    except Exception:
        print("body (raw):", resp.text[:500])
    print()


def test_telegraph():
    from telegraph import Telegraph
    te = Telegraph(access_token=PH_TOKEN)
    print("--- Telegraph 请求 ---")
    print("create_page(title='Test', content=[img], author_name=筋肉控, ...)")
    print()
    try:
        page = te.create_page(
            title="Test Page",
            content=[{"tag": "img", "attrs": {"src": "https://telegra.ph/file/1.jpg"}}],
            author_name=AUTHOR_NAME,
            author_url=AUTHOR_URL,
        )
        print("--- Telegraph 响应 ---")
        print("create_page 返回:", json.dumps(page, ensure_ascii=False, indent=2))
        path = page.get("path")
        print(f"解析出的首页链接: https://telegra.ph/{path}" if path else "解析出的 path: 无")
    except Exception as e:
        print("Telegraph 请求异常:", e)


def main():
    print("========== 图床 + Telegraph 实际解析测试 ==========\n")
    ensure_deps()
    test_imgbed()
    print("========== Telegraph ==========\n")
    test_telegraph()
    print("\n完成。")


if __name__ == "__main__":
    main()
