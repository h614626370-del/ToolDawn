# 身份模块

## 运行配置

在已有远程连接的基础上运行 `scripts/setup-auth.ps1`，生成本地 `TOOLDAWN_AUTH_SECRET`。该脚本保留已有密钥；不要提交 `.env`。更换该密钥会使已发出的验证码失效，已有会话不受影响。

执行 `uv run alembic upgrade head` 创建 `users`、`email_challenges`、`sessions` 三张表，随后重启 API。身份服务要求 PostgreSQL、Redis 和登录密钥同时配置。

默认文件邮件模式将邮件写入 `.runtime/mail/`；仅用于开发，不提供公开预览接口。文件含验证码，应定期清理。验证码不会出现在接口响应或应用日志中。

真实邮件模式在 `services/api/.env` 中设置：

```dotenv
TOOLDAWN_MAIL_MODE=smtp
TOOLDAWN_SMTP_HOST=smtp.example.com
TOOLDAWN_SMTP_PORT=587
TOOLDAWN_SMTP_SECURITY=starttls
TOOLDAWN_SMTP_USERNAME=your-account
TOOLDAWN_SMTP_PASSWORD=your-secret
TOOLDAWN_SMTP_FROM=ToolDawn <noreply@example.com>
TOOLDAWN_PUBLIC_ORIGINS=["https://your-domain.example"]
```

465 端口通常搭配 `TOOLDAWN_SMTP_SECURITY=tls`，具体按邮件供应商配置。支持验证证书的 STARTTLS 和隐式 TLS，不提供明文 SMTP 模式。生产配置禁止文件投递，要求 HTTPS 来源和真实邮件配置；供应商连通性仍需实际验证。

## 行为

- 邮箱去除首尾空白并转小写，首次验证成功创建普通用户。
- 六位数字验证码有效 10 分钟，每次最多尝试 5 次；数据库行锁保证并发验证只能消费一次。
- 同一邮箱发送间隔 60 秒、每小时最多 10 次；同一 IP 每小时最多发送 20 次，10 分钟最多验证 60 次。
- Redis 使用原子计数并修复缺失的 TTL；Redis 故障返回 503，不放行登录请求。
- 数据库仅存验证码的 HMAC 摘要、随机会话令牌的 SHA-256 摘要。会话默认 30 天，可配置 1–90 天。
- Cookie 使用 HttpOnly、SameSite=Lax、`/api/v1` 路径；生产开启 Secure。所有身份写接口检查完整 Origin 和 Fetch Metadata。
- 退出立即删除当前会话；重新登录替换当前浏览器的旧会话。禁用用户的全部会话立即不可用。
- `/api/v1/auth/*` 和 `/api/v1/me` 响应禁止缓存，账户页和登录页也禁止公共缓存。

Nuxt 开发转发层覆盖客户端提供的 `X-Forwarded-For`，使用真实连接地址。API 仅在本机代理连接时读取单个合法的转发地址。生产反向代理必须覆盖转发头，并按实际代理拓扑限制 Uvicorn 的可信代理范围；增加代理层后应复核 IP 限流。

## 运维与边界

在 `services/api` 运行 `uv run python -m tooldawn.cli create-admin --email <自己的邮箱>` 授予管理员身份。此命令可重复执行，不创建密码，也不自动启用已禁用账户。管理员仍使用邮箱验证码登录，随后从账户页进入 `/admin`，或直接访问 `/admin/tools`、`/admin/categories`、`/admin/users`。

管理 API 使用 `require_admin` 逐请求鉴权，并禁止缓存。写操作校验来源；普通用户和未登录用户分别返回 403 和 401。禁用普通用户会在同一事务撤销全部会话、作废该邮箱已发出的验证码，并写入审计。恢复后需要重新获取验证码登录。后台禁止禁用任何管理员，不开放角色修改。

目录编辑使用不可变 slug 与递增版本号，旧版本提交返回 409。工具上下架独立于执行状态；本站执行器尚未实现，因此只能保存为“开发中”。管理操作与 `audit_logs` 同事务提交，日志保存操作者、动作、目标和提交字段名，不保存验证码、会话令牌或表单值。目前没有审计查询页面。

`uv run python -m tooldawn.cli cleanup-auth` 删除过期验证码和会话；目前未自动调度。用户账户暂不提供自助注销和邮箱修改。收藏仍是浏览器本地数据。

参考了用户提供的 sub2api 项目中邮件冷却时间、原子限流与故障拒绝思路，本模块按 Python 技术栈独立实现，未复制其 Go 源码。

## 验证

无远程配置的单元测试验证来源检查、配置、邮件文件和 Redis 故障处理。设置专用 `TOOLDAWN_TEST_DATABASE_URL` 后，测试覆盖并发单次消费、错误次数、过期、禁用、会话撤销与管理员权限；只清理各测试创建的账户。`scripts/check_remote.py` 在独立 `tooldawn_test` 库执行，并验证真实 Redis 的原子限流、冷却与 TTL。邮件投递在自动化测试中模拟，真实 SMTP 需要部署时另行验证。

## 密码找回

登录页的“忘记密码？”进入 `/forgot-password`，通过账户邮箱验证码设置新密码。
普通用户和普通管理员均可使用；超级管理员继续禁止邮箱验证码认证，需要服务器维护。

- `POST /api/v1/auth/password-reset/code`：提交邮箱，返回验证码请求 ID、有效期和重发等待时间。未知、禁用和超级管理员账户返回相同响应但不发送邮件，不创建账户。
- `POST /api/v1/auth/password-reset`：提交 `email`、`challenge_id`、`code` 和 `new_password`；密码长度 6–128 个字符，不限制字符组合，成功返回 204，随后使用新密码登录。设置密码、修改密码及管理员首次修改凭据采用相同规则，已有密码的登录不受新规则影响。
- 重置码与登录码分开验证，10 分钟有效，最多尝试 5 次；复用现有 Redis 发送限流和 60 秒冷却。
- 重置码绑定账户及签发时的密码状态，密码变更后此前的重置码全部失效。消费验证码、修改密码、注销全部会话和记录审计在同一事务完成。
- 邮件复用后台 SMTP 设置，开发文件邮件位于 `.runtime/mail/`。发送失败会删除验证码，接口仍返回统一响应，避免泄露账户是否存在。

更新代码后先在 `services/api` 执行 `uv run alembic upgrade head`，增加验证码用途字段（迁移 `0007_password_reset`），再重启服务。已有登录验证码默认保持 `login` 用途。
