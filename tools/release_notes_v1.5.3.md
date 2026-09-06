# v1.5.3 — 邀请码注册 + 24 小时审核 + 设备注册管控

## 新增 / New

**中文：**

- 注册表单新增"邀请码"选填框：持有效邀请码注册**立即免审核**，注册完成即可转换（邀请码由商务发放，一次性使用）
- 无邀请码注册进入 24 小时审核期：注册成功即可登录、完善资料，转换时提示"账号审核中（注册后最长 24 小时自动通过）"；审核期满自动通过，无需人工等待
- 用户中心额度总览新增账号状态标识，审核状态一目了然
- 服务端注册管控三件套（已同步上线）：每台设备最多注册 2 个账号（防换号刷免费额度）；管理后台新增「设备管理」「邀请码」页签与账号「通过/拒绝」审核按钮；支持设备拉黑/解封与管理员重置密码

**English:**

- Registration now accepts an optional **invite code**: signing up with a valid code skips review entirely — the account is usable immediately (codes are issued by sales, one-time use)
- Without an invite code, new accounts enter a 24-hour review period: you can log in and complete your profile right away, while conversions show "account under review (auto-approved within 24 hours of signup)"; approval is automatic once the period ends
- User Center quota overview now shows the account status badge
- Server-side signup controls (already deployed): max 2 accounts per device (prevents quota farming by re-registering); admin panel adds "Devices" and "Invite Codes" tabs plus Approve/Reject review actions; device block/unblock and admin password reset supported

## 优化 / Improved

**中文：**

- 注册限频放宽至 15 次/小时，多人共用网络注册不再误伤
- 客户端与服务端错误提示统一：审核中 / 已拒绝 / 邀请码无效均有明确中文文案

**English:**

- Registration rate limit relaxed to 15/hour per IP, avoiding false positives on shared networks
- Unified client/server error messages with clear Chinese copy for pending / rejected / invalid invite code

## 下载 / Download

- `geoconvert-setup-1.5.3.exe`（Windows x64，免管理员安装）

## 说明 / Notes

- v1.5.0 – v1.5.2 用户直接下载覆盖安装即可，账号与剩余额度不受影响
- 老客户端注册仍走旧流程（无审核拦截），服务端完全兼容；建议升级以获得邀请码免审通道
