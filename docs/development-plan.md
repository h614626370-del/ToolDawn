# ToolDawn 开发规划

首期规划日期：2026-10-24；状态说明更新：2026-10-29。

本文保留首期规划供设计追溯，后续章节中的目录、接口、部署图和阶段安排不代表当前实现。当前产品范围以 `PRODUCT.md` 和各功能文档为准。

当前已实现六个文字工具、独立图像工作台及图片 Worker、模型账号分组、账户中心、公告与多渠道积分充值。仅提供站内自有工具；本地基础服务使用 WSL PostgreSQL 与 Redis。图片结果暂存数据库，私有对象存储仍待接入。详见 [图片工具](image-tools.md)、[模型账号分组](model-groups.md)、[账户中心](account-center.md) 和 [支付供应商](payment-providers.md)。

## 1. 产品范围

- 主域名首页是公开工具导航：搜索、分类、精选工具、最近更新。
- 导航同时支持站外工具和本站自有工具，清晰显示访问入口。
- 每个工具有独立详情页；本站工具另有工作台，支持输入、运行、结果预览和下载。
- 中文为默认语言，支持英文切换；文案集中管理，工具标识、路由和数据库字段采用英文。
- 风格沿用 `output/imagegen/zh-v4-public-directory.png`：深色顶栏、浅灰主体、黄色强调；工作台按实际操作需求设计。

首期建议交付：图片压缩、文本润色。前者验证文件处理，后者验证模型代理接入。之后增加图片生成，验证长任务与图片结果展示。

按用户追加需求已提前实现积分充值基础和中英文切换。仍暂缓：支付订阅、多租户、团队空间、社区评论、复杂推荐算法、模型账号池。

## 2. 技术与职责

| 部分 | 采用方案 | 职责 |
| --- | --- | --- |
| 前端 | Nuxt + Vue + TypeScript | 导航、详情、工作台、用户中心和管理界面 |
| 样式 | Tailwind CSS + Lucide（@lucide/vue） | 共享样式、响应式布局和操作图标 |
| 国际化 | @nuxtjs/i18n | 中英文界面、语言偏好与服务端渲染 |
| 支付 | Stripe Checkout + 官方 Python SDK | 托管收款、签名回调；套餐由后端配置 |
| 前端状态 | Nuxt 数据加载与组合函数；复杂编辑状态再引入 Pinia | 避免重复保存服务端数据 |
| 后端 | Python + FastAPI + Pydantic | 身份校验、参数校验、业务 API 与上游请求 |
| 数据库 | PostgreSQL + SQLAlchemy + Alembic | 业务持久化、数据访问与数据库迁移 |
| 后台执行 | 独立 Python Worker | 领取任务、文件处理、模型调用与结果保存 |
| Redis | 缓存、限流、短期并发额度 | 不作为任务与结果的唯一持久存储 |
| 文件 | S3 兼容对象存储 | 上传原文件与处理结果，使用短期签名链接 |
| 开发基础服务 | 远程 Docker Compose + 公网直连 | PostgreSQL、Redis 位于指定服务器；S3 与邮件服务后续配置 |
| 部署 | 容器 + Caddy | HTTPS、同域名路由、应用服务与健康检查 |

Nuxt 负责页面呈现，Python 后端负责业务。前端不直接持有代理密钥；不在 Nuxt 服务端重复实现一套业务后端。组件库在脚手架阶段按 Nuxt 版本兼容性选择。

后端计划使用 uv 管理依赖与锁文件，Ruff 做代码检查和格式化，pytest 验证关键行为。API 使用异步数据访问和 HTTP 客户端；每个请求或任务使用独立数据库会话。CPU 密集处理放在 Worker 的独立进程中，不阻塞 API 事件循环或 Worker 租约心跳。

公开目录页与详情页采用服务端渲染；登录后页面避免公共缓存。首期统一主域名路径，上线阶段再决定是否启用工具子域名。

具体依赖版本在脚手架阶段查证并锁定，不在规划中猜测版本。

## 3. 运行结构

```text
浏览器
  |
  v
Caddy
  |-- 页面请求 ------------> Nuxt
  |-- /api/v1/* -----------> FastAPI
  |                           |-- PostgreSQL
  |                           |-- Redis
  |                           `-- S3 兼容存储
  |
  `-- 签名文件请求 ---------> S3 兼容存储

Python Worker
  |-- 从 PostgreSQL 领取持久化任务
  |-- 调用本地处理器或上游代理
  `-- 写入结果文件与任务状态
```

先使用一个代码仓库、一个 Python 包、API 与 Worker 两个运行入口。共享服务代码，分开运行，后续可独立扩容。当前不拆微服务。

上游代理负责请求指纹及其账号策略。ToolDawn 负责本站鉴权、配额、超时、错误提示和必要的限流。

## 4. 建议代码目录

以下目录在开发对应阶段创建，不提前生成空文件或占位实现。

```text
ToolDawn/
  AGENTS.md
  README.md
  docs/
    development-plan.md
  apps/
    web/
      app/
        pages/                  # 公开页面、工作台、用户中心、管理页
        layouts/                # directory / workspace / admin
        components/
          ui/                   # 通用交互组件
          directory/            # 搜索、分类、工具展示
          workspace/            # 输入、上传、任务状态、结果
        composables/            # API 请求、会话、任务轮询
        features/
          image-compress/       # 工具专属界面和参数
          text-polish/
        locales/                # 中文文案，保留国际化边界
      nuxt.config.ts
  services/
    api/
      pyproject.toml
      uv.lock
      alembic.ini
      migrations/               # Alembic 数据库迁移
      src/
        tooldawn/
          __init__.py
          main.py               # FastAPI 应用入口
          worker.py             # 独立任务进程入口
          config.py
          errors.py
          http/                 # 路由、鉴权、请求 ID、中间件
          modules/
            auth/
            catalog/
            files/
            jobs/
            tools/
              image_compress/
              text_polish/
            admin/
          integrations/
            model_gateway/      # 上游代理客户端
            storage/            # S3 操作
            mail/               # 登录邮件
          infra/                # 数据库、Redis、日志初始化
      tests/                    # 关键 API 与数据一致性集成测试
  infra/
    compose.yaml
    Caddyfile
  output/
    imagegen/                   # 已有原型和提示词
```

模块先使用少量文件；复杂后再拆 `routes.py`、`schemas.py`、`service.py`、`repository.py`。Pydantic 请求与响应结构和 SQLAlchemy 数据模型分开，禁止直接序列化包含敏感字段的数据库记录。

## 5. 功能模块

| 模块 | 首期能力 | 边界 |
| --- | --- | --- |
| 工具目录 catalog | 分类、标签、工具列表、关键词搜索、精选、详情 | 支持站外链接和自有工作台，独立于执行器 |
| 用户 auth | 邮箱验证码登录、会话、退出、普通用户与管理员 | 开发使用邮件捕获服务，上线前配置真实邮件供应商 |
| 文件 files | 上传凭证、上传完成校验、元数据、签名下载、到期清理 | 私有存储；校验所有权、大小、真实文件格式与像素上限 |
| 任务 jobs | 提交、状态、结果、失败原因、取消、历史记录 | PostgreSQL 持久化，幂等、领取租约和超时恢复 |
| 工具 tools | 图片压缩、文本润色，后续图片生成 | 各工具持有专属参数和处理逻辑，复用任务与文件模块 |
| 代理接入 model_gateway | 服务端凭证、连接与读取超时、错误映射、用量记录 | 首期一个服务端配置的代理地址，不开放用户自定义 URL |
| 管理 admin | 工具与分类维护、发布状态、任务排查、用户禁用 | 服务端逐请求校验管理员权限，记录操作审计 |
| 基础服务 | 请求 ID、结构化日志、健康检查、限流 | 不记录令牌、验证码、用户原文和文件内容 |

用户无需登录即可浏览目录。首期运行工具需要登录，方便控制成本和访问历史。管理员由明确的初始化命令创建，不提供默认账号密码。

工具目录只管理展示内容、排序和可见性；内置执行器与参数校验必须存在于代码中。后台新增站外链接不会自动生成可执行工具。

## 6. 页面与 API 草案

| 页面 | 用途 |
| --- | --- |
| `/` | 搜索、分类入口、精选工具、最近更新 |
| `/tools` | 搜索结果、分类与标签筛选，URL 保存筛选条件 |
| `/tools/:slug` | 工具说明、示例、限制及使用入口 |
| `/tools/:slug/workspace` | 自有工具的输入、参数、任务进度与结果 |
| `/login` | 邮箱验证码登录 |
| `/account/history` | 本人任务、结果查看与删除 |
| `/admin/tools` | 工具内容、分类与发布维护 |
| `/admin/categories` | 分类名称、图标、颜色与排序 |
| `/admin/users` | 用户搜索、禁用和恢复 |
| `/admin/jobs` | 失败任务排查及脱敏执行信息 |

```text
GET    /api/v1/categories
GET    /api/v1/tools?q=&category=&cursor=
GET    /api/v1/tools/:slug
POST   /api/v1/auth/email-code
POST   /api/v1/auth/verify
POST   /api/v1/auth/logout
GET    /api/v1/me
POST   /api/v1/files/upload-intents
POST   /api/v1/files/:id/complete
GET    /api/v1/files/:id/download
POST   /api/v1/tools/:slug/jobs
GET    /api/v1/jobs?cursor=
GET    /api/v1/jobs/:id
POST   /api/v1/jobs/:id/cancel
DELETE /api/v1/jobs/:id
GET    /api/v1/admin/jobs
GET    /api/v1/admin/tools
POST   /api/v1/admin/tools
PUT    /api/v1/admin/tools/:slug
GET    /api/v1/admin/categories
POST   /api/v1/admin/categories
PUT    /api/v1/admin/categories/:slug
GET    /api/v1/admin/users
PATCH  /api/v1/admin/users/:id
```

私有 API 校验会话、对象所有权或管理员权限。列表限制分页大小；统一错误包含 `code`、可展示的 `message` 和 `request_id`，不向用户透传上游响应正文。

会话使用 HttpOnly Cookie，生产开启 Secure 与适当的 SameSite 策略。写操作校验请求来源并防御 CSRF；验证码限时、限制尝试次数、仅存摘要且单次使用。

## 7. 数据表草案

| 表 | 核心内容 |
| --- | --- |
| users | 用户 ID、规范化且唯一的邮箱、角色、禁用状态、时间 |
| sessions | 用户 ID、会话令牌摘要、到期时间、撤销时间 |
| email_challenges | 邮箱、验证码摘要、有效期、尝试次数、使用时间 |
| categories / tags | 稳定 slug、中文展示文案、排序 |
| tools | slug、类型、执行器标识或外链、文案、发布状态、精选排序 |
| tool_categories / tool_tags | 工具与分类、标签关联 |
| files | 所有者、存储 key、类型、大小、状态、保留期限 |
| jobs | 所有者、工具、参数版本、状态、输入与结果引用、幂等键、租约、取消标记 |
| job_attempts | 尝试编号、领取令牌、执行时间、上游请求 ID、错误类型、用量 |
| audit_logs | 管理员、动作、目标、时间、请求 ID、脱敏变更摘要 |
| credit_wallets / credit_entries | 积分余额、不可覆盖的变动流水、幂等来源与管理员原因 |
| payment_orders | 套餐价格快照、Checkout 会话、支付状态和到账时间 |

任务参数采用各工具专属结构校验，持久化时带版本号；文件引用使用明确关联并校验所有者。优先为工具 slug、用户任务时间、可领取任务建立索引。

搜索首期使用 PostgreSQL 中工具名称、关键词和简介匹配，限制结果规模；根据中文与英文样本评估效果后再扩展，不先引入独立搜索引擎。

## 8. 任务执行与故障处理

1. API 验证身份、参数、文件和额度；在一个数据库事务中写入任务。用户与幂等键建立唯一约束，同键不同参数返回冲突。
2. Worker 用事务和行锁领取可执行任务，设置领取令牌、租约与心跳。只在领取阶段持有数据库锁。
3. 本地处理器处理文件，或代理客户端发起请求；耗时操作均在数据库事务外执行。
4. Worker 保存结果，再通过领取令牌条件更新任务；租约过期的旧执行者不得覆盖新执行者。
5. 前端首期轮询状态，退避并在页面隐藏时减少请求；完成后展示结果。后续有需要再引入 SSE。

状态：`queued -> running -> succeeded / failed / canceled`。请求取消先记标记；Worker 在安全位置确认取消。无法终止的上游请求可能仍产生费用，不承诺取消即停止计费。

任务超时后区分两类情况：本地可安全重复处理的任务允许有限次数重试；已发送且结果未知的付费上游请求进入人工或查询核对流程，不盲目重发。仅在上游支持幂等或能确认未执行时自动重试。

Redis 故障不会丢失任务。涉及付费调用的限流或额度判断不可用时拒绝新增执行，避免无限放行。Redis 仅做加速，任务领取与恢复不依赖它。

删除历史先隐藏记录并安排文件清理；运行中任务先取消并延迟清理，避免 Worker 继续写出无人管理的结果。清理任务需涵盖过期上传、输入、输出及失败产生的孤立文件。

## 9. 开发阶段与验收

以下阶段表是首期验收草案，不作为当前待办清单；当前功能状态见本文开头及对应功能文档，检查结果以实际运行记录为准。

| 阶段 | 交付内容 | 验收标准 |
| --- | --- | --- |
| P0 工程基础 | Nuxt、FastAPI/Worker、Compose、配置模板、Alembic 迁移、健康检查、CI | 新环境按 README 可启动；前端类型检查与构建、后端 Ruff 检查及基础测试通过 |
| P1 目录体验 | 中文首页、搜索筛选、详情页、种子数据、响应式界面 | 导航可用；公开详情能从 HTML 读取标题与正文；移动端无溢出 |
| P2 身份与文件 | 邮箱登录、会话、管理员初始化、私有上传下载 | 本地邮件能完成登录；越权访问被拒绝；超限与伪装文件被拒绝 |
| P3 工具闭环 | 图片压缩、文本润色、持久化任务、历史与结果 | 两个工具端到端可用；重复提交不重复入队；重启不丢任务；失败可解释 |
| P4 管理与上线 | 目录维护、任务排查、清理、真实邮件/存储配置、备份恢复 | 管理权限验证通过；过期文件可清理；数据库恢复演练通过 |
| P5 扩展 | 图片生成、流式输出、用量展示；已提前接入中英文和充值账本 | 收款需商户联调；退款、订阅及工具扣费单独交付 |

六个文字工具在 API 请求中执行，支持积分预扣、失败退分、幂等凭证和最近记录，见 [AI 文字工具](ai-tools.md)。图片任务使用独立 Worker 与 PostgreSQL 持久化队列，支持参考图处理和过期任务恢复，见 [图片工具](image-tools.md)。真实模型质量及费用需结合运营配置联调。

验证重点：跨用户文件与任务隔离、管理员鉴权、验证码与会话生命周期、幂等冲突、Worker 租约恢复、结果未知时禁止重复付费调用、文件格式与像素限制。

页面验证覆盖桌面与移动端，以及加载、空结果、上传失败、任务失败、超时、登录过期等状态。真实代理测试用受控小样本；其余集成测试使用可控的模拟代理。

## 10. 技术核对资料

以下为技术选型的官方资料入口；具体版本和选项在初始化阶段复核。

- Nuxt 路由渲染规则：`https://github.com/nuxt/nuxt/blob/main/docs/1.getting-started/13.server.md`
- FastAPI：`https://fastapi.tiangolo.com/`
- SQLAlchemy：`https://docs.sqlalchemy.org/`
- Alembic：`https://alembic.sqlalchemy.org/`
- Redis 数据类型：`https://redis.io/docs/latest/develop/data-types/`
