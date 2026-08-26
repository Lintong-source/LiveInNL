# Expatus v1.3.0 发布清单

- 产品版本：1.3.0
- 发布类型：Production Release Candidate
- 主域名：https://www.expatus.nl
- 应用入口：`app.py` / `wsgi.py`
- 数据库：Turso，SQLite 仅用于本地回归测试
- 页面、文案、视觉与策略规则：与锁定的 v1.3 本地测试版一致
- 生产依赖：已统一到根目录 `requirements.txt`
- Windows 时区依赖：`requirements.txt` 会自动安装 `tzdata`
- Vercel Turso：兼容现有 `expatus_TURSO_*` 集成变量，无需复制 Token
- 发布阶段：免费、非商业公开测试版；转为商业服务前重新评估 Vercel/Turso 计划与 DPA
- 生产环境文件：只提供空白模板，不包含真实凭据
- 本地数据库、`.env`、虚拟环境和测试数据：不包含

## 发布门槛

- [ ] Turso 正式数据库已备份
- [ ] Turso 副本迁移已通过
- [ ] SMTP 已通过真实邮箱测试
- [ ] 隐私声明真实信息已确认
- [ ] Vercel Production 环境变量已通过 preflight
- [ ] Preview 端到端测试已通过
- [ ] www/apex 重定向已验证
- [ ] Google/Bing sitemap 已更新
- [ ] GA 内部流量与同意流程已验证
- [ ] 旧 Vercel Deployment 和回滚路径已保留
