# 站内公告

参考本地 sub2api 的公告发布、铃铛入口及弹窗提醒流程，使用 ToolDawn 现有 Nuxt / FastAPI / PostgreSQL 结构实现。

## 使用

- 后台「运营管理 → 公告管理」(`/admin/announcements`)：创建、编辑、预览、筛选公告；选择草稿、已发布或已归档。归档即停止展示，可再次编辑发布。
- 内容支持 Markdown 标题、列表、引用、表格、链接和代码。前台与后台预览共用渲染器，禁用原始 HTML 和嵌入图片，危险链接不会生成可点击链接。
- 提醒方式为「仅铃铛提醒」或「弹窗提醒」。可见范围为所有访客或仅登录用户。
- 开始与结束时间可留空。后台按设备本地时区填写，接口要求带时区时间，数据库保存时区时间；服务端只返回已发布且处于展示时间内的公告。开始时间包含边界，结束时间不包含边界。
- 前台顶部铃铛打开分页列表，支持查看正文与「本页标为已读」。重要公告在首页、工具列表和工具详情展示，登录、账户页面不主动弹窗。
- 「稍后再看」和关闭不会标为已读，同一浏览器标签页会话内同一版本不重复主动弹出；「我已阅读」确认后保存已读。
- 登录用户已读状态按账号存入数据库；游客仅存当前浏览器。浏览器拒绝存储时本次访问仍可阅读，并提示下次可能再次提醒。游客阅读不计入后台人数，也不自动合并到登录账号。
- 修改公告产生新版本并重新提醒；无实质变化的保存保持版本。后台已读人数统计当前版本的登录用户。并发编辑、旧版本已读请求会返回冲突，避免覆盖新内容。

## 实现与边界

迁移 `0010_announcements` 新建 `announcements` 和 `announcement_reads`。本地开发与专用测试库已迁移。新环境需运行 `python -m alembic upgrade head` 后再启用新版 API。

公共接口 `GET /api/v1/announcements` 返回分页内容、未读数量和最多 10 条最新未读弹窗候选。游客额外获得当前有效公告的版本索引，用于跨分页判断未读。前台在初始化、重新获得焦点及可见标签页的每分钟检查更新；正在阅读公告或输入内容时避免弹窗打断。关闭后可从铃铛继续阅读其他公告。

登录已读接口为 `POST /api/v1/announcements/read`，仅接受公告 ID 和版本，用户身份取自会话。后台列表、新建、更新接口在 `/api/v1/admin/announcements` 下，普通管理员与超级管理员均可管理，未完成初始密码修改的管理员不能操作。所有写入校验请求来源，新建和更新写操作日志。归档保留历史记录，不提供永久删除入口。

原系统设置中的单行站点通知横幅保留；它与有发布状态、时间和已读记录的公告中心是独立内容。公告正文不自动翻译，操作界面支持中英文。

## 验证（2026-10-26）

- PostgreSQL 集成测试：公告权限、来源校验、草稿/归档/未来/到期隐藏、游客与成员可见范围、分页、已读隔离与幂等、并发编辑、更新后重读和操作日志；连同现有后台及运营模块共 15 项通过。
- Markdown 渲染测试 2 项通过，覆盖格式和 HTML / 脚本 URL / 嵌入图片处理。
- 前端类型检查、生产构建通过；本机 Node 24.0.0 的既有版本提示仍存在。
- 浏览器验证发布 → 弹窗 → 已读 → 刷新去重 → 归档隐藏，登录账号已读统计与游客浏览器记忆，五套前台主题、后台浅色/深色、中英文和手机布局。
- 验收公告「公告功能验收（测试）」已归档，不在前台展示。效果截图 `.runtime/announcement-popup-desktop.png`、`.runtime/announcement-popup-mobile.png`、`.runtime/announcement-admin.png` 为验收时保存的画面。

测试命令（在对应服务目录）：

```text
python ../../scripts/check_remote.py tests/test_announcements_postgres.py tests/test_admin_postgres.py tests/test_operations_postgres.py
node --experimental-strip-types --test tests/announcement-markdown.test.mjs
npm run typecheck
npm run build
```

`check_remote.py` 名称为历史沿用，本次已核验并使用本机独立 `tooldawn_test` 数据库。开发端口使用 3001 时，需将 `http://127.0.0.1:3001` 和 `http://localhost:3001` 加入本地 `TOOLDAWN_PUBLIC_ORIGINS`；不能关闭来源校验。
