# 快聊（Kuaichat）

一个基于 Flask + SQLite 的网页聊天应用，主打「隐私至上 · 好友加密聊天」。
后端为 Python/Flask，前端为原生 HTML + CSS + JavaScript（无框架），开箱即用。

当前版本：v1.8.0

## 功能特性

- 聊天：私聊、群聊、群公告、@提醒、消息引用回复、撤回、删除、多选删除、转发、收藏、置顶、草稿
- 好友：添加好友、好友申请、备注、分组、在线状态、二维码添加
- 动态（朋友圈）：图文动态、评论、回复、点赞、可见范围设置
- 积分商店：积分获取（每日签到等）、商品购买/赠送、头像框、礼物
- 宠物系统：领养/喂养/改名（陪伴型小宠物）
- 增值能力：Web Push 网页推送、语音消息、定时消息、投票、红包、位置共享
- 文件：图片/视频/文件上传，语音转写接口（默认未接引擎）
- 账号：昵称+密码登录、邀请码注册、邮箱申请邀请码（通过 Resend 发送邮件）、人机滑块验证
- 管理后台：用户管理、举报处理、封禁/禁言、邀请码申请审核
- 内置小游戏：2048、贪吃蛇、翻牌记忆、石头剪刀布、五子棋
- 界面：移动端优先、暗色模式

## 技术栈

- Python 3 / Flask
- SQLite（数据库文件自动创建：`kuaichat.db`）
- 原生 HTML / CSS / JavaScript

## 目录结构

```
mysite/
├── app.py               # Flask 主应用（路由 + API + 页面）
├── new_features*.py     # 功能模块（按 feature 拆分，由 app.py 注册）
├── templates/
│   ├── landing.html     # 落地页
│   ├── chat.html        # 聊天主界面
│   └── admin.html       # 管理后台
└── static/              # 前端 JS 模块
```

## 部署（PythonAnywhere）

1. 上传本项目到 PythonAnywhere 的 `/home/<用户名>/mysite/`
2. 在 Web 页新建 Web App（Python 3.10），Source code 目录指向 `mysite`
3. WSGI 配置文件内容：

```python
import sys
sys.path.insert(0, '/home/<用户名>/mysite')
from app import app as application
```

4. 安装依赖：`pip install flask`
5. 设置环境变量（见下），点击 **Reload** 即可访问

## 环境变量

代码中不包含任何硬编码密钥，部署时通过环境变量提供：

| 变量 | 用途 | 是否必填 |
| --- | --- | --- |
| `RESEND_API_KEY` | Resend 邮件服务 API Key（用于发送邀请码邮件） | 否（不配置则邮件功能不可用） |
| `ADMIN_PASSWORD` | 管理后台登录密码 | 是（不配置则无法登录管理后台） |

可选：`vapid_keys.txt`（Web Push VAPID 密钥，格式 `PUBLIC=...` / `PRIVATE=...`），不配置则推送功能不可用。

## 本地运行

```bash
pip install flask
export RESEND_API_KEY=your_key        # 可选
export ADMIN_PASSWORD=your_password
python app.py
```

然后访问 `http://127.0.0.1:5000/`。

## 说明

- 首次启动会自动创建 SQLite 数据库及全部数据表。
- 本仓库为净化后的开源版本：已移除所有硬编码的 API 密钥与管理员密码，原部署代码中的密钥已从公开版本剔除。
- 若需二次开发，请自行补充 LICENSE 后发布。
