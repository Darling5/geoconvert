# v1.5.12 — 修复 3D Tiles 模型跳变、拉远后消失

## 修复 / Fixed

**中文：**

- **修复倾斜摄影模型加载后跳变、缩放拉远后整个模型不显示的问题**：此前 OSGB 转 3D Tiles 时会生成少量无内容（content）的"空壳"瓦片，Cesium 对空壳瓦片既不渲染也不下钻，视距变化时子树整体消失又突然出现（表现为画面跳变）；同时空壳瓦片作为 REPLACE 父级的子级时，细层级流式加载期间粗模被跳过，出现空洞后突然填充。另外根瓦片 geometricError 偏小，拉远到一定距离后 Cesium 直接整棵树不渲染（表现为模型消失）。现转换时自动剔除全部空壳瓦片（子级上提、粗模始终兜底），根瓦片 geometricError 加大，从最近到最远（全球视野）任何视距都保证正常渲染，加载过程平滑无跳变
- **附赠工具**：`tools/fix_tileset_lod.py` 可对已转换好的旧 tileset.json 原地修复（无需重新转换）

**English:**

- **Fix photogrammetry models flickering/jumping and disappearing when zooming out**: the OSGB → 3D Tiles converter used to emit a few content-less "shell" tiles. Cesium neither renders shell tiles nor traverses into them, so subtrees vanished and reappeared as the camera distance changed (visible flicker); when a shell tile sat under a REPLACE parent, the coarse fallback mesh was skipped during streaming, leaving holes that suddenly filled in. The root tile's geometricError was also too small, so past a certain zoom distance Cesium stopped rendering the whole tileset. The converter now collapses all empty shell tiles (children promoted, coarse meshes always available as fallback) and enlarges the root geometricError so the model renders at any viewing distance, from close-up to a global view, with smooth streaming and no popping
- **Bonus tool**: `tools/fix_tileset_lod.py` repairs existing tileset.json files in place (no re-conversion needed)

## 下载 / Download

- `geoconvert-setup-1.5.12.exe`（Windows x64，免管理员安装）

## 说明 / Notes

- 直接覆盖安装即可，账号与剩余额度不受影响
- 用 v1.5.11 转换的模型如出现跳变/消失，用本版重新转换即可（4 GB 级数据约 3 分钟），或运行附带的 fix_tileset_lod.py 原地修复
