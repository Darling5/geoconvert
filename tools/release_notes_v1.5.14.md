# v1.5.14 — TIF 正射影像三级 LOD 金字塔

## 新增 / Added

**中文：**

- **TIF 正射影像转换为三级 LOD 金字塔 3D 平面**：此前 TIF 转换只有两级（总览→高清），大尺寸影像在缩放过程中加载策略不够精细。现升级为与倾斜摄影同标准的三级金字塔结构：
  - **L0 总览**：整幅缩到 ≤1024px 单张贴图，远视角只加载这一张，秒开不卡顿
  - **L1 中清**：每块覆盖 2×2 个高清块，纹理 ≤1024px，中距离自动切换
  - **L2 高清**：保持原分辨率（上限 16384px），网格块 ≤2048px，贴近后按视野加载所在高清块
- 层级切换复刻 Cesium 选瓦逻辑验证：远→中→近逐级过渡无跳变、无拉远消失（沿用 v1.5.12 的 GE 修复经验）
- 小图自动降级：影像较小（高清网格 ≤2×2）时自动退化为两级，单块时为单平面，行为与旧版一致
- 透明边缘处理保持 v1.5.13 修复：自带 alpha 通道直接沿用，无白边

**English:**

- **Three-level LOD pyramid for TIF orthophoto conversion**: TIF planes previously had only two levels (overview → full-res). They now use the same three-level pyramid standard as oblique photogrammetry:
  - **L0 overview**: whole image downscaled to ≤1024px, the only tile loaded at far distances — instant display
  - **L1 mid-res**: each tile covers 2×2 high-res cells at ≤1024px, auto-selected at medium range
  - **L2 high-res**: native resolution (up to 16384px) in ≤2048px grid cells; only cells in view load up close
- Level switching verified against a replica of Cesium's tile-selection logic: no popping, no vanishing when zooming out (same GE fix as v1.5.12)
- Small images degrade gracefully: ≤2×2 high-res cells fall back to two levels; single-cell images stay single-plane, same as before
- Transparent-edge handling keeps the v1.5.13 fix: built-in alpha channel preserved, no white borders

## 下载 / Download

- `geoconvert-setup-1.5.14.exe`（Windows x64，免管理员安装）

## 说明 / Notes

- 直接覆盖安装即可，账号与剩余额度不受影响
- 转换后的 TIF 平面与旧版产物格式兼容，可直接替换旧 tileset
