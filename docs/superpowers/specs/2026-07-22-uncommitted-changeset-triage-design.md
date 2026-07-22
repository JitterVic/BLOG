# 至知 Journal — 未提交改动梳理与落地计划

**日期**:2026-07-22
**状态**:已执行(2026-07-23)。基线 **39 条全绿**(用 `--basetemp` 绕过损坏的 `%TEMP%\pytest-of-22937` 后)、F1 修复 + 回归测试通过。改动分三次提交落地(主功能 changeset / 运维备份 / 本计划文档)。F2 属环境问题(删 `pytest-of-22937` 或用 `--basetemp`),无仓库改动。
**触发**:`/brainstorming` → 用户选择「先梳理未提交工作」→「先逐个审查计划外的」→「先出计划再动手」

---

## 1. 背景与目标

上一轮路线图(`linked-wondering-llama.md`)最后一次提交是 `9f27a6f`,当时工作树干净。此后一个会话在**未提交**的情况下写了一大坨代码:

- tracked:12 个文件,约 **+1365 / −59** 行(`app.py` +293、`store.py` +454、`test_backend.py` +346 为大头)
- untracked 功能文件:`backend/static/admin/admin-media.js`、`backend/templates/admin_media.html`、`备份.ps1`
- untracked 废文件:`_inspect.py`、`_out.txt`、`_read_plan.py`、`_t.py`

**目标**:把这批工作安全、可复审、可单独回滚地落地——而不是继续在一个巨型未提交 blob 上叠加。

---

## 2. 盘点:里面到底有什么(以测试为准)

| # | 功能 | 路线图内? | 主要落点 |
|---|------|:--:|------|
| 1 | NBSP 归一化(导入) | ✅ | `store.py` `import_markdown` |
| 2 | Atom feed + sitemap + robots | ✅ | `app.py` `/feed.xml` `/sitemap.xml` `/robots.txt` |
| 3 | 文章页 og: meta 服务端注入 | ✅ | `app.py` `render_spa_index` |
| 4 | 图片管线(剥 EXIF/降采样/缓存头) | ✅ | `store.py` `process_uploaded_image_bytes`、`/uploads` Cache-Control |
| 5 | 备份脚本 | ✅ | `备份.ps1` |
| 6 | 历史版本(快照/预览/恢复) | ❌ 计划外 | `post_revisions` 表 + `_insert_revision`/`list/get/restore_post_revision` + 3 路由 + 写作台面板 |
| 7 | 回收站(软删/恢复/30 天清除) | ❌ 计划外 | `deleted_at` 列 + `trash/restore_post`/`purge_expired_trash` + 2 路由 + 总览分区 |
| 8 | 发布预检(`/validate-post`) | ❌ 计划外 | `validate_post_for_publish` + 端点 + 写作台警告确认 |
| 9 | 浏览计数(每会话一次) | ❌ 计划外 | `click_count` 列 + `increment_post_click` + `post_detail` 会话去重 |
| 10 | 媒体库(引用计数) | ❌ 计划外 | `list_media_assets` + `/admin/media` + 模板/JS |

**5 个计划内 + 5 个计划外。**

---

## 3. 审查结论

**整体质量高,不是半成品草稿。** 安全边界都守住了:

- og 注入所有值走 `html.escape(quote=True)`(`app.py:832-868`);
- catch-all 仍对 `api/` `uploads/` admin 前缀 `abort(404)`(`app.py:892-895`),CLAUDE.md 警告的不变量没破;
- 图片先 `validate_image_upload` 校验再 `process_uploaded_image_bytes` 重编码,`secure_filename` + 时间戳命名(`store.py:1475-1497`);
- 公开接口靠 `published_only`(`status='published'`)天然把 draft 与 trashed 都挡在外面;
- `post_revisions` 表 `FOREIGN KEY ... ON DELETE CASCADE`,`slug TEXT NOT NULL UNIQUE`。

**逐功能判定:5 个计划外功能都值得留。**

- **⑥ 历史版本** — 快照、每篇限量、恢复永远落成草稿、恢复前先存 `pre_restore` 可回退。设计稳。**有 1 个真 bug(见 F1)。**
- **⑦ 回收站** — 软删、`delete_post` 只是 `trash_post` 别名(无硬删路径)、`purge_expired_trash` 确有接线(`app.py:216` 启动 + `app.py:475` 每次进总览)。数据安全:好。
- **⑧ 发布预检** — 纯校验、不改数据。低风险。
- **⑨ 浏览计数** — 每会话每 slug 一次、`viewed_posts` cookie 封顶 80 条、只数已发布。干净。
- **⑩ 媒体库** — 只读(明确不提供删除,防误删被引用图片)。无数据风险。

---

## 4. 需要处理的问题(动手内容)

### F1 —(真 bug)恢复历史版本时 slug 未去重
`restore_post_revision`(`store.py:1393`)直接用 `snapshot.slug or slugify(title)` 写回,**没走 `ensure_unique_slug`**。而 `slug` 是 `UNIQUE`。构造场景:A 改过 slug、其旧 slug 又被 B 占用 → 恢复 A 的旧版本触发 `sqlite3.IntegrityError`;路由只 catch `ValueError`(`app.py:711-714`),于是返回 **500**。
- **修**:改为 `self.ensure_unique_slug(snapshot.get("slug") or title, post_id=post_id)`。
- **补测试**:构造 slug 冲突 → 恢复不 500、且结果 slug 唯一。
- 严重度:边缘场景,但确是缺陷。当前为**代码推断**,复现待 shell 恢复后加测试证实。

### F2 —(测试环境,**已诊断**)pytest 在 setup 阶段就炸
`pytest` 里所有用 `tmp_path` 的用例在 **setup** 抛 `PermissionError [WinError 5] 拒绝访问: C:\Users\22937\AppData\Local\Temp\pytest-of-22937`(traceback:`tmp_path` → `getbasetemp` → `make_numbered_dir` → `os.scandir(root)`)。
- **根因**:`%TEMP%` 里遗留的 `pytest-of-22937` 目录 **ACL 损坏**,当前用户无法访问 → fixture 建 basetemp 失败 → 测试体从未执行(所以此前拿不到任何真实信号)。**与代码/WAL/teardown 均无关**(先前「teardown 型」猜测已被 traceback 推翻)。
- **即时绕过(拿真实信号)**:`--basetemp=<全新干净目录>`,例如
  `python -m pytest backend/tests/ -p no:cacheprovider --basetemp=C:/Users/22937/AppData/Local/Temp/blog-pytest --tb=short -q`
- **永久修**:删掉 `C:\Users\22937\AppData\Local\Temp\pytest-of-22937`(`Remove-Item -Recurse -Force`,必要时管理员);之后无需 `--basetemp`。
- **注意**:setup 修好后,才可能暴露出真正的 teardown 型问题(WAL 句柄没关 → per-test `rmtree` 失败)。若那时出现,再加 `backend/tests/conftest.py` 关连接;否则不需要。
- **目标**:约 39 条(含新增 F1 测试)在 Windows 上全绿,拿到可信基线。

### F3 —(清理)删除废文件
`_inspect.py`、`_out.txt`、`_read_plan.py`、`_t.py` —— 调试残留,删除不提交。

### F4 —(复核)`test_env_int_falls_back_on_invalid_values` 报 failed
读 `env_loader.env_int`(`env_loader.py:61-77`)逻辑是对的(会 `warnings.warn(RuntimeWarning)` 并回退),无 `filterwarnings=error` 配置。疑似顺序/告警假象。**干净跑一遍确认**;若真失败再修。

### 观察项(非阻塞)
- `list_admin_posts` 不带 status 过滤 → trashed 混进总览查询,但**已确认处理正确**(读 `admin_dashboard.html`):有状态筛选下拉(全部/已发布/草稿/回收站)+ 专属徽章 + trashed 只给「恢复为草稿」操作(不能编辑/再删)。非缺陷。
- `purge_expired_trash` 每次渲染总览都跑一次 DELETE;此规模可接受,不改。

---

## 5. 提交分组(建议顺序)

工作树里这些改动**混在同一批文件里**(如 `store.py` 同时含图片/版本/回收站/媒体多个功能;`admin_write.html` 同时含版本面板与预检警告)。要拆成下面的细粒度提交需要 `git add -p` 逐块挑,较繁琐。

**细粒度方案(9+1 提交)**

- **C0 基线+清理**:F3 删废文件 + F2 测试基建修复 + F4 复核。跑绿再往下。(注:源码里已无字面 NBSP 字节,grep 确认;导入期 `.replace("\xa0"," ")` 已在 `store.py:1501`,路线图的旧 NBSP 遗留项无需再处理。)
- **C1 可发现性**:feed/sitemap/robots + `index.html` link + `.env.example` 的 `BLOG_PUBLIC_BASE_URL`。
- **C2 og 注入**:`render_spa_index` + catch-all。
- **C3 图片管线**:`process_uploaded_image_bytes` + `/uploads` Cache-Control。
- **C4 浏览计数**:`click_count` + `increment_post_click` + `post_detail`。
- **C5 历史版本**:schema + store 方法 + 路由 + 写作台面板(**含 F1 slug 修复**)。
- **C6 回收站**:`deleted_at` + trash/restore/purge + 路由 + 总览分区。
- **C7 发布预检**:`/validate-post` + 写作台警告确认。
- **C8 媒体库**:`list_media_assets` + `/admin/media` + 模板/JS。
- **C9 运维/文档**:`备份.ps1` + `.gitignore`(`storage-backups/`)+ `README` + `.env.example` 收尾。

**粗粒度替代(4 提交,省去逐块挑)**
1. 基线+清理(C0)
2. 可发现性+og+图片(C1–C3)
3. 版本+回收站+预检+计数(C4–C7,含 F1)
4. 媒体库+运维文档(C8–C9)

> schema 迁移(`click_count`/`cover_image`/`deleted_at`/`post_revisions`)集中在 `_migrate_schema`/`_create_schema`,拆提交时它会被 C4/C5/C6 共享——细粒度方案里把整块 schema 归到最早触及它的提交(C4),后续提交不再重复动。

---

## 6. 验证(每个提交)

- `python -m pytest backend/tests/ -q` 全绿(约 38 条)
- `cd frontend && npm run build` 通过
- `一键启动.ps1` 起全栈冒烟:
  - `/feed.xml` `/sitemap.xml` `/robots.txt` 三条 200 + content-type,含 published 不含 draft/trashed
  - view-source `/posts/<slug>` 看 og:title/og:image/canonical,恶意标题已转义
  - 后台传手机大图 → 落盘 ≤1920 且无 EXIF;DevTools 看 `/uploads` 命中长缓存
  - 回收站:删→进回收站→恢复成草稿→前台仍 404
  - 历史版本:改两次→预览旧版→恢复(落草稿);**F1 场景:造 slug 冲突后恢复不 500**
  - 媒体库:引用计数正确(封面+正文各计一次)

---

## 7. 风险与回退

- **动 `store.py` 图片/迁移路径前先备份 `storage/`**(AGENTS.md 惯例;`备份.ps1` 可用,另有旧备份 `storage/backup-20260718-113114-phase-next/`)。
- 每个提交独立、可 `git revert`。
- schema 迁移是 `ADD COLUMN` / `CREATE TABLE IF NOT EXISTS`,对现有库幂等、不删列,安全。

---

## 8. 未决 / 依赖

- **F1 复现、F2 诊断、F4 复核、以及一切 pytest/build/git 操作都依赖 shell 恢复**(本会话 Bash 与 PowerShell 的安全分类器全程不可用,只能读、不能跑)。恢复后按 C0 起步。
