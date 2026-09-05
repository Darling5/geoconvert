# geoconvert v1.4.1

## Bug Fix / 缺陷修复

### Gizmo handles now follow the axes / 调整控件跟随坐标轴

- Fixed: the 3 axis scale boxes (small squares on each axis) and the 3 diagonal-move quads (translucent squares between axes) did **not** move together with the axes when the model was translated or rotated — they stuck to the ground / 修复：平移或旋转模型时，轴上的 3 个缩放方块与两轴之间的 3 个斜移半透明方块不跟随坐标轴移动、贴在地表的问题
- Root cause: Cesium polygon entities without `perPositionHeight` ignore the Z coordinate of their vertices; all gizmo polygons now keep their true 3D positions / 根因：Cesium polygon 实体缺 `perPositionHeight` 时会丢弃顶点 Z 坐标贴地渲染；现所有 gizmo 多边形均按真实三维位置渲染
- Verified with pixel-level scene picking: all handles (3 arrows, 3 rings, 3 scale boxes, 3 plane quads) move in sync after a 60 m Z translation / 已通过像素级拾取验证：Z 平移 60 米后箭头、圆环、缩放方块、斜移方块全部同步移动

## Download / 下载

- **geoconvert-setup-1.4.1.exe** — Windows installer (no admin rights required) / Windows 安装包（免管理员权限）
- Install to `%LocalAppData%\Programs\geoconvert`, desktop & start-menu shortcuts created automatically / 安装到用户目录，自动创建桌面和开始菜单快捷方式

## Tianditu (天地图) imagery / 影像底图

The app does not ship a Tianditu API key. After install, open the app → 3D 预览 → fill in your own key in the "天地图 Key" field and save / 安装后在软件 3D 预览页的「天地图 Key」输入框填入你自己的 key 并保存。Apply for a free key at https://www.tianditu.gov.cn / 可在天地图官网免费申请。

Without a key the app still works normally (ArcGIS imagery only) / 不配置 key 也能正常使用（仅 ArcGIS 影像）。
