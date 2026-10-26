# ToolDawn

中文在线工具导航，使用 Nuxt + Vue + TypeScript 前端和 Python + FastAPI 后端。

当前本地开发已切换为 WSL Ubuntu 的独立 PostgreSQL / Redis，Windows 连接 `127.0.0.1:25432` / `127.0.0.1:26379`。运行 `scripts/dev.ps1` 会先检查并启动本地基础服务。原远程服务器保留；下文“远程 PostgreSQL 与 Redis”是原环境说明，当前无需重新执行远程配置。详见 [本地基础服务](docs/local-infra.md)。

## 当前交付范围

- 导航首页、全部工具、关键词搜索、分类筛选、排序、工具详情与相关工具。
- 当前浏览器收藏、加载与错误提示、404、移动端布局、公开页服务端渲染。
- 独立目录 API，参数校验、请求 ID、健康检查，PostgreSQL 数据模型与 Alembic 初始迁移。
- 只读开发种子模式，无需本机数据库即可预览；生产环境禁止使用种子模式。
- 邮箱验证码登录、可撤销会话、账户页、退出登录、管理员初始化命令。
- 密码登录和邮箱验证码找回密码；重置成功注销全部旧会话。超级管理员不开放邮箱验证码找回，详见 `docs/authentication.md`。
- 管理后台：工具与分类新增、编辑、排序、精选、上下架，以及用户搜索、禁用和恢复。
- 六个 AI 文字工作台：润色、改写、摘要、邮件、翻译、生日祝福；支持积分预扣、失败退分、记录与结果下载。模型服务配置见 [AI 工具说明](docs/ai-tools.md)。
- 中英文切换、积分钱包、后台积分调整、Stripe 充值订单；实际收款需商户配置。
- 文件上传、图片工具和独立任务 Worker 尚未实现。

## 目录与边界

```text
apps/web/app/pages/                  页面与 SEO
apps/web/app/components/directory/   工具目录组件
apps/web/app/components/tools/       工具详情；后续工作台组件
apps/web/app/components/admin/       后台编辑弹窗、外观与分页组件
apps/web/app/pages/admin/            工具、分类与用户管理页面
apps/web/app/components/layout/      顶栏与页脚
apps/web/app/components/ui/          图标和通用状态
apps/web/app/composables/            筛选与本地收藏
apps/web/server/api/                 同域 API 转发，无业务逻辑
services/api/src/tooldawn/http/      中间件、错误响应、健康检查
services/api/src/tooldawn/modules/   按业务拆分的模块
services/api/src/tooldawn/infra/     数据库与 Redis 连接
services/api/migrations/             数据库结构变更
infra/                              远程服务器基础服务配置
```

目录模块内部区分 `routes.py`、`schemas.py`、`repository.py`、`models.py` 与种子内容。后续用户、文件和任务分别创建模块，不集中写入应用入口。

## 本地启动

要求 Node.js 22 或更新版本、Python 3.12、uv。锁文件为 `apps/web/package-lock.json` 与 `services/api/uv.lock`。

PowerShell 终端一：

```powershell
cd D:\hjk\ai-tool-hub\ToolDawn\services\api
uv sync --locked --group dev
uv run uvicorn tooldawn.main:create_app --factory --reload --host 127.0.0.1 --port 8000
```

终端二：

```powershell
cd D:\hjk\ai-tool-hub\ToolDawn\apps\web
npm ci
npm run dev -- --port 3000
```

前端访问 `http://127.0.0.1:3000`，API 文档访问 `http://127.0.0.1:8000/api/docs`。

依赖安装后，也可从项目根目录运行 `.\scripts\dev.ps1`，在后台启动两个服务，日志位于 `.runtime/`。脚本会显示进程 ID；停止时使用 `Stop-Process -Id <进程ID>`。脚本只用于 Windows 本地开发。

端口冲突时使用 `.\scripts\dev.ps1 -WebPort 3001 -ApiPort 8001`。手工启动时，修改 API 端口还需要在前端进程中设置 `$env:NUXT_API_BASE="http://127.0.0.1:8001"`。

## 远程 PostgreSQL 与 Redis

数据库和 Redis 已部署到指定服务器 `154.201.90.159` 的 `/opt/tooldawn-infra`，开发机不安装这两个服务，使用公网直接连接。远程实例独立于服务器原有项目。种子模式与数据库模式显式切换，连接失败不会静默回退。

首次配置连接（已有 `.env` 时拒绝覆盖）：

```powershell
cd D:\hjk\ai-tool-hub\ToolDawn
.\scripts\configure-remote.ps1 -ServerHost 154.201.90.159 -IdentityFile 'D:\ideaWord\服务器\20g\154.201.90.159_id_ed25519'
cd services\api
uv run alembic upgrade head
uv run python -m tooldawn.cli seed-catalog
```

种子导入可重复运行，已有 slug 不会被覆盖。数据库模式使用独立异步会话；查询通过 ORM 参数绑定执行，并将用户输入中的 `%`、`_` 作为普通字符处理。

| 服务 | 公网连接地址 |
| --- | --- |
| PostgreSQL | `154.201.90.159:25432` |
| Redis | `154.201.90.159:26379` |

数据保存在服务器 Docker 卷，无需启动 SSH 隧道。Redis 已接入生命周期、就绪检查和登录限流。S3 后续配置；邮件支持本地文件和 SMTP。远程运维与凭据说明见 `docs/remote-infra.md`。

生产环境必须设置 `TOOLDAWN_ENVIRONMENT=production`、`TOOLDAWN_CATALOG_BACKEND=postgres` 和数据库 URL，另需 Redis、登录密钥、SMTP 和 HTTPS 来源配置；使用生产凭据，先执行迁移，不将种子内容当成自动发布流程。

## 登录与账户

已有远程连接配置后，从项目根目录运行 `.\scripts\setup-auth.ps1`，生成登录摘要密钥并开启文件邮件模式，然后在 `services/api` 执行 `uv run alembic upgrade head`，重启 API。

访问 `/login` 获取验证码。开发邮件写入被忽略的 `.runtime/mail/<验证码请求ID>.eml`，可用邮件客户端或文本编辑器查看，不会真的发到邮箱。配置真实 SMTP 后才会投递邮件。邮箱首次验证后自动创建普通账户，没有默认管理员账号和密码。

管理员通过 `services/api` 中的命令初始化：

```powershell
uv run python -m tooldawn.cli create-admin --email admin@example.com
uv run python -m tooldawn.cli cleanup-auth
```

将示例邮箱替换为自己的邮箱；命令只授予角色，仍通过验证码登录。第二条命令清理过期验证码和会话，可交由部署平台定期执行。收藏目前仍保存在浏览器，不随账户同步。

管理员登录后可从账户页进入 `/admin`。后台要求 PostgreSQL 和身份服务，所有管理 API 逐请求校验管理员身份。工具新增默认为未上架；上架状态与“可使用 / 开发中”分别维护。下架后公开列表、详情和分类数量均不再包含该工具。后台分类数量包含未上架工具。

编辑工具与分类使用版本号防止覆盖其他人的修改；管理操作在同一事务写入审计记录。禁用普通用户会删除其全部会话并作废已发出的验证码；恢复后需要重新登录。后台不提供管理员禁用、角色修改、删除记录、文件上传和任务排查。

配置和身份模块说明见 `docs/authentication.md`。自定义前端端口时，还需将实际来源加入 `TOOLDAWN_PUBLIC_ORIGINS`。

## 支付、积分和多语言

账户 `/account/credits` 已提供余额、充值入口、积分明细和订单。后台 `/admin/orders` 查看订单，用户列表的钱包按钮可查看和调整积分。默认不启用收款，需要自行配置 Stripe 商户密钥、签名密钥和套餐；浏览器支付返回不作为入账依据。

右上角支持中文/English 切换，刷新保留选择。新建的自定义工具文案目前按原文展示。

配置、回调事件、测试方式和未完成的退款/工具计费边界见 [支付与多语言](docs/billing.md)。

## 检查与构建

```powershell
cd services\api
uv run ruff check .
uv run ruff format --check .
uv run pytest
# 只生成 SQL，不连接数据库
$env:TOOLDAWN_DATABASE_URL="postgresql+asyncpg://local:local@localhost/tooldawn"
uv run alembic upgrade head --sql

cd ..\..\apps\web
npm run typecheck
npm run build
```

PostgreSQL 集成测试需要已迁移、已导入种子的专用测试库，设置 `TOOLDAWN_TEST_DATABASE_URL` 后运行 `uv run pytest tests/test_postgres.py`。未配置时明确跳过。GitHub Actions 配置了带 PostgreSQL 的独立验证任务；尚未推送前，不代表远程 CI 已通过。

已配置远程连接时，在 `services/api` 运行 `uv run python ../../scripts/check_remote.py`，自动迁移并重复导入专用 `tooldawn_test` 库，然后执行全部测试和 Redis 命名空间读写验证。该脚本不清空数据库。

生产前端启动：在 `apps/web` 目录运行 `node .output/server/index.mjs`。通过 `NUXT_API_BASE` 指向部署的 Python API；该值只用于服务端，不向浏览器暴露代理密钥。

## 素材

工具预览图片存放于 `apps/web/public/images/`。来源记录于 `docs/assets.md`。已确认的设计原型保存在 `output/imagegen/`。

AI 图片生成工作台位于 `/tools/image-generate`，需要独立图片 Worker。账号分组接入、启动方式、任务恢复及结果存储说明见 [图片工具](docs/image-tools.md)。

完整功能规划见 `docs/development-plan.md`。

站内公告已支持后台发布与归档、Markdown 预览、定时展示、公开/仅登录可见、铃铛与弹窗提醒和版本化已读记录。后台入口为 `/admin/announcements`，使用与验证说明见 [站内公告](docs/announcements.md)。

- 2026-10-26 产品范围调整：本站仅提供自有工具，不收录站外工具。迁移 `0009_internal_tools_only` 删除站外目录记录并禁止新增；原有本站工具、账号和业务记录保留。
