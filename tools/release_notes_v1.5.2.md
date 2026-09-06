# v1.5.2 — 密码显隐 + 确认密码 + Gitee 国内更新源 + 多年续期

## 新增 / New

**中文：**

- 所有密码输入框（登录/注册、注册确认密码、用户中心修改密码 3 项）右侧新增"小眼睛"按钮，一键切换明文/密文显示
- 注册新增"确认密码"输入框，两次输入不一致时提交前即时拦截提示
- 更新检查优先从 Gitee 国内源拉取（GitHub 自动兜底），国内用户检查更新、下载新版更快更稳
- 项目在 GitHub 与 Gitee 双平台同步发布，README 提供双克隆地址
- 服务端：管理后台续期支持 1-10 年多选（未过期在现有效期上叠加、已过期从当天起算），年度配额窗口在有效期内每满一年自动滚动重开；用户列表新增"有效期至"列

**English:**

- Added an eye toggle to every password field (login/register, new confirm-password field, and all 3 password fields in User Center) to show/hide plaintext
- Registration now requires confirming the password, with instant mismatch validation before submit
- Update checks now prefer the Gitee mirror (China-friendly) with GitHub as automatic fallback — faster and more reliable for users in China
- The project is now published on both GitHub and Gitee; README lists both clone URLs
- Server: admin renewal now supports 1-10 years (stacks on the current validity if not expired, restarts from today if expired); the yearly quota window auto-rolls each year within the validity period; the user list shows the "valid until" column

## 优化 / Improved

**中文：**

- 用户中心"年度周期"改为整行显示，不再折行

**English:**

- User Center "Yearly cycle" now occupies a full row instead of wrapping

## 下载 / Download

- `geoconvert-setup-1.5.2.exe`（Windows x64，免管理员安装）

## 说明 / Notes

- v1.5.0 / v1.5.1 用户直接下载覆盖安装即可，账号与剩余额度不受影响
- 服务端已同步升级部署；老客户端不受影响
