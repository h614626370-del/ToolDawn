# 远程基础服务

部署日期：2026-10-24。服务器 `154.201.90.159`，目录 `/opt/tooldawn-infra`，Compose 项目 `tooldawn-infra`。

## 连接与隔离

- PostgreSQL 17.11、Redis 8.10.1 运行于独立容器，开机自动恢复。
- 按用户要求改为公网直连：PostgreSQL `154.201.90.159:25432`，Redis `154.201.90.159:26379`。
- 开发机不安装数据库和 Redis，不依赖 SSH 隧道。SSH 仅用于初始化配置与服务器运维。
- PostgreSQL 应用账号 `tooldawn` 仅拥有业务库，测试账号 `tooldawn_test` 仅拥有专用测试库，均非超级用户。
- Redis 禁用默认用户；账号 `tooldawn` 仅允许 `tooldawn:*` 键与频道，禁止危险命令。
- PostgreSQL 卷为 `tooldawn-infra_postgres_data`，Redis 卷为 `tooldawn-infra_redis_data`；Redis 启用 AOF。
- PostgreSQL 内存上限 512 MB，Redis 容器上限 192 MB、数据上限 96 MB，达到上限拒绝写入。

## 凭据

服务器凭据位于 `/opt/tooldawn-infra/secrets/`，上级目录仅 root 可访问。Compose 挂载文件供服务读取，不把密码放入容器环境变量。

本地 `services/api/.env` 被 Git 忽略，文件 ACL 限制为当前 Windows 用户。配置脚本通过 SSH 获取应用及测试凭据，不获取数据库管理员密码，不打印凭据。不要将 `.env`、SSH 私钥或服务器 secrets 加入版本控制。

新部署时将 `infra/` 中四个配置文件复制到服务器指定目录，运行 `python3 /opt/tooldawn-infra/bootstrap.py`。脚本仅在 Linux 指定路径运行，保留已有密码。已部署后不要删除持久卷或随意改写密码文件；数据库账号密码变更需要同步执行 SQL 和更新客户端配置。

## 状态与日志

SSH 登录后执行：

```sh
cd /opt/tooldawn-infra
docker compose ps
docker compose logs --tail=50 postgres redis
```

应用 `/api/v1/health/ready` 检查数据库结构及 Redis 连通性，故障返回 503；`/api/v1/health/live` 仅检查进程存活。

本地 `.env` 已配置公网地址，启动前后端即可连接。当前采用密码认证的 TCP 连接，未配置 TLS。原 `scripts/tunnel.ps1` 保留为手动备用方式，不是启动依赖。

## 手动备份

在服务器执行下列命令创建业务库备份，备份目录仅 root 可访问：

```sh
install -d -m 700 /opt/tooldawn-backups
umask 077
docker exec tooldawn-infra-postgres-1 pg_dump -U postgres -Fc tooldawn > "/opt/tooldawn-backups/tooldawn-$(date +%Y%m%d-%H%M%S).dump"
```

备份还应复制到服务器外保存。当前尚未配置自动备份或完成恢复演练，上线前需要补齐。恢复时使用专用空库核验备份，避免覆盖业务库。
