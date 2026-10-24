# 开发约定

## 项目

- 项目暂定名为 **ToolDawn**，面向国际用户提供在线 AI 工具。
- 本目录是新项目的开发目录。已确定使用 Nuxt + Vue + TypeScript 前端，Python + FastAPI 后端，PostgreSQL + SQLAlchemy + Alembic 数据层，Redis 缓存与限流，S3 兼容对象存储。
- 后端 API 与独立 Python Worker 共用业务模块，任务持久化在 PostgreSQL；耗时工具处理放在 Worker 中。
- 按用户最新要求，本地开发使用 WSL Ubuntu 中的独立 Docker PostgreSQL 和 Redis，Compose 项目为 `tooldawn-local`，配置目录 `/opt/tooldawn-infra`，Windows 通过 `127.0.0.1:25432` 和 `127.0.0.1:26379` 连接。不要修改其他项目的数据库或 Redis；凭据放在被忽略的本地配置中，禁止提交。原远程实例保留，切换回远程前需明确确认数据同步方向。
- 模块、代码目录与阶段计划见 `docs/development-plan.md`；具体依赖版本在初始化时验证兼容性并锁定。
- 主域名定位为工具导航，提供搜索、分类和工具入口；具体操作放在独立工具页，首页不做编辑工作台。
- 上游请求指纹由代理负责，本项目通过标准 API 调用代理，不实现客户端指纹模拟或账号池。
- `../参考项目/` 仅供查阅，不在其中开发，也不默认沿用其架构和依赖。
- 管理后台包括仪表盘、监控、操作日志、用户管理、工具与分类管理、模型账号、系统设置、支付套餐和工单。
- 超级管理员首次启动时由服务端生成随机邮箱和密码，保存到被忽略的 `.runtime/initial-admin.json`；首次登录必须修改凭据。后续可在个人中心的安全页面修改邮箱和密码。
- 模型账号的 `base_url`、模型名和 API Key 在后台维护；API Key 使用服务端加密存储，接口和前端只显示是否已配置。
- 业务设置优先保存在 PostgreSQL 的 `system_settings` 表中，站点信息、注册开关、AI 工具开关、调用限额、提示词、模型账号、邮件、Stripe 和积分套餐都可以从后台修改。
- 登录用户可以进入个人中心管理昵称、密码和会话，查看积分、使用记录和工单；首页、搜索、分类和工具详情保持公开访问。
- 工单和使用记录必须做用户隔离；管理端支持工单回复、状态流转和使用记录筛选。

## 工作方式

- 使用中文沟通，代码标识符使用清晰的英文。
- 修改前先阅读相关代码；需求不明确时，先确认影响架构或产品方向的关键问题。
- 优先实现当前需求，保持代码简单，避免无关重构和提前设计。
- 不覆盖或撤销用户已有的修改，不提交密钥、密码等敏感信息。
- 引入依赖前确认必要性，优先采用成熟且维护良好的方案。

## 界面与验证

- 默认使用中文，已支持中英文切换。新界面文案同步维护 `apps/web/i18n/locales/`，切换语言保留当前页面和登录状态。
- 支付支持易支付、支付宝直连、微信 Native、Stripe Checkout 和 Airwallex 托管收银台，供应商、套餐与价格由服务端配置；仅签名校验通过的支付回调可充值入账，浏览器跳转不能确认支付。积分变动保留流水，更新余额使用数据库事务与用户行锁。供应商配置与接入边界见 `docs/payment-providers.md`。
- 内置文字工具在 `services/api/src/tooldawn/modules/ai_tools/` 注册提示词；模型通过服务端 `TOOLDAWN_LLM_*` 配置调用。生成预扣积分、失败退分、请求保持幂等，不保存输入原文，不把模型输出作为 HTML 执行。接入与限制见 `docs/ai-tools.md`。
- 页面兼顾桌面和移动端，交互提供必要的加载、空数据和错误状态。
- 完成修改后执行与改动相关的检查，并说明验证结果及尚未完成的事项。
- 项目具备可运行页面后，启动本地服务并提供访问地址。

## 启动与验证

- 本地开发服务使用 `scripts/dev.ps1`，默认前端 `http://127.0.0.1:3000`，API `http://127.0.0.1:8000`。
- 数据库和 Redis 使用 WSL 本地独立实例；`scripts/dev.ps1` 在检测到上述本地连接配置时先启动对应 Compose 服务。不要把 `.env`、`.runtime/` 或真实密钥提交到 Git。连接与恢复说明见 `docs/local-infra.md`。
- 后端迁移使用 `services/api` 下的 `uv run alembic upgrade head`。远程专用测试库使用项目根目录的 `scripts/check_remote.py`，它会先迁移、种子化，再执行 pytest。
- 前端检查使用 `npm run typecheck` 和 `npm run build`。
- 修改权限、设置、支付、模型账号或工单时，同时检查接口的未登录、普通用户、管理员和超级管理员边界。

## 生图方式

- 用户已指定通过当前 Codex 配置的接口直接调用生图 API，后续生图沿用此方式。
- 从 Codex 配置目录（优先使用 `CODEX_HOME`，否则为 `~/.codex`）的 `config.toml` 读取当前 `model_provider` 对应的 `base_url`，从 `auth.json` 读取 `OPENAI_API_KEY`。
- 默认使用 `gpt-image-2`；用户也允许使用 `gpt-image-2.5-flare` 或 `gpt-image-2.5-sunburst`，切换前确认接口支持。
- 使用 imagegen 技能附带的 `scripts/image_gen.py`，通过进程环境变量 `OPENAI_BASE_URL` 和 `OPENAI_API_KEY` 传入配置；多个方案使用 `generate-batch`。
- 请求方式为 HTTP POST，接口路径为 `/v1/images/generations`。按服务地址拼接路径，避免重复添加 `/v1`；将响应中的 `data[].b64_json` 解码保存为图片。
- 本项目已成功使用该方式生成原型：`gpt-image-2`、`1536x1024`、`high` 质量。图片和提示词保存到 `output/imagegen/`，不同方案使用独立提示词和文件名。
- 密钥仅在运行时读取和传递，不输出到聊天或日志，不写入项目文件。完成后检查图片并展示结果，说明实际使用的模型及文件位置。
