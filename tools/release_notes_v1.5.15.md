# v1.5.15 — 离线应急授权（后端故障期间可正常使用）

## 新增 / Added

**中文：**

- **新增离线应急授权能力（企业维护场景）**：授权服务器维护、故障或网络中断期间，持有官方签发授权文件的设备可启用「超级管理员」模式——转换不限次数、不消耗账号额度、无需连接授权服务器；删除授权文件即回到普通账号模式，即时生效
- **授权文件采用 Ed25519 数字签名并绑定设备**：防伪造（没有官方私钥无法签发）、防拷贝（复制到其他电脑无效）；客户端只内置公钥，二进制内不存在任何可用凭据
- **普通用户体验完全不变**：注册 / 登录、免费额度、离线兜底转换等逻辑均无改动；授权文件仅随商务支持按需签发

**English:**

- **Offline emergency authorization (for maintenance scenarios)**: while the license server is under maintenance, down, or the network is offline, devices holding an officially issued authorization file can enable "Super Admin" mode — unlimited conversions, no quota consumption, no server connection required; removing the file instantly returns to normal account mode
- **Authorization files are Ed25519-signed and device-bound**: tamper-proof (cannot be issued without the official private key) and non-transferable (invalid when copied to another machine); the client embeds only the public key — no usable credentials exist inside the binary
- **No change for regular users**: registration / login, free quotas, and the offline fallback flow are untouched; authorization files are issued on demand through business channels only

## 下载 / Download

- `geoconvert-setup-1.5.15.exe`（Windows x64，免管理员安装）

## 说明 / Notes

- 直接覆盖安装即可，账号与剩余额度不受影响
- 需要离线授权支持请联系商务
