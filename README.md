# 至知 Journal (Paper Notes)

基于 **Flask + Vue 3** 构建的报刊排版风格个人博客系统。轻量级单文件 SQLite 持久化，内置单管理员内容管理后台，具备完备的 Markdown 写作工作流、自动化安全防御、SEO 增强与多端运维支持。

---

## 核心特性

- **报刊版式前台**
  - 经典排版美学：报头封面、大图头条卡片、热点排行、日历归档与多标签筛选。
  - 阅读增强：实时阅读进度、动态目录跟随（TOC Observer）、代码高亮与一键复制、图片灯箱（Lightbox）、相关文章推荐。
  - 交互细节：内置可交互吉祥物桌面宠物（Cat Mascot）、自定义光标微动效、Print 打印专用样式适配。
  - SEO 优化：服务端动态注入 Open Graph / Canonical 标签，内建 Atom Feed (`/feed.xml`)、Sitemap (`/sitemap.xml`) 与 `robots.txt`。

- **写作与内容管理（后台）**
  - 多视图写作台：写作 / 分栏 / 实时预览模式，内置 Markdown 快捷工具栏。
  - 状态保障：本地草稿缓存 + 服务端自动同步 + 版本冲突检测 + 离线自动重试。
  - 发布预检：多维度字段约束与完整性校验，精准定位未满足项。
  - 版本追踪：发布、下架、恢复等关键动作自动留档，支持历史版本对比与一键回滚。
  - 媒体素材库：支持粘贴/拖拽批量上传、图片自动压缩、文章引用关系追踪。
  - 稿件运维：多条件组合筛选、批量状态变更、文章回收站（30 天自动清理）。

- **数据与安全体系**
  - SQLite WAL 模式运行，启动时自动建表与幂等增量迁移。
  - XSS 严格防御：基于 `SafeHTMLCleaner` 白名单的 HTML 消毒处理。
  - 资产隔离：上传文件类型白名单校验，访问路径严格限定。
  - 访问控制：可配置独立管理后台路径（`BLOG_ADMIN_PREFIX`）、防暴力破解登录限流、生产环境启动强校验。

---

## 技术架构

### 技术栈

| 领域 | 选型 | 说明 |
|---|---|---|
| **前端 (SPA)** | Vue 3 + Vue Router 4 + Vite 6 | `<script setup>` 组合式 API，单例 Composables 状态管理 |
| **富文本与样式** | highlight.js + Editorial CSS | 12 层按序层叠样式系统，原生 CSS 变量驱动主题 |
| **后端 API** | Python 3.10+ / Flask 3.x | 路由-服务-仓储三层架构，标准化 JSON 响应 |
| **管理后台** | Flask + Jinja2 + 原生 ES Modules | 服务端渲染独立管理面板，与前台 SPA 完全解耦 |
| **数据与渲染** | SQLite 3 (WAL) + Python-Markdown + Pillow | 自定义渲染扩展、图片安全处理与尺寸压缩 |
| **生产运行** | Gunicorn + Systemd + Nginx + Certbot | 进程守护、沙箱加固、反向代理与自动化 HTTPS |

### 模块结构

```text
BLOG/
├── backend/                  # 服务端 Python 包 (src/blog)
│   ├── pyproject.toml        # 依赖与打包配置 (uv / hatchling)
│   ├── src/blog/
│   │   ├── app.py            # 应用工厂 (Flask 实例、蓝图挂载、错误处理)
│   │   ├── config.py         # 配置加载与生产环境强校验
│   │   ├── security.py       # 会话鉴权、CSRF 防护、登录限流与安全响应头
│   │   ├── serializers.py    # API 响应字段裁剪与序列化
│   │   ├── seo.py            # Atom / Sitemap / Open Graph 动态生成
│   │   ├── uploads.py        # 媒体上传管线与 Pillow 压缩处理
│   │   ├── validation.py     # 表单与字段规则校验
│   │   ├── store.py          # 兼容门面层 (BlogStore)
│   │   ├── routes/           # 路由层 (public / feed / spa / admin_*)
│   │   ├── services/         # 业务服务层 (post / media / profile / dashboard / import)
│   │   ├── repository/       # 数据仓储层 (database / posts / revisions / profile / media)
│   │   ├── markdown_tools/   # Markdown 解析、HTML 消毒与正文统计
│   │   ├── templates/        # 后台 Jinja2 模板
│   │   └── static/           # 后台静态资产 (CSS / JS 模块)
│   └── tests/                # 后端自动化测试套件 (pytest)
├── frontend/                 # 前端 Vue 3 单页应用
│   ├── package.json          # 前端依赖配置
│   ├── vite.config.js        # Vite 构建与开发代理配置
│   └── src/
│       ├── main.js           # 前端入口
│       ├── App.vue           # 根组件
│       ├── router/           # 路由配置 (HTML5 History 模式)
│       ├── services/         # API 请求客户端 (http.js / api.js)
│       ├── composables/      # 响应式状态管理单例 (useSite / usePost / usePosts 等)
│       ├── components/       # 视图组件 (home / post / posts / pet / common)
│       ├── views/            # 页面路由组件 (Home / Posts / Post / About / NotFound)
│       └── styles/           # 样式聚合与 Editorial 主题模块
├── deploy/                   # Linux 生产部署与运维脚本
│   ├── deploy.sh             # 自动化一键部署脚本
│   ├── backup.sh             # WAL 安全备份脚本
│   ├── restore.sh            # 容灾快照恢复脚本
│   ├── blog.service.example  # Systemd 服务单元模板
│   └── nginx.conf.example    # Nginx 反向代理配置模板
├── scripts/                  # 本地开发与运维辅助脚本 (PowerShell / Python)
│   ├── dev.ps1               # 本地前后端联动启动脚本 (含看门狗守护)
│   ├── verify.ps1            # 发布前自动化冒烟与配置核验脚本
│   └── backup.ps1            # Windows 环境本地备份脚本
├── storage/                  # 运行时持久化数据 (数据库、上传媒体；不入版本库)
└── docs/                     # 工程文档与发布检查清单
```

---

## 快速开始

### 环境依赖

- **Python** ≥ 3.10（推荐使用 [uv](https://docs.astral.sh/uv/) 快速管理依赖）
- **Node.js** ≥ 18 / npm ≥ 9

### 1. 本地启动

#### 方式 A：一键联动启动（推荐）

在仓库根目录下运行 PowerShell 脚本，自动启动前后端服务并挂载看门狗守护进程（终端关闭时自动清理子进程）：

```powershell
.\scripts\dev.ps1
```

#### 方式 B：手动分步启动

```bash
# 1. 初始化后端虚拟环境并安装依赖
uv sync --directory backend --group dev --group prod
# 或使用 pip：python -m venv backend/.venv && ./backend/.venv/bin/pip install -e "backend[dev,prod]"

# 2. 启动 Flask 后端（默认监听 127.0.0.1:5000）
backend/.venv/bin/python -m blog
# Windows: .\backend\.venv\Scripts\python.exe -m blog

# 3. 启动前端开发服务器（另开终端）
cd frontend
npm install
npm run dev
# 访问 http://127.0.0.1:5173，Vite 自动将 /api 与 /uploads 请求代理至 5000 端口
```

---

## 环境变量配置

复制 `.env.example` 为 `.env` 后按需调整：

| 变量名 | 默认值 | 作用说明 | 生产环境要求 |
|---|---|---|---|
| `BLOG_SECRET_KEY` | `dev-secret-...` | Flask Session 签名密钥 | **必须替换**为 ≥32 位随机字符串 |
| `BLOG_ADMIN_PASSWORD` | `admin123456` | 管理员后台登录密码 | **必须替换**为 ≥12 位高强度密码 |
| `BLOG_ADMIN_PREFIX` | `/admin` | 管理后台 URL 前缀 | 建议修改为非公开混淆路径 |
| `BLOG_HOST` / `BLOG_PORT` | `127.0.0.1` / `5000` | 后端服务监听地址与端口 | 生产环境由 Gunicorn 指定 |
| `BLOG_DEBUG` | `false` | Flask 调试模式 | 生产环境**必须为 `false`** |
| `BLOG_COOKIE_SECURE` | `false` | Session Cookie 仅限 HTTPS 传输 | HTTPS 环境下**必须设为 `true`** |
| `BLOG_PUBLIC_BASE_URL` | 空 | 站点公开对外根地址（如 `https://example.com`） | 生产环境必填（RSS/OG/Sitemap 依赖） |
| `BLOG_REQUIRE_PUBLIC_BASE_URL` | `false` | 启动时强校验对外根地址 | 生产环境建议设为 `true` |
| `BLOG_TRUSTED_PROXY_COUNT` | `0` | 可信反向代理层数（用于准确获取客户端 IP） | Nginx 单层反代环境下**设为 `1`** |
| `BLOG_HSTS_MAX_AGE` | `31536000` | HSTS 响应头有效期（秒） | 启用 HTTPS 时生效 |
| `BLOG_DATABASE_PATH` | `storage/blog.db` | SQLite 数据库文件路径 | 相对路径自动按项目根目录解析 |
| `BLOG_MAX_UPLOAD_BYTES` | `10485760` (10MB) | 请求体上传最大字节数 | 需与 Nginx `client_max_body_size` 保持一致 |
| `BLOG_MAX_IMAGE_BYTES` | `5242880` (5MB) | 单张图片大小上限 | 超过限制将拒绝上传 |
| `BLOG_MAX_IMAGE_PIXELS` | `20000000` (20MP) | 图片解压防像素炸弹上限 | 超过限制将拒绝处理 |
| `BLOG_SESSION_LIFETIME_SECONDS` | `28800` (8小时) | 后台会话有效时长 | 按需调整 |
| `BLOG_LOGIN_MAX_ATTEMPTS` | `5` | 登录重试次数限制阈值 | 超出后触发 IP 锁定 |
| `BLOG_LOGIN_RATE_WINDOW_SECONDS` | `300` (5分钟) | 登录限流时间窗口 | 超出阈值后的锁定时长 |

> **提示**：系统在生产模式（`BLOG_DEBUG=false`）启动时内置强校验机制。使用默认弱密码、默认密钥或缺失安全配置将直接阻断启动。

---

## 测试与构建验证

### 自动化测试

运行后端测试套件（覆盖集成接口、生命周期、Markdown 消毒、上传管线、SEO 与安全边界）：

```bash
backend/.venv/bin/python -m pytest backend/tests -q
```

### 前端构建

```bash
cd frontend
npm run build
# 产物输出至 frontend/dist，由 Flask 后端在生产环境下统一托管
```

### 发布前一体化核验

Windows 开发环境下提供全流程自动化核验脚本（执行测试 + 前端构建 + API 冒烟测试 + 生产配置合规检查）：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\verify.ps1
# 上线前严格校验模式（强校验公网域名配置）：
powershell -ExecutionPolicy Bypass -File .\scripts\verify.ps1 -StrictLaunch
```

---

## 生产部署 (Linux)

推荐环境：Ubuntu 22.04 / 24.04 LTS 或 Debian 12。

### 一键部署

在服务器目标目录（如 `/opt/blog`）就绪代码及 `.env` 配置文件后，执行自动化部署脚本：

```bash
# 标准部署（自动配置 Python 虚拟环境、构建前端、安装 systemd 服务、配置 Nginx 并申请 TLS 证书）
DOMAIN=blog.example.com INSTALL_NGINX=1 INSTALL_TLS=1 TLS_EMAIL=admin@example.com deploy/deploy.sh
```

### 可用部署环境变量

| 变量 | 默认值 | 作用说明 |
|---|---|---|
| `DOMAIN` | — | 站点访问域名（配置 Nginx 与证书时必填） |
| `SERVICE_NAME` | `blog` | Systemd 服务名称 |
| `SERVICE_USER` | 当前用户 | 运行服务的系统用户（不存在时自动创建沙箱账号） |
| `APP_PORT` | `8000` | Gunicorn 内部监听端口 |
| `GUNICORN_WORKERS` | `2` | Gunicorn Worker 进程数 |
| `INSTALL_SERVICE` | `1` | 是否注册并启动 Systemd 服务 |
| `INSTALL_NGINX` | `0` | 是否写入 Nginx 反代配置并重载 |
| `INSTALL_TLS` | `0` | 是否调用 Certbot 自动申请与配置 HTTPS 证书 |
| `TLS_EMAIL` | — | Let's Encrypt 证书注册邮箱（`INSTALL_TLS=1` 时必填） |
| `RUN_TESTS` | `1` | 部署前是否执行 pytest 测试 |
| `BACKUP_KEEP` | `7` | 保留的历史备份文件数量 |

---

## 备份与容灾恢复

### 数据备份

采用 SQLite 官方在线备份接口（`sqlite3.Connection.backup`），在 WAL 模式下安全生成一致性快照，无锁表停机影响：

```bash
# Linux 环境手动执行备份（数据库快照 + 媒体文件归档）
bash deploy/backup.sh
# 备份产物生成于 storage-backups/blog-backup-<时间戳>.tar.gz

# Windows 本地备份
powershell -ExecutionPolicy Bypass -File .\scripts\backup.ps1
```

> **自动定时备份**：`deploy.sh` 部署时会自动注册 Systemd Timer，每日凌晨 03:20 执行增量备份并清理过期快照。

### 数据恢复

从备份归档快速还原站点数据（恢复前自动创建临时回滚快照）：

```bash
bash deploy/restore.sh storage-backups/blog-backup-YYYYMMDD_HHMMSS.tar.gz --yes
```

---

## 安全实践规范

1. **凭证隔离**：严禁将真实 `.env` 提交至版本库；生产部署必须使用非默认 `BLOG_ADMIN_PREFIX` 与强密码。
2. **反向代理配置**：在 Nginx 代理架构下，必须确保 `BLOG_TRUSTED_PROXY_COUNT=1`，防止客户端 IP 伪造破坏登录限流机制。
3. **传输安全**：对外服务必须启用 HTTPS，并保持 `BLOG_COOKIE_SECURE=true` 与 HSTS 开启。
4. **权限防护**：持久化数据目录 `storage/` 权限严格限定为运行用户所有，禁止对 Web 进程开放多余目录写权限。
