# AI 文字工具

已提供文字润色、文案改写、长文摘要、邮件助手、自然翻译、生日祝福六个工作台。
每个工具有独立内置提示词，支持风格、输出语言、补充要求、示例、复制、TXT 下载和最近 20 条记录。

## 配置

在 `services/api/.env` 私下配置业务使用的模型服务：

```dotenv
TOOLDAWN_LLM_BASE_URL=https://your-provider.example/v1
TOOLDAWN_LLM_API_KEY=YOUR_PRIVATE_KEY
TOOLDAWN_LLM_MODEL=YOUR_TEXT_MODEL
TOOLDAWN_AI_TOOL_COST=1
```

使用兼容 Chat Completions 的文本模型，支持 system/user 消息、`max_completion_tokens`、
`stream=false`，返回 `choices[0].message.content` 和 `finish_reason=stop`。
地址包含版本前缀，程序追加 `/chat/completions`。不自动读取开发者 Codex 凭据，
不向前端发送模型密钥。没有完整配置时，工作台展示未开放状态且不能扣分。
开发环境可连接 localhost HTTP 模拟接口，生产环境只接受 HTTPS。
开发测试可设积分费用为 0；正式收费由运营方确定。

从 `services/api` 执行：

```powershell
uv sync --locked
uv run alembic upgrade head
uv run python -m tooldawn.cli install-text-tools
```

安装命令新增缺少的工具，并将未被编辑过的旧文字工具占位记录升级为工作台。
保留已编辑、下架的记录；这些工具可由管理员按需设置为“本站工具 / 可使用 / 上架”。
重启 API 后访问 `/tools/text-polish` 等详情页。

## 模块

- `modules/ai_tools/registry.py`：六套提示词及工具表单定义。
- `gateway.py`：模型 HTTP 调用、超时、输出验证。
- `repository.py`：任务凭证、结果、积分预扣与退还。
- `routes.py`：工具配置、生成、历史、删除结果接口。
- `useTextTool.ts`：页面提交、结果恢复和交互。
- `TextToolWorkspace.vue`、`workspace.css`：桌面双栏、手机纵向布局。

新增提示词工具时注册 `TextTool` 并执行安装命令，同时补充中英文文案。
后台上架的 slug 必须与注册表一致；自定义外部工具不会变成模型调用入口。

## 积分与重试

登录用户每次提交携带 UUID 请求标识。服务端用用户行锁串行处理积分，
保存内容的带密钥摘要，不保存原文；相同请求只预扣一次。
模型请求在数据库事务外执行，不持有数据库锁。成功保存结果，失败退回积分，
失败后重试使用新标识。每个用户同时最多一个任务，每分钟最多 10 次提交。
积分费用来自服务端配置，浏览器不能覆盖。

模型总超时 65 秒，任务租约 120 秒。进程中断后，下次读取历史或提交时，
自动将过期任务标为失败并退分。被标为失败的任务不会再次成功或重复退分。
这不是持久化后台队列：生成期间应保持页面打开；长任务、图片生成及定时自动恢复
应迁移至独立 Worker。当前不向上游自动重试，避免隐式重复模型费用。

结果按纯文本展示，不执行 HTML 或模型返回的脚本。用户可删除结果正文，
任务凭证、幂等摘要及积分流水仍保留；该操作不会退还成功生成的积分。
模型服务商的数据保存策略由所选服务商决定。

## 验证

使用模拟模型接口验证请求结构和返回解析，不产生真实模型费用。
数据库集成测试覆盖余额不足、重复请求、并发、失败退分、超时恢复、用户隔离和删除结果。
真实模型联调需完整配置后另行验证，包括该服务商的协议兼容性和实际输出质量。
