# v1.5.20 — 大型正射影像稳定转换 · 3D 预览定位修复 · 界面细节

> 本版为 1.5.16 起的累计更新（1.5.16 ~ 1.5.20）。

## 新增 / Added

**中文：**

- **数值输入框微调控件**：所有数值输入框右侧新增与主题同色的 ▲/▼ 按钮，支持在输入框上滚动鼠标滚轮微调，微调步进 **0.01**
- **3D 预览定位改为提交式**：经纬度 / 高程输入在 **回车、失焦或点击「定位」按钮**后生效，新增「定位」按钮（此前边输边刷新，出现「改经度生效、改纬度不生效」的错觉）
- **内嵌窗口标题栏随主题**：桌面客户端顶栏改为网页主题的深色，不再出现白栏
- **模型转换页新增高程输入**：OBJ / OSGB 提供高程输入框，TIF 提供离地高度输入框
- **高德 place 链接解析**：支持在「3D 预览」页配置自己的高德 Web 服务 Key 以解析地点链接

**English:**

- **Numeric stepper buttons**: every numeric field now has theme-colored ▲/▼ buttons; the mouse wheel over the field also nudges the value with a **0.01** step
- **Commit-style geolocation in 3D preview**: longitude / latitude / elevation now apply on **Enter, blur, or clicking the new "Locate" button** (previously every keystroke refreshed, which felt like "longitude works but latitude doesn't")
- **Themed embedded window title bar**: the desktop client's caption bar now follows the dark web theme instead of showing a white bar
- **Elevation input on the convert page**: OBJ / OSGB get an elevation field; TIF gets a height-above-ground field
- **Amap place-link parsing**: you can now configure your own Amap Web Service key on the 3D Preview page to resolve place links

## 修复 / Fixed

**中文：**

- **超大正射影像（DOM）TIF 转换内存溢出**：改用 tifffile 按段流式解码 + numpy 面积平均降采样，避免 Pillow 12.3 无条件整幅加载导致的 MemoryError；同时处理预乘 alpha 平均，避免透明白底渗色
- **3D 预览相机停在远景、模型不可见**：相机定位改用同步 API（原动画依赖 requestAnimationFrame，标签页被节流时永不推进）
- **冻结版程序启动崩溃（OSError [Errno 22]）**：无控制台环境下 CLI 输出可能写到坏句柄，现统一兜底，任何输出都不会中断启动
- **安装包体积异常膨胀**：打包时排除未使用的 ML / GPU 依赖
- **定位锚点偏差**：3D 预览锚点改用模型包围盒**底面中心**，高程反解更准确

**English:**

- **Out-of-memory on huge orthophoto (DOM) TIFs**: switched to tifffile segment-based streaming decode plus numpy area-averaging downsampling, avoiding Pillow 12.3's unconditional full-image load; premultiplied-alpha averaging is handled to prevent white halo bleed
- **3D preview camera stuck at far distance**: camera positioning now uses the synchronous API (the old tween depended on requestAnimationFrame and never advanced when the tab was throttled)
- **Frozen build crashed at startup (OSError [Errno 22])**: under a console-less context CLI output could write to a broken handle; output is now fully guarded so nothing can abort startup
- **Bloated installer size**: unused ML / GPU dependencies are now excluded from packaging
- **Anchor offset**: the 3D preview anchor now uses the bottom-face center of the model's bounding box for more accurate elevation math

## 改进 / Improved

**中文：**

- 3D 预览 gizmo 悬停容差放宽至 16px，轴上缩放方块最小半径 12px，细轴操作更顺手
- 经纬度 / 高程输入非法时给出明确提示并还原原值

**English:**

- The 3D preview gizmo hover tolerance is widened to 16px and the axis scale handles have a 12px minimum radius, making thin-axis interaction easier
- Invalid longitude / latitude / elevation input now shows a clear message and restores the previous value

## 下载 / Download

- `geoconvert-setup-1.5.20.exe`（Windows x64，免管理员安装）

## 说明 / Notes

- 直接覆盖安装即可，账号与剩余额度不受影响
