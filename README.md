# Expatus v1.3.0 Production Release

这是 Expatus v1.3 的正式发布源码包。页面、文案、样式与策略规则已经冻结；本包相对本地测试版只增加生产依赖、生产配置模板、部署校验与运维文档。

> 不要直接把压缩包中的占位配置用于生产。部署前必须完成 `docs/PRODUCTION-DEPLOYMENT.md`。

## 技术结构

- Flask 应用工厂：`expatus/__init__.py`
- HTTP 控制器：`expatus/controllers/`
- 数据访问：`expatus/repositories/`
- 业务服务：`expatus/services/`
- 后端策略引擎：`expatus/services/strategy_engine.py`
- Turso/SQLite 兼容与增量迁移：`expatus/database.py`
- 页面模板：`templates/`
- CSS 源码：`static/css/src/`
- CSS 构建产物：`static/css/dist/`

## 生产部署前

1. 将代码提交到 GitHub 发布分支。
2. 将 `.env.example` 中的变量逐项配置到 Vercel Production。
3. 运行不读取或输出密钥的配置检查：

```bash
python tools/production_preflight.py
```

4. 备份正式 Turso 数据库，在副本上演练增量迁移。
5. 验证 SMTP 注册、登录、重置密码、数据导出、账户删除和后台。
6. 按 `docs/PRODUCTION-DEPLOYMENT.md` 完成 Preview、Production 和回滚准备。

## 本地回归测试

复制开发模板后运行：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.development.example .env
python tools/build_css.py
python -m unittest discover -s tests -v
python tools/check_project.py
python app.py
```

访问 `http://127.0.0.1:8000`。

## 数据迁移原则

应用启动时只执行增量建表、加列和旧状态名称映射，不主动删除账户或房源。即使如此，也不能把第一次迁移直接作用于唯一一份正式数据库；必须先在 Turso 副本上演练并保留回滚备份。

## 数据清理

默认预览，不删除：

```bash
python tools/purge_expired_data.py
```

确认目标和数量后才执行：

```bash
python tools/purge_expired_data.py --apply
```

## 版本

- 产品版本：`1.3.0`
- 策略引擎：`strategy-v2-backend-2026-08-26`
- 主域名：`https://www.expatus.nl`
- 默认生产数据库：Turso
- 正式环境默认 GA：关闭，完成同意与过滤器验证后再开启
