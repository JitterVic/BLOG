# 至知 Journal (Paper Notes)

> **分支方向说明**：`main` 是「报刊 · v1」版面方向的历史归档，已冻结、不再开发。
> 现行开发方向在 **`notebook`** 分支（「笔记本 · v2」：蓝黑墨水摊开的笔记本版式），
> 两条分支各自独立演化、**永不合并**。本分支以下内容按 v1 时代原样保留。

> 一份"报刊排版"的个人博客：前台是翻开的报纸，后台是同一位排字工的编辑台。

基于 **Flask 3 + Vue 3** 构建，SQLite 单文件持久化，内置单管理员内容管理后台。Markdown 是正文的唯一真实数据源，读写两侧都走同一套渲染与消毒管线。

---

## 目录

- [核心特性](#核心特性)
- [设计约定](#设计约定)
- [技术架构](#技术架构)
- [快速开始](#快速开始)
- [环境变量](#环境变量)
- [后台管理](#后台管理)
- [公开接口](#公开接口)
- [测试与构建](#测试与构建)
- [生产部署（Linux）](#生产部署linux)
- [备份与容灾](#备份与容灾)
- [安全实践规范](#安全实践规范)

---

## 核心特性

### 前台（Vue 3 SPA）

- **报刊版式**：报头封面、头条大图、热点排行，正文按"版次"分节并带页码；打印样式单独成层，屏幕与纸张两套节奏。
- **文章阅读页**：视口级对称三轨网格 —— 左轨是同栏目编年索引（范围可在「本栏目 / 全站最新 / 其它栏目」之间切换），右轨是章节目录。两轨都可折叠成竖排书脊并记住偏好，正文列恒定居中、宽度不随开合变化。
- **文章目录页**：单一形态的年份分组编年索引（日期 / 标题 + 摘要 / 时长 + 标签），配栏目筛选与站内搜索；筛选与翻页可以并存。
- **阅读增强**：实时阅读进度、目录跟随、代码高亮与一键复制、图片灯箱、相邻文章导航、相关文章推荐。
- **彩蛋**：无文字的交互式桌面宠物（单击回顶 / 长按抚摸 / 拖动换位 / 右键切换音效 / 打字时打鼓）。
- **SEO**：服务端为 SPA 外壳动态注入 Open Graph 与 canonical，另有 Atom Feed、Sitemap 与 robots.txt。

### 后台（Jinja2 编辑台）

- **四页工作流**：稿件总览（Desk）→ 文章写作（Write）→ 封面资料（Profile）→ 媒体资源（Media），顶栏常驻四页入口与稿件计数。
- **写作台**：写作 / 分栏 / 预览三种视图，Markdown 快捷工具栏，目录、文章设置、图片、版本四个抽屉。
- **状态保障**：本地草稿缓存 + 服务端自动同步 + 版本冲突检测 + 离线重试；顶栏状态点会明确区分"仅本地 / 同步中 / 已入服务端 / 出错"。
- **发布预检**：发布前逐项校验必填与风险项，点击问题项可直接跳到对应字段。
- **版本追踪**：发布、下架、回收站等关键动作自动留档，可对比任意历史版本并恢复。
- **稿件运维**：多条件筛选（标题 / slug / 栏目 / 标签 / 状态）+ 排序 + 批量操作 + 回收站（30 天自动清理）。
- **媒体库**：粘贴 / 拖拽上传、Pillow 内存安全压缩、文章引用关系追踪（可筛选"未引用"图片）。

### 数据与安全

- SQLite WAL 模式运行，启动时自动建表并做幂等增量迁移。
- **XSS 防御**：所有 Markdown 渲染产物经 `SafeHTMLCleaner` 白名单消毒后才入库 / 出库。
- **上传边界**：图片类型与像素上限校验，`/uploads/<path>` 必须先通过路径白名单。
- **访问控制**：可自定义后台路径、基于 HMAC 的会话鉴权、CSRF 校验、登录失败限流与审计日志。
- **生产强校验**：`BLOG_DEBUG=false` 时，默认密钥 / 弱密码 / 默认后台路径会直接阻断启动。

---

## 设计约定

### 分类只有三层，且各有边界

| 层 | 字段 | 可枚举 | 前台筛选 | 对外可见 |
|---|---|---|---|---|
| 栏目 | `category` | 是（`taxonomy.CATEGORY_PRESETS`：算法 / 工程 / 教学 / 项目 / 随想 / 读书） | ✅ 唯一筛选维度 | ✅ |
| 标签 | `tags` | 否，自由词表 | ❌ 只展示与检索 | ✅ |
| 关键词 | `keywords` | 否，别名与英文写法 | ❌ 只参与站内搜索 | ❌ 不出现在任何对外载荷 |

栏目是下拉选择而非自由录入，发布预检会拒绝词表以外的值：一旦允许随意填写，前台那条筛选栏迟早会退化成第二个标签云。

### 后台与前台共用一套纸面

后台不是另一个产品。`static/admin/css/theme.css` 里的设计令牌与 `frontend/src/styles/base.css` **保持同一份取值**（纸色 `--paper: #f6f1e8`、墨色、栏线、字体栈、缓动曲线），两个渲染入口各自 `@import` 它：

- 纸色与墨色分叉的后果是肉眼可见的 —— 同一张封面图在前后台会显出两种偏色。
- `admin_base.html`、`admin_login.html`、`admin_preview.html` 都必须加载与前台相同的 Google Fonts；缺了这一句，中文标题会掉回系统宋体、正文掉回 Consolas，同一屏并排就能看出不是一家刊物。
- 半透明纸面统一写成 `rgb(var(--paper-rgb) / 0.9)` 这类形式，颜色只在令牌里定义一次；散落的 `rgba(244, 239, 230, .9)` 会让"改 `--paper`"变成一句空话。

### `/api/posts` 只有一种载荷形状

永远返回 `{ items, total, page, per_page, has_more }`。不带 `page` 时按 `page=1` 处理，此时页大小缺省为 50（带 `page` 时缺省为 10），上限同为 50；不存在"有时是数组、有时是信封"的分支。

---

## 技术架构

### 技术栈

| 领域 | 选型 | 说明 |
|---|---|---|
| 前端 SPA | Vue 3 + Vue Router 4 + Vite 6 | `<script setup>`，单例 Composables 管理状态，不引入 Pinia/Vuex |
| 样式 | 原生 CSS 变量 + Editorial CSS | 12 个按层叠顺序 `@import` 的主题模块，无预处理器 |
| 后端 API | Python ≥ 3.10 / Flask 3 | 路由 → 服务 → 仓储三层，统一 JSON 响应 |
| 管理后台 | Flask + Jinja2 + 原生 ES Modules | 服务端渲染，与前台 SPA 完全解耦；主题与前台同源 |
| 数据与渲染 | SQLite 3 (WAL) + Python-Markdown + Pillow | 自定义渲染扩展、HTML 消毒、图片安全压缩 |
| 生产运行 | Gunicorn + Systemd + Nginx + Certbot | 进程守护、沙箱账号、反向代理与自动 HTTPS |

### 目录结构

```text
BLOG/
├── backend/                      # 服务端 Python 包（src-layout，uv / hatchling 管理）
│   ├── pyproject.toml
│   ├── src/blog/
│   │   ├── app.py                # 应用工厂、蓝图挂载、安全钩子、SPA 兜底
│   │   ├── config.py             # 启动配置读取与生产就绪强校验
│   │   ├── security.py           # 会话鉴权、CSRF、限流、安全响应头与审计
│   │   ├── login_throttle.py     # 登录失败计数落库（多 worker 下不能放进程内存）
│   │   ├── taxonomy.py           # 栏目固定词表
│   │   ├── seo.py                # Atom / Sitemap / robots.txt / OG 注入
│   │   ├── uploads.py            # 上传管线、路径白名单、Pillow 压缩
│   │   ├── serializers.py        # 对外载荷裁剪
│   │   ├── validation.py         # 字段长度与规则校验
│   │   ├── store.py              # BlogStore 门面与依赖装配（兼容层）
│   │   ├── routes/               # public / feed / spa / admin_auth / admin_pages / admin_posts / admin_api
│   │   ├── services/             # post / media / profile / dashboard / import
│   │   ├── repository/           # database / posts / revisions / profile / media
│   │   ├── markdown_tools/       # renderer（含 SafeHTMLCleaner）/ analysis / frontmatter
│   │   ├── templates/            # 后台 Jinja2 模板（admin_base + 四页 + partials）
│   │   └── static/admin/         # 后台静态资产
│   │       ├── css/              # theme（与前台同源令牌）/ base / login / dashboard / write / media / profile
│   │       └── js/write/         # 写作台 ES Modules（autosave / editor / preview / publish / revisions…）
│   └── tests/                    # pytest 测试套件
├── frontend/                     # 前端 Vue 3 单页应用
│   ├── vite.config.js            # 开发代理：/api 与 /uploads → :5000
│   └── src/
│       ├── components/           # home / post / posts / pet / 通用组件
│       ├── composables/          # useSite / usePosts / usePost / usePostRail / usePanelPin …
│       ├── services/             # http.js（超时与 ApiError）+ api.js
│       ├── styles/               # editorial.css 聚合 12 个主题模块
│       └── views/                # Home / Posts / Post / About / NotFound
├── deploy/                       # 生产部署与运维脚本（deploy / backup / restore + 配置模板）
├── scripts/                      # 本地开发辅助（dev.ps1 / verify.ps1 / backup.ps1 / dev_watchdog.py）
├── docs/                         # 上线核对清单与设计稿
├── storage/                      # 运行时数据：数据库与上传媒体（不入版本库）
└── output/                       # 本地排查产物与截图（不入版本库）
```

---

## 快速开始

### 环境依赖

- **Python** ≥ 3.10（推荐 [uv](https://docs.astral.sh/uv/)）
- **Node.js** ≥ 18 / npm ≥ 9

### 依赖安装

```bash
uv sync --directory backend --group dev --group prod
cd frontend && npm install
```

### 启动方式 A：一键联动（推荐，Windows）

```powershell
.\scripts\dev.ps1
```

脚本会同时拉起后端（`127.0.0.1:5000`）与前端（`127.0.0.1:5173`），并挂上看门狗：关闭终端或按 `Ctrl+C` 时两个子进程一并退出。

### 启动方式 B：手动分步

```bash
# 后端（默认 127.0.0.1:5000）
backend/.venv/bin/python -m blog
# Windows: .\backend\.venv\Scripts\python.exe -m blog

# 前端（另开终端，Vite 会把 /api 与 /uploads 代理到 5000）
cd frontend && npm run dev
```

打开 `http://127.0.0.1:5173` 查看前台；后台地址是 `BLOG_ADMIN_PREFIX`（默认 `/admin`，例如 `http://127.0.0.1:5173/admin/login`）。

> 生产模式下 Flask 直接托管 `frontend/dist/`，因此上线前必须先 `npm run build`。

---

## 环境变量

复制 `.env.example` 为 `.env` 后按需调整。相对路径按仓库根目录解析。

| 变量名 | 默认值 | 作用说明 | 生产环境要求 |
|---|---|---|---|
| `BLOG_SECRET_KEY` | `dev-secret-key-change-me` | Flask Session 签名密钥 | **必须替换**为 ≥32 位随机字符串 |
| `BLOG_ADMIN_PASSWORD` | `admin123456` | 后台登录密码 | **必须替换**为 ≥12 位强密码 |
| `BLOG_ADMIN_PREFIX` | `/admin` | 后台 URL 前缀 | **不能保留默认值**，建议换成不易猜到的路径 |
| `BLOG_HOST` / `BLOG_PORT` | `127.0.0.1` / `5000` | 内置开发服务器监听地址 | 生产由 Gunicorn 接管 |
| `BLOG_DEBUG` | `false` | 调试模式 | **必须为 `false`**（为 `true` 时跳过全部生产校验） |
| `BLOG_COOKIE_SECURE` | `false` | Session Cookie 仅走 HTTPS | HTTPS 环境**必须为 `true`** |
| `BLOG_PUBLIC_BASE_URL` | 空 | 对外根地址，用于 RSS / Sitemap / OG 绝对 URL | 生产必填，且必须 `https://` 开头 |
| `BLOG_REQUIRE_PUBLIC_BASE_URL` | `false` | 启动时强制要求上面这项非空 | 上线核验时置 `true` |
| `BLOG_TRUSTED_PROXY_COUNT` | `0` | 可信反向代理层数 | Nginx 单层反代**必须设为 `1`**（详见 `.env.example` 注释） |
| `BLOG_HSTS_MAX_AGE` | `31536000` | HSTS 有效期（秒），`0` 关闭 | 仅 `BLOG_COOKIE_SECURE=true` 时生效 |
| `BLOG_SESSION_LIFETIME_SECONDS` | `28800` | 后台会话时长 | 按需调整 |
| `BLOG_LOGIN_MAX_ATTEMPTS` | `5` | 窗口内允许的登录失败次数 | 超出后按 IP 临时锁定 |
| `BLOG_LOGIN_RATE_WINDOW_SECONDS` | `300` | 限流窗口与锁定时长 | 按需调整 |
| `BLOG_DATABASE_PATH` | `storage/blog.db` | SQLite 文件路径 | 与 `storage/` 一同纳入备份 |
| `BLOG_MAX_UPLOAD_BYTES` | `10485760` (10MB) | 请求体上限 | 需与 Nginx `client_max_body_size` 一致 |
| `BLOG_MAX_IMAGE_BYTES` | `5242880` (5MB) | 单张图片上限 | 超出直接拒绝 |
| `BLOG_MAX_IMAGE_PIXELS` | `20000000` (20MP) | 解压像素上限 | 防"像素炸弹" |

> **注意**：一旦 `BLOG_PUBLIC_BASE_URL` 填了 `https://` 域名，就必须同时设 `BLOG_COOKIE_SECURE=true`，否则启动会被拦下来。

---

## 后台管理

后台由 `BLOG_ADMIN_PREFIX` 决定入口，登录页与四个工作页共用一套报刊主题。

| 页面 | 路径 | 职责 |
|---|---|---|
| 登录 | `<prefix>/login` | 单密码入口；失败计数落库，多 worker 下同样有效 |
| 稿件总览 | `<prefix>/` | 统计、继续写作、筛选排序、批量操作、待处理与内容健康 |
| 文章写作 | `<prefix>/write[/<id>]` | 写作台：三视图 + 四抽屉（目录 / 文章设置 / 图片 / 版本） |
| 封面资料 | `<prefix>/profile` | 首页身份、联系卡片、关于页简介（带实时预览） |
| 媒体资源 | `<prefix>/media` | 浏览上传图片、复制引用、查看引用关系 |

写作台细节：

- 自动保存会同时落本地草稿与服务端；顶栏状态点区分"仅本地 / 同步中 / 已入服务端 / 出错"，失败时可点「重试同步」。
- `Ctrl/Cmd + S` 立即保存，`Ctrl/Cmd + Enter` 发布；粘贴或拖入图片直接上传，拖入 `.md` 文件直接导入。
- 发布前会跑完整校验，不通过时列出原因并可直接跳转到对应字段。
- 最终预览走 `<prefix>/preview/<id>`，与前台共用同一份渲染与消毒结果。

后台页面均带 `noindex, nofollow`，且使用与前台相同的字体与图标；主题令牌集中在 `static/admin/css/theme.css`，改一次两处同时生效。

---

## 公开接口

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/health` | 健康检查 |
| GET | `/api/site` | 站点资料（不含关键词） |
| GET | `/api/posts` | 文章列表，统一信封 `{items,total,page,per_page,has_more}`；支持 `category` / `tag` / `q` / `sort` / `page` / `limit` |
| GET | `/api/posts/<slug>` | 文章详情（渲染后 HTML 已消毒） |
| GET | `/uploads/<path>` | 上传媒体，路径需通过白名单 |
| GET | `/feed.xml` | Atom 订阅源 |
| GET | `/sitemap.xml` | 站点地图 |
| GET | `/robots.txt` | 爬虫规则 |

---

## 测试与构建

### 后端测试

```bash
backend/.venv/bin/python -m pytest backend/tests -q -p no:cacheprovider --basetemp=.tmp/pytest
```

> Windows 下**必须**带 `--basetemp`：系统临时目录的 ACL 会拦住 pytest 创建临时目录。

覆盖范围：接口集成、文章生命周期、Markdown 消毒、上传管线、SEO 输出、序列化裁剪与安全边界（CSRF / 限流 / 响应头）。

### 前端构建

```bash
cd frontend
npm run build     # 产物输出至 frontend/dist/，由 Flask 在生产环境统一托管
```

### 一体化核验（Windows）

```powershell
# 常规：测试 + 前端构建 + API 冒烟 + 配置审计
powershell -ExecutionPolicy Bypass -File .\scripts\verify.ps1

# 上线前严格模式：额外强制要求真实的 HTTPS 公开域名
powershell -ExecutionPolicy Bypass -File .\scripts\verify.ps1 -StrictLaunch
```

不想把生产取值写进开发用 `.env` 时，可放到独立文件里再核验：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\verify.ps1 -StrictLaunch -EnvFile output\launch-check.env
```

具体步骤见 [docs/launch-checklist.md](docs/launch-checklist.md)。

---

## 生产部署（Linux）

推荐 Ubuntu 22.04 / 24.04 LTS 或 Debian 12。把代码与生产 `.env` 放到目标目录（如 `/opt/blog`）后执行：

```bash
# 自动完成：虚拟环境与依赖、前端构建、Systemd 服务、Nginx 反代、Certbot 证书、定时备份
DOMAIN=blog.example.com INSTALL_NGINX=1 INSTALL_TLS=1 TLS_EMAIL=admin@example.com deploy/deploy.sh
```

### 可用部署变量

| 变量 | 默认值 | 作用 |
|---|---|---|
| `DOMAIN` | — | 站点域名（配置 Nginx / 证书时必填） |
| `SERVICE_NAME` | `blog` | Systemd 服务名 |
| `SERVICE_USER` | 当前用户 | 运行服务的系统用户（不存在时自动创建沙箱账号） |
| `APP_PORT` | `8000` | Gunicorn 内部监听端口 |
| `GUNICORN_WORKERS` | `2` | Worker 进程数 |
| `INSTALL_SERVICE` | `1` | 是否注册并启动 Systemd 服务 |
| `INSTALL_NGINX` | `0` | 是否写入 Nginx 反代配置并重载（同时写入 `BLOG_TRUSTED_PROXY_COUNT=1`） |
| `INSTALL_TLS` | `0` | 是否调用 Certbot 申请并安装证书 |
| `TLS_EMAIL` | — | Let's Encrypt 注册邮箱（`INSTALL_TLS=1` 时必填） |
| `RUN_TESTS` | `1` | 部署前是否执行 pytest |
| `BACKUP_KEEP` | `7` | 保留的历史备份份数 |

---

## 备份与容灾

### 备份

使用 SQLite 官方在线备份接口（`sqlite3.Connection.backup`），在 WAL 模式下生成一致性快照，无需停写：

```bash
bash deploy/backup.sh                                   # → storage-backups/blog-backup-<时间戳>.tar.gz
powershell -ExecutionPolicy Bypass -File .\scripts\backup.ps1   # Windows 本地备份
```

> `deploy.sh` 会同时注册 Systemd Timer，每日 03:20 自动备份并清理过期快照。

### 恢复

```bash
bash deploy/restore.sh storage-backups/blog-backup-YYYYMMDD_HHMMSS.tar.gz --yes
```

恢复前会自动创建一份"故障前"临时快照，还原数据库与媒体文件并清理残留的 WAL/SHM。

---

## 安全实践规范

1. **凭证隔离**：真实 `.env` 严禁入库；生产必须使用非默认后台路径与强密码。
2. **反向代理**：Nginx 架构下必须设置 `BLOG_TRUSTED_PROXY_COUNT=1`。保留 `0` 会让所有请求的客户端 IP 变成 `127.0.0.1` —— 登录限流退化成"全站共用一个桶"，审计日志里的 IP 也全是同一个。
3. **传输安全**：对外必须启用 HTTPS，并保持 `BLOG_COOKIE_SECURE=true` 与 HSTS 开启。
4. **权限最小化**：`storage/` 仅允许运行用户读写，不要给 Web 进程开放多余目录。
5. **渲染边界**：正文只存 Markdown；任何对外 HTML 都必须经过 `SafeHTMLCleaner` 消毒，不要绕过渲染层直接输出。
