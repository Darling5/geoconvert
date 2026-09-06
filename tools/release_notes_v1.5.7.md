# v1.5.7 — 用户中心布局优化：卡片同行排列 + 滚动条收进页面

## 优化 / Improved

**中文：**

- **用户中心卡片布局调整**：
  - 「有效期至」与「年度周期」并排同一行——额度总览改为固定 3 列网格（6 卡 = 3×2），窄窗口自动降 2 列仍保持同行
  - 「出品」与「合作伙伴」并排同一行，与版本信息卡片视觉对齐
- **窗口滚动条收进页面**：不再使用浏览器窗口右缘滚动，改由页面内容区内部滚动——滚动条移至 1200px 版心内侧，细窄深色圆角样式，与深色主题融合，hover 变亮
- 切换页面时内容宽度恒定，3D 预览画布不抖动

**English:**

- **User Center card layout**:
  - "Valid Until" and "Annual Cycle" now sit side by side on the same row — quota overview uses a fixed 3-column grid (6 cards = 3×2), auto-collapsing to 2 columns on narrow windows while keeping them on one row
  - "Produced By" and "Partners" now share one row, visually aligned with the version info cards
- **Window scrollbar moved inside the page**: scrolling now happens inside the content area instead of the browser window — the scrollbar sits at the inner edge of the 1200px content column, styled as a slim dark rounded bar that fits the dark theme and brightens on hover
- Content width stays constant when switching pages, so the 3D preview canvas no longer jitters

## 下载 / Download

- `geoconvert-setup-1.5.7.exe`（Windows x64，免管理员安装）

## 说明 / Notes

- 直接覆盖安装即可，账号与剩余额度不受影响
- 在线卫星图（ArcGIS / 天地图注记）需联网；离线环境自动使用内置底图
