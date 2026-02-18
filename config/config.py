import os
import yaml

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.environ.get("CONFIG_PATH") or os.path.join(BASE_DIR, "config.yaml")

if not os.path.isfile(CONFIG_PATH):
    raise FileNotFoundError(f"配置文件不存在: {CONFIG_PATH}")

with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    cfg = yaml.safe_load(f)

# 默认值
cfg.setdefault("proxy", None)
cfg.setdefault("max_concurrent_tasks", 2)
cfg.setdefault("task_per_user_per_minute", 2)
cfg.setdefault("archive_password", "gallery")
cfg.setdefault("allowed_user", [])
cfg.setdefault("db_path", "./data/bot.db")
cfg.setdefault("crawl_enabled", False)
cfg.setdefault("crawl_interval", 3600)
cfg.setdefault("crawl_sources", [])
cfg.setdefault("crawl_page_delay", 2)
cfg.setdefault("crawl_retry_limit", 3)
cfg.setdefault("crawl_alert_threshold", 5)
