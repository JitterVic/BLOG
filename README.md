# Flask + Vue Personal Blog

一个参考 [PaperGrid](https://github.com/xywml/PaperGrid) 气质重新实现的个人博客项目，前端使用 Vue 3 + Vite，后端使用 Flask，内容存储切换到了 SQLite，并内置了一个可登录的管理后台。

## 现在支持的能力

- 前台博客展示：首页、文章、归档、标签、关于页
- SQLite 数据库存储：站点资料、文章、草稿都落在本地数据库
- 后台管理入口：登录后可以编辑个人资料、更新关于页内容、维护文章
- Markdown 工作流：支持导入 `.md` 文件、在线预览、保存草稿、发布文章
- 文件上传：支持头像上传和正文图片上传

## 目录结构

```text
backend/    Flask API、管理后台模板、数据库访问层
frontend/   Vue 前端页面
storage/    SQLite 数据库和上传文件
```

## 本地运行

1. 安装后端依赖

```bash
python -m pip install -r requirements.txt
```

2. 启动 Flask 后端

```bash
python backend/app.py
```

3. 安装前端依赖

```bash
cd frontend
npm install
```

4. 启动 Vue 前端开发服务器

```bash
npm run dev
```

前端默认运行在 `http://127.0.0.1:5173`，并通过 Vite 代理访问 Flask 的 `/api`。

## 使用 `.env`

项目根目录已经支持自动读取 `.env`。你只需要直接运行：

```bash
python backend/app.py
```

后端会自动加载根目录下的 `.env`，不需要额外传参。

当前可配置的主要变量：

```bash
BLOG_SECRET_KEY=change-me-before-deploy
BLOG_ADMIN_PASSWORD=admin123456
BLOG_ADMIN_PREFIX=/admin
BLOG_DATABASE_PATH=storage/blog.db
BLOG_HOST=127.0.0.1
BLOG_PORT=5000
BLOG_DEBUG=false
```

- `.env` 已加入忽略规则，不会被提交
- `.env.example` 可以作为服务器或新环境的配置模板
- `BLOG_DATABASE_PATH=storage/blog.db` 这种相对路径会自动按项目根目录解析

## 后台入口

默认后台地址：`/admin/login`

默认后台密码：`admin123456`

建议你在部署前一定修改下面这些环境变量：

```bash
BLOG_SECRET_KEY=replace-with-a-random-secret
BLOG_ADMIN_PASSWORD=replace-with-a-strong-password
BLOG_ADMIN_PREFIX=/your-hidden-admin-path
BLOG_DATABASE_PATH=/absolute/path/to/blog.db
BLOG_HOST=127.0.0.1
BLOG_PORT=5000
BLOG_DEBUG=false
```

说明：

- `BLOG_ADMIN_PREFIX` 可以把后台入口从 `/admin` 改成你自己的隐藏路径，更接近你想要的“后门入口”
- `BLOG_DATABASE_PATH` 不配置时，默认使用 `storage/blog.db`
- 上传的头像和文章图片默认存放在 `storage/avatars` 和 `storage/media`

## Markdown 发布流程

1. 登录后台
2. 在文章编辑区导入 `.md` 文件，或直接粘贴 Markdown 正文
3. 点击“预览文章”检查排版和摘要
4. 保存草稿，确认无误后再发布
5. 如果正文里需要图片，可以先在右侧上传图片，再把返回的 URL 插入 Markdown

## 构建前端

```bash
cd frontend
npm run build
```

构建后，Flask 会自动托管 `frontend/dist` 里的静态文件。

## 部署前建议

- 修改默认后台密码和 `secret key`
- 把 `BLOG_ADMIN_PREFIX` 设成不容易猜到的路径
- 关闭 `BLOG_DEBUG`
- 备份 `storage/blog.db` 和 `storage/` 上传目录
- 如果是正式服务器，建议使用 Nginx + Gunicorn / Waitress 之类的生产部署方式，而不是 Flask 自带开发服务器

## 第一阶段上线需求说明

当前项目已按“个人主页优先 + 轻量上线 + 单管理员后台”的方向推进：

- 首页定位为个人主页，突出头像、昵称、身份、简介、联系方式、精选/最新文章和关注标签。
- 关于页展示更完整的个人资料、动态记录和联系入口。
- 文章页补齐了未发布/不存在文章的友好提示，并优化了 Markdown 图片、表格、代码块等基础阅读样式。
- 后台继续保持单管理员模式，支持维护首页标题、身份、简介、关于页、头像、文章和正文图片。
- 后台文章可以保存为草稿/下架、发布、设置为首页精选，也可以删除。
- 草稿文章不会出现在前台 API 和页面中。

### 上线前检查清单

1. 修改 `.env` 中的 `BLOG_SECRET_KEY` 和 `BLOG_ADMIN_PASSWORD`。
2. 将 `BLOG_ADMIN_PREFIX` 改成不容易猜到的后台路径。
3. 确认 `BLOG_DEBUG=false`。
4. 执行 `cd frontend && npm run build` 生成前端静态文件。
5. 备份 `storage/blog.db`、`storage/avatars` 和 `storage/media`。
6. 登录后台确认首页资料、关于页文案、联系方式和已发布文章内容。

