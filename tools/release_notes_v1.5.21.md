# v1.5.21 — 授权服务器迁移 · 登录与配额保持

## 变更 / Changed

**中文：**

- **授权 / 配额服务器迁移到新节点**（HTTPS，仍为证书固定，客户端内置证书不变）
- 存量账号、设备绑定、剩余转换次数、销售线索数据已完整迁移，登录与转换配额不受影响
- 升级后若提示「登录已过期」，用原账号重新登录一次即可

**English:**

- **License / quota server migrated to a new node** (HTTPS with the same certificate pinning; the client's built-in certificate is unchanged)
- Existing accounts, bound devices, remaining conversions and sales leads were migrated intact; login and quota are unaffected
- If the app reports "login expired" after upgrading, simply sign in again with the same account

## 下载 / Download

- `geoconvert-setup-1.5.21.exe`（Windows x64，免管理员安装）

## 说明 / Notes

- 直接覆盖安装即可，账号与剩余额度不受影响
