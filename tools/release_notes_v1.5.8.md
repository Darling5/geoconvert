# v1.5.8 — 离线转换兜底：断网可继续转换，联网自动同步

## 新增 / Added

**中文：**

- **离线转换兜底（加密记账）**：
  - 授权服务器临时不可达时不再直接拦截——已登录用户按最近一次在线额度快照继续转换（本地加密记账），恢复网络后自动逐笔补扣同步到服务器，服务器端零改动
  - 离线可转换笔数上限 3 次；月度/年度额度本地实时扣减，转换失败或取消自动本地退还
  - 本地账本带 HMAC-SHA256 签名（密钥绑定设备+账号令牌），手工篡改视为整本作废
  - 需联网成功使用一次后激活（首次登录/查询即可），快照 7 天有效
- **离线状态可视化**：
  - 右上角账号区显示「⚠ 离线」标记与「⇅ 待同步 N 次」实时徽标
  - 用户中心显示离线模式横幅与待同步笔数，恢复网络自动消失

## 修复 / Fixed

**中文：**

- **models.json 自动探测修复（安装版）**：此前安装版 exe 位于 C:\AppData 下，盘符扫描只到第一层目录，探不到 D:\WEB\zicaiduck\www\public 这类两层深度的系统路径——现改为盘符下扫两层（自动跳过 Windows/Program Files 等系统目录），实测 0.1 秒内正确找到

**English:**

- **Offline conversion fallback (encrypted local ledger)**:
  - When the license server is temporarily unreachable, signed-in users can keep converting based on the last online quota snapshot (encrypted local ledger); records sync back to the server automatically once the network recovers — zero server-side changes
  - Up to 3 offline conversions; monthly/yearly quotas are deducted locally in real time, with automatic local refund on failure or cancel
  - The local ledger is HMAC-SHA256 signed (key bound to device + account token); manual tampering voids the whole ledger
  - Activated after one successful online login/query; snapshot valid for 7 days
- **Offline status visibility**: header shows a "⚠ Offline" badge and a live "⇅ N pending sync" counter; User Center shows an offline banner that disappears once reconnected
- **Fixed models.json auto-detection (installed edition)**: the installed exe lives under C:\AppData and the previous drive scan only covered first-level directories, missing system paths two levels deep such as D:\WEB\zicaiduck\www\public — now scans two levels per drive (skipping Windows/Program Files etc.), verified to find it within 0.1s

## 下载 / Download

- `geoconvert-setup-1.5.8.exe`（Windows x64，免管理员安装）

## 说明 / Notes

- 直接覆盖安装即可，账号与剩余额度不受影响
- 离线兜底与服务器无关，无需服务端升级
- 在线卫星图（ArcGIS / 天地图注记）需联网；离线环境自动使用内置底图
