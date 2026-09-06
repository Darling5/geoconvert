; geoconvert 安装程序脚本
; 编译: ISCC.exe installer.iss
; 产物: dist\geoconvert-setup-{#MyAppVersion}.exe（单文件安装包，安装时一次性解压到用户目录）
; 设计: PrivilegesRequired=lowest → 免管理员/UAC，装到 %LocalAppData%\Programs\geoconvert

#define MyAppName "geoconvert"
#define MyAppVersion "1.5.8"
#define MyAppExeName "geoconvert.exe"
#define MyAppPublisher "智环未来（深圳）科技有限公司"

[Setup]
AppId={{1D9E4B6A-8C2F-4E7B-9A3D-5F0B8C2E4A61}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
UninstallDisplayName=geoconvert 三维模型转换器
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName=geoconvert 三维模型转换器
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
ArchitecturesAllowed=x64compatible
Compression=lzma2/max
SolidCompression=yes
SetupIconFile=tools\appicon.ico
OutputDir=dist
OutputBaseFilename=geoconvert-setup-{#MyAppVersion}

[Languages]
Name: "chs"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: checkedonce

[Files]
Source: "dist\geoconvert\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\geoconvert 三维模型转换器"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{group}\卸载 geoconvert"; Filename: "{uninstallexe}"
Name: "{autodesktop}\geoconvert 三维模型转换器"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent
