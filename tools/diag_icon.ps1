Add-Type -AssemblyName System.Drawing
$exe = Join-Path $env:LOCALAPPDATA 'Programs\geoconvert\geoconvert.exe'
$ico = [System.Drawing.Icon]::ExtractAssociatedIcon($exe)
$ico.ToBitmap().Save((Join-Path $PSScriptRoot 'inst_exe_icon.png'))
Write-Host ('exe icon size: ' + $ico.Size)

$ws = New-Object -ComObject WScript.Shell
$lnks = @(
  "$env:USERPROFILE\Desktop\geoconvert 三维模型转换器.lnk",
  "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\geoconvert 三维模型转换器.lnk"
)
foreach ($lnk in $lnks) {
  if (Test-Path $lnk) {
    $s = $ws.CreateShortcut($lnk)
    Write-Host ($lnk + "`n  Target: " + $s.TargetPath + "`n  IconLocation: [" + $s.IconLocation + "]")
  } else { Write-Host ($lnk + ' 不存在') }
}
Write-Host '--- 桌面/开始菜单里所有 geoconvert 相关 .lnk ---'
Get-ChildItem "$env:USERPROFILE\Desktop\*.lnk", "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\*.lnk" -ErrorAction SilentlyContinue | Where-Object { $_.Name -match 'geoconvert' } | ForEach-Object { $_.FullName }
Write-Host '--- 任务栏固定项 ---'
Get-ChildItem "$env:APPDATA\Microsoft\Internet Explorer\Quick Launch\User Pinned\TaskBar\*.lnk" -ErrorAction SilentlyContinue | ForEach-Object { $_.FullName }
