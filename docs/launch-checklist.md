# 生产上线核对清单 (Production Launch Runbook)

本文档定义系统从「本地开发」推进至「生产环境安全运行」的标准化执行步骤与质量卡点。

---

## 阶段一：生产环境配置审计

在生产服务器的 `.env` 配置文件中核对以下关键参数：

| 配置项 | 生产要求 | 风险说明 |
|---|---|---|
| `BLOG_SECRET_KEY` | ≥32 位随机字符 | 严禁使用默认值，否则导致会话伪造 |
| `BLOG_ADMIN_PASSWORD` | ≥12 位高强度密码 | 包含大小写字母、数字及特殊字符 |
| `BLOG_ADMIN_PREFIX` | 自定义混淆路径（如 `/sys-portal-x9`） | 杜绝使用 `/admin`，防止自动化字典扫描 |
| `BLOG_PUBLIC_BASE_URL` | 真实 HTTPS 域名（如 `https://blog.example.com`） | 必须配置，影响 RSS、Sitemap 与 Open Graph |
| `BLOG_REQUIRE_PUBLIC_BASE_URL` | `true` | 启用启动期强校验，防止遗漏域名配置 |
| `BLOG_COOKIE_SECURE` | `true` | 仅允许 HTTPS 传输会话 Cookie |
| `BLOG_DEBUG` | `false` | 必须关闭调试模式，防止敏感信息泄露 |
| `BLOG_TRUSTED_PROXY_COUNT` | `1`（Nginx 单层反代下） | 必须设为 1，确保客户端真实 IP 取自可信 XFF |
| `BLOG_MAX_UPLOAD_BYTES` | `10485760` (10MB) | 需与 Nginx `client_max_body_size` 严格对齐 |

---

## 阶段二：发布前自动化核验

在执行线上部署前，必须在本地或 CI 流水线中通过完整性核验。

**在服务器上执行**（该机的 `.env` 已按阶段一填好）：

```bash
# Linux 部署机上同样可用（脚本为 PowerShell，需 pwsh 7+）：
pwsh -File ./scripts/verify.ps1 -StrictLaunch
```

**在本机执行**（本机 `.env` 通常是开发配置，`BLOG_PUBLIC_BASE_URL` 留空，直接加
`-StrictLaunch` 会被拦下来）。此时把生产取值放进**另一份文件**，用 `-EnvFile` 指过去即可：

```powershell
# 1) 复制一份生产取值模板（该文件不要提交，放 output/ 或仓库外）
Copy-Item .env.example output\launch-check.env
# 2) 按阶段一填写，至少这六项：
#    BLOG_DEBUG=false / BLOG_SECRET_KEY=<≥32 位随机> / BLOG_ADMIN_PASSWORD=<≥12 位强密码>
#    BLOG_ADMIN_PREFIX=/<自定义隐藏路径> / BLOG_PUBLIC_BASE_URL=https://<真实域名>
#    BLOG_REQUIRE_PUBLIC_BASE_URL=true / BLOG_COOKIE_SECURE=true
# 3) 严格核验
powershell -ExecutionPolicy Bypass -File .\scripts\verify.ps1 -StrictLaunch -EnvFile output\launch-check.env
```

`-EnvFile` 的语义：**这份文件是严格核验的唯一配置来源**（不读进程变量、也不回落到开发
`.env`），但只在「严格配置检查」与「冒烟服务」两步生效，`pytest` 仍在日常环境下跑——测试
用例对 `BLOG_TRUSTED_PROXY_COUNT` 之类取值的假设是开发默认值，把生产取值带进测试进程会让
用例失真。开发用的 `.env` 因此可以一直保持「留空、可 http 登录」的状态。

**核验卡点标准**：
- [ ] 后端单元与集成测试套件全部通过（`pytest backend/tests`）
- [ ] 前端构建成功生成 `frontend/dist/` 静态产物（`npm run build`）
- [ ] API 冒烟接口正常响应（`/api/health`, `/api/posts`, `/api/site`）
- [ ] 生产配置安全策略校验无违规项（`[0/3] 严格上线配置检查` 无输出即通过）

---

## 阶段三：Linux 生产一键部署

在目标 Linux 服务器执行标准部署（推荐以具备 sudo 权限的管理员账号运行）：

```bash
# 1. 克隆代码至目标部署目录
sudo mkdir -p /opt/blog && sudo chown $USER:$USER /opt/blog
git clone <REPO_URL> /opt/blog && cd /opt/blog

# 2. 准备生产 .env
cp .env.example .env
nano .env # 按阶段一完成参数配置

# 3. 执行自动化部署（服务注册 + Nginx 配置 + Certbot TLS 证书申请 + 定时备份注册）
DOMAIN=blog.example.com INSTALL_NGINX=1 INSTALL_TLS=1 TLS_EMAIL=admin@example.com deploy/deploy.sh
```

**自动化部署执行管线**：
1. **环境诊断**：Python 3.10+、Node.js 18+、Nginx、Certbot 依赖检查。
2. **依赖就绪**：优先使用 `uv` 初始化 `backend/.venv`（缺失时自动回退 pip）。
3. **自动化测试**：部署机执行 `pytest`，测试失败即刻终止。
4. **前端构建**：执行 `npm install && npm run build` 生成最新静态资源。
5. **系统服务**：写入并启动加固版 Systemd 服务单元（`blog.service`）。
6. **反代与证书**：生成 Nginx 配置，调用 Certbot 申请并部署 TLS 证书。
7. **定时任务**：注册每日凌晨 03:20 执行的 Systemd 备份 Timer（`blog-backup.timer`）。
8. **健康探测**：请求内部端口验证服务状态。

---

## 阶段四：上线后冒烟与健康检查

部署完成后，进行线上功能与状态确认：

1. **核心端点探测**：
   - 访问 `https://<域名>/api/health` 确认返回 `{"status":"ok"}`
   - 访问 `https://<域名>/feed.xml` 与 `https://<域名>/sitemap.xml` 确认 XML 结构正常
   - 访问 `https://<域名>/` 确认前台 UI 渲染正常、静态资源加载无 404
2. **管理后台验证**：
   - 访问 `https://<域名><BLOG_ADMIN_PREFIX>/login` 确认可正常登录
   - 验证后台仪表盘数据、稿件编辑、图片上传功能
3. **定时备份服务确认**：
   - 检查 Timer 状态：`systemctl status blog-backup.timer`
   - 手动触发单次备份验证：`bash deploy/backup.sh`

---

## 阶段五：容灾备份与快速回滚

### 数据快照生成

```bash
# 生成包含 SQLite 在线快照与媒体文件的压缩归档
bash deploy/backup.sh
# 产物存储于 storage-backups/blog-backup-YYYYMMDD_HHMMSS.tar.gz
```

### 故障快速回滚

若上线出现异常，立即执行一键还原：

```bash
# 执行还原（自动创建临时故障前快照 -> 还原数据库与文件 -> 清理残留 WAL/SHM -> 重启服务）
bash deploy/restore.sh storage-backups/blog-backup-<目标快照>.tar.gz --yes
```
