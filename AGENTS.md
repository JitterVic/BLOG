# Repository Guidelines & Architecture Standards

本项目为基于 Flask + Vue 3 的报刊排版风格个人博客。本文档为开发人员及 AI 编码助手提供代码架构、开发约束、设计原则与质量把控基准。

---

## 1. 架构分层与职责边界

### 后端分层架构 (`backend/src/blog/`)

后端采用标准 Python src-layout 结构，严格执行分层设计与单一职责原则：

1. **路由层 (`routes/`)**：
   - `public.py`：公开数据接口（`/api/site`, `/api/posts`, `/api/posts/<slug>`, `/api/health`）。
   - `feed.py`：动态生成 `/feed.xml`（Atom）、`/sitemap.xml` 与 `/robots.txt`。
   - `spa.py`：SPA 单页应用托管与基于路由的 Open Graph 动态注入。
   - `admin_auth.py` / `admin_pages.py` / `admin_posts.py` / `admin_api.py`：管理后台登录、页面渲染、稿件操作及 AJAX 交互接口。
   - 职责范围：仅负责 HTTP 请求解析、权限拦截、响应封装，不包含直接 SQL 操作或复杂业务逻辑。

2. **服务层 (`services/`)**：
   - `post_service.py`：文章生命周期管理（草稿、发布、版本快照、自动清理、Slug 唯一性算法）。
   - `media_service.py`：素材上传处理、图片尺寸约束与文章引用关联追踪。
   - `profile_service.py`：站点全局配置管理。
   - `dashboard_service.py`：仪表盘统计数据聚合与健康度分析。
   - `import_service.py`：Markdown/Frontmatter 内容解析与导入转换。

3. **仓储层 (`repository/`)**：
   - `database.py`：SQLite 连接池（WAL 模式）、建表与幂等增量迁移机制。
   - `posts.py` / `revisions.py` / `profile.py` / `media.py`：纯 SQL 数据访问层，负责底层数据持久化与 JSON 字段编解码。

4. **工具与基建层**：
   - `markdown_tools/`：Markdown 扩展渲染、`SafeHTMLCleaner` XSS 消毒与正文统计指标计算。
   - `seo.py`：Atom feed / sitemap / robots.txt 生成与 SPA 页面的 meta、OG、canonical 注入。
   - `security.py`：基于 HMAC 的 Session 鉴权、CSRF 防护、防爆破登录限流（`BLOG_TRUSTED_PROXY_COUNT`）。
   - `login_throttle.py`：登录失败计数落库（多 worker 下不能放在进程内存）。
   - `uploads.py`：图片类型校验与 Pillow 内存安全压缩。
   - `taxonomy.py`：栏目（大类）固定词表——前台唯一的粗粒度筛选维度。
   - `serializers.py` / `validation.py` / `env_loader.py` / `config.py`：载荷裁剪、字段长度校验、环境变量解析、启动配置与生产就绪校验。
   - `store.py`：门面层（`BlogStore`）与依赖装配入口，为历史代码提供向下兼容的统一委托。

### 后端性能约定（改动前请先量，别凭直觉）

以下几条都是实测出来的，乱改会让接口明显变慢：

- **`journal_mode` 不做逐连接设置**：`Database.connect()` 只在每个实例的首次连接（以及 `init()`）设置 `PRAGMA journal_mode = WAL`。它是写进数据库文件的持久属性，实测带这条 PRAGMA 的连接 0.93ms、不带 0.13ms，连「只读回 journal_mode」都要 0.91ms；而一次请求要开 2~4 条连接。
- **两条索引别删**：`idx_posts_hot`（前台首页热点排序，计划从临时 B 树排序变为覆盖索引）与 `idx_posts_status_tags`（标签词表的覆盖索引，避免为取一列 tags 把每篇整行连正文一起读出来）。400 篇实测：`/api/posts?sort=hot` 2.42 → 1.49ms，`/api/site` 6.08 → 3.64ms。
- **标签词表在 SQL 侧聚合，且只认「数组里的字符串」**：用 `json_each` 的 `type` 列判断类型，不要用 `json_type(value)` —— json_each 的 `value` 已是解码后的原生值，字符串元素本身不是合法 JSON 文档，`json_type('python')` 会抛 `malformed JSON`；未校验的脏 `tags`（`"null"`、`[broken`）直接喂给 `json_each` 同样会抛，必须用 `json_valid` + `json_type(...)='array'` 的嵌套 CASE 兜住。旧实现里 `list_taxonomy` 遇到 `tags="null"` 会 `for item in None` 直接 500。
- **`validate_post_for_publish(include_normalized=False)`**：后台总览逐篇调用它只为拿 errors / warnings，而 `normalized` 里的 slug / 摘要 / 阅读时长要在每篇正文上再跑 8 次正则。改动前 400 篇干净库的后台总览是 39.5ms，跳过之后 32.3ms；再叠上「收满 `limit` 就停止验证」，默认库从 39.0ms 降到 22.0ms。
- **先建基线再优化**：`output/perf/bench_backend.py`（合成库 + 接口计时）、`bench_admin.py`（后台页面计时）、`ab_dashboard.py` / `ab_endpoints.py`（交替取样 A/B，抵消这台机器上的漂移）。这台机器上顺序测量与交替测量能差出一倍，别用单次计时下结论。

### 内容分类的三层约定

- **栏目（`category`）**：前台唯一允许的筛选维度，取值限定为 `taxonomy.CATEGORY_PRESETS`（算法 / 工程 / 教学 / 项目 / 随想 / 读书）。后台是下拉选择，发布预检会拒绝词表以外的值——放开自由录入，筛选条迟早会退化成第二个标签云。
- **标签（`tags`）**：自由词表，只做展示与检索，不做前台筛选。
- **关键词（`keywords`）**：别名、同义词、英文写法，只参与站内搜索，**不出现在任何对外载荷**（列表、站点载荷、文章详情都不含）。

### 前端架构 (`frontend/src/`)

- **状态管理**：采用单例 Composables 模式（如 `useSite.js`, `usePosts.js`, `usePost.js`），在模块作用域持有响应式状态并去重并发请求，不引入额外的状态管理库（Pinia/Vuex）。
- **组件划分**：按业务模块拆分子目录（`components/home/`, `components/post/`, `components/posts/`, `components/pet/`），通用 UI 组件平铺于 `components/`。
- **文章阅读页（`/posts/:slug`）**：阅读版式是**视口级对称三轨网格**（`.post-reading-layout` = `1fr / 760px / 1fr`，区域 `rail article toc`），正文因此恒定居中且宽度不随侧栏开合变化。左轨是**可切换范围**的编年索引（`components/post/PostRail.vue`，范围 = 本栏目 / 全站最新 / 其它栏目，选项收进表头那一个词的位置，避免左栏变成第二个筛选条；数据由 `composables/usePostRail.js` 做成模块级单例缓存，范围是读者选择的状态，换篇之间保持）。右轨是章节目录（`PostToc.vue`）；两者都可折叠成竖排书脊并记住偏好（书脊上只留箭头与竖排名称，不挂数字）。侧栏只在 ≥1440px 存在，**绝对定位**，吸附前贴在各自网格区域顶端随正文滚，越过吸附线后由 `.is-pinned` 换成 `position: fixed` 钉住；可用高度与吸附线由 `composables/usePanelPin.js` 给出。**既不能用 `position: sticky`**（区域高度由正文决定，短文下会把面板连同收起按钮一起顶出屏幕），**也不能每帧在绝对定位的面板上写 `top`**（DOM 改写永远晚于滚动一帧，面板会一直抖——实测 55px/帧 滚动时面板顶部稳定落后 55px）。面板宽度用三道 `min()` 夹取（设计宽度 / 轨道宽 − 间隙 / 版面框外侧留白 − 边缘余量 − 呼吸带），同时阅读页的版面框本身在 ≥1281px 收窄为 `min(1180px, max(800px, 100vw - 40rem))` 并把外侧留白暴露成 `--post-outer-margin`——1180px 的框要 1888px 以上的视口才容得下两侧面板，否则面板会压过框线。收起箭头朝外、展开箭头朝内，因此 `post.css` 里只允许存在一处 `rotate(180deg)`（左栏书脊）。
- **文章目录页（`/posts`）**：单一形态——按年份分组的编年索引（`components/posts/ArchiveLedger.vue`），配 `PostsToolbox.vue` 的栏目筛选与搜索。索引行 = 日期 / 标题 + 摘要 / 时长 + 标签；筛选走服务端 `category` 参数，因此筛选与翻页可以并存。标签不参与筛选（标签是自由词表，做成筛选维度就会长成第二个标签云），因此文章页的标签链接走检索维度 `?q=`。`/api/posts` **只有一种载荷形状**：永远返回 `{items, total, page, per_page, has_more}`，缺省即 `page=1`（不带 `page` 时 `per_page` 上限 50），不再有裸数组分支。
- **样式体系**：基于原生 CSS 变量构建 `styles/editorial.css`，聚合 12 个按层叠顺序加载的主题模块（reset, tokens, layout, typography, components, print 等）。

### 后台管理面板 (`templates/` + `static/admin/`)

- **与前台同源的主题**：设计令牌集中在 `static/admin/css/theme.css`（纸色 `--paper: #f6f1e8`、墨色、栏线、字体栈、缓动、`--ring-focus`），取值必须与 `frontend/src/styles/base.css` 保持一致。`base.css` 与 `login.css` 各自 `@import` 它，模板只挂各自页面的样式表。
- **字体必须真的加载**：`admin_base.html`、`admin_login.html`、`admin_preview.html` 都要引与前台相同的 Google Fonts（Playfair Display / Noto Serif SC / IBM Plex Mono）。少了这一句，中文标题掉回系统宋体、正文掉回 Consolas，前后台并排就不像同一家刊物。
- **半透明纸面用 RGB 令牌**：写成 `rgb(var(--paper-rgb) / 0.9)`，不要散落 `rgba(244, 239, 230, .9)` 这类字面量——否则改 `--paper` 时那几十处仍旧是旧纸色。
- **后台页面一律 `noindex, nofollow`**：`robots.txt` 故意不列出后台路径（避免泄漏前缀），因此收录控制只能落在页面自身的 meta 上。
- **登录页是独立页面**：`admin_login.html` 不继承 `admin_base.html`（登录前没有导航可挂），但必须共用 `theme.css` 的纸面与字体，禁止再引入第二套配色。

---

## 2. 编码规范与命名约定

- **Python**：
  - 遵循 PEP 8，4 空格缩进。
  - 文件路径处理统一采用 `pathlib.Path`。
  - 函数与方法保持精简，类型提示与异常处理明确。
- **Vue & JavaScript**：
  - Vue 3 组件统一采用 `<script setup>` 语法，2 空格缩进。
  - 组件文件名使用 PascalCase（如 `PostCard.vue`, `CatPet.vue`）。
  - JavaScript 变量、函数与 Composable 使用 camelCase（如 `useTableOfContents.js`, `formatDate`）。
- **持久化与数据规范**：
  - Markdown 正文为**唯一真实数据源**（Source of Truth），读取文章时统一动态渲染与消毒。
  - 数据库增量字段使用 `_migrate_schema` 中的 `PRAGMA table_info` 校验后执行 `ALTER TABLE ADD COLUMN`，保持幂等性。

---

## 3. 安全防护与边界约束

1. **XSS 消毒边界**：所有 Markdown 渲染产物必须经过 `SafeHTMLCleaner` 标签与属性白名单清洗后方可存储或输出。
2. **上传路径隔离**：上传资源只允许保存至 `storage/media/`（及历史 `storage/avatars/`），通过 `/uploads/<path>` 提供访问前必须通过 `is_allowed_public_upload_path` 路径白名单拦截。
3. **代理与限流安全**：Nginx 等反向代理环境下必须配置 `BLOG_TRUSTED_PROXY_COUNT=1`，确保客户端真实 IP 取自可信的 `X-Forwarded-For` 节点，防止限流绕过。
4. **生产环境强拦截**：`BLOG_DEBUG=false` 时，若检测到默认密钥、默认弱密码或默认后台路径，后端将强制终止启动。

---

## 4. 构建、测试与验证基准

- **依赖同步**：
  - 后端：`uv sync --directory backend --group dev --group prod`
  - 前端：`cd frontend && npm install`
- **本地服务启动**：
  - 后端：`backend/.venv/bin/python -m blog`（Windows: `.\backend\.venv\Scripts\python.exe -m blog`）
  - 前端：`cd frontend && npm run dev`
  - 一键启动：`.\scripts\dev.ps1`
- **自动化测试**：
  - 执行指令：`backend/.venv/bin/python -m pytest backend/tests -q -p no:cacheprovider --basetemp=.tmp/pytest`
- **静态构建**：
  - 执行指令：`cd frontend && npm run build`（产物输出至 `frontend/dist/`）
- **一键发布验证**：
  - Windows 环境：`powershell -ExecutionPolicy Bypass -File .\scripts\verify.ps1 -StrictLaunch`

---

## 5. 提交与变更规范

- **Git Commit**：使用祈使语态的简明中文摘要。
- **Pull Request**：包含改动摘要、相关 issue 索引、测试执行结果及 UI 改动的截图或录屏。
- **敏感信息防御**：严禁提交包含真实凭证的 `.env` 文件；持久化数据 `storage/` 严禁提交至版本控制。
