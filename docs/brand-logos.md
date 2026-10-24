# 预置 Logo

超级管理员进入「系统设置 → 站点设置 → 站点 Logo」，选择 03 锐角疾速、04 复古典藏、05 自由签名或 10 街头涂写，然后点击「保存设置」。选择时显示实际尺寸预览，保存后更新后台侧栏、前台页头、页脚及浏览器标签页图标。原太阳标识保留为默认选项。

选择存于现有 system_settings 的 runtime JSON 字段 site_logo，无需数据库迁移。合法值限定为 default、speed、heritage、signature、street；通过现有超级管理员权限、Origin 校验和 revision 并发保护保存，公开站点接口仅返回预置标识。新访客获取当前选择，已经打开的其他页面刷新后同步。

素材来自用户选定的第四轮生图原图，仅裁剪、缩放并压缩为 WebP，没有重新绘制设计。素材在 apps/web/public/images/brand，原图和提示词在 output/imagegen/logo-v4-styles/selected。导航使用独立字母标识，旁边继续显示可配置的站点名称。

浅深色模式和 Logo 选择独立，四个选项使用相同显示尺寸。恢复 default 即可切回原太阳标识。

浏览器图标由 app.vue 统一响应 site-settings，使用每版独立的 64px PNG 地址；保存时刷新站点设置即可更新，不依赖页面路由。恢复默认使用 favicon.svg。
