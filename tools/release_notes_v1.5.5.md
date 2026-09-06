# v1.5.5 — 坐标转换修复：支持高德短链与地图搜索链接

## 修复 / Fixed

**中文：**

- 修复地图分享链接解析：国内地图分享链接多为短链或纯地址（无坐标），此前直接提示"无法识别"。现自动走三级解析：
  1. 高德短链（如 `surl.amap.com/xxx`）自动展开为长链再取坐标（GCJ-02 → WGS-84）
  2. 必应中国版（`cn.bing.com/maps/search?q=地址`）、Google、高德等搜索链接无坐标时，自动联网做地址检索（天地图地理编码，直接得到 WGS-84）
  3. 保留原有能力：坐标串、高德/腾讯/百度/必应/Google 带坐标链接、GCJ-02/BD-09/WGS-84 手动指定
- 高德主站分享链接 `www.amap.com/?p=POI,纬度,经度` 格式此前解析失败，现已支持
- 短链展开与地址检索强制直连（不走系统代理），挂代理的网络环境下更稳

**English:**

- Fixed map share-link parsing: Chinese map share links are usually short links or plain addresses without coordinates, which previously showed "unrecognized". Parsing now falls back automatically:
  1. Amap short links (`surl.amap.com/xxx`) are expanded to full URLs to extract coordinates (GCJ-02 → WGS-84)
  2. Search links with an address but no coordinates (e.g. `cn.bing.com/maps/search?q=...`) trigger an online geocoding lookup (Tianditu, returns WGS-84 directly)
  3. Existing behavior kept: raw coordinate strings, coordinate-bearing links from Amap/Tencent/Baidu/Bing/Google, manual GCJ-02/BD-09/WGS-84 source selection
- Added support for the `www.amap.com/?p=POI,lat,lng` share format
- Short-link expansion and geocoding bypass the system proxy for reliability

## 下载 / Download

- `geoconvert-setup-1.5.5.exe`（Windows x64，免管理员安装）

## 说明 / Notes

- 地址检索需要联网（天地图服务，国内直连）；短链展开需要能访问对应地图服务
- 直接覆盖安装即可，账号与剩余额度不受影响
