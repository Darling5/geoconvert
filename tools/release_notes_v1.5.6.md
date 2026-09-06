# v1.5.6 — 3D 预览修复：根治灰色底图 + 模型地下部分正确遮挡 + 高程面板

## 修复 / Fixed

**中文：**

- **根治 3D 预览灰色底图**（两处来源全部处理）：
  1. 天地图影像/注记层限定中国范围请求——境外区域（含未填经纬度、落在赤道 0,0 的模型）天地图各层级均返回「此级别下，该区域无影像」不透明占位灰图，此前会盖住底层真实影像
  2. 新增灰色占位瓦片自动检测：ArcGIS 卫星图在远海/偏远地区中高缩放级别（z14+）会返回「Map data not yet available」灰色占位图（HTTP 200 无法按错误拦截），现自动识别并替换为透明瓦片，透出底层内置底图——**画面最多变糊，永远不会变灰**
- **模型沉入地下仍透视显示的问题**：开启地形深度测试，模型低于地面/海面的部分被地面正确遮挡，不再"穿地透视"
- 新增**模型高程面板**：实时显示模型底部/顶部高程（相对地面），悬空或入地自动标色提示
- 新增**贴地按钮**：一键把模型最低点对齐到地面，自动修正悬空/入地偏移
- 真实卫星影像区域（如深圳）实测无任何误判，天地图中文注记显示正常

**English:**

- **Root fix for gray base maps in the 3D preview** (both sources handled):
  1. Tianditu imagery/annotation layers are now restricted to the China region — outside China (including models without coordinates that land at 0,0) Tianditu returns an opaque "no imagery at this level" placeholder that used to cover the real imagery below
  2. Added automatic gray placeholder-tile detection: ArcGIS World Imagery returns "Map data not yet available" gray placeholders over remote/ocean areas at mid-high zoom (z14+, HTTP 200 so it cannot be blocked by error code). Detected placeholders are replaced with transparent tiles revealing the offline base map below — **the view may get blurry when zoomed past real coverage, but never gray**
- **Models below ground no longer render through the terrain**: depth-testing against the globe is now enabled, so parts of a model sunk under the surface are correctly hidden
- New **model elevation panel**: live bottom/top height readout with colored warnings for floating or buried models
- New **Snap-to-ground button**: one click to align the model's lowest point with the ground
- Verified with real imagery areas (Shenzhen) — no false positives, Chinese annotations render correctly

## 下载 / Download

- `geoconvert-setup-1.5.6.exe`（Windows x64，免管理员安装）

## 说明 / Notes

- 在线卫星图（ArcGIS / 天地图注记）需联网；离线环境自动使用内置底图
- 模型未填经纬度时默认落在赤道，建议转换时填写经纬度或预览后用「调整位置」移动
- 直接覆盖安装即可，账号与剩余额度不受影响
