# v1.5.11 — 支持新版 ContextCapture OSGB（OSG v131），局部坐标不再报错

## 修复 / Fixed

**中文：**

- **支持新版 ContextCapture 生成的 OSGB 数据**：较新版本 ContextCapture 输出的 OSGB 文件为 OSG v131（OSG 3.6.5+）格式，启用了二进制括号（binary brackets）块大小标记与新版数组/图元集对象序列化，旧版解析器无法读取导致转换失败。现已完整支持该格式
- **SRS=LOCAL 局部坐标系不再报错**：metadata.xml 中 SRS 为 LOCAL（重建时选择了局部坐标系、无真实地理参考）的数据，此前会直接报错终止。现在自动降级为赤道 ENU 定位完成转换，可在命令行加 `--lat 纬度 --lon 经度` 手动指定模型位置，或导入系统后用「调整位置」功能移动到目标位置

**English:**

- **Support OSGB from recent ContextCapture versions**: OSGB files written by newer ContextCapture releases use the OSG v131 (OSG 3.6.5+) format with binary-brackets block sizes and the new array/primitive-set object serialization, which the old parser could not read (conversion failed). This format is now fully supported
- **SRS=LOCAL no longer aborts the conversion**: datasets whose metadata.xml declares a LOCAL spatial reference (no real georeference) previously failed immediately. They now fall back to an equator ENU placement; you can pass `--lat`/`--lon` to place the model, or use the in-app "Adjust Position" tool after import

## 下载 / Download

- `geoconvert-setup-1.5.11.exe`（Windows x64，免管理员安装）

## 说明 / Notes

- 直接覆盖安装即可，账号与剩余额度不受影响
- 已在 4631 个 OSGB 文件（8 个 Block、4 GB 级数据）上验证全部转换成功
