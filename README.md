# Expatus MVP v0.2 - 2026-08-16

这是今天锁定后的整合版：统一首页、注册登录、我的进度、我的收藏、莱顿城市指南和退租押金/问题收集页面；两项收费内容暂不上线。

## 第一次本地启动（Windows）

```bat
cd /d 你的项目目录
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python app.py
```

浏览器打开：`http://127.0.0.1:8000`

之后可以直接双击 `启动Expatus.bat`。

### 本地测试账号

- 邮箱：`demo@expatus.test`
- 密码：`expatus123`
- 如果本地没有配置 SMTP，邮箱验证码会打印到启动服务器的命令行中；demo 邮箱验证码固定为 `123456`。

## 正式上线前必须改

1. `.env` 中换掉 `SECRET_KEY`。
2. 设置 `COOKIE_SECURE=1`、`FLASK_DEBUG=0`、`DEMO_MODE=0`、`DEV_SHOW_VERIFICATION_CODE=0`。
3. 配置真实 SMTP；验证邮件才会真正发送。
4. 确认服务器持久化保存 `data/expatus.db`，不要让每次部署覆盖数据库。
5. 推荐生产环境由反向代理 + Gunicorn 运行，而不是直接使用 Flask debug server。

## 今天已实现

- **首页**：按今天锁定的新版视觉和内容；收费包隐藏；平台数据清洗；城市指南 Banner；合同/入住 PDF 下载。
- **首页 SEO**：尽量保持当前线上主页的 title、description、keywords、canonical、OG、Twitter 和 WebSite 结构化数据不变；同时保留原域名 `/`，避免无必要的 SEO 迁移。
- **Google Analytics**：沿用线上已有的 `G-FZPQP950J0`，统一加载到所有页面。
- **注册/登录**：邮箱 + 密码；注册邮箱 6 位验证码；验证码 10 分钟；60 秒重发；密码至少 8 位；30 天登录状态；忘记密码流程；异步按钮状态。
- **我的进度**：待处理 → 已表达意向 → 准备申请材料 → 已提交申请 → 已签约；非等距进度 0/20/45/75/100；状态可直接跳转；异步保存；编辑；停止跟进及原因；恢复；删除；已结束默认展开。
- **我的收藏**：独立页面，登录后云端保存。
- **莱顿页**：渠道分类、交易风险、SCIS/SUWB、综合租房说明、通勤地图、住房/大学/车站地图；最终 SEO 标题与描述已加入。
- **退租押金页**：最终锁定内容与视觉；法律依据链接；Huurcommissie / Juridisch Loket / Municipality / 律师 / Kantonrechter 路径；匿名问题收集表单异步写入 SQLite。
- **问题后台**：设置 `.env` 中的 `ADMIN_PASSWORD` 后，访问 `/admin/cases` 查看用户提交；后台可直接导出 CSV。原来的 `python scripts/export_cases.py` 仍可离线导出 `data/case_submissions.csv`。

## SEO 路由

公开并进入 sitemap：

- `/`
- `/city/leiden`
- `/deposit-return-netherlands.html`

私人页面使用 `noindex`：

- `/auth`
- `/progress`
- `/favorites`

同时保留 301 兼容入口：`/index.html`、`/account-login.html`、`/my-rental-progress.html`、`/leiden-rental-guide.html`、`/deposit-return-netherlands/`。

## PDF 下载

- `/downloads/contract-checklist.pdf`
- `/downloads/move-in-checklist.pdf`

## 数据库

SQLite 默认：`data/expatus.db`。首次运行自动建表；如果使用之前 v0.1 的本地数据库，会尝试做轻量字段兼容和旧进度状态迁移。


## v0.3 补充

### 查看用户提交的问题

用户提交的数据保存在 `data/expatus.db` 的 `case_submissions` 表中。

推荐方式：

1. 在 `.env` 中设置一个强密码：
   `ADMIN_PASSWORD=你自己的长密码`
2. 重启 Expatus。
3. 浏览器打开：`http://127.0.0.1:8000/admin/cases`
4. 输入后台密码后即可查看提交，并可点“导出 CSV”。

如果 `ADMIN_PASSWORD` 留空，整个 `/admin` 后台会自动禁用（返回 404），避免误上线一个默认密码。

### 为什么本地注册没有收到邮件？

当前 `.env.example` 默认是开发模式：

- `SMTP_HOST=` 为空：不会真正发邮件；
- 验证码会打印在启动 Flask 的命令行；
- `DEV_SHOW_VERIFICATION_CODE=1` 时，页面也会显示“本地开发验证码”。

正式上线前需要配置真实 SMTP，并设：

- `DEMO_MODE=0`
- `DEV_SHOW_VERIFICATION_CODE=0`

### 首页 v0.3

可见 H1 改为“荷兰租房导航站”，删除 Hero 下方说明句；SEO 的 `<title>`、description、canonical、OG、结构化数据和现有 GA4 ID 保持不变。Hero 与“你现在走到哪一步？”之间的空白也已缩小。

### 升级时不要丢数据库

如果你已经在 v0.2 本地测试并产生了账号、进度或问题提交，升级到新目录时请把旧目录的 `data/expatus.db` 复制到新目录的 `data/expatus.db`。正式服务器同样必须把该数据库放在持久化存储中。


## v0.4：联系我们

公开页面：`/contact`

- 不要求登录；
- 不要求姓名；
- 可选择留言类型；
- 留言内容必填；
- 邮箱和微信仅在希望收到回复时选填；
- 数据保存到 SQLite 的 `contact_messages` 表；
- 每个浏览器会话每小时最多提交 5 条，作为轻量防滥用。

后台设置 `ADMIN_PASSWORD` 后：

- `/admin/cases`：退租押金 / 租房费用问题
- `/admin/messages`：联系我们页面留言

两个后台页面都支持 CSV 导出。


## v0.4.1 后台访问修复

如果没有设置 `ADMIN_PASSWORD`：

- 现在访问 `/admin/messages` 或 `/admin/cases` 会跳到 `/admin/login`；
- 登录页会明确提示如何配置后台密码；
- 不再返回容易误解的 404“页面不存在”。

配置方式：

```env
ADMIN_PASSWORD=你自己的后台密码
```

修改 `.env` 后必须重启 Flask。


## v0.5 Turso / Vercel

This version automatically selects the database backend:

- If `TURSO_DATABASE_URL` and `TURSO_AUTH_TOKEN` exist: use the remote Turso database.
- Otherwise: continue using local `data/expatus.db` for development.

On Vercel, the Turso Marketplace integration injects the two Turso variables automatically.

Important production variables:
- `TURSO_DATABASE_URL`
- `TURSO_AUTH_TOKEN`
- `SECRET_KEY`
- `ADMIN_PASSWORD`
- Gmail SMTP variables
- `DEMO_MODE=0`
- `DEV_SHOW_VERIFICATION_CODE=0`
- `COOKIE_SECURE=1`
- `FLASK_DEBUG=0`

The database schema is initialized lazily on the first request instead of writing to the filesystem while Vercel imports `app.py`.
