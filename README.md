# Telegram Bot for E-Hentai 画廊归档推送

根据项目《开发文档》实现的 Telegram 机器人：在指定群组接收 E-Hentai 画廊链接，自动下载、重命名、加密打包、上传图床、生成 Telegraph，并向指定频道推送（备用下载 + 主推送）。

## 功能概览

- 在配置的 `allowed_group` 内监听消息，匹配 `https://e[-x]hentai.org/g/<gid>/<token>` 后入队。
- 任务排队与并发限制：可配置 `max_concurrent_tasks`、`task_per_user_per_minute`。
- 流水线：下载重采样 zip → 解压 → 自然排序重命名 → 以画廊副标题（日文）命名并清理非法字符 → 加密压缩包 → 图片上传图床（CloudFlare ImgBed 风格 API）→ 生成 Telegraph（超过 200 张自动分页）→ 备用频道发送「文件名 + 文件 + 密码」并获取消息链接 → 主频道发送缩略图 + 描述 + Telegraph + 备用链接 → 本地文件清理。

## 配置

1. 复制 `config/config.yaml.example` 为 `config/config.yaml`。
2. 必填项：
   - `BOT_TOKEN`：Telegram Bot Token
   - `eh_cookie`：E-Hentai Cookie（`ipb_member_id`、`ipb_pass_hash`、`igneous`）
   - `allowed_group`：允许触发 Bot 的群组 ID 列表
   - `channel_backup_id` / `channel_main_id`：备用下载频道、主推送频道 ID
   - `imgbed_base_url` / `imgbed_api_token`：图床地址与 API Token
   - `ph_token`：Telegraph token

3. 敏感配置不要提交到仓库，建议将 `config/config.yaml` 加入 `.gitignore`。

## 运行

```bash
cd telegrambotforhentai
pip install -r requirements.txt
python main.py
```

可选：通过环境变量指定配置路径：`CONFIG_PATH=/path/to/config.yaml python main.py`。

## 参考

- 需求与设计见同目录《开发文档》。
- E-Hentai 解析与下载逻辑参考 [archive-at-home](https://github.com/mhdy2233/archive-at-home) 的 `server/utils/ehentai.py`、`client/utils/ehentai.py` 及 `server/utils/preview.py`。
