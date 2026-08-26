# Expatus CSS 架构与复用规范

本版本把全部本地 CSS 从 HTML 中移出。16 个前台 HTML 页面和管理后台均只加载对应的独立页面入口文件：

```text
static/css/
├── src/                  唯一需要人工维护的源码
│   ├── core/             全站基础、文章基础、整合层和小型工具类
│   ├── components/       可复用组件
│   │   ├── primitives.css
│   │   └── privacy-and-account.css
│   └── pages/
│       ├── index.css     每个 HTML 对应一个源码入口
│       └── _partials/    仅该页面使用的既有样式
└── dist/                 构建生成；HTML 实际加载的一页一包 CSS
```

Leaflet 是唯一的第三方样式依赖，仍由莱顿页单独加载；其它页面只加载自己的 `dist/*.css`。

## 加载规则

每个 `src/pages/*.css` 只负责声明依赖顺序，不直接堆放大段规则。当前顺序保留了重构前的 cascade，因此不要随意调整：

1. `components/primitives.css`：低优先级公共组件；
2. `core/` 或页面 `_partials/`：原页面基础与页面规则；
3. `core/runtime-guard.css`：首屏隐藏保护；
4. `core/integration.css`：全站导航、字体、响应式整合；
5. `core/utilities.css`：明确的小型覆盖规则。

账户菜单、隐私确认及可选 Cookie 同意控件统一由 `components/privacy-and-account.css` 提供。后台和隐私声明增加了独立页面入口，不会把管理后台规则泄漏到前台文章页面。

渠道页、策略页和 Plan B 原本重复的 19KB 基础规则已抽到 `core/article-foundation.css`；渠道、策略、材料和 Plan B 第二阶段重复的视觉规则另抽到 `core/article-refinement-foundation.css`。

## 类名规范

- 公共组件：`expatus-{component}`。
- 组件元素：`expatus-{component}__element`。
- 组件变体：`expatus-{component}--modifier`。
- 页面专用规则：应放在对应 `_partials/` 中；新增选择器建议以 `body.page-{page-name}` 开头。
- JavaScript 状态：使用 `is-*`、`has-*` 或 `data-*`，不要把业务状态伪装成视觉组件名。
- 不使用新的无语义缩写，也不要新增全局 `.card2`、`.box-new`、`.green-panel` 等名字。

## 公共组件

`components/primitives.css` 提供：

- `.expatus-panel`：面板基础；
- `.expatus-notice` 及 `--warm`、`--danger`：提示框；
- `.expatus-table`：表格 / 表格型列表外框；
- `.expatus-field`、`.expatus-input`、`.expatus-select`、`.expatus-textarea`：表单；
- `.expatus-button` 及 `--secondary`：按钮；
- `.expatus-related-*`：相关文章 / 继续浏览；
- `.expatus-action-row`：水平操作区。

现有页面同时保留旧类名和公共组件类名，是为了不改变已经确认的视觉。后续重做某个组件时，应优先调整 `src/components/primitives.css`，再逐步删除该页面 partial 中已被替代的旧规则，不要重新复制一套。

## 编码规则

1. HTML 中禁止 `<style>` 和 `style="..."`。
2. 每个 HTML 只加载自己的一个 `dist/` CSS；不要直接链接 `src/`。
3. 颜色、圆角、边框和阴影优先使用 `primitives.css` 中的 `--expatus-*` token。
4. 共享规则不得写入页面 partial；页面特殊规则不得写入 `core/`。
5. 不用 `!important` 解决普通优先级问题；仅旧版兼容层和明确 utility 可以保留。
6. 响应式断点放在所属组件或页面模块中，禁止在 HTML 中临时覆盖。
7. 动态图表的高度和颜色由 JavaScript 设置运行时值，结构模板本身不再生成 `style` 属性。
8. `dist/` 禁止手工修改；任何 CSS 改动都应修改 `src/` 后重新构建。

## 修改后检查

在页面包根目录先构建，再检查：

```bash
python tools/build_css.py
python tools/check_project.py
python -m unittest discover -s tests -v
```

构建器会解析本地模块、自动修正图片相对路径并生成 17 个页面包。工程检查器会验证 HTML/CSS 分离、构建产物、主域名、禁用统计与本地数据库安全默认值；自动化测试还会覆盖隐私声明、账号、策略和后台功能。
