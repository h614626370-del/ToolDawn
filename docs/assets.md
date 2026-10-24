# 图片素材

目录预览使用 Unsplash 图片，在运行时从本站静态目录加载，不向第三方图片站发送浏览器请求。

| 文件 | 内容 | 图片源 |
| --- | --- | --- |
| mountain.jpg | 山景与湖泊 | `https://images.unsplash.com/photo-1464822759023-fed622ff2c3b?auto=format&fit=crop&w=800&q=85` |
| product.jpg | 运动鞋 | `https://images.unsplash.com/photo-1542291026-7eec264c27ff?auto=format&fit=crop&w=800&q=85` |
| food.jpg | 餐食 | `https://images.unsplash.com/photo-1512621776951-a57141f2eefd?auto=format&fit=crop&w=800&q=85` |

图片用于展示工具用途，并非已执行模型的结果。界面图标使用 Lucide 的 @lucide/vue 包；站点 favicon 为项目内的简单矢量标识。

## 中文字体

界面自托管 Noto Sans SC 可变字体的 WOFF2 子集，文件位于 `apps/web/public/fonts/`，遵循同目录 `OFL.txt` 中的 SIL Open Font License。字体覆盖当前界面和工具数据中的字符；用户输入的其他字符使用系统字体回退。

新增中文界面文案后，在项目根目录执行 `uv run --with fonttools --with brotli python scripts/subset-font.py C:/Windows/Fonts/NotoSansSC-VF.ttf` 更新子集。该脚本也接受其他位置的 OFL 授权 Noto Sans SC 源字体，不需要为应用安装字体处理依赖。
