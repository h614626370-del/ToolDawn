# 图像工作台架构

站内路由不等于共用目录布局。`/tools/image-generate` 是独立产品入口，共用登录、积分、模型账号与服务端任务体系，视觉和交互拥有自己的空间。

## 前端边界

- `apps/web/app/layouts/workspace.vue`：紧凑顶栏、全窗口高度、继承首页五套主题配色；无目录侧栏、推荐内容或页脚。
- `apps/web/app/pages/tools/image-generate.vue`：静态路由、工具可用性与 SEO。其他工具继续使用 `[slug].vue`，复杂工具未来可按需增加静态入口。
- `apps/web/app/features/image-studio/useImageStudio.ts`：登录、积分、任务提交／轮询、参考图生命周期、作品选择；组件不各自复制请求逻辑。
- `features/image-studio/components/StudioControls.vue`：文生图／图生图、提示词、参考图、比例、质量、透明背景和费用。
- `StudioCanvas.vue`：预览、缩放、拖动、全屏、编辑、继续创作、下载。
- `StudioHistory.vue`：个人作品缩略图和任务状态，可收起以扩大画布。
- `StudioImageEditor.vue`：第三方编辑器适配、按需加载、导出及关闭处理。
- `ImageStudio.vue`：组合上述区域、移动端面板切换和共享反馈。

“新建”清空提示词、临时参考图和画布选择，恢复文生图、方形、标准质量与非透明背景，并重置缩放和提交幂等键；历史作品和积分不受影响。列表刷新不会自动选回旧作品。生成、上传或首次加载期间禁用新建。

目录与工作台共用 `useDirectoryStyle` 的状态和 Cookie，并通过 `directory-palette.css` 共用颜色变量。工作台只继承配色，不继承目录的场景图片和布局；主题切换在两个入口同步，刷新或直接访问也保持选择。移动端使用三个面板，不把桌面三栏压缩成细列。

## 开源组件集成

集成 Filerobot Image Editor 4.8.1（MIT），通过其原生 JavaScript 接口挂载，React 依赖仅用于编辑器内部。组件打开时才加载；主应用保持 Nuxt／Vue。

本地功能包括裁剪、旋转、翻转、调色、滤镜、标注和调整尺寸。图像使用同源接口或本地 Blob，关闭在线翻译和 Cloudimage 服务；中文翻译随应用打包。编辑结果可下载 PNG，也可上传为图生图参考图。原始生成作品不被覆盖。许可证保留在 `apps/web/public/third-party-notices/filerobot-image-editor.txt`。

这里集成的是可复用编辑器，并非复制另一套完整生图平台；生成任务仍走本站已有的账号分组、积分和持久化 Worker。第三方接口收敛在一个适配组件中，后续替换不影响任务业务。

## 后端边界

`modules/image_tools/` 分为输入／输出 schema、参考图解码、数据库任务、路由和上游网关；`image_worker.py` 独立执行。迁移 `0014_image_studio` 添加参考图表及任务选项。详细限制、队列与退分规则见 `image-tools.md`。

页面只读取安全的用户提示；上游错误正文、账号密钥、解密载荷不展示。参考图和任务输入仅加密短暂保存，完成后清空任务输入；永久作品不包含提示词原文。

## 下一阶段

当前是单参考图、单张输出的可用工作台。尚未实现局部重绘蒙版、多参考图、批量生成、图层工程持久化与跨设备草稿。先按实际使用反馈决定优先级；扩展应放在 feature 内，不退回通用详情页堆叠功能。正式扩大使用前，将作品迁移到私有对象存储并明确保留周期。
