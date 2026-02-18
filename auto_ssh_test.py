#!/usr/bin/env python3
"""自动 SSH 连接测试服务器并执行图床+Telegraph 测试（无需 expect）。"""
import sys
import os

# 确保可导入 paramiko
try:
    import paramiko
except ImportError:
    print("正在安装 paramiko ...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "paramiko", "-q"])
    import paramiko

HOST = "103.93.252.172"
PORT = 22
USER = "root"
PASSWORD = "XdWNOwvfzgkvkGy1EnqS"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PY_SCRIPT = os.path.join(SCRIPT_DIR, "run_test_on_server.py")
REMOTE_PATH = "/root/run_test_on_server.py"


def main():
    if not os.path.isfile(PY_SCRIPT):
        print(f"错误: 未找到 {PY_SCRIPT}")
        sys.exit(1)

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    print(f">>> 连接 {USER}@{HOST}:{PORT} ...")
    try:
        client.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=15)
    except Exception as e:
        print(f"连接失败: {e}")
        sys.exit(1)

    print(">>> 上传 run_test_on_server.py ...")
    try:
        sftp = client.open_sftp()
        sftp.put(PY_SCRIPT, REMOTE_PATH)
        sftp.close()
    except Exception as e:
        print(f"上传失败: {e}")
        client.close()
        sys.exit(1)

    print(">>> 执行测试 ...\n")
    stdin, stdout, stderr = client.exec_command("python3 " + REMOTE_PATH, get_pty=False, timeout=120)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    client.close()

    print(out)
    if err.strip():
        print("stderr:", err)
    print("\n完成。")


if __name__ == "__main__":
    main()
