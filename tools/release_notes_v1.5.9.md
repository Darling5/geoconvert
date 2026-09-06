# v1.5.9 — 坐标转换页新增 3D 地球预览，落针标点结果位置

## 新增 / Added

**中文：**

- **坐标转换 3D 地球预览**：
  - 坐标转换页下方新增 3D 地球卡片，解析成功后自动落大头针标点（蓝色标针 + 悬浮标签显示地址与 WGS-84 坐标），并平滑飞行到结果位置上空 5200 米俯视
  - 底图与「3D 预览」页同源：ArcGIS 卫星图 + 天地图影像/中文地名注记（含灰色占位图检测兜底）；无网络时自动降级内置底图
  - 切换到坐标转换页即后台预载 3D 引擎，首次解析落针零等待；重新输入时旧标点自动清除
  - 支持全部解析来源：坐标串（GCJ-02/WGS-84/BD-09）、高德/腾讯/百度/必应/Google 地图分享链接（含短链展开）、纯地址文本（天地图地理编码）

## 修复 / Fixed

**中文：**

- **高德短链解析再次失效修复**：高德短链（surl.amap.com）的跳转链路新增了 wb.amap.com 中转，且该跳转的 Location 响应头里塞的是未编码的 UTF-8 中文——程序自动跟随时直接报编码错误导致「无法识别」。现改为手动逐跳跟随并还原中文编码，实测 `https://surl.amap.com/PtA5D4u4pD` 可正确解析出坐标与公司名称

**English:**

- **3D globe preview on the Coordinate page**:
  - A 3D globe card is added below the coordinate conversion card; once parsing succeeds, a pin marker is dropped automatically (blue pin with a floating label showing the address and WGS-84 coordinates) and the camera smoothly flies to the result location at 5200 m
  - Same basemap stack as the "3D Preview" page: ArcGIS satellite imagery + Tianditu imagery/Chinese labels (with gray-placeholder detection); silently falls back to the built-in offline basemap without network
  - The 3D engine preloads in the background when the Coordinate page opens, so the first pin drops with zero wait; the old pin clears automatically on new input
  - Works with every parse source: raw coordinates (GCJ-02/WGS-84/BD-09), Amap/Tencent/Baidu/Bing/Google share links (incl. short-URL expansion), and plain address text (Tianditu geocoding)
- **Fixed Amap short-link parsing regression**: Amap added a wb.amap.com hop to the short-link redirect chain, and that hop's Location header contains raw unencoded UTF-8 Chinese — automatic redirect following crashed with an encoding error ("unrecognized"). The expander now follows hops manually and restores the encoding; `https://surl.amap.com/PtA5D4u4pD` verifiably resolves to the correct coordinates and company name

## 下载 / Download

- `geoconvert-setup-1.5.9.exe`（Windows x64，免管理员安装）

## 说明 / Notes

- 直接覆盖安装即可，账号与剩余额度不受影响
- 在线卫星图与地理编码需联网；离线环境使用内置底图
