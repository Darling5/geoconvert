# v1.5.1 — 弹窗修复 + 图形验证码 + 用户中心

## 修复 / Fixes

**中文：**

- 修复 v1.5.0 中弹窗全部挤在窗口左侧、内容被压扁的问题（登录/注册、联系方式、文件浏览弹窗均受影响）
- 原因：新旧弹窗样式使用了同名 CSS 类，相互覆盖导致遮罩层宽度塌陷；现已重命名隔离，所有弹窗恢复屏幕居中显示
- 修复账号绑定第 3 台设备被拒后仍占用名额、导致原设备无法登录的账号锁死问题（服务端同步修复）

**English:**

- Fixed a v1.5.0 bug where all dialogs (login/register, contact, file browser) were squashed against the left edge of the window with broken layout (CSS class-name collision; classes are now isolated and all dialogs center on screen again)
- Fixed an account-lock bug where a rejected 3rd-device binding still consumed a device slot, locking out already-bound devices (fixed server-side)

## 新增 / New

**中文：**

- 登录/注册弹窗新增 4 位字母图形验证码（点击图片可刷新），防止批量注册和暴力破解
- 新增「用户中心」（左侧功能栏入口）：
  - 转换额度总览：本月剩余/上限、年度剩余/上限、累计转换次数、年度周期
  - 个人资料管理：联系电话、邮箱、公司/单位（用户名不可改）
  - 修改密码：校验原密码，改完下次登录生效
  - 关于软件：当前版本、最新版本、手动检查更新
- 界面布局调整：登录/注册入口与登录后的用户信息移至主界面右上方；版本检查统一收纳到用户中心「关于软件」

**English:**

- Added a 4-letter graphical captcha (click to refresh) to the login/register dialog to stop bot registrations and brute-force attempts
- Added a "User Center" (left sidebar entry) with: quota overview (monthly/yearly left & limit, total conversions, yearly cycle), profile management (phone/email/company), password change (old password required), and About (current/latest version, manual update check)
- UI rearrangement: login/register entry and post-login user info moved to the top-right of the main window; version check consolidated into User Center → About

## 下载 / Download

- `geoconvert-setup-1.5.1.exe`（Windows x64，免管理员安装）

## 说明 / Notes

- v1.5.0 用户请直接下载本安装包覆盖安装，账号与剩余额度不受影响
- 账号体系功能（12 次/年 + 2 次/月免费额度、失败自动退还、线索奖励 5 次）与 v1.5.0 一致
