# geoconvert v1.4.2

## What's New / 新功能

### In-app update check / 软件内更新检查

- On startup the app silently checks GitHub for a newer release; if one exists, a green banner appears at the top with a "前往下载" button that opens the release page / 启动时自动静默检查 GitHub 最新版本，有新版时顶部显示绿色提示条，点「前往下载」直达发布页
- New "检查更新" button in the header (next to the version badge) for manual checks, with instant feedback / 界面右上角新增「检查更新」按钮（版本号旁），可随时手动检查并即时反馈结果
- Version number now shown in the header / 标题栏右侧常驻显示当前版本号
- Checks never block or break the app: network failures are silent on auto-check and clearly reported on manual check / 检查失败不影响使用（自动检查静默跳过，手动检查给出提示）；结果缓存 30 分钟，手动检查强制刷新
- Note: users on v1.4.2 or earlier won't see this feature — it starts notifying from v1.4.3 onward / 注意：v1.4.2 及更早版本不含此功能，从 v1.4.3 起才会收到新版提示

## Download / 下载

- **geoconvert-setup-1.4.2.exe** — Windows installer (no admin rights required) / Windows 安装包（免管理员权限）
- Install to `%LocalAppData%\Programs\geoconvert`, desktop & start-menu shortcuts created automatically / 安装到用户目录，自动创建桌面和开始菜单快捷方式

## Tianditu (天地图) imagery / 影像底图

The app does not ship a Tianditu API key. After install, open the app → 3D 预览 → fill in your own key in the "天地图 Key" field and save / 安装后在软件 3D 预览页的「天地图 Key」输入框填入你自己的 key 并保存。Apply for a free key at https://www.tianditu.gov.cn / 可在天地图官网免费申请。

Without a key the app still works normally (ArcGIS imagery only) / 不配置 key 也能正常使用（仅 ArcGIS 影像）。
