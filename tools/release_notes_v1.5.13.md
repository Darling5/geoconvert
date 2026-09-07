# v1.5.13 — 修复 3D 预览保存后模型消失 / TIF 白边

## 修复 / Fixed

**中文：**

- **修复 3D 预览中"保存烘焙后模型消失、只剩坐标轴"的问题**：当透明度滑块低于 100% 时点击保存，烘焙并自动重新加载模型后，模型会完全消失且怎么调整都找不回来。原因是 Cesium 渲染引擎的缺陷：半透明样式若在瓦片加载开始前应用，半透明渲染管线会永久失效。现透明度改为在模型瓦片加载完成后再应用，保存后模型保持正常显示（半透明状态也保持）。数据本身无损——此前"消失"的模型文件与位置调整全部完好，把透明度拉回 100% 重新打开预览即可找回
- **修复带透明通道 TIF 正射影像转 3D 平面出现白边的问题**：DJI Terra / Pix4D 等软件导出的 DOM 影像（无数据区为纯白底 + 透明通道），转换后四周会出现一圈实心白边。原因是旧代码丢弃了影像自带的透明通道，白色底变成了不透明像素。现直接沿用影像自身的透明通道，边缘干净透明（无 alpha 的老影像仍按"近黑边缘转透明"处理，行为不变）
- 主系统模型管理页的同款隐患已同步修复

**English:**

- **Fix models vanishing after "Save" in the 3D preview**: with the opacity slider below 100%, saving the baked transform and reloading the model made it disappear entirely (only the gizmo axes remained) with no way to bring it back. Root cause is a Cesium engine flaw: applying a translucent style before tiles start streaming permanently breaks the translucent pipeline. Opacity is now applied after the initial tiles finish loading, so the model stays visible after saving (semi-transparent state included). No data was ever lost — the "vanished" model files and baked transforms are intact; setting opacity back to 100% and reopening the preview restores the model
- **Fix white borders when converting alpha-channel TIF orthophotos to 3D planes**: DOM imagery exported by DJI Terra / Pix4D (white no-data fill + alpha channel) came out with a solid white border around the plane. The old code discarded the image's own alpha channel, turning the white fill into opaque pixels. The built-in alpha channel is now preserved, giving clean transparent edges (TIFs without alpha keep the previous near-black-edge transparency, unchanged)
- The same latent issue in the web system's model manager was fixed as well

## 下载 / Download

- `geoconvert-setup-1.5.13.exe`（Windows x64，免管理员安装）

## 说明 / Notes

- 直接覆盖安装即可，账号与剩余额度不受影响
- 旧版遇到模型消失时：透明度拉回 100% → 重新打开 3D 预览即可找回模型
