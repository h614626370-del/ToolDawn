# 本地 PostgreSQL 与 Redis

2026-10-24 按用户要求从公网连接切换到 WSL Ubuntu。原远程业务库通过一致性快照复制到本地，远程实例保持原状，之后两个数据库不会自动同步。

| 服务 | Windows 地址 | WSL 容器 |
| --- | --- | --- |
| PostgreSQL 17 | `127.0.0.1:25432` | `tooldawn-local-postgres-1` |
| Redis 8 | `127.0.0.1:26379` | `tooldawn-local-redis-1` |

WSL 配置目录 `/opt/tooldawn-infra`，Compose 项目 `tooldawn-local`。复用本机已有镜像，使用独立的 `tooldawn-local_postgres_data`、`tooldawn-local_redis_data` 数据卷，不与其他项目共享业务库和缓存。端口只绑定回环地址；重启 WSL 或容器不会删除数据。

业务库与用户为 `tooldawn`，测试库与用户为 `tooldawn_test`。Redis 使用 `tooldawn` 用户，只允许 `tooldawn:*` 命名空间。连接凭据保存在被 Git 忽略的 `services/api/.env`，WSL 凭据文件位于 root 专用目录 `/opt/tooldawn-infra/secrets`。

## 启动

在 Windows 项目根目录执行 `scripts/dev.ps1`，脚本识别本地连接配置后会先启动 WSL Compose，再启动前后端。手动检查基础服务：

网站默认端口为 3000。本机 8000 当前无法绑定，因此 API 使用 8001；脚本在未显式指定 API 端口且默认端口无法绑定时自动尝试 8001，并同步配置前端转发地址。也可以明确执行 `scripts/dev.ps1 -ApiPort 8001`。

```powershell
wsl -d Ubuntu -u root -- sh -lc 'cd /opt/tooldawn-infra && docker compose ps'
wsl -d Ubuntu -u root -- sh -lc 'cd /opt/tooldawn-infra && docker compose up -d --wait'
```

`/api/v1/health/ready` 应返回 `catalog_backend: postgres`、`redis: ok`。WSL 关闭时数据库不可用，需要先启动 WSL；不要使用 `docker compose down -v`，该命令会删除数据卷。

## 数据与验证

迁移保留了业务账号、工具、设置和 PostgreSQL 会话，认证及加密根密钥未变。Redis 从空缓存开始，旧限流计数不迁移。

本机 `.runtime/remote-api.env` 保存切换前的连接配置，`.runtime/remote-to-local-20261024.dump` 保存迁移时的业务库快照，均仅当前 Windows 用户可读写并被 Git 忽略。不要把旧快照直接覆盖到已有数据的库。

在 `services/api` 下运行以下命令可验证本地专用测试库（脚本名字沿用原项目，实际连接目标取自 `.env`）：

```powershell
.venv/Scripts/python.exe ../../scripts/check_remote.py
```

远程实例不再是当前开发写入目标。需要恢复远程开发时，先决定以哪一份数据为准并做备份，再调整连接，避免丢失本地新增数据。
