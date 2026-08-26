# 上线前隐私、域名和运行检查

本文件是下一阶段的核对单；当前交付仍然仅用于本地测试。隐私声明是工程落地模板，不能代替针对实际运营主体和数据处理方式的法律审核。

## 免费测试阶段说明

- 当前版本按免费、非商业公开测试服务发布。
- Vercel Hobby 与 Turso Free 未提供与付费计划相同的 DPA 获取范围；不得在对外文案中声称已签齐商业级处理者协议。
- 开始收费、接入广告、推广付费服务或扩大个人数据处理前，重新评估并升级计划或迁移服务商。
- Vercel Team Settings → Data Preferences 中应关闭模型训练与第三方模型共享。

## 正式上线前必须确认

1. 将 `PRIVACY_CONTROLLER_NAME` 替换为网站真实运营者或公司名称；不要继续使用“Expatus 网站运营者”。
2. 将 `PRIVACY_CONTACT_EMAIL` 改成真实能够收件、有人负责处理数据请求的邮箱。
3. 核实运营主体所在国家，以及实际 Vercel 部署区域、实际 Turso 数据库区域。
4. 核实 Vercel、Turso、邮件供应商和 Google 的数据处理条款；如涉及欧洲经济区以外传输，确认适用的数据传输保障措施。
5. 确认注册邮箱用途仅包括验证、登录、找回密码和必要账户通知；不能默认添加营销邮件。
6. 检查联系表单是否真的需要微信、邮箱和问题细节；确保可选字段保持可选，不要求上传证件、BSN、工资单或合同。
7. 根据真实需要确定日志、策略记录与留言保留期限，并为 `tools/purge_expired_data.py --apply` 建立可靠的定期运行方式。
8. 用真实用户流程验证：不勾选“已阅读隐私声明”不能完成新注册；拒绝分析 Cookie 仍可正常注册和使用全部工作台功能。
9. 为旧用户验证：首次登录提示阅读新版隐私声明，确认时间与版本可在后台查到。
10. 核实个人数据导出与账户删除可以使用；确认收到隐私请求后有人处理。

## 域名与搜索引擎

1. 在 Vercel 的项目域名中把 `www.expatus.nl` 设置为正式主域名。
2. 将 `expatus.nl` 指向同一项目，并永久跳转到 `https://www.expatus.nl`；同时保留 HTTPS。
3. 设置 `BASE_URL=https://www.expatus.nl` 与 `ENFORCE_CANONICAL_HOST=1`。
4. 检查首页、城市页、攻略页、材料页和押金页的 canonical 均为 `https://www.expatus.nl/...`。
5. 检查 `https://www.expatus.nl/robots.txt` 指向 `https://www.expatus.nl/sitemap.xml`。
6. 在 Google Search Console 提交 www 域名下的 sitemap；检查旧 apex 地址和旧 `.html` 地址均为单跳永久重定向。
7. 不要把 `/admin`、`/auth`、`/workspace`、`/progress`、`/favorites` 或 `/api` 放入站点地图。

## Google Analytics

- 本地及预发布环境保持 `ANALYTICS_ENABLED=0`。
- 仅在正式环境确定需要访问分析后，才设置 `ANALYTICS_ENABLED=1` 和正确的 `GA_MEASUREMENT_ID`。
- 用户没有主动允许分析前，浏览器不请求 Google Analytics 脚本，也不授予分析存储权限。
- 管理后台和已打开后台会话不加载分析脚本，避免维护与测试访问混入。
- 在 GA4 管理界面另外设置内部流量 / 开发流量过滤器，作为生产环境的第二层保护。
- 已经产生的历史测试数据不能靠本地代码追溯性清除；需要在 GA4 报表、过滤配置或数据管理功能中单独处理。

## 正式环境配置：本次不要执行

- 使用高强度且独立的 `SECRET_KEY`、后台密码、SMTP 密码和 Turso 凭据。
- 正式环境关闭 `DEMO_MODE`、`DEV_SHOW_VERIFICATION_CODE` 和 Flask 调试模式。
- 启用 HTTPS Cookie，并确认邮件验证码通过真实 SMTP 投递。
- 连接 Turso 前先备份正式数据库，在副本上演练增量迁移和完整登录/找房流程。
- 不提交 `.env`、SQLite 数据库、凭据、虚拟环境或测试账号数据。

## 参考资料

- European Commission, data protection obligations: <https://commission.europa.eu/law/law-topic/data-protection/information-business-and-organisations/obligations_en>
- European Data Protection Board, data protection basics: <https://www.edpb.europa.eu/sme/learn-the-basics/data-protection-basics_en>
- Google, consent mode: <https://developers.google.com/tag-platform/security/guides/consent>
- Google Search Central, canonicalization: <https://developers.google.com/search/docs/crawling-indexing/canonicalization>
- Google Analytics, data filters: <https://support.google.com/analytics/answer/13296761?hl=en>
