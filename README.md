<div align="center">

# geoconvert

Convert OBJ / OSGB / TIF into positioned 3D Tiles (b3dm) for Cesium

将 OBJ / OSGB / TIF 转换为带定位的 3D Tiles（b3dm），可直接加载进 Cesium 三维系统

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

</div>

---

## Overview / 概述

**English:** A Windows desktop tool (browser UI served by a local process) that converts photogrammetry and survey data into **3D Tiles with real-world coordinates**:

- **OBJ** (single file or multi-block directory) → 3-level LOD 3D Tiles
- **OSGB** (Smart3D/context-capture data) → 3D Tiles, keeps the SRS position from metadata
- **TIF** (DOM orthophoto) → terrain-ready tiles with alpha-preserving PNG output

It also provides:

- **Coordinate helper** — paste a share link from Amap / Baidu / Tencent / Bing Maps, get WGS-84 lat/lon auto-filled into the converter
- **3D preview** (bundled offline Cesium) — verify position, fine-tune with gizmo (translate / rotate / per-axis & uniform scale), opacity slider, then **bake** the adjustment into `tileset.json`
- **Model registration** — one click to copy output into your system's `www/public` and append an entry to `models.json`

**中文：** 一个 Windows 桌面工具（本地进程起服务 + 浏览器界面），把倾斜摄影与测量数据转换为**带真实坐标的 3D Tiles**：

- **OBJ**（单文件或多分块整目录）→ 三级 LOD 3D Tiles
- **OSGB**（Smart3D/ ContextCapture 数据）→ 3D Tiles，自动读取元数据中的坐标系定位
- **TIF**（DOM 正射影像）→ 地形瓦片，PNG 输出保留透明通道

附加能力：

- **坐标助手** — 粘贴高德 / 百度 / 腾讯 / 必应地图分享链接，自动换算 WGS-84 经纬度并填入转换参数
- **3D 预览**（内置离线 Cesium）— 校验落点，gizmo 微调（平移 / 旋转 / 单轴与整体缩放）、透明度滑块，确认后把调整**烘焙**进 `tileset.json`
- **模型注册** — 一键把产物拷入系统 `www/public` 并写入 `models.json` 条目

## Quick Start / 快速开始

```bash
# 国内推荐（更快）
git clone https://gitee.com/darling5/geoconvert.git
# 或 GitHub
git clone https://github.com/Darling5/geoconvert.git
cd geoconvert
pip install -r requirements.txt
python -m geoconvert            # 无参数 = 图形界面（自动开浏览器）
python -m geoconvert --help     # 命令行用法
```

典型流程（详见 `tools/manual/geoconvert使用手册.docx`）：

1. 选模型类型 → 上传模型文件夹
2. 没有经纬度？在地图网站拿分享链接 → 粘贴解析 → 填入定位
3. 选导出目录 → 开始转换
4. 3D 预览微调位置 → 保存 → 注册进系统

## Tianditu Map Key / 天地图 Key 配置

3D 预览默认叠加 ArcGIS 在线卫星图。若需**天地图影像 + 中文地名注记**（偏远地区 ArcGIS 高层级无影像时的更好选择），请自行申请 key（[tianditu.gov.cn](https://console.tianditu.gov.cn)，免费）：

1. 复制 `config.example.json` 为 `config.json`（与 `geoconvert` 包同目录 / exe 同目录）
2. 填入 `"tianditu_key": "<你的key>"`
3. 或直接在软件「3D 预览」页的 **天地图 Key** 输入框中填写并保存

`config.json` 属个人配置，已在 `.gitignore` 中排除，不会随仓库分发。

## Build the EXE / 打包 EXE

```bash
pip install pyinstaller
pyinstaller geoconvert.spec --noconfirm        # 产物在 dist\geoconvert\（onedir）
# 可选：Inno Setup 制作安装包（Inno Setup 7）
ISCC.exe installer.iss                          # 产物 dist\geoconvert-setup-x.y.z.exe
```

- onedir 而非 onefile：免解压 + 免杀毒扫描延迟，启动 1~2 秒
- `console=False`：双击无黑窗；终端运行仍正常输出

## Repository Layout / 目录结构

```
geoconvert/          Python 包（转换器核心 + Web UI）
  objconv/           OBJ → 3-level LOD 3D Tiles
  osgb/              OSGB → 3D Tiles（SRS 元数据定位）
  tifconv/           TIF → DOM 瓦片
  webui/             界面（index.html / preview.js / 离线 Cesium）
tools/               测试、手册生成、图标等工具
installer.iss        Inno Setup 安装包脚本
```

## License / 许可

[MIT](LICENSE)
