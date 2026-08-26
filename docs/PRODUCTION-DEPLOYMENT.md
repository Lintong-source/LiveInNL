# Expatus v1.3 正式部署手册

本手册只处理发布，不改变已经冻结的 v1.3 功能、页面、文案、样式或策略规则。

## 一、发布前冻结

1. 将本目录提交到发布分支。
2. 创建候选标签，例如 `v1.3.0-rc1`。
3. 保存当前线上 Git commit、Vercel Deployment URL 和环境变量名称清单。
4. 不把 `.env`、数据库、令牌、SMTP 密码或虚拟环境提交到 Git。

## 二、Turso 备份与副本演练

1. 使用 Turso 控制台或 CLI 导出当前正式数据库备份。
2. 从正式数据建立一个临时副本，或将备份恢复到独立测试数据库。
3. 为本地终端配置生产模式，但把 `TURSO_DATABASE_URL` 和令牌指向副本。
4. 运行 `python tools/production_preflight.py`。
5. 只对副本启动一次应用，让增量迁移执行：`python -c "from expatus import create_app; create_app(); print('migration complete')"`。
6. 在副本验证旧用户、登录、收藏、房源、策略、留言和后台统计。
7. 迁移演练完成后不要把副本凭据带入正式环境。

应用迁移采用建表、加列和旧状态名称映射，不主动删除账户或房源。正式数据库仍必须有上线前备份。

## 三、Vercel 环境变量

以 `.env.example` 为清单，在 Vercel 的 Production 环境逐项填写。敏感值不要放在仓库或部署说明中。

必须确认：

- `APP_ENV=production`
- `DATABASE_BACKEND=turso`
- `BASE_URL=https://www.expatus.nl`
- `ENFORCE_CANONICAL_HOST=1`
- `COOKIE_SECURE=1`
- `DEMO_MODE=0`
- `DEV_SHOW_VERIFICATION_CODE=0`
- `FLASK_DEBUG=0`
- 独立随机的 `SECRET_KEY` 与 `ADMIN_PASSWORD`
- 正式 Turso 和 SMTP 凭据
- 真实隐私控制者、联系邮箱及基础设施区域

Turso 凭据既支持标准名称 `TURSO_DATABASE_URL` / `TURSO_AUTH_TOKEN`，也支持
Vercel Marketplace 当前生成的 `expatus_TURSO_DATABASE_URL` /
`expatus_TURSO_AUTH_TOKEN`。标准名称存在时优先使用，不需要复制集成管理的 Token。

初次部署保持 `ANALYTICS_ENABLED=0`，生产冒烟测试完成后再决定是否开启。

## 四、Preview 验证

Preview 必须使用独立的 Turso 副本，不得连接正式数据库，也不得发送正式 GA 数据。环境变量可参考 `.env.preview.example`：使用 `APP_ENV=staging`、关闭规范域名强制跳转并保持安全 Cookie；否则 Preview 域名会被生产 www 跳转规则挡住。

验证：

1. 首页和全部公开页面返回 200。
2. 未登录不能访问工作台、进度、收藏、账户数据和后台。
3. 邮箱注册、验证码、登录、退出和密码重置正常。
4. 收藏、房源增删改、状态回退和策略重新计算正常。
5. 个人数据 ZIP 可以打开，账户删除会清理关联数据。
6. 正常留言可以提交，垃圾信息和过度提交会被拦截。
7. 后台可以查看用户、登录、安全事件、策略和留言。
8. 拒绝分析 Cookie 不影响功能，并且不会请求 GA 脚本。

## 五、Production 部署

1. 确认正式 Turso 备份完成。
2. 确认生产环境变量通过 preflight。
3. 在访问量较低时部署 Production。
4. 不要立即删除旧 Vercel Deployment。
5. 使用新建真实测试账户完成一次端到端流程，完成后删除该账户。

## 六、域名与 SEO 验证

逐项检查：

- `https://www.expatus.nl/` 返回 200。
- `https://expatus.nl/任意路径?参数` 单次 301 到同路径的 www URL，并保留查询参数。
- canonical、robots 和 sitemap 全部使用 www。
- 旧 `.html` 地址只跳转一次到当前规范地址。
- `/admin`、`/auth`、`/workspace`、`/progress`、`/favorites` 与 API 不进入 sitemap。
- Google Search Console 和 Bing Webmaster Tools 提交 `https://www.expatus.nl/sitemap.xml`。

## 七、GA 启用

完成生产功能验证后：

1. 确认 GA Measurement ID。
2. 配置内部或开发流量过滤器。
3. 设置适当的数据保留期限。
4. 设置 `ANALYTICS_ENABLED=1` 并重新部署。
5. 拒绝 Cookie 时确认没有 GA 请求；同意后确认 Realtime 出现访问。

## 八、数据清理

至少每月运行一次：

```bash
python tools/purge_expired_data.py
python tools/purge_expired_data.py --apply
```

第一次始终先看预览数量。执行环境必须使用正式 Turso 凭据，不要在 Vercel 请求处理中运行批量清理。

## 九、回滚条件

出现以下任一情况立即回滚应用，并保留日志：

- 大量 500 错误；
- 无法登录或发送验证码；
- 用户数据跨账户显示；
- 正式数据库迁移异常；
- apex/www 重定向循环；
- 未经同意加载 GA；
- 数据导出或账户删除访问了错误账户。

回滚顺序：将 Vercel 指向旧的稳定 Deployment；停止继续操作数据库；保留错误日志；根据影响决定是否从备份恢复。数据库恢复属于单独的高风险操作，不能仅因为应用回滚就自动覆盖正式数据。
